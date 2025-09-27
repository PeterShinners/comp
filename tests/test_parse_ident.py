"""
Comprehensive identifier parsing tests for the Comp language.

Tests identifiers through the main comp.parse() method with proper parser flow.
"""

import pytest

import comp


@pytest.mark.parametrize("identifier", [
    "hello", "a", "HELLO", "XMLHttpRequest", "iOS",
    "user1", "test123", "var2name", "item42",
    "user-name", "file_path", "get-user-data", "a-b-c",
    "_private", "__dunder__", "_",
    "active?", "ready?", "is-active?",
])
def test_identifiers(identifier):
    """Test valid identifier."""
    result = comp.parse(identifier)
    assert isinstance(result, comp.Identifier)
    assert result.name == identifier


@pytest.mark.parametrize("identifier", [
    "用户名",  # Chinese characters
    "naïve",  # Latin with diacritics
    "Москва",  # Cyrillic
    "θεός",  # Greek
    "café-table",  # Mixed script with hyphen
    "用户-名称",  # Chinese with hyphen
    "готов?",  # Cyrillic boolean
    "válido?",  # Spanish boolean
])
def test_unicode_identifiers(identifier):
    """Unicode identifiers following UAX #31."""
    result = comp.parse(identifier)
    assert isinstance(result, comp.Identifier)
    assert result.name == identifier


@pytest.mark.parametrize("invalid_input", [
    "😀hello",  # Emoji (symbol, not letter)
    "❤️love",  # Emoji with modifier
    "€price",  # Currency symbol
    "©copyright",  # Copyright symbol
    "one?two?",  # Internal question mark
    "really??",  # Double question mark
])
def test_invalid_unicode_characters(invalid_input):
    """Characters that should not be valid identifier starts."""
    with pytest.raises(comp.ParseError):
        comp.parse(invalid_input)

