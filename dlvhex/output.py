from abc import ABCMeta, abstractmethod
from typing import Any, Iterable, Tuple, Optional, Union, Mapping, MutableMapping  # flake8: noqa

# An unprocessed answer set, i.e. simply a set of facts (not yet mapped to any objects).
# It is stored as mapping from predicate names to a collection of argument tuples.
AnswerSet = Mapping[str, Iterable[Tuple[Union[int, str], ...]]]


class Reference():
    def __init__(self, name: str) -> None:
        assert len(name) > 0
        self.name = name


class Variable():
    def __init__(self, name: str) -> None:
        assert len(name) > 0
        self.name = name


class Content():
    def __init__(self, constructor_name: Optional[str], args: Iterable[Union[int, str, 'Content', Variable]]) -> None:
        self.constructor_name = constructor_name  # If None, we will construct a tuple
        self.args = tuple(args)


class OutputSpec(metaclass=ABCMeta):

    # @abstractmethod
    def perform_mapping(self, facts: AnswerSet, context) -> Any:
        pass


class OutputObject(OutputSpec):
    def __init__(self, constructor_name: Optional[str], args: Iterable[Union[int, str, 'OutputSpec', Reference]]) -> None:
        self.constructor_name = constructor_name  # If None, we will construct a tuple
        self.args = tuple(args)


class OutputSet(OutputSpec):
    def __init__(self, predicate_name: str, content: Content) -> None:
        pass


class OutputSimpleSet(OutputSpec):
    def __init__(self, predicate_name: str) -> None:
        self.predicate_name = predicate_name

    def perform_mapping(self, facts: AnswerSet, context) -> Any:
        return set(facts.get(self.predicate_name, []))


class OutputSequence(OutputSpec):
    def __init__(self, predicate_name: str, content: Content, index: Variable) -> None:
        pass


class OutputMapping(OutputSpec):
    def __init__(self, predicate_name: str, content: Content, key: Content) -> None:
        pass


class OutputSpecification:

    def __init__(self, named_specs: Iterable[Tuple[str, OutputSpec]]) -> None:
        specs = {}  # type: MutableMapping[str, OutputSpec]
        for (name, spec) in named_specs:
            if name not in specs:
                specs[name] = spec
            else:
                raise ValueError('duplicate name')  # TODO: more specific error
        self.specs = specs  # type: Mapping[str, OutputSpec]
        # TODO: Check for cycles in references (or we can do that while mapping)
