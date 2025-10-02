"""
Test cases for string literal parsing.

SPECIFICATION:
- Basic strings: "hello", "", "with spaces"
- Escape sequences: \\", \\\\, \\n, \\t, \\r, \\0
- Unicode: UTF-8 literals, \\uXXXX, \\UXXXXXXXX escape sequences
- Error cases: unterminated strings, invalid escapes

PARSER EXPECTATIONS:
- comp.parse_expr('"hello"') → String("hello")
- comp.parse_expr('"say \\"hi\\""') → String('say "hi"')

AST NODE: String(value: str)

NOTE: Refactored to use comptest helpers for clean parametrized testing.
"""

import pytest

import comp
import comptest


@comptest.params(
    "code value",
    hello=('"hello"', "hello"),
    empty=('""', ""),
    spaces=('"with spaces"', "with spaces"),
    multi=('"multiple words here"', "multiple words here"),
    triple_empty=('""""""', ""),  # Triple-quoted empty string
)
def test_parse_basic_strings(key, code, value):
    """Basic string literals."""
    result = comptest.parse_value(code, comp.String)
    assert result.value == value
    comptest.roundtrip(result)


@comptest.params(
    "code value",
    quotes=(r'"say \"hi\""', 'say "hi"'),
    newlines=(r'"line1\nline2"', "line1\nline2"),
    backslash=(r'"backslash: \\"', "backslash: \\"),
    tabs=(r'"tab:\there"', "tab:\there"),
    carriage=(r'"line1\rline2"', "line1\rline2"),
    triple_basic=('"""hello world"""', "hello world"),  # Triple-quoted basic
)
def test_parse_escaped_strings(key, code, value):
    """Strings with standard escape sequences."""
    result = comptest.parse_value(code, comp.String)
    assert result.value == value
    comptest.roundtrip(result)


@comptest.params(
    "code value",
    single=(r'"\0"', "\0"),
    middle=(r'"hello\0world"', "hello\0world"),
    multi=(r'"\0\0\0"', "\0\0\0"),
    start=(r'"\0start"', "\0start"),
    end=(r'"end\0"', "end\0"),
)
def test_null_characters(key, code, value):
    """Null characters \\0 should be handled correctly."""
    result = comptest.parse_value(code, comp.String)
    assert result.value == value
    comptest.roundtrip(result)


@comptest.params(
    "code value",
    u4_A=(r'"\u0041"', "A"),
    u4_hello=(r'"\u0048\u0065\u006C\u006C\u006F"', "Hello"),
    u8_A=(r'"\U00000041"', "A"),
    emoji1=(r'"\U0001F600"', "😀"),
    emoji2=('"""👍"""', "👍"),  # Triple-quoted emoji
)
def test_unicode_escape_sequences(key, code, value):
    """Unicode escape sequences \\u and \\U."""
    result = comptest.parse_value(code, comp.String)
    assert result.value == value
    comptest.roundtrip(result)


@comptest.params(
    "code value",
    mixed1=(r'"Say \"Hello\n\u0041\U0001F600\""', 'Say "Hello\nA😀"'),
    mixed2=(r'"Path: C:\\folder\ttab\u0020end"', "Path: C:\\folder\ttab end"),
)
def test_mixed_escape_sequences(key, code, value):
    """Strings with mixed escape types."""
    result = comptest.parse_value(code, comp.String)
    assert result.value == value
    comptest.roundtrip(result)


@comptest.params(
    "code value",
    empty=('""', ""),
    space=('" "', " "),
    spaces=('"   "', "   "),
    escapes=(r'"\t\n\r"', "\t\n\r"),
)
def test_empty_and_whitespace_strings(key, code, value):
    """Empty strings and strings with only whitespace."""
    result = comptest.parse_value(code, comp.String)
    assert result.value == value
    comptest.roundtrip(result)


@comptest.params(
    "code value",
    cafe=('"café"', "café"),
    chinese=('"用户名"', "用户名"),
    emoji=('"Hello 👋 World 🌍"', "Hello 👋 World 🌍"),
    cyrillic=('"""Москва"""', "Москва"),  # Triple-quoted Cyrillic
)
def test_utf8_literal_strings(key, code, value):
    """Strings with literal UTF-8 characters."""
    result = comptest.parse_value(code, comp.String)
    #assert result.value == value
    #comptest.roundtrip(result)


@comptest.params(
    "code value",
    int=('"42"', "42"),
    float=('"3.14"', "3.14"),
    neg=('"-17"', "-17"),
    hex=('"0xFF"', "0xFF"),
    bin=('"0b1010"', "0b1010"),
    exp=('"1e3"', "1e3"),
)
def test_string_vs_number_disambiguation(key, code, value):
    """Ensure strings that look like numbers are parsed as strings."""
    result = comptest.parse_value(code, comp.String)
    assert result.value == value
    comptest.roundtrip(result)


@pytest.mark.filterwarnings("ignore::SyntaxWarning")
@comptest.params(
    "code value",
    hex_esc=(r'"\x41"', "A"),  # Hex escape - now supported
    z_esc=('"\\z"', "\\z"),  # Invalid escape -> literal
    dollar=('"\\$"', "\\$"),  # Invalid escape -> literal
)
def test_invalid_escape_sequences(key, code, value):
    """Invalid escape sequences should be treated as literals (Python behavior)."""
    # Python's ast.literal_eval converts invalid escapes to literal characters
    result = comptest.parse_value(code, comp.String)
    assert result.value == value
    comptest.roundtrip(result)


@comptest.params(
    "code",
    u4_short1=(r'"\u123"',),   # Too short (need 4 hex digits)
    u4_short2=(r'"\u12"',),    # Too short
    u4_none=(r'"\u"',),        # No digits
    u4_bad=(r'"\uGHIJ"',),     # Invalid hex digits
    u4_mixed=(r'"\u123G"',),   # Mixed valid/invalid hex
    u8_short1=(r'"\U0001F60"',),  # Too short (need 8 hex digits)
    u8_short2=(r'"\U123"',),   # Too short
    u8_bad=(r'"\UGHIJKLMN"',), # Invalid hex digits
    u8_none=(r'"\U"',),        # No digits
)
#@pytest.mark.xfail(reason="Unicode escaping not quite connected yet")
def test_invalid_unicode_escapes(key, code):
    """Invalid Unicode escape sequences should raise ParseError."""
    comptest.invalid_parse(code, match=r"unicode|escape")


@comptest.params(
    "code",
    hello=('"hello',),         # Missing closing quote
    world=('"hello world',),   # Missing closing quote
    single=('"',),             # Just opening quote
)
def test_unterminated_strings(key, code):
    """Unterminated strings should raise ParseError."""
    comptest.invalid_parse(code, match=r"unterminated|string")


@comptest.params(
    "code value",
    empty=('""""""', ""),
    simple=('"""hello world"""', "hello world"),
    newline=('"""line1\nline2"""', "line1\nline2"),
    multi_newline=('"""first\nsecond\nthird"""', "first\nsecond\nthird"),
    embedded_single=('''"""He said "hello" today"""''', 'He said "hello" today'),
    embedded_double=('''"""She said "it's great" aloud"""''', '''She said "it's great" aloud'''),
    mixed_quotes=('''"""Both 'single' and "double" quotes"""''', '''Both 'single' and "double" quotes'''),
    spaces=('"""   spaces   """', "   spaces   "),
    unicode=('"""Привет мир 世界 🌍"""', "Привет мир 世界 🌍"),
    escaped_backslash=(r'"""backslash: \\"""', "backslash: \\"),
)
def test_triple_quoted_strings(key, code, value):
    """Triple-quoted strings with newlines and embedded quotes."""
    result = comptest.parse_value(code, comp.String)
    assert result.value == value
    comptest.roundtrip(result)
