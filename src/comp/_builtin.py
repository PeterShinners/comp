"""Builtin module providing core tags, shapes, and functions.

This module contains the fundamental definitions that all other modules
inherit by default:
- Core tags: #true, #false, #fail, #fail.runtime, #fail.type, etc.
- Primitive shapes: ~num, ~str, ~bool, ~any
- Core functions: |print, |double, |identity, |add, |wrap

Every module (except builtin itself) automatically has a namespace reference
to builtin, allowing code to reference these definitions without explicit imports.
"""

__all__ = ["create_builtin_module", "get_builtin_module"]

from . import _function, _module


def create_builtin_module() -> _module.Module:
    """Create and populate the builtin module.

    Returns:
        A Module containing all builtin tags, shapes, and functions
    """
    module = _module.Module(is_builtin=True)

    # ========================================================================
    # Core Tags
    # ========================================================================

    # Boolean tags
    module.define_tag(["true"], value=None)
    module.define_tag(["false"], value=None)

    # Failure tags
    module.define_tag(["fail"], value=None)
    module.define_tag(["fail", "runtime"], value=None)
    module.define_tag(["fail", "type"], value=None)
    module.define_tag(["fail", "div_zero"], value=None)
    module.define_tag(["fail", "not_found"], value=None)
    module.define_tag(["fail", "ambiguous"], value=None)

    # ========================================================================
    # Primitive Shapes
    # ========================================================================

    # Note: These are placeholder definitions. The actual type checking
    # will be done in the morph system based on runtime values.
    # We define them here so they can be referenced in user code.

    module.define_shape(["num"], fields=[])
    module.define_shape(["str"], fields=[])
    module.define_shape(["bool"], fields=[])
    module.define_shape(["any"], fields=[])
    module.define_shape(["tag"], fields=[])

    # ========================================================================
    # Built-in Functions
    # ========================================================================

    # Register Python-backed functions
    builtins = _function.create_builtin_functions()

    for name, py_func in builtins.items():
        # Create a FunctionDefinition with the Python function as body
        module.define_function(
            path=[name],
            body=py_func,  # Store the PythonFunction directly as the body
            is_pure=False,  # I/O functions aren't pure
            doc=py_func.python_func.__doc__ if hasattr(py_func.python_func, '__doc__') else None,
        )

    return module


def get_builtin_module() -> _module.Module:
    """Get the shared builtin module instance.

    Lazily creates the builtin module on first call, then returns
    the same instance for all subsequent calls.

    Returns:
        The singleton builtin module
    """
    global _builtin_module
    if _builtin_module is None:
        _builtin_module = create_builtin_module()
    return _builtin_module


# Singleton instance
_builtin_module: _module.Module | None = None
