"""Runtime values for the generator-based engine."""

__all__ = ["Value", "fail", "Unnamed", "ChainedScope"]

import decimal

import comp

from . import _entity


class Value(_entity.Entity):
    """Runtime value wrapper.

    Can hold Python primitives (int, float, str) or Comp values (comp.TagRef, dict).
    This is a simplified version for the new engine. Uses .data for the
    underlying value, and provides .struct as an alias when it's a dict.

    Inherits from Entity, making it passable through scopes and returnable
    from evaluate() methods.
    """

    def __init__(self, data):
        """Create a value from Python types or Comp values.

        Args:
            data: The underlying data. Can be:
                - Value (copied)
                - None (empty struct)
                - bool (converted to TRUE/FALSE tags)
                - int/float (converted to Decimal)
                - Decimal (stored directly)
                - str (stored directly)
                - comp.TagRef (stored directly)
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
            self.data = comp.builtin.TRUE if data else comp.builtin.FALSE
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

        # Handle comp.TagRef
        if isinstance(data, comp.TagRef):
            self.data = data
            return

        # Handle Block and RawBlock (can be wrapped in Value)
        from . import _function
        if isinstance(data, (_function.Block, _function.RawBlock)):
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
        return isinstance(self.data, comp.TagRef)

    @property
    def is_block(self) -> bool:
        """Check if this Value wraps a Block or RawBlock."""
        return isinstance(self.data, (comp.Block, comp.RawBlock))

    @property
    def is_fail(self):
        """Check if a value is a fail value."""
        if not self.is_struct:
            return False

        # Look for #fail tag or any child of #fail in unnamed fields
        for val in self.data.values():
            if val.is_tag:
                name = val.data.full_name
                if name == "fail" or name.startswith("fail."):
                    return True
        return False

    @property
    def struct(self) -> dict | None:
        """Alias for .data when it's a dict (for compatibility with AST nodes)."""
        return self.data if isinstance(self.data, dict) else None

    def as_scalar(self):
        """Return value as a scalar value or itself.
        
        Unwraps single-element structs (named or unnamed).
        """
        if self.is_struct and isinstance(self.data, dict):
            if len(self.data) == 1:
                value = list(self.data.values())[0]
                if value.is_number or value.is_string or value.is_tag or value.is_block:
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
        if isinstance(self.data, comp.TagRef):
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
            - bool for #true/#false tags
            - comp.TagRef for other tags
            - dict for structures (with recursively converted keys/values)
        """
        if isinstance(self.data, comp.TagRef):
            # Convert #true and #false to Python booleans
            if self.data.full_name == "true":
                return True
            elif self.data.full_name == "false":
                return False
            # Other tags remain as TagRef
            return self.data
        if isinstance(self.data, (decimal.Decimal, str)):
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


def fail(message):
    """Create a failure structure with the given message.

    The structure has the #fail tag as an unnamed field, plus named fields
    for type and message. This allows morphing against #fail to detect failures.
    """
    # Import here to avoid circular dependency
    from .builtin import get_builtin_module

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
        Unnamed(): Value(comp.TagRef(fail_tag_def)),  # Tag as unnamed field for morphing
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

    def __init__(self, *scopes):
        """Create a chained scope from multiple Value structs.

        Args:
            *scopes: Value objects to chain. Earlier scopes have priority.
        """
        self.scopes = scopes

    def lookup_field(self, field_key):
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
