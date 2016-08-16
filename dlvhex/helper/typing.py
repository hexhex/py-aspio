from typing import Generic, Iterable, Mapping, Tuple, TypeVar

# An unprocessed answer set, i.e. simply a set of facts (not yet mapped to any objects).
# It is stored as mapping from predicate names to a collection of argument tuples.
FactArgumentTuple = Tuple[str, ...]
AnswerSet = Mapping[str, Iterable[FactArgumentTuple]]

ASPRule = str  # TODO: Could be a more sophisticated type to support passing the rule to dlvhex directly (when it is used via a shared library)

T = TypeVar('T', covariant=True)


class ClosableIterable(Generic[T], Iterable[T]):
    def close(self):
        pass
