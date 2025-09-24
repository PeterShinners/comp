"""
AST node definitions and exceptions for Comp language.

This module defines the Abstract Syntax Tree nodes used to represent parsed Comp code.
Currently supports number and string literals, designed to grow with the full language.
"""

__all__ = ["ASTNode", "NumberLiteral", "StringLiteral", "Identifier", "ParseError"]

import ast
import decimal
from typing import Any


class ParseError(Exception):
    """Raised when parsing fails due to invalid syntax."""

    def __init__(
        self, message: str, line: int | None = None, column: int | None = None
    ):
        super().__init__(message)
        self.line = line
        self.column = column


class ASTNode:
    """Base class for all AST nodes."""

    def __init__(self):
        # Location information for error reporting (future)
        self.line: int | None = None
        self.column: int | None = None

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(...)"


class NumberLiteral(ASTNode):
    """AST node representing a number literal."""

    def __init__(self, value: decimal.Decimal):
        super().__init__()
        self.value = value

    @classmethod
    def fromToken(cls, token):
        """Create NumberLiteral from a Lark token."""
        number_text = str(token)

        try:
            # Handle based integers (0x, 0b, 0o) with ast.literal_eval
            if token.type == "BASED":
                python_int = ast.literal_eval(number_text)
                decimal_value = decimal.Decimal(python_int)
            else:  # DECIMAL types
                # Direct conversion for decimal precision preservation
                decimal_value = decimal.Decimal(number_text)

            return cls(decimal_value)

        except (decimal.InvalidOperation, ValueError) as err:
            raise ParseError(f"Invalid number syntax: {number_text}") from err
        except SyntaxError as err:
            raise ParseError(f"Invalid number format: {err.args[0]}") from err

    def __repr__(self) -> str:
        return f"NumberLiteral({self.value})"

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, NumberLiteral):
            return False
        return self.value == other.value

    def __hash__(self) -> int:
        return hash(self.value)


class StringLiteral(ASTNode):
    """AST node representing a string literal."""

    def __init__(self, value: str):
        super().__init__()
        self.value = value

    @classmethod
    def fromToken(cls, token):
        """Create StringLiteral from a Lark token."""
        string_text = str(token)

        try:
            # Use Python's built-in string literal parsing
            processed = ast.literal_eval(string_text)
            return cls(processed)

        except (ValueError, SyntaxError) as err:
            raise ParseError(f"Invalid string literal: {string_text}") from err

    def __repr__(self) -> str:
        return f"StringLiteral({self.value!r})"

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, StringLiteral):
            return False
        return self.value == other.value

    def __hash__(self) -> int:
        return hash(self.value)


class Identifier(ASTNode):
    """AST node representing an identifier (variable name, etc)."""

    def __init__(self, name: str):
        super().__init__()
        self.name = name

    def __repr__(self) -> str:
        return f"Identifier({self.name!r})"

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Identifier):
            return False
        return self.name == other.name

    def __hash__(self) -> int:
        return hash(self.name)
