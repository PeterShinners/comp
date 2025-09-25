"""
Comprehensive identifier parsing tests for the Comp language.

Tests identifiers through the main comp.parse() method with proper parser flow.
"""

import pytest

import comp


@pytest.mark.parametrize("identifier", [
    "hello", "world", "test", "a", "Test", "HELLO"
])
def test_simple_identifiers(identifier):
    """Simple alphabetic identifiers."""
    result = comp.parse(identifier)
    _assertIdent(result, identifier)


@pytest.mark.parametrize("identifier", [
    "user-name", "file-path", "get-user-data", "a-b-c"
])
def test_lisp_case_identifiers(identifier):
    """Lisp-case identifiers (preferred style)."""
    result = comp.parse(identifier)
    _assertIdent(result, identifier)


@pytest.mark.parametrize("identifier", [
    "user_name", "file_path", "_private", "__dunder__", "_"
])
def test_underscore_identifiers(identifier):
    """Underscore identifiers (allowed)."""
    result = comp.parse(identifier)
    _assertIdent(result, identifier)


@pytest.mark.parametrize("identifier", [
    "active?", "ready?", "empty?", "valid?"
])
def test_simple_boolean_identifiers(identifier):
    """Basic boolean-style identifiers."""
    result = comp.parse(identifier)
    _assertIdent(result, identifier)


@pytest.mark.parametrize("identifier", [
    "is-active?", "has-value?", "user-exists?", "file-ready?"
])
def test_lisp_case_boolean_identifiers(identifier):
    """Lisp-case boolean-style identifiers."""
    result = comp.parse(identifier)
    _assertIdent(result, identifier)


@pytest.mark.parametrize("identifier", [
    "userId", "firstName", "XMLHttpRequest", "iOS"
])
def test_mixed_case_identifiers(identifier):
    """Mixed case identifiers."""
    result = comp.parse(identifier)
    _assertIdent(result, identifier)


@pytest.mark.parametrize("identifier", [
    "user1", "test123", "var2name", "item42"
])
def test_numbers_in_identifiers(identifier):
    """Identifiers with numbers (not at start)."""
    result = comp.parse(identifier)
    _assertIdent(result, identifier)


@pytest.mark.parametrize("identifier", [
    "用户名",  # Chinese characters
    "naïve",  # Latin with diacritics
    "Москва",  # Cyrillic
    "θεός",  # Greek
])
def test_unicode_identifiers(identifier):
    """Unicode identifiers following UAX #31."""
    result = comp.parse(identifier)
    _assertIdent(result, identifier)


@pytest.mark.parametrize("identifier", [
    "café-table",  # Mixed script with hyphen
    "用户-名称",  # Chinese with hyphen
])
def test_unicode_identifiers_with_hyphens(identifier):
    """Unicode identifiers with hyphens (lisp-case style)."""
    result = comp.parse(identifier)
    _assertIdent(result, identifier)


@pytest.mark.parametrize("identifier", [
    "готов?",  # Cyrillic boolean
    "válido?",  # Spanish boolean
])
def test_unicode_boolean_identifiers(identifier):
    """Unicode boolean-style identifiers."""
    result = comp.parse(identifier)
    _assertIdent(result, identifier)


@pytest.mark.parametrize("invalid_input", [
    "😀hello",  # Emoji (symbol, not letter)
    "🚀launch",  # Another emoji
    "❤️love",  # Emoji with modifier
    "€price",  # Currency symbol
    "©copyright",  # Copyright symbol
])
def test_invalid_unicode_characters(invalid_input):
    """Characters that should not be valid identifier starts."""
    with pytest.raises(comp.ParseError):
        comp.parse(invalid_input)


def _assertIdent(value, match):
    """Helper to assert a parsed identifier matches expected name."""
    assert isinstance(value, comp.Identifier)
    assert value.name == match
