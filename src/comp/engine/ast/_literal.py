"""Nodes for literal values."""

__all__ = ["Number", "String", "Placeholder"]

import comp.engine as comp
from . import _base


class Number(_base.ValueNode):
    """Numeric literal."""

    def __init__(self, value: int | float):
        self.value = value

    def evaluate(self, frame):
        """Numbers evaluate to themselves."""
        return comp.Value(self.value)
        yield  # Make it a generator

    def unparse(self) -> str:
        """Convert back to source code."""
        return str(self.value)

    def __repr__(self):
        return f"Number({self.value})"


class String(_base.ValueNode):
    """String literal."""

    def __init__(self, value: str):
        self.value = value

    def evaluate(self, frame):
        """Strings evaluate to themselves."""
        return comp.Value(self.value)
        yield  # Make it a generator

    def unparse(self) -> str:
        """Convert back to source code."""
        # Escape quotes and backslashes
        escaped = self.value.replace('\\', '\\\\').replace('"', '\\"')
        return f'"{escaped}"'

    def __repr__(self):
        return f"String({self.value!r})"


class Placeholder(_base.ValueNode):
    """Placeholder literal"""

    def evaluate(self, frame):
        """Strings evaluate to themselves."""
        return comp.fail("Placeholder --- cannot be evaluated")
        yield  # generator

    def unparse(self) -> str:
        """Convert back to source code."""
        return "---"

    def __repr__(self):
        return f"Placeholder(---)"
