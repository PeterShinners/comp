"""Builtin constants used for Comp runtime."""

__all__ = []

from . import _tag, _value

true = _tag.Tag(("true",), "builtin")
false = _tag.Tag(("false",), "builtin")

skip = _tag.Tag(("skip",), "builtin")
break_ = _tag.Tag(("break",), "builtin")

nil = _value.Value({})

