from .input import RedefinedVariableError, UndefinedVariableError
from .program import Program, register, import_from_module
from .solver import Solver, SolverError

debug = False  # type: bool

__all__ = [
    'RedefinedVariableError',
    'UndefinedVariableError',
    #
    'Program',
    'register',
    'import_from_module',
    #
    'Solver',
    'SolverError',
]
