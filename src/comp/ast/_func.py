"""Ast nodes for functions and pipelines"""

__all__ = [
    "FuncDef",
    "FuncRef",
    "Pipeline",
    "PipeFallback",
    "PipeStruct",
    "PipeBlock",
    "PipeFunc",
    "PipeWrench",
]

from . import _node
import comp



class FuncDef(_node.Node):
    """Function definition at module level"""

    def __init__(self, tokens: list[str] | None = None, assign_op: str = "="):
        self.tokens = list(tokens) if tokens else []
        self.assign_op = assign_op
        self._argIdx = self._bodIdx = None
        super().__init__()

    @property
    def name(self):
        """Get the function name as a dotted string (for compatibility)."""
        return ".".join(self.tokens)

    @property
    def shape(self):
        """Get the input shape (first child, always present)."""
        return self.kids[0] if self.kids else None

    @property
    def args(self):
        """Get the args shape (can be shape reference, inline shape, etc., or None)."""
        return self.kids[self._argIdx] if self._argIdx is not None else None

    @property
    def body(self):
        """Get the function body structure (third child, always present)."""
        return self.kids[self._bodIdx] if self._bodIdx is not None else None

    def unparse(self) -> str:
        parts = ["!func", "|" + ".".join(self.tokens)]
        if self.shape:
            parts.append(self.shape.unparse())
        args = self.args
        if args:
            parts.append("^" + args.unparse())
        if self.assign_op:
            parts.append(self.assign_op)
        if self.body:
            parts.append(self.body.unparse())
        return " ".join(parts)

    @classmethod
    def from_grammar(cls, tree):
        """Parse from grammar tree using rule aliases to distinguish cases."""
        tokens = [t.value for t in tree.children[1].children[1::2]]

        if tree.data == "func_with_args":
            # After walk, kids will be: [shape, args, body]
            assign_op_token = tree.children[4]  # Get from tree before walk
            assign_op = assign_op_token.value if hasattr(assign_op_token, 'value') else str(assign_op_token)
            self = cls(tokens=tokens, assign_op=assign_op)
            self._argIdx = 1  # args is second in kids
            self._bodIdx = 2  # body is third in kids
        else:  # func_no_args
            # After walk, kids will be: [shape, body]
            assign_op_token = tree.children[3]  # Get from tree before walk
            assign_op = assign_op_token.value if hasattr(assign_op_token, 'value') else str(assign_op_token)
            self = cls(tokens=tokens, assign_op=assign_op)
            self._argIdx = None  # No args
            self._bodIdx = 1  # body is second in kids

        return self


class FuncRef(_node.BaseRef):
    """Function reference: |path"""
    SYMBOL = "|"


class Pipeline(_node.Node):
    """Pipeline expression in square brackets"""

    def __init__(self):
        self._seedIdx = None
        super().__init__()

    @property
    def seed(self):
        """The seed expression (None if unseeded pipeline)."""
        return self.kids[self._seedIdx] if self._seedIdx is not None else None

    @property
    def operations(self):
        """List of pipeline operations (all children if no seed, or all after seed)."""
        if self._seedIdx is not None:
            return self.kids[self._seedIdx + 1:]
        else:
            return self.kids[:]

    def unparse(self) -> str:
        parts = []
        for kid in self.kids:
            parts.append(kid.unparse())

        value = " ".join(parts)
        # Pipelines now use square brackets
        return f"[{value}]"

    @classmethod
    def from_grammar(cls, tree):
        node = cls()

        # Check the rule alias to determine seed index
        if tree.data == 'pipeline_unseeded':
            # No seed - operations start at kids[0]
            node._seedIdx = None
        else:  # pipeline_seeded
            # Seed at kids[0], operations start at kids[1]
            node._seedIdx = 0

        return node


class PipelineOp(_node.Node):
    """Pipeline op base class."""


class PipeFallback(PipelineOp):
    """Pipeline op to handle failures."""

    @property
    def fallback(self):
        """The fallback expression (first child)."""
        return self.kids[0] if self.kids else None

    def unparse(self) -> str:
        if self.kids:
            return f"|? {self.fallback.unparse()}"
        return "|? ???"


class PipeStruct(PipelineOp):
    """Pipeline op to define new structure."""

    def unparse(self) -> str:
        if self.kids:
            items = " ".join(kid.unparse() for kid in self.kids)
            return f"|{{{items}}}"
        return "|{ }"


class PipeBlock(PipelineOp):
    """Pipeline op invoke a block."""

    @property
    def block(self):
        """The block identifier (first child)."""
        return self.kids[0] if self.kids else None

    def unparse(self) -> str:
        if self.kids:
            return f"|: {self.block.unparse()}"
        return "|: ???"


class PipeFunc(PipelineOp):
    """Pipeline op invoke a function."""

    @property
    def func(self):
        """The function reference (first child)."""
        return self.kids[0] if self.kids else None

    @property
    def args(self):
        """The function arguments structure (second child)."""
        return self.kids[1] if len(self.kids) > 1 else None

    def unparse(self) -> str:
        if self.args and self.args.kids:
            return f"{self.func.unparse()} {self.args.unparse()[1:-1]}"
        else:
            return f"{self.func.unparse()}"


class PipeWrench(PipelineOp):
    """Pipeline op to modify pipeline in-place"""

    @property
    def wrench(self):
        """The wrench function reference (first child)."""
        return self.kids[0] if self.kids else None

    def unparse(self) -> str:
        if self.kids:
            return f"|-| {self.wrench.unparse()}"
        return "|-| ???"

