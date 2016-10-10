from abc import ABCMeta, abstractmethod
from contextlib import contextmanager
from itertools import chain
from typing import AbstractSet, Any, Iterable, Tuple, Optional, Union, Mapping, MutableMapping, Sequence  # noqa
from .errors import CircularReferenceError, DuplicateKeyError, InvalidIndicesError, RedefinedNameError, UndefinedNameError
from .registry import Registry
from . import asp
from . import parser

__all__ = [
    'OutputSpec'
]


class OutputResult:
    __object_is_being_mapped = object()  # sentinel value, used for cycle detection

    def __init__(self, toplevel: Mapping[str, 'Expr'], answer_set: asp.RawAnswerSet, registry: Registry) -> None:
        self.toplevel = toplevel
        self.answer_set = answer_set
        self.registry = registry
        # The objects created from the given answer set and registry
        self.objs = {}  # type: MutableMapping[str, Any]

    def get_object(self, name: str) -> Any:
        if name not in self.objs:
            if name not in self.toplevel:
                raise UndefinedNameError('No top-level name "{0}".'.format(name))
            self.objs[name] = OutputResult.__object_is_being_mapped
            self.objs[name] = self.toplevel[name].evaluate(self, LocalContext())
            # We don't need to keep the raw data around after everything has been mapped
            if len(self.toplevel) == len(self.objs):
                del self.answer_set
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
    def evaluate(self, r: OutputResult, lc: LocalContext) -> Any:
        pass

    def variables(self) -> Iterable['Variable']:
        '''All the variable expressions (i.e., does not include those occurring only in queries) used in this expression and any subexpressions.'''
        return ()

    def check(self, toplevel_name: str, bound_variables: Tuple[str, ...]) -> None:
        pass

    def additional_rules(self) -> Iterable[asp.Rule]:
        return ()

    def captured_predicates(self) -> Iterable[str]:
        return ()


class Constant(Expr):
    def __init__(self, value: Union[int, str]) -> None:
        self.value = value

    def evaluate(self, r: OutputResult, lc: LocalContext) -> Union[int, str]:
        return self.value


class Reference(Expr):
    def __init__(self, name: str) -> None:
        assert len(name) > 0
        self.name = name

    def evaluate(self, r: OutputResult, lc: LocalContext) -> Any:
        return r.get_object(self.name)


class Variable(Expr):
    def __init__(self, name: str) -> None:
        assert len(name) > 0
        self.name = name

    def __str__(self):
        return self.name

    def __repr__(self):
        return 'Variable({0!r})'.format(self.name)

    def evaluate(self, r: OutputResult, lc: LocalContext) -> str:
        assert self.name in lc.va
        return str(lc.va[self.name])

    def variables(self) -> Iterable['Variable']:
        return [self]

    def check(self, toplevel_name: str, bound_variables: Tuple[str, ...]) -> None:
        if self.name not in bound_variables:
            raise UndefinedNameError('Variable {0!s} is not defined at point of use (at least once in definition of {1!s}).'.format(self.name, toplevel_name))


# TODO: We keep saying "constructor", but the implementation itself supports arbitrary functions, whether they construct a new object or not (but there are no guarantees w.r.t. side effects).
class ExprObject(Expr):
    def __init__(self, constructor_name: Optional[str], args: Iterable[Expr]) -> None:
        self.constructor_name = constructor_name  # If None, we will construct a tuple
        self.args = tuple(args)

    def evaluate(self, r: OutputResult, lc: LocalContext) -> Any:
        if self.constructor_name is None:
            def make_tuple(*args):
                # `tuple()` expects an Iterable, but the `constructor` is fed a number of separate arguments
                return r.registry.tuple_constructor(args)
            constructor = make_tuple
        else:
            constructor = r.registry.resolve(self.constructor_name)
        if constructor is None:
            raise NotImplementedError('constructor {0!r} not defined'.format(self.constructor_name))  # TODO
        mapped_args = (subexpr.evaluate(r, lc) for subexpr in self.args)
        return constructor(*mapped_args)

    def variables(self) -> Iterable['Variable']:
        # return chain(*(subexpr.variables() for subexpr in self.args))
        for subexpr in self.args:
            yield from subexpr.variables()

    def additional_rules(self) -> Iterable[asp.Rule]:
        for subexpr in self.args:
            yield from subexpr.additional_rules()
        # return chain(*(subexpr.additional_rules() for subexpr in self.args))

    def captured_predicates(self) -> Iterable[str]:
        for subexpr in self.args:
            yield from subexpr.captured_predicates()
        # return chain(*(subexpr.captured_predicates() for subexpr in self.args))

    def check(self, toplevel_name: str, bound_variables: Tuple[str, ...]) -> None:
        for subexpr in self.args:
            subexpr.check(toplevel_name, bound_variables)


def ExprSimpleSet(predicate_name: str, arity: int, constructor_name: Optional[str]) -> Expr:
    # Simple set semantics: just take the tuples as-is and put them in a set.
    varnames = ['X' + str(i) for i in range(arity)]
    literal = asp.Literal(predicate_name, tuple(asp.Variable(v) for v in varnames), False)
    query = asp.Query((literal,))
    if arity == 1 and constructor_name is None:
        # 1-tuples are unpacked automatically
        content = Variable(varnames[0])  # type: Expr
    else:
        content = ExprObject(constructor_name, tuple(Variable(v) for v in varnames))
    return ExprSet(query, content)


# TODO: Separate ABC ExprComposed for the subexpressions? Could then use that in ExprObject too
class ExprCollection(Expr):
    def __init__(self, query: asp.Query, subexpressions: Sequence[Expr]) -> None:
        self.query = query
        self.subexpressions = tuple(subexpressions)
        # # TODO: Note the precondition somewhere: no predicate starting with aspio__ may be used anywhere in the ASP program (or our additional rules will alter the program's meaning).
        # TODO: Special handling for cases where the original predicate can be used (e.g., only one literal and all variables captured)
        # TODO: Similar output expressions may generate duplicate rules... would be good if both expressions could use the same rule, without having all the data twice in the answer set
        self.output_predicate = 'aspio__' + str(id(self))  # unique for as long as this object is alive
        self.captured_variables = None  # type: Tuple[str, ...]

    def additional_rules(self) -> Iterable[asp.Rule]:
        rule = self.output_predicate + '(' + ','.join(self.captured_variables) + ') :- ' + str(self.query) + '.'
        yield rule
        for subexpr in self.subexpressions:
            yield from subexpr.additional_rules()
        # return chain([rule], *(expr.additional_rules() for expr in self.subexpressions))

    def captured_predicates(self) -> Iterable[str]:
        # return chain([self.output_predicate], *(expr.captured_predicates() for expr in self.subexpressions))
        yield self.output_predicate
        for subexpr in self.subexpressions:
            yield from subexpr.captured_predicates()

    def variables(self) -> Iterable[Variable]:
        for subexpr in self.subexpressions:
            yield from subexpr.variables()

    def check(self, toplevel_name: str, bound_variables: Tuple[str, ...]) -> None:
        # NOTE: We have to use the variable names (i.e., strings) here,
        #       because the query returns ASP variable objects, while the expressions return variable expression objects.
        #
        # All variables that appear in the query
        query_variables = set(str(v) for v in self.query.variables())
        # All variables that are fixed from the surrounding expression
        # (semantically equivalent: variables that are replaced by constants before evaluating the query for this expression)
        self.fixed_query_variables = tuple(query_variables.intersection(bound_variables))
        # All variables that are varying in the context of one result of this expression
        # (i.e., these variables vary and thus the content subexpression results in different contained objects),
        # and are also used in the construction of at least one subexpression
        used_varying_query_variables = query_variables.intersection(str(v) for v in self.variables())
        # We need to capture all fixed and (used) varying variables in the query, and ignore all others
        # IMPORTANT: The fixed variables must come first! (cf. get_captured_values)
        self.captured_variables = self.fixed_query_variables + tuple(used_varying_query_variables.difference(self.fixed_query_variables))
        assert len(set(self.captured_variables)) == len(self.captured_variables)
        self.used_varying_query_variables = self.captured_variables[len(self.fixed_query_variables):]
        assert set(self.used_varying_query_variables) == used_varying_query_variables

        for subexpr in self.subexpressions:
            subexpr.check(toplevel_name, bound_variables + tuple(query_variables))

    def get_captured_values(self, r: OutputResult, lc: LocalContext) -> Iterable[Tuple[str, ...]]:
        '''Return only those tuples of the `output_predicate` that assign the correct values for the fixed variables.'''
        for captured_values in r.answer_set.get(self.output_predicate, ()):
            # Only yield tuples that assign the correct values for the fixed variables
            for (i, v) in enumerate(self.fixed_query_variables):
                assert self.captured_variables[i] == v
                if lc.va[v] != captured_values[i]:
                    break
            else:
                # fixed_query_variables was exhausted without reaching `break`, which means all fixed variables have the correct value
                yield captured_values

    # @contextmanager
    # def assign_varying_variables(self, lc: LocalContext, values: Sequence[str]):
    #     assert len(self.captured_variables) == len(values)
    #     # Only assign the (used) varying values, the fixed variables are already assigned
    #     i = len(self.fixed_query_variables)
    #     with lc.assign_variables(self.captured_variables[i:], values[i:]):
    #         yield

    def eval_subexpression(self, expr: Expr, captured_values: Sequence[str], r: OutputResult, lc: LocalContext) -> Any:
        assert len(self.captured_variables) == len(captured_values)
        # Only assign the (used) varying values, the fixed variables are already assigned
        i = len(self.fixed_query_variables)
        with lc.assign_variables(self.captured_variables[i:], captured_values[i:]):
            return expr.evaluate(r, lc)


class ExprSet(ExprCollection):
    # TODO: Note the limitation somewhere (contents must be hashable)

    def __init__(self, query: asp.Query, content: Expr) -> None:
        super().__init__(query, [content])
        self.content = content

    def evaluate(self, r: OutputResult, lc: LocalContext) -> AbstractSet[Any]:
        make_set = r.registry.set_constructor  # type: ignore
        gen = (self.eval_subexpression(self.content, vs, r, lc) for vs in self.get_captured_values(r, lc))
        return make_set(gen)  # type: ignore


class ExprSequence(ExprCollection):
    def __init__(self, query: asp.Query, content: Expr, index: Variable) -> None:
        super().__init__(query, [content, index])
        self.content = content
        self.index = index

    def evaluate(self, r: OutputResult, lc: LocalContext) -> Sequence[Any]:
        def index_for(captured_values):
            str_value = captured_values[self.index_pos]
            try:
                return int(str_value)
            except ValueError as e:
                raise InvalidIndicesError('index variable is not an integer: {0!s}'.format(e))

        def content_for(captured_values):
            return self.eval_subexpression(self.content, captured_values, r, lc)

        # TODO: Options to determine how missing/duplicate indices should be handled
        # Currently: We require the indices to form a range of integers from 0 to n without any duplicates.
        all_captured_values = tuple(self.get_captured_values(r, lc))
        indices = sorted(index_for(captured_values) for captured_values in all_captured_values)
        if indices != list(range(len(indices))):
            raise InvalidIndicesError('not a valid range of indices')  # TODO: better message
        xs = sorted((index_for(captured_values), content_for(captured_values)) for captured_values in all_captured_values)
        make_sequence = r.registry.sequence_constructor  # type: ignore
        return make_sequence(x[1] for x in xs)  # type: ignore

    def check(self, toplevel_name: str, bound_variables: Tuple[str, ...]) -> None:
        super().check(toplevel_name, bound_variables)
        self.index_pos = self.captured_variables.index(self.index.name)


class ExprDictionary(ExprCollection):
    # TODO: Note the limitation somewhere (keys must be hashable)

    def __init__(self, query: asp.Query, content: Expr, key: Expr) -> None:
        super().__init__(query, [content, key])
        self.content = content
        self.key = key

    def evaluate(self, r: OutputResult, lc: LocalContext) -> Mapping[Any, Any]:
        d = {}  # type: MutableMapping[Any, Any]
        for captured_values in self.get_captured_values(r, lc):
            k = self.eval_subexpression(self.key, captured_values, r, lc)
            if k not in d:
                d[k] = self.eval_subexpression(self.content, captured_values, r, lc)
            else:
                raise DuplicateKeyError('Duplicate key: {0}'.format(repr(k)))
        make_dictionary = r.registry.dictionary_constructor  # type: ignore
        return make_dictionary(d)  # type: ignore


class OutputSpec:
    def __init__(self, named_exprs: Iterable[Tuple[str, Expr]]) -> None:
        exprs = {}  # type: MutableMapping[str, Expr]
        for (name, expr) in named_exprs:
            if name not in exprs:
                exprs[name] = expr
            else:
                raise RedefinedNameError('Duplicate top-level name: {0}'.format(name))
        # Note: easier with dict(named_exprs), check len(exprs) == len(named_exprs); but: error message is not as meaningful!
        self.exprs = exprs  # type: Mapping[str, Expr]
        # TODO: Check for cycles in references (currently we do that while mapping, but for consistency it would be nice to have it checked at time of construction -- it is some additional work though, while we get the result 'for free' during mapping)
        for (name, expr) in self.exprs.items():
            expr.check(toplevel_name=name, bound_variables=())  # , bound_references=self.exprs.keys())

    @staticmethod
    def empty() -> 'OutputSpec':
        return OutputSpec(())

    @staticmethod
    def parse(string: str) -> 'OutputSpec':
        return parser.parse_output_spec(string)

    def prepare_mapping(self, answer_set: asp.RawAnswerSet, registry: Registry) -> OutputResult:
        return OutputResult(self.exprs, answer_set, registry)

    def additional_rules(self) -> Iterable[asp.Rule]:
        for expr in self.exprs.values():
            yield from expr.additional_rules()

    def captured_predicates(self) -> Iterable[str]:
        # create a set to remove duplicates
        return set(chain(*(expr.captured_predicates() for expr in self.exprs.values())))
