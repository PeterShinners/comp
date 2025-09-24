"""
Comprehensive identifier parsing tests for the Comp language.

Tests identifiers through the main comp.parse() method with proper parser flow.
"""

import comp


def test_simple_identifiers():
    """Simple alphabetic identifiers."""
    test_cases = ["hello", "world", "test", "a", "Test", "HELLO"]

    for identifier in test_cases:
        result = comp.parse(identifier)
        _assertIdent(result, identifier)


def test_lisp_case_identifiers():
    """Lisp-case identifiers (preferred style)."""
    test_cases = ["user-name", "file-path", "get-user-data", "a-b-c"]

    for identifier in test_cases:
        result = comp.parse(identifier)
        _assertIdent(result, identifier)


def test_underscore_identifiers():
    """Underscore identifiers (allowed)."""
    test_cases = ["user_name", "file_path", "_private", "__dunder__", "_"]

    for identifier in test_cases:
        result = comp.parse(identifier)
        _assertIdent(result, identifier)


def test_simple_boolean_identifiers():
    """Basic boolean-style identifiers."""
    test_cases = ["active?", "ready?", "empty?", "valid?"]

    for identifier in test_cases:
        result = comp.parse(identifier)
        _assertIdent(result, identifier)


def test_lisp_case_boolean_identifiers():
    """Lisp-case boolean-style identifiers."""
    test_cases = ["is-active?", "has-value?", "user-exists?", "file-ready?"]

    for identifier in test_cases:
        result = comp.parse(identifier)
        _assertIdent(result, identifier)



def test_mixed_case_identifiers():
    """Mixed case identifiers."""
    test_cases = ["userId", "firstName", "XMLHttpRequest", "iOS"]

    for identifier in test_cases:
        result = comp.parse(identifier)
        _assertIdent(result, identifier)



def test_numbers_in_identifiers():
    """Identifiers with numbers (not at start)."""
    test_cases = ["user1", "test123", "var2name", "item42"]

    for identifier in test_cases:
        result = comp.parse(identifier)
        _assertIdent(result, identifier)


def _assertIdent(value, match):
    """Helper to assert a parsed identifier matches expected name."""
    assert isinstance(value, comp.Identifier)
    assert value.name == match
