"""Python interop for Comp language.

Provides handles and functions for working with Python objects from Comp code:
- @py-handle: Manages Python object references with automatic cleanup
- |push: Convert Comp values to Python objects
- |pull: Convert Python objects back to Comp values
- |lookup: Get Python object by qualified name
- |call: Call Python functions/methods

The py-handle uses a drop block to automatically decrement Python reference
counts when handles are dropped, preventing memory leaks.

Python objects are stored as private data on @py-handle values to avoid
automatic conversion by the Value constructor.
"""

import comp
import decimal
import pydoc
from typing import Any, Dict, List, Tuple


class _PythonObjectWrapper:
    """Internal wrapper to hold Python objects without Value constructor conversion.
    
    This prevents the Value constructor from auto-converting Python objects like
    named tuples, which would otherwise be converted to Comp structs.

    This is used to pass internal implementation data through Value objects.
    Comp code has no way to create or access these normally.
    """
    __slots__ = ['obj']
    
    def __init__(self, obj):
        self.obj = obj


def py_decref(frame, input_value, args=None):
    """Decrement Python reference count for the wrapped object.
    
    This is called automatically by the @py-handle drop-handle function.
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


def push(frame, input_value, args=None):
    """Push a Comp value into Python (convert Comp → Python).
    
    Creates a Python object from the Comp value and wraps it in a @py-handle:
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
        @py-handle wrapping the Python object
    """
    if False:  # Make this a generator
        yield
    
    try:
        # Convert Comp value to Python object
        input_scalar = input_value.as_scalar()
        py_obj = _comp_to_python(input_scalar)
        
        # Wrap in @py-handle (same pattern as call_function)
        module = frame.scope('module')
        if module is None:
            return comp.fail("push requires module scope")
        
        py_handle_def = module.lookup_handle(["py-handle"], None)
        handle_instance = comp.HandleInstance(py_handle_def)
        handle_value = comp.Value(handle_instance)
        
        # Store the Python object as private data
        wrapper = _PythonObjectWrapper(py_obj)
        handle_value.set_private('__python_object__', comp.Value(wrapper))
        
        return handle_value
    except Exception as e:
        return comp.fail(f"Failed to convert Comp value to Python: {e}")


def pull(frame, input_value, args=None):
    """Pull a Python object from @py-handle into Comp (convert Python → Comp).
    
    Extracts the Python object from a @py-handle and converts it to a Comp value:
    - dict → Struct
    - list/tuple → Struct with numeric keys
    - int/float → Number
    - str → String
    - bool → Tag (#true or #false)
    - None → empty struct
    
    Args:
        frame: Execution frame
        input_value: @py-handle containing Python object in private data
        args: Optional arguments (not used)
        
    Returns:
        Comp Value converted from Python object
    """
    if False:  # Make this a generator
        yield
    
    try:
        # Extract handle
        handle = input_value.as_scalar()
        if not handle.is_handle:
            return comp.fail("pull requires @py-handle input")
        
        # Extract Python object from handle's private data
        py_obj_value = handle.get_private('__python_object__')
        if py_obj_value is None:
            return comp.fail("pull: handle does not contain Python object")
        
        # Extract the actual Python object from the wrapper
        wrapper = py_obj_value.data
        if not isinstance(wrapper, _PythonObjectWrapper):
            return comp.fail(f"pull: expected wrapper, got {type(wrapper).__name__}")
        py_obj = wrapper.obj
        
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
        # Check if all keys are Unnamed AND there's at least one element - if so, convert to list
        # Empty structs remain as empty dicts
        all_unnamed = all(isinstance(key, comp.Unnamed) for key in value.struct.keys()) and len(value.struct) > 0
        if all_unnamed:
            # Convert to Python list
            return [_comp_to_python(val) for val in value.struct.values()]
        
        # Mixed or all named keys - convert to dict
        result = {}
        unnamed_index = 0  # Track position of unnamed fields
        for key, val in value.struct.items():
            # Handle both Value keys and Unnamed keys
            if isinstance(key, comp.Value):
                py_key = _comp_to_python(key)
            elif isinstance(key, comp.Unnamed):
                # Unnamed key - use sequential index
                py_key = unnamed_index
                unnamed_index += 1
            else:
                # Fallback for unknown key types
                py_key = str(key)
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
        # Convert list/tuple to Comp struct with unnamed fields
        struct_dict = {}
        for val in obj:
            comp_key = comp.Unnamed()  # Use Unnamed for positional/ordered fields
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
        
        # If it's a list (all unnamed fields), extend pos with list items as separate positional args
        if isinstance(py_map, list):
            pos.extend(py_map)
        # Explicit args/kwargs if present in dict
        elif isinstance(py_map, dict):
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


def lookup(frame, input_value, args=None):
    """Lookup a Python object by fully qualified name.

    Args:
        frame: Execution frame
        input_value: Unused (for pipeline compatibility)
        args: Comp Value struct with field 'name' (string) - unnamed args auto-paired by morph

    Returns:
        comp.Value: Struct with keys 'value' (Python object), 'type' (string), 'repr' (string)
                    or a fail value on error.
                    
    Example:
        [{} |lookup "sys.float_info.epsilon"]  # Unnamed string → name field via morph
        [{} |lookup {name="sys.version_info"}]  # Explicit name field
    """
    if False:  # Make this a generator
        yield
    
    try:
        # Extract name from args (morph system has already paired unnamed→named)
        if args is None or not args.is_struct:
            return comp.fail("lookup requires name argument")
        
        name_key = comp.Value("name")
        if name_key not in args.struct or not args.struct[name_key].is_string:
            return comp.fail("lookup requires 'name' string field")
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
        return comp.fail(f"lookup failed: {e}")


def call_function(frame, input_value, args=None):
    """Call a Python function by fully-qualified name.

    Args:
        frame: Execution frame
        input_value: Comp Value struct containing Python function arguments
                    (positional as numeric keys, keyword as string keys)
        args: String with fully-qualified function name, or struct with 'name' field
              and optional 'exception-tags' mapping

    Returns:
        comp.Value: @py-handle wrapping the Python object result, or fail on error.
        
    Example:
        [{url="http://example.com" scheme="https"} |call-func "urllib.parse.urlparse"]
        [{database=$path} |call-func {name="sqlite3.connect" exception-tags=$mod.exception-tags}]
    """
    if False:  # Make this a generator
        yield
    
    try:
        # Extract function name and exception-tags from args
        if args is None:
            return comp.fail("call-func requires function name as argument")
        
        exception_tags_map = None
        
        # Accept either a string directly or a struct with 'name' field
        if args.is_string:
            name = args.data
        elif args.is_struct:
            name_key = comp.Value("name")
            if name_key not in args.struct or not args.struct[name_key].is_string:
                return comp.fail("call-func requires 'name' string field in arg struct")
            name = args.struct[name_key].data
            
            # Check for exception-tags field
            exception_tags_key = comp.Value("exception-tags")
            if exception_tags_key in args.struct:
                exception_tags_map = args.struct[exception_tags_key]
                # If it's an empty struct (default value), treat as not provided
                if exception_tags_map.is_struct and len(exception_tags_map.struct) == 0:
                    exception_tags_map = None
        else:
            return comp.fail("call-func requires string name or struct with 'name' field")
        
        # Fallback to $mod.exception-tags if not provided in args
        if exception_tags_map is None:
            mod = frame.scope('mod')
            if mod is not None and mod.is_struct:
                mod_exception_tags_key = comp.Value("exception-tags")
                if mod_exception_tags_key in mod.struct:
                    exception_tags_map = mod.struct[mod_exception_tags_key]
        
        # Resolve function using pydoc.locate
        func_obj = pydoc.locate(name)
        if func_obj is None:
            return comp.fail(f"Could not locate function: {name!r}")

        # Prepare args/kwargs from input_value
        pos, kwargs = _extract_call_args(input_value)
        python_result = func_obj(*pos, **kwargs)
        
        # Smart conversion: auto-convert simple types, wrap complex types as handles
        if python_result is None or isinstance(python_result, (bool, int, float, str, list, dict)):
            # Simple types: convert directly to Comp values
            return _python_to_comp(python_result)
        else:
            # Complex types (objects, modules, functions): wrap as @py-handle
            module = frame.scope('module')
            if module is None:
                return comp.fail("call-func requires module scope")
            
            py_handle_def = module.lookup_handle(["py-handle"], None)
            handle_instance = comp.HandleInstance(py_handle_def)
            
            # Create a Value wrapping the handle, and store the Python object in private data
            handle_value = comp.Value(handle_instance)
            # Wrap the Python object to prevent Value constructor conversion (e.g., tuples -> structs)
            wrapper = _PythonObjectWrapper(python_result)
            handle_value.set_private('__python_object__', comp.Value(wrapper))
            
            return handle_value
    except Exception as e:
        # Map exception to specific fail tag if exception-tags mapping is provided
        fail_tag = None
        if exception_tags_map is not None and exception_tags_map.is_struct:
            # Look up the exception type in the mapping
            exception_type_key = comp.Value(type(e).__name__)
            if exception_type_key in exception_tags_map.struct:
                mapped_value = exception_tags_map.struct[exception_type_key]
                if mapped_value.is_tag:
                    fail_tag = mapped_value
        
        # Return failure with mapped tag if found, otherwise generic fail
        if fail_tag is not None:
            return comp.Value({
                comp.Unnamed(): fail_tag,
                comp.Value("message"): comp.Value(str(e)),
                comp.Value("exception_type"): comp.Value(type(e).__name__),
                comp.Value("exception_module"): comp.Value(type(e).__module__),
            })
        else:
            return comp.fail(
                str(e),
                exception_type=type(e).__name__,
                exception_module=type(e).__module__,
            )


def call_str(frame, input_value, args=None):
    """Pure string method call - only allows str type and safe string methods.
    
    This is a pure function that can be called from pure Comp functions.
    It validates that the input is a string and only allows calling methods
    from a safe allowlist of pure string methods.
    
    Input can be:
    - A string (scalar): for simple method calls with no arguments
    - A struct with 'self' field: 'self' is the string, other fields become method arguments
      - Named fields become keyword arguments
      - Unnamed fields become positional arguments
    
    Args:
        frame: Execution frame
        input_value: Comp Value - string or struct with 'self' string field
        args: Comp Value - string with method name
        
    Returns:
        comp.Value: Result of the string method call (auto-converted to Comp value)
        
    Example:
        ["hello" |call-str "upper"]  → "HELLO"
        [{self="hello" "l" "r"} |call-str "replace"]  → "herro"  (positional args)
        [{self="hello" fillchar="=" width=10} |call-str "center"]  → "===hello=="  (keyword args)
    """
    if False:  # Make this a generator
        yield
    
    # Extract method name from args
    if args is None:
        return comp.fail("call-str requires method name argument")

    print("CALLSTR:", input_value, input_value.unparse(), args.unparse())

    # Args might be a struct with unnamed field wrapping the string
    if args.is_struct:
        # Check for unnamed field
        for key, val in args.struct.items():
            if isinstance(key, comp.Unnamed) and val.is_string:
                method_name = val.data
                break
        else:
            return comp.fail(f"call-str requires string method name, got struct without unnamed string: {args}")
    elif args.is_string:
        method_name = args.data
    else:
        return comp.fail(f"call-str requires string method name, got {type(args.data).__name__}")
    
    # Extract string value and method arguments from input
    input_scalar = input_value.as_scalar()
    
    if input_scalar.is_string:
        # Simple string input: no method arguments
        target_string = input_scalar.data
        method_args = comp.Value({})
    elif input_scalar.is_struct:
        # Struct input: extract 'self' field as the string, rest are method arguments
        self_key = comp.Value("self")
        if self_key not in input_scalar.struct:
            return comp.fail("call-str struct input requires 'self' field with string value")
        
        target_value = input_scalar.struct[self_key].as_scalar()
        if not isinstance(target_value.data, str):
            return comp.fail(f"call-str 'self' field must be string, got {type(target_value.data).__name__}")
        
        target_string = target_value.data
        # Extract method arguments (everything except 'self')
        method_args = comp.Value({k: v for k, v in input_scalar.struct.items() if k != self_key})
    else:
        return comp.fail(f"call-str requires string or struct input, got {type(input_scalar.data).__name__}")
    
    # Allowlist of safe pure string methods
    SAFE_STRING_METHODS = {
        'upper', 'lower', 'capitalize', 'title', 'swapcase', 'casefold',
        'strip', 'lstrip', 'rstrip', 'removeprefix', 'removesuffix',
        'split', 'rsplit', 'splitlines', 'partition', 'rpartition',
        'join', 'replace', 'translate', 'maketrans',
        'center', 'ljust', 'rjust', 'zfill', 'expandtabs',
        'startswith', 'endswith', 'find', 'rfind', 'index', 'rindex',
        'count', 'format', 'format_map',
        'isalnum', 'isalpha', 'isascii', 'isdecimal', 'isdigit',
        'isidentifier', 'islower', 'isnumeric', 'isprintable',
        'isspace', 'istitle', 'isupper',
        '__len__', '__contains__', '__getitem__', '__mul__',
    }
    
    if method_name not in SAFE_STRING_METHODS:
        return comp.fail(f"call-str: method '{method_name}' not in safe list")
    
    # Get the method
    try:
        method = getattr(target_string, method_name)
    except AttributeError:
        return comp.fail(f"call-str: string has no method '{method_name}'")

    # Convert arguments to Python
    pos, kwargs = _extract_call_args(method_args)

    # Convert Decimal arguments to int for methods that need integers
    # (like __mul__ for string repetition)
    # Also convert empty dicts to None for methods like split(sep=None)
    pos_converted = []
    for arg in pos:
        if isinstance(arg, decimal.Decimal) and arg == int(arg):
            pos_converted.append(int(arg))
        elif isinstance(arg, dict) and len(arg) == 0:
            pos_converted.append(None)
        else:
            pos_converted.append(arg)

    kwargs_converted = {}
    for key, val in kwargs.items():
        if isinstance(val, dict) and len(val) == 0:
            kwargs_converted[key] = None
        elif isinstance(val, decimal.Decimal):
            # Convert Decimal to int if it's a whole number
            kwargs_converted[key] = int(val)
        else:
            kwargs_converted[key] = val

    # Call the method
    try:
        # Debug: print what we're passing
        # print(f"DEBUG call-str: method={method_name}, pos={pos_converted}, kwargs={kwargs_converted}")
        result = method(*pos_converted, **kwargs_converted)
    except Exception as e:
        # Include debug info in error message
        return comp.fail(f"call-str '{method_name}' failed: {e}\nArgs: pos={pos_converted}, kwargs={kwargs_converted}")
    
    # Auto-convert result to Comp value
    compresult = _python_to_comp(result)
    compresult = compresult.as_struct()
    return compresult


def call_method(frame, input_value, args=None):
    """Call a method on a Python object.

    This overload is selected when input is a @py-handle.
    Additional fields in a struct input become method arguments.

    Args:
        frame: Execution frame
        input_value: Comp Value - either:
                    - Scalar @py-handle (for simple method calls with no args)
                    - Struct with 'self' @py-handle field (for methods with args)
        args: Comp Value struct with 'name' field for method name and optional 'exception-tags' mapping

    Returns:
        comp.Value: @py-handle wrapping the Python object result, or fail on error.
        
    Example:
        [$pyobj |call "method_name"]  # Scalar input
        [{self=$pyobj x=1} |call "method_name"]  # Struct input with args
    """
    if False:  # Make this a generator
        yield
    
    try:
        # Extract method name and exception-tags from args
        if args is None or not args.is_struct:
            return comp.fail("call requires method name")
        
        name_key = comp.Value("name")
        if name_key not in args.struct or not args.struct[name_key].is_string:
            return comp.fail("call requires 'name' string field")
        method_name = args.struct[name_key].data
        
        # Check for exception-tags field
        exception_tags_map = None
        exception_tags_key = comp.Value("exception-tags")
        if exception_tags_key in args.struct:
            exception_tags_map = args.struct[exception_tags_key]
            # If it's an empty struct (default value), treat as not provided
            if exception_tags_map.is_struct and len(exception_tags_map.struct) == 0:
                exception_tags_map = None
        
        # Fallback to $mod.exception-tags if not provided in args
        if exception_tags_map is None:
            mod = frame.scope('mod')
            if mod is not None and mod.is_struct:
                mod_exception_tags_key = comp.Value("exception-tags")
                if mod_exception_tags_key in mod.struct:
                    exception_tags_map = mod.struct[mod_exception_tags_key]
        
        # Input should be a struct with 'self' field (morph handles unnamed→named pairing)
        # Scalar handles get auto-wrapped to unnamed field, then morphed to 'self'
        if not input_value.is_struct:
            return comp.fail("call (method) expected struct input")
        
        self_key = comp.Value("self")
        if self_key not in input_value.struct:
            return comp.fail("call (method) requires struct with 'self' field containing @py-handle")
        
        target_handle = input_value.struct[self_key].as_scalar()
        
        # Extract method arguments from input (everything except 'self')
        method_args = comp.Value({k: v for k, v in input_value.struct.items() if k != self_key})
        
        # Extract the Python object from the handle's private data
        if not target_handle.is_handle:
            return comp.fail("call (method) requires @py-handle input")
        
        py_obj_value = target_handle.get_private('__python_object__')
        if py_obj_value is None:
            return comp.fail("call (method): handle does not contain Python object")
        
        # Extract the actual Python object from the wrapper
        wrapper = py_obj_value.data  # Get the _PythonObjectWrapper instance
        if not isinstance(wrapper, _PythonObjectWrapper):
            return comp.fail(f"call (method): expected wrapper, got {type(wrapper).__name__}")
        target = wrapper.obj
        
        # Convert arguments to Python
        pos, kwargs = _extract_call_args(method_args)
        
        # Get the method and call it
        func = getattr(target, method_name)
        python_result = func(*pos, **kwargs)
        
        # Smart conversion: auto-convert simple types, wrap complex types as handles
        if python_result is None or isinstance(python_result, (bool, int, float, str, list, dict)):
            # Simple types: convert directly to Comp values
            return _python_to_comp(python_result)
        else:
            # Complex types (objects, modules, functions): wrap as @py-handle
            module = frame.scope('module')
            if module is None:
                return comp.fail("call requires module scope")
            
            py_handle_def = module.lookup_handle(["py-handle"], None)
            handle_instance = comp.HandleInstance(py_handle_def)
            
            handle_value = comp.Value(handle_instance)
            wrapper = _PythonObjectWrapper(python_result)
            handle_value.set_private('__python_object__', comp.Value(wrapper))
            
            return handle_value
    except Exception as e:
        # Map exception to specific fail tag if exception-tags mapping is provided
        fail_tag = None
        if exception_tags_map is not None and exception_tags_map.is_struct:
            # Look up the exception type in the mapping
            exception_type_key = comp.Value(type(e).__name__)
            if exception_type_key in exception_tags_map.struct:
                mapped_value = exception_tags_map.struct[exception_type_key]
                if mapped_value.is_tag:
                    fail_tag = mapped_value
        
        # Return failure with mapped tag if found, otherwise generic fail
        if fail_tag is not None:
            return comp.Value({
                comp.Unnamed(): fail_tag,
                comp.Value("message"): comp.Value(str(e)),
                comp.Value("exception_type"): comp.Value(type(e).__name__),
                comp.Value("exception_module"): comp.Value(type(e).__module__),
            })
        else:
            return comp.fail(
                str(e),
                exception_type=type(e).__name__,
                exception_module=type(e).__module__,
            )


def py_slice(frame, input_value, args=None):
    """Slice a sequence (string, list, etc.) using Python slice syntax.

    This is a pure function that performs slicing on the input object.
    Accepts start, stop, and step parameters.

    Args:
        frame: Execution frame
        input_value: Comp Value - the object to slice (string, list, etc.)
        args: Comp Value struct with optional 'start', 'stop', 'step' fields (all numbers or nil)

    Returns:
        Sliced result converted to Comp value

    Example:
        ["hello" |py/slice {start=0 stop=3}]  → "hel"
        ["hello" |py/slice {step=-1}]  → "olleh"
        ["hello" |py/slice {start=1}]  → "ello"
    """
    if False:  # Make this a generator
        yield

    try:
        # Extract the input object
        input_scalar = input_value.as_scalar()

        # Convert to Python object
        py_obj = _comp_to_python(input_scalar)

        # Verify the object supports slicing
        if not hasattr(py_obj, '__getitem__'):
            return comp.fail(f"slice: object of type {type(py_obj).__name__} does not support slicing")

        # Extract slice parameters from args
        start = None
        stop = None
        step = None

        if args is not None and args.is_struct:
            start_key = comp.Value("start")
            stop_key = comp.Value("stop")
            step_key = comp.Value("step")

            if start_key in args.struct:
                start_val = args.struct[start_key]
                if start_val.is_number:
                    start = int(start_val.data)

            if stop_key in args.struct:
                stop_val = args.struct[stop_key]
                if stop_val.is_number:
                    stop = int(stop_val.data)

            if step_key in args.struct:
                step_val = args.struct[step_key]
                if step_val.is_number:
                    step = int(step_val.data)

        # Perform the slice operation
        result = py_obj[start:stop:step]

        # Convert result back to Comp
        return _python_to_comp(result)
    except Exception as e:
        return comp.fail(f"slice failed: {e}")


def py_vars(frame, input_value, args=None):
    """Return a shallow structure/dict representation of a Python object.

    Extracts the Python object from a @py-handle and converts its attributes to a Comp struct.
    Prefers vars(obj), falls back to reading __dict__, or non-callable attributes
    from dir(obj). Values are converted to Comp via _python_to_comp.
    Exceptions are caught and returned as fail.

    Args:
        frame: Execution frame
        input_value: @py-handle containing Python object in private data
        args: Optional arguments (not used)

    Returns:
        Comp Value struct representation or fail on error
    """
    if False:  # Make this a generator
        yield

    try:
        # Extract handle
        handle = input_value.as_scalar()
        if not handle.is_handle:
            return comp.fail("vars requires @py-handle input")

        # Extract Python object from handle's private data
        py_obj_value = handle.get_private('__python_object__')
        if py_obj_value is None:
            return comp.fail("vars: handle does not contain Python object")

        # Extract the actual Python object from the wrapper
        wrapper = py_obj_value.data
        if not isinstance(wrapper, _PythonObjectWrapper):
            return comp.fail(f"vars: expected wrapper, got {type(wrapper).__name__}")
        obj = wrapper.obj

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
        return comp.fail(f"vars failed: {e}")


def create_module():
    """Create the Python interop module for stdlib imports.
    
    This function is called by the stdlib import system when a user imports:
        !import /py = stdlib "python"
    
    Returns:
        Comp Module with @py-handle and conversion/call functions
    """
    module = comp.Module()
    
    # Define the @py-handle FIRST so it can be referenced in shapes
    module.define_handle(
        path=["py-handle"]
    )
    
    module.define_py_function(
        path=["py-decref"],
        python_func=py_decref,
        # is_pure=False,
    )
    
    module.define_py_function(
        path=["push"],
        python_func=push,
        is_pure=True,
    )
    
    module.define_py_function(
        path=["pull"],
        python_func=pull,
        is_pure=True,
    )

    # Python API
    module.define_py_function(
        path=["lookup"],
        python_func=lookup,
        arg_shape="~{name ~str}",
        is_pure=True,
    )

    module.define_py_function(
        path=["call-func"],
        python_func=call_function,
        arg_shape="~{name ~str exception-tags ~struct={}}",
    )

    # Pure string method call - for use in pure Comp functions
    # Input can be string (scalar) or struct with 'self' field
    # Arg is just the method name as a string
    module.define_py_function(
        path=["call-str"],
        python_func=call_str,
        input_shape="~any",  # Accept string or struct with 'self'
        arg_shape="~str",  # Method name as string
        is_pure=True,
    )

    # Pure slice creation - for use in pure Comp functions
    module.define_py_function(
        path=["slice"],
        python_func=py_slice,
        input_shape="~struct|~str",
        arg_shape="~{start ~num|~nil={} stop ~num|~nil={} step ~num|~nil={}}",
        is_pure=True,
    )

    # Register two overloads of |call:
    # Both take {name~str} as args, but differ in input shape:
    # 1. Method call: input is @py-handle (scalar Python object)
    # 2. Function call: input is a struct with function arguments
    # Overload resolution discriminates based on input: ~{self @py-handle} scores higher than ~any
    
    # Method overload: Input = struct with 'self' @py-handle field, Args = {name~str}
    # Calls method on the Python object
    # Input can be:
    #   - Scalar handle (auto-wrapped to unnamed field, then morphed to 'self' field)
    #   - Explicit struct {self=handle}
    #   - Struct with additional fields that become method arguments
    # The shape ~{self @py-handle} uses weak morph to allow additional fields and unnamed→named pairing
    module.define_py_function(
        path=["call"],
        python_func=call_method,
        input_shape="~{self @py-handle}",
        arg_shape="~{name ~str exception-tags ~struct={}}",
    )
    
    # Function call overload: Input = ~any, Args = {name~str}
    # Calls fully qualified Python function with input as arguments
    module.define_py_function(
        path=["call"],
        python_func=call_function,
        input_shape="~any",
        arg_shape="~{name ~str exception-tags ~struct={}}",
    )

    module.define_py_function(
        path=["vars"],
        python_func=py_vars,
        is_pure=True,
    )
    
    # Define the |drop-handle function for @py-handle
    # This is called by the !drop operator
    drop_pipeline = comp.ast.Pipeline(
        seed=None,  # Unseeded pipeline uses $in
        operations=[
            comp.ast.PipeFunc(func_name="py-decref", args=None, namespace=None)
        ]
    )
    drop_structure = comp.ast.Structure(ops=[comp.ast.FieldOp(key=None, value=drop_pipeline)])
    module.define_function(
        path=["drop-handle"],
        body=comp.ast.Block(body=drop_structure),
        doc="Drop handler for @py-handle - decrements Python reference count",
    )
    
    return module
