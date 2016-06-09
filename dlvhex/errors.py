__all__ = [
    'UndefinedVariableError',
    'RedefinedVariableError',
]


class UndefinedVariableError(ValueError):
    '''Raised when a variable name is referenced that is not bound at that location.'''


class RedefinedVariableError(ValueError):
    '''Raised when a variable name is declared when it has already been declared in the surrounding scope.'''
