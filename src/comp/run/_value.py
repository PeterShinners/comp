"""Runtime value for Comp."""

__all__ = ["Value", "Unnamed"]

import decimal

from . import _tag


class Value:
    """Runtime value in Comp."""
    __slots__ = ("num", "str", "tag", "struct")

    def __init__(self, value: object):
        """Create a value with the given python (with some best effort)."""
        self.num = None
        self.str = None
        self.tag = None
        self.struct = None

        if isinstance(value, Value):
            self.num = value.num
            self.str = value.str
            self.tag = value.tag
            self.struct = value.struct  # not copying this
            return

        if value is None:
            value = {}
        elif isinstance(value, bool):
            from . import builtin
            value = builtin.true if value else builtin.false
        elif isinstance(value, int):
            value = decimal.Decimal(value)
        elif isinstance(value, float):
            value = decimal.Decimal(str(value))  # not an ideal conversion

        if isinstance(value, decimal.Decimal):
            self.num = value
        elif isinstance(value, str):
            self.str = value
        elif isinstance(value, _tag.TagValue):
            self.tag = value
        elif isinstance(value, dict):
            self.struct = {k if isinstance(k, Unnamed) else Value(k): Value(v) for k, v in value.items()}
        elif isinstance(value, (list, tuple)):
            self.struct = {Unnamed(): Value(v) for v in value}
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

    def to_python(self):
        """Convert this value to a Python equivalent."""
        if self.num is not None:
            return self.num
        if self.str is not None:
            return self.str
        if self.tag is not None:
            return self.tag
        if self.struct is not None:
            # Recursively convert struct fields
            result = {}
            for key, val in self.struct.items():
                if isinstance(key, Unnamed):
                    # For unnamed keys, use numeric indices
                    result[len(result)] = val.to_python()
                else:
                    # Convert Value keys to Python
                    result[key.to_python()] = val.to_python()
            return result
        return None

    def __repr__(self):
        if self.num is not None:
            return str(self.num)
        if self.str is not None:
            return repr(self.str).replace('"', '\\"').replace("'", '"')
        if self.tag is not None:
            return repr(self.tag)
        fields = []
        for key, val in self.struct.items():
            if isinstance(key, Unnamed):
                fields.append(repr(val))
            elif key.is_str and key.str.isidentifier():
                fields.append(f"{key.str}={val!r}")
            else:
                fields.append(f"{key!r}={val!r}")
        return f"{{{' '.join(fields)}}}"

    def __eq__(self, other):
        """Value equality."""
        if not isinstance(other, Value):
            return False
        return (self.num == other.num
                and self.str == other.str
                and self.tag == other.tag
                and self.struct == other.struct)

    def __hash__(self):
        """Hash for use in sets/dicts."""
        if self.num is not None:
            return hash(self.num)
        if self.str is not None:
            return hash(self.str)
        if self.tag is not None:
            return hash(self.tag)
        return hash(tuple(self.struct.items()) if self.struct else ())


class Unnamed:
    """Unnamed placeholder for unnamed fields with unique identity"""
    __slots__ = ()

    def __init__(self):
        pass

    def __repr__(self):
        return "???"

    def __hash__(self):
        return id(self)

    def __eq__(self, other):
        return False
