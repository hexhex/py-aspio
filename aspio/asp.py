from collections import namedtuple
from typing import Any, Iterable, Mapping, Tuple, Union


class Variable(namedtuple('Variable', ['name'])):
    '''Represents a variable in ASP syntax.'''
    __slots__ = ()

    def __str__(self):
        return self.name


class AnonymousVariable():
    '''Represents an anonymous variable in ASP syntax.'''
    __slots__ = ()

    def __str__(self):
        return '_'


def quote(arg: Any) -> str:
    '''Enclose the given argument in double quotes, escaping any contained quotes and backslashes with a backslash.'''
    return '"' + str(arg).replace('\\', '\\\\').replace('\"', '\\\"') + '"'


# dlvhex2 distinguishes between unquoted and quoted strings,
# i.e. abc and "abc" are different constant symbols,
# or in other words, the program
#       p(abc). -p("abc").
# has an answer set.
# We must preserve this distinction in the query.
# Unquoted constants are represented by `str`, and quoted constants by `QuotedConstant`.
class QuotedConstant(namedtuple('QuotedConstant', ['value'])):
    '''Represents a quoted string constant in ASP syntax.'''
    __slots__ = ()

    def __str__(self):
        return quote(self.value)

Term = Union[int, str, QuotedConstant, Variable]
TermTuple = Tuple[Term, ...]


class Literal(namedtuple('Literal', ['predicate', 'arguments', 'defaultNegated'])):
    '''A literal, not necessarily ground, possibly default-negated'''
    __slots__ = ()

    def __str__(self):
        return ('not ' if self.defaultNegated else '') + self.predicate + '(' + ','.join(str(t) for t in self.arguments) + ')'

    def variables(self) -> Iterable[Variable]:
        for arg in self.arguments:
            if isinstance(arg, Variable):
                yield arg

Literal.predicate.__doc__ = 'predicate name (prefixed with a `-` for strongly negated literals)'
Literal.arguments.__doc__ = 'a tuple containing the argument terms, cf. type `TermTuple`'
Literal.defaultNegated.__doc__ = 'a bool determining whether the literal is default-negated'


class Query:
    '''A set of (possibly non-ground) literals, representing a query.'''

    def __init__(self, literals: Tuple[Literal, ...]) -> None:
        self.literals = literals

    def __str__(self) -> str:
        return ','.join(str(t) for t in self.literals)

    def variables(self) -> Iterable[Variable]:
        for lit in self.literals:
            yield from lit.variables()


Rule = str  # TODO: Should be a more sophisticated type to support passing the rule to the solver directly (when it is used via a shared library)

# "raw" answer set, i.e. the constants are just strings
RawAnswerSet = Mapping[str, Iterable[Tuple[str, ...]]]
