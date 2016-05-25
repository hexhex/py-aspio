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
    def __init__(self, arguments, predicates):
        """Represents an INPUT statement, i.e. the complete input mapping description for an ASP program.

        @param arguments: The input arguments that need to be given when solving the program.
        @param predicates: A list of InputPredicate instances describing how to generate facts from the input arguments.
        """
        self._arguments = tuple(arguments)
        self._predicates = tuple(predicates)
        # TODO: Check for name errors in accessor and iteration definitions (two kinds: using an undefined variable name, redefining a variable name)

    def perform_mapping(self, input_args, output_stream):
        pass
