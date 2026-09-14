"""Compatibility shim: ``avantis_trader_sdk`` is now ``veranta_sdk``.

Avantis is now Veranta. This package re-exports ``veranta_sdk`` and aliases
every ``avantis_trader_sdk.<module>`` import to ``veranta_sdk.<module>`` so
existing integrations keep working. It is the final release under the old
name; migrate with https://sdk.veranta.xyz/migration/rename.
"""

# ruff: noqa: E402  -- imports must run after the alias finder is installed
from __future__ import annotations

import importlib
import sys
import types
import warnings
from importlib.abc import Loader, MetaPathFinder
from importlib.machinery import ModuleSpec

_OLD = "avantis_trader_sdk"
_NEW = "veranta_sdk"


class _AliasModule(types.ModuleType):
    """A module object that forwards attribute access to its veranta_sdk twin."""

    def __init__(self, name: str, target: types.ModuleType) -> None:
        super().__init__(name, target.__doc__)
        self.__dict__["_target"] = target
        if hasattr(target, "__path__"):
            self.__path__ = []  # marks this alias as a package for submodule imports

    def __getattr__(self, item: str):  # noqa: ANN204
        return getattr(self.__dict__["_target"], item)

    def __dir__(self):  # noqa: ANN204
        return dir(self.__dict__["_target"])


class _AliasFinder(MetaPathFinder, Loader):
    """Resolve ``avantis_trader_sdk.X`` to a proxy of ``veranta_sdk.X``."""

    def find_spec(self, fullname: str, path=None, target=None):  # noqa: ANN001, ANN201
        if not fullname.startswith(_OLD + "."):
            return None
        return ModuleSpec(fullname, self, origin=f"alias of {_NEW}")

    def create_module(self, spec: ModuleSpec) -> types.ModuleType:
        real = importlib.import_module(_NEW + spec.name[len(_OLD) :])
        return _AliasModule(spec.name, real)

    def exec_module(self, module: types.ModuleType) -> None:
        return None


if not any(isinstance(finder, _AliasFinder) for finder in sys.meta_path):
    sys.meta_path.insert(0, _AliasFinder())

warnings.warn(
    "avantis_trader_sdk is now veranta_sdk (Avantis is now Veranta). This package is a "
    "compatibility shim and receives no further updates; switch your imports to "
    "veranta_sdk. See https://sdk.veranta.xyz/migration/rename",
    DeprecationWarning,
    stacklevel=2,
)

from veranta_sdk import *  # noqa: F401, F403, I001
from veranta_sdk import (
    AsyncVeranta,
    Veranta,
    VerantaConfig,
    VerantaError,
    __all__,
    __version__ as __version__,
)

# Pre-rename class names, without a second warning (the import above warned).
AsyncAvantis = AsyncVeranta
Avantis = Veranta
AvantisConfig = VerantaConfig
AvantisError = VerantaError

__all__ = [*__all__, "AsyncAvantis", "Avantis", "AvantisConfig", "AvantisError"]
