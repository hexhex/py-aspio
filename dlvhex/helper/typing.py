from typing import Generic, Iterable, TypeVar


T = TypeVar('T', covariant=True)


class ClosableIterable(Generic[T], Iterable[T]):
    def close(self):
        pass
