from abc import ABC, abstractmethod
from copy import copy
from typing import Callable, IO, Iterable, Optional, Sequence  # noqa
from ..helper.typing import ClosableIterable
from .. import asp

__all__ = [
    'Solver',
    'SolverOptions',
]


class SolverOptions:
    def __init__(self, *,
                 max_answer_sets: Optional[int] = None,
                 max_int: Optional[int] = None,
                 capture: Optional[Iterable[str]] = None,
                 custom: Optional[Sequence[str]] = None) -> None:
        self.max_answer_sets = max_answer_sets
        '''Instruct the solver to compute at most `max_answer_sets` answer sets. Compute all answer sets if `None`.'''
        self.max_int = max_int
        '''Set maximum integer value.'''
        self.capture = capture
        '''Capture additional predicates if they are to be examined manually.'''
        # TODO: Provide some "sentinel" value for the capture options that just means "capture everything"
        self.custom = custom
        '''Custom solver options, passed to the solver as-is'''
        # TODO: Add a "timeout" option? => creates a watchdog thread that just kills the solver after the time elapses (prompting a SolverTimeoutExpired exception or something like that.)

    def __copy__(self) -> 'SolverOptions':
        return SolverOptions(
            max_answer_sets=self.max_answer_sets,
            max_int=self.max_int,
            capture=copy(self.capture),
            custom=copy(self.custom))


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
