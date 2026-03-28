"""Runtime values for the generator-based engine."""

__all__ = ["Value", "Unnamed", "materialize_handles"]

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
        stash: Module-private data storage dict
        handles: Three-state handle tracker.
            None      -- definitely contains no handles (fast path)
            True      -- contains handles, frozenset not yet materialised
            frozenset -- materialised set of HandleInstance objects, never empty
    """

    __slots__ = ("data", "cop", "stash", "handles", "unit")
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

        # Unit tag attached to this value (Tag | None)
        # e.g. measure.length.inch for 12[inch]
        self.unit = None

        # Module-private data storage
        # Maps module_id -> Value (structure containing private data) Used by
        # the & syntax for module-scoped private data
        self.stash = None
        # Three-state handle tracker (see class docstring for states).
        self.handles = None

        # Data may not be valid for a Comp Value here, but accept it as-is in
        # the name of efficiency. The `validate_value` method can be used for
        # stricter checking.

        if isinstance(data, comp.HandleInstance):
            # The value IS a handle — materialise immediately, never deferred.
            self.handles = frozenset([data])
            # The handle's tag identifies its type.  Expose it as value.unit so
            # ~handle[file] constraints work via the existing _unit_match_score
            # path, exactly like ~num[time.second] works for numeric units.
            self.unit = data.tag
        elif isinstance(data, dict):
            # Cheap bloom check: any field containing handles taints this struct.
            if any(v.handles for v in data.values()):
                self.handles = True

        self.data = data

        # Late initialization of important maps for fetching types
        if Value._shapemap is None:
            Value._shapemap = {
                tuple: comp.shape_num,
                str: comp.shape_text,
                dict: comp.shape_struct,
                comp.Tag: comp.shape_tag,
                comp.Callable: comp.shape_block,
                comp.HandleInstance: comp.shape_handle,
                comp.Shape: comp.shape_shape,
                comp.ShapeUnion: comp.shape_union,
            }
            Value._shapetypes = (comp.RawTag,)

    @property
    def shape(self):
        """(Shape | Tag) Shape reference for this value's data type."""
        shape = Value._shapemap.get(type(self.data))  # type: ignore
        if shape is None and isinstance(self.data, Value._shapetypes):  # type: ignore
            shape = self.data  # tag
        return shape

    def with_unit(self, unit):
        """Return a new Value identical to self but with a different unit.

        Args:
            unit: (Tag | None) The unit to attach, or None to strip unit

        Returns:
            (Value) New value with the given unit
        """
        new_val = Value.__new__(Value)
        new_val.data = self.data
        new_val.cop = self.cop
        new_val.stash = self.stash
        new_val.handles = self.handles
        new_val.unit = unit
        return new_val

    def format(self):
        """Convert value to Comp literal expression.

        Returns:
            (str) String representation suitable for display
        """
        # Check if we have a finalized constant in self.cop

        shape = self.shape
        if shape is comp.shape_num:
            base = comp._num.num_format(self.data)
        elif shape is comp.shape_text:
            value = self.data.replace('"', '\\"')
            escaped = value.replace("\n", "\\n")
            base = (
                f'"""{escaped}"""' if "\n" in value else f'"{value}"'
            )
        elif self.data is comp.tag_nil:
            return "nil"
        elif self.data is comp.tag_true:
            return "true"
        elif self.data is comp.tag_false:
            return "false"
        elif isinstance(self.data, comp.Tag):
            return f"{self.data.qualified}"
        elif isinstance(self.data, comp.RawTag):
            return f"({self.data.qualified})"
        elif isinstance(self.data, comp.Callable):
            return self.data.format()
        elif isinstance(self.data, comp.HandleInstance):
            qualifier = self.data.tag.qualified if self.data.tag else "unknown"
            return f"handle#{qualifier}"
        elif isinstance(self.data, comp.Shape):
            return self.data.format()
        elif isinstance(self.data, comp.ShapeUnion):
            return self.data.format()
        elif shape is comp.shape_struct:
            fields = []
            for k, v in self.data.items():
                if isinstance(k, Unnamed):
                    fields.append(v.format())
                elif isinstance(k, Value):
                    if k.shape == comp.shape_text:
                        key = k.format()[1:-1]
                        # Abbreviate nested struct "cop" fields to avoid gnarly output
                        if key == "cop" and v.shape is comp.shape_struct:
                            fields.append("cop=...")
                            continue
                        # Check if key is a valid Comp identifier (TOKEN pattern: /[^\W\d][\w-]*[?]?/)
                        # Must start with letter/underscore, contain only alphanumeric/underscore/hyphen, optional trailing ?
                        val = v.format()
                        if len(val) > 20:
                            val = val[:17] + "..."
                        if re.match(r"^[^\W\d][\w-]*\??$", key):
                            fields.append(f"{key}={val}")
                        else:
                            # Need to quote the key
                            fields.append(f'"{key}"={val}')
                    else:
                        fields.append(f"'{k.format()}'={val}")
            return "{" + " ".join(fields) + "}"
        else:
            base = str(self.data)

        # Append unit suffix for num and text values
        if self.unit is not None:
            return f"{base}#{self.unit.qualified}"
        return base

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
        if isinstance(self.data, tuple):
            n, d, _ = self.data
            if d == 1:
                return n
            if rich_numbers:
                return self.data
            return n / d

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
            return cls(comp.tag_true)
        if value is False:
            return cls(comp.tag_false)

        if isinstance(value, int):
            return cls((value, 1, 0))
        if isinstance(value, float):
            return cls(comp._num.num_from_decimal_str(str(value)))
        if isinstance(value, decimal.Decimal):
            return cls(comp._num.num_from_decimal_str(str(value)))
        if isinstance(value, fractions.Fraction):
            import math as _math
            g = _math.gcd(abs(value.numerator), value.denominator)
            return cls((value.numerator // g, value.denominator // g, 0))

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

        # Allow Tag, RawTag, Shape, ShapeUnion, Callable objects to be wrapped in Values
        if isinstance(value, (comp.Tag, comp.RawTag, comp.Shape, comp.ShapeUnion, comp.Callable)):
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
        if self.unit is not other.unit:
            return False
        return comp._ops._equal(self, other)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __lt__(self, other):
        if not isinstance(other, Value):
            return NotImplemented
        return comp._ops._compare(self, other) < 0

    def __le__(self, other):
        if not isinstance(other, Value):
            return NotImplemented
        return comp._ops._compare(self, other) <= 0

    def __gt__(self, other):
        if not isinstance(other, Value):
            return NotImplemented
        return comp._ops._compare(self, other) > 0

    def __ge__(self, other):
        if not isinstance(other, Value):
            return NotImplemented
        return comp._ops._compare(self, other) >= 0

    def __hash__(self):
        """Make Value hashable so it can be used as dict keys."""
        if isinstance(self.data, dict):
            # Dicts aren't hashable, use tuple of items
            data_hash = hash(tuple(sorted(self.data.items())))
        else:
            data_hash = hash(self.data)
        return hash((data_hash, self.unit))


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

#     result.stash = {}
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
