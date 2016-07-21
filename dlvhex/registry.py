import importlib
from copy import copy
from types import ModuleType
from typing import Callable, Iterable, MutableMapping, Optional, Union  # noqa

__all__ = [
    'Constructor',
    'global_registry',
    'import_from_module',
    'register',
    'Registry',
]


Constructor = Callable[..., object]


class Registry:
    def __init__(self) -> None:
        self._registered_names = {}  # type: MutableMapping[str, Constructor]

    def __copy__(self) -> 'Registry':
        other = Registry()
        other._registered_names = copy(self._registered_names)
        return other

    def register(self, name: str, constructor: Constructor, *, replace: bool = False) -> None:
        if not replace and name in self._registered_names:
            raise ValueError('Name {0} is already registered. Pass replace=True to re-register.'.format(name))
        if not callable(constructor):
            raise ValueError('constructor argument needs to be callable')
        self._registered_names[name] = constructor

    def import_from_module(self, names: Iterable[str], module_or_module_name: Union[ModuleType, str], package: Optional[str] = None) -> None:
        '''Import names from the given module.

        All objects bound to the given names in the module are registered.
        The state at the time of import is captured,
        i.e. no assignments to the given names after the import_from_module call will be noticed.
        '''
        if isinstance(module_or_module_name, ModuleType):
            module = module_or_module_name
        else:
            module = importlib.import_module(module_or_module_name, package=package)
        for name in names:
            self.register(name, getattr(module, name))

    def get(self, name: str) -> Constructor:
        return self._registered_names.get(name)


global_registry = Registry()

register = global_registry.register
import_from_module = global_registry.import_from_module

# def register(name: str, constructor: Constructor, *, replace: bool = False) -> None:
#     global_registry.register(name, constructor, replace=replace)


# def import_from_module(names: Iterable[str], module_or_module_name: Union[ModuleType, str], package: Optional[str] = None) -> None:
#     global_registry.import_from_module(names, module_or_module_name, package)
