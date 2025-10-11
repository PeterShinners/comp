"""Function system for the engine.

Simple function infrastructure to support pipeline operations.
Starts with Python-implemented functions, will add Comp-defined functions later.
"""

__all__ = ["Function", "PythonFunction"]

import comp.engine as comp
from . import _value


class Function:
    """Base class for callable functions in the engine.

    Functions in Comp are invoked through pipelines and receive:
    - input: The value flowing through the pipeline ($in)
    - args: Optional argument structure (^{...})

    Functions evaluate and return Value objects.
    """

    def __init__(self, name: str):
        """Create a function.

        Args:
            name: Function name (without | prefix)
        """
        self.name = name

    def __call__(self, frame, input_value: _value.Value, args: _value.Value | None = None):
        """Invoke the function.

        Args:
            frame: The evaluation frame
            input_value: Value from pipeline ($in)
            args: Optional argument structure

        Returns:
            Value result or fail value
        """
        raise NotImplementedError(f"Function {self.name} must implement __call__")

    def __repr__(self):
        return f"Function(|{self.name})"


class PythonFunction(Function):
    """Function implemented in Python.

    Wraps a Python callable to make it available in Comp pipelines.
    The callable receives (engine, input_value, args) and returns Value.
    """

    def __init__(self, name: str, python_func):
        """Create a Python-implemented function.

        Args:
            name: Function name (without | prefix)
            python_func: Callable(frame, input_value, args) -> Value
        """
        super().__init__(name)
        self.python_func = python_func

    def __call__(self, frame, input_value: _value.Value, args: _value.Value | None = None):
        """Invoke the Python function."""
        try:
            return self.python_func(frame, input_value, args)
        except Exception as e:
            return comp.fail(f"Error in function |{self.name}: {e}")

    def __repr__(self):
        return f"PythonFunction(|{self.name})"


# ============================================================================
# Built-in Functions
# ============================================================================

def builtin_double(frame, input_value: _value.Value, args: _value.Value | None = None):
    """Double a number: [5 |double] → 10"""
    input_value = input_value.as_scalar()
    if not input_value.is_number:
        return comp.fail(f"|double expects number, got {input_value.data}")
    return _value.Value(input_value.data * 2)


def builtin_print(frame, input_value: _value.Value, args: _value.Value | None = None):
    """Print a value and pass it through: [5 |print] → 5 (with side effect)"""
    # Print the value
    print(f"[PRINT] {input_value.data}")
    # Pass through unchanged
    return input_value


def builtin_identity(frame, input_value: _value.Value, args: _value.Value | None = None):
    """Identity function - returns input unchanged: [5 |identity] → 5"""
    return input_value


def builtin_add(frame, input_value: _value.Value, args: _value.Value | None = None):
    """Add argument to input: [5 |add ^{n=3}] → 8"""
    input_value = input_value.as_scalar()
    if not input_value.is_number:
        return comp.fail(f"|add expects number input, got {input_value.data}")

    if args is None or not args.is_struct:
        return comp.fail("|add requires argument ^{n=...}")

    n_key = _value.Value("n")
    if n_key not in args.struct:
        return comp.fail("|add requires argument ^{n=...}")

    n_value = args.struct[n_key]
    if not n_value.is_number:
        return comp.fail(f"|add argument n must be number, got {n_value.data}")

    return _value.Value(input_value.data + n_value.data)


def builtin_wrap(frame, input_value: _value.Value, args: _value.Value | None = None):
    """Wrap input in a struct with given key: [5 |wrap ^{key="x"}] → {x: 5}"""
    if args is None or not args.is_struct:
        return comp.fail("|wrap requires argument ^{key=...}")

    key_key = _value.Value("key")
    if key_key not in args.struct:
        return comp.fail("|wrap requires argument ^{key=...}")

    key_value = args.struct[key_key]
    return _value.Value({key_value: input_value})


# ============================================================================
# Function Registry
# ============================================================================

def create_builtin_functions():
    """Create all built-in Python functions.

    Returns:
        Dict mapping function names to Function objects
    """
    return {
        "double": PythonFunction("double", builtin_double),
        "print": PythonFunction("print", builtin_print),
        "identity": PythonFunction("identity", builtin_identity),
        "add": PythonFunction("add", builtin_add),
        "wrap": PythonFunction("wrap", builtin_wrap),
    }
