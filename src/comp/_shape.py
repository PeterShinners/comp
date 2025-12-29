"""Shape definitions and operations"""

import comp


__all__ = [
    "Shape",
    "FieldDef",
    "shape_num",
    "shape_text",
    "shape_struct",
    "shape_any",
    "shape_func",
    "shape_tag",
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
        fields: (list[FieldDef]) Field definitions for structure shapes
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


class FieldDef:
    """Internal field definition within a shape.

    Fields can have a name, a shape constraint, and a default value.
    At least one of name or shape must be provided.

    These aren't exposed to the Comp language directly.

    Args:
        name: (str | None) Field name, None for positional/unnamed fields
        shape: (Shape | Tag | None) Shape constraint for the field
        default: (Value | None) Default value if field is omitted

    Attributes:
        name: (str | None) Field name
        shape: (Shape | Tag | None) Shape constraint
        default: (Value | None) Default value
    """

    __slots__ = ("name", "shape", "default")

    def __init__(self, name=None, shape=None, default=None):
        self.name = name
        self.shape = shape
        self.default = default

    def __repr__(self):
        parts = []
        if self.name:
            parts.append(self.name)
        if self.shape:
            parts.append(f":{self.shape.qualified}")
        if self.default is not None:
            parts.append(f"={self.default}")
        return f"Field<{''.join(parts)}>"


# Builtin shapes for primitive types
shape_num = Shape("num", False)
shape_text = Shape("text", False)
shape_struct = Shape("struct", False)
shape_any = Shape("any", False)
shape_func = Shape("func", False)

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
    tag_value = cop_node.positional(0)
    tag = tag_value.data if hasattr(tag_value, 'data') else tag_value

    if not isinstance(tag, comp.Tag) or tag.qualified != "value.shape":
        raise comp.CodeError(
            f"Expected value.shape node, got {tag.qualified if isinstance(tag, comp.Tag) else type(tag)}",
            cop_node
        )

    # Create Shape
    shape_def = Shape(qualified_name, private)

    # TODO: Parse field definitions from cop_node
    # For now, just create the basic definition

    # Wrap in Value and set cop attribute
    value = comp.Value.from_python(shape_def)
    value.cop = cop_node

    return value
