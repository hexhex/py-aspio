from abc import ABCMeta, abstractmethod
from contextlib import contextmanager
from itertools import chain
from typing import AbstractSet, Any, Iterable, Tuple, Optional, Union, Mapping, MutableMapping, Sequence  # noqa
from .helper.typing import AnswerSet, ASPRule, FactArgumentTuple
from .errors import CircularReferenceError, DuplicateKeyError, InvalidIndicesError, RedefinedNameError, UndefinedNameError
from .registry import Registry
from . import parser

__all__ = [
    'OutputSpec'
]


class OutputResult:
    __object_is_being_mapped = object()  # sentinel value, used for cycle detection

    def __init__(self, toplevel: Mapping[str, 'Expr'], facts: AnswerSet, registry: Registry) -> None:
        self.toplevel = toplevel
        self.facts = facts
        self.registry = registry
        # The objects created from the given facts and registry
        self.objs = {}  # type: MutableMapping[str, Any]

    def get_object(self, name: str) -> Any:
        if name not in self.objs:
            if name not in self.toplevel:
                raise UndefinedNameError('No top-level name "{0}".'.format(name))
            self.objs[name] = OutputResult.__object_is_being_mapped
            self.objs[name] = self.toplevel[name].perform_mapping(self, LocalContext())
            # We don't need to keep the raw data around after everything has been mapped
            if len(self.toplevel) == len(self.facts):
                del self.facts
        if self.objs[name] is OutputResult.__object_is_being_mapped:
            raise CircularReferenceError('Circular reference detected while trying to resolve name "{0}".'.format(name))
        return self.objs[name]


class LocalContext:
    def __init__(self) -> None:
        # Current assignment of ASP variables
        self.va = {}  # type: MutableMapping[str, str]

    @contextmanager
    def assign_variables(self, names: Sequence[str], values: Sequence[str]):
            assert len(names) == len(values)
            for (name, value) in zip(names, values):
                assert name not in self.va
                self.va[name] = value
            yield
            for name in names:
                del self.va[name]


class Expr(metaclass=ABCMeta):
    @abstractmethod
    def perform_mapping(self, r: OutputResult, lc: LocalContext) -> Any:
        pass

    def free_variables(self) -> Iterable['Variable']:
        return []

    def check(self, toplevel_name: str, bound_variables: Iterable[str], bound_references: Iterable[str]) -> None:
        pass

    def additional_rules(self) -> Iterable[ASPRule]:
        return []

    def captured_predicates(self) -> Iterable[str]:
        return []


class Literal(Expr):
    def __init__(self, value: Union[int, str]) -> None:
        self.value = value

    def perform_mapping(self, r: OutputResult, lc: LocalContext) -> Union[int, str]:
        return self.value


class Reference(Expr):
    def __init__(self, name: str) -> None:
        assert len(name) > 0
        self.name = name

    def perform_mapping(self, r: OutputResult, lc: LocalContext) -> Any:
        return r.get_object(self.name)


class Variable(Expr):
    def __init__(self, name: str) -> None:
        assert len(name) > 0
        self.name = name

    def __str__(self):
        return self.name

    def __repr__(self):
        return 'Variable({0!r})'.format(self.name)

    def perform_mapping(self, r: OutputResult, lc: LocalContext) -> str:
        assert self.name in lc.va
        # TODO: Check this at construction time, and throw an exception then.
        #       During execution we just have the assertion, which can be disabled in release mode.
        # if self.name not in lc.va:
        #     raise UndefinedNameError('Variable "{0}" is not bound'.format(self.name))
        return lc.va[self.name]

    def free_variables(self) -> Iterable['Variable']:
        return [self]


# TODO: We keep saying "constructor", but the implementation itself supports arbitrary functions, whether they construct a new object or not (but there are no guarantees w.r.t. side effects).
class ExprObject(Expr):
    def __init__(self, constructor_name: Optional[str], args: Iterable[Expr]) -> None:
        self.constructor_name = constructor_name  # If None, we will construct a tuple
        self.args = tuple(args)

    def perform_mapping(self, r: OutputResult, lc: LocalContext) -> Any:
        if self.constructor_name is None:
            def make_tuple(*args):
                return tuple(args)
            constructor = make_tuple
        else:
            constructor = r.registry.resolve(self.constructor_name)
        if constructor is None:
            raise NotImplementedError('constructor {0!r} not defined'.format(self.constructor_name))  # TODO
        mapped_args = (subexpr.perform_mapping(r, lc) for subexpr in self.args)
        return constructor(*mapped_args)

    def free_variables(self) -> Iterable['Variable']:
        return chain(*(subexpr.free_variables() for subexpr in self.args))

    def additional_rules(self) -> Iterable[ASPRule]:
        return chain(*(subexpr.additional_rules() for subexpr in self.args))

    def captured_predicates(self) -> Iterable[str]:
        return chain(*(subexpr.captured_predicates() for subexpr in self.args))


def ExprSimpleSet(predicate_name: str, arity: int, constructor_name: Optional[str]) -> Expr:
    print(predicate_name, arity, constructor_name)
    # Simple set semantics: just take the tuples as-is and put them in a set.
    variables = [Variable('X' + str(i)) for i in range(arity)]
    query = predicate_name + '(' + ','.join(map(str, variables)) + ')'
    if arity == 1 and constructor_name is None:
        # 1-tuples are unpacked automatically
        content = variables[0]  # type: Expr
    else:
        content = ExprObject(constructor_name, variables)
    return ExprSet(query, content)


# TODO: Separate ABC ExprComposed for the subexpressions? Could then use that in ExprObject too
class ExprCollection(Expr):
    def __init__(self, query: str, subexpressions: Sequence[Expr]) -> None:
        self.query = query
        self.subexpressions = tuple(subexpressions)
        # # TODO: Note the precondition somewhere: no predicate starting with pydlvhex__ may be used anywhere in the ASP program (or our additional rules will alter the program's meaning).
        self.output_predicate_name = 'pydlvhex__' + str(id(self))  # unique for as long as this object is alive
        self.captured_variable_names = tuple(set(var.name for expr in self.subexpressions for var in expr.free_variables()))  # 'set' to remove duplicates, then 'tuple' to fix the order
        # TODO: See notes in test_argument_subset and think about whether that's the desired semantics (or if we should capture all referenced variables)

    def additional_rules(self) -> Iterable[ASPRule]:
        rule = self.output_predicate_name + '(' + ','.join(self.captured_variable_names) + ') :- ' + str(self.query) + '.'
        return chain([rule], *(expr.additional_rules() for expr in self.subexpressions))

    def captured_predicates(self) -> Iterable[str]:
        return chain([self.output_predicate_name], *(expr.captured_predicates() for expr in self.subexpressions))


class ExprSet(ExprCollection):
    def __init__(self, query: str, content: Expr) -> None:
        super().__init__(query, [content])
        self.content = content

    def perform_mapping(self, r: OutputResult, lc: LocalContext) -> AbstractSet[Any]:
        # TODO: So far, a nested container can access variables from parent containers in the content clause, but cannot use it inside its query.
        # (well, it can be used, but it will be a "new" variable that cannot be referenced in the content clause)
        def content_for(captured_values):
            with lc.assign_variables(self.captured_variable_names, captured_values):
                return self.content.perform_mapping(r, lc)
        # TODO:
        # We might want to use a list here. Reasons:
        # * dlvhex2 already takes care of duplicates
        # * A set may only contain hashable objects, but a user might want to create custom classes in the output that aren't hashable
        # * Actually a tuple would be better than a list, since tuples are hashable iff their contents are hashable (so the tuple could still be used as a dict key later)
        # However:
        # * A set may be used as dict key… in that case we need the contents not only to be free of duplicates, but also have a deterministic order.
        #   Could be achieved by sorting the captured values as those only contain integers and strings, but in almost all cases that would be unnecessary work.
        # TODO: Note the limitation somewhere (contents must be hashable), maybe mention it in the paper too
        return frozenset(content_for(captured_values) for captured_values in r.facts.get(self.output_predicate_name, []))


class ExprSequence(ExprCollection):
    def __init__(self, query: str, content: Expr, index: Variable) -> None:
        super().__init__(query, [content, index])
        self.content = content
        self.index_pos = self.captured_variable_names.index(index.name)

    def perform_mapping(self, r: OutputResult, lc: LocalContext) -> Sequence[Any]:
        def index_for(captured_values):
            str_value = captured_values[self.index_pos]
            try:
                return int(str_value)
            except ValueError as e:
                raise InvalidIndicesError('index variable is not an integer: {0!s}'.format(e))

        def content_for(captured_values):
            with lc.assign_variables(self.captured_variable_names, captured_values):
                return self.content.perform_mapping(r, lc)

        # TODO: Options to determine how missing/duplicate indices should be handled
        # Currently: We require the indices to form a range of integers from 0 to n without any duplicates.
        all_captured_values = r.facts.get(self.output_predicate_name, [])
        indices = sorted(index_for(captured_values) for captured_values in all_captured_values)
        if indices != list(range(len(indices))):
            raise InvalidIndicesError('not a valid range of indices')  # TODO: better message
        xs = sorted((index_for(captured_values), content_for(captured_values)) for captured_values in all_captured_values)
        return [x[1] for x in xs]


class ExprDictionary(ExprCollection):
    def __init__(self, query: str, content: Expr, key: Expr) -> None:
        super().__init__(query, [content, key])
        self.content = content
        self.key = key

    def perform_mapping(self, r: OutputResult, lc: LocalContext) -> Mapping[Any, Any]:
        def obj_for(expr, captured_values):
            with lc.assign_variables(self.captured_variable_names, captured_values):
                return expr.perform_mapping(r, lc)
        d = {}  # type: MutableMapping[Any, Any]
        for captured_values in r.facts.get(self.output_predicate_name, []):
            # TODO: Note the limitation somewhere (keys must be hashable), maybe mention it in the paper too
            k = obj_for(self.key, captured_values)
            if k not in d:
                d[k] = obj_for(self.content, captured_values)
            else:
                raise DuplicateKeyError('Duplicate key: {0}'.format(repr(k)))
        return d


class OutputSpec:
    def __init__(self, named_exprs: Iterable[Tuple[str, Expr]]) -> None:
        exprs = {}  # type: MutableMapping[str, Expr]
        for (name, expr) in named_exprs:
            if name not in exprs:
                exprs[name] = expr
            else:
                raise RedefinedNameError('Duplicate top-level name: {0}'.format(name))
        self.exprs = exprs  # type: Mapping[str, Expr]
        # TODO: Check for cycles in references (currently we do that while mapping, but for consistency it would be nice to have it checked at time of construction -- it is some additional work though, while we get the result 'for free' during mapping)
        # TODO: Check for variables (undefined/redefined etc)
        for (name, expr) in self.exprs.items():
            expr.check(toplevel_name=name, bound_variables=[], bound_references=self.exprs.keys())

    @staticmethod
    def empty() -> 'OutputSpec':
        return OutputSpec([])

    @staticmethod
    def parse(string: str) -> 'OutputSpec':
        return parser.parse_output_spec(string)

    def prepare_mapping(self, facts: AnswerSet, registry: Registry) -> OutputResult:
        return OutputResult(self.exprs, facts, registry)

    def additional_rules(self) -> Iterable[ASPRule]:
        return chain(*(expr.additional_rules() for expr in self.exprs.values()))

    def captured_predicates(self) -> Iterable[str]:
        # create a set to remove duplicates
        return set(chain(*(expr.captured_predicates() for expr in self.exprs.values())))
