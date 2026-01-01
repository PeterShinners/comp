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
    "shape_func",
    "shape_tag",
    "shape_shape",
    "shape_union",
    "create_shapedef",
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
        format = self.name or ""
        if self.shape:
            shapefmt = comp.cop_unparse(self.shape)
            if shapefmt != "~()":
                format += f"~{shapefmt}"
        if self.default:
            format += f"={comp.cop_unparse(self.default)}"
        return format


# Builtin shapes for primitive types
shape_num = Shape("num", False)
shape_text = Shape("text", False)
shape_struct = Shape("struct", False)
shape_any = Shape("any", False)
shape_func = Shape("func", False)
shape_shape = Shape("shape", False)
shape_union = Shape("union", False)

# Internal shapes - used by implementation, not exposed to comp language
shape_tag = Shape("tag", True)


def create_shapedef(qualified_name, private, cop_node):
    """Create a Shape from a value.shape COP node and wrap in a Value.

    This is a pure initialization function that doesn't depend on Module or Interp.

    Args:
        qualified_name: (str) Fully qualified shape name (e.g., "Point")
        private: (bool) Whether shape is private
        cop_node: (Struct) The value.shape COP node

    Returns:
        Value: Initialized shape definition wrapped in a Value with cop attribute set

    Raises:
        CodeError: If cop_node is not a value.shape node
    """
    # Validate node type
    tag = comp.cop_tag(cop_node)
    if tag != "shape.define":
        raise comp.CodeError(
            f"Expected shape.define node, got {tag}",
            cop_node
        )

    # Only works with shape field cop nodes (not unions or references)
    shape = Shape(qualified_name, private)

    for kid in comp.cop_kids(cop_node):
        kid_tag = comp.cop_tag(kid)
        if kid_tag != "shape.field":
            continue  # Skip non-field kids

        # Parse field definition
        field_name = None
        field_shape = None
        field_default = None

        for fkid in comp.cop_kids(kid):
            fkid_tag = comp.cop_tag(fkid)
            if fkid_tag == "field.name":
                field_name = fkid.field("value").data
            elif fkid_tag == "field.shape":
                field_shape = fkid.field("shape")
            elif fkid_tag == "field.default":
                field_default = fkid.field("value")

        shape_field = ShapeField(
            name=field_name,
            shape=field_shape,
            default=field_default
        )
        shape.fields.append(shape_field)

    # TODO: Parse field definitions from cop_node
    # For now, just create the basic definition

    # Wrap in Value and set cop attribute
    value = comp.Value.from_python(shape)
    value.cop = cop_node

    return value
