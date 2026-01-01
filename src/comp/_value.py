"""Runtime values for the generator-based engine."""

__all__ = ["Value", "Unnamed", "validate"]

import copy
import decimal
import fractions
import re

import comp


_emptyset = frozenset()


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

    Using helper methods:
        >>> v = Value.from_python({"x": 1, "y": 2})
        >>> v.has_field("x")
        True
        >>> v.get_field("x").data
        1
        >>> for name, value in v.fields():
        ...     print(f"{name}: {value.data}")
        x: 1
        y: 2

    Type checking:
        >>> v = Value.from_python({"a": 1})
        >>> v.is_struct()
        True
        >>> v.is_tag("nil")
        False

    Args:
        data: The underlying data.

    Attributes:
        data: The underlying data (primitives, tags, structs, etc.)
        shape: (ShapeRef) Definition of represented data, or unit for basic types
        cop: Optional parsed cop that created this value (for errors and diags)
        private: Module-private data storage dict
        handles: Frozenset of HandleInstance objects contained in this value
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
        # Value tracks (recursively) and references used, which are used to when
        # cleaning up stack frames
        self.handles = _emptyset

        # Data may not be valid for a Comp Value here, but accept it as-is in
        # the name of efficiency. The `validate_value` method can be used for
        # stricter checking.

        if isinstance(data, dict):
            self._guard = iter(data)  # Used for validation

        self.data = data

        # Late initialization of important maps for fetching types
        if Value._shapemap is None:
            Value._shapemap = {
                fractions.Fraction: comp.shape_num,
                decimal.Decimal: comp.shape_num,
                str: comp.shape_text,
                dict: comp.shape_struct,
                comp.Func: comp.shape_func,
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
            return (
                f'"""{value.replace("\n", "\\n")}"""' if "\n" in value else f'"{value}"'
            )
        if shape is comp.tag_nil:
            return "nil"
        if shape is comp.tag_true:
            return "true"
        if shape is comp.tag_false:
            return "false"
        if isinstance(self.data, comp.Tag):
            return f"{self.data.qualified}"
        if isinstance(self.data, comp.Func):
            return self.data.format()
        if isinstance(self.data, comp.Shape):
            return self.data.format()
        if isinstance(self.data, comp.ShapeUnion):
            return self.data.format()

        # Handle shape definitions (stored as structs tagged with shape.define)
        if shape is comp.shape_struct and isinstance(self.data, dict):
            first_key = next(iter(self.data.keys()), None)
            if (first_key and isinstance(first_key, Unnamed) and
                hasattr(self.data[first_key], 'data') and
                hasattr(self.data[first_key].data, 'qualified') and
                self.data[first_key].data.qualified == 'shape.define'):
                # This is a shape definition
                return self._format_shape_definition()

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

            return "(" + " ".join(fields) + ")"

        return str(self.data)

    def _format_shape_definition(self):
        """Format a shape definition value as a shape literal.

        Shape definitions are stored as structs with a shape.define tag and kids containing shape.field nodes.
        Each shape.field has a name and potentially type constraints and default values.

        After Module.finalize(), identifier references in type constraints are resolved to value.constant nodes.
        We read from self.cop (if available) to get the finalized version, otherwise fall back to self.data.

        Returns:
            str: Formatted shape literal like "~(x y)" or "~(x~num y~text)"
        """
        try:
            # Prefer reading from self.cop if available (has finalized identifiers)
            # Otherwise fall back to self.data
            source_cop = self.cop if hasattr(self, 'cop') and self.cop is not None else None

            if source_cop:
                # Read from the COP
                kids = source_cop.field("kids")
            else:
                # Read from self.data (pre-finalize)
                kids_key = None
                for k in self.data.keys():
                    if isinstance(k, Value) and k.data == "kids":
                        kids_key = k
                        break

                if not kids_key or not self.data[kids_key].data:
                    return "~()"

                kids = self.data[kids_key]

            if not kids.data:
                return "~()"

            field_parts = []

            for kid_key, kid_val in kids.data.items():
                # Each kid should be a shape.field
                kid_tag = kid_val.positional(0).data.qualified
                if kid_tag != "shape.field":
                    continue

                # Extract field name
                field_name = None
                name_key = None
                for k in kid_val.data.keys():
                    if isinstance(k, Value) and k.data == "name":
                        name_key = k
                        break

                if name_key:
                    field_name = kid_val.data[name_key].data

                # Get the kids (type constraint and/or default value)
                field_kids_key = None
                for k in kid_val.data.keys():
                    if isinstance(k, Value) and k.data == "kids":
                        field_kids_key = k
                        break

                # Build the field string
                field_str = field_name if field_name else ""

                if field_kids_key and kid_val.data[field_kids_key].data:
                    field_kids = list(kid_val.data[field_kids_key].data.values())

                    # First kid is the type constraint (if not None)
                    if len(field_kids) >= 1 and field_kids[0] is not None:
                        type_cop = field_kids[0]

                        try:
                            cop_tag = type_cop.positional(0).data.qualified
                        except (AttributeError, KeyError):
                            # Can't get tag, skip type annotation
                            cop_tag = None

                        # Handle unresolved identifiers (before finalize)
                        if cop_tag == "value.identifier":
                            # Extract identifier name
                            type_kids = type_cop.field("kids").data
                            for tk, tv in type_kids.items():
                                if tv.positional(0).data.qualified == "ident.token":
                                    type_name = tv.field("value").data
                                    field_str += f"~{type_name}"
                                    break

                        # Handle resolved constants (after finalize)
                        elif cop_tag == "value.constant":
                            # The type has been resolved to a constant value (e.g., a shape)
                            # Show a preview of the shape instead of the full definition
                            try:
                                resolved_value = type_cop.field("value")
                                # Format the resolved value, but limit length
                                resolved_str = resolved_value.format()
                                # For shapes, show a compact form
                                if resolved_str.startswith("~(") and len(resolved_str) > 15:
                                    # Show just the shape literal (already has ~)
                                    field_str += "(...)"
                                elif resolved_str.startswith("~("):
                                    # Short shape - show it fully without adding extra ~
                                    field_str += resolved_str
                                elif len(resolved_str) > 15:
                                    # Truncate other long values
                                    field_str += f"~{resolved_str[:12]}..."
                                else:
                                    # Show short non-shape values with ~
                                    field_str += f"~{resolved_str}"
                            except (KeyError, AttributeError):
                                pass

                    # Second kid is the default value (if present)
                    if len(field_kids) >= 2:
                        default_cop = field_kids[1]
                        # Extract and format the default value from the COP
                        try:
                            cop_tag = default_cop.positional(0).data.qualified
                            if cop_tag == "value.number":
                                default_str = str(default_cop.field("value").data)
                            elif cop_tag == "value.text":
                                text_val = default_cop.field("value").data
                                default_str = f'"{text_val}"'
                            else:
                                # For other types, try to format the COP
                                default_str = default_cop.format()
                                if len(default_str) > 20:
                                    default_str = None
                            if default_str and len(default_str) < 20:
                                field_str += f"={default_str}"
                        except (KeyError, AttributeError):
                            pass

                if field_str:
                    field_parts.append(field_str)

            if field_parts:
                return "~(" + " ".join(field_parts) + ")"
            else:
                return "~()"

        except (KeyError, AttributeError):
            # If we can't parse the structure, fall back to basic representation
            return "~(...)"


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

        # Allow Tag, Shape, ShapeUnion, Func objects to be wrapped in Values
        if isinstance(value, (comp.Tag, comp.Shape, comp.ShapeUnion, comp.Func)):
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
            if not val.handles.issubset(value.handles):
                raise comp.EvalError(
                    f"Struct field {key!r} has invalid handles in value {val!r}"
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

    if not isinstance(data, (comp.Tag, str, decimal.Decimal, fractions.Fraction)):
        raise TypeError(f"Unknown internal type for value: {type(data).__name__}")
