import os
import tempfile
import warnings
import weakref
from abc import ABC, abstractmethod

__all__ = [
    'FilesystemIPC',
    'TemporaryFile',
    'TemporaryNamedPipe',
]


class FilesystemIPC(ABC):
    '''An IPC mechanism that is accessible via the filesystem.'''

    def __init__(self) -> None:
        self.name = None  # type: str

    @abstractmethod
    def cleanup(self) -> None:
        pass

    def __enter__(self) -> str:
        return self.name

    def __exit__(self, exc_type, exc_value, traceback):
        self.cleanup()
        return False


def _warn_cleanup(typename, filename):
    warnings.warn('Did not call cleanup() on {0} with name {1}'.format(typename, filename), ResourceWarning)


class TemporaryNamedPipe(FilesystemIPC):
    def __init__(self) -> None:
        '''Create a temporary named pipe.

        The path to the named pipe can be retrieved from the `name` attribute on the returned object.

        To ensure proper removal of the pipe after use,
        make sure to call `cleanup()` on the returned object, or use it as a context manager.

        Raises `OSError` if the named pipe could not be created.
        Raises `NotImplementedError` if `mkfifo` from the builtin `os` module is not available.
        '''
        if hasattr(os, 'mkfifo'):
            self.tmpdir = tempfile.TemporaryDirectory(prefix='pyaspio_')  # creates a temporary directory, avoiding any race conditions
            self.name = os.path.join(self.tmpdir.name, 'pipe')
            os.mkfifo(self.name)  # may raise OSError

            self._cleanup_warning = weakref.finalize(self, _warn_cleanup, type(self).__name__, self.name)  # type: ignore
            self._cleanup_warning.atexit = True
        else:
            # Notes about a possible Windows implementation:
            #   Windows provides named pipes, see the CreateNamedPipe function in the Windows API: https://msdn.microsoft.com/en-us/library/aa365150(v=vs.85).aspx
            #   We can use the `ctypes` module to call this function, e.g.:
            #
            #       import ctypes
            #       kernel32 = ctypes.windll.kernel32
            #       pipe_handle = kernel32.CreateNamedPipeW(name, ...)
            #
            #   Related functions: ConnectNamedPipe, WriteFile, DisconnectNamedPipe, CloseHandle.
            #
            #   Overall the Windows pipe system seems more complicated,
            #   and I was not yet able to make it work without also changing the client code (which expects to read from a file).
            #
            #   For now, fall back to a temporary file on Windows.
            raise NotImplementedError()

    def cleanup(self) -> None:
        if self._cleanup_warning.peek() is not None:
            self.tmpdir.cleanup()
            self._cleanup_warning.detach()


class TemporaryFile(FilesystemIPC):
    def __init__(self) -> None:
        '''Create a temporary file.

        The path to the file can be retrieved from the `name` attribute on the returned object.

        To ensure proper removal of the file after use,
        make sure to call `cleanup()` on the returned object, or use it as a context manager.
        '''
        fd, self.name = tempfile.mkstemp(prefix='pyaspio_')
        # Ideally, we would use this file descriptor instead of reopening the file from the path later,
        # but then we do not know whether the file descriptor has already been closed.
        # (possible problems: we might leak a file descriptor, or close it twice (thus risking to close another unrelated file))
        os.close(fd)

        self._cleanup_warning = weakref.finalize(self, _warn_cleanup, type(self).__name__, self.name)  # type: ignore
        self._cleanup_warning.atexit = True

    def cleanup(self) -> None:
        if self._cleanup_warning.peek() is not None:
            os.remove(self.name)
            self._cleanup_warning.detach()
