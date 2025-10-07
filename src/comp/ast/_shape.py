"""Ast nodes for shapes"""

__all__ = [
    "ShapeDef",
    "ShapeField",
    "ShapeSpread",
    "ShapeUnion",
    "ShapeInline",
    "ShapeRef",
]

from . import _node, _ops, _tag
import comp


class ShapeDef(_node.Node):
    """Shape definition at module level"""

    def __init__(self, tokens: list[str] | None = None, assign_op: str = "="):
        self.tokens = list(tokens) if tokens else []
        self.assign_op = assign_op
        super().__init__()

    def unparse(self) -> str:
        shape_path = "~" + ".".join(self.tokens)

        if not self.kids:
            # Shape with no body (shouldn't happen in valid code)
            return f"!shape {shape_path}"

        # Alias with default (2 kids: type + default expression)
        if len(self.kids) == 2 and isinstance(self.kids[0], (ShapeRef, _tag.TagRef)):
            # Alias with default: !shape ~one = ~num=1
            return f"!shape {shape_path} = {self.kids[0].unparse()}={self.kids[1].unparse()}"

        # Simple alias or union (single child that's a type reference/union)
        if len(self.kids) == 1 and isinstance(self.kids[0], (ShapeRef, _tag.TagRef)):
            # Simple alias: !shape ~number = ~num
            return f"!shape {shape_path} = {self.kids[0].unparse()}"

        # Union or other shape_type expression
        if len(self.kids) == 1 and not isinstance(self.kids[0], (ShapeField, ShapeSpread)):
            # Union or complex type: !shape ~result = ~success | ~error
            return f"!shape {shape_path} = {self.kids[0].unparse()}"

        # Definition with fields: !shape ~point = {x ~num y ~num}
        fields_str = " ".join(kid.unparse() for kid in self.kids)
        return f"!shape {shape_path} = {{{fields_str}}}"

    @classmethod
    def from_grammar(cls, tree):
        # shape_path: "~" reference_identifiers
        # shape_body: LBRACE shape_field* RBRACE | shape_type
        shape_path_tree = tree.children[1]
        assign_op_token = tree.children[2]
        shape_body_tree = tree.children[3]

        # shape_path -> "~" reference_identifiers
        reference_identifiers = shape_path_tree.children[1]  # Skip "~" token

        # Extract tokens from reference_identifiers (TOKEN ("." TOKEN)*)
        tokens = []
        for child in reference_identifiers.children:
            if hasattr(child, 'value') and child.value != ".":
                tokens.append(child.value)

        assign_op = assign_op_token.value if hasattr(assign_op_token, 'value') else str(assign_op_token)
        return cls(tokens=tokens, assign_op=assign_op)


class ShapeField(_node.Node):
    """Single field in a shape definition, named or unnamed with optional default."""

    def __init__(self, name: str | None = "", optional: bool = False):
        self.name = name
        self.optional = optional
        super().__init__()

    @property
    def type_ref(self):
        """First child is the type reference (if present)."""
        return self.kids[0] if self.kids else None

    @property
    def default(self):
        """Second child is the default value (if present)."""
        return self.kids[1] if len(self.kids) > 1 else None

    def unparse(self) -> str:
        if self.name is None:
            result = ""
        else:
            result = self.name
        if self.type_ref:
            if result:  # Named field: add space before type
                result += f" {self.type_ref.unparse()}"
            else:  # Positional field: no space, just type
                result = self.type_ref.unparse()
        if self.default:
            result += f" = {self.default.unparse()}"
        return result

    @classmethod
    def from_grammar(cls, tree):
        # shape_field_def: TOKEN QUESTION? shape_type? (ASSIGN expression)?
        # | shape_type (ASSIGN expression)?
        children = tree.children

        # Check if first child is a TOKEN (named field) or shape_type (positional field)
        first_child = children[0] if children else None

        if first_child and hasattr(first_child, 'type') and first_child.type == 'TOKEN':
            # Named field: first child is TOKEN
            name = first_child.value
            # Check if name ends with ? (optional field)
            optional = name.endswith('?')
            return cls(name=name, optional=optional)
        else:
            # Positional field: no name token, starts with shape_type
            # Return field with empty name to indicate positional
            return cls(name=None, optional=False)


class ShapeSpread(_node.Node):
    """Shape spread in definition like '..~shape'"""

    def __init__(self):
        super().__init__()

    @property
    def shape_type(self):
        """The shape type being spread (first child)."""
        return self.kids[0] if self.kids else None

    def unparse(self) -> str:
        if self.shape_type:
            return f"..{self.shape_type.unparse()}"
        return ".."

    @classmethod
    def from_grammar(cls, tree):
        # shape_spread: SPREAD shape_type
        return cls()


class ShapeUnion(_node.Node):
    """Union of shape types like `type1 | ~type2 | ~type3`"""

    def __init__(self):
        super().__init__()

    def unparse(self) -> str:
        if not self.kids:
            return "???"
        return " | ".join(kid.unparse() for kid in self.kids)

    @classmethod
    def from_grammar(cls, tree):
        # shape_union: shape_type_atom (PIPE shape_type_atom)+
        return cls()


class ShapeInline(_node.Node):
    """Inline anonymous shape definition like '~{...fields...}'"""

    def __init__(self):
        super().__init__()

    def unparse(self) -> str:
        if not self.kids:
            return "~{}"
        fields = " ".join(kid.unparse() for kid in self.kids)
        return f"~{{{fields}}}"

    @classmethod
    def from_grammar(cls, tree):
        # shape_type_atom: TILDE LBRACE shape_field* RBRACE
        return cls()


class ShapeRef(_node.BaseRef):
    """Shape reference like '~path'"""
    SYMBOL = "~"


