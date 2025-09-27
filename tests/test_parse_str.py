"""
Test cases for string literal parsing.

SPECIFICATION:
- Basic strings: "hello", "", "with spaces"
- Escape sequences: \\", \\\\, \\n, \\t, \\r, \\0
- Unicode: UTF-8 literals, \\uXXXX, \\UXXXXXXXX escape sequences
- Error cases: unterminated strings, invalid escapes

PARSER EXPECTATIONS:
- comp.parse('"hello"') → StringLiteral("hello")
- comp.parse('"say \\"hi\\""') → StringLiteral('say "hi"')

AST NODE: StringLiteral(value: str)
"""

from decimal import Decimal

import pytest

import comp


@pytest.mark.parametrize("input_text,expected_value", [
    ('"hello"', "hello"),
    ('""', ""),
    ('"with spaces"', "with spaces"),
    ('"multiple words here"', "multiple words here"),
])
def test_parse_basic_strings(input_text, expected_value):
    """Basic string literals."""
    result = comp.parse(input_text)
    _assertStr(result, expected_value)


def test_parse_escaped_strings():
    """Strings with standard escape sequences."""
    # Escaped quotes
    result = comp.parse(r'"say \"hi\""')
    _assertStr(result, 'say "hi"')

    # Newlines
    result = comp.parse(r'"line1\nline2"')
    _assertStr(result, "line1\nline2")

    # Backslashes
    result = comp.parse(r'"backslash: \\"')
    _assertStr(result, "backslash: \\")

    # Tabs
    result = comp.parse(r'"tab:\there"')
    _assertStr(result, "tab:\there")

    # Carriage returns
    result = comp.parse(r'"line1\rline2"')
    _assertStr(result, "line1\rline2")


def test_null_characters():
    """Null characters \\0 should be handled correctly."""
    # Single null character
    result = comp.parse(r'"\0"')
    _assertStr(result, "\0")

    # Null in middle of string
    result = comp.parse(r'"hello\0world"')
    _assertStr(result, "hello\0world")

    # Multiple nulls
    result = comp.parse(r'"\0\0\0"')
    _assertStr(result, "\0\0\0")

    # Null at start and end
    result = comp.parse(r'"\0start"')
    _assertStr(result, "\0start")

    result = comp.parse(r'"end\0"')
    _assertStr(result, "end\0")


def test_unicode_escape_sequences():
    """Unicode escape sequences \\u and \\U."""
    # 4-digit Unicode escapes
    result = comp.parse(r'"\u0041"')
    _assertStr(result, "A")

    result = comp.parse(r'"\u0048\u0065\u006C\u006C\u006F"')
    _assertStr(result, "Hello")

    # 8-digit Unicode escapes
    result = comp.parse(r'"\U00000041"')
    _assertStr(result, "A")

    # Emoji with 8-digit escape
    result = comp.parse(r'"\U0001F600"')
    _assertStr(result, "😀")

    result = comp.parse(r'"\U0001F44D"')
    _assertStr(result, "👍")


def test_mixed_escape_sequences():
    """Strings with mixed escape types."""
    result = comp.parse(r'"Say \"Hello\n\u0041\U0001F600\""')
    _assertStr(result, 'Say "Hello\nA😀"')

    result = comp.parse(r'"Path: C:\\folder\ttab\u0020end"')
    _assertStr(result, "Path: C:\\folder\ttab end")


def test_empty_and_whitespace_strings():
    """Empty strings and strings with only whitespace."""
    result = comp.parse('""')
    _assertStr(result, "")

    result = comp.parse('" "')
    _assertStr(result, " ")

    result = comp.parse('"   "')
    _assertStr(result, "   ")

    result = comp.parse(r'"\t\n\r"')
    _assertStr(result, "\t\n\r")


def test_utf8_literal_strings():
    """Strings with literal UTF-8 characters."""
    result = comp.parse('"café"')
    _assertStr(result, "café")

    result = comp.parse('"用户名"')
    _assertStr(result, "用户名")

    result = comp.parse('"Hello 👋 World 🌍"')
    _assertStr(result, "Hello 👋 World 🌍")

    result = comp.parse('"Москва"')
    _assertStr(result, "Москва")


def test_string_equality_and_comparison():
    """String literals should support equality comparison."""
    result1 = comp.parse('"hello"')
    result2 = comp.parse('"hello"')
    result3 = comp.parse('"world"')

    assert result1 == result2
    assert result1 != result3
    assert hash(result1) == hash(result2)


def test_string_vs_number_disambiguation():
    """Ensure strings that look like numbers are parsed as strings."""
    # These should be parsed as strings, not numbers
    string_numbers = [
        ('"42"', "42"),
        ('"3.14"', "3.14"),
        ('"-17"', "-17"),
        ('"0xFF"', "0xFF"),
        ('"0b1010"', "0b1010"),
        ('"1e3"', "1e3"),
    ]

    for input_str, expected_value in string_numbers:
        result = comp.parse(input_str)
        _assertStr(result, expected_value)


def test_integration_with_number_parsing():
    """Ensure string parsing works alongside existing number parsing."""
    # Numbers should still work
    num_result = comp.parse("42")
    assert isinstance(num_result, comp.NumberLiteral)
    assert num_result.value == 42

    hex_result = comp.parse("0xFF")
    assert isinstance(hex_result, comp.NumberLiteral)
    assert hex_result.value == 255

    decimal_result = comp.parse("3.14")
    assert isinstance(decimal_result, comp.NumberLiteral)
    assert decimal_result.value == Decimal("3.14")

    # Strings should work
    str_result = comp.parse('"hello"')
    _assertStr(str_result, "hello")

    escaped_str = comp.parse(r'"say \"hi\""')
    _assertStr(escaped_str, 'say "hi"')


@pytest.mark.filterwarnings("ignore::SyntaxWarning")
def test_invalid_escape_sequences():
    """Invalid escape sequences should be treated as literals (Python behavior)."""
    # Python's ast.literal_eval converts invalid escapes to literal characters
    # This is more permissive than our old manual parser

    result = comp.parse(r'"\x41"')  # Hex escape - now supported
    _assertStr(result, "A")

    result = comp.parse('"\\z"')  # Invalid escape -> literal (using double backslash to avoid warning)
    _assertStr(result, "\\z")

    result = comp.parse('"\\$"')  # Invalid escape -> literal (using double backslash to avoid warning)
    _assertStr(result, "\\$")


def test_invalid_unicode_escapes():
    """Invalid Unicode escape sequences should raise ParseError."""
    invalid_unicode = [
        r'"\u123"',  # Too short (need 4 hex digits)
        r'"\u12"',  # Too short
        r'"\u"',  # No digits
        r'"\uGHIJ"',  # Invalid hex digits
        r'"\u123G"',  # Mixed valid/invalid hex
        r'"\U0001F60"',  # Too short (need 8 hex digits)
        r'"\U123"',  # Too short
        r'"\UGHIJKLMN"',  # Invalid hex digits
        r'"\U"',  # No digits
    ]

    for invalid in invalid_unicode:
        with pytest.raises(comp.ParseError):
            comp.parse(invalid)


def test_unterminated_strings():
    """Unterminated strings should raise ParseError."""
    unterminated_cases = [
        '"hello',  # Missing closing quote
        '"hello world',  # Missing closing quote
        '"',  # Just opening quote
    ]

    for case in unterminated_cases:
        with pytest.raises(comp.ParseError):
            comp.parse(case)


def test_long_strings():
    """Very long string literals should work correctly."""
    long_content = "a" * 1000
    result = comp.parse(f'"{long_content}"')
    _assertStr(result, long_content)

    # Long string with escapes
    long_with_escapes = "Hello\\n" * 100
    result = comp.parse(f'"{long_with_escapes}"')
    _assertStr(result, long_with_escapes.replace("\\n", "\n"))


def test_empty_input():
    """Empty input should raise ParseError."""
    with pytest.raises(comp.ParseError, match="Empty input"):
        comp.parse("")

    with pytest.raises(comp.ParseError, match="Empty input"):
        comp.parse("   ")


def test_single_literal_parsing():
    """Parser should handle exactly one literal per parse() call."""
    # Single number should work
    result = comp.parse("42")
    assert isinstance(result, comp.NumberLiteral)

    # Single string should work
    result = comp.parse('"hello"')
    assert isinstance(result, comp.StringLiteral)

    # Multiple literals should fail (not supported yet)
    # This will be enabled in later phases for expressions
    with pytest.raises(comp.ParseError):
        comp.parse('42 "hello"')

    with pytest.raises(comp.ParseError):
        comp.parse('"hello" 42')


def _assertStr(value, match):
    """Helper to assert a parsed string matches expected value."""
    assert isinstance(value, comp.StringLiteral)
    assert value.value == match
