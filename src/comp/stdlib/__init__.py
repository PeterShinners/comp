"""Standard library modules for Comp.

Python-implemented modules that can be imported into Comp code.
These modules provide functionality beyond the builtin module.

Available modules:
- string: String manipulation functions
"""

__all__ = ["get_stdlib_module", "list_stdlib_modules"]

from ._string import create_string_module


# Registry of available stdlib modules
_STDLIB_MODULES = {
    "string": create_string_module,
}

# Cache for created modules
_module_cache: dict[str, any] = {}


def get_stdlib_module(name: str):
    """Get a standard library module by name.

    Args:
        name: Module name (e.g., "string")

    Returns:
        Module instance, or None if not found

    Example:
        string_mod = get_stdlib_module("string")
    """
    if name not in _STDLIB_MODULES:
        return None

    # Return cached module if available
    if name in _module_cache:
        return _module_cache[name]

    # Create and cache the module
    creator_func = _STDLIB_MODULES[name]
    module = creator_func()
    _module_cache[name] = module

    return module


def list_stdlib_modules() -> list[str]:
    """Get list of available stdlib module names.

    Returns:
        List of module names
    """
    return list(_STDLIB_MODULES.keys())
