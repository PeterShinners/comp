"""Generator-based evaluation engine - proof of concept.

This is a clean-room implementation to explore generator-based evaluation
separate from the existing runtime. It demonstrates:

- AST nodes with evaluate() generators
- EvalContext managing execution (recursive or stackless)
- Automatic skip value propagation
- No manual short-circuit checks in AST nodes
"""

from .context import EvalContext
from .value import Value
from .nodes import Number, String, BinaryOp, UnaryOp

__all__ = [
    "EvalContext",
    "Value", 
    "Number",
    "String",
    "BinaryOp",
    "UnaryOp",
]
