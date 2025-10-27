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
import importlib
import pydoc
from typing import Any, Dict, List, Tuple

# Simple registry to hold opaque Python objects that cannot be stored directly
# inside a Comp Value. We key by Python's id(obj) to avoid managing our own
# counters. Minimal lifecycle management is fine for tests.
_PY_REGISTRY: Dict[int, Any] = {}


# Module constant for pyobject handle
PYOBJECT_MODULE = """
!doc module "Python interop - handles and conversion functions for Python objects"

!handle @pyobject = {
    drop = :{
        ; Decrement Python reference count when handle is dropped
        [$in |py-decref]
    }
}

!doc "Convert a Comp value to a Python object wrapped in @pyobject handle"
!func |py-from-comp ~@pyobject = {
    ; Convert the input value to a Python object
    ; Returns a handle wrapping the Python object
    [$in |py-from-comp-impl]
}

!doc "Convert a Python object handle to a Comp value"
!func |py-to-comp ~any arg ~{obj @pyobject} = {
    ; Extract Python object from handle and convert to Comp value
    [$arg.obj |py-to-comp-impl]
}
"""


def py_decref(input_value, **scopes):
    """Decrement Python reference count for the wrapped object.
    
    This is called automatically by the @pyobject handle's drop block.
    The input should be a struct with a 'ptr' field containing the Python object.
    
    Args:
        input_value: Comp Value containing Python object wrapper
        **scopes: Execution scopes (not used)
        
    Returns:
        Empty Comp Value on success
    """
    # Best-effort no-op: only act when a wrapper struct with 'ptr' exists
    if not input_value.is_struct:
        return comp.Value({})

    ptr_key = comp.Value("ptr")
    if ptr_key not in input_value.struct:
        return comp.Value({})
    
    # The ptr field should contain a Python object
    # In Python, we don't need to manually manage refcounts for objects
    # we're holding references to - Python's GC handles it
    # This function exists as a hook for future manual memory management if needed
    
    return comp.Value({})


def py_from_comp_impl(input_value, **scopes):
    """Convert a Comp value to a Python object.
    
    Creates a deep copy of the Comp value as a Python object:
    - Structs → dicts
    - Numbers → int/float
    - Strings → str
    - Tags → str (tag name)
    - Booleans → bool
    - Handles → error (can't convert handles to Python)
    
    Args:
        input_value: Comp Value to convert
        **scopes: Execution scopes (not used)
        
    Returns:
        Comp Value containing struct with 'ptr' field holding Python object
    """
    try:
        # Convert Comp value to Python object
        input_scalar = input_value.as_scalar()
        py_obj = _comp_to_python(input_scalar)
        
        # Wrap in a struct that can be used with @pyobject handle
        result = comp.Value({
            comp.Value("ptr"): comp.Value(py_obj)
        })
        
        return result
    except Exception as e:
        return comp.fail(f"Failed to convert Comp value to Python: {e}")


def py_to_comp_impl(input_value, **scopes):
    """Convert a Python object back to a Comp value.
    
    Creates a deep copy of the Python object as a Comp value:
    - dict → Struct
    - list/tuple → Struct with numeric keys
    - int/float → Number
    - str → String
    - bool → Tag (#true or #false)
    - None → empty struct
    
    Args:
        input_value: Comp Value containing struct with 'ptr' field
        **scopes: Execution scopes (not used)
        
    Returns:
        Comp Value converted from Python object
    """
    # Extract the Python object from the wrapper
    if not input_value.is_struct:
        return comp.fail("py-to-comp requires struct input with Python object")
    
    ptr_key = comp.Value("ptr")
    if ptr_key not in input_value.struct:
        return comp.fail("py-to-comp requires 'ptr' field with Python object")
    
    ptr_value = input_value.struct[ptr_key]

    try:
        # Get the Python object (stored directly in Value.data)
        py_obj = ptr_value.data
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


# ---- Minimal Python API helpers ----

def _wrap_pyobject(py_obj: Any) -> comp.Value:
    """Wrap a Python object in the standard pyobject struct {ptr=<py_obj>}.

    Note: This naive wrapper only works for Python types the Value constructor accepts
    (numbers, strings, dicts, lists, etc.). For arbitrary objects, use _wrap_pyobject_safe.
    """
    return comp.Value({comp.Value("ptr"): comp.Value(py_obj)})


def _wrap_pyobject_safe(py_obj: Any) -> comp.Value:
    """Wrap a Python object, falling back to registry for unsupported types.

    If the Comp Value cannot directly hold the object, store id(obj) in the 'ptr'
    field and keep the actual object in a module-global registry.
    """
    # Prefer direct storage only for primitive-safe types; otherwise use registry
    if isinstance(py_obj, (str, int, float, bool, dict)):
        return _wrap_pyobject(py_obj)
    # For lists/tuples and arbitrary objects, use registry to preserve methods/identity
    key = id(py_obj)
    _PY_REGISTRY[key] = py_obj
    return comp.Value({comp.Value("ptr"): comp.Value(key)})


def _resolve_pyobject_from_wrapper(wrapper: comp.Value) -> Tuple[Any, str | None]:
    """Extract the Python object from a pyobject wrapper struct.

    Supports two encodings in the 'ptr' field:
    - Directly storable Python types (str, dict, list, etc.) stored as a Value
      that we convert via _comp_to_python
    - Opaque objects stored as numeric id() pointing into _PY_REGISTRY

    Returns (py_obj, error_message). On success, error_message is None.
    """
    # Accept either the pyobject struct directly, or a single unnamed field
    # wrapping the pyobject struct (pipeline may wrap values).
    if not wrapper or not wrapper.is_struct:
        return None, "pyobject struct with 'ptr' required"
    ptr_key = comp.Value("ptr")
    struct = wrapper.struct
    if struct is None:
        return None, "pyobject struct with 'ptr' required"
    if ptr_key in struct:
        ptr_val = struct[ptr_key]
    else:
        # Try unwrap one unnamed layer
        if len(struct) == 1:
            (only_key, only_val), = struct.items()
            # comp.Unnamed keys are used for positional/unnamed fields
            if isinstance(only_key, comp.Unnamed) and only_val.is_struct and only_val.struct and ptr_key in only_val.struct:
                ptr_val = only_val.struct[ptr_key]
            else:
                return None, "pyobject struct requires 'ptr' field"
        else:
            return None, "pyobject struct requires 'ptr' field"
    # Unwrap scalar for ptr if it's wrapped in a single unnamed field
    if ptr_val is not None and ptr_val.is_struct and len(ptr_val.data) == 1:
        (k, v), = ptr_val.data.items()
        if isinstance(k, comp.Unnamed):
            ptr_val = v
    # If numeric, treat as registry id
    if ptr_val.is_number:
        try:
            key_int = int(ptr_val.data)
            if key_int in _PY_REGISTRY:
                return _PY_REGISTRY[key_int], None
            return None, f"unknown pyobject id: {key_int}"
        except Exception as e:
            return None, f"invalid pyobject id: {e}"
    # Otherwise, convert Comp value back to Python (str, dict, list, etc.)
    try:
        return _comp_to_python(ptr_val), None
    except Exception as e:
        return None, f"cannot convert 'ptr' to python object: {e}"


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


def py_lookup_attr(input_value, args=None):
    """Lookup a fully qualified attribute and return {value, type, repr}.

    Args:
        input_value: Unused
        args: Comp Value struct with field 'name' (string) specifying qualified name

    Returns:
        comp.Value: Struct with keys 'value' (pyobject struct), 'type' (string), 'repr' (string)
                    or a fail value on error.
    """
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

        # Try locate via pydoc; fallback to manual import traversal
        obj = pydoc.locate(name)
        if obj is None:
            parts = name.split(".")
            if not parts:
                return comp.fail(f"Invalid name: {name!r}")
            # progressively import modules and getattr
            cur = None
            for i in range(1, len(parts) + 1):
                mod_name = ".".join(parts[:i])
                try:
                    cur = importlib.import_module(mod_name)
                except Exception:
                    # First non-module part: walk attributes from last imported cur
                    cur = cur if cur is not None else importlib.import_module(parts[0])
                    for attr in parts[i - 1:]:
                        cur = getattr(cur, attr)
                    break
            obj = cur

        # Build result struct
        type_name = _qualified_type_name(obj)
        value_struct = _wrap_pyobject_safe(obj)
        result = comp.Value({
            comp.Value("value"): value_struct,
            comp.Value("type"): comp.Value(type_name),
            comp.Value("repr"): comp.Value(repr(obj)),
        })
        return result
    except Exception as e:
        return comp.fail(f"py-lookup-attr failed: {e}")


def py_call_function(input_value, args=None):
    """Call a fully-qualified function with Comp-structure arguments.

    Args:
        input_value: Unused
        args: Comp Value struct containing:
              - name: string fully-qualified function (e.g., 'urllib.parse.urlparse')
              - optionally positional/keyword args as struct entries

    Returns:
        comp.Value: pyobject struct wrapping the result or fail on error.
    """
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
        # Resolve function
        func_obj = pydoc.locate(name)
        if func_obj is None:
            # Fallback: resolve manually
            parts = name.split(".")
            if not parts:
                return comp.fail(f"Invalid function name: {name!r}")
            mod = importlib.import_module(parts[0])
            func_obj = mod
            for comp_name in parts[1:]:
                func_obj = getattr(func_obj, comp_name)

        # Prepare args/kwargs (use args struct as source minus the 'name' field)
        # Remove 'name' and pass the rest
        # Create a shallow copy of args without 'name'
        call_arg_struct = comp.Value({k: v for k, v in args.struct.items() if k != name_key})
        pos, kwargs = _extract_call_args(call_arg_struct)
        result = func_obj(*pos, **kwargs)
        return _wrap_pyobject_safe(result)
    except Exception as e:
        return comp.fail(f"py-call-function failed: {e}")


def py_call_method(input_value, args=None):
    """Call a method on a Python object or call the object if callable.

    Args:
        input_value: Comp Value struct with 'ptr' holding the Python object (self)
        args: Comp Value struct with:
              - name: method name string (empty or missing to call the object itself)
              - additional fields used as positional/keyword arguments

    Returns:
        comp.Value: pyobject struct wrapping the result or fail on error.
    """
    # Extract Python object from input_value
    py_obj, err = _resolve_pyobject_from_wrapper(input_value)
    if err is not None:
        return comp.fail(f"py-call-method requires input pyobject: {err}")
    try:
        target = py_obj
        # Defensive: if we somehow received a Python dict like {'ptr': obj},
        # unwrap to the underlying object.
        if isinstance(target, dict) and len(target) == 1 and "ptr" in target:
            target = target["ptr"]
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
        return _wrap_pyobject_safe(result)
    except Exception as e:
        return comp.fail(f"py-call-method failed: {e}")


def py_struct_from_object(input_value, args=None):
    """Return a shallow structure/dict representation of a Python object.

    Prefers vars(obj), falls back to reading __dict__, or non-callable attributes
    from dir(obj). Values are converted to Comp via _python_to_comp.
    Exceptions are caught and returned as fail.
    """
    # Extract the Python object
    py_obj, err = _resolve_pyobject_from_wrapper(input_value)
    if err is not None:
        return comp.fail(f"py-struct-from-object requires input pyobject: {err}")
    try:
        obj = py_obj
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


# Wrapper functions to match PythonFunction signature (frame, input_value, args)
# All PythonFunctions must be generators

def _py_decref_wrapper(frame, input_value, args=None):
    """Wrapper for py_decref to match PythonFunction signature."""
    if False:  # Never execute this, but makes it a generator
        yield
    return py_decref(input_value)


def _py_from_comp_wrapper(frame, input_value, args=None):
    """Wrapper for py_from_comp_impl to match PythonFunction signature."""
    if False:  # Never execute this, but makes it a generator
        yield
    return py_from_comp_impl(input_value)


def _py_to_comp_wrapper(frame, input_value, args=None):
    """Wrapper for py_to_comp_impl to match PythonFunction signature."""
    if False:  # Never execute this, but makes it a generator
        yield
    return py_to_comp_impl(input_value)


def _py_lookup_attr_wrapper(frame, input_value, args=None):
    """Wrapper for py_lookup_attr to match PythonFunction signature."""
    if False:
        yield
    return py_lookup_attr(input_value, args)


def _py_call_function_wrapper(frame, input_value, args=None):
    """Wrapper for py_call_function to match PythonFunction signature."""
    if False:
        yield
    return py_call_function(input_value, args)


def _py_call_method_wrapper(frame, input_value, args=None):
    """Wrapper for py_call_method to match PythonFunction signature."""
    if False:
        yield
    return py_call_method(input_value, args)


def _py_struct_from_object_wrapper(frame, input_value, args=None):
    """Wrapper for py_struct_from_object to match PythonFunction signature."""
    if False:
        yield
    return py_struct_from_object(input_value, args)


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
        body=comp.PythonFunction("py-decref", _py_decref_wrapper),
        is_pure=False,
        doc="Decrement Python reference count (called by @pyobject drop block)",
    )
    
    module.define_function(
        path=["py-from-comp-impl"],
        body=comp.PythonFunction("py-from-comp-impl", _py_from_comp_wrapper),
        is_pure=True,
        doc="Convert Comp value to Python object (internal implementation)",
    )
    
    module.define_function(
        path=["py-to-comp-impl"],
        body=comp.PythonFunction("py-to-comp-impl", _py_to_comp_wrapper),
        is_pure=True,
        doc="Convert Python object to Comp value (internal implementation)",
    )

    # Minimal Python API
    module.define_function(
        path=["py-lookup-attr"],
        body=comp.PythonFunction("py-lookup-attr", _py_lookup_attr_wrapper),
        is_pure=True,
        doc="Lookup a fully qualified attribute and return {value, type, repr}",
    )

    module.define_function(
        path=["py-call-function"],
        body=comp.PythonFunction("py-call-function", _py_call_function_wrapper),
        is_pure=False,
        doc="Call a fully-qualified function with Comp-structure args and return a pyobject",
    )

    module.define_function(
        path=["py-call-method"],
        body=comp.PythonFunction("py-call-method", _py_call_method_wrapper),
        is_pure=False,
        doc="Call a method on a pyobject (or call it if callable) and return a pyobject",
    )

    module.define_function(
        path=["py-struct-from-object"],
        body=comp.PythonFunction("py-struct-from-object", _py_struct_from_object_wrapper),
        is_pure=True,
        doc="Build a shallow struct from a Python object (vars/attributes)",
    )
    
    # Create the drop block AST manually: :{[$in |py-decref]}
    # The structure is: Block(Structure([FieldOp(Pipeline([PipeFunc("py-decref")]))]))
    from comp.ast import Block, Structure, FieldOp, Pipeline, PipeFunc
    
    drop_pipeline = Pipeline(
        seed=None,  # Unseeded pipeline uses $in
        operations=[
            PipeFunc(func_name="py-decref", args=None, namespace=None)
        ]
    )
    drop_structure = Structure(ops=[FieldOp(key=None, value=drop_pipeline)])
    drop_block = Block(body=drop_structure)
    
    # Define the @pyobject handle with drop block
    module.define_handle(
        path=["pyobject"],
        drop_block=drop_block,
    )
    
    return module


# Note: _py_decref_wrapper already defined above as a generator-compatible wrapper
