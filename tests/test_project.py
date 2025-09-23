"""
Test cases for project module.

SPECIFICATION SUMMARY:
The comp module must properly import and provide best practices and information
for a modern Python library.

- The 'comp' module imports properly
- It provides a sensible exposed api
    - no underscored internal names
    - docstrings on functions and classes
- The package provides standard metadata
    - name, version, author, license, description

"""

import pytest


class TestImport:
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