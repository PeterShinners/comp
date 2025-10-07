"""
Comprehensive identifier parsing tests for the Comp language.

Tests identifiers through the main comp.parse_expr() method with proper parser flow.
"""

import comp
import asttest


@asttest.params(
    "identifier",
    hello=("hello",),
    single=("a",),
    upper=("HELLO",),
    camel=("XMLHttpRequest",),
    ios=("iOS",),
    num1=("user1",),
    num2=("test123",),
    num3=("var2name",),
    num4=("item42",),
    dash1=("user-name",),
    under=("file_path",),
    dash2=("get-user-data",),
    dash3=("a-b-c",),
    private=("_private",),
    dunder=("__dunder__",),
    under1=("_",),
    bool1=("active?",),
    bool2=("ready?",),
    bool3=("is-active?",),
)
def test_identifiers(key, identifier):
    """Test valid identifier."""
    result = asttest.parse_value(identifier, comp.ast.Identifier)
    # Verify the identifier unparsed back to the same value
    assert result.unparse() == identifier


@asttest.params(
    "identifier",
    chinese=("用户名",),  # Chinese characters
    latin=("naïve",),  # Latin with diacritics
    cyrillic=("Москва",),  # Cyrillic
    greek=("θεός",),  # Greek
    mixed=("café-table",),  # Mixed script with hyphen
    chinese_dash=("用户-名称",),  # Chinese with hyphen
    cyrillic_bool=("готов?",),  # Cyrillic boolean
    spanish_bool=("válido?",),  # Spanish boolean
)
def test_unicode_identifiers(key, identifier):
    """Unicode identifiers following UAX #31."""
    result = asttest.parse_value(identifier, comp.ast.Identifier)
    # Verify the identifier unparsed back to the same value
    assert result.unparse() == identifier


@asttest.params(
    "code",
    emoji1=("😀hello",),  # Emoji (symbol, not letter)
    emoji2=("❤️love",),  # Emoji with modifier
    currency=("€price",),  # Currency symbol
    copyright=("©copyright",),  # Copyright symbol
    internal_q=("one?two?",),  # Internal question mark
    double_q=("really??",),  # Double question mark
)
def test_invalid_unicode_characters(key, code):
    """Characters that should not be valid identifier starts."""
    asttest.invalid_parse(code, match=r"parse error|unexpected")

