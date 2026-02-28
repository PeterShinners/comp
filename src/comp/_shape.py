"""Shape definitions and operations"""

import comp


__all__ = [
    "Shape",
    "ShapeField",
    "ShapeUnion",
    "shape_num",
    "shape_text",
    "shape_struct",
    "shape_any",
    "shape_block",
    "shape_tag",
    "shape_func",
    "shape_shape",
    "shape_union",
    "shape_failure",
]


class Shape:
    """A shape definition.

    Shapes define the structure and types of values in the comp language.
    User-defined shapes describe structure fields, while builtin shapes
    represent primitive types (num, text, struct, any).

    Args:
        qualified: (str) Fully qualified shape name
        private: (bool) Shape is private to its module

    Attributes:
        qualified: (str) Fully qualified shape name
        private: (bool) Shape is private to its module
        module: (Module | None) The module that defined this shape
        fields: (list[ShapeField]) Field definitions for structure shapes
    """

    __slots__ = ("qualified", "private", "module", "fields")

    def __init__(self, qualified, private):
        self.qualified = qualified
        self.module = None
        self.private = private
        self.fields = []

    def __repr__(self):
        return f"Shape<{self.qualified}>"

    def __hash__(self):
        return hash((self.qualified, self.module))

    def format(self):
        """Format to literal string representation.

        Named shapes (builtins and user-defined) render as ~name.
        Anonymous structural shapes render as ~(field ...).

        Returns:
            str: Formatted shape literal like "~num" or "~{x~num y~text}"
        """
        if self.qualified and self.qualified != "anonymous":
            return f"~{self.qualified}"
        fields = [f.format() for f in self.fields]
        return "~{" + " ".join(fields) + "}"


class ShapeUnion:
    """A union of multiple shapes.

    Used for type constraints that can accept multiple shapes.

    Args:
        shapes: (list) List of shape COPs or Shape objects in the union
        default: (Value | None) Default value for the union, or None

    Attributes:
        shapes: (list) List of shape COPs or Shape objects in the union
        default: (Value | None) Default value for the union
    """

    __slots__ = ("shapes", "default")

    def __init__(self, shapes, default=None):
        self.shapes = list(shapes)
        self.default = default

    def __repr__(self):
        return f"ShapeUnion<{self.format()}>"

    def format(self):
        """Format to literal string representation.

        Returns:
            str: Formatted union like "~(tree | nil)" or "~(num | text)"
        """
        parts = []
        for shape_item in self.shapes:
            if isinstance(shape_item, Shape):
                parts.append(shape_item.qualified)
            elif hasattr(shape_item, "qualified"):
                # Tag or other named object
                parts.append(shape_item.qualified)
            else:
                # It's a COP node, unparse it
                parts.append(comp.cop_unparse(shape_item))
        return "~(" + " | ".join(parts) + ")"


class ShapeField:
    """Internal field definition within a shape.

    Fields can have a name, a shape constraint, a unit constraint, and a default value.
    At least one of name or shape must be provided.

    These aren't exposed to the Comp language directly.

    Args:
        name: (str | None) Field name, None for positional/unnamed fields
        shape: (cop | None) Shape constraint for the field
        unit: (Tag | None) Expected unit tag for the field value
        default: (cop | None) Default value if field is omitted
        limits: (list | None) List of (name_str, param_value_or_None) limit tuples

    Attributes:
        name: (str | None) Field name
        shape: (cop | None) Shape constraint
        unit: (Tag | None) Expected unit tag
        default: (cop | None) Default value
        limits: (list) List of (func_val, param_value_or_None) limit tuples
                       func_val is a resolved callable Value; param_value is the
                       single argument Value or None for zero-param limits.
    """

    __slots__ = ("name", "shape", "unit", "default", "limits")

    def __init__(self, name=None, shape=None, unit=None, default=None, limits=None):
        self.name = name
        self.shape = shape  # cop node for shape
        self.unit = unit    # Tag | None — expected unit for this field
        self.default = default  # cop node for default
        self.limits = limits if limits is not None else []  # [(name_str, param_val_or_None)]

    def __repr__(self):
        parts = []
        if self.name:
            parts.append(self.name)
        if self.shape:
            if hasattr(self.shape, "qualified"):
                parts.append(f":{self.shape.qualified}")
            else:
                parts.append(f":{self.shape!r}")
        if self.unit:
            parts.append(f"[{self.unit.qualified}]")
        if self.default is not None:
            parts.append(f"={self.default}")
        return f"Field<{''.join(parts)}>"

    def format(self):
        """Format individual shape field to literal representation."""
        result = self.name or ""
        if self.shape:
            if isinstance(self.shape, ShapeUnion):
                result += self.shape.format()
            else:
                result += f"~{self.shape.qualified}"
        if self.unit:
            result += f"[{self.unit.qualified}]"
        if self.default:
            result += f"={self.default.format()}"
        return result


# Builtin shapes for primitive types
shape_num = Shape("num", False)
shape_text = Shape("text", False)
shape_struct = Shape("struct", False)
shape_any = Shape("any", False)
shape_block = Shape("block", False)
shape_shape = Shape("shape", False)
shape_union = Shape("union", False)

# Internal shapes - used by implementation, not exposed to comp language
shape_tag = Shape("tag", True)
shape_func = Shape("func", True)

# Failure shape — defined here so it's available early; fields are set by
# _init_shape_failure() which is called from __init__.py after all modules
# are loaded.  The cause field is self-referential: shape_failure is created
# before its fields so the ShapeUnion can safely reference it.
shape_failure = Shape("failure", False)


def _init_shape_failure():
    """Initialize shape_failure fields.

    Called from __init__.py after all modules are fully loaded so that
    Value.from_python can safely reference comp.Shape, comp.Block, etc.
    """
    nil_default = comp.Value.from_python(comp.tag_nil)
    shape_failure.fields = [
        ShapeField(name="fail"),
        ShapeField(name="message", shape=shape_text, default=comp.Value.from_python("")),
        ShapeField(name="cause",
                   shape=ShapeUnion([shape_failure, comp.tag_nil], default=nil_default),
                   default=nil_default),
        ShapeField(name="cop",
                   shape=ShapeUnion([shape_struct, comp.tag_nil], default=nil_default),
                   default=nil_default),
    ]