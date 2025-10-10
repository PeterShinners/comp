"""Runtime values for the generator-based engine."""

from typing import Any


class Tag:
    """A tag value (like #true, #false, #fail, etc)."""

    def __init__(self, name: str):
        self.name = name

    def __repr__(self):
        return f"#{self.name}"

    def __eq__(self, other):
        return isinstance(other, Tag) and self.name == other.name

    def __hash__(self):
        return hash(self.name)


class Value:
    """Runtime value wrapper.

    Can hold Python primitives (int, float, str) or Comp values (Tag, dict).
    This is a simplified version for the new engine. Uses .data for the
    underlying value, and provides .struct as an alias when it's a dict.
    """

    def __init__(self, data: Any, tag: Tag | None = None):
        """Create a value.

        Args:
            data: The underlying data (int, float, str, dict, list, etc)
            tag: Optional tag for this value
        """
        self.data = data
        self.tag = tag

    @property
    def is_number(self) -> bool:
        return isinstance(self.data, (int, float))

    @property
    def is_string(self) -> bool:
        return isinstance(self.data, str)

    @property
    def is_struct(self) -> bool:
        return isinstance(self.data, dict)

    @property
    def is_tag(self) -> bool:
        return isinstance(self.data, Tag)

    @property
    def struct(self) -> dict | None:
        """Alias for .data when it's a dict (for compatibility with AST nodes)."""
        return self.data if isinstance(self.data, dict) else None

    def __repr__(self):
        if self.tag:
            return f"Value({self.data!r}, tag={self.tag})"
        return f"Value({self.data!r})"

    def __eq__(self, other):
        if not isinstance(other, Value):
            return False
        return self.data == other.data and self.tag == other.tag

    def __hash__(self):
        """Make Value hashable so it can be used as dict keys."""
        if isinstance(self.data, dict):
            # Dicts aren't hashable, use tuple of items
            return hash((tuple(sorted(self.data.items())), self.tag))
        return hash((self.data, self.tag))


class Unnamed:
    """Marker for unnamed/positional fields in structures.

    Each instance has unique identity - unnamed fields are distinguishable
    by their position, not their key. This allows multiple unnamed fields
    in a struct without key conflicts.

    Comparison always returns False - unnamed fields are never "equal"
    as keys, they're distinguished by position/identity.
    """
    __slots__ = ()

    def __repr__(self):
        return "???"

    def __hash__(self):
        """Use object identity for hashing - each instance is unique."""
        return id(self)

    def __eq__(self, other):
        """Unnamed keys are never equal - they're distinguished by identity."""
        return False


# Builtin tags
TRUE = Tag("true")
FALSE = Tag("false")
FAIL = Tag("fail")
FAIL_TYPE = Tag("fail.type")
FAIL_DIV_ZERO = Tag("fail.div_zero")
