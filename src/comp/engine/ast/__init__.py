"""AST nodes designed for evaluation.

This is a clean-room redesign of AST nodes focused on the evaluate() protocol
rather than parser translation. Each node knows how to evaluate itself using
generators and the Engine.

Node hierarchies by coordination requirements:
- ValueNode: Self-contained nodes (most common)
- FieldNode: Nodes requiring field_value context from parent (coordination)
- ShapeNode: Type domain nodes
"""

from .base import AstNode, FieldNode, ShapeNode, ValueNode
from .identifiers import (
    ComputeField,
    Identifier,
    IndexField,
    ScopeField,
    TokenField,
)
from .literals import Number, String
from .operators import ArithmeticOp, BooleanOp, ComparisonOp, UnaryOp
from .pipelines import PipeFallback, PipeFunc, Pipeline, PipelineOp, PipeStruct
from .structures import FieldOp, SpreadOp, Structure, StructOp

__all__ = [
    "AstNode",
    "ValueNode",
    "FieldNode",
    "ShapeNode",
    "Identifier",
    "ScopeField",
    "TokenField",
    "IndexField",
    "ComputeField",
    "Number",
    "String",
    "ArithmeticOp",
    "ComparisonOp",
    "BooleanOp",
    "UnaryOp",
    "Structure",
    "StructOp",
    "FieldOp",
    "SpreadOp",
    "Pipeline",
    "PipelineOp",
    "PipeFunc",
    "PipeStruct",
    "PipeFallback",
]
