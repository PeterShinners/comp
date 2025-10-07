"""Ast nodes for operators and expressions"""

__all__ = [
    "Identifier",
    "ScopeField",
    "TokenField",
    "IndexField",
    "ComputeField",
    "StringField",
    "ExprIdentifier",
]

from . import _node
import comp


class Identifier(_node.Node):
    """Fully qualified fields 'foo.bar' or '$in.foo."baz".#0'"""

    def unparse(self) -> str:
        if not self.kids:
            return "???"

        tokens = [kid.unparse() for kid in self.kids]
        if len(tokens) >= 2 and tokens[0] in ("@", "^"):
            tokens[:2] = [tokens[0] + tokens[1]]
        return ".".join(tokens)


class TokenField(_node.Node):
    """Simple name like 'foo' or 'bar-baz'"""

    def __init__(self, value: str = ""):
        self.value = value
        super().__init__()

    def unparse(self) -> str:
        return self.value

    @classmethod
    def from_grammar(cls, tree):
        # Parse from Lark tree: tokenfield -> TOKEN
        return cls(value=tree.children[0].value)


class IndexField(_node.Node):
    """Positional numeric access like '#0' or '#1'"""

    def __init__(self, value: int = 0):
        self.value = value
        super().__init__()

    def unparse(self) -> str:
        return f"#{self.value}"

    @classmethod
    def from_grammar(cls, tree):
        # Parse from Lark tree: indexfield -> INDEXFIELD
        return cls(value=int(tree.children[0].value[1:]))


class ComputeField(_node.Node):
    """Expression field quoted with single quotes with any type like '#true' or '2+2'"""

    @property
    def expr(self):
        """The computed expression (first child)."""
        return self.kids[0] if self.kids else None

    def unparse(self) -> str:
        if self.kids:
            return f"'{self.expr.unparse()}'"
        return "'???'"


class ScopeField(_node.Node):
    """Leading scope field like '@' or '$mod'"""

    def __init__(self, value: str = "@"):
        self.value = value
        super().__init__()

    def unparse(self) -> str:
        return self.value

    @classmethod
    def from_grammar(cls, tree):
        if tree.data == 'localscope':
            return cls(value="@")
        elif tree.data == 'argscope':
            return cls(value="^")
        elif tree.data == 'namescope':
            # kids[0] is namescope, kids[1] should be TOKEN
            return cls(value="$" + tree.children[1].value)


class StringField(_node.String):
    """String literal field allowing any characters like '"<n/a>"' or '"Try again"'"""


class ExprIdentifier(_node.Node):
    """Field access on an expression: '(expr).field.field2'
    
    Children are flattened: [expr, field1, field2, ...]
    """

    @property
    def expr(self):
        """The leading expression (first child)"""
        return self.kids[0] if self.kids else None

    @property
    def fields(self):
        """All field accesses after the expression"""
        return self.kids[1:]

    def unparse(self) -> str:
        if not self.kids:
            return "???"
        # First kid is the expr (may need parens), rest are fields
        expr = self.expr
        if not expr:
            return "???"
        expr_str = expr.unparse()
        if self.fields:
            fields_str = ".".join(f.unparse() for f in self.fields)
            return f"({expr_str}).{fields_str}"
        return f"({expr_str})"

