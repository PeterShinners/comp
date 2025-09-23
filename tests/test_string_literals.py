"""
Test cases for string literal parsing - Phase 03 (Not implemented yet).

SPECIFICATION SUMMARY:
String parsing with UTF-8 support and standard escape sequences.
Part of Phase 03 along with tag literals.

REQUIREMENTS FROM DESIGN DOCS:
- UTF-8 strings with escape sequences (\", \\, \n, \r, \t)
- Basic string literals before advanced templating features
- Integration with existing number and future tag parsing

PARSER EXPECTATIONS:
- comp.parse('"hello"') → StringLiteral("hello")
- comp.parse('"say \\"hi\\""') → StringLiteral('say "hi"')
- comp.parse('"line1\\nline2"') → StringLiteral("line1\nline2")

ERROR CASES TO HANDLE:
- Unterminated strings: "unterminated (missing quote)
- Invalid escape sequences

AST NODE STRUCTURE:
- StringLiteral: value (str)

NOTE: All tests in this file are currently skipped as Phase 03
(tag literals and string literals) is not implemented yet.
"""

import pytest

import comp


@pytest.mark.skip(reason="String parsing not implemented yet")
def test_parse_basic_strings():
    """Basic string literals."""
    result = comp.parse('"hello"')
    assert isinstance(result, comp.StringLiteral)
    assert result.value == "hello"

    result = comp.parse('""')
    assert isinstance(result, comp.StringLiteral)
    assert result.value == ""

    result = comp.parse('"with spaces"')
    assert isinstance(result, comp.StringLiteral)
    assert result.value == "with spaces"


@pytest.mark.skip(reason="String parsing not implemented yet")
def test_parse_escaped_strings():
    """Strings with escape sequences."""
    result = comp.parse(r'"say \"hi\""')
    assert isinstance(result, comp.StringLiteral)
    assert result.value == 'say "hi"'

    result = comp.parse(r'"line1\nline2"')
    assert isinstance(result, comp.StringLiteral)
    assert result.value == "line1\nline2"

    result = comp.parse(r'"backslash: \\"')
    assert isinstance(result, comp.StringLiteral)
    assert result.value == "backslash: \\"

    result = comp.parse(r'"tab:\there"')
    assert isinstance(result, comp.StringLiteral)
    assert result.value == "tab:\there"


@pytest.mark.skip(reason="String parsing not implemented yet")
def test_invalid_strings():
    """Invalid string formats should raise ParseError."""
    with pytest.raises(comp.ParseError):
        comp.parse('"unterminated')  # Missing closing quote
