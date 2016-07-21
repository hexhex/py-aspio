from copy import copy
from types import ModuleType
from typing import Iterable, Optional, Union
from .solver import Solver, Results, Result
from .input import InputSpec
from .output import OutputSpec
from .parser import parse_embedded_spec
from .registry import Constructor, Registry, global_registry

__all__ = ['Program']


class Program:
    '''Represents an answer set program.'''

    def __init__(self, *, filename: Optional[str] = None, code: Optional[str] = None, use_global_registry=True) -> None:
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

    def append_file(self, filename: str, *, parse_io_spec: bool = True) -> None:
        '''Append ASP code contained in the given file to the program.

        Note that unless the `parse_io_spec` argument is `False`, the file is opened immediately to extract any embedded I/O specifications.
        The file path is passed to the solver that will read the actual ASP code at the time of solving.
        '''
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

    def register(self, name: str, constructor: Constructor, *, replace: bool = False) -> None:
        self.local_registry.register(name, constructor, replace=replace)

    def import_from_module(self, names: Iterable[str], module_or_module_name: Union[ModuleType, str], package: Optional[str] = None) -> None:
        self.local_registry.import_from_module(names, module_or_module_name, package)

    def solve(self, *input_arguments, solver: Optional[Solver] = None, cache: bool = False) -> Results:
        '''Solve the ASP program with the given input arguments and return a collection of answer sets.

        If deterministic cleanup of the solver subprocess is required, call close() on the returned object.
        Alternatively, use the returned object as a context manager in a `with` statement.
        '''
        # TODO: Also allow to pass input arguments as keyword arguments, with names as defined in the input spec
        if solver is None:
            solver = self.solver
        if solver is None:
            solver = Solver()
        return solver.run(self, input_arguments, cache=cache)

    def solve_one(self, *input_arguments, solver: Optional[Solver] = None) -> Optional[Result]:
        '''Solve the ASP program and return one of the computed answer sets, or None if no answer set exists. No special cleanup is necessary.'''
        # TODO: Use additional solver option '--number=1'
        with self.solve(*input_arguments, solver=solver, cache=False) as results:
            try:
                return next(iter(results))
            except StopIteration:
                return None
