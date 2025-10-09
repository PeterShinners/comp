"""AST nodes designed for evaluation.

This is a clean-room redesign of AST nodes focused on the evaluate() protocol
rather than parser translation. Each node knows how to evaluate itself using
generators and the Engine.

Node hierarchies by coordination requirements:
- ValueNode: Self-contained nodes (most common)
- FieldNode: Nodes requiring field_value context from parent (coordination)
- ShapeNode: Type domain nodes
"""

from .base import AstNode, ValueNode, FieldNode, ShapeNode
from .identifiers import (
    Identifier,
    Field,
    ScopeField,
    TokenField,
    IndexField,
    ComputeField,
    ImplicitField,
)
from .literals import Number, String
from .operators import ArithmeticOp, ComparisonOp, BooleanOp, UnaryOp

__all__ = [
    "AstNode",
    "ValueNode",
    "FieldNode",
    "ShapeNode",
    "Identifier",
    "Field",
    "ScopeField",
    "TokenField",
    "IndexField",
    "ComputeField",
    "ImplicitField",
    "Number",
    "String",
    "ArithmeticOp",
    "ComparisonOp",
    "BooleanOp",
    "UnaryOp",
]
