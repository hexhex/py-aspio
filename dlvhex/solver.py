import io
import signal
import weakref
from subprocess import Popen, PIPE, TimeoutExpired  # type: ignore
from typing import Any, Generic, Iterable, Iterator, Mapping, Sequence, Tuple, TypeVar, Union
from .errors import UndefinedNameError, SolverError, SolverSubprocessError
from .helper import CachingIterable, StreamCaptureThread, TemporaryNamedPipe
from .input import InputSpec, StreamAccumulator
from .output import OutputSpec
from .parser import parse_answer_set, ParseException  # type: ignore
from .registry import Registry
from . import program as p  # noqa

__all__ = [
    'Solver',
]


class Solver:
    '''Interface to the dlvhex2 solver.'''

    # TODO: Check what encoding dlvhex2 expects (on stdin and for input files) -- this is not supposed to be an option, but the encoding that dlvhex2 uses to read from stdin (and input files)
    default_encoding = 'UTF-8'

    # TODO: Some way to pass dlvhex options like maxint
    def __init__(self, *, executable: str = None) -> None:
        '''Initialize a dlvhex2 solver instance.

        @param executable The path to the dlvhex2 executable. If not specified, looks for "dlvhex2" in the current $PATH.
        '''
        self.executable = executable if executable is not None else 'dlvhex2'
        self.encoding = Solver.default_encoding

    def run(self, program: 'p.Program', input_args: Sequence[Any], cache: bool) -> 'Results':
        '''Run the dlvhex solver on the given program.'''
        # No input/output spec given? This is equivalent to using an empty spec.
        input_spec = program.input_spec
        if input_spec is None:
            input_spec = InputSpec.empty()
        output_spec = program.output_spec
        if output_spec is None:
            output_spec = OutputSpec.empty()

        with TemporaryNamedPipe() as tmp_input_name:
            args = [
                self.executable,
                # only print the answer sets themselves
                '--silent',
                # only capture relevant predicates
                '--filter=' + ','.join(output_spec.captured_predicates()),
                # wait for a newline on stdin between answer sets
                '--waitonmodel',
                # tell dlvhex2 to read our input from the named pipe
                tmp_input_name,
            ]
            args.extend(program.file_parts)
            # Start dlvhex2 subprocess.
            # It needs to be running before we pass any input on the named pipe, or we risk a deadlock by filling the pipe's buffer.
            process = Popen(
                args,
                stdin=PIPE,
                stdout=PIPE,
                stderr=PIPE,
            )
            # with io.TextIOWrapper(process.stdin, encoding=self.encoding) as text_stdin:
            with open(tmp_input_name, 'wt', encoding=self.encoding) as text_stdin:
                # Map input data and pass it over stdin
                input_spec.perform_mapping(input_args, StreamAccumulator(text_stdin))
                # Additional rules required for output mapping
                text_stdin.write('\n'.join(str(rule) for rule in output_spec.additional_rules()))
                # Pass code given as string over stdin
                for code in program.code_parts:
                    text_stdin.write(code)
            # At this point the input pipe is flushed and closed, and dlvhex2 starts processing
            return Results(
                answer_sets=AnswerSetParserIterable(DlvhexLineReader(process, self.encoding)),
                output_spec=output_spec,
                registry=program.local_registry,
                cache=cache
            )


T = TypeVar('T', covariant=True)


class ClosableIterable(Generic[T], Iterable[T]):
    def close(self):
        pass


class DlvhexLineReader(ClosableIterable[str]):
    '''Wraps a process and provides its standard output for line-based iteration.

    It is only possible to iterate *once* over a DlvhexLineReader instance.

    If the process exits with a return code other than 0,
    a SolverSubprocessError will be thrown during iteration, containing the return code and stderr output of the process.
    '''

    def __init__(self, process: Popen, encoding: str) -> None:
        self.process = process
        self.stdout_encoding = encoding
        # self.closed = False
        self.iterating = False
        #
        # We need to capture stderr in a background thread to avoid deadlocks.
        # (The problem would occur when dlvhex2 is blocked because the OS buffers on the stderr pipe are full... so we have to constantly read from *both* stdout and stderr)
        self.stderr_capture_thread = StreamCaptureThread(self.process.stderr)
        self.stderr_capture_thread.start()
        #
        # Set up finalization. Using weakref.finalize seems to work more robustly than using __del__.
        # (One problem that occurred with __del__: It seemed like python was calling __del__ for self.process and its IO streams first,
        # which resulted in ResourceWarnings even though we were closing the streams properly in our __del__ function.)
        self.__close = DlvhexLineReader.__CloseHelper(process, self.stderr_capture_thread, encoding)
        f = weakref.finalize(self, self.__close)  # type: ignore
        f.atexit = True  # make sure the subprocess will be terminated if it's still running when the python process exits

    def __iter__(self) -> Iterator[str]:
        '''Return an iterator over the lines written to stdout. May only be called once! Might raise a SolverSubprocessError.'''
        assert not self.iterating, 'You may only iterate once over a single DlvhexLineReader instance.'
        self.iterating = True
        # Requirement: dlvhex2 needs to flush stdout after every line
        with io.TextIOWrapper(self.process.stdout, encoding=self.stdout_encoding) as stdout_lines:
            for line in stdout_lines:
                yield line
                # Tell dlvhex2 to prepare the next answer set
                if not self.process.stdin.closed:
                    self.process.stdin.write(b'\n')
                    self.process.stdin.flush()
                else:
                    break
        # We've exhausted stdout, so either:
        #   1. we got all answer sets, or
        #   2. an error occurred,
        # and dlvhex closed stdout (and probably terminated).
        # Give it a chance to terminate gracefully.
        try:
            self.process.wait(timeout=0.005)
        except TimeoutExpired:
            pass
        self.close()

    def close(self) -> None:
        '''Shuts down the process if it is still running. Raises a SolverSubprocessError if the process exited with an error.'''
        self.__close()

    # We need to do destruction in a separate class to avoid reference cycles.
    class __CloseHelper:
        def __init__(self, process: Popen, stderr_capture_thread: StreamCaptureThread[bytes], stderr_encoding: str) -> None:
            self.process = process
            self.stderr_capture_thread = stderr_capture_thread
            self.stderr_encoding = stderr_encoding

        def is_running(self) -> bool:
            '''True iff the process is still running.'''
            return self.process.poll() is None

        def __call__(self) -> None:
            '''Shuts down the process if it is still running. Raises a SolverSubprocessError if the process exited with an error.'''
            if self.is_running():
                # Still running? Kill the subprocess
                self.process.terminate()
                try:
                    self.process.wait(timeout=0.001)
                except TimeoutExpired:
                    # Kill unconditionally after a short timeout.
                    # A potential problem with SIGKILL: we might not get all the error messages on stderr (if the child process is killed before it has a chance to write an error message)
                    self.process.kill()
                    self.process.wait()
                assert not self.is_running()
                # Various outcomes were observed that do not signify a real error condition as far as py-dlvhex is concerned:
                # * dlvhex2 simply terminates by itself between the is_running() check and the terminate() call
                # * dlvhex2 executes its SIGTERM handler and exits with code 2, and a message on stderr ("dlvhex2 [...] got termination signal 15")
                # * dlvhex2 doesn't have its SIGTERM handler active and the default handler exits with code -15
                # * dlvhex2 hangs after receiving SIGTERM (maybe when it's blocking on stdout? we're not reading from it anymore at this point), so we send SIGKILL after the timeout and it exits with -9
                # * dlvhex2 receives SIGTERM and crashes with "Assertion failed: (!res), function ~mutex, file /usr/local/include/boost/thread/pthread/mutex.hpp, line 111", and exit code -6 (SIGABRT)
                if self.process.returncode in (2, -signal.SIGTERM, -signal.SIGKILL, -signal.SIGABRT):
                    # In the cases mentioned above (and only if we called terminate()), don't throw an exception
                    self.process.returncode = 0
            # Note: only close stdin after the process has been terminated, otherwise dlvhex will start outputting everything at once
            self.process.stdin.close()
            self.process.stdout.close()
            self.stderr_capture_thread.join()  # ensure cleanup of stderr
            if self.process.returncode != 0:
                err = SolverSubprocessError(self.process.returncode, str(self.stderr_capture_thread.data, encoding=self.stderr_encoding))
                self.process.returncode = 0  # make sure we only raise an error once
                raise err


# These should actually be import from the .output module, but mypy currently does not support importing type aliases.
# Until mypy fixes this, we just redefine the types here as a workaround.
FactArgumentTuple = Tuple[Union[int, str], ...]
AnswerSet = Mapping[str, Iterable[FactArgumentTuple]]


class AnswerSetParserIterable(ClosableIterable[AnswerSet]):
    def __init__(self, lines: ClosableIterable[str]) -> None:
        self.lines = lines

    def __iter__(self) -> Iterator[AnswerSet]:
        for line in self.lines:
            try:
                yield parse_answer_set(line)
            except ParseException:
                e = SolverError('Unable to parse answer set received from solver')
                e.line = line  # type: ignore
                raise e

    def close(self):
        self.lines.close()


class Results(Iterable['Result']):
    '''The collection of results of a dlvhex2 invocation, corresponding to the set of all answer sets.'''
    # TODO: Describe implicit access to mapped objects through __getattr__ (e.g. .graph iterates over answer sets, returning the "graph" object for every answer set)

    def __init__(self, answer_sets: ClosableIterable[AnswerSet], output_spec: OutputSpec, registry: Registry, cache: bool) -> None:
        self.output_spec = output_spec
        self.registry = registry
        self.answer_sets = answer_sets
        self.results = (
            Result(answer_set, self.output_spec, self.registry) for answer_set in self.answer_sets
        )  # type: Iterable[Result]
        if cache:
            self.results = CachingIterable(self.results)

    def __iter__(self) -> Iterator['Result']:
        # Make sure we can only create one results iterator if we aren't caching
        assert self.results is not None, 'Pass cache=True if you need to iterate over dlvhex results multiple times.'
        results = self.results
        if type(self.results) != CachingIterable:
            self.results = None
        yield from results

    def __getattr__(self, name: str) -> Any:
        return ResultsAttributeIterator(self, name)

    def close(self) -> None:
        self.answer_sets.close()

    def __enter__(self) -> 'Results':
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        self.close()
        return False


class ResultsAttributeIterator(Iterator[Any]):
    '''Helps with cleanup when using shortcuts.'''

    def __init__(self, results, name):
        self.results = results
        self.results_iter = iter(results)
        self.name = name

    def __iter__(self):
        return self

    def __next__(self):
        return getattr(next(self.results_iter), self.name)

    def close(self):
        self.results.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False


class Result:
    '''Represents a single answer set.'''

    def __init__(self, answer_set: AnswerSet, output_spec: OutputSpec, registry: Registry) -> None:
        self._r = output_spec.prepare_mapping(answer_set, registry)

    def get(self, name: str) -> Any:
        return self._r.get_object(name)

    def __getattr__(self, name: str) -> Any:
        try:
            return self.get(name)
        except UndefinedNameError as e:
            raise AttributeError(e)
