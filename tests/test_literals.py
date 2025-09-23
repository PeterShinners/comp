"""
Test cases for basic number and string literal parsing.

SPECIFICATION SUMMARY:
This module tests the two most fundamental literal types in Comp - numbers and strings.
This is the absolute minimum needed to start building a parser.

REQUIREMENTS FROM DESIGN DOCS:
- Numbers: All become IEEE 754 doubles, support integers, decimals, scientific notation
- Strings: UTF-8 with standard escape sequences (\", \\, \n, \r, \t)

PARSER EXPECTATIONS:
- parse("42") → NumberLiteral(42.0)
- parse("3.14") → NumberLiteral(3.14)  
- parse('"hello"') → StringLiteral("hello")
- parse('"say \\"hi\\""') → StringLiteral('say "hi"')

ERROR CASES TO HANDLE:
- Invalid numbers: "3.14.15", "1e" (incomplete)
- Invalid strings: "unterminated (missing quote)

AST NODE STRUCTURE:
- NumberLiteral: value (float)
- StringLiteral: value (str)

FUTURE PHASES (not implemented yet):
- Tags: #true, #active, #namespace.item
- Structures: {}, {x=1}, {1 2 3}
- Expressions: 1 + 2, field access
- Everything else
"""

import pytest
from comp.parser import parse
from comp.ast_nodes import NumberLiteral, StringLiteral


class TestNumberLiterals:
    """
    Test parsing of number literals.
    
    DESIGN REQUIREMENT: All numbers become IEEE 754 doubles (design/type.md).
    No integer vs float distinction - everything is a float internally.
    Must support: integers, decimals, scientific notation.
    """
    
    def test_parse_integers(self):
        """Integer literals should become floats."""
        result = parse("42")
        assert isinstance(result, NumberLiteral)
        assert result.value == 42.0
        
        result = parse("-17")
        assert isinstance(result, NumberLiteral) 
        assert result.value == -17.0
        
        result = parse("0")
        assert isinstance(result, NumberLiteral)
        assert result.value == 0.0
    
    def test_parse_decimals(self):
        """Decimal literals."""
        result = parse("3.14")
        assert isinstance(result, NumberLiteral)
        assert result.value == 3.14
        
        result = parse("-2.5")
        assert isinstance(result, NumberLiteral)
        assert result.value == -2.5
        
        result = parse("0.0")
        assert isinstance(result, NumberLiteral)
        assert result.value == 0.0
    
    def test_parse_scientific_notation(self):
        """Scientific notation numbers."""
        result = parse("1e3")
        assert isinstance(result, NumberLiteral)
        assert result.value == 1000.0
        
        result = parse("1.23e-4")
        assert isinstance(result, NumberLiteral)
        assert result.value == 0.000123
        
        result = parse("-2.5e2") 
        assert isinstance(result, NumberLiteral)
        assert result.value == -250.0


class TestStringLiterals:
    """
    Test parsing of string literals.
    
    DESIGN REQUIREMENT: UTF-8 strings with standard escape sequences.
    Must handle: basic strings, escaped quotes, newlines, backslashes.
    Escape sequences: \", \\, \n, \r, \t (standard C-style).
    """
    
    def test_parse_basic_strings(self):
        """Basic string literals."""
        result = parse('"hello"')
        assert isinstance(result, StringLiteral)
        assert result.value == "hello"
        
        result = parse('""')
        assert isinstance(result, StringLiteral)
        assert result.value == ""
        
        result = parse('"with spaces"')
        assert isinstance(result, StringLiteral)
        assert result.value == "with spaces"
    
    def test_parse_escaped_strings(self):
        """Strings with escape sequences."""
        result = parse(r'"say \"hi\""')
        assert isinstance(result, StringLiteral)
        assert result.value == 'say "hi"'
        
        result = parse(r'"line1\nline2"')
        assert isinstance(result, StringLiteral)
        assert result.value == "line1\nline2"
        
        result = parse(r'"backslash: \\"')
        assert isinstance(result, StringLiteral)
        assert result.value == "backslash: \\"
        
        result = parse(r'"tab:\there"')
        assert isinstance(result, StringLiteral)
        assert result.value == "tab:\there"


class TestBasicLiteralErrors:
    """
    Test that invalid literal syntax raises appropriate errors.
    
    PARSER ROBUSTNESS: Must fail cleanly on invalid input.
    Key error cases: malformed numbers, unterminated strings.
    Should raise ParseError (or similar) with helpful messages.
    """
    
    def test_invalid_numbers(self):
        """Invalid number formats should raise ParseError."""
        with pytest.raises(Exception):  # Will be ParseError when implemented
            parse("3.14.15")  # Double decimal
        
        with pytest.raises(Exception):
            parse("1e")  # Incomplete scientific notation
    
    def test_invalid_strings(self):
        """Invalid string formats should raise ParseError.""" 
        with pytest.raises(Exception):
            parse('"unterminated')  # Missing closing quote


# Note: These tests will fail until the parser is implemented
# They serve as specifications for what the parser should do