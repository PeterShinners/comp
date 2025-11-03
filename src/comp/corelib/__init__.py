"""Standard library modules for Comp.

Python-implemented modules that can be imported into Comp code.
These modules provide functionality beyond the builtin module.

Available modules:
- string: String manipulation functions
"""

__all__ = ["get_stdlib_module", "list_stdlib_modules"]

from collections.abc import Callable

_modules: dict[str, any] = {}
_registry: dict[str, Callable] = {}


def get_stdlib_module(name: str):
    """Get a standard library module by name.

    Args:
        name: Module name (e.g., "str")

    Returns:
        Module instance, or None if not found

    Example:
        string_mod = get_stdlib_module("string")
    """

    mod = _modules.get(name)
    if mod:
        return mod
    
    init = _lib().get(name)
    if not init:
        return None
    
    mod = init()
    _modules[name] = mod
    # Note: Don't call prepare() - stdlib modules are created directly in Python,
    # not from AST, so they don't need preparation
    return mod


def list_stdlib_modules() -> list[str]:
    """Get list of available stdlib module names.

    Returns:
        List of module names
    """
    return list(_lib())


def _lib():
    """registry of standard libraries."""
    global _registry
    if not _registry:
        from . import num, str, python, tag
        _registry.update(
            str=str.create_module,
            num=num.create_module,
            python=python.create_module,
            tag=tag.create_module,
        )
    return _registry
