import importlib
from copy import copy
from types import ModuleType
from typing import Any, Callable, Iterable, Tuple, Optional, Union, Mapping, MutableMapping

__all__ = ['register', 'import_from_module']


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
        if isinstance(module_or_module_name, ModuleType):
            module = module_or_module_name
        else:
            module = importlib.import_module(module_or_module_name, package=package)
        for name in names:
            self.register(name, getattr(module, name))

    def get(self, name: str) -> Constructor:
        return self._registered_names.get(name)


def LocalRegistry() -> Registry:
    return copy(_global_registry)


_global_registry = Registry()

def register(name: str, constructor: Constructor, *, replace: bool = False) -> None:
    _global_registry.register(name, constructor, replace=replace)

def import_from_module(names: Iterable[str], module_or_module_name: Union[ModuleType, str], package: Optional[str] = None) -> None:
    _global_registry.import_from_module(names, module_or_module_name, package)
