from threading import Thread
from typing import Generic, IO, TypeVar

__all__ = ['StreamCaptureThread']


S = TypeVar('S', str, bytes)


class StreamCaptureThread(Generic[S], Thread):
    '''A thread that reads all contents of the given stream.

    The stream's contents can be accessed through the data attribute after the thread has finished.
    '''

    def __init__(self, stream: IO[S]) -> None:
        super().__init__(daemon=True)
        self.stream = stream
        self.data = None  # type: S

    def run(self):
        '''Reads the stream's contents and closes the stream.'''
        with self.stream as s:
            self.data = s.read()
