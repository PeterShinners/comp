"""
AST node definitions for Comp language - Clean Redesign

This module defines a simplified Abstract Syntax Tree for the Comp language.
Combines MiniAst's simplicity with structured node classes.

Design principles:
- Uniform structure: all nodes have 'kids' list for children
- Simple construction with kwargs
- Compact repr showing type and key attributes
- Clean tree printing (MiniAst style)
- Short find methods (2-4 lines)
"""

__all__ = [
    "ParseError",
    "AstNode",
    "Number",
    "String",
    "BinaryOp",
    "UnaryOp",
    "Structure",
    "Block",
    "StructAssign",
    "StructUnnamed",
    "StructSpread",
    "Identifier",
    "ScopeField",
    "TokenField",
    "IndexField",
    "ComputeField",
    "StringField",
    "FieldAccess",
    "Placeholder",
    "Pipeline",
    "PipeFallback",
    "PipeStruct",
    "PipeBlock",
    "PipeFunc",
    "PipeWrench",
    "TagRef",
    "ShapeRef",
    "FuncRef",
]

import decimal


class ParseError(Exception):
    """Exception raised for parsing errors."""

    def __init__(self, message: str, position: int | None = None):
        self.message = message
        self.position = position
        super().__init__(f"Parse error: {message}")


class AstNode:
    """Base class for all AST nodes."""

    def __init__(self, kids: list["AstNode"] | None = None):
        """Initialize node with arbitrary attributes.

        The 'kids' attribute should be a list of child AstNode objects.
        Other attributes are node-specific (value, op, path, etc.).

        Args:
            kids: List of child nodes
            _lark_tree: Internal - Lark tree to extract position info from
        """
        self.kids = list(kids) if kids else []
        self.position = (None, None)

    def __repr__(self):
        """Compact representation showing type and key attributes."""
        attrs = []
        if self.kids:
            attrs.append(f'*{len(self.kids)}')
        for key, value in self.__dict__.items():
            if key not in ('kids', 'position'):
                attrs.append(f'{key}={value!r}')
        return f"{self.__class__.__name__}({' '.join(attrs)})"

    def tree(self, indent=0):
        """Print tree structure."""
        print(f"{'  '*indent}{self!r}")
        for kid in self.kids:
            kid.tree(indent + 1)

    def find(self, node_type):
        """Find first descendant of given type, including self."""
        if isinstance(self, node_type):
            return self
        for kid in self.kids:
            if result := kid.find(node_type):
                return result
        return None

    def find_all(self, node_type):
        """Find all descendants of given type, including self."""
        results = [self] if isinstance(self, node_type) else []
        for kid in self.kids:
            results.extend(kid.find_all(node_type))
        return results

    def unparse(self) -> str:
        """Convert back to Comp source representation."""
        return "???"

    @classmethod
    def fromGrammar(cls, lark_tree):
        """Create node from Lark parse tree.

        Default implementation for nodes that just need to collect children.
        Override for nodes with specific parsing logic.
        """
        return cls()


class Root(AstNode):
    """Root of grammar Ast."""
    def unparse(self) -> str:
        return " ".join(kid.unparse() for kid in self.kids)


# === LITERALS ===


class Number(AstNode):
    """Numeric literal."""

    def __init__(self, value: decimal.Decimal = decimal.Decimal(0)):
        self.value = value
        super().__init__()

    def unparse(self) -> str:
        return str(self.value)

    @classmethod
    def fromGrammar(cls, tree):
        """Parse number from Lark tree: number -> INTBASE | DECIMAL"""
        token = tree.children[0]
        try:
            if token.type == "INTBASE":
                python_int = int(token.value, 0)  # Auto-detect base
                value = decimal.Decimal(python_int)
            else:  # DECIMAL
                value = decimal.Decimal(token.value)
            return cls(value=value)
        except (ValueError, decimal.InvalidOperation) as e:
            raise ParseError(f"Invalid number: {token.value}") from e


class String(AstNode):
    """String literal."""

    def __init__(self, value: str = ""):
        self.value = value
        super().__init__()

    def unparse(self) -> str:
        # Escape quotes and backslashes
        escaped = self.value.replace('\\', '\\\\').replace('"', '\\"')
        return f'"{escaped}"'

    @classmethod
    def fromGrammar(cls, tree):
        """Parse string from Lark tree: string -> QUOTE content? QUOTE"""
        kids = tree.children
        # kids: [QUOTE, content, QUOTE] or [QUOTE, QUOTE] for empty string
        if len(kids) == 3:
            return cls(value=kids[1].value)
        else:
            return cls(value="")


class BinaryOp(AstNode):
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
    def fromGrammar(cls, tree):
        """Parse binary operation from Lark tree."""
        return cls(tree.children[1].value)

class UnaryOp(AstNode):
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
    def fromGrammar(cls, tree):
        """Parse string from Lark tree: string -> QUOTE content? QUOTE"""
        return cls(tree.children[0].value)


# === STRUCTURES ===


class Structure(AstNode):
    """Structure literal: { ... }"""

    def unparse(self) -> str:
        if not self.kids:
            return "{}"
        items = " ".join(kid.unparse() for kid in self.kids)
        return f"{{{items}}}"


class Block(Structure):
    """Block literal: :{ ... }"""

    def unparse(self) -> str:
        return ":" + super().unparse()


class StructAssign(AstNode):
    """Structure assignment: key = value"""

    def __init__(self, op: str = "="):
        self.op = op
        super().__init__()

    def unparse(self) -> str:
        # First kid is the identifier/key, second is the value
        if len(self.kids) >= 2:
            key = self.kids[0].unparse()
            value = self.kids[1].unparse()
            return f"{key} {self.op} {value}"
        return "??? = ???"

    @classmethod
    def fromGrammar(cls, tree):
        """Parse from Lark tree: structure_assign -> _qualified _assignment_op expression"""
        kids = tree.children
        op_token = next((k for k in kids if hasattr(k, 'type')), None)
        return cls(op=op_token.value if op_token else '=')


class StructUnnamed(AstNode):
    """Structure unnamed value: expression"""

    def unparse(self) -> str:
        if self.kids:
            return self.kids[0].unparse()
        return "???"


class StructSpread(AstNode):
    """Structure spread: ..expression"""

    def unparse(self) -> str:
        if self.kids:
            return f"..{self.kids[0].unparse()}"
        return "..???"


# === IDENTIFIERS AND FIELDS ===


class TokenField(AstNode):
    """Token field: simple name like 'foo' or 'bar-baz'"""

    def __init__(self, value: str = ""):
        self.value = value
        super().__init__()

    def unparse(self) -> str:
        return self.value

    @classmethod
    def fromGrammar(cls, tree):
        """Parse from Lark tree: tokenfield -> TOKEN"""
        return cls(value=tree.children[0].value)


class IndexField(AstNode):
    """Index field: #0, #1, #2, etc."""

    def __init__(self, value: int = 0):
        self.value = value
        super().__init__()

    def unparse(self) -> str:
        return f"#{self.value}"

    @classmethod
    def fromGrammar(cls, tree):
        """Parse from Lark tree: indexfield -> INDEXFIELD"""
        return cls(value=int(tree.children[0].value[1:]))


class ComputeField(AstNode):
    """Computed field: 'expression' in single quotes"""

    def unparse(self) -> str:
        if self.kids:
            return f"'{self.kids[0].unparse()}'"
        return "'???'"


class Identifier(AstNode):
    """Identifier: chain of fields like foo.bar or @foo.bar or foo."baz".#0"""

    def unparse(self) -> str:
        if not self.kids:
            return "???"

        tokens = [kid.unparse() for kid in self.kids]
        if len(tokens) >= 2 and tokens[0] in ("@", "^"):
            tokens[:2] = [tokens[0] + tokens[1]]
        return ".".join(tokens)


class ScopeField(AstNode):
    """Scope marker field: @, ^, or $name - used as first field in an Identifier"""

    def __init__(self, value: str = "@"):
        self.value = value
        super().__init__()

    def unparse(self) -> str:
        return self.value

    @classmethod
    def fromGrammar(cls, tree):
        """Parse from Lark tree: localscope/argscope/namescope"""
        if tree.data == 'localscope':
            return cls(value="@")
        elif tree.data == 'argscope':
            return cls(value="^")
        elif tree.data == 'namescope':
            # kids[0] is namescope, kids[1] should be TOKEN
            return cls(value="$" + tree.children[1].value)


class StringField(String):
    """String literal used in an identifier"""


class FieldAccess(AstNode):
    """Field access on an expression: (expr).field"""

    def unparse(self) -> str:
        return ".".join(kid.unparse() for kid in self.kids)


# === PLACEHOLDER ===


class Placeholder(AstNode):
    """Placeholder: ??? for unknown values"""

    def __init__(self):
        super().__init__()

    def unparse(self) -> str:
        return "???"


# === PIPELINES ===


class Pipeline(AstNode):
    """Pipeline expression: expr | op1 | op2"""

    def unparse(self) -> str:
        value = " ".join(kid.unparse() for kid in self.kids)
        if isinstance(self.kids[0], PipelineOp):
            return f"({value})"
        return value


class PipelineOp(AstNode):
    """Shared base class for all pipeline operators."""


class PipeFallback(PipelineOp):
    """Pipe fallback: |? expr"""

    def unparse(self) -> str:
        if self.kids:
            return f"|? {self.kids[0].unparse()}"
        return "|? ???"


class PipeStruct(PipelineOp):
    """Pipe struct: |{ ops }"""

    def unparse(self) -> str:
        if self.kids:
            items = " ".join(kid.unparse() for kid in self.kids)
            return f"|{{{items}}}"
        return "|{ }"


class PipeBlock(PipelineOp):
    """Pipe block: |: qualified"""

    def unparse(self) -> str:
        if self.kids:
            return f"|: {self.kids[0].unparse()}"
        return "|: ???"


class PipeFunc(PipelineOp):
    """Pipe function: | func args"""

    @property
    def func(self):
        return self.kids[0]

    @property
    def args(self):
        return self.kids[1]

    def unparse(self) -> str:
        if self.args and self.args.kids:
            return f"{self.func.unparse()} {self.args.unparse()[1:-1]}"
        else:
            return f"{self.func.unparse()}"


class PipeWrench(PipelineOp):
    """Pipe wrench: |<< func"""

    def unparse(self) -> str:
        return f"|<< {self.kids[0].unparse()}"


# === REFERENCES ===


class _BaseRef(AstNode):
    """Base class for references: TagRef, ShapeRef, FuncRef"""
    SYMBOL = "?"
    def __init__(self, tokens:list[str]|None=None, namespace:str|None=None):
        self.tokens = tokens
        self.namespace = namespace
        super().__init__()

    def unparse(self) -> str:
        path = ".".join(self.tokens)
        full = "/".join((path, self.namespace)) if self.namespace else path
        return f"{self.SYMBOL}{full}"

    @classmethod
    def fromGrammar(cls, tree):
        """Parse from Lark tree: tag_reference -> "#" _reference_path"""
        tokens = []
        namespace = None
        for token in tree.children[1].children:
            value = token.value
            if value != ".":
                tokens.append(value)
        if len(tree.children) > 2:
            namespace = tree.children[2].children[1].value
        return cls(tokens=tuple(tokens), namespace=namespace)


class TagRef(_BaseRef):
    """Tag reference: #path"""
    SYMBOL = "#"


class ShapeRef(_BaseRef):
    """Shape reference: ~path"""
    SYMBOL = "~"


class FuncRef(_BaseRef):
    """Function reference: |path"""
    SYMBOL = "|"

