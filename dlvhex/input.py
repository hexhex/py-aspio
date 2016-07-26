import collections
import enum
import numbers
from abc import ABCMeta, abstractmethod
from typing import Iterable, Any, Union, Dict, Iterator, MutableSet, Sequence, AbstractSet
from typing.io import TextIO  # type: ignore
import dlvhex
from . import parser
from .errors import RedefinedNameError, UndefinedNameError


Context = Dict['Variable', Any]


class FactAccumulator(metaclass=ABCMeta):
    @abstractmethod
    def add_fact(self, predicate: str, args: Sequence[Any]) -> None:
        pass


class StreamAccumulator(FactAccumulator):
    def __init__(self, output_stream: TextIO) -> None:
        if not output_stream.writable:
            raise ValueError('output_stream must be writable')
        self._stream = output_stream

    def quote(self, arg: Any) -> str:
        '''Enclose the given argument in double quotes, escaping any contained quotes and backslashes with a backslash.'''
        return '"' + str(arg).replace('\\', '\\\\').replace('\"', '\\\"') + '"'

    def arg_str(self, arg: Any) -> str:
        '''Convert the given argument to a string suitable to be passed to dlvhex.'''
        if isinstance(arg, numbers.Integral):
            # Output integers without quotes (so we can use them for arithmetic in dlvhex)
            return str(arg)
        else:
            # Everything else is converted to a string and quoted unconditionally
            return self.quote(arg)

    def add_fact(self, predicate: str, args: Sequence[Any]) -> None:
        '''Writes a fact to the output stream, in the usual ASP syntax: predicate(arg1, arg2, arg3).'''
        # assert isinstance(predicate, str)
        assert len(predicate) > 0
        self._stream.write(predicate)
        self._stream.write('(')
        for (idx, arg) in enumerate(args):
            if idx > 0:
                self._stream.write(',')
            self._stream.write(self.arg_str(arg))
        self._stream.write(').\n')
        if dlvhex.debug:
            print(predicate, args, '\t=> ' + predicate + '(' + ', '.join(self.arg_str(x) for x in args) + ')')  # TODO: more sophisticated approach... "tee" output stream to stderr in constructor? see also http://stackoverflow.com/a/4985080/1889401


class AssignmentTarget(metaclass=ABCMeta):
    @abstractmethod
    def check_and_update_variable_bindings(self, bound_variables: MutableSet['Variable']) -> None:
        pass

    @abstractmethod
    def assign(self, value: Any, context: Context) -> None:
        pass


class Variable(AssignmentTarget):
    def __init__(self, name: str) -> None:
        assert len(name) > 0
        self._name = name

    def assign(self, value: Any, context: Context) -> None:
        context[self] = value

    def check_and_update_variable_bindings(self, bound_variables: MutableSet['Variable']) -> None:
        if self in bound_variables:
            raise RedefinedNameError('Variable {0} is defined twice'.format(self))
        bound_variables.add(self)

    def __repr__(self):
        return 'Variable({0})'.format(repr(self._name))

    def __str__(self):
        return self._name

    def __eq__(self, other):
        if isinstance(other, Variable):
            return self._name == other._name
        else:
            return NotImplemented

    def __hash__(self):
        return hash(self._name)


class TupleMatch(AssignmentTarget):
    def __init__(self, targets: Sequence[AssignmentTarget]) -> None:
        self._targets = tuple(targets)

    def assign(self, value: Any, context: Context) -> None:
        if len(value) != len(self._targets):
            raise ValueError('length mismatch')  # TODO better message
        for t, v in zip(self._targets, value):
            t.assign(v, context)

    def check_and_update_variable_bindings(self, bound_variables: MutableSet[Variable]) -> None:
        for t in self._targets:
            t.check_and_update_variable_bindings(bound_variables)

    def __repr__(self):
        return 'TupleMatch([{0}])'.format(','.join(repr(t) for t in self._targets))

    def __str__(self):
        return '({0})'.format(', '.join(str(t) for t in self._targets))


class Accessor:
    def __init__(self, variable: Variable, attribute_path: Sequence[Union[int, str]]) -> None:
        self._variable = variable
        self._attribute_path = tuple(attribute_path)
        # TODO:
        # We should also allow string subscripts (would allow easy access to dicts with fixed keys, e.g. JSON data)
        # => don't store raw int and str objects in the attribute_path, wrap them in Attribute(name) and Subscript(index_or_key) classes.

    def __str__(self) -> str:
        return str(self._variable) + ''.join('.' + repr(attr) for attr in self._attribute_path)

    def check_variable_bindings(self, bound_variables: AbstractSet[Variable]) -> None:
        if self._variable not in bound_variables:
            raise UndefinedNameError('Undefined variable {0} is being accessed'.format(self._variable))

    def perform_access(self, context: Context) -> Any:
        '''Performs the represented object access relative to the given context.'''
        result = context[self._variable]
        for attr in self._attribute_path:
            if isinstance(attr, int):
                # index access
                result = result[attr]  # TODO: handle errors (throw ValueError)
            else:
                # attribute access
                result = getattr(result, attr)  # TODO: handle errors (throw ValueError)
        return result


@enum.unique
class IterationType(enum.Enum):
    SET = 1
    SEQUENCE = 2
    DICTIONARY = 3


class Iteration:
    def __init__(self, target: AssignmentTarget, itertype: IterationType, accessor: Accessor) -> None:
        self._target = target
        self._itertype = itertype
        self._accessor = accessor

    def check_and_update_variable_bindings(self, bound_variables: MutableSet[Variable]) -> None:
        self._accessor.check_variable_bindings(bound_variables)
        self._target.check_and_update_variable_bindings(bound_variables)

    def get_collection_iterator(self, context: Context) -> Iterator[Any]:
        collection = self._accessor.perform_access(context)
        if self._itertype == IterationType.SET:
            return iter(collection)
        elif self._itertype == IterationType.SEQUENCE:
            # TODO: enumerate works with any iterable, but maybe we should check if the collection is a sequence type and raise an error otherwise? Might prevent some silent errors.
            return enumerate(collection)  # yields (index, element) tuples
        elif self._itertype == IterationType.DICTIONARY:
            if isinstance(collection, collections.Mapping):
                return iter(collection.items())  # yields (key, element) tuples
            else:
                raise ValueError('When trying to perform iteration {0}: collection is not a dictionary, got instead: {1}'.format(repr(self), repr(collection)))

    def assign_to_target(self, value: Any, context: Context) -> None:
        self._target.assign(value, context)

    def __str__(self) -> str:
        return 'FOR {0} IN {1} {2}'.format(str(self._target), self._itertype.name, str(self._accessor))


class Predicate:
    def __init__(self, predicate: str, arguments: Sequence[Accessor], iterations: Sequence[Iteration]) -> None:
        '''Represents a single input mapping that produces facts of a single predicate.

        @param predicate: The name of the predicate to generate. Must be a non-empty string.
        @param arguments: A list of Accessor instances that describe the arguments of the generated facts.
        @param iterations: A list of Iteration instances that describe how to generate the set of facts from the input arguments.
        '''
        self._predicate = predicate
        self._arguments = tuple(arguments)
        self._iterations = tuple(iterations)

    def check_variable_bindings(self, input_variables: Iterable[Variable]) -> None:
        bound_variables = set(input_variables)
        for it in self._iterations:
            it.check_and_update_variable_bindings(bound_variables)  # adds newly bound variables to the set
        for arg in self._arguments:
            arg.check_variable_bindings(bound_variables)

    def perform_mapping(self, initial_context: Context, accumulator: FactAccumulator) -> None:
        # TODO: Add some explanation and use better variable names (it/iter??? maybe rename InputIteration to InputLoop so we don't confuse the python iterator concept with our iteration concept)
        context = initial_context.copy()
        iter_stack = []  # type: List[Iterator[Any]]
        while True:
            # Advance innermost iteration
            if len(iter_stack) > 0:
                col_iter = iter_stack[-1]
                it = self._iterations[len(iter_stack) - 1]
                try:
                    it.assign_to_target(next(col_iter), context)
                except StopIteration:
                    iter_stack.pop()
                    if len(iter_stack) == 0:
                        # Last iteration stopped? We're done
                        break
                    else:
                        continue

            if len(iter_stack) == len(self._iterations):
                # All iterations have been performed
                # => Generate a fact
                accumulator.add_fact(self._predicate, tuple(arg.perform_access(context) for arg in self._arguments))
                if len(self._iterations) == 0:
                    break
            else:
                # Haven't yet performed all iterations, move on to inner iteration
                assert(len(iter_stack) < len(self._iterations))
                it = self._iterations[len(iter_stack)]
                iter_stack.append(it.get_collection_iterator(context))


class InputSpec:
    def __init__(self, parameters: Sequence[Variable], predicates: Iterable[Predicate]) -> None:
        '''Represents an INPUT statement, i.e. the complete input mapping description for an ASP program.

        @param parameters: The input parameters that need to be given when solving the program.
        @param predicates: A list of Predicate instances describing how to generate facts from the input arguments.
        '''
        self._parameters = tuple(parameters)
        self._predicates = tuple(predicates)
        # Check for name errors in input arguments (i.e. there must not be duplicate names)
        if len(self._parameters) != len(set(self._parameters)):
            raise RedefinedNameError('Input parameters must have unique names')
        # Check for name errors in accessor and iteration definitions (two kinds of errors: either using an undefined variable name, or redefining a variable name)
        for pred in self._predicates:
            pred.check_variable_bindings(self._parameters)

    @staticmethod
    def empty() -> 'InputSpec':
        return InputSpec([], [])

    @staticmethod
    def parse(string: str) -> 'InputSpec':
        return parser.parse_input_spec(string)

    def perform_mapping(self, arguments: Sequence[Any], accumulator: FactAccumulator) -> None:
        '''Perform the input mapping.

        Transforms the arguments to an ASP representation according to the InputSpec,
        and passes the results to the given accumulator (see FactAccumulator class).
        '''
        if len(arguments) != len(self._parameters):
            raise ValueError('Wrong number of arguments: expecting {0}, got {1}'.format(len(self._parameters), len(arguments)))
        for pred in self._predicates:
            context = dict(zip(self._parameters, arguments))
            pred.perform_mapping(context, accumulator)
