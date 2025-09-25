"""
Test cases for parsing architecture and integration.

These tests validate the overall parser architecture, public API structure,
error handling consistency, and integration between different parsing components.
"""

import pytest

import comp


def test_ast_node_hierarchy():
    """Test that AST nodes have proper inheritance."""
    num = comp.parse("42")
    string = comp.parse('"hello"')

    # Both should be AST nodes
    assert isinstance(num, comp.ASTNode)
    assert isinstance(string, comp.ASTNode)

    # But different specific types
    assert isinstance(num, comp.NumberLiteral)
    assert isinstance(string, comp.StringLiteral)
    assert not isinstance(num, comp.StringLiteral)
    assert not isinstance(string, comp.NumberLiteral)


def test_parse_error_consistency():
    """Test that ParseError is raised consistently across different parsing scenarios."""
    # Empty input
    with pytest.raises(comp.ParseError, match="Empty input"):
        comp.parse("")

    # Invalid syntax
    with pytest.raises(comp.ParseError, match="Invalid character"):
        comp.parse("invalid!")

    # Invalid number
    with pytest.raises(comp.ParseError):
        comp.parse("3.14.15")

    # Unterminated string
    with pytest.raises(comp.ParseError):
        comp.parse('"unterminated')


def test_single_expression_parsing():
    """Test that parser handles exactly one expression at a time."""
    # Single expressions should work
    assert comp.parse("42").value == 42
    assert comp.parse('"hello"').value == "hello"
    assert comp.parse("0xFF").value == 255
    assert comp.parse('""').value == ""

    # Multiple expressions should fail (not supported yet)
    with pytest.raises(comp.ParseError):
        comp.parse('42 "hello"')

    with pytest.raises(comp.ParseError):
        comp.parse('"hello" "world"')

    with pytest.raises(comp.ParseError):
        comp.parse("42 0xFF")


def test_ast_node_properties():
    """Test that AST nodes have expected properties and string representations."""
    num = comp.parse("42")
    string = comp.parse('"hello"')

    # All nodes should have these properties (even if None for now)
    assert hasattr(num, "line")
    assert hasattr(num, "column")
    assert hasattr(string, "line")
    assert hasattr(string, "column")

    # Should have proper string representations
    assert "NumberLiteral" in repr(num)
    assert "42" in repr(num)
    assert "StringLiteral" in repr(string)
    assert "hello" in repr(string)


def test_parser_reuse():
    """Test that the parser can be reused without issues."""
    # Multiple calls should work fine without state interference
    results = []
    for i in range(10):
        results.append(comp.parse(f"{i}"))
        results.append(comp.parse(f'"item{i}"'))

    # All should be parsed correctly
    for i, result in enumerate(results):
        if i % 2 == 0:  # Even indices are numbers
            assert isinstance(result, comp.NumberLiteral)
            assert result.value == i // 2
        else:  # Odd indices are strings
            assert isinstance(result, comp.StringLiteral)
            assert result.value == f"item{i // 2}"


def test_error_message_quality():
    """Test that error messages are helpful and informative."""
    # Test various error conditions and ensure messages are informative
    error_cases = [
        ("", "Empty input"),
        ('"unterminated', "Unterminated string literal"),
        (r'"\u123"', "Invalid"),  # Should mention Unicode escape issue
        ("invalid!", "Invalid character"),  # Invalid character in input
    ]

    for input_str, expected_msg_part in error_cases:
        with pytest.raises(comp.ParseError) as exc_info:
            comp.parse(input_str)
        error_msg = str(exc_info.value).lower()
        assert expected_msg_part.lower() in error_msg, (
            f"Expected '{expected_msg_part}' in error message for '{input_str}', got: {exc_info.value}"
        )


def test_cross_type_parsing_integration():
    """Test that number and string parsing work correctly together."""
    # Numbers should still work as expected
    num_result = comp.parse("42")
    assert isinstance(num_result, comp.NumberLiteral)
    assert num_result.value == 42

    # Strings should work as expected
    str_result = comp.parse('"hello"')
    assert isinstance(str_result, comp.StringLiteral)
    assert str_result.value == "hello"

    # String literals that look like numbers should be strings
    str_number = comp.parse('"42"')
    assert isinstance(str_number, comp.StringLiteral)
    assert str_number.value == "42"

    # Number literals should not be confused with strings
    hex_number = comp.parse("0xFF")
    assert isinstance(hex_number, comp.NumberLiteral)
    assert hex_number.value == 255
