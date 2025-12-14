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
    tags. Use the `frompython` and `topython` methods to convert between
    more native data types.

    The contents of the value are considered immutable, even when
    represented by structures with dicts. 

    Args:
        data: The underlying data.
        token: Optional source token
    Attributes:
        data: The underlying data (primitives, tags, structs, etc.)
        shape: (ShapeRef) Definition of represented data, or unit for basic types
        token: Optional parsed token that created this value (for error messages)
        private: Module-private data storage dict
        handles: Frozenset of HandleInstance objects contained in this value
    """
    __slots__ = ("data", "token", "private", "handles", "_guard")
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
        self.token = None

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
            for value in data.values():
                self.handles = self.handles.union(value.handles)
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
            }
            Value._shapetypes = (comp.Tag, comp.Shape)

    @property
    def shape(self):
        """(ShapeDef | TagDef) Shape reference for this value's data type."""
        shape = Value._shapemap.get(type(self.data))
        if shape is None and isinstance(self.data, Value._shapetypes):
            shape = self.data  # tag
        return shape

    def format(self):
        """Convert value to Comp literal expression.

        Returns:
            (str) String representation suitable for display
        """
        shape = self.shape
        if shape is comp.shape_num:
            return str(self.data)
        if shape is comp.shape_text:
            value = self.data.replace('"', '\\"')
            return f'"""{value.replace('\n', '\\n')}"""' if '\n' in value else f'"{value}"'
        if shape is comp.tag_true:
            return "true"
        if shape is comp.tag_false:
            return "false"
        if isinstance(self.data, comp.Tag):
            return f"{self.data.qualified}"
        if isinstance(self.data, comp.Func):
            return f"{self.data.definition.qualified}()"

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
                        if re.match(r'^[^\W\d][\w-]*\??$', key):
                            fields.append(f"{key}={v.format()}")
                        else:
                            # Need to quote the key
                            fields.append(f'"{key}"={v.format()}')
                    else:
                        fields.append(f"'{k.format()}'={v.unparse()}")

            return "{" + " ".join(fields) + "}"

        return str(self.data)

    def to_python(self, field=None):
        """Convert this value to a Python equivalent.

        If field is given it will assume this is a struct value and access
        the given field by name (str) or by position (int).

        Args:
            field: (str | int | None) Optional field to access from struct
        Returns:
            (object) Converted python value

        """
        if field is not None:
            if not self.is_struct:
                raise TypeError(f"Cannot access field on non-struct value")
            if isinstance(field, int):
                # Access by position
                for i, (k, v) in enumerate(self.data.items()):
                    if i == field:
                        return v.to_python()
                raise IndexError(f"Struct field index {field} out of range")
            else:
                # Access by name
                for k, v in self.data.items():
                    if isinstance(k, Value) and k.is_string and k.data == field:
                        return v.to_python()
                raise KeyError(f"Struct field '{field}' not found")

        if isinstance(self.data, comp.Tag):
            # Convert #bool.true and #bool.false to Python booleans
            if self.data.qualified == "bool.true":
                return True
            elif self.data.qualified == "bool.false":
                return False
            # Other tags remain as Tag
            return self.data

        if isinstance(self.data, decimal.Decimal):
            return self.data
        if isinstance(self.data, fractions.Fraction):
            return self.data
        if isinstance(self.data, str):
            return self.data

        if isinstance(self.data, dict):
            # Check if all keys are Unnamed - convert to list
            if self.data and all(isinstance(k, Unnamed) for k in self.data):
                return [v.to_python() for v in self.data.values()]

            # Mixed or named keys - convert to dict
            result = {}
            for key, val in self.data.items():
                if isinstance(key, Unnamed):
                    result[len(result)] = val.to_python()
                else:
                    result[key.to_python()] = val.to_python()
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
            raise TypeError("from_python called with existing Value")

        if isinstance(value, str):
            return cls(value)

        if value is True:
            return cls(comp.Tag("bool.true", "", None))
        if value is False:
            return cls(comp.Tag("bool.false", "", None))

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

        if isinstance(value, comp.Tag):
            return cls(value)

        raise TypeError(f"Cannot convert Python type {type(value).__name__} to Comp Value")


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
                raise comp.EvalError(f"Struct field {key!r} has invalid handles in value {val!r}")
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

