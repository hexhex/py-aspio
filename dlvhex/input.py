import collections
import numbers
from abc import ABCMeta, abstractmethod
from typing import Iterable, Any, Union, Dict, Iterator, MutableSet, Sequence, AbstractSet, Tuple
from typing.io import TextIO  # type: ignore
import dlvhex
from .parser import parse_input_spec
from .errors import UndefinedVariableError, RedefinedVariableError


# type aliases
Variable = str
VariableAssignment = Dict[Variable, Any]


class FactAccumulator(metaclass=ABCMeta):
    @abstractmethod
    def add_fact(self, predicate: str, args: Sequence[Any]) -> None:
        pass


class StreamAccumulator(FactAccumulator):
    def __init__(self, output_stream: TextIO) -> None:
        # if not isinstance(output_stream, io.TextIOBase):
        #     raise ValueError("output_stream must be a text stream")
        if not output_stream.writable:
            raise ValueError("output_stream must be writable")
        self._stream = output_stream

    def quote(self, arg: Any) -> str:
        """Enclose the given argument in double quotes, escaping any contained quotes with a backslash."""
        return '"' + str(arg).replace(r'"', r'\"') + '"'

    def arg_str(self, arg: Any) -> str:
        """Convert the given argument to a string suitable to be passed to dlvhex."""
        if isinstance(arg, numbers.Integral):
            # Output integers without quotes (so we can use them for arithmetic in dlvhex)
            return str(arg)
        else:
            # Everything else is converted to a string and quoted unconditionally
            # (however: dlvhex does not consider "abc" and abc (with/without quotes) to be equal... that could lead to problems, TODO: investigate)
            return self.quote(arg)

    def add_fact(self, predicate: str, args: Sequence[Any]) -> None:
        """Writes a fact to the output stream, in the usual ASP syntax: predicate(arg1, arg2, arg3)."""
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
            print(predicate, args)  # TODO: more sophisticated approach... "tee" output stream to stderr in constructor? see also http://stackoverflow.com/a/4985080/1889401


class InputAccessor:
    def __init__(self, variable: Variable, attribute_path: Sequence[Union[int, str]]) -> None:
        self._variable = variable
        self._attribute_path = tuple(attribute_path)

    def __repr__(self) -> str:
        return self._variable + ''.join('.' + repr(attr) for attr in self._attribute_path)

    def check_variable_bindings(self, bound_variables: AbstractSet[Variable]) -> None:
        if self._variable not in bound_variables:
            raise UndefinedVariableError("Undefined variable {0} is being accessed".format(self._variable))

    def perform_access(self, variable_assignment: VariableAssignment) -> Any:
        """Performs the represented object access relative to the given variable assignment."""
        result = variable_assignment[self._variable]
        for attr in self._attribute_path:
            if isinstance(attr, int):
                # index access
                result = result[attr]  # TODO: handle errors (throw ValueError)
            else:
                # attribute access
                result = getattr(result, attr)  # TODO: handle errors (throw ValueError)
        return result


class InputIteration(metaclass=ABCMeta):
    @abstractmethod
    def check_and_update_variable_bindings(self, bound_variables: MutableSet[Variable]) -> None:
        pass

    @abstractmethod
    def get_collection_iterator(self, variable_assignment: VariableAssignment) -> Iterator[Any]:
        pass

    @abstractmethod
    def assign_variables(self, value: Any, variable_assignment: VariableAssignment) -> None:
        pass

    def _check_var_and_update(self, var: Variable, bound_variables: MutableSet[Variable]) -> None:
        """Helper function for subclasses. Add variable to given variable assignment, raising a ValueError if it is already contained."""
        if var in bound_variables:
            raise RedefinedVariableError("Variable {0} is defined twice".format(var))
        bound_variables.add(var)


class InputSetIteration(InputIteration):
    def __init__(self, element_variable: Variable, accessor: InputAccessor) -> None:
        self.element_variable = element_variable
        self.accessor = accessor

    def __repr__(self) -> str:
        return 'FOR {0} IN SET {1}'.format(repr(self.element_variable), repr(self.accessor))

    def check_and_update_variable_bindings(self, bound_variables: MutableSet[Variable]) -> None:
        self.accessor.check_variable_bindings(bound_variables)
        self._check_var_and_update(self.element_variable, bound_variables)

    def get_collection_iterator(self, variable_assignment: VariableAssignment) -> Iterator[Any]:
        return iter(self.accessor.perform_access(variable_assignment))

    def assign_variables(self, value: Any, variable_assignment: VariableAssignment) -> None:
        variable_assignment[self.element_variable] = value


class InputSequenceIteration(InputIteration):
    def __init__(self, index_variable: Variable, element_variable: Variable, accessor: InputAccessor) -> None:
        self.index_variable = index_variable
        self.element_variable = element_variable
        self.accessor = accessor

    def __repr__(self) -> str:
        return 'FOR ({0}, {1}) IN SEQUENCE {2}'.format(repr(self.index_variable), repr(self.element_variable), repr(self.accessor))

    def check_and_update_variable_bindings(self, bound_variables: MutableSet[Variable]) -> None:
        self.accessor.check_variable_bindings(bound_variables)
        if self.index_variable is not None:
            self._check_var_and_update(self.index_variable, bound_variables)
        self._check_var_and_update(self.element_variable, bound_variables)

    def get_collection_iterator(self, variable_assignment: VariableAssignment) -> Iterator[Tuple[int, Any]]:
        # yields (index, element) tuples
        return enumerate(self.accessor.perform_access(variable_assignment))
        # TODO: enumerate works with any iterable, but maybe we should check if the collection is a sequence type and raise an error otherwise? Might prevent some silent errors.

    def assign_variables(self, value: Tuple[int, Any], variable_assignment: VariableAssignment) -> None:
        variable_assignment[self.index_variable] = value[0]
        variable_assignment[self.element_variable] = value[1]


class InputMappingIteration(InputIteration):
    def __init__(self, key_variable: Variable, element_variable: Variable, accessor: InputAccessor) -> None:
        self.key_variable = key_variable
        self.element_variable = element_variable
        self.accessor = accessor

    def __repr__(self) -> str:
        return 'FOR ({0}, {1}) IN MAPPING {2}'.format(repr(self.key_variable), repr(self.element_variable), repr(self.accessor))

    def check_and_update_variable_bindings(self, bound_variables: MutableSet[Variable]) -> None:
        self.accessor.check_variable_bindings(bound_variables)
        if self.key_variable is not None:
            self._check_var_and_update(self.key_variable, bound_variables)
        self._check_var_and_update(self.element_variable, bound_variables)

    def get_collection_iterator(self, variable_assignment: VariableAssignment) -> Iterator[Tuple[Any, Any]]:
        collection = self.accessor.perform_access(variable_assignment)
        if isinstance(collection, collections.Mapping):
            # yields (key, element) tuples
            return iter(collection.items())
        else:
            raise ValueError('When trying to perform iteration {0}: collection is not a mapping, got instead: {1}'.format(repr(self), repr(collection)))

    def assign_variables(self, value: Tuple[Any, Any], variable_assignment: VariableAssignment) -> None:
        variable_assignment[self.key_variable] = value[0]
        variable_assignment[self.element_variable] = value[1]


class InputPredicate:
    def __init__(self, predicate: str, arguments: Sequence[InputAccessor], iterations: Sequence[InputIteration]) -> None:
        """Represents a single input mapping that produces facts of a single predicate.

        @param predicate: The name of the predicate to generate. Must be a non-empty string.
        @param arguments: A list of InputAccessor instances that describe the arguments of the generated facts.
        @param iterations: A list of InputIteration instances that describe how to generate the set of facts from the input arguments.
        """
        self._predicate = predicate
        self._arguments = tuple(arguments)
        self._iterations = tuple(iterations)

    def check_variable_bindings(self, input_variables: Iterable[Variable]) -> None:
        bound_variables = set(input_variables)
        for it in self._iterations:
            it.check_and_update_variable_bindings(bound_variables)  # adds newly bound variables to the set
        for arg in self._arguments:
            arg.check_variable_bindings(bound_variables)

    def perform_mapping(self, initial_variable_assignment: VariableAssignment, accumulator: FactAccumulator) -> None:
        # TODO: Add some explanation and use better variable names (it/iter??? maybe rename InputIteration to InputLoop so we don't confuse the python iterator concept with our iteration concept)
        va = initial_variable_assignment.copy()
        iter_stack = []  # type: List[Iterator[Any]]
        while True:
            # Advance innermost iteration
            if len(iter_stack) > 0:
                col_iter = iter_stack[-1]
                it = self._iterations[len(iter_stack) - 1]
                try:
                    it.assign_variables(next(col_iter), va)
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
                accumulator.add_fact(self._predicate, tuple(arg.perform_access(va) for arg in self._arguments))
                if len(self._iterations) == 0:
                    break
            else:
                # Haven't yet performed all iterations, move on to inner iteration
                assert(len(iter_stack) < len(self._iterations))
                it = self._iterations[len(iter_stack)]
                iter_stack.append(it.get_collection_iterator(va))


class InputSpecification:
    parse = parse_input_spec

    def __init__(self, arguments: Sequence[Variable], predicates: Iterable[InputPredicate]) -> None:
        """Represents an INPUT statement, i.e. the complete input mapping description for an ASP program.

        @param arguments: The input arguments that need to be given when solving the program.
        @param predicates: A list of InputPredicate instances describing how to generate facts from the input arguments.
        """
        self._arguments = tuple(arguments)
        self._predicates = tuple(predicates)
        # Check for name errors in input arguments (i.e. there must not be duplicate names)
        if len(arguments) != len(set(arguments)):
            raise RedefinedVariableError("Input arguments must have unique names")
        # Check for name errors in accessor and iteration definitions (two kinds of errors: either using an undefined variable name, or redefining a variable name)
        for pred in self._predicates:
            pred.check_variable_bindings(self._arguments)

    def perform_mapping(self, input_args: Sequence[Any], accumulator: FactAccumulator) -> None:
        """Perform the input mapping.

        Transforms the input_args to an ASP representation according to the InputMapping,
        and passes the results to the given accumulator (see FactAccumulator class).
        """
        if len(input_args) != len(self._arguments):
            raise ValueError("Wrong number of arguments: expecting %d, got %d" % (len(self._arguments), len(input_args)))
        for pred in self._predicates:
            variable_assignment = dict(zip(self._arguments, input_args))
            pred.perform_mapping(variable_assignment, accumulator)
