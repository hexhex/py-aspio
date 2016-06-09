import importlib
from abc import ABCMeta, abstractmethod
from copy import copy
from itertools import chain
from types import ModuleType
from typing import Any, Callable, Iterable, Tuple, Optional, Union, Mapping, MutableMapping  # flake8: noqa

__all__ = [
    'OutputSpecification'
]

# An unprocessed answer set, i.e. simply a set of facts (not yet mapped to any objects).
# It is stored as mapping from predicate names to a collection of argument tuples.
FactArgumentTuple = Tuple[Union[int, str], ...]
AnswerSet = Mapping[str, Iterable[FactArgumentTuple]]
Constructor = Callable[..., object]


class Registry:
    def __init__(self) -> None:
        self._registered_names = {}  # type: MutableMapping[str, Constructor]

    def __copy__(self) -> 'Registry':
        other = Registry()
        other._registered_names = copy(self._registered_names)
        return other

    def register(self, name: str, constructor: Constructor, *, replace: bool = False) -> None:
        if not replace and name in self._registered_names:
            raise ValueError('Name {0} is already registered. Pass replace=True to re-register.'.format(name))
        if not callable(constructor):
            raise ValueError('constructor argument needs to be callable')
        self._registered_names[name] = constructor

    def import_from_module(self, names: Iterable[str], module_or_module_name: Union[ModuleType, str], package: Optional[str] = None) -> None:
        if isinstance(module_or_module_name, ModuleType):
            module = module_or_module_name
        else:
            module = importlib.import_module(module_or_module_name, package=package)
        for name in names:
            self.register(name, getattr(module, name))

    def get(self, name: str) -> Constructor:
        return self._registered_names.get(name)


ASPRule = str  # TODO: Could be a more sophisticated type to support passing the rule to dlvhex directly (when it is used via a shared library)


class Context:
    __is_being_mapped = object()

    def __init__(self, toplevel: Mapping[str, 'Expr'], facts: AnswerSet, registry: Registry) -> None:
        self.toplevel = toplevel
        self.facts = facts
        self.registry = registry
        # Current assignment of ASP variables
        self.va = {}  # type: MutableMapping[str, Union[int, str]]
        # The objects created from the given facts and registry
        self.objs = {}  # type: MutableMapping[str, object]

    def get_object(self, name):
        if name not in self.objs:
            if name not in self.toplevel:
                raise ValueError('No top-level mapping with name "{0}".'.format(name))
            self.objs[name] = Context.__is_being_mapped  # for cycle detection
            self.objs[name] = self.toplevel[name].perform_mapping(self)
        if self.objs[name] is Context.__is_being_mapped:
            raise ValueError('cycle detected when trying to resolve name "{0}".'.format(name))
        return self.objs[name]


class Expr(metaclass=ABCMeta):
    @abstractmethod
    def perform_mapping(self, context: Context) -> Any:
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

    def perform_mapping(self, context: Context) -> Union[int, str]:
        return self.value


class Reference(Expr):
    def __init__(self, name: str) -> None:
        assert len(name) > 0
        self.name = name

    def perform_mapping(self, context: Context) -> Any:
        return context.get_object(self.name)


class Variable(Expr):
    def __init__(self, name: str) -> None:
        assert len(name) > 0
        self.name = name

    def __repr__(self):
        return 'Variable({0})'.format(repr(self.name))

    def perform_mapping(self, context: Context) -> Any:
        if self.name not in context.va:
            raise ValueError('Variable "{0}" is not bound'.format(self.name))
        return context.va[self.name]

    def free_variables(self) -> Iterable['Variable']:
        return [self]


# TODO: We keep saying "constructor", but the implementation itself supports arbitrary functions, whether they construct a new object or not (but there are no guarantees w.r.t. side effects).
class ExprObject(Expr):
    def __init__(self, constructor_name: Optional[str], args: Iterable[Expr]) -> None:
        self.constructor_name = constructor_name  # If None, we will construct a tuple
        self.args = tuple(args)

    def perform_mapping(self, context: Context) -> Any:
        if self.constructor_name is None:
            def make_tuple(*args):
                return tuple(args)
            constructor = make_tuple
        else:
            constructor = context.registry.get(self.constructor_name)
        mapped_args = (subexpr.perform_mapping(context) for subexpr in self.args)
        return constructor(*mapped_args)

    def free_variables(self) -> Iterable['Variable']:
        return chain(*(subexpr.free_variables() for subexpr in self.args))

    def additional_rules(self) -> Iterable[ASPRule]:
        return chain(*(subexpr.additional_rules() for subexpr in self.args))

    def captured_predicates(self) -> Iterable[str]:
        return chain(*(subexpr.captured_predicates() for subexpr in self.args))

class ExprSimpleSet(Expr):
    def __init__(self, predicate_name: str) -> None:
        self.predicate_name = predicate_name

    def perform_mapping(self, context: Context) -> Any:
        # Simple set semantics: just take the tuples as-is
        return frozenset(context.facts.get(self.predicate_name, []))

    def captured_predicates(self) -> Iterable[str]:
        return [self.predicate_name]


# TODO: Maybe make a common base class for ExprSet, ExprSequence and ExprMapping ("ExprCollection"?)
class ExprSet(Expr):
    def __init__(self, predicate: str, content: Expr) -> None:
        self.predicate = predicate
        self.content = content
        # TODO: Note the precondition somewhere: no predicate starting with pydlvhex__ may be used anywhere in the ASP program (or our additional rules will alter the program's meaning).
        self.output_predicate_name = 'pydlvhex__' + str(id(self))  # unique for as long as this object is alive
        self.captured_variable_names = tuple(set(v.name for v in content.free_variables()))  # 'set' to remove duplicates, then 'tuple' to fix the order

    def additional_rules(self) -> str:
        rule = self.output_predicate_name + '(' + ','.join(self.captured_variable_names) + ') :- ' + self.predicate + '.'
        return chain([rule], self.content.additional_rules())

    def perform_mapping(self, context: Context) -> Any:
        # TODO: So far, a nested container can access variables from parent containers in the content clause, but cannot use it inside its query.
        # (well, it can be used, but it will be a "new" variable that cannot be referenced in the content clause)
        def content_for(captured_values):
            assert len(self.captured_variable_names) == len(captured_values)
            for (name, value) in zip(self.captured_variable_names, captured_values):
                assert name not in context.va
                context.va[name] = value
            obj = self.content.perform_mapping(context)
            for name in self.captured_variable_names:
                del context.va[name]
            return obj
        # TODO:
        # We might want to use a list here. Reasons:
        # * dlvhex2 already takes care of duplicates
        # * A set may only contain hashable objects, but a user might want to create custom classes in the output that aren't hashable
        return frozenset(content_for(captured_values) for captured_values in context.facts.get(self.output_predicate_name, []))

    def captured_predicates(self) -> Iterable[str]:
        return chain([self.output_predicate_name], self.content.captured_predicates())


class ExprSequence(Expr):
    def __init__(self, predicate: str, content: Expr, index: Variable) -> None:
        pass
    def perform_mapping(self, context: Context) -> Any:
        raise NotImplementedError()

    def additional_rules(self) -> str:
        rule = self.output_predicate_name + '(' + ','.join(self.captured_variables) + ') :- ' + self.predicate + '. '
        return chain([rule], self.content.additional_rules())


class ExprMapping(Expr):
    def __init__(self, predicate: str, content: Expr, key: Expr) -> None:
        pass
    def perform_mapping(self, context: Context) -> Any:
        raise NotImplementedError()

    def additional_rules(self) -> str:
        rule = self.output_predicate_name + '(' + ','.join(self.captured_variables) + ') :- ' + self.predicate + '. '
        return chain([rule], self.content.additional_rules(), self.key.additional_rules())


class OutputSpecification:
    def __init__(self, named_exprs: Iterable[Tuple[str, Expr]]) -> None:
        exprs = {}  # type: MutableMapping[str, Expr]
        for (name, expr) in named_exprs:
            if name not in exprs:
                exprs[name] = expr
            else:
                raise ValueError('duplicate name')  # TODO: more specific error
        self.exprs = exprs  # type: Mapping[str, Expr]
        # TODO: Check for cycles in references (or we can do that while mapping)
        # TODO: Check for variables (undefined/redefined etc)
        for (name, expr) in self.exprs.items():
            expr.check(toplevel_name=name, bound_variables=[], bound_references=self.exprs.keys())

    def get_mapping_context(self, facts: AnswerSet, registry: Registry) -> Context:
        return Context(self.exprs, facts, registry)

    def additional_rules(self) -> Iterable[ASPRule]:
        return chain(*(expr.additional_rules() for expr in self.exprs.values()))

    def captured_predicates(self) -> Iterable[str]:
        # create a set to remove duplicates
        return set(chain(*(expr.captured_predicates() for expr in self.exprs.values())))
