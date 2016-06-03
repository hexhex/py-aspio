from .input import UndefinedVariableError, RedefinedVariableError
from .program import Program
from .solver import Solver, SolverError

debug = False  # type: bool

__all__ = [
    'Program',
    'RedefinedVariableError',
    'Solver',
    'SolverError',
    'UndefinedVariableError',
]
