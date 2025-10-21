"""Node for base classes."""

__all__ = ["AstNode", "ValueNode", "FieldNode", "ShapeNode", "SourcePosition"]

from collections.abc import Generator
from dataclasses import dataclass

import comp


@dataclass
class SourcePosition:
    """Source code position information for AST nodes.
    
    Tracks where an AST node originated in the source code,
    useful for error messages and debugging.
    
    Attributes:
        filename: Source file path (e.g., "examples/greet.comp")
        start_line: Starting line number (1-indexed)
        start_column: Starting column number (1-indexed)
        end_line: Ending line number (1-indexed)
        end_column: Ending column number (1-indexed)
    """
    filename: str | None = None
    start_line: int | None = None
    start_column: int | None = None
    end_line: int | None = None
    end_column: int | None = None
    
    def __str__(self) -> str:
        """Format position for error messages (just line number)."""
        if self.start_line:
            return f"on line {self.start_line}"
        return ""


class AstNode:
    """Base class for all AST nodes.

    AST nodes are immutable structures that describe how Comp works at runtime.
    They are validated on construction and will raise exceptions if invalid.

    They are driven by the `evaluate` generator that returns a computed
    `Value` result and may yield AstNodes to request further evaluation.
    The yield is a two way channel that receives the resulting value from
    the evaluated node.

    This is a base class that should not be instantiated directly.
    Subclasses must implement evaluate() and unparse().
    
    Attributes:
        position: Optional source position information (filename, line, column).
                  Set by parser when creating nodes from source code.
    """

    def evaluate(self, lookup) -> Generator['AstNode', comp.Value, comp.Value]:
        """Evaluate this node to produce a Value.

        Args:
            engine: The Engine managing execution

        Yields:
            Child node instances that need evaluation

        Receives:
            Value instances (results from evaluating children)

        Returns:
            Final Value result
        """
        raise NotImplementedError(f"{self.__class__.__name__}.evaluate() not implemented")

    def unparse(self) -> str:
        """Convert this node back to source code.

        Used for debugging, error messages, and code generation.
        Should produce valid Comp source that parses back to equivalent AST.

        Returns:
            Source code string
        """
        raise NotImplementedError(f"{self.__class__.__name__}.unparse() not implemented")

    def print_tree(self, depth=0):
        """Print ast nodes for debugging."""
        indent = "  " * depth
        print(f"{indent}{self!r}")
        for value in vars(self).values():
            if isinstance(value, AstNode):
                value.print_tree(depth + 1)
            elif isinstance(value, list):
                for child in value:
                    if isinstance(child, AstNode):
                        child.print_tree(depth + 1)

class ValueNode(AstNode):
    """Base class for nodes that evaluate to runtime Values.

    ValueNodes are self-contained: they don't require coordination context
    from their parent (though they may coordinate their own children).

    Examples:
    - Literals: Number, String, Tag
    - Operators: BinaryOp, UnaryOp
    - Structures: Structure, Pipeline
    - Calls: FunctionCall
    - Coordinators: Identifier (coordinates fields)

    This is the most common node type.
    """
    pass


class FieldNode(AstNode):
    """Base class for field access nodes.

    These require an 'identifier' scope in the engine.

    """
    pass


class ShapeNode(AstNode):
    """Base class for nodes that represent shape/type information.

    These nodes evaluate in the shape domain and produce ShapeValue results.
    They cannot be used where regular Values are expected.

    ShapeValues never escape shape contexts - they're compile-time only.

    This is a base class that should not be instantiated directly.
    """
    pass
