"""
Number parsing for Comp language - Phase 02

This module provides parsing functionality specifically for Comp number literals.
It will grow over time to support the full Comp language.
"""

__all__ = ["parse_numbers"]

import ast
import decimal
from pathlib import Path

import lark

from . import _ast, _parser


class NumberParser:
    """Parser for Comp number literals using Lark grammar."""

    def __init__(self):
        # Load main grammar file
        grammar_path = Path(__file__).parent / "lark" / "comp.lark"
        with open(grammar_path) as f:
            grammar = f.read()

        # Set up parser with import path for modular grammars
        import_paths = [Path(__file__).parent / "lark"]
        self.parser = lark.Lark(grammar, start="start", import_paths=import_paths)

    def parse(self, text: str) -> lark.Tree:
        """Parse text containing whitespace-separated numbers."""
        return self.parser.parse(text)

    def parse_number(self, text: str) -> _ast.NumberLiteral:
        """Parse a single number literal to NumberLiteral AST node."""
        # Parse and extract the first number from the tree
        tree = self.parser.parse(text.strip())
        # Navigate: start -> number_list -> number (token directly)
        number_list = tree.children[0]  # number_list
        number_node = number_list.children[0]  # number
        decimal_value = self._convert_number_token(number_node.children[0])
        return _ast.NumberLiteral(decimal_value)

    def _convert_number_token(self, token: lark.Token) -> decimal.Decimal:
        """Convert a parsed number tree node to decimal.Decimal."""
        number = str(token)
        try:
            if "DECIMAL" not in token.type:
                number = ast.literal_eval(number)
            return decimal.Decimal(number)

        except (decimal.InvalidOperation, ValueError) as err:
            raise _parser.ParseError(f"Invalid number syntax: {number}") from err
        except SyntaxError as err:
            raise _parser.ParseError(err.args[0]) from err


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
            decimal_value = parser._convert_number_token(number_node.children[0])
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
