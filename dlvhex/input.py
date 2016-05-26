import io
from . import parser


class InputAccessor:
    def __init__(self, variable, attribute_path):
        self._variable = variable
        self._attribute_path = tuple(attribute_path)

    def __repr__(self):
        return self._variable + ''.join('.' + repr(attr) for attr in self._attribute_path)


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
        # evtl. bringt "yield" was?


class InputPredicate:
    def __init__(self, predicate, arguments, iterations):
        """Represents a single input mapping that produces facts of a single predicate.

        @param predicate: The name of the predicate to generate.
        @param arguments: A list of InputAccessor instances that describe the arguments of the generated facts.
        @param iterations: A list of InputIteration instances that describe how to generate the set of facts from the input arguments.
        """
        self._predicate = predicate
        self._arguments = tuple(arguments)
        self._iterations = tuple(iterations)

    def perform_mapping(self, initial_variable_assignment, output_stream):
        pass


class InputSpecification:
    _PARSER = None

    @classmethod
    def parse(cls, string):
        if cls._PARSER is None:
            cls._PARSER = parser.InputParser()
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

    def perform_mapping(self, input_args, output_stream):
        """Perform the input mapping.

        Transforms the input_args to an ASP representation according to the InputMapping,
        and writes the results to the given output_stream (a writable stream in text mode).
        """
        if len(input_args) != len(self._arguments):
            raise ValueError("Wrong number of arguments: expecting %d, got %d" % (len(self._arguments), len(input_args)))
        if not (isinstance(output_stream, io.TextIOBase) and output_stream.writable):
            raise ValueError("output_stream must be a writable text stream")
        for pred in self._predicates:
            variable_assignment = dict(zip(self._arguments, input_args))
            pred.perform_mapping(variable_assignment, output_stream)
