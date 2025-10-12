"""Node for base classes."""

__all__ = ["AstNode", "ValueNode", "FieldNode", "ShapeNode"]

from collections.abc import Generator

import comp


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
