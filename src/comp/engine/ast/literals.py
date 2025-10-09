"""Literal value nodes."""

from .base import ValueNode
from ..value import Value


class Number(ValueNode):
    """Numeric literal."""
    
    def __init__(self, value: int | float):
        self.value = value
    
    def evaluate(self, engine):
        """Numbers evaluate to themselves."""
        return Value(self.value)
        yield  # Make it a generator
    
    def unparse(self) -> str:
        """Convert back to source code."""
        return str(self.value)
    
    def __repr__(self):
        return f"Number({self.value})"


class String(ValueNode):
    """String literal."""
    
    def __init__(self, value: str):
        self.value = value
    
    def evaluate(self, engine):
        """Strings evaluate to themselves."""
        return Value(self.value)
        yield  # Make it a generator
    
    def unparse(self) -> str:
        """Convert back to source code."""
        # Escape quotes and backslashes
        escaped = self.value.replace('\\', '\\\\').replace('"', '\\"')
        return f'"{escaped}"'
    
    def __repr__(self):
        return f"String({self.value!r})"
