"""Runtime values for the generator-based engine."""

__all__ = ["TagRef", "Value", "fail", "Unnamed", "ChainedScope", "TRUE", "FALSE", "FAIL", "FAIL_TYPE", "FAIL_DIV_ZERO"]

import decimal

from ._entity import Entity


class TagRef:
    """A tag reference value that points to a TagDefinition.

    TagRefs must be created from a TagDefinition - they are runtime references
    to tags defined in modules. This ensures all tags have proper definitions
    and are properly scoped.

    Attributes:
        tag_def: Reference to the TagDefinition
    """

    def __init__(self, tag_def):
        """Create a tag reference from a TagDefinition.

        Args:
            tag_def: A TagDefinition object from a module
        """
        self.tag_def = tag_def

    @property
    def full_name(self) -> str:
        """Get the full hierarchical name (e.g., 'fail.syntax')."""
        return self.tag_def.full_name

    @property
    def value(self):
        """Get the associated value from the tag definition (if any)."""
        return self.tag_def.value

    def __repr__(self):
        return f"#{self.full_name}"

    def __eq__(self, other):
        if not isinstance(other, TagRef):
            return False
        # Compare by full name for identity
        return self.full_name == other.full_name

    def __hash__(self):
        return hash(self.full_name)


class Value(Entity):
    """Runtime value wrapper.

    Can hold Python primitives (int, float, str) or Comp values (TagRef, dict).
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
                - TagRef (stored directly)
                - Block/RawBlock (stored directly)
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

        # Handle TagRef
        if isinstance(data, TagRef):
            self.data = data
            return

        # Handle Block and RawBlock (can be wrapped in Value)
        from . import _module
        if isinstance(data, (_module.Block, _module.RawBlock)):
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
        return isinstance(self.data, TagRef)

    @property
    def is_block(self) -> bool:
        """Check if this Value wraps a Block or RawBlock."""
        # Import here to avoid circular dependency
        from . import _module
        return isinstance(self.data, (_module.Block, _module.RawBlock))

    @property
    def struct(self) -> dict | None:
        """Alias for .data when it's a dict (for compatibility with AST nodes)."""
        return self.data if isinstance(self.data, dict) else None

    def as_scalar(self):
        """Return value as a scalar value or itself."""
        if self.is_struct and isinstance(self.data, dict):
            if len(self.data) == 1:
                value = list(self.data.values())[0]
                if value.is_number or value.is_string or value.is_tag:
                    return value
            # By returning self we are still a struct, which users who use this will ignore
            return self
        return self

    def as_struct(self):
        """Wrap scalar values into single field structure."""
        if self.is_struct:
            return self
        return Value({Unnamed(): self})

    def unparse(self) -> str:
        """Convert value back to a source-like representation.

        Similar to AST node unparse() methods, this produces a string that
        represents the value in a human-readable form. For simple values
        (numbers, strings, tags), returns the data. For structs with a single
        unnamed field, extracts that field's representation.

        Returns:
            String representation suitable for display
        """
        if self.is_number:
            return str(self.data)
        if self.is_string:
            return repr(self.data).replace('"', '\\"').replace("'", '"')
        if self.is_tag:
            return f"#{self.data.full_name}"
        if self.is_struct:
            fields = []
            for k, v in self.data.items():
                if isinstance(k, Unnamed):
                    fields.append(v.unparse())
                else:
                    key = k.unparse()[1:-1]
                    if not key.isidentifier():
                        key = "'{key}'"
                    fields.append(f"{key}={v.unparse()}")
            return "{" + " ".join(fields) + "}"

        # Return the data, converting tags and decimals to strings
        if isinstance(self.data, TagRef):
            return str(self.data)
        if isinstance(self.data, decimal.Decimal):
            return str(self.data)
        if isinstance(self.data, str):
            return self.data
        if isinstance(self.data, dict):
            # For complex structs, return the full representation
            return str(self.data)
        return str(self.data)

    def to_python(self):
        """Convert this value to a Python equivalent.

        Returns:
            - Decimal for numbers
            - str for strings
            - TagRef for tags
            - dict for structures (with recursively converted keys/values)
        """
        if isinstance(self.data, (decimal.Decimal, str, TagRef)):
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
    # Import here to avoid circular dependency
    from ._builtin import get_builtin_module

    # Get the #fail tag from builtin module
    builtin = get_builtin_module()
    try:
        fail_tag_def = builtin.lookup_tag(["fail"])
    except ValueError as e:
        # This should never happen - builtin module must have #fail tag
        raise RuntimeError(f"Critical error: builtin #fail tag not found: {e}") from e

    # Create Value directly without going through constructor conversion
    result = Value.__new__(Value)
    result.data = {
        Unnamed(): Value(TagRef(fail_tag_def)),  # Tag as unnamed field for morphing
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


# Builtin tag constants - initialized on first import
# These are created by looking up tag definitions from the builtin module
def _init_builtin_tags():
    """Initialize builtin tag constants from the builtin module."""
    from ._builtin import get_builtin_module
    builtin = get_builtin_module()

    try:
        return {
            'TRUE': TagRef(builtin.lookup_tag(["true"])),
            'FALSE': TagRef(builtin.lookup_tag(["false"])),
            'FAIL': TagRef(builtin.lookup_tag(["fail"])),
            'FAIL_TYPE': TagRef(builtin.lookup_tag(["type", "fail"])),
            'FAIL_DIV_ZERO': TagRef(builtin.lookup_tag(["div_zero", "fail"])),
        }
    except ValueError as e:
        # This should never happen - builtin module must have these tags
        raise RuntimeError(f"Critical error: builtin tags not properly initialized: {e}") from e

# Initialize on module load
_builtin_tags = _init_builtin_tags()
TRUE = _builtin_tags['TRUE']
FALSE = _builtin_tags['FALSE']
FAIL = _builtin_tags['FAIL']
FAIL_TYPE = _builtin_tags['FAIL_TYPE']
FAIL_DIV_ZERO = _builtin_tags['FAIL_DIV_ZERO']
