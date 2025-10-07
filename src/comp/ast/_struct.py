"""Ast nodes for structures"""

__all__ = [
    "Structure",
    "Block",
    "StructAssign",
    "StructUnnamed",
    "StructSpread",
]


from . import _node
import comp


class Structure(_node.Node):
    """Structure literal like '{ }'"""

    def unparse(self) -> str:
        if not self.kids:
            return "{}"
        items = " ".join(kid.unparse() for kid in self.kids)
        return f"{{{items}}}"


class Block(Structure):
    """Block literal like  ':{ }'"""

    def unparse(self) -> str:
        return ":" + super().unparse()


class StructAssign(_node.Node):
    """Named field assignment like 'key=value'"""

    def __init__(self, op: str = "="):
        self.op = op
        super().__init__()

    @property
    def key(self):
        """The key/identifier (first child)."""
        return self.kids[0] if self.kids else None

    @property
    def value(self):
        """The assigned value (second child)."""
        return self.kids[1] if len(self.kids) > 1 else None

    def unparse(self) -> str:
        if len(self.kids) >= 2:
            key = self.key.unparse()
            value = self.value.unparse()
            return f"{key} {self.op} {value}"
        return "??? = ???"

    @classmethod
    def from_grammar(cls, tree):
        # structure_assign -> _qualified _assignment_op expression
        kids = tree.children
        op_token = next((k for k in kids if hasattr(k, 'type')), None)
        return cls(op=op_token.value if op_token else '=')


class StructUnnamed(_node.Node):
    """Unnamed field like 'expression'"""

    @property
    def value(self):
        """The unnamed value expression (first child)."""
        return self.kids[0] if self.kids else None

    def unparse(self) -> str:
        if self.kids:
            return self.value.unparse()
        return "???"


class StructSpread(_node.Node):
    """Structure spread like '..expression'"""

    @property
    def value(self):
        """The spread expression (first child)."""
        return self.kids[0] if self.kids else None

    def unparse(self) -> str:
        if self.kids:
            return f"..{self.value.unparse()}"
        return "..???"
