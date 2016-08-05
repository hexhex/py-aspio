import importlib
import logging
from copy import copy
from types import ModuleType
from typing import Any, Callable, Iterable, Mapping, MutableMapping, Optional, Union  # noqa

__all__ = [
    'Constructor',
    'global_registry',
    'import_from_module',
    'register',
    'register_dict',
    'Registry',
]

log = logging.getLogger(__name__)

Constructor = Callable[..., object]


class Registry:
    def __init__(self) -> None:
        self._registered_names = {
            'int': int  # 'int' constructor must be available as per the language specification
        }  # type: MutableMapping[str, Constructor]

    def __copy__(self) -> 'Registry':
        other = Registry()
        other._registered_names = copy(self._registered_names)
        return other

    def register(self, name: str, constructor: Constructor, *, replace: bool = False) -> None:
        '''Register the given constructor with the given name.

        Raises a `ValueError` when trying to re-register a name with a different constructor (unless `replace` is `True`).
        Raises a `ValueError` when the constructor argument is not callable.
        '''
        if not replace and name in self._registered_names:
            if self._registered_names[name] is constructor:
                # If we try to register the same object again, there is no problem.
                # This might happen in practice when calling `register_dict` with `globals()`, since all the imported names are registered too.
                return
            raise ValueError('Name {0!r} is already registered. Pass replace=True to re-register.'.format(name))
        if not callable(constructor):
            raise ValueError('The constructor argument must be callable.')
        log.debug('Registry: registering name %r with constructor %r', name, constructor)
        self._registered_names[name] = constructor

    def register_dict(self, name_dict: Mapping[str, Any]) -> None:
        '''Import names from the given dict.

        Skips entries where the associated constructor is not callable.
        Skips entries with a 'special attribute'-like name (i.e., starting and ending with double underscores).
        Can be used to easily add all definitions of the current module when called as `register_dict(globals())`.
        '''
        for name, obj in name_dict.items():
            # Note: In practice, objects bound to these "special" names aren't callable anyways...
            # But the names are the same in every module, so we want to prevent conflicts in case one of them *does* become callable in a future version.
            if name.startswith('__') and name.endswith('__'):
                continue
            if callable(obj):
                self.register(name, obj)

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
        '''Return the constructor registered to `name`, or `None` if the name is not registered.'''
        return self._registered_names.get(name)


global_registry = Registry()

register = global_registry.register
register_dict = global_registry.register_dict
import_from_module = global_registry.import_from_module
