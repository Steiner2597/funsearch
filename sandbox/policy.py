"""
Sandbox policy definitions and import/builtin guards.
"""

from __future__ import annotations

import builtins
from collections.abc import Callable, Iterable, Sequence
from types import ModuleType
from typing import cast

BLOCKED_MODULES = [
    "os",
    "sys",
    "subprocess",
    "socket",
    "urllib",
    "requests",
    "http",
    "ctypes",
    "importlib",
    "__import__",
    "eval",
    "exec",
    "compile",
    "open",
    "file",
    "input",
    "raw_input",
]

ALLOWED_MODULES = [
    "math",
    "random",
    "itertools",
    "functools",
    "collections",
    "typing",
    "dataclasses",
]


def _normalize_modules(modules: Iterable[str] | None) -> set[str]:
    return {name for name in (modules or [])}


def build_import_guard(
    allowed_modules: Iterable[str] | None = None,
    blocked_modules: Iterable[str] | None = None,
) -> Callable[[str, dict[str, object] | None, dict[str, object] | None, Sequence[str], int], ModuleType]:
    """
    Build a restricted __import__ hook that only allows allowlisted modules
    and explicitly blocks denied modules.
    """
    allowed = _normalize_modules(allowed_modules or ALLOWED_MODULES)
    blocked = _normalize_modules(blocked_modules or BLOCKED_MODULES)
    original_import: Callable[
        [str, dict[str, object] | None, dict[str, object] | None, Sequence[str], int],
        ModuleType,
    ] = cast(
        Callable[[str, dict[str, object] | None, dict[str, object] | None, Sequence[str], int], ModuleType],
        builtins.__import__,
    )

    def guarded_import(
        name: str,
        globals: dict[str, object] | None = None,
        locals: dict[str, object] | None = None,
        fromlist: Sequence[str] = (),
        level: int = 0,
    ) -> ModuleType:
        root = name.split(".")[0]
        if root in blocked or name in blocked:
            raise ImportError(f"Import of '{root}' blocked by sandbox policy")
        if root not in allowed:
            raise ImportError(f"Import of '{root}' is not allowlisted")
        return original_import(name, globals, locals, fromlist, level)

    return guarded_import


def install_import_guard(
    allowed_modules: Iterable[str] | None = None,
    blocked_modules: Iterable[str] | None = None,
) -> Callable[[str, dict[str, object] | None, dict[str, object] | None, Sequence[str], int], ModuleType]:
    """Install a restricted __import__ hook into builtins."""
    guard = build_import_guard(allowed_modules=allowed_modules, blocked_modules=blocked_modules)
    builtins.__import__ = guard
    return guard


def disable_blocked_builtins(blocked_names: Iterable[str] | None = None) -> None:
    """Disable dangerous builtins like open/eval/exec/compile/input."""
    blocked = _normalize_modules(blocked_names or BLOCKED_MODULES)
    blocked.discard("__import__")

    def _blocked(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("Blocked by sandbox policy")

    for name in blocked:
        if hasattr(builtins, name):
            setattr(builtins, name, _blocked)
