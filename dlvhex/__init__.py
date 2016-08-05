import logging
from .errors import CircularReferenceError, InvalidIndicesError, RedefinedNameError, UndefinedNameError
from .input import InputSpec
from .output import OutputSpec
from .program import Program
from .registry import register, register_dict, import_from_module
from .solver import Solver, SolverError

__all__ = [
    'CircularReferenceError',
    'InvalidIndicesError',
    'RedefinedNameError',
    'UndefinedNameError',
    #
    'InputSpec',
    #
    'OutputSpec',
    #
    'Program',
    #
    'register',
    'register_dict',
    'import_from_module',
    #
    'Solver',
    'SolverError',
]

# Set up logging. By default, do not output any log messages from library code.
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())
