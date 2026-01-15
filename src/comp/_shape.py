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
    "shape_shape",
    "shape_union",
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
        return f"Shape<{self.format()}>"

    def __hash__(self):
        return hash((self.qualified, self.module))

    def format(self):
        """Format to literal string representation.

        Returns:
            str: Formatted shape literal like "~(x y)" or "~(x~num y~text)"
        """
        fields = [f.format() for f in self.fields]
        return "~(" + " ".join(fields) + ")"


class ShapeUnion:
    """A union of multiple shapes.

    Used for type constraints that can accept multiple shapes.

    Args:
        shapes: (list) List of shape COPs or Shape objects in the union

    Attributes:
        shapes: (list) List of shape COPs or Shape objects in the union
    """

    __slots__ = ("shapes",)

    def __init__(self, shapes):
        self.shapes = list(shapes)

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
            else:
                # It's a COP node, unparse it
                parts.append(comp.cop_unparse(shape_item))
        return "~(" + " | ".join(parts) + ")"


class ShapeField:
    """Internal field definition within a shape.

    Fields can have a name, a shape constraint, and a default value.
    At least one of name or shape must be provided.

    These aren't exposed to the Comp language directly.

    Args:
        name: (str | None) Field name, None for positional/unnamed fields
        shape: (cop | None) Shape constraint for the field
        default: (cop | None) Default value if field is omitted

    Attributes:
        name: (str | None) Field name
        shape: (cop | None) Shape constraint
        default: (cop | None) Default value
    """

    __slots__ = ("name", "shape", "default")

    def __init__(self, name=None, shape=None, default=None):
        self.name = name
        self.shape = shape  # cop node for shape
        self.default = default  # cop node for default

    def __repr__(self):
        parts = []
        if self.name:
            parts.append(self.name)
        if self.shape:
            parts.append(f":{self.shape.qualified}")
        if self.default is not None:
            parts.append(f"={self.default}")
        return f"Field<{''.join(parts)}>"

    def format(self):
        """Format individual shape field to literal representation."""
        result = self.name or ""
        if self.shape:
            result += f"~{self.shape.qualified}"
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