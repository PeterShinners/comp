"""
Number parsing for Comp language - Phase 02

This module provides parsing functionality specifically for Comp number literals.
It will grow over time to support the full Comp language.
"""

__all__ = ["parse_numbers"]

import ast
import decimal
from pathlib import Path

from lark import Lark, Tree

from . import _ast


class NumberParser:
    """Parser for Comp number literals using Lark grammar."""

    def __init__(self):
        # Load main grammar file
        grammar_path = Path(__file__).parent / "lark" / "comp.lark"
        with open(grammar_path) as f:
            grammar = f.read()

        # Set up parser with import path for modular grammars
        import_paths = [Path(__file__).parent / "lark"]
        self.parser = Lark(grammar, start="start", import_paths=import_paths)

    def parse(self, text: str) -> Tree:
        """Parse text containing whitespace-separated numbers."""
        return self.parser.parse(text)

    def parse_number(self, text: str) -> _ast.NumberLiteral:
        """Parse a single number literal to NumberLiteral AST node."""
        # Parse and extract the first number from the tree
        tree = self.parser.parse(text.strip())
        # Navigate: start -> number_list -> number (token directly)
        number_list = tree.children[0]  # number_list
        number_node = number_list.children[0]  # number
        decimal_value = self._convert_number_node(number_node)
        return _ast.NumberLiteral(decimal_value)

    def _convert_number_node(self, node: Tree) -> decimal.Decimal:
        """Convert a parsed number tree node to decimal.Decimal."""
        # With simplified grammar, node.children[0] is the token directly
        token = node.children[0]
        number_text = str(token)

        # Validate base-specific patterns before processing
        self._validate_number_format(number_text)

        # Determine type by checking for decimal indicators
        has_dot = '.' in number_text
        # Check for scientific notation: 'e' followed by optional +/- and digits
        import re
        has_exponent = bool(re.search(r'e[+-]?\d', number_text, re.IGNORECASE))

        if has_dot or has_exponent:
            # Decimal formats: pass directly to Decimal to avoid float precision loss
            return decimal.Decimal(number_text)
        else:
            # Integer formats: use ast.literal_eval to handle all bases/signs/underscores
            python_int = ast.literal_eval(number_text)
            return decimal.Decimal(python_int)

    def _validate_number_format(self, number_text: str) -> None:
        """Validate number format and provide specific error messages for invalid base numbers."""
        import re

        # Remove sign for pattern matching
        unsigned = number_text.lstrip('+-')

        # Check for invalid binary numbers (0b prefix with non-binary digits)
        if re.match(r'0[bB]', unsigned):
            if not re.match(r'0[bB][01_]+$', unsigned):
                raise ValueError(f"Invalid binary number '{number_text}': contains non-binary digits")

        # Check for invalid octal numbers (0o prefix with non-octal digits)
        elif re.match(r'0[oO]', unsigned):
            if not re.match(r'0[oO][0-7_]+$', unsigned):
                raise ValueError(f"Invalid octal number '{number_text}': contains non-octal digits")

        # Check for invalid hex numbers (0x prefix with invalid characters)
        elif re.match(r'0[xX]', unsigned):
            if not re.match(r'0[xX][0-9a-fA-F_]+$', unsigned):
                raise ValueError(f"Invalid hexadecimal number '{number_text}': contains invalid hex digits")


# Convenience function for quick testing
def parse_numbers(text: str) -> list[_ast.NumberLiteral]:
    """Parse whitespace-separated numbers from text."""
    parser = NumberParser()
    tree = parser.parse(text)

    numbers = []
    # Navigate: start -> number_list -> [number, number, ...]
    number_list = tree.children[0]  # number_list
    for number_node in number_list.children:
        if number_node:  # Skip empty nodes
            # With simplified grammar, number_node contains the token directly
            decimal_value = parser._convert_number_node(number_node)
            ast_node = _ast.NumberLiteral(decimal_value)
            numbers.append(ast_node)

    return numbers


# Quick test function
if __name__ == "__main__":
    # Compact smoke test covering all number formats
    test_cases = [
        "42 -3.14 1e-2",  # Basic decimal formats
        "0b1010 0o755 0xFF_FF",  # Alternative bases with underscores
        "+.5 -0b11 +0x10",  # Signed numbers (new feature)
    ]
    for test in test_cases:
        try:
            numbers = parse_numbers(test)
            print(f"'{test}' -> {numbers}")
        except Exception as e:
            print(f"'{test}' -> ERROR: {e}")
