from .abc import Solver, SolverOptions
from .dlvhex2 import Dlvhex2Solver

__all__ = [
    'DefaultSolver',
    'Dlvhex2Solver',
    'Solver',
    'SolverOptions',
]


def DefaultSolver() -> Solver:
    """Returns an instance of the default solver."""
    # TODO: Once we support multiple solvers, we should set the default solver depending on what's installed
    return Dlvhex2Solver()
