import io
import signal
import subprocess  # type: ignore
import weakref
from itertools import chain
from typing import Callable, IO, Iterable, Iterator, Optional
from ..helper.typing import ClosableIterable
from ..errors import SolverError, SolverSubprocessError
from ..helper import FilesystemIPC, StreamCaptureThread, TemporaryFile, TemporaryNamedPipe
from ..parser import parse_answer_set, ParseException
from .abc import Solver, SolverOptions
from .. import asp


class Dlvhex2Solver(Solver):
    '''Interface to the dlvhex2 solver.'''

    # TODO: Check what encoding dlvhex2 expects (on stdin and for input files) -- this is not supposed to be an option, but the encoding that dlvhex2 uses to read from stdin (and input files)
    default_encoding = 'UTF-8'

    def __init__(self, *, executable: str = None) -> None:
        '''Initialize a dlvhex2 solver instance.

        @param executable The path to the dlvhex2 executable. If not specified, looks for "dlvhex2" in the current $PATH.
        '''
        self.executable = executable if executable is not None else 'dlvhex2'
        self.encoding = type(self).default_encoding

    def __copy__(self) -> 'Solver':
        other = Dlvhex2Solver()
        other.executable = self.executable
        other.encoding = self.encoding
        return other

    def run(self, *,
            write_input: Callable[[IO[str]], None],
            capture_predicates: Iterable[str],
            file_args: Iterable[str],
            options: Optional[SolverOptions]) -> ClosableIterable[asp.RawAnswerSet]:
        '''Run the dlvhex solver on the given program.'''
        # Prefer named pipes, but fall back to a file if pipes are not implemented for the current platform
        try:
            tmp_input = TemporaryNamedPipe()  # type: FilesystemIPC
        except NotImplementedError:
            tmp_input = TemporaryFile()

        if options is not None and options.capture is not None:
            capture_predicates = chain(capture_predicates, options.capture)

        try:
            args = [
                self.executable,
                # only print the answer sets themselves
                '--silent',
                # only capture relevant predicates
                '--filter=' + ','.join(capture_predicates),
                # wait for a newline on stdin between answer sets
                '--waitonmodel',
            ]
            # options passed in by caller
            if options is not None:
                if options.max_answer_sets is not None:
                    args.append('--number={0!s}'.format(options.max_answer_sets))
                if options.max_int is not None:
                    args.append('--maxint={0!s}'.format(options.max_int))
                if options.custom is not None:
                    args.extend(options.custom)
            # tell dlvhex2 to read our input from the named pipe
            args.append(tmp_input.name)
            args.extend(file_args)

            # If we have a temporary file, we must pass the data before starting the subprocess
            if isinstance(tmp_input, TemporaryFile):
                with open(tmp_input.name, 'wt', encoding=self.encoding) as stream:
                    write_input(stream)

            # Start dlvhex2 subprocess
            process = subprocess.Popen(
                args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            try:
                # If we have a named pipe, we must pass the data after starting the subprocess,
                # or we risk a deadlock by filling the pipe's buffer
                if isinstance(tmp_input, TemporaryNamedPipe):
                    with open(tmp_input.name, 'wt', encoding=self.encoding) as stream:
                        write_input(stream)
                    # At this point the input pipe is flushed and closed, and dlvhex2 starts processing

                lines = DlvhexLineReader(process=process, encoding=self.encoding, tmp_input=tmp_input)
                return AnswerSetParserIterable(lines)
            except:
                process.kill()
                # Close streams to prevent ResourceWarnings
                process.stdin.close()
                process.stdout.close()
                process.stderr.close()
                raise
        except:
            tmp_input.cleanup()
            raise


class DlvhexLineReader(ClosableIterable[str]):
    '''Wraps a process and provides its standard output for line-based iteration.

    It is only possible to iterate *once* over a DlvhexLineReader instance.

    If the process exits with a return code other than 0,
    a SolverSubprocessError will be thrown during iteration, containing the return code and stderr output of the process.
    '''

    def __init__(self, *, process: subprocess.Popen, encoding: str, tmp_input: FilesystemIPC) -> None:
        self.process = process
        self.stdout_encoding = encoding
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
        self._finalize = weakref.finalize(self, DlvhexLineReader.__close, process, self.stderr_capture_thread, encoding, tmp_input)  # type: ignore
        # Make sure the subprocess will be terminated if it's still running when the python process exits
        self._finalize.atexit = True

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
            self.process.wait(timeout=0.005)  # type: ignore (mypy does not know about `timeout`)
        except subprocess.TimeoutExpired:  # type: ignore (mypy does not know about `TimeoutExpired`)
            pass
        self.close()

    def close(self) -> None:
        self._finalize()

    # We cannot have a reference to `self` because we must avoid reference cycles here (see weakref.finalize documentation).
    @staticmethod
    def __close(process: subprocess.Popen, stderr_capture_thread: StreamCaptureThread[bytes], stderr_encoding: str, tmp_input: FilesystemIPC) -> None:
        '''Shut down the process if it is still running. Raise a SolverSubprocessError if the process exited with an error.'''
        if process.poll() is None:
            # Still running? Kill the subprocess
            process.terminate()
            try:
                process.wait(timeout=0.001)  # type: ignore (mypy does not know about `timeout`)
            except subprocess.TimeoutExpired:  # type: ignore (mypy does not know about `TimeoutExpired`)
                # Kill unconditionally after a short timeout.
                # A potential problem with SIGKILL: we might not get all the error messages on stderr (if the child process is killed before it has a chance to write an error message)
                process.kill()
                process.wait()
            assert process.poll() is not None  # subprocess has stopped
            # Various outcomes were observed that do not signify a real error condition as far as py-dlvhex is concerned:
            # * dlvhex2 simply terminates by itself between the is_running() check and the terminate() call
            # * dlvhex2 executes its SIGTERM handler and exits with code 2, and a message on stderr ("dlvhex2 [...] got termination signal 15")
            # * dlvhex2 doesn't have its SIGTERM handler active and the default handler exits with code -15
            # * dlvhex2 hangs after receiving SIGTERM (maybe when it's blocking on stdout? we're not reading from it anymore at this point), so we send SIGKILL after the timeout and it exits with -9
            # * dlvhex2 receives SIGTERM and crashes with "Assertion failed: (!res), function ~mutex, file /usr/local/include/boost/thread/pthread/mutex.hpp, line 111", and exit code -6 (SIGABRT)
            if process.returncode in (2, -signal.SIGTERM, -signal.SIGKILL, -signal.SIGABRT):
                # In the cases mentioned above (and only if we are responsible for termination, i.e. after calling terminate() from this function), don't throw an exception
                process.returncode = 0
        # Note: only close stdin after the process has been terminated, otherwise dlvhex will start outputting everything at once
        process.stdin.close()
        process.stdout.close()
        stderr_capture_thread.join()  # ensure cleanup of stderr
        # Remove the temporary input pipe/file
        # Note: To clean up tmp_input in a reliable way, we must be sure dlvhex2 has already read all the data (or, has at the very least opened the file).
        #       Because of this, the earliest point where we are able to clean up tmp_input would be when dlvhex2 starts outputting the first answer set.
        tmp_input.cleanup()
        if process.returncode != 0:
            err = SolverSubprocessError(process.returncode, str(stderr_capture_thread.data, encoding=stderr_encoding))
            process.returncode = 0  # make sure we only raise an error once
            raise err


class AnswerSetParserIterable(ClosableIterable[asp.RawAnswerSet]):
    def __init__(self, lines: ClosableIterable[str]) -> None:
        self.lines = lines

    # @staticmethod
    # def _parse(line):
    #     try:
    #         return parse_answer_set(line)
    #     except ParseException:
    #         e = SolverError('Unable to parse answer set received from solver')
    #         e.line = line  # type: ignore
    #         raise e

    def __iter__(self) -> Iterator[asp.RawAnswerSet]:
        # return iter(map(type(self)._parse, self.lines))
        for line in self.lines:
            try:
                yield parse_answer_set(line)
            except ParseException:
                e = SolverError('Unable to parse answer set received from solver')
                e.line = line  # type: ignore
                raise e

    def close(self) -> None:
        self.lines.close()
