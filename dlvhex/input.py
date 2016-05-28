import io
from . import parser


class StreamAccumulator:
    def __init__(self, output_stream):
        if not isinstance(output_stream, io.TextIOBase):
            raise ValueError("output_stream must be a text stream")
        if not output_stream.writable:
            raise ValueError("output_stream must be writable")
        self._stream = output_stream

    def add_fact(self, predicate, *args):
        # TODO write to self._stream
        pass


class InputAccessor:
    def __init__(self, variable, attribute_path):
        self._variable = variable
        self._attribute_path = tuple(attribute_path)

    def __repr__(self):
        return self._variable + ''.join('.' + repr(attr) for attr in self._attribute_path)

    def perform_access(self, variable_assignment):
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


class InputIteration:
    def __init__(self, index_variable, element_variable, accessor):
        # index_variable can be None (e.g. for sets or if the index isn't needed)
        self._index_variable = index_variable
        self._element_variable = element_variable
        self._accessor = accessor

    def __repr__(self):
        return 'FOR (' + repr(self._index_variable) + ', ' + repr(self._element_variable) + ') IN ' + repr(self._accessor)

    def perform_iteration(self, variable_assignment):
        """Performs the represented iteration relative to the given variable assignment.

        @returns
            An iterable containing the newly generated variable assignments.
            The returned variable assignments contain all the bindings of the original assignment unchanged,
            but will add one or two new bindings.
        """
        # TODO: It does not seem good to create new objects for every single fact...
        # Can't we reuse a single dictionary and update its contents during iteration?
        # maybe perform iteration in InputPredicate, using a stack?
        collection = self._accessor.perform_access(variable_assignment)
        if self._index_variable is not None:
            pass  # TODO
        else:
            for x in collection:
                d = variable_assignment.copy()
                d[self._element_variable] = x
                yield d

    def get_collection_iterator(self, variable_assignment):
        collection = self._accessor.perform_access(variable_assignment)
        if self._index_variable is not None:
            pass  # TODO
        else:
            yield from collection

    def assign_variables(self, value, variable_assignment):
        if self._index_variable is not None:
            pass  # TODO
        else:
            variable_assignment[self._element_variable] = value

    def delete_variables(self, variable_assignment):
        if self._index_variable is not None:
            del variable_assignment[self._index_variable]
        del variable_assignment[self._element_variable]


class InputPredicate:
    def __init__(self, predicate, arguments, iterations):
        """Represents a single input mapping that produces facts of a single predicate.

        @param predicate: The name of the predicate to generate.
        @param arguments: A list of InputAccessor instances that describe the arguments of the generated facts.
        @param iterations: A list of InputIteration instances that describe how to generate the set of facts from the input arguments.
        """
        print(predicate, arguments, iterations)
        self._predicate = predicate
        self._arguments = tuple(arguments)
        self._iterations = tuple(iterations)

    def perform_mapping(self, initial_variable_assignment, accumulator):
        va = initial_variable_assignment.copy()
        iter_stack = []
        while True:
            # Advance innermost iteration
            if len(iter_stack) > 0:
                col_iter = iter_stack[-1]
                it = self._iterations[len(iter_stack) - 1]
                try:
                    it.assign_variables(next(col_iter), va)
                except StopIteration:
                    iter_stack.pop()
                    # it.delete_variables(va)  # TODO: Not strictly necessary
                    if len(iter_stack) == 0:
                        # Last iteration stopped? We're done
                        break
                    else:
                        continue

            if len(iter_stack) == len(self._iterations):
                # All iterations have been performed
                # => Generate a fact
                accumulator.add_fact(self._predicate, map(lambda arg: arg.perform_access(va), self._arguments))
                if len(self._iterations) == 0:
                    break
            else:
                # Haven't yet performed all iterations, move on to inner iteration
                assert(len(iter_stack) < len(self._iterations))
                it = self._iterations[len(iter_stack)]
                iter_stack.append(it.get_collection_iterator(va))


class InputSpecification:
    _PARSER = None

    @classmethod
    def parse(cls, string):
        if cls._PARSER is None:
            cls._PARSER = parser.InputSpecParser()
        return parser.parse(cls._PARSER, string)

    def __init__(self, arguments, predicates):
        """Represents an INPUT statement, i.e. the complete input mapping description for an ASP program.

        @param arguments: The input arguments that need to be given when solving the program.
        @param predicates: A list of InputPredicate instances describing how to generate facts from the input arguments.
        """
        if len(arguments) != len(set(arguments)):
            raise ValueError("Input arguments must have unique names")
        self._arguments = tuple(arguments)
        self._predicates = tuple(predicates)
        # TODO: Check for name errors in accessor and iteration definitions (two kinds: using an undefined variable name, redefining a variable name)

    def perform_mapping(self, input_args, accumulator):
        """Perform the input mapping.

        Transforms the input_args to an ASP representation according to the InputMapping,
        and writes the results to the given output_stream (a writable stream in text mode).
        """
        if len(input_args) != len(self._arguments):
            raise ValueError("Wrong number of arguments: expecting %d, got %d" % (len(self._arguments), len(input_args)))
        for pred in self._predicates:
            variable_assignment = dict(zip(self._arguments, input_args))
            pred.perform_mapping(variable_assignment, accumulator)
