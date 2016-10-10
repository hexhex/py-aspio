import logging
import numbers
from copy import copy
from pathlib import Path
from typing import Any, IO, Iterable, Iterator, List, Mapping, Optional, Sequence, Union  # noqa
from .helper.typing import ClosableIterable
from .solver import DefaultSolver, Solver, SolverOptions
from .helper import CachingIterable
from .input import InputSpec, FactAccumulator
from .output import UndefinedNameError, OutputSpec
from .parser import parse_embedded_spec
from .registry import Registry, global_registry
from . import asp

__all__ = ['Program']

log = logging.getLogger(__name__)


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
        if filename is not None:
            self.append_file(filename)
        if code is not None:
            self.append_code(code)

    def __copy__(self) -> 'Program':
        other = Program()
        other.file_parts = copy(self.file_parts)
        other.code_parts = copy(self.code_parts)
        other._input_spec = copy(self._input_spec)
        other._output_spec = copy(self._output_spec)
        other.solver = copy(self.solver)
        other.local_registry = copy(self.local_registry)
        return other

    @property
    def local_registry(self) -> Registry:
        return self._local_registry

    @local_registry.setter
    def local_registry(self, value: Registry) -> None:
        self._local_registry = value
        self.register = self._local_registry.register
        self.register_dict = self._local_registry.register_dict
        self.import_from_module = self._local_registry.import_from_module

    @property
    def input_spec(self) -> InputSpec:
        '''The input specification, if one has been set or parsed from input, or an empty specification otherwise.'''
        if self._input_spec is not None:
            return self._input_spec
        else:
            return InputSpec.empty()

    @input_spec.setter
    def input_spec(self, value: InputSpec) -> None:
        self._input_spec = value

    @property
    def has_input_spec(self) -> bool:
        '''True iff an input specification has been set.'''
        return self._input_spec is not None

    @property
    def output_spec(self) -> OutputSpec:
        '''The output specification, if one has been set or parsed from output, or an empty specification otherwise.'''
        if self._output_spec is not None:
            return self._output_spec
        else:
            return OutputSpec.empty()

    @output_spec.setter
    def output_spec(self, value: OutputSpec) -> None:
        self._output_spec = value

    @property
    def has_output_spec(self) -> bool:
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

    def append_file(self, filename: Union[str, Path], *, parse_io_spec: bool = True, encoding: str = 'UTF-8') -> None:
        '''Append ASP code contained in the given file to the program.

        Note that unless the `parse_io_spec` argument is `False`, the file is opened immediately to extract any embedded I/O specifications.
        The file path is passed to the solver that will read the actual ASP code at the time of solving.
        '''
        filename = str(filename)  # also support pathlib.Path instances
        # TODO: If the encoding differs from what the solver expects, we should just read the file and append it to the code parts
        self.file_parts.append(filename)
        if parse_io_spec:
            with open(filename, 'rt', encoding=encoding) as file:
                self.parse_spec(file.read())

    def append_code(self, code: str, *, parse_io_spec: bool = True) -> None:
        '''Append the given ASP code to the program.

        Unless the `parse_io_spec` argument is `False`, any embedded I/O specifications are extracted from the given string.
        '''
        self.code_parts.append(code)
        if parse_io_spec:
            self.parse_spec(code)

    def solve(self,
              *input_arguments,
              solver: Optional[Solver] = None,
              options: Optional[SolverOptions] = None,
              cache: bool = True) -> 'Results':
        '''Solve the ASP program with the given input arguments and return a collection of answer sets.

        If deterministic cleanup of the solver subprocess is required, call close() on the returned object,
        or use the returned object as a context manager in a `with` statement.
        '''
        if solver is None:
            solver = self.solver
            if solver is None:
                solver = DefaultSolver()

        def write_asp_input(text_stream: IO[str]) -> None:
            '''Write all facts and rules that are needed in addition to the original ASP code to the given stream.'''
            # Map input data and pass it over the stream
            # Raises exception if the input arguments are not as expected (e.g., wrong count, an attribute does not exist, ...)
            self.input_spec.perform_mapping(input_arguments, StreamAccumulator(text_stream))
            # Additional rules required for output mapping
            for rule in self.output_spec.additional_rules():
                log.debug('Program: Adding helper rule %r', rule)
                text_stream.write(str(rule))
                text_stream.write('\n')
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

    def solve_one(self,
                  *input_arguments,
                  solver: Optional[Solver] = None,
                  options: Optional[SolverOptions] = None) -> Optional['Result']:
        '''Solve the ASP program and return one of the computed answer sets, or None if no answer set exists. No special cleanup is necessary.'''
        options = SolverOptions() if options is None else copy(options)
        options.max_answer_sets = 1
        with self.solve(*input_arguments, solver=solver, options=options, cache=False) as results:
            try:
                return next(iter(results))
            except StopIteration:
                return None


class StreamAccumulator(FactAccumulator):
    def __init__(self, output_stream: IO[str]) -> None:
        if not output_stream.writable:
            raise ValueError('output_stream must be writable')
        self._stream = output_stream

    def arg_str(self, arg: Any) -> str:
        '''Convert the given argument to a string suitable to be passed to the ASP solver.'''
        if isinstance(arg, numbers.Integral):
            # Output integers without quotes (so we can use them for arithmetic in ASP)
            return str(arg)
        else:
            # Everything else is converted to a string and quoted unconditionally
            return asp.quote(arg)

    def add_fact(self, predicate: str, args: Sequence[Any]) -> None:
        '''Writes a fact to the output stream, in the usual ASP syntax: predicate(arg1, arg2, arg3).'''
        assert len(predicate) > 0
        self._stream.write(predicate)
        self._stream.write('(')
        for (idx, arg) in enumerate(args):
            if idx > 0:
                self._stream.write(',')
            self._stream.write(self.arg_str(arg))
        self._stream.write(').\n')
        if log.isEnabledFor(logging.DEBUG):  # type: ignore
            fact = predicate + '(' + ', '.join(self.arg_str(x) for x in args) + ')'
            log.debug('StreamAccumulator: Adding fact for predicate %r with args %r:\t=> %s', predicate, args, fact)


class Results(Iterable['Result']):
    '''The collection of results of a Solver invocation, corresponding to the set of all answer sets.'''
    # TODO: Describe implicit access to mapped objects through __getattr__ (e.g. .all_graph iterates over answer sets, returning the "graph" object for every answer set)
    # TODO: Should support async/await

    def __init__(self, answer_sets: ClosableIterable[asp.RawAnswerSet], output_spec: OutputSpec, registry: Registry, cache: bool) -> None:
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
        assert self.results is not None, 'Pass cache=True if you need to iterate over results multiple times.'
        rs = self.results
        if type(self.results) != CachingIterable:
            self.results = None
        yield from rs

    def __bool__(self) -> bool:
        # TODO: Handle case when cache=False
        # if not self.cache:
        #     raise NotImplementedError('Because cache=False, only (one) iteration is supported.')
        try:
            next(iter(self))
            return True
        except StopIteration:
            return False

    def __getattr__(self, name: str) -> Any:
        prefix = 'each_'
        if name.startswith(prefix):
            return ResultsAttributeIterator(self, name[len(prefix):])
        else:
            raise AttributeError("No attribute with name {0!r}. Prefix an output variable name with '{1!s}' when iterating over its values for all answer sets.".format(name, prefix))

    def close(self) -> None:
        self.answer_sets.close()

    def __enter__(self) -> 'Results':
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False


class ResultsAttributeIterator(Iterable[Any]):
    '''Helper class to iterate over the values of the output variable with the given name for all answer sets.'''
    # This class is required to support explicit cleanup with 'all_' shortcuts when accessing the output data.

    def __init__(self, results: Results, name: str) -> None:
        self.results = results
        self.name = name

    def __iter__(self) -> Iterator[Any]:
        return iter(getattr(r, self.name) for r in self.results)

    def close(self) -> None:
        self.results.close()

    def __enter__(self) -> 'ResultsAttributeIterator':
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False


class Result:
    '''Represents a single answer set.'''

    def __init__(self, answer_set: asp.RawAnswerSet, output_spec: OutputSpec, registry: Registry) -> None:
        self.answer_set = answer_set
        self._r = output_spec.prepare_mapping(answer_set, registry)

    def get(self, name: str) -> Any:
        return self._r.get_object(name)

    def __getattr__(self, name: str) -> Any:
        try:
            return self.get(name)
        except UndefinedNameError as e:
            raise AttributeError(e)
