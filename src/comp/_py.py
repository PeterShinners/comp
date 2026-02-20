"""Python interop internal module for Comp.

Provides functions for working with Python objects from Comp code:
- lookup: Get a Python object by qualified name (e.g. "sys.version")
- call: Call a Python callable with positional/keyword args
- load: Convert a @py wrapped object back to a Comp value
- dump: Convert a Comp value into a @py wrapped object
- vars: Get attributes of a @py wrapped object as a Comp struct
- getattr: Get a single attribute from a @py wrapped object

Python objects are stored inside HandleInstance.private_data wrapped in
a _PythonObjectWrapper to prevent the Value constructor from auto-converting
things like named tuples into Comp structs.

Usage from Comp:
    !import /py = "py"
    /py.lookup :"math.pi"          -- returns @py handle
    /py.load $handle                -- extracts value as Comp number/text/struct
    /py.call :"math.sqrt" 16       -- calls function, returns result
"""

__all__ = []

import decimal
import pydoc

import comp


class _PythonObjectWrapper:
    """Hold a Python object without Value constructor conversion.

    The Value constructor auto-converts Python dicts, lists, named tuples,
    etc. This wrapper prevents that by being an opaque type that Value
    stores as-is.
    """

    __slots__ = ("obj",)

    def __init__(self, obj):
        self.obj = obj

    def __repr__(self):
        return f"<py:{type(self.obj).__name__}>"


def _wrap_py_object(obj, py_tag, module):
    """Wrap a Python object in a @py handle.

    Args:
        obj: Python object to wrap
        py_tag: (Tag) The @py tag from the internal module
        module: (InternalModule) The py module (for ownership)

    Returns:
        (Value) A Value containing a HandleInstance with the object
    """
    wrapper = _PythonObjectWrapper(obj)
    handle = comp.HandleInstance(
        tag=py_tag,
        module_id=module.token,
        private_data=comp.Value(wrapper),
    )
    return comp.Value(handle)


def _unwrap_py_object(handle_val):
    """Extract the Python object from a @py handle Value.

    Args:
        handle_val: (Value) Value whose data is a HandleInstance

    Returns:
        The unwrapped Python object

    Raises:
        comp.CodeError: If the value is not a valid @py handle
    """
    inst = handle_val.data
    if not isinstance(inst, comp.HandleInstance):
        raise comp.CodeError(
            f"Expected @py handle, got {handle_val.format()}"
        )
    if inst.released:
        raise comp.CodeError("Cannot use released @py handle")
    if inst.private_data is None:
        raise comp.CodeError("@py handle has no data")
    wrapper = inst.private_data.data
    if not isinstance(wrapper, _PythonObjectWrapper):
        raise comp.CodeError(
            f"@py handle contains unexpected data: {type(wrapper).__name__}"
        )
    return wrapper.obj


# ---------------------------------------------------------------------------
# Conversion helpers
# ---------------------------------------------------------------------------

def _comp_to_python(value):
    """Recursively convert a Comp Value to a Python object.

    Args:
        value: (Value) Comp value to convert

    Returns:
        Python object (dict, list, int, float, str, bool, None)

    Raises:
        ValueError: If value contains unconvertible types (handles, blocks)
    """
    data = value.data

    # Tag values
    if isinstance(data, comp.Tag):
        qn = data.qualified
        if qn == "bool.true":
            return True
        if qn == "bool.false":
            return False
        if qn == "nil":
            return None
        return qn

    # Numbers
    if isinstance(data, (decimal.Decimal, int, float)):
        return data

    # Strings
    if isinstance(data, str):
        return data

    # Structs (dicts)
    if isinstance(data, dict):
        all_unnamed = (
            len(data) > 0 and
            all(isinstance(k, comp.Unnamed) for k in data)
        )
        if all_unnamed:
            return [_comp_to_python(v) for v in data.values()]
        result = {}
        unnamed_idx = 0
        for k, v in data.items():
            if isinstance(k, comp.Unnamed):
                py_key = unnamed_idx
                unnamed_idx += 1
            elif isinstance(k, comp.Value):
                py_key = _comp_to_python(k)
            else:
                py_key = str(k)
            result[py_key] = _comp_to_python(v)
        return result

    if isinstance(data, comp.HandleInstance):
        raise ValueError("Cannot convert handle to Python object")
    if isinstance(data, (comp.Block, comp.InternalCallable)):
        raise ValueError("Cannot convert block to Python object")

    return data


def _python_to_comp(obj):
    """Recursively convert a Python object to a Comp Value.

    Args:
        obj: Python object to convert

    Returns:
        (Value) Comp value
    """
    if isinstance(obj, comp.Value):
        return obj
    if obj is None:
        return comp.Value(comp.tag_nil)
    if isinstance(obj, bool):
        return comp.Value(comp.tag_true if obj else comp.tag_false)
    if isinstance(obj, int):
        return comp.Value.from_python(obj)
    if isinstance(obj, float):
        return comp.Value.from_python(obj)
    if isinstance(obj, decimal.Decimal):
        return comp.Value(obj)
    if isinstance(obj, str):
        return comp.Value(obj)
    if isinstance(obj, dict):
        d = {}
        for k, v in obj.items():
            d[comp.Value.from_python(k)] = _python_to_comp(v)
        return comp.Value(d)
    if isinstance(obj, (list, tuple)):
        d = {}
        for v in obj:
            d[comp.Unnamed()] = _python_to_comp(v)
        return comp.Value(d)
    # Fallback: convert to string representation
    return comp.Value(str(obj))


def _extract_call_args(args_value):
    """Convert a Comp args Value into Python positional and keyword args.

    Unnamed struct fields become positional args (in order).
    Named struct fields become keyword args.
    A non-struct value is treated as a single positional arg.

    Args:
        args_value: (Value or None) Comp args

    Returns:
        (list, dict) positional args and keyword args
    """
    pos = []
    kwargs = {}
    if args_value is None:
        return pos, kwargs

    if not isinstance(args_value.data, dict):
        return [_comp_to_python(args_value)], {}

    for k, v in args_value.data.items():
        py_val = _comp_to_python(v)
        if isinstance(k, comp.Unnamed):
            pos.append(py_val)
        elif isinstance(k, comp.Value) and isinstance(k.data, str):
            kwargs[k.data] = py_val
        else:
            pos.append(py_val)
    return pos, kwargs


def _smart_return(result, py_tag, module):
    """Return simple Python values as Comp values, complex ones as @py handles.

    Args:
        result: Python object returned from a call
        py_tag: (Tag) The @py tag
        module: (InternalModule) The py module

    Returns:
        (Value) Either a direct Comp value or a @py handle
    """
    if result is None or isinstance(result, (bool, int, float, str)):
        return _python_to_comp(result)
    if isinstance(result, (list, dict)):
        return _python_to_comp(result)
    # Complex object — wrap as handle
    return _wrap_py_object(result, py_tag, module)


# ---------------------------------------------------------------------------
# Builtin callable implementations
# ---------------------------------------------------------------------------

# These closures capture py_tag and module via the factory in create_py_module.


def _make_lookup(py_tag, module):
    """Create the lookup callable."""

    def _lookup(input_val, args_val, frame):
        """Look up a Python object by qualified name.

        Args:
            input_val: (Value) Unused (pipeline input)
            args_val: (Value) First positional arg is the dotted name string

        Returns:
            (Value) @py handle wrapping the located object
        """
        name_val = args_val.positional(0)
        if name_val is None or not isinstance(name_val.data, str):
            raise comp.CodeError("lookup requires a string name argument")
        name = name_val.data

        obj = pydoc.locate(name)
        if obj is None:
            raise comp.CodeError(f"Could not locate Python name: {name!r}")

        return _wrap_py_object(obj, py_tag, module)

    return _lookup


def _make_call(py_tag, module):
    """Create the call callable."""

    def _call(input_val, args_val, frame):
        """Call a Python callable by qualified name.

        First positional arg is the dotted name of the callable.
        Remaining args (from input) become call arguments.

        Example:
            42 | /py.call :"math.sqrt"
            {1 2} | /py.call :"math.pow"
        """
        name_val = args_val.positional(0)
        if name_val is None or not isinstance(name_val.data, str):
            raise comp.CodeError("call requires a string function name argument")
        name = name_val.data

        func_obj = pydoc.locate(name)
        if func_obj is None:
            raise comp.CodeError(f"Could not locate Python callable: {name!r}")

        pos, kwargs = _extract_call_args(input_val)
        # Convert Decimal args to int/float for Python interop
        pos = [int(a) if isinstance(a, decimal.Decimal) and a == int(a) else a for a in pos]
        try:
            result = func_obj(*pos, **kwargs)
        except Exception as e:
            raise comp.CodeError(
                f"Python call {name}() failed: {type(e).__name__}: {e}"
            )

        return _smart_return(result, py_tag, module)

    return _call


def _make_method(py_tag, module):
    """Create the method callable (call a method on a @py handle)."""

    def _method(input_val, args_val, frame):
        """Call a method on a Python object stored in a @py handle.

        The piped input is the @py handle. First arg is the method name string.
        Remaining positional args are forwarded to the method.

        Example:
            $handle | /py.method :"keys"
            $handle | /py.method :"get" "default_key"
        """
        obj = _unwrap_py_object(input_val)

        # Unwrap args — binding may double-wrap the struct
        # positional(0) gets the inner struct, positional(0) again gets method name
        inner = args_val.positional(0)
        if inner is not None and isinstance(inner.data, dict):
            # Double-wrapped: args_val = {inner_struct}, inner = {"join" ...}
            method_name_val = inner.positional(0)
            args_struct = inner
        else:
            # Single-wrapped: args_val = {"method_name" ...}
            method_name_val = inner
            args_struct = args_val

        if method_name_val is None or not isinstance(method_name_val.data, str):
            raise comp.CodeError("method requires a string method name argument")
        method_name = method_name_val.data

        func = getattr(obj, method_name, None)
        if func is None:
            raise comp.CodeError(
                f"Python object {type(obj).__name__!r} has no attribute {method_name!r}"
            )

        # Remaining positional args (skip the method name at index 0)
        pos = []
        kwargs = {}
        if isinstance(args_struct.data, dict):
            for i, (k, v) in enumerate(args_struct.data.items()):
                if i == 0:
                    continue  # skip method name
                py_val = _comp_to_python(v)
                if isinstance(k, comp.Unnamed):
                    pos.append(py_val)
                elif isinstance(k, comp.Value) and isinstance(k.data, str):
                    kwargs[k.data] = py_val

        pos = [int(a) if isinstance(a, decimal.Decimal) and a == int(a) else a for a in pos]

        try:
            result = func(*pos, **kwargs)
        except Exception as e:
            raise comp.CodeError(
                f"Python method {type(obj).__name__}.{method_name}() failed: "
                f"{type(e).__name__}: {e}"
            )

        return _smart_return(result, py_tag, module)

    return _method


def _make_load(py_tag, module):
    """Create the load callable (extract Python → Comp)."""

    def _load(input_val, args_val, frame):
        """Convert a @py handle's Python object to a Comp value.

        Simple types (int, float, str, bool, None, list, dict) are
        converted recursively. Complex objects raise an error.
        """
        obj = _unwrap_py_object(input_val)
        return _python_to_comp(obj)

    return _load


def _make_dump(py_tag, module):
    """Create the dump callable (Comp → Python, wrapped in @py)."""

    def _dump(input_val, args_val, frame):
        """Convert a Comp value to a Python object and wrap in @py handle."""
        py_obj = _comp_to_python(input_val)
        return _wrap_py_object(py_obj, py_tag, module)

    return _dump


def _make_vars(py_tag, module):
    """Create the vars callable."""

    def _vars(input_val, args_val, frame):
        """Return attributes of a @py object as a Comp struct.

        Tries vars(obj), falls back to __dict__, then non-callable dir() attrs.
        """
        obj = _unwrap_py_object(input_val)

        data = None
        try:
            data = vars(obj)
        except TypeError:
            pass
        if data is None:
            d = getattr(obj, "__dict__", None)
            if isinstance(d, dict):
                data = dict(d)
            else:
                data = {}
                for name in dir(obj):
                    if name.startswith("__") and name.endswith("__"):
                        continue
                    try:
                        val = getattr(obj, name)
                    except Exception:
                        continue
                    if callable(val):
                        continue
                    data[name] = val

        return _python_to_comp(data)

    return _vars


def _make_getattr_fn(py_tag, module):
    """Create the getattr callable."""

    def _getattr(input_val, args_val, frame):
        """Get a single attribute from a @py object.

        The piped input is the @py handle. First arg is the attribute name.

        Example:
            $handle | /py.getattr :"__class__"
        """
        obj = _unwrap_py_object(input_val)

        attr_name_val = args_val.positional(0)
        if attr_name_val is None or not isinstance(attr_name_val.data, str):
            raise comp.CodeError("getattr requires a string attribute name")
        attr_name = attr_name_val.data

        try:
            result = getattr(obj, attr_name)
        except AttributeError:
            raise comp.CodeError(
                f"Python object {type(obj).__name__!r} has no attribute {attr_name!r}"
            )

        return _smart_return(result, py_tag, module)

    return _getattr


def _make_drop(py_tag, module):
    """Create the drop callable (release a @py handle)."""

    def _drop(input_val, args_val, frame):
        """Release a @py handle. Called on !drop.

        Python's GC handles actual cleanup; this just marks the handle
        as released so further use is prevented.
        """
        inst = input_val.data
        if isinstance(inst, comp.HandleInstance) and not inst.released:
            inst.released = True
        return comp.Value(comp.tag_nil)

    return _drop


def _make_typeof(py_tag, module):
    """Create the typeof callable."""

    def _typeof(input_val, args_val, frame):
        """Return the Python type name of a @py object as a string.

        Example:
            $handle | /py.typeof   -- returns "ParseResult" or "module" etc.
        """
        obj = _unwrap_py_object(input_val)
        t = type(obj)
        mod = getattr(t, "__module__", "")
        qn = getattr(t, "__qualname__", getattr(t, "__name__", str(t)))
        full = f"{mod}.{qn}" if mod else qn
        return comp.Value(full)

    return _typeof


# ---------------------------------------------------------------------------
# Module registration
# ---------------------------------------------------------------------------

@comp._internal.register_internal_module("py")
def _create_py_module(module):
    """Python interop: lookup, call, method, pull, push, vars, getattr, typeof."""

    # The @py tag — used to identify handle instances
    py_tag = module.add_tag("py")

    # Core functions
    module.add_callable("lookup", _make_lookup(py_tag, module))
    module.add_callable("call", _make_call(py_tag, module))
    module.add_callable("method", _make_method(py_tag, module))

    # Value conversion
    module.add_callable("load", _make_load(py_tag, module))
    module.add_callable("dump", _make_dump(py_tag, module))

    # Introspection
    module.add_callable("vars", _make_vars(py_tag, module))
    module.add_callable("getattr", _make_getattr_fn(py_tag, module))
    module.add_callable("typeof", _make_typeof(py_tag, module))

    # Handle lifecycle
    module.add_callable("drop", _make_drop(py_tag, module))
