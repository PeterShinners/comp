"""
Test cases for reference literal parsing - Phase 04.

SPECIFICATION:
- Tag references: #tag, #user-name, #timeout.error, #error/std
- Shape references: ~shape, ~user-profile, ~database.record, ~record/database
- Function references: |func, |parse-config, |json.parse, |query/database
- Unified pattern: 99% shared parsing logic across #, ~, |
- Hierarchical: dot notation for qualified paths (error.status)
- Modular: slash notation for modules (identifier/module)

PARSER EXPECTATIONS:
- comp.parse("#active") → TagReference("active")
- comp.parse("~user") → ShapeReference("user")
- comp.parse("|connect") → FunctionReference("connect")

AST NODES: TagReference(name), ShapeReference(name), FunctionReference(name)
"""

import pytest

import comp


# ============================================================================
# TAG LITERAL TESTS
# ============================================================================


@pytest.mark.parametrize("input_text,expected_name", [
    # Simple tags
    ("#true", "true"),
    ("#active", "active"),
    # Kebab-case tags
    ("#user-name", "user-name"),
    ("#error-status", "error-status"),
    # Hierarchical tags
    ("#timeout.error", "timeout.error"),
    ("#timeout.error.status", "timeout.error.status"),
    # Module tags
    ("#error/std", "error/std"),
    ("#status/user-auth", "status/user-auth"),
    # Full tags (hierarchy + module)
    ("#timeout.error.status/std", "timeout.error.status/std"),
    ("#primary.button.ui/components", "primary.button.ui/components"),
])
def test_parse_tags(input_text, expected_name):
    """Comprehensive tag parsing: simple, kebab-case, hierarchical, module, and full references."""
    result = comp.parse(input_text)
    _assertTag(result, expected_name)


# ============================================================================
# SHAPE LITERAL TESTS
# ============================================================================


@pytest.mark.parametrize("input_text,expected_name", [
    # Simple shapes
    ("~num", "num"),
    ("~bool", "bool"),
    # Kebab-case shapes
    ("~user-profile", "user-profile"),
    ("~api-response", "api-response"),
    # Hierarchical shapes
    ("~database.record", "database.record"),
    ("~ui.component", "ui.component"),
    # Module shapes
    ("~record/database", "record/database"),
    ("~user/auth", "user/auth"),
    # Full shapes (hierarchy + module)
    ("~database.record/persistence", "database.record/persistence"),
    ("~button.primary.ui/components", "button.primary.ui/components"),
])
def test_parse_shapes(input_text, expected_name):
    """Comprehensive shape parsing: simple, kebab-case, hierarchical, module, and full references."""
    result = comp.parse(input_text)
    _assertShape(result, expected_name)


# ============================================================================
# FUNCTION LITERAL TESTS
# ============================================================================


@pytest.mark.parametrize("input_text,expected_name", [
    # Simple functions
    ("|connect", "connect"),
    ("|validate", "validate"),
    # Kebab-case functions
    ("|parse-config", "parse-config"),
    ("|send-email", "send-email"),
    # Hierarchical functions
    ("|database.query", "database.query"),
    ("|json.parse", "json.parse"),
    # Module functions
    ("|query/database", "query/database"),
    ("|validate/auth", "validate/auth"),
    # Full functions (hierarchy + module)
    ("|database.query.select/persistence", "database.query.select/persistence"),
    ("|user.auth.validate/security", "user.auth.validate/security"),
])
def test_parse_functions(input_text, expected_name):
    """Comprehensive function parsing: simple, kebab-case, hierarchical, module, and full references."""
    result = comp.parse(input_text)
    _assertFunc(result, expected_name)


# ============================================================================
# UNIFIED PATTERN TESTS
# ============================================================================


def test_unified_pattern_consistency():
    """All three reference types should follow identical patterns."""
    # Simple references
    tag = comp.parse("#status")
    shape = comp.parse("~status")
    func = comp.parse("|status")

    _assertTag(tag, "status")
    _assertShape(shape, "status")
    _assertFunc(func, "status")

    # Hierarchical references
    tag_hier = comp.parse("#error.status")
    shape_hier = comp.parse("~error.status")
    func_hier = comp.parse("|error.status")

    _assertTag(tag_hier, "error.status")
    _assertShape(shape_hier, "error.status")
    _assertFunc(func_hier, "error.status")

    # Module references
    tag_mod = comp.parse("#status/std")
    shape_mod = comp.parse("~status/std")
    func_mod = comp.parse("|status/std")

    _assertTag(tag_mod, "status/std")
    _assertShape(shape_mod, "status/std")
    _assertFunc(func_mod, "status/std")

    # Full references
    tag_full = comp.parse("#error.status/std")
    shape_full = comp.parse("~error.status/std")
    func_full = comp.parse("|error.status/std")

    _assertTag(tag_full, "error.status/std")
    _assertShape(shape_full, "error.status/std")
    _assertFunc(func_full, "error.status/std")


def test_mixed_naming_conventions():
    """Different naming conventions should work across all reference types."""
    naming_patterns = [
        "simple",
        "with-hyphens",
        "with_underscores",
        "mixedCase",
        "用户名",  # Unicode
        "naïve",  # Accented
    ]

    for pattern in naming_patterns:
        tag = comp.parse(f"#{pattern}")
        shape = comp.parse(f"~{pattern}")
        func = comp.parse(f"|{pattern}")

        _assertTag(tag, pattern)
        _assertShape(shape, pattern)
        _assertFunc(func, pattern)


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================


def test_invalid_reference_formats():
    """Invalid reference formats should raise ParseError."""
    invalid_references = [
        "#",  # Empty tag
        "~",  # Empty shape
        "|",  # Empty function
        "#123",  # Starts with digit
        "~456",  # Starts with digit
        "|789",  # Starts with digit
        "#-invalid",  # Starts with hyphen
        "~-invalid",  # Starts with hyphen
        "|-invalid",  # Starts with hyphen
    ]

    for invalid in invalid_references:
        with pytest.raises(comp.ParseError):
            comp.parse(invalid)


def test_invalid_hierarchy_formats():
    """Invalid hierarchical references should raise ParseError."""
    invalid_hierarchies = [
        "#.invalid",  # Starts with dot
        "~.invalid",  # Starts with dot
        "|.invalid",  # Starts with dot
        "#invalid.",  # Ends with dot
        "~invalid.",  # Ends with dot
        "|invalid.",  # Ends with dot
        "#..double",  # Double dots
        "~..double",  # Double dots
        "|..double",  # Double dots
        "#invalid..dot",  # Double dots in middle
    ]

    for invalid in invalid_hierarchies:
        with pytest.raises(comp.ParseError):
            comp.parse(invalid)


def test_invalid_module_formats():
    """Invalid module references should raise ParseError."""
    invalid_modules = [
        "#/empty",  # Missing identifier before /
        "~/empty",  # Missing identifier before /
        "|/empty",  # Missing identifier before /
        "#invalid/",  # Missing module after /
        "~invalid/",  # Missing module after /
        "|invalid/",  # Missing module after /
        "#invalid//",  # Double slashes
        "~invalid//",  # Double slashes
        "|invalid//",  # Double slashes
        "#/",  # Just slash
        "~/",  # Just slash
        "|/",  # Just slash
    ]

    for invalid in invalid_modules:
        with pytest.raises(comp.ParseError):
            comp.parse(invalid)


@pytest.mark.parametrize("invalid_input", [
    "#user@name",  # @ not allowed
    "~user$name",  # $ not allowed
    "|user%name",  # % not allowed
    "#user name",  # Space not allowed
    "~user\tname",  # Tab not allowed
    "|user\nname",  # Newline not allowed
    "#user=value",  # = not allowed
    "~user*strong",  # * not allowed
    "|user?weak",  # ? not allowed (except in boolean naming)
])
def test_invalid_identifier_characters(invalid_input):
    """References with invalid identifier characters should raise ParseError."""
    with pytest.raises(comp.ParseError):
        comp.parse(invalid_input)


@pytest.mark.parametrize("reserved_input", [
    "@local",  # @ reserved for local scope
    "$scope",  # $ reserved for scopes
    "^arg",  # ^ reserved for arguments
    "!directive",  # ! reserved for directives
    "&privacy",  # & reserved for privacy structures
    "%template",  # % reserved for templates
    "??fallback",  # ?? reserved for fallback
])
def test_reserved_sigils(reserved_input):
    """Other sigils should not be valid for references."""
    with pytest.raises(comp.ParseError):
        comp.parse(reserved_input)


# ============================================================================
# INTEGRATION TESTS
# ============================================================================


def test_integration_with_existing_literals():
    """Reference literals should work alongside numbers and strings."""
    # Numbers should still work
    num_result = comp.parse("42")
    assert isinstance(num_result, comp.NumberLiteral)
    assert num_result.value == 42

    # Strings should still work
    str_result = comp.parse('"hello"')
    assert isinstance(str_result, comp.StringLiteral)
    assert str_result.value == "hello"

    # References should work
    tag_result = comp.parse("#active")
    _assertTag(tag_result, "active")

    shape_result = comp.parse("~num")
    _assertShape(shape_result, "num")

    func_result = comp.parse("|connect")
    _assertFunc(func_result, "connect")


def test_reference_equality_and_comparison():
    """Reference literals should support equality comparison."""
    # Same references should be equal
    tag1 = comp.parse("#active")
    tag2 = comp.parse("#active")
    assert tag1 == tag2
    assert hash(tag1) == hash(tag2)

    # Different references should not be equal
    tag3 = comp.parse("#inactive")
    assert tag1 != tag3

    # Different types should not be equal
    shape = comp.parse("~active")
    func = comp.parse("|active")
    assert tag1 != shape
    assert tag1 != func
    assert shape != func


def test_preparation_for_future_phases():
    """Reference literals should prepare for future language features."""
    # These references will be used in future phases for:
    # - Polymorphic dispatch (#tag)
    # - Shape morphing (~shape)
    # - Function calls (|function)

    references = [
        "#status",
        "~user",
        "|validate",
        "#error.timeout",
        "~database.record",
        "|json.parse",
        "#active/std",
        "~config/app",
        "|connect/database",
    ]

    for ref in references:
        result = comp.parse(ref)
        # Verify the result is a reference type with a string name
        assert (isinstance(result, comp.TagReference) or
                isinstance(result, comp.ShapeReference) or
                isinstance(result, comp.FunctionReference))
        # The helper functions already check the name attribute


def test_error_messages_are_specific():
    """Error messages should clearly identify the problem."""
    # Test specific error messages for different failure modes

    # Empty reference
    with pytest.raises(comp.ParseError) as exc_info:
        comp.parse("#")
    assert (
        "syntax error" in str(exc_info.value).lower()
        or "invalid character" in str(exc_info.value).lower()
    )

    # Invalid start character
    with pytest.raises(comp.ParseError) as exc_info:
        comp.parse("#123abc")
    assert (
        "syntax error" in str(exc_info.value).lower()
        or "invalid character" in str(exc_info.value).lower()
    )

    # Invalid hierarchy
    with pytest.raises(comp.ParseError) as exc_info:
        comp.parse("#..invalid")
    assert (
        "syntax error" in str(exc_info.value).lower()
        or "invalid input" in str(exc_info.value).lower()
        or "invalid character" in str(exc_info.value).lower()
    )

    # Invalid module reference
    with pytest.raises(comp.ParseError) as exc_info:
        comp.parse("#/")
    assert (
        "syntax error" in str(exc_info.value).lower()
        or "invalid character" in str(exc_info.value).lower()
    )


def _assertTag(value, match):
    """Helper to assert a parsed tag reference matches expected name."""
    assert isinstance(value, comp.TagReference)
    assert value.name == match


def _assertShape(value, match):
    """Helper to assert a parsed shape reference matches expected name."""
    assert isinstance(value, comp.ShapeReference)
    assert value.name == match


def _assertFunc(value, match):
    """Helper to assert a parsed function reference matches expected name."""
    assert isinstance(value, comp.FunctionReference)
    assert value.name == match
