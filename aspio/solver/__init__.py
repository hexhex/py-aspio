from .solver import Solver, SolverOptions
from .dlvhex2 import Dlvhex2Solver

__all__ = [
    'DefaultSolver',
    'Dlvhex2Solver',
    'Solver',
    'SolverOptions',
]

# TODO: Once we support multiple solvers, we should set the default solver depending on what's installed
DefaultSolver = Dlvhex2Solver  # type: Callable[..., Solver]
