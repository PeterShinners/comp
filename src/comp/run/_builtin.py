"""Builtin constants and functions for Comp runtime."""

__all__ = ["BUILTIN_FUNCS", "BUILTIN_TAGS", "get_builtin_module"]

from . import _module, _tag, _value

# Singleton builtin tag instances
# TODO: When implementing comparison operators, these need special handling:
#   - Comparison operators (==, <, etc.) should return these exact Tag instances
#   - Tag equality must be based on identity/definition, not name or identifier
#   - Module namespace resolution needs to return references to these singletons
#   - Each module importing builtins should reference the same Tag instances,
#     not create new ones with the same name
_true_tag = _tag.Tag(["true"], "builtin")
_false_tag = _tag.Tag(["false"], "builtin")
_skip_tag = _tag.Tag(["skip"], "builtin")
_break_tag = _tag.Tag(["break"], "builtin")
_fail_tag = _tag.Tag(["fail"], "builtin")
_fail_syntax_tag = _tag.Tag(["fail", "syntax"], "builtin")
_fail_missing_tag = _tag.Tag(["fail", "missing"], "builtin")

# Expose as backwards-compatible names
true = _true_tag
false = _false_tag
skip = _skip_tag
break_ = _break_tag
fail = _fail_tag
fail_syntax = _fail_syntax_tag
fail_undefined = _fail_missing_tag

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


# Registry of builtin functions
BUILTIN_FUNCS: dict[str, _module.PythonFuncImpl] = {
    "print": _module.PythonFuncImpl(_print_func, "print"),
    "double": _module.PythonFuncImpl(_double_func, "double"),
    "upper": _module.PythonFuncImpl(_upper_func, "upper"),
    "lower": _module.PythonFuncImpl(_lower_func, "lower"),
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
}


# Shared builtin module instance
_builtin_module: _module.Module | None = None


def get_builtin_module() -> _module.Module:
    """Get or create the shared builtin module.

    This module contains all builtin tags and functions. All user modules
    should reference this single instance to ensure singleton tag behavior.
    """
    global _builtin_module

    if _builtin_module is None:
        _builtin_module = _module.Module("builtin")

        # Add builtin tags
        for name, tag_value in BUILTIN_TAGS.items():
            # Split dotted names into identifier list (e.g., "fail.syntax" -> ["fail", "syntax"])
            identifier = name.split(".")
            tag_def = _module.TagDef(identifier=identifier)
            tag_def.value = tag_value
            _builtin_module.tags[name] = tag_def

        # Add builtin functions
        for name, python_impl in BUILTIN_FUNCS.items():
            func_def = _module.FuncDef(identifier=[name])
            func_def.implementations.append(python_impl)
            _builtin_module.funcs[name] = func_def

    return _builtin_module
