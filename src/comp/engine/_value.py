"""Runtime values for the generator-based engine."""

__all__ = ["Tag", "Value", "fail", "Unnamed", "TRUE", "FALSE", "FAIL", "FAIL_TYPE", "FAIL_DIV_ZERO"]

import decimal

from ._entity import Entity


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


class Value(Entity):
    """Runtime value wrapper.

    Can hold Python primitives (int, float, str) or Comp values (Tag, dict).
    This is a simplified version for the new engine. Uses .data for the
    underlying value, and provides .struct as an alias when it's a dict.

    Inherits from Entity, making it passable through scopes and returnable
    from evaluate() methods.
    """

    def __init__(self, data: object, tag: Tag | None = None):
        """Create a value from Python types or Comp values.

        Args:
            data: The underlying data. Can be:
                - Value (copied)
                - None (empty struct)
                - bool (converted to TRUE/FALSE tags)
                - int/float (converted to Decimal)
                - Decimal (stored directly)
                - str (stored directly)
                - Tag (stored directly)
                - dict (recursively converted)
                - list/tuple (converted to unnamed struct fields)
            tag: Optional side-tag for this value (will be removed in future)
        """
        # Handle Value copying
        if isinstance(data, Value):
            self.data = data.data
            self.tag = data.tag if tag is None else tag
            return

        # Handle None -> empty struct
        if data is None:
            self.data = {}
            self.tag = tag
            return

        # Handle bool -> Tag conversion
        if isinstance(data, bool):
            self.data = TRUE if data else FALSE
            self.tag = tag
            return

        # Handle numeric types -> Decimal
        if isinstance(data, int):
            self.data = decimal.Decimal(data)
            self.tag = tag
            return
        if isinstance(data, float):
            self.data = decimal.Decimal(str(data))  # Convert via string to avoid precision issues
            self.tag = tag
            return
        if isinstance(data, decimal.Decimal):
            self.data = data
            self.tag = tag
            return

        # Handle string
        if isinstance(data, str):
            self.data = data
            self.tag = tag
            return

        # Handle Tag
        if isinstance(data, Tag):
            self.data = data
            self.tag = tag
            return

        # Handle dict -> struct (recursively convert keys and values)
        if isinstance(data, dict):
            self.data = {
                k if isinstance(k, Unnamed) else Value(k): Value(v)
                for k, v in data.items()
            }
            self.tag = tag
            return

        # Handle list/tuple -> unnamed struct fields
        if isinstance(data, (list, tuple)):
            self.data = {Unnamed(): Value(v) for v in data}
            self.tag = tag
            return

        raise ValueError(f"Cannot convert Python {type(data)} to Comp Value")

    @property
    def is_number(self) -> bool:
        return isinstance(self.data, decimal.Decimal)

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

    def as_scalar(self):
        """Return value as a scalar value or itself."""
        if self.is_struct:
            if len(self.data) == 1:
                return next(iter(self.data.values()))
            # By returning self we are still a struct, which users who use this will ignore
            return self
        return self

    def as_struct(self):
        """Wrap scalar values into single field structure."""
        if self.is_struct:
            return self
        return Value({Unnamed(): self})

    def to_python(self):
        """Convert this value to a Python equivalent.

        Returns:
            - Decimal for numbers
            - str for strings
            - Tag for tags
            - dict for structures (with recursively converted keys/values)
        """
        if isinstance(self.data, (decimal.Decimal, str, Tag)):
            return self.data
        if isinstance(self.data, dict):
            # Recursively convert struct fields
            result = {}
            for key, val in self.data.items():
                if isinstance(key, Unnamed):
                    # For unnamed keys, use numeric indices
                    result[len(result)] = val.to_python()
                else:
                    # Convert Value keys to Python
                    result[key.to_python()] = val.to_python()
            return result
        return None

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


def fail(message: str) -> Value:
    """Create a failure structure with the given message."""
    # Create Value directly without going through constructor conversion
    result = Value.__new__(Value)
    result.data = {Value('type'): Value('fail'), Value('message'): Value(message)}
    result.tag = FAIL
    return result


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
        return "_"

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
