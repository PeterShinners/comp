"""Generator-based evaluation engine.

This is a clean-room implementation focused on:

- Immutable AST nodes with evaluate() generators
- Engine class with dual stacks (context + scope)
- Stackless execution with explicit generator management
- Elegant fail propagation with context managers
- No AST mutation during evaluation
"""

from .engine import Engine
from .value import Value
from . import ast

__all__ = [
    "Engine",
    "Value",
    "ast",
]
