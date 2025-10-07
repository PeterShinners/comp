"""Function definition classes."""

__all__ = ["FuncDef", "FuncImpl", "PythonFuncImpl"]

import comp


class FuncDef:
    """Function definition - immutable, belongs to defining module."""
    def __init__(self, identifier):
        """Create a function definition."""
        self.identifier = identifier
        self.name = ".".join(identifier)
        self.implementations = []

    def __repr__(self):
        return f"FuncDef(|{self.name})"


class FuncImpl:
    """Implementation of a function for a specific shape."""

    def __init__(self, ast_node):
        self._ast_node = ast_node
        self.shape = None
        self._resolved = False

    def resolve(self, module):
        """Resolve shape references in module context."""
        if self._resolved:
            return

        if self.shape:
            self.shape.resolve(module)

        self._resolved = True

    def matches(self, value):
        """Check if this implementation matches the value's shape.

        Returns (specificity, quality) tuple. Higher = better match.
        """
        if not self.shape:
            return (0, 1)  # No shape = matches anything (low priority)

        return self.shape.matches(value)

    def __repr__(self):
        shape_str = f" shape={self.shape}" if self.shape else ""
        return f"FuncImpl({shape_str})"


class PythonFuncImpl:
    """Python-implemented function that can be called from Comp code.

    This allows implementing built-in functions in Python that integrate
    seamlessly with Comp's runtime system.
    """

    def __init__(self, python_func, name=None):
        """Create a Python function implementation.

        Args:
            python_func: Python callable that takes (in_value, arg_value) and returns Value
            name: Optional name for debugging/display
        """
        self.python_func = python_func
        self.name = name or (python_func.__name__ if hasattr(python_func, '__name__') else "python_func")
        self.shape = None
        self._resolved = True  # Python funcs don't need resolution

    def resolve(self, module):
        """Resolve shape references in module context."""
        # Python functions are already resolved
        pass

    def matches(self, value):
        """Check if this implementation matches the value's shape.

        Returns (specificity, quality) tuple. Higher = better match.
        """
        if not self.shape:
            return (0, 1)  # No shape = matches anything (low priority)

        return self.shape.matches(value)

    def __repr__(self):
        shape_str = f" shape={self.shape}" if self.shape else ""
        return f"PythonFuncImpl({self.name}{shape_str})"
