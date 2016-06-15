__all__ = [
    'CircularReferenceError',
    'DuplicateKeyError',
    'InvalidIndicesError',
    'RedefinedNameError',
    'UndefinedNameError',
]


class CircularReferenceError(ValueError):
    '''Raised when a circular reference is detected in an output specification.'''


class DuplicateKeyError(ValueError):
    '''Raised when duplicate keys appear while mapping a predicate to a dictionary.'''


class InvalidIndicesError(ValueError):
    '''Raised when the indices do not form a valid range of integers (i.e., there a duplicates or missing indices) while mapping a predicate to a list.'''


class RedefinedNameError(ValueError):
    '''Raised when a name is declared when it has already been declared in the surrounding scope.'''


class UndefinedNameError(ValueError):
    '''Raised when a name is referenced that is not bound at that location.'''
