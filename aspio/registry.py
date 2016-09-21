import importlib
import logging
from copy import copy
from types import ModuleType
from typing import Any, AbstractSet, Callable, Iterable, Mapping, MutableMapping, Optional, Sequence, Union  # noqa

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
    # Default constructors for collections (global setting)
    tuple_constructor = tuple  # type: Callable[[Iterable[Any]], object]
    set_constructor = frozenset  # type: Callable[[Iterable[Any]], AbstractSet[Any]]
    sequence_constructor = list  # type: Callable[[Iterable[Any]], Sequence[Any]]
    dictionary_constructor = dict  # type: Callable[[Mapping[Any, Any]], Mapping[Any, Any]]

    def __init__(self) -> None:
        self._registered_names = {
            'int': int  # 'int' constructor must be available as per the language specification
        }  # type: MutableMapping[str, Constructor]
        # Default constructors for collections (local setting)
        self.tuple_constructor = type(self).tuple_constructor  # type: ignore  # bug in mypy: https://github.com/python/mypy/issues/708
        self.set_constructor = type(self).set_constructor  # type: ignore
        self.sequence_constructor = type(self).sequence_constructor  # type: ignore
        self.dictionary_constructor = type(self).dictionary_constructor  # type: ignore

    def __copy__(self) -> 'Registry':
        other = Registry()
        other._registered_names = copy(self._registered_names)
        return other

    def register(self, constructor: Constructor, name: str = None, *, replace: bool = False) -> None:
        '''Register the given constructor with the given name.

        If `name` is not given, it defaults to `constructor.__name__` (raising a `ValueError` if this attribute does not exist).

        Raises a `ValueError` when trying to re-register a name with a different constructor (unless `replace` is `True`).
        Raises a `ValueError` when the constructor argument is not callable.
        '''
        if name is None:
            try:
                name = constructor.__name__
            except AttributeError:
                raise ValueError("Constructor {0!r} has no attribute '__name__'. Please provide the name argument manually.".format(constructor))
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
                self.register(obj, name)

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
            self.register(getattr(module, name), name)

    def get(self, name: str) -> Constructor:
        '''Return the constructor registered to `name`, or `None` if the name is not registered.'''
        return self._registered_names.get(name)

    def resolve(self, name: str) -> Constructor:
        '''Resolve the given (possibly qualified) name.

        The name is split into parts separated by dots.
        The leftmost (top level) name is looked up in this registry or, if it is not registered, imported as module.
        '''
        toplevel, *parts = name.split('.')
        obj = self.get(toplevel)  # type: Any
        if obj is None:
            try:
                obj = importlib.import_module(toplevel)
            except ImportError:
                pass
        if obj is None:
            return None
        for part in parts:
            try:
                obj = getattr(obj, part)
            except AttributeError:
                return None
        if callable(obj):
            return obj
        else:
            return None


global_registry = Registry()

register = global_registry.register
register_dict = global_registry.register_dict
import_from_module = global_registry.import_from_module
