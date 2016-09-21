from typing import Generic, Iterable, Iterator, TypeVar

__all__ = ['CachingIterable']


T = TypeVar('T', covariant=True)


class CachingIterable(Generic[T], Iterable[T]):
    '''Caches the contents of an iterable.

    Similar to calling list() on an iterable.
    However, where list() would finish the whole iteration before returning,
    the CachingIterable only advances the underlying iterator when the element is actually requested.

    Supports multiple iterators,
    but calls to next() on iterators constructed from instances of this class
    must be synchronized if they are to be used from multiple threads.
    '''

    def __init__(self, base_iterable: Iterable[T]) -> None:
        self.base_iterator = iter(base_iterable)
        self.cache = []  # type: List[T]
        self.done = False

    def __iter__(self) -> Iterator[T]:
        pos = 0
        while True:
            if pos < len(self.cache):
                yield self.cache[pos]
                pos += 1
            elif self.done:
                break
            else:
                self._generate_next()

    def _generate_next(self) -> None:
        if not self.done:
            try:
                value = next(self.base_iterator)
                self.cache.append(value)
            except StopIteration:
                self.done = True
                del self.base_iterator  # release underlying object
