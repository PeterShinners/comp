"""Rutnime value type for Comp."""


__all__ = ["Value"]

import decimal
from typing import Any

from . import _builtin, _struct, _tag


class Value:
    """Runtime value in Comp."""
    __slots__ = ("num", "str", "tag", "struct")

    def __init__(self, value: object):
        """Create a value with the given python (with some best effort)."""
        self.num: decimal.Decimal | None = None
        self.str: str | None = None
        self.tag: _tag.Tag | None = None
        self.struct: dict[Value|_struct.Unnamed, Value] | None = None

        if isinstance(value, Value):
            self.num = value.num
            self.str = value.str
            self.tag = value.tag
            self.struct = value.struct  # not copying this
            return

        if value is None:
            value = {}
        elif isinstance(value, bool):
            value = _builtin.true if value else _builtin.false
        elif isinstance(value, int):
            value = decimal.Decimal(value)
        elif isinstance(value, float):
            value = decimal.Decimal(str(value))  # not an ideal conversion

        if isinstance(value, decimal.Decimal):
            self.num = value
        elif isinstance(value, str):
            self.str = value
        elif isinstance(value, _tag.Tag):
            self.tag = value
        elif isinstance(value, dict):
            self.struct = {Value(k): Value(v) for k, v in value.items()}
        elif isinstance(value, (list, tuple)):
            self.struct = {_struct.Unnamed(): Value(v) for v in value}
        else:
            raise ValueError(f"Cannot convert Python {type(value)} to Comp Value")

    @property
    def is_num(self) -> bool:
        """Check if this is a number."""
        return self.num is not None
    @property
    def is_str(self) -> bool:
        """Check if this is a string."""
        return self.str is not None
    @property
    def is_tag(self) -> bool:
        """Check if this is a tag."""
        return self.tag is not None
    @property
    def is_struct(self) -> bool:
        """Check if this is a structure."""
        return self.struct is not None

    def to_python(self) -> Any:
        """Convert this value to a Python equivalent."""
        if self.num is not None:
            return self.num
        if self.str is not None:
            return self.str
        if self.tag is not None:
            return self.tag
        return self.struct

    def __repr__(self) -> str:
        if self.num is not None:
            return str(self.num)
        if self.str is not None:
            return repr(self.str).replace('"', '\\"').replace("'", '"')
        if self.tag is not None:
            return repr(self.tag)
        fields = []
        for key, val in self.struct.items():
            if isinstance(key, _struct.Unnamed):
                fields.append(repr(val))
            elif key.is_str and key.str.isidentifier():
                fields.append(f"{key.str}={val!r}")
            else:
                fields.append(f"{key!r}={val!r}")
        return f"{{{' '.join(fields)}}}"

    def __eq__(self, other: Any) -> bool:
        """Value equality."""
        if not isinstance(other, Value):
            return False
        return (self.num == other.num
                and self.str == other.str
                and self.tag == other.tag
                and self.struct == other.struct)

    def __hash__(self) -> int:
        """Hash for use in sets/dicts."""
        if self.num is not None:
            return hash(self.num)
        if self.str is not None:
            return hash(self.str)
        if self.tag is not None:
            return hash(self.tag)
        return hash(tuple(self.struct.items()) if self.struct else ())
