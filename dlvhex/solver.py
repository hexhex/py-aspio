import io
from subprocess import Popen, PIPE
from threading import Thread
from typing import Any, Sequence, Iterable
from .input import StreamAccumulator
from .output import OutputSpecification
from . import program as p  # flake8: noqa

__all__ = ['SolverError', 'Solver']


class SolverError(ValueError):  # TODO: This is not really a ValueError, or is it?
    '''Raised when an error with the solver subprocess occurs.'''
    def __init__(self, returncode, stderr):
        message = 'dlvhex2 terminated with error {0}.\nOutput on stderr:\n{1}'.format(returncode, stderr)
        super().__init__(message)


class Solver:
    '''Interface to the dlvhex2 solver.'''

    # TODO: Check what encoding dlvhex2 expects (on stdin and for input files) -- this is not supposed to be an option, but the encoding that dlvhex2 uses to read from stdin (and input files)
    default_encoding = 'UTF-8'

    # TODO: Some way to pass dlvhex options like maxint
    def __init__(self, *, executable: str = None) -> None:
        '''Initialize a dlvhex2 solver instance.

        @param executable The path to the dlvhex2 executable. If not specified, looks for "dlvhex2" in the current $PATH.
        '''
        self.executable = executable or 'dlvhex2'
        self.encoding = Solver.default_encoding

    def run(self, program: 'p.Program', input_args: Sequence[Any], cache: bool) -> 'AnswerSetCollection':
        '''Run the dlvhex solver on the given program.'''
        args = [
            self.executable,
            '--silent',     # only print the answer sets themselves
            '--',           # tell dlvhex2 to read input from stdin, too
        ]
        args.extend(program.file_parts)
        # TODO:
        # * maybe use waitonmodel option (but how does this work if we're giving input on stdin?)
        #   Alternative: use stop/continue signals (does that work on windows?), e.g.:
        #               process.send_signal(signal.SIGSTOP)
        #               process.send_signal(signal.SIGCONT)
        #   (other possibilities: temporary file, named pipe)
        # * use filter to only get the predicates we need according to the output specification
        # * need a way to specify maxint
        process = Popen(
            args,
            stdin=PIPE,
            stdout=PIPE,
            stderr=PIPE,
        )
        text_stdin = io.TextIOWrapper(process.stdin, encoding=self.encoding)
        # Map input data and pass it over stdin
        if program.input_spec is not None:
            program.input_spec.perform_mapping(input_args, StreamAccumulator(text_stdin))
        # Pass code given as string over stdin
        for code in program.code_parts:
            text_stdin.write(code)
        text_stdin.close()  # flush and close stream, dlvhex2 starts processing after this
        return AnswerSetCollection(process=process, output_spec=program.output_spec, encoding=self.encoding, cache=cache)


class ProcessWrapper(Iterable):
    '''Wraps a process and provides its standard output for line-based iteration.

    It is only possible to iterate *once* over a ProcessWrapper instance.

    If the process exits with a return code other than 0,
    a SolverError will be thrown during iteration, containing the return code and stderr output of the process.
    '''

    class CaptureThread(Thread):
        def __init__(self, stream):
            super().__init__(daemon=True)
            self.stream = stream
            self.data = None

        def run(self):
            with self.stream as s:
                self.data = s.read()

    def __init__(self, process: Popen, encoding: str) -> None:
        self.process = process
        self.encoding = encoding
        self.iterating = False
        #
        # We need to capture stderr in a background thread to avoid deadlocks.
        # (The problem would occur when dlvhex2 is blocked because the OS buffers on the stderr pipe are full... so we have to constantly read from *both* stdout and stderr)
        self.stderr_capture_thread = ProcessWrapper.CaptureThread(self.process.stderr)
        self.stderr_capture_thread.start()

    def __iter__(self):
        '''Return an iterator over the lines written to stdout. May only be called once!'''
        assert not self.iterating, 'You may only iterate once over a single ProcessWrapper instance.'
        self.iterating = True
        # TODO: Requirement: dlvhex2 needs to flush stdout after every line
        with io.TextIOWrapper(self.process.stdout, encoding=self.encoding) as stdout_lines:
            yield from stdout_lines
        # stdout has been closed, wait for dlvhex2 to terminate
        self.process.wait()
        if self.error():
            self.stderr_capture_thread.join()
            raise SolverError(self.process.returncode, str(self.stderr_capture_thread.data, encoding=self.encoding))
        # for line in io.TextIOWrapper(self.process.stdout, encoding=self.encoding):
        #     yield line
        #     # answer_set = line  # TODO: parse
        #     # yield answer_set
        # else:
        #     # stdout has been closed, wait for dlvhex2 to terminate
        #     self.process.wait()
        #     if self.error():
        #         self.stderr_capture_thread.join()
        #         raise SolverError(self.process.returncode, str(self.stderr_capture_thread.data, encoding=self.encoding))

    def is_running(self):
        '''True iff the process is still running.'''
        return self.process.poll() is None
        # return self.process.returncode is None

    def error(self):
        '''True iff the process terminated with error.'''
        return self.process.poll() not in (None, 0)

    def close(self) -> None:
        '''Shut down the process if it is still running. It is usually not necessary to call this method.'''
        if self.is_running():
            print('calling terminate()')
            self.process.terminate()

    def __del__(self) -> None:
        self.close()


class CachingIterable(Iterable):
    '''Caches the contents of an iterable.

    Similar to calling list() on an iterable.
    However, where list() would finish the whole iteration before returning,
    the CachingIterable only advances the underlying iterator when the element is actually requested.

    Supports multiple iterators,
    but calls to next() on iterators constructed from instances of this class must be synchronized
    if they are to be used from multiple threads.
    '''

    def __init__(self, base_iterable):
        self.base_iterator = iter(base_iterable)
        self.cache = []
        self.done = False

    def __iter__(self):
        pos = 0
        while True:
            if pos < len(self.cache):
                yield self.cache[pos]
                pos += 1
            elif self.done:
                break
            else:
                self._generate_next()

    def _generate_next(self):
        if not self.done:
            try:
                value = next(self.base_iterator)
                self.cache.append(value)
            except StopIteration:
                self.done = True
                del self.base_iterator  # release underlying object


class AnswerSetCollection:
    '''The result of a dlvhex2 invocation, corresponding to the set of all answer sets.'''
    # TODO: Describe implicit access to mapped objects through __getattr__ (e.g. .graph iterates over answer sets, returning the "graph" object for every answer set)

    def __init__(self, process: Popen, output_spec: OutputSpecification, encoding: str, cache: bool) -> None:
        self.answer_sets = (
            AnswerSet(line, output_spec) for line in ProcessWrapper(process, encoding=encoding)
        )  # type: Iterable[AnswerSet]
        if cache:
            self.answer_sets = CachingIterable(self.answer_sets)

    def __iter__(self):
        if self.answer_sets is None:
            raise ValueError('Pass cache=True if you need to iterate over answer sets multiple times.')
        yield from self.answer_sets
        if not isinstance(self.answer_sets, CachingIterable):
            self.answer_sets = None

    def __getattr__(self, name):
        for answer_set in self:
            yield getattr(answer_set, name)


class AnswerSet:
    '''Represents a single answer set.'''

    def __init__(self, answer_set_string: str, output_spec: OutputSpecification) -> None:
        self.output_spec = output_spec
        # TODO: Parse string
        self.data = answer_set_string

    def __repr__(self):
        return repr(self.data)

    def __getattr__(self, name):
        # TODO: Generate object according to output_spec
        # Maybe store with setattr(self, name, obj)
        raise AttributeError
