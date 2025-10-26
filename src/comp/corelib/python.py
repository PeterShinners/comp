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
        py_obj = _comp_to_python(input_value)
        
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
