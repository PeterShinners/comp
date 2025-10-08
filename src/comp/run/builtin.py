"""Builtin constants and functions for Comp runtime."""

__all__ = ["get_builtin_module"]

from . import _func, _mod, _tag, _value

# Singleton builtin tag instances
# TODO: When implementing comparison operators, these need special handling:
#   - Comparison operators (==, <, etc.) should return these exact TagValue instances
#   - Tag equality must be based on identity/definition, not name or identifier
#   - Module namespace resolution needs to return references to these singletons
#   - Each module importing builtins should reference the same TagValue instances,
#     not create new ones with the same name
_true_tag = _tag.TagValue(["true"], "builtin")
_false_tag = _tag.TagValue(["false"], "builtin")
_skip_tag = _tag.TagValue(["skip"], "builtin")
_break_tag = _tag.TagValue(["break"], "builtin")
_fail_tag = _tag.TagValue(["fail"], "builtin")
_fail_syntax_tag = _tag.TagValue(["fail", "syntax"], "builtin")
_fail_missing_tag = _tag.TagValue(["fail", "missing"], "builtin")
_fail_type_tag = _tag.TagValue(["fail", "type"], "builtin")
_fail_value_tag = _tag.TagValue(["fail", "value"], "builtin")
_fail_index_tag = _tag.TagValue(["fail", "index"], "builtin")
_fail_runtime_tag = _tag.TagValue(["fail", "runtime"], "builtin")
_fail_placeholder_tag = _tag.TagValue(["fail", "placeholder"], "builtin")


# Expose as backwards-compatible names
true = _true_tag
false = _false_tag
skip = _skip_tag
break_ = _break_tag
fail = _fail_tag
fail_syntax = _fail_syntax_tag
fail_missing = _fail_missing_tag
fail_type = _fail_type_tag
fail_value = _fail_value_tag
fail_index = _fail_index_tag
fail_runtime = _fail_runtime_tag
fail_placeholder = _fail_placeholder_tag

nil = _value.Value({})


# Builtin Python functions

def _print_func(in_value: _value.Value, arg_value: _value.Value) -> _value.Value:
    """Print function - prints the input value and passes it through."""
    print(in_value)
    return in_value


def _double_func(in_value: _value.Value, arg_value: _value.Value) -> _value.Value:
    """Double function - doubles a numeric value or all numeric fields in a struct."""
    if in_value.is_num:
        return _value.Value(in_value.num * 2)
    elif in_value.is_struct and in_value.struct:
        # Double all numeric fields
        result = {}
        for key, val in in_value.struct.items():
            if val.is_num:
                result[key] = _value.Value(val.num * 2)
            else:
                result[key] = val
        return _value.Value(result)
    return in_value


def _upper_func(in_value: _value.Value, arg_value: _value.Value) -> _value.Value:
    """Upper function - converts string to uppercase."""
    if in_value.is_str:
        return _value.Value(in_value.str.upper())
    return in_value


def _lower_func(in_value: _value.Value, arg_value: _value.Value) -> _value.Value:
    """Lower function - converts string to lowercase."""
    if in_value.is_str:
        return _value.Value(in_value.str.lower())
    return in_value


def _is_a_func(in_value: _value.Value, arg_value: _value.Value) -> _value.Value:
    """Check if input tag is-a (child of or equal to) the parent tag in args.
    
    Args:
        in_value: Tag to check (child)
        arg_value: Struct with 'parent' field containing the parent tag
        
    Returns:
        #true if child is-a parent (including if equal), #false otherwise
        
    Examples:
        [#timeout.error.status |is-a parent=#status]  ; Returns #true
        [#active.status |is-a parent=#status]          ; Returns #true
        [#status |is-a parent=#status]                 ; Returns #true (equal)
        [#red |is-a parent=#status]                    ; Returns #false
    """
    # Check if input is a tag
    if not in_value.is_tag:
        return _value.Value(_false_tag)
    
    # Extract parent tag from arguments
    if not arg_value.is_struct or not arg_value.struct:
        return _value.Value(_false_tag)
    
    # Find the 'parent' field in the struct
    parent_value = None
    for key, val in arg_value.struct.items():
        if isinstance(key, _value.Value) and key.is_str and key.str == "parent":
            parent_value = val
            break
    
    if parent_value is None or not parent_value.is_tag:
        return _value.Value(_false_tag)
    
    # Use the existing is_parent_or_equal function
    result = _tag.is_parent_or_equal(parent_value.tag, in_value.tag)
    
    # result >= 0 means parent is an ancestor or equal
    if result >= 0:
        return _value.Value(_true_tag)
    else:
        return _value.Value(_false_tag)


# Registry of builtin functions
BUILTIN_FUNCS: dict[str, _func.PythonFuncImpl] = {
    "print": _func.PythonFuncImpl(_print_func, "print"),
    "double": _func.PythonFuncImpl(_double_func, "double"),
    "upper": _func.PythonFuncImpl(_upper_func, "upper"),
    "lower": _func.PythonFuncImpl(_lower_func, "lower"),
    "is-a": _func.PythonFuncImpl(_is_a_func, "is-a"),
}

# Registry of builtin tag values
# These are the actual runtime values that get added to module namespaces
BUILTIN_TAGS: dict[str, _value.Value] = {
    "true": _value.Value(_true_tag),
    "false": _value.Value(_false_tag),
    "skip": _value.Value(_skip_tag),
    "break": _value.Value(_break_tag),
    "fail": _value.Value(_fail_tag),
    "fail.syntax": _value.Value(_fail_syntax_tag),
    "fail.missing": _value.Value(_fail_missing_tag),
    "fail.type": _value.Value(_fail_type_tag),
    "fail.value": _value.Value(_fail_value_tag),
    "fail.index": _value.Value(_fail_index_tag),
    "fail.runtime": _value.Value(_fail_runtime_tag),
    "fail.placeholder": _value.Value(_fail_runtime_tag),
}


# Shared builtin module instance
_builtin_module = None


def python_exception_to_comp_failure(exc: Exception) -> _value.Value:
    """Convert a Python exception to a Comp failure structure.
    
    Creates a struct with a failure tag as the first unnamed field, followed by
    error details in named fields.
    
    Args:
        exc: Python exception to convert
        
    Returns:
        Value with structure: {#fail.type message ~str type ~str}
        The failure tag is stored as an unnamed field, with message and type as named fields.
        
    Examples:
        ValueError("bad value") -> {#fail.value message="bad value" type="ValueError"}
        TypeError("wrong type") -> {#fail.type message="wrong type" type="TypeError"}
        IndexError("out of bounds") -> {#fail.index message="out of bounds" type="IndexError"}
    """
    # Determine the appropriate failure tag based on exception type
    if isinstance(exc, (TypeError, AttributeError)):
        fail_tag = _fail_type_tag
    elif isinstance(exc, (ValueError, KeyError)):
        fail_tag = _fail_value_tag
    elif isinstance(exc, (IndexError)):
        fail_tag = _fail_index_tag
    elif isinstance(exc, NotImplementedError):
        fail_tag = _fail_runtime_tag
    else:
        # Default to generic #fail.runtime for unknown exception types
        fail_tag = _fail_runtime_tag
    
    # Build the failure structure with the tag as the first unnamed field
    failure_struct = {
        _value.Unnamed(): fail_tag,
        "message": str(exc),
        "type": type(exc).__name__,
    }
    
    # Add traceback details if available (optional, commented out for now to keep structs simpler)
    # tb_lines = traceback.format_exception(type(exc), exc, exc.__traceback__)
    # if tb_lines:
    #     failure_struct[_value.Value("traceback")] = _value.Value("".join(tb_lines))
    
    failure_value = _value.Value(failure_struct)
    return failure_value


def get_builtin_module() -> _mod.Module:
    """Get or create the shared builtin module.

    This module contains all builtin tags and functions. All user modules
    should reference this single instance to ensure singleton tag behavior.
    """
    global _builtin_module

    if _builtin_module is None:
        _builtin_module = _mod.Module("builtin")

        # Add builtin tags
        for name, tag_value in BUILTIN_TAGS.items():
            # Split dotted names into identifier list (e.g., "fail.syntax" -> ["fail", "syntax"])
            identifier = name.split(".")
            tagdef = _tag.TagDef(identifier=identifier, namespace="builtin")
            tagdef.value = tag_value
            # CRITICAL: Override the tag_value created in TagDef.__init__ with our singleton
            # This ensures identity checks (value.tag is builtin.true) work correctly
            # The tag_value in BUILTIN_TAGS is a Value wrapping a TagValue
            if tag_value.is_tag:
                tagdef.tag_value = tag_value.tag  # type: ignore[misc]
            _builtin_module.tags[name] = tagdef

        # Add builtin functions
        for name, python_impl in BUILTIN_FUNCS.items():
            funcdef = _func.FuncDef(identifier=[name])
            funcdef.implementations.append(python_impl)
            _builtin_module.funcs[name] = funcdef

    return _builtin_module
