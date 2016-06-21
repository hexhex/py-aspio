import os
import tempfile
import weakref

__all__ = ['TemporaryNamedPipe']


class TemporaryNamedPipe:
    def __init__(self):
        self.tmpdir = tempfile.TemporaryDirectory()  # creates a temporary directory, avoiding any race conditions
        self.name = os.path.join(self.tmpdir.name, 'pydlvhex_fifo_' + str(id(self)))
        if hasattr(os, 'mkfifo'):
            try:
                os.mkfifo(self.name)
            except OSError:
                raise  # rethrow
        else:
            # TODO: Windows version? http://stackoverflow.com/questions/13319679/createnamedpipe-in-python?lq=1
            raise NotImplementedError()
        # Safety net in case someone forgets to call close() -- TODO: should we log a ResourceWarning there?
        f = weakref.finalize(self, self.tmpdir.cleanup)
        f.atexit = True

    def close(self):
        # This will also remove the named pipe inside the directory
        self.tmpdir.cleanup()

    def __enter__(self):
        return self.name

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False
