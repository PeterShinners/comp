"""
AST node definitions for Comp language

This module defines a simplified Abstract Syntax Tree for the Comp language.

"""

__all__ = [
    "Pipeline",
    "PipeFallback",
    "PipeStruct",
    "PipeBlock",
    "PipeFunc",
    "PipeWrench",
]

from . import _node


class Pipeline(_node.Node):
    """Pipeline expression: [expr |op1 |op2] or [|op1 |op2]

    If no explicit seed is provided (pipeline_unseeded), the seed property returns None.
    Remaining children are PipelineOp subclasses (PipeFunc, PipeFallback, etc).
    """

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
        """Create Pipeline node using rule alias to determine if seed is present.

        Uses rule aliases:
        - 'pipeline_unseeded': [|op ...] - no seed, operations start at kids[0]
        - 'pipeline_seeded': [expr |op ...] - has seed at kids[0], operations after
        """
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
    """Shared base class for all pipeline operators."""


class PipeFallback(PipelineOp):
    """Pipe fallback: |? expr"""

    @property
    def fallback(self):
        """The fallback expression (first child)."""
        return self.kids[0] if self.kids else None

    def unparse(self) -> str:
        if self.kids:
            return f"|? {self.fallback.unparse()}"
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

    @property
    def block(self):
        """The block identifier (first child)."""
        return self.kids[0] if self.kids else None

    def unparse(self) -> str:
        if self.kids:
            return f"|: {self.block.unparse()}"
        return "|: ???"


class PipeFunc(PipelineOp):
    """Pipe function: | func args"""

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
    """Pipe wrench: |-| func"""

    @property
    def wrench(self):
        """The wrench function reference (first child)."""
        return self.kids[0] if self.kids else None

    def unparse(self) -> str:
        if self.kids:
            return f"|-| {self.wrench.unparse()}"
        return "|-| ???"

