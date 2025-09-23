"""
Main parser interface for the Comp language.

This module provides the primary parse() function that handles single expressions.
It's built on top of the number parsing infrastructure but will eventually
handle all Comp language constructs.

DESIGN GOALS:
- Simple public API: parse(text) → ASTNode
- Clear error messages with source location
- Extensible for all future language features

CURRENT CAPABILITIES:
- Number literals (all formats)

FUTURE CAPABILITIES:
- String literals
- Tag literals
- Structure literals
- Expressions
- Everything else
"""

from lark import ParseError as LarkParseError

from . import _ast, _numbers

__all__ = ["parse", "ParseError"]


class ParseError(Exception):
    """Raised when parsing fails due to invalid syntax."""

    def __init__(
        self, message: str, line: int | None = None, column: int | None = None
    ):
        super().__init__(message)
        self.line = line
        self.column = column


def parse(text: str) -> _ast.ASTNode:
    """
    Parse a single Comp expression from text.

    Args:
        text: The source text to parse

    Returns:
        An AST node representing the parsed expression

    Raises:
        ParseError: If the text cannot be parsed

    Examples:
        >>> parse("42")
        NumberLiteral(42)
        >>> parse("0xFF")
        NumberLiteral(255)
        >>> parse("3.14")
        NumberLiteral(3.14)
    """
    text = text.strip()
    if not text:
        raise ParseError("Empty input")

    # For now, we only handle numbers
    # Try to parse as a single number first
    try:
        # Use our existing number parser
        numbers = _numbers.parse_numbers(text)
        if len(numbers) == 1:
            return numbers[0]
        elif len(numbers) > 1:
            raise ParseError(f"Expected single expression, got {len(numbers)} numbers")
        else:
            raise ParseError("No valid expression found")
    except LarkParseError as e:
        # Convert Lark errors to our ParseError
        raise ParseError(f"Syntax error: {e}") from e
    except Exception as e:
        raise ParseError(f"Parse error: {e}") from e
