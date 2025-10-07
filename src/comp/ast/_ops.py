"""Ast nodes for operators and expressions"""

__all__ = [
    "BinaryOp",
    "UnaryOp",
    "MorphOp",
]

from . import _node, _shape
import comp


class BinaryOp(_node.Node):
    """Binary operation."""

    def __init__(self, op: str = "?"):
        self.op = op
        super().__init__()

    @property
    def left(self):
        return self.kids[0]

    @property
    def right(self):
        return self.kids[1]

    def unparse(self) -> str:
        # Escape quotes and backslashes
        left = self.left.unparse()
        if isinstance(self.left, BinaryOp):
            left = f"({left})"
        right = self.right.unparse()
        if isinstance(self.right, BinaryOp):
            right = f"({right})"
        return f'{left} {self.op} {right}'

    @classmethod
    def from_grammar(cls, tree):
        """Parse binary operation from Lark tree."""
        return cls(tree.children[1].value)


class UnaryOp(_node.Node):
    """Unary operation."""

    def __init__(self, op: str = ""):
        self.op = op
        super().__init__()

    @property
    def right(self):
        return self.kids[0]

    def unparse(self) -> str:
        right = self.right.unparse()
        if isinstance(self.right, BinaryOp):
            right = f"({right})"
        return f'{self.op}{right}'

    @classmethod
    def from_grammar(cls, tree):
        """Parse string from Lark tree: string -> QUOTE content? QUOTE"""
        return cls(tree.children[0].value)


class MorphOp(_node.Node):
    """Shape morph operation: expr ~shape, expr ~* shape, expr ~? shape

    Transforms a value to match a shape specification.

    Examples:
        data ~point
        {x=1 y=2 z=3} ~* point-2d
        partial ~? user

    Children:
        [0] - Expression to morph
        [1] - Shape type (ShapeRef, ShapeUnion, ShapeInline, etc.)
    """

    def __init__(self, mode: str = "normal"):
        """Initialize morph operation.

        Args:
            mode: "normal" (~), "strong" (~*), or "weak" (~?)
        """
        self.mode = mode
        super().__init__()

    @property
    def expr(self):
        """The expression being morphed (first child)."""
        return self.kids[0] if self.kids else None

    @property
    def shape(self):
        """The target shape (second child)."""
        return self.kids[1] if len(self.kids) > 1 else None

    def unparse(self) -> str:
        """Unparse morph operation back to source code."""
        if len(self.kids) != 2:
            return "<?morph?>"

        expr_str = self.expr.unparse()

        # Handle different shape type formats
        if isinstance(self.shape, _shape.ShapeUnion):
            # For unions, keep ~ on each member: val ~cat | ~dog
            shape_str = " | ".join(kid.unparse() for kid in self.shape.kids)
            # Union already has ~ on members, so we need special formatting
            if self.mode == "strong":
                return f"{expr_str} ~* {shape_str}"
            elif self.mode == "weak":
                return f"{expr_str} ~? {shape_str}"
            else:
                # For normal morph with union, no ~ prefix (members have it)
                return f"{expr_str} {shape_str}"
        else:
            # Single shape reference or inline shape
            shape_str = self.shape.unparse()
            # Strip leading ~ since it's part of our operator
            if (isinstance(self.shape, (_shape.ShapeRef, _shape.ShapeInline)) and
                shape_str.startswith("~")):
                shape_str = shape_str[1:]

            if self.mode == "strong":
                return f"{expr_str} ~* {shape_str}"
            elif self.mode == "weak":
                return f"{expr_str} ~? {shape_str}"
            else:
                # Normal morph - no space between ~ and shape
                return f"{expr_str} ~{shape_str}"

    @classmethod
    def from_grammar(cls, tree):
        # morph_expr TILDE shape_type -> morph_op
        # morph_expr STRONG_MORPH shape_type -> strong_morph_op
        # morph_expr WEAK_MORPH shape_type -> weak_morph_op
        # Mode determined by which grammar rule matched
        if tree.data == "strong_morph_op":
            mode = "strong"
        elif tree.data == "weak_morph_op":
            mode = "weak"
        else:
            mode = "normal"
        return cls(mode=mode)

