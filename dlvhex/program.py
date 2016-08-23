from copy import copy
from itertools import chain
from pathlib import Path
from typing import Any, IO, Iterable, Iterator, List, Mapping, Optional, Union  # noqa
from .helper.typing import AnswerSet, ClosableIterable
from .solver import Solver
from .helper import CachingIterable
from .input import InputSpec, StreamAccumulator
from .output import UndefinedNameError, OutputSpec
from .parser import parse_embedded_spec
from .registry import Registry, global_registry

__all__ = ['Program']


class Program:
    '''Represents an answer set program.'''

    def __init__(self,
                 *,
                 filename: Optional[Union[str, Path]] = None,
                 code: Optional[str] = None,
                 use_global_registry: bool = True) -> None:
        '''Initialize an answer set program.

        For convenience, calls the appropriate `append...` method with the given `filename` and `code` keyword arguments.
        '''
        self.file_parts = []  # type: List[str]
        self.code_parts = []  # type: List[str]
        self._input_spec = None  # type: Optional[InputSpec]
        self._output_spec = None  # type: Optional[OutputSpec]
        self.solver = None  # type: Solver
        self.local_registry = copy(global_registry) if use_global_registry else Registry()  # type: Registry
        self.register = self.local_registry.register
        self.register_dict = self.local_registry.register_dict
        self.import_from_module = self.local_registry.import_from_module
        if filename is not None:
            self.append_file(filename)
        if code is not None:
            self.append_code(code)

    @property
    def input_spec(self):
        '''The input specification, if one has been set or parsed from input, or an empty specification otherwise.'''
        if self._input_spec is not None:
            return self._input_spec
        else:
            return InputSpec.empty()

    @input_spec.setter
    def input_spec(self, value):
        self._input_spec = value

    @property
    def has_input_spec(self):
        '''True iff an input specification has been set.'''
        return self._input_spec is not None

    @property
    def output_spec(self):
        '''The output specification, if one has been set or parsed from output, or an empty specification otherwise.'''
        if self._output_spec is not None:
            return self._output_spec
        else:
            return OutputSpec.empty()

    @output_spec.setter
    def output_spec(self, value):
        self._output_spec = value

    @property
    def has_output_spec(self):
        '''True iff an output specification has been set.'''
        return self._output_spec is not None

    def parse_spec(self, code: str) -> None:
        i, o = parse_embedded_spec(code)
        if i is not None:
            if not self.has_input_spec:
                self.input_spec = i
            else:
                raise ValueError("Only one INPUT specification per program is allowed.")
        if o is not None:
            if not self.has_output_spec:
                self.output_spec = o
            else:
                raise ValueError("Only one OUTPUT specification per program is allowed.")

    def append_file(self, filename: Union[str, Path], *, parse_io_spec: bool = True) -> None:
        '''Append ASP code contained in the given file to the program.

        Note that unless the `parse_io_spec` argument is `False`, the file is opened immediately to extract any embedded I/O specifications.
        The file path is passed to the solver that will read the actual ASP code at the time of solving.
        '''
        filename = str(filename)  # also support pathlib.Path instances
        self.file_parts.append(filename)
        if parse_io_spec:
            encoding = self.solver.encoding if self.solver is not None else Solver.default_encoding
            with open(filename, 'rt', encoding=encoding) as file:
                self.parse_spec(file.read())

    def append_code(self, code: str, *, parse_io_spec: bool = True) -> None:
        '''Append the given ASP code to the program.

        Unless the `parse_io_spec` argument is `False`, any embedded I/O specifications are extracted from the given string.
        '''
        self.code_parts.append(code)
        if parse_io_spec:
            self.parse_spec(code)


    def solve(self, *input_arguments, solver: Optional[Solver] = None, cache: bool = True, options: Optional[Iterable[str]] = None) -> 'Results':
        '''Solve the ASP program with the given input arguments and return a collection of answer sets.

        If deterministic cleanup of the solver subprocess is required, call close() on the returned object,
        or use the returned object as a context manager in a `with` statement.
        '''
        # TODO: Also allow to pass input arguments as keyword arguments, with names as defined in the input spec
        if solver is None:
            solver = self.solver
        if solver is None:
            solver = Solver()
        if options is None:
            options = []

        def write_asp_input(text_stream: IO[str]) -> None:
            '''Write all facts and rules that are needed in addition to the original ASP code to the given stream.'''
            # Map input data and pass it over the stream
            # Raises exception if the input arguments are not as expected (e.g., wrong count, an attribute does not exist, ...)
            self.input_spec.perform_mapping(input_arguments, StreamAccumulator(text_stream))
            # Additional rules required for output mapping
            text_stream.write('\n'.join(str(rule) for rule in self.output_spec.additional_rules()))
            # Pass code given as string over stdin
            for code in self.code_parts:
                text_stream.write(code)

        answer_sets = solver.run(
            write_input=write_asp_input,
            capture_predicates=self.output_spec.captured_predicates(),
            file_args=self.file_parts,
            options=options
        )
        return Results(answer_sets, self.output_spec, self.local_registry, cache)

    def solve_one(self, *input_arguments, solver: Optional[Solver] = None, options: Optional[Iterable[str]] = None) -> Optional['Result']:
        '''Solve the ASP program and return one of the computed answer sets, or None if no answer set exists. No special cleanup is necessary.'''
        if options is None:
            options = []
        options = chain(options, ['--number=1'])
        with self.solve(*input_arguments, solver=solver, cache=False, options=options) as results:
            try:
                return next(iter(results))
            except StopIteration:
                return None


class Results(Iterable['Result']):
    '''The collection of results of a dlvhex2 invocation, corresponding to the set of all answer sets.'''
    # TODO: Describe implicit access to mapped objects through __getattr__ (e.g. .graph iterates over answer sets, returning the "graph" object for every answer set)

    def __init__(self, answer_sets: ClosableIterable[AnswerSet], output_spec: OutputSpec, registry: Registry, cache: bool) -> None:
        self.output_spec = output_spec
        self.registry = registry
        self.answer_sets = answer_sets
        self.results = (
            Result(answer_set, self.output_spec, self.registry) for answer_set in self.answer_sets
        )  # type: Iterable[Result]
        if cache:
            self.results = CachingIterable(self.results)

    def __iter__(self) -> Iterator['Result']:
        # Make sure we can only create one results iterator if we aren't caching
        assert self.results is not None, 'Pass cache=True if you need to iterate over dlvhex results multiple times.'
        results = self.results
        if type(self.results) != CachingIterable:
            self.results = None
        yield from results

    def __getattr__(self, name: str) -> Any:
        if name.startswith('all_'):
            return ResultsAttributeIterator(self, name[4:])
        else:
            raise AttributeError("No attribute with name {0!r}. Prefix an output variable name with 'all_' when iterating over its values for all answer sets.".format(name))

    def close(self) -> None:
        self.answer_sets.close()

    def __enter__(self) -> 'Results':
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        self.close()
        return False


class ResultsAttributeIterator(Iterator[Any]):
    '''Helps with cleanup when using shortcuts.'''

    def __init__(self, results, name):
        self.results = results
        self.results_iter = iter(results)
        self.name = name

    def __iter__(self):
        return self

    def __next__(self):
        return getattr(next(self.results_iter), self.name)

    def close(self):
        self.results.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False


class Result:
    '''Represents a single answer set.'''

    def __init__(self, answer_set: AnswerSet, output_spec: OutputSpec, registry: Registry) -> None:
        self._r = output_spec.prepare_mapping(answer_set, registry)

    def get(self, name: str) -> Any:
        return self._r.get_object(name)

    def __getattr__(self, name: str) -> Any:
        try:
            return self.get(name)
        except UndefinedNameError as e:
            raise AttributeError(e)
