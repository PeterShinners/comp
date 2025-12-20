"""Shape definitions and operations"""

import comp


__all__ = [
    "ShapeDef",
    "Shape",
    "FieldDef",
    "shape_num",
    "shape_text",
    "shape_struct",
    "shape_any",
    "shape_func",
    "shape_tag",
]


class ShapeDef:
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


class Shape:
    """Reference to a Shape definition.

    To use a shape as a type constraint there must be a reference to its
    definition. The reference stores additional information about where
    it came from and how it was named.

    Shape references can point to either a ShapeDef or a TagDef, since
    tags are valid shape constraints in the language.

    Unlike tags, shapes are not serializable and don't need anchor logic
    for floating vs anchored comparisons.

    Args:
        definition: (ShapeDef | TagDef | HandleDef) Definition for this shape reference

    """

    __slots__ = ("definition",)

    def __init__(self, definition):
        self.definition = definition

    def __repr__(self):
        if self.definition.module:
            suffix = (
                self.definition.module.token if self.definition.module.token else ""
            )
            return f"Shape({self.definition.qualified}/{suffix})"
        return f"Shape({self.definition.qualified})"


class FieldDef:
    """Internal field definition within a shape.

    Fields can have a name, a shape constraint, and a default value.
    At least one of name or shape must be provided.

    These aren't exposed to the Comp language directly.

    Args:
        name: (str | None) Field name, None for positional/unnamed fields
        shape: (ShapeDef | TagDef | None) Shape constraint for the field
        default: (Value | None) Default value if field is omitted

    Attributes:
        name: (str | None) Field name
        shape: (ShapeDef | TagDef | None) Shape constraint
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
shape_num = ShapeDef("num", False)
shape_text = ShapeDef("text", False)
shape_struct = ShapeDef("struct", False)
shape_any = ShapeDef("any", False)
shape_func = ShapeDef("func", False)

# Internal shapes - used by implementation, not exposed to comp language
shape_tag = ShapeDef("tag", True)
