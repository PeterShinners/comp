"""
AST node definitions and exceptions for Comp language.

This module defines the Abstract Syntax Tree nodes used to represent parsed Comp code.
Currently supports number and string literals, identifiers, and reference literals.
"""

__all__ = [
    "ASTNode",
    "NumberLiteral",
    "StringLiteral",
    "Identifier",
    "TagReference",
    "ShapeReference",
    "FunctionReference",
    "StructureLiteral",
    "NamedField",
    "PositionalField",
    "BinaryOperation",
    "UnaryOperation",
    "ParseError",
]

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
        try:
            # Handle based integers (0x, 0b, 0o) with ast.literal_eval
            # Check for both old and new token type names (with mathematical_operators prefix)
            if token.type == "BASED" or token.type.endswith("__BASED"):
                python_int = ast.literal_eval(str(token))
                decimal_value = decimal.Decimal(python_int)
            else:  # DECIMAL types
                decimal_value = decimal.Decimal(str(token))

            return cls(decimal_value)

        except SyntaxError as err:
            # Pass through literal_eval's better error messages
            raise ParseError(f"Invalid number: {err.args[0]}") from err
        except (decimal.InvalidOperation, ValueError) as err:
            raise ParseError(f"Invalid number syntax: {token}") from err

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


class TagReference(ASTNode):
    """AST node representing a tag reference (#tag)."""

    def __init__(self, name: str):
        super().__init__()
        self.name = name

    @classmethod
    def fromToken(cls, token):
        """Create TagReference from a Lark token (without the # sigil)."""
        # Token contains the identifier path without the sigil
        return cls(str(token))

    def __repr__(self) -> str:
        return f"TagReference({self.name!r})"

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, TagReference):
            return False
        return self.name == other.name

    def __hash__(self) -> int:
        return hash(self.name)


class ShapeReference(ASTNode):
    """AST node representing a shape reference (~shape)."""

    def __init__(self, name: str):
        super().__init__()
        self.name = name

    @classmethod
    def fromToken(cls, token):
        """Create ShapeReference from a Lark token (without the ~ sigil)."""
        # Token contains the identifier path without the sigil
        return cls(str(token))

    def __repr__(self) -> str:
        return f"ShapeReference({self.name!r})"

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, ShapeReference):
            return False
        return self.name == other.name

    def __hash__(self) -> int:
        return hash(self.name)


class FunctionReference(ASTNode):
    """AST node representing a function reference (|function)."""

    def __init__(self, name: str):
        super().__init__()
        self.name = name

    @classmethod
    def fromToken(cls, token):
        """Create FunctionReference from a Lark token (without the | sigil)."""
        # Token contains the identifier path without the sigil
        return cls(str(token))

    def __repr__(self) -> str:
        return f"FunctionReference({self.name!r})"

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, FunctionReference):
            return False
        return self.name == other.name

    def __hash__(self) -> int:
        return hash(self.name)


class StructureLiteral(ASTNode):
    """AST node representing a structure literal {...}."""

    def __init__(self, fields: list[ASTNode]):
        super().__init__()
        self.fields = fields

    @classmethod
    def fromToken(cls, tokens):
        """Create StructureLiteral from a list of field tokens."""
        # tokens is a list of NamedField and PositionalField nodes
        return cls(tokens)

    def __repr__(self) -> str:
        return f"StructureLiteral({self.fields!r})"

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, StructureLiteral):
            return False
        return self.fields == other.fields

    def __hash__(self) -> int:
        return hash(tuple(self.fields))


class NamedField(ASTNode):
    """AST node representing a named field in a structure (key=value)."""

    def __init__(self, name: str, value: ASTNode):
        super().__init__()
        self.name = name
        self.value = value

    @classmethod
    def fromToken(cls, tokens):
        """Create NamedField from key and value tokens."""
        # tokens[0] is the key (identifier or string), tokens[1] is the value
        key = tokens[0]
        value = tokens[1]

        # Extract the name from the key AST node
        if isinstance(key, Identifier):
            name = key.name
        elif isinstance(key, StringLiteral):
            name = key.value
        else:
            raise ParseError(f"Invalid field name type: {type(key)}")

        return cls(name, value)

    def __repr__(self) -> str:
        return f"NamedField({self.name!r}, {self.value!r})"

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, NamedField):
            return False
        return self.name == other.name and self.value == other.value

    def __hash__(self) -> int:
        return hash((self.name, self.value))


class PositionalField(ASTNode):
    """AST node representing a positional field in a structure (value)."""

    def __init__(self, value: ASTNode):
        super().__init__()
        self.value = value

    @classmethod
    def fromToken(cls, tokens):
        """Create PositionalField from value token."""
        # tokens[0] is the value expression
        value = tokens[0]
        return cls(value)

    def __repr__(self) -> str:
        return f"PositionalField({self.value!r})"

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, PositionalField):
            return False
        return self.value == other.value

    def __hash__(self) -> int:
        return hash(self.value)


class BinaryOperation(ASTNode):
    """AST node representing a binary operation (left operator right)."""

    def __init__(self, left: ASTNode, operator: str, right: ASTNode):
        super().__init__()
        self.left = left
        self.operator = operator
        self.right = right

    @classmethod
    def fromToken(cls, tokens):
        """Create BinaryOperation from tokens: [left, operator, right]."""
        left, operator, right = tokens
        return cls(left, str(operator), right)

    def __repr__(self) -> str:
        return f"BinaryOperation({self.left!r}, {self.operator!r}, {self.right!r})"

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, BinaryOperation):
            return False
        return (
            self.left == other.left
            and self.operator == other.operator
            and self.right == other.right
        )

    def __hash__(self) -> int:
        return hash((self.left, self.operator, self.right))


class UnaryOperation(ASTNode):
    """AST node representing a unary operation (operator operand)."""

    def __init__(self, operator: str, operand: ASTNode):
        super().__init__()
        self.operator = operator
        self.operand = operand

    @classmethod
    def fromToken(cls, tokens):
        """Create UnaryOperation from tokens: [operator, operand]."""
        operator, operand = tokens
        return cls(str(operator), operand)

    def __repr__(self) -> str:
        return f"UnaryOperation({self.operator!r}, {self.operand!r})"

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, UnaryOperation):
            return False
        return self.operator == other.operator and self.operand == other.operand

    def __hash__(self) -> int:
        return hash((self.operator, self.operand))
