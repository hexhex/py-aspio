from .solver import Solver
from .dlvhex2 import Dlvhex2Solver

__all__ = [
    'DefaultSolver',
    'Dlvhex2Solver',
    'Solver',
]

DefaultSolver = Dlvhex2Solver  # type: Callable[..., Solver]
