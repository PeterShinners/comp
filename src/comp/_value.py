"""Runtime values for the generator-based engine."""

__all__ = ["Tag", "Value", "fail", "Unnamed", "ChainedScope", "TRUE", "FALSE", "FAIL", "FAIL_TYPE", "FAIL_DIV_ZERO"]

import decimal

from ._entity import Entity


class Tag:
    """A tag value that references a TagDefinition.

    Tags carry a reference to their definition, allowing access to:
    - Full hierarchical path
    - Associated value (if any)
    - Module context

    For builtin tags (#true, #false, #fail), a simple name string is sufficient
    since they have no associated values and are globally known.

    Attributes:
        tag_def: Reference to the TagDefinition (if available)
        name: Simple name string (for builtins or when definition unavailable)
    """

    def __init__(self, name_or_def):
        """Create a tag from either a name string or TagDefinition.

        Args:
            name_or_def: Either a string name (for builtins) or a TagDefinition object
        """
        if isinstance(name_or_def, str):
            # Simple name-based tag (for builtins)
            self.tag_def = None
            self.name = name_or_def
        else:
            # Tag with full definition
            self.tag_def = name_or_def
            self.name = name_or_def.name if hasattr(name_or_def, 'name') else str(name_or_def)

    @property
    def full_name(self) -> str:
        """Get the full hierarchical name (e.g., 'fail.syntax')."""
        if self.tag_def and hasattr(self.tag_def, 'full_name'):
            return self.tag_def.full_name
        return self.name

    @property
    def value(self):
        """Get the associated value from the tag definition (if any)."""
        if self.tag_def and hasattr(self.tag_def, 'value'):
            return self.tag_def.value
        return None

    def __repr__(self):
        return f"#{self.full_name}"

    def __eq__(self, other):
        if not isinstance(other, Tag):
            return False
        # Compare by full name for identity
        return self.full_name == other.full_name

    def __hash__(self):
        return hash(self.full_name)


class Value(Entity):
    """Runtime value wrapper.

    Can hold Python primitives (int, float, str) or Comp values (Tag, dict).
    This is a simplified version for the new engine. Uses .data for the
    underlying value, and provides .struct as an alias when it's a dict.

    Inherits from Entity, making it passable through scopes and returnable
    from evaluate() methods.
    """

    def __init__(self, data: object):
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
        """
        # Handle Value copying
        if isinstance(data, Value):
            self.data = data.data
            return

        # Handle None -> empty struct
        if data is None:
            self.data = {}
            return

        # Handle bool -> Tag conversion
        if isinstance(data, bool):
            self.data = TRUE if data else FALSE
            return

        # Handle numeric types -> Decimal
        if isinstance(data, int):
            self.data = decimal.Decimal(data)
            return
        if isinstance(data, float):
            self.data = decimal.Decimal(str(data))  # Convert via string to avoid precision issues
            return
        if isinstance(data, decimal.Decimal):
            self.data = data
            return

        # Handle string
        if isinstance(data, str):
            self.data = data
            return

        # Handle Tag
        if isinstance(data, Tag):
            self.data = data
            return

        # Handle dict -> struct (recursively convert keys and values)
        if isinstance(data, dict):
            self.data = {
                k if isinstance(k, Unnamed) else Value(k): Value(v)
                for k, v in data.items()
            }
            return

        # Handle list/tuple -> unnamed struct fields
        if isinstance(data, (list, tuple)):
            self.data = {Unnamed(): Value(v) for v in data}
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
        if self.is_struct and isinstance(self.data, dict):
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
        return f"Value({self.data!r})"

    def __eq__(self, other):
        if not isinstance(other, Value):
            return False
        return self.data == other.data

    def __hash__(self):
        """Make Value hashable so it can be used as dict keys."""
        if isinstance(self.data, dict):
            # Dicts aren't hashable, use tuple of items
            return hash(tuple(sorted(self.data.items())))
        return hash(self.data)


def fail(message: str) -> Value:
    """Create a failure structure with the given message.

    The structure has the #fail tag as an unnamed field, plus named fields
    for type and message. This allows morphing against #fail to detect failures.
    """
    # Create Value directly without going through constructor conversion
    result = Value.__new__(Value)
    result.data = {
        Unnamed(): Value(FAIL),  # Tag as unnamed field for morphing
        Value('type'): Value('fail'),
        Value('message'): Value(message)
    }
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


class ChainedScope:
    """A scope that chains multiple Value structs for field lookup.

    When looking up a field, tries each scope in order and returns the first match.
    This is used for the 'unnamed' scope to chain $out (accumulator) with $in.
    """

    def __init__(self, *scopes: Value):
        """Create a chained scope from multiple Value structs.

        Args:
            *scopes: Value objects to chain. Earlier scopes have priority.
        """
        self.scopes = scopes

    def lookup_field(self, field_key: Value) -> Value | None:
        """Look up a field in the chained scopes.

        Args:
            field_key: The field key to look up (as a Value)

        Returns:
            The value if found in any scope, None otherwise
        """
        for scope in self.scopes:
            if scope is not None and scope.is_struct:
                struct = scope.struct
                if struct is not None and field_key in struct:
                    return struct[field_key]
        return None


# Builtin tags
TRUE = Tag("true")
FALSE = Tag("false")
FAIL = Tag("fail")
FAIL_TYPE = Tag("fail.type")
FAIL_DIV_ZERO = Tag("fail.div_zero")
