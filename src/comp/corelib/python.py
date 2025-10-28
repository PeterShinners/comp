"""Python interop for Comp language.

Provides handles and functions for working with Python objects from Comp code:
- @pyobject handle: Manages Python object references with automatic cleanup
- |py-from-comp: Convert Comp values to Python objects
- |py-to-comp: Convert Python objects back to Comp values

The pyobject handle uses a drop block to automatically decrement Python reference
counts when handles are dropped, preventing memory leaks.
"""

import comp
import decimal
import pydoc
from typing import Any, Dict, List, Tuple


def py_decref(frame, input_value, args=None):
    """Decrement Python reference count for the wrapped object.
    
    This is called automatically by the @pyobject handle's drop-handle function.
    The input should be a handle value containing the Python object directly.
    
    Args:
        frame: Execution frame
        input_value: Comp Value containing Python object directly in data
        args: Optional arguments (not used)
        
    Returns:
        Empty Comp Value on success
    """
    if False:  # Make this a generator
        yield
    
    # In Python, we don't need to manually manage refcounts for objects
    # we're holding references to - Python's GC handles it automatically
    # This function exists as a hook for future manual memory management if needed
    
    return comp.Value({})


def py_from_comp_impl(frame, input_value, args=None):
    """Convert a Comp value to a Python object.
    
    Creates a deep copy of the Comp value as a Python object:
    - Structs → dicts
    - Numbers → int/float
    - Strings → str
    - Tags → str (tag name)
    - Booleans → bool
    - Handles → error (can't convert handles to Python)
    
    Args:
        frame: Execution frame
        input_value: Comp Value to convert
        args: Optional arguments (not used)
        
    Returns:
        Comp Value containing Python object directly
    """
    if False:  # Make this a generator
        yield
    
    try:
        # Convert Comp value to Python object
        input_scalar = input_value.as_scalar()
        py_obj = _comp_to_python(input_scalar)
        
        # Return the Python object directly in the Value
        return comp.Value(py_obj)
    except Exception as e:
        return comp.fail(f"Failed to convert Comp value to Python: {e}")


def py_to_comp_impl(frame, input_value, args=None):
    """Convert a Python object back to a Comp value.
    
    Creates a deep copy of the Python object as a Comp value:
    - dict → Struct
    - list/tuple → Struct with numeric keys
    - int/float → Number
    - str → String
    - bool → Tag (#true or #false)
    - None → empty struct
    
    Args:
        frame: Execution frame
        input_value: Comp Value containing Python object directly in data
        args: Optional arguments (not used)
        
    Returns:
        Comp Value converted from Python object
    """
    if False:  # Make this a generator
        yield
    
    try:
        # Get the Python object directly from Value.data
        py_obj = input_value.data
        # Convert Python object to Comp value
        return _python_to_comp(py_obj)
    except Exception as e:
        return comp.fail(f"Failed to convert Python object to Comp: {e}")


def _comp_to_python(value):
    """Recursively convert Comp Value to Python object.
    
    Args:
        value: Comp Value to convert
        
    Returns:
        Python object (dict, list, int, float, str, bool, None)
        
    Raises:
        ValueError: If value contains unconvertible types
    """
    if value.is_struct:
        # Convert struct to dict
        result = {}
        for key, val in value.struct.items():
            # Handle both Value keys and Unnamed keys
            if isinstance(key, comp.Value):
                py_key = _comp_to_python(key)
            else:
                # Unnamed key - use index
                py_key = key.index if hasattr(key, 'index') else str(key)
            py_val = _comp_to_python(val)
            result[py_key] = py_val
        return result
    
    elif value.is_number:
        # Return Python number
        return value.data
    
    elif value.is_string:
        # Return Python string
        return value.data
    
    elif value.is_tag:
        # Convert tags: #true/#false -> Python bool, others -> full tag name string
        tag_name = value.data.full_name
        if tag_name == "true":
            return True
        if tag_name == "false":
            return False
        return tag_name
    
    elif value.is_bool:
        # Convert to Python bool
        return value.data
    
    elif value.is_handle:
        raise ValueError("Cannot convert handle to Python object")
    
    elif value.is_block or value.is_raw_block:
        raise ValueError("Cannot convert block to Python object")
    
    elif value.is_fail:
        # Convert fail to dict with error info
        fail_dict = {}
        for key, val in value.struct.items():
            # Handle both Value keys and Unnamed keys
            if isinstance(key, comp.Value):
                py_key = _comp_to_python(key)
            else:
                # Unnamed key - use index
                py_key = key.index if hasattr(key, 'index') else str(key)
            py_val = _comp_to_python(val)
            fail_dict[py_key] = py_val
        return fail_dict
    
    else:
        # Default: try to return data as-is
        return value.data


def _python_to_comp(obj):
    """Recursively convert Python object to Comp Value.
    
    Args:
        obj: Python object to convert
        
    Returns:
        Comp Value
    """
    # Pass-through for already-wrapped Comp Values (from prior conversions)
    if isinstance(obj, comp.Value):
        return obj

    if isinstance(obj, dict):
        # Convert dict to Comp struct
        struct_dict = {}
        for key, val in obj.items():
            comp_key = _python_to_comp(key)
            comp_val = _python_to_comp(val)
            struct_dict[comp_key] = comp_val
        return comp.Value(struct_dict)
    
    elif isinstance(obj, (list, tuple)):
        # Convert list/tuple to Comp struct with numeric keys
        struct_dict = {}
        for i, val in enumerate(obj):
            comp_key = comp.Value(i)
            comp_val = _python_to_comp(val)
            struct_dict[comp_key] = comp_val
        return comp.Value(struct_dict)
    
    elif isinstance(obj, bool):
        # Convert bool to tag (#true or #false)
        return comp.Value(comp.builtin.TRUE if obj else comp.builtin.FALSE)
    
    elif isinstance(obj, (int, float)):
        # Convert number to Comp number
        return comp.Value(obj)

    elif isinstance(obj, decimal.Decimal):
        # Preserve Decimal numeric values
        return comp.Value(obj)
    
    elif isinstance(obj, str):
        # Convert string to Comp string
        return comp.Value(obj)
    
    elif obj is None:
        # Convert None to empty struct
        return comp.Value({})
    
    else:
        # For other types, try to convert to string representation
        return comp.Value(str(obj))


def _qualified_type_name(obj: Any) -> str:
    """Return the qualified type name for a python object."""
    t = type(obj)
    mod = getattr(t, "__module__", "builtins")
    qn = getattr(t, "__qualname__", getattr(t, "__name__", str(t)))
    return f"{mod}.{qn}" if mod else qn


def _extract_call_args(args_value: comp.Value | None) -> Tuple[List[Any], Dict[str, Any]]:
    """Convert a Comp args struct into Python positional and keyword args.

    Rules (minimal and permissive):
    - If args_value is not a struct, it's treated as a single positional argument.
    - If struct, convert to Python dict; numeric keys (0,1,2,...) become positional,
      others become kwargs.
    - Also honor optional 'args' (list/tuple) and 'kwargs' (dict) keys if provided.
    """
    pos: List[Any] = []
    kwargs: Dict[str, Any] = {}
    if args_value is None:
        return pos, kwargs
    try:
        if not args_value.is_struct:
            return [_comp_to_python(args_value)], {}
        py_map = _comp_to_python(args_value)
        # Explicit args/kwargs if present
        if isinstance(py_map, dict):
            explicit_args = py_map.get("args")
            explicit_kwargs = py_map.get("kwargs")
            if isinstance(explicit_args, (list, tuple)):
                pos.extend(list(explicit_args))
            if isinstance(explicit_kwargs, dict):
                for k, v in explicit_kwargs.items():
                    kwargs[str(k)] = v

            # Other keys: numeric -> positional (sorted by index), others -> kwargs
            num_keys = sorted(k for k in py_map.keys() if isinstance(k, int))
            for k in num_keys:
                pos.append(py_map[k])
            for k, v in py_map.items():
                if isinstance(k, int):
                    continue
                if k in ("args", "kwargs"):
                    continue
                kwargs[str(k)] = v
    except Exception:
        # On any conversion failure, leave empty to let call likely fail with meaningful error
        pass
    return pos, kwargs


def py_lookup_attr(frame, input_value, args=None):
    """Lookup a fully qualified attribute and return {value, type, repr}.

    Args:
        frame: Execution frame
        input_value: Unused or argument struct
        args: Comp Value struct with field 'name' (string) specifying qualified name

    Returns:
        comp.Value: Struct with keys 'value' (Python object), 'type' (string), 'repr' (string)
                    or a fail value on error.
    """
    if False:  # Make this a generator
        yield
    
    try:
        # Allow passing the argument struct either as args or as input_value
        empty_args = (args is not None and args.is_struct and len(args.struct) == 0)
        if ((args is None or empty_args or not args.is_struct)
            and (input_value is not None and input_value.is_struct)):
            args = input_value
        # Validate args
        if args is None or not args.is_struct:
            return comp.fail("py-lookup-attr requires arg struct with 'name' string")
        name_key = comp.Value("name")
        if name_key not in args.struct or not args.struct[name_key].is_string:
            return comp.fail("py-lookup-attr requires 'name' string field")
        name = args.struct[name_key].data

        # Use pydoc.locate to resolve the name
        obj = pydoc.locate(name)
        if obj is None:
            return comp.fail(f"Could not locate: {name!r}")

        # Build result struct
        type_name = _qualified_type_name(obj)
        result = comp.Value({
            comp.Value("value"): comp.Value(obj),
            comp.Value("type"): comp.Value(type_name),
            comp.Value("repr"): comp.Value(repr(obj)),
        })
        return result
    except Exception as e:
        return comp.fail(f"py-lookup-attr failed: {e}")


def py_call_function(frame, input_value, args=None):
    """Call a fully-qualified function with Comp-structure arguments.

    Args:
        frame: Execution frame
        input_value: Unused or argument struct
        args: Comp Value struct containing:
              - name: string fully-qualified function (e.g., 'urllib.parse.urlparse')
              - optionally positional/keyword args as struct entries

    Returns:
        comp.Value: Python object result or fail on error.
    """
    if False:  # Make this a generator
        yield
    
    try:
        # Allow passing the argument struct either as args or as input_value
        empty_args = (args is not None and args.is_struct and len(args.struct) == 0)
        if ((args is None or empty_args or not args.is_struct)
            and (input_value is not None and input_value.is_struct)):
            args = input_value
        # Validate args
        if args is None or not args.is_struct:
            return comp.fail("py-call-function requires arg struct with 'name' string")
        name_key = comp.Value("name")
        if name_key not in args.struct or not args.struct[name_key].is_string:
            return comp.fail("py-call-function requires 'name' string field")
        name = args.struct[name_key].data
        
        # Resolve function using pydoc.locate
        func_obj = pydoc.locate(name)
        if func_obj is None:
            return comp.fail(f"Could not locate function: {name!r}")

        # Prepare args/kwargs (use args struct as source minus the 'name' field)
        call_arg_struct = comp.Value({k: v for k, v in args.struct.items() if k != name_key})
        pos, kwargs = _extract_call_args(call_arg_struct)
        result = func_obj(*pos, **kwargs)
        return comp.Value(result)
    except Exception as e:
        return comp.fail(f"py-call-function failed: {e}")


def py_call_method(frame, input_value, args=None):
    """Call a method on a Python object or call the object if callable.

    Args:
        frame: Execution frame
        input_value: Comp Value containing Python object directly in data
        args: Comp Value struct with:
              - name: method name string (empty or missing to call the object itself)
              - additional fields used as positional/keyword arguments

    Returns:
        comp.Value: Python object result or fail on error.
    """
    if False:  # Make this a generator
        yield
    
    try:
        # Get Python object directly from input_value.data
        target = input_value.data
        
        method_name = None
        if args and args.is_struct and comp.Value("name") in args.struct:
            name_val = args.struct[comp.Value("name")]
            if name_val.is_string:
                method_name = name_val.data

        # Build call args from args struct without 'name'
        arg_struct = None
        if args and args.is_struct:
            arg_struct = comp.Value({k: v for k, v in args.struct.items() if k != comp.Value("name")})
        pos, kwargs = _extract_call_args(arg_struct)

        # Determine callable
        if method_name and len(method_name) > 0:
            func = getattr(target, method_name)
        else:
            func = target
        result = func(*pos, **kwargs)
        return comp.Value(result)
    except Exception as e:
        return comp.fail(f"py-call-method failed: {e}")


def py_struct_from_object(frame, input_value, args=None):
    """Return a shallow structure/dict representation of a Python object.

    Prefers vars(obj), falls back to reading __dict__, or non-callable attributes
    from dir(obj). Values are converted to Comp via _python_to_comp.
    Exceptions are caught and returned as fail.
    
    Args:
        frame: Execution frame
        input_value: Comp Value containing Python object directly in data
        args: Optional arguments (not used)
        
    Returns:
        Comp Value struct representation or fail on error
    """
    if False:  # Make this a generator
        yield
    
    try:
        # Get Python object directly from input_value.data
        obj = input_value.data
        
        data = None
        try:
            data = vars(obj)
        except Exception:
            pass
        if data is None:
            if hasattr(obj, "__dict__") and isinstance(getattr(obj, "__dict__"), dict):
                data = dict(getattr(obj, "__dict__"))
            else:
                # Last resort: use dir and collect non-callable attrs
                data = {}
                for name in dir(obj):
                    if name.startswith("__") and name.endswith("__"):
                        continue
                    try:
                        val = getattr(obj, name)
                    except Exception:
                        continue
                    # Skip callables
                    if callable(val):
                        continue
                    data[name] = val
        return _python_to_comp(data)
    except Exception as e:
        return comp.fail(f"py-struct-from-object failed: {e}")


def create_module():
    """Create the Python interop module for stdlib imports.
    
    This function is called by the stdlib import system when a user imports:
        !import /py = stdlib "python"
    
    Returns:
        Comp Module with pyobject handle and conversion functions
    """
    module = comp.Module()
    
    # Define the internal Python implementation functions
    module.define_function(
        path=["py-decref"],
        body=comp.PythonFunction("py-decref", py_decref),
        is_pure=False,
        doc="Decrement Python reference count (called by drop-handle function)",
    )
    
    module.define_function(
        path=["py-from-comp-impl"],
        body=comp.PythonFunction("py-from-comp-impl", py_from_comp_impl),
        is_pure=True,
        doc="Convert Comp value to Python object (internal implementation)",
    )
    
    module.define_function(
        path=["py-to-comp-impl"],
        body=comp.PythonFunction("py-to-comp-impl", py_to_comp_impl),
        is_pure=True,
        doc="Convert Python object to Comp value (internal implementation)",
    )

    # Minimal Python API
    module.define_function(
        path=["py-lookup-attr"],
        body=comp.PythonFunction("py-lookup-attr", py_lookup_attr),
        is_pure=True,
        doc="Lookup a fully qualified attribute and return {value, type, repr}",
    )

    module.define_function(
        path=["py-call-function"],
        body=comp.PythonFunction("py-call-function", py_call_function),
        is_pure=False,
        doc="Call a fully-qualified function with Comp-structure args and return a pyobject",
    )

    module.define_function(
        path=["py-call-method"],
        body=comp.PythonFunction("py-call-method", py_call_method),
        is_pure=False,
        doc="Call a method on a pyobject (or call it if callable) and return a pyobject",
    )

    module.define_function(
        path=["py-struct-from-object"],
        body=comp.PythonFunction("py-struct-from-object", py_struct_from_object),
        is_pure=True,
        doc="Build a shallow struct from a Python object (vars/attributes)",
    )
    
    # Define the @pyobject handle
    module.define_handle(
        path=["pyobject"],
        drop_block=None,  # Drop behavior defined via |drop-handle function
    )
    
    # Define the |drop-handle function for @pyobject
    # This is called by the !drop operator
    from comp.ast import Block, Structure, FieldOp, Pipeline, PipeFunc
    
    drop_pipeline = Pipeline(
        seed=None,  # Unseeded pipeline uses $in
        operations=[
            PipeFunc(func_name="py-decref", args=None, namespace=None)
        ]
    )
    drop_structure = Structure(ops=[FieldOp(key=None, value=drop_pipeline)])
    drop_block = Block(body=drop_structure)
    
    module.define_function(
        path=["drop-handle"],
        body=drop_block,
        is_pure=False,
        doc="Drop handler for @pyobject - decrements Python reference count",
    )
    
    return module
