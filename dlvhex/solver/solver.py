from abc import ABC, abstractmethod
from typing import Callable, IO, Iterable
from ..helper.typing import ClosableIterable
from .. import asp

__all__ = [
    'Solver',
]


class SolverOptions:
    # TODO: Abstract some common options over different solvers
    # maxint, evtl. maxmodels
    # but also provide a field for custom options, could be e.g. a List[str]
    # also incorporate the "capture" option here?
    def __init__(self) -> None:
        self.maxmodels = None  # type: int TODO rename
        self.maxint = None  # type: int
        self.custom = None  # type: List[str]
        # TODO: Add a "timeout" options? => creates a watchdog thread that just kills the solver after the time elapses (prompting a SolverTimeoutExpired exception or something like that.)
        pass

    def __copy__(self) -> 'SolverOptions':
        pass


class Solver(ABC):
    '''Abstract solver interface.'''

    @abstractmethod
    def run(self, *,
            write_input: Callable[[IO[str]], None],
            capture_predicates: Iterable[str],
            file_args: Iterable[str],
            options: SolverOptions = None) -> ClosableIterable[asp.RawAnswerSet]:
        pass

    @abstractmethod
    def __copy__(self) -> 'Solver':
        pass
