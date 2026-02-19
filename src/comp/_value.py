"""Runtime values for the generator-based engine."""

__all__ = ["Value", "Unnamed", "validate", "materialize_handles"]

import copy
import decimal
import fractions
import re

import comp


class Value:
    """Comp runtime value.

    Represents any of the possible data types supported by comp.
    This means numbers, strings, tags, functions, shapes, handles, and more.

    Values have an optional token that is set when the value comes from
    a compiled data source. This is optional, and allows better error
    reporting and tracking.

    Many builtin types like "nil" and "true" in comp are represented as
    tags. Use the `from_python()` and `to_python()` methods to convert between
    more native data types.

    The contents of the value are considered immutable, even when
    represented by structures with dicts.

    ## Examples

    Creating values:
        >>> v = Value.from_python(42)
        >>> v.data
        42
        >>> v = Value.from_python({"name": "Alice"})
        >>> v.data[Value.from_python("name")].data
        'Alice'

    Args:
        data: The underlying data.

    Attributes:
        data: The underlying data (primitives, tags, structs, etc.)
        shape: (ShapeRef) Definition of represented data, or unit for basic types
        cop: Optional parsed cop that created this value (for errors and diags)
        private: Module-private data storage dict
        handles: Three-state handle tracker.
            None      -- definitely contains no handles (fast path)
            True      -- contains handles, frozenset not yet materialised
            frozenset -- materialised set of HandleInstance objects, never empty
    """

    __slots__ = ("data", "cop", "private", "handles", "_guard")
    _shapemap = None
    _shapetypes = None

    def __init__(self, data):
        if isinstance(data, Value):
            # This means values generally shouldn't be copied from other values,
            # instead their references should be shared. Because of this the
            # constructor will error for any code that tries to wrap a value on
            # an existing value.
            raise TypeError(f"Value init called with existing Value {data}")

        # Token used for diagnostics and messages about where value came from
        self.cop = None

        # Module-private data storage
        # Maps module_id -> Value (structure containing private data) Used by
        # the & syntax for module-scoped private data
        self.private = None
        # Three-state handle tracker (see class docstring for states).
        self.handles = None

        # Data may not be valid for a Comp Value here, but accept it as-is in
        # the name of efficiency. The `validate_value` method can be used for
        # stricter checking.

        if isinstance(data, comp.HandleInstance):
            # The value IS a handle — materialise immediately, never deferred.
            self.handles = frozenset([data])
        elif isinstance(data, dict):
            self._guard = iter(data)  # Used for validation
            # Cheap bloom check: any field containing handles taints this struct.
            if any(v.handles for v in data.values()):
                self.handles = True

        self.data = data

        # Late initialization of important maps for fetching types
        if Value._shapemap is None:
            Value._shapemap = {
                fractions.Fraction: comp.shape_num,
                decimal.Decimal: comp.shape_num,
                str: comp.shape_text,
                dict: comp.shape_struct,
                comp.Block: comp.shape_block,
                comp.Shape: comp.shape_shape,
                comp.ShapeUnion: comp.shape_union,
            }
            Value._shapetypes = (comp.Tag, comp.Shape, comp.ShapeUnion)

    @property
    def shape(self):
        """(Shape | Tag) Shape reference for this value's data type."""
        shape = Value._shapemap.get(type(self.data))  # type: ignore
        if shape is None and isinstance(self.data, Value._shapetypes):  # type: ignore
            shape = self.data  # tag
        return shape

    def format(self):
        """Convert value to Comp literal expression.

        Returns:
            (str) String representation suitable for display
        """
        # Check if we have a finalized constant in self.cop

        shape = self.shape
        if shape is comp.shape_num:
            return str(self.data)
        if shape is comp.shape_text:
            value = self.data.replace('"', '\\"')
            escaped = value.replace("\n", "\\n")
            return (
                f'"""{escaped}"""' if "\n" in value else f'"{value}"'
            )
        if shape is comp.tag_nil:
            return "nil"
        if shape is comp.tag_true:
            return "true"
        if shape is comp.tag_false:
            return "false"
        if isinstance(self.data, comp.Tag):
            return f"{self.data.qualified}"
        if isinstance(self.data, comp.Block):
            return self.data.format()
        if isinstance(self.data, comp.HandleInstance):
            return self.data.format()
        if isinstance(self.data, comp.Shape):
            return self.data.format()
        if isinstance(self.data, comp.ShapeUnion):
            return self.data.format()

        if shape is comp.shape_struct:
            fields = []
            for k, v in self.data.items():
                if isinstance(k, Unnamed):
                    fields.append(v.format())
                elif isinstance(k, Value):
                    if k.shape == comp.shape_text:
                        key = k.format()[1:-1]
                        # Check if key is a valid Comp identifier (TOKEN pattern: /[^\W\d][\w-]*[?]?/)
                        # Must start with letter/underscore, contain only alphanumeric/underscore/hyphen, optional trailing ?
                        if re.match(r"^[^\W\d][\w-]*\??$", key):
                            fields.append(f"{key}={v.format()}")
                        else:
                            # Need to quote the key
                            fields.append(f'"{key}"={v.format()}')
                    else:
                        fields.append(f"'{k.format()}'={v.format()}")

            return "{" + " ".join(fields) + "}"

        return str(self.data)

    def as_scalar(self):
        """Unwrap single-element structs to their scalar value.

        If this value is a struct with exactly one field (named or unnamed),
        returns that field's value. Otherwise returns self unchanged.

        This is used by operators to automatically unwrap parenthesized
        expressions like (5+20) which parse as single-field structs.

        Returns:
            (Value) The unwrapped value, or self if not unwrappable
        """
        # Only unwrap struct values
        if not isinstance(self.data, dict):
            return self

        # Must have exactly one field
        if len(self.data) != 1:
            return self

        # Extract the single value
        value = next(iter(self.data.values()))
        return value

    def to_python(self, field=None, rich_numbers=False):
        """Convert this value to a Python equivalent.

        If field is given it will assume this is a struct value and access
        the given field by name (str) or by position (int).

        Args:
            field: (str | int | None) Optional field to access from struct
            rich_numbers: (bool) Allow richer number types like Decimal
        Returns:
            (object) Converted python value

        """
        if field is not None:
            if not isinstance(self.data, dict):
                raise TypeError(f"Cannot access field on non-struct value")
            if isinstance(field, int):
                # Access by position
                for i, (k, v) in enumerate(self.data.items()):
                    if i == field:
                        return v.to_python(rich_numbers=rich_numbers)
                raise IndexError(f"Struct field index {field} out of range")
            else:
                # Access by name
                for k, v in self.data.items():
                    if (
                        isinstance(k, Value)
                        and isinstance(k.data, str)
                        and k.data == field
                    ):
                        return v.to_python(rich_numbers=rich_numbers)
                raise KeyError(f"Struct field '{field}' not found")

        if isinstance(self.data, comp.Tag):
            # Convert #bool.true and #bool.false to Python booleans
            if self.data.qualified == "nil":
                return None
            if self.data.qualified == "bool.true":
                return True
            if self.data.qualified == "bool.false":
                return False
            # Other tags remain as Tag
            return self.data

        if isinstance(self.data, str):
            return self.data
        if isinstance(self.data, (fractions.Fraction, decimal.Decimal)):
            num, denom = self.data.as_integer_ratio()
            if rich_numbers:
                return self.data
            if denom == 1:
                return num
            return float(self.data)

        if isinstance(self.data, dict):
            # Check if all keys are Unnamed - convert to list
            if self.data and all(isinstance(k, Unnamed) for k in self.data):
                return [
                    v.to_python(rich_numbers=rich_numbers) for v in self.data.values()
                ]

            # Mixed or named keys - convert to dict
            result = {}
            for key, val in self.data.items():
                if isinstance(key, Unnamed):
                    val = val.to_python(rich_numbers=rich_numbers)
                    result[len(result)] = val
                else:
                    key = key.to_python(rich_numbers=rich_numbers)
                    val = val.to_python(rich_numbers=rich_numbers)
                    result[key] = val
            return result

        return self.data

    @classmethod
    def from_python(cls, value):
        """Convert Python values into native Comp Values.

        Args:
            value: Python value to convert
        Returns:
            (Value) Comp Value equivalent
        Raises:
            TypeError: If value is already a Value or cannot be converted
        """
        if isinstance(value, Value):
            return value

        if isinstance(value, str):
            if type(value) is not str:
                raise TypeError(
                    f"Cannot convert Python string subtype {type(value).__name__} to Comp Value"
                )
            return cls(value)

        if value is None:
            return cls(comp.tag_nil)
        if value is True:
            return comp.tag_true
        if value is False:
            return comp.tag_false

        if isinstance(value, (int, float)):
            return cls(decimal.Decimal(value))
        if isinstance(value, decimal.Decimal):
            return cls(value)
        if isinstance(value, fractions.Fraction):
            return cls(value)

        if isinstance(value, dict):
            struct = {}
            for k, v in value.items():
                if not isinstance(k, Unnamed):
                    k = cls.from_python(k)
                struct[k] = cls.from_python(v)
            return cls(struct)

        if isinstance(value, (tuple, list)):
            struct = {}
            for item in value:
                struct[Unnamed()] = cls.from_python(item)
            return cls(struct)

        # Allow Tag, Shape, ShapeUnion, Block, DefinitionSet objects to be wrapped in Values
        if isinstance(value, (comp.Tag, comp.Shape, comp.ShapeUnion, comp.Block, comp.DefinitionSet)):
            return cls(value)

        # Allow HandleInstance objects to be wrapped directly
        if isinstance(value, comp.HandleInstance):
            return cls(value)

        raise TypeError(
            f"Cannot convert Python type {type(value).__name__} to Comp Value"
        )

    def field(self, name):
        """Get named field from struct, otherwise TypeError"""
        if self.shape != comp.shape_struct:
            raise TypeError(
                f"Cannot access named field on non-struct value, {self.format()}"
            )
        if not isinstance(name, Value):
            name = Value.from_python(name)
        value = self.data.get(name)
        if value is None:
            raise KeyError(f"Struct field '{name.format()}' not found in value")
        return value

    def positional(self, index):
        """Get positional field from struct value, otherwise TypeError"""
        if self.shape != comp.shape_struct:
            raise TypeError(
                f"Cannot access positional field on non-struct value, {self.format()}"
            )
        if index < 0:
            raise IndexError(f"Negative positional index {index} not supported")
        elif index >= len(self.data):
            raise IndexError(
                f"Positional index {index} out of range for struct with {len(self.data)} fields"
            )
        for i, (k, v) in enumerate(self.data.items()):
            if i == index:
                return v

    def __repr__(self):
        return f"Value({self.format()})"

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


# def fail(message, ast=None, **extra_fields):
#     """Create a failure structure with the given message.

#     The structure has the #fail tag as an unnamed field, plus named fields
#     for type and message. Additional fields can be added via kwargs.
#     This allows morphing against #fail to detect failures.

#     Args:
#         message: The failure message
#         ast: Optional AST node that generated this failure (for error messages and source tracking)
#         **extra_fields: Additional named fields to include in the failure struct
#     """
#     builtin = comp.builtin.get_builtin_module()
#     try:
#         fail_tag_def = builtin.lookup_tag(["fail"])
#     except ValueError as e:
#         # This should never happen - builtin module must have #fail tag
#         raise RuntimeError(f"Critical error: builtin #fail tag not found: {e}") from e

#     # Create Value directly without going through constructor conversion
#     result = Value.__new__(Value)
#     result.data = {
#         Unnamed(): Value(comp.Tag(fail_tag_def)),  # Tag as unnamed field for morphing
#         Value('type'): Value('fail'),
#         Value('message'): Value(message)
#     }

#     # Add any extra fields
#     for key, value in extra_fields.items():
#         result.data[Value(key)] = Value(value)

#     result.private = {}
#     result.ast = ast
#     # Compute handles from field values
#     result.handles = frozenset()  # fail values don't contain handles
#     return result


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


def validate(value):
    """Validate that a Value is in a proper state.

    This isn't regularly done during runtime for efficiency. This can be used
    for testing or analysis tools to detect problems with the runtime.

    This shouldn't ever fail, if it does that means there is a bug in the
    implementation, not any comp code.

    Args:
        value: (Value) object to check
    Raises:
        (Exception) if any type of problem is found
    """
    if not isinstance(value, Value):
        raise TypeError(f"Expected Value, got {type(value).__name__}")

    data = value.data

    if isinstance(data, dict):
        for key, val in data.items():
            if not isinstance(key, (Value, Unnamed)):
                raise TypeError(f"Invalid field name for struct {val!r}")
            if not isinstance(val, Value):
                raise TypeError(f"Invalid field value for struct {key!r}={val!r}")
            # A field with handles requires the parent to also have handles.
            if val.handles and not value.handles:
                raise comp.EvalError(
                    f"Struct field {key!r} has handles but parent value does not"
                )
            # would be nice to pass some context to these, so the error describe
            # the path to where this error happened
            validate(key)
            validate(val)

        try:
            copy.copy(value._guard)
        except RuntimeError:
            # This catches if dictionary changed size after getting created,
            # but doesn't catch if existing values are changed. For now I'll
            # take it as a lightweight check.
            raise comp.EvalError(f"Struct data has been mutated")

    if not isinstance(data, (comp.Tag, str, decimal.Decimal, fractions.Fraction, comp.HandleInstance)):
        raise TypeError(f"Unknown internal type for value: {type(data).__name__}")


def materialize_handles(value):
    """Return the complete frozenset of HandleInstance objects inside value.

    If value.handles is None, returns an empty frozenset without allocation.
    If already a frozenset, returns it directly.
    If True (deferred), walks the value tree once, caches, and returns the set.

    Args:
        value: (Value) Any runtime value

    Returns:
        (frozenset) All HandleInstance objects reachable from value
    """
    if value.handles is None:
        return frozenset()
    if isinstance(value.handles, frozenset):
        return value.handles
    # handles is True — compute and cache
    collected = set()
    _collect_handles_into(value, collected)
    fs = frozenset(collected)
    value.handles = fs
    return fs


def _collect_handles_into(value, result):
    """Recursively collect HandleInstance objects from value into result set."""
    if not value.handles:
        return
    if isinstance(value.data, comp.HandleInstance):
        result.add(value.data)
    elif isinstance(value.data, dict):
        for v in value.data.values():
            if v.handles:
                _collect_handles_into(v, result)
