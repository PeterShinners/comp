"""
Test cases for reference literal parsing - Phase 04.

SPECIFICATION SUMMARY:
Reference literals for tags (#tag), shapes (~shape), and functions (|function)
using unified parsing pattern with hierarchical and module references.

REQUIREMENTS FROM DESIGN DOCS:
- Unified reference pattern: 99% shared parsing logic for #, ~, |
- Local references: #identifier, ~identifier, |identifier
- Hierarchical references: #identifier.qualified.path
- Module references: #identifier/module
- Full references: #identifier.qualified.path/module
- Lisp-case naming: #user-name, ~api-response, |parse-config

PARSER EXPECTATIONS:
- comp.parse("#true") → TagLiteral("true")
- comp.parse("~num") → ShapeLiteral("num")
- comp.parse("|connect") → FunctionLiteral("connect")
- comp.parse("#timeout.error.status") → TagLiteral("timeout.error.status")
- comp.parse("~record/database") → ShapeLiteral("record/database")

ERROR CASES TO HANDLE:
- Invalid references: #123, ~, |
- Empty components: #.invalid, #/empty
- Invalid identifiers in references
- Malformed hierarchy: #..double.dot

AST NODE STRUCTURE:
- TagLiteral: name (str)
- ShapeLiteral: name (str)
- FunctionLiteral: name (str)

IMPLEMENTATION DETAILS:
Comprehensive tests for unified reference literal parsing pattern.

KEY FEATURES TESTED:

TAG LITERALS (#):
- Simple tags: #true, #false, #active, #error
- Hierarchical tags: #timeout.error.status, #http.get.method
- Module tags: #error/std, #active/other
- Full references: #timeout.error.status/std

SHAPE LITERALS (~):
- Simple shapes: ~num, ~str, ~bool, ~user
- Hierarchical shapes: ~database.record, ~ui.component
- Module shapes: ~record/database, ~component/ui
- Full references: ~database.record/persistence

FUNCTION LITERALS (|):
- Simple functions: |connect, |validate, |process
- Hierarchical functions: |database.query, |json.parse
- Module functions: |query/database, |parse/json
- Full references: |database.query.select/persistence

UNIFIED PATTERN TESTING:
- 99% shared parsing logic across all three types
- Consistent naming conventions (lisp-case, kebab-case)
- Error handling for invalid references, hierarchies, modules
- Integration with existing literal types

DESIGN COMPLIANCE:
- Reversed hierarchy notation (most specific first)
- Dot notation for hierarchy (timeout.error.status)
- Slash notation for modules (identifier/module)
- UAX #31 + hyphen identifier rules
- Comprehensive error handling and clear error messages

TEST ORGANIZATION:
All tests follow the established patterns from Phase 2:
- Comprehensive docstrings with specification summaries
- Clear test organization by feature category
- Specific error testing with expected error messages
- Integration testing with existing functionality
- Preparation testing for future phases

ERROR HANDLING:
- Invalid format detection
- Boundary case testing
- Clear, specific error messages
- Integration failure scenarios

FUTURE-PROOFING:
- Tests prepare for subsequent language phases
- Integration points clearly documented
- Performance considerations included
- Extensibility patterns established

IMPLEMENTATION READINESS:
When Phase 4 is implemented:
1. Remove `@pytest.mark.skip` decorators from relevant tests
2. Implement missing AST nodes: `TagLiteral`, `ShapeLiteral`, `FunctionLiteral`
3. Update main parser to handle reference literal parsing
4. Tests will immediately validate implementation correctness

The tests are designed to pass immediately once the implementation is complete,
providing comprehensive validation of the language specifications from the design documents.

NOTE: All tests in this file are currently skipped as Phase 04
(reference literals) is not implemented yet.
"""

import pytest

import comp


# ============================================================================
# TAG LITERAL TESTS
# ============================================================================


def test_parse_simple_tags():
    """Simple tag references without hierarchy."""
    result = comp.parse("#true")
    _assertTag(result, "true")

    result = comp.parse("#false")
    _assertTag(result, "false")

    result = comp.parse("#active")
    _assertTag(result, "active")

    result = comp.parse("#error")
    _assertTag(result, "error")


def test_parse_lisp_case_tags():
    """Tags using lisp-case naming convention."""
    result = comp.parse("#user-name")
    assert isinstance(result, comp.TagReference)
    assert result.name == "user-name"

    result = comp.parse("#error-status")
    assert isinstance(result, comp.TagReference)
    assert result.name == "error-status"

    result = comp.parse("#long-descriptive-name")
    assert isinstance(result, comp.TagReference)
    assert result.name == "long-descriptive-name"


def test_parse_hierarchical_tags():
    """Tags with hierarchical references using dot notation."""
    result = comp.parse("#timeout.error")
    assert isinstance(result, comp.TagReference)
    assert result.name == "timeout.error"

    result = comp.parse("#timeout.error.status")
    assert isinstance(result, comp.TagReference)
    assert result.name == "timeout.error.status"

    result = comp.parse("#network.error.status")
    assert isinstance(result, comp.TagReference)
    assert result.name == "network.error.status"

    result = comp.parse("#http.get.method")
    assert isinstance(result, comp.TagReference)
    assert result.name == "http.get.method"


def test_parse_module_tags():
    """Tags with module references using slash notation."""
    result = comp.parse("#error/std")
    assert isinstance(result, comp.TagReference)
    assert result.name == "error/std"

    result = comp.parse("#active/other")
    assert isinstance(result, comp.TagReference)
    assert result.name == "active/other"

    result = comp.parse("#status/user-auth")
    assert isinstance(result, comp.TagReference)
    assert result.name == "status/user-auth"


def test_parse_full_tags():
    """Tags with both hierarchy and module references."""
    result = comp.parse("#timeout.error.status/std")
    assert isinstance(result, comp.TagReference)
    assert result.name == "timeout.error.status/std"

    result = comp.parse("#active.status/other")
    assert isinstance(result, comp.TagReference)
    assert result.name == "active.status/other"

    result = comp.parse("#primary.button.ui/components")
    assert isinstance(result, comp.TagReference)
    assert result.name == "primary.button.ui/components"


# ============================================================================
# SHAPE LITERAL TESTS
# ============================================================================


def test_parse_simple_shapes():
    """Simple shape references without hierarchy."""
    result = comp.parse("~num")
    assert isinstance(result, comp.ShapeReference)
    assert result.name == "num"

    result = comp.parse("~str")
    assert isinstance(result, comp.ShapeReference)
    assert result.name == "str"

    result = comp.parse("~bool")
    assert isinstance(result, comp.ShapeReference)
    assert result.name == "bool"

    result = comp.parse("~user")
    assert isinstance(result, comp.ShapeReference)
    assert result.name == "user"


def test_parse_lisp_case_shapes():
    """Shapes using lisp-case naming convention."""
    result = comp.parse("~user-profile")
    assert isinstance(result, comp.ShapeReference)
    assert result.name == "user-profile"

    result = comp.parse("~api-response")
    assert isinstance(result, comp.ShapeReference)
    assert result.name == "api-response"

    result = comp.parse("~database-record")
    assert isinstance(result, comp.ShapeReference)
    assert result.name == "database-record"


def test_parse_hierarchical_shapes():
    """Shapes with hierarchical references using dot notation."""
    result = comp.parse("~database.record")
    assert isinstance(result, comp.ShapeReference)
    assert result.name == "database.record"

    result = comp.parse("~ui.component")
    assert isinstance(result, comp.ShapeReference)
    assert result.name == "ui.component"

    result = comp.parse("~math.vector")
    assert isinstance(result, comp.ShapeReference)
    assert result.name == "math.vector"

    result = comp.parse("~http.request.headers")
    assert isinstance(result, comp.ShapeReference)
    assert result.name == "http.request.headers"


def test_parse_module_shapes():
    """Shapes with module references using slash notation."""
    result = comp.parse("~record/database")
    assert isinstance(result, comp.ShapeReference)
    assert result.name == "record/database"

    result = comp.parse("~component/ui")
    assert isinstance(result, comp.ShapeReference)
    assert result.name == "component/ui"

    result = comp.parse("~user/auth")
    assert isinstance(result, comp.ShapeReference)
    assert result.name == "user/auth"


def test_parse_full_shapes():
    """Shapes with both hierarchy and module references."""
    result = comp.parse("~database.record/persistence")
    assert isinstance(result, comp.ShapeReference)
    assert result.name == "database.record/persistence"

    result = comp.parse("~button.primary.ui/components")
    assert isinstance(result, comp.ShapeReference)
    assert result.name == "button.primary.ui/components"

    result = comp.parse("~vector.math/geometry")
    assert isinstance(result, comp.ShapeReference)
    assert result.name == "vector.math/geometry"


# ============================================================================
# FUNCTION LITERAL TESTS
# ============================================================================


def test_parse_simple_functions():
    """Simple function references without hierarchy."""
    result = comp.parse("|connect")
    assert isinstance(result, comp.FunctionReference)
    assert result.name == "connect"

    result = comp.parse("|validate")
    assert isinstance(result, comp.FunctionReference)
    assert result.name == "validate"

    result = comp.parse("|process")
    assert isinstance(result, comp.FunctionReference)
    assert result.name == "process"

    result = comp.parse("|save")
    assert isinstance(result, comp.FunctionReference)
    assert result.name == "save"


def test_parse_kebab_case_functions():
    """Functions using kebab-case naming convention."""
    result = comp.parse("|parse-config")
    assert isinstance(result, comp.FunctionReference)
    assert result.name == "parse-config"

    result = comp.parse("|send-email")
    assert isinstance(result, comp.FunctionReference)
    assert result.name == "send-email"

    result = comp.parse("|validate-input")
    assert isinstance(result, comp.FunctionReference)
    assert result.name == "validate-input"


def test_parse_hierarchical_functions():
    """Functions with hierarchical references using dot notation."""
    result = comp.parse("|database.query")
    assert isinstance(result, comp.FunctionReference)
    assert result.name == "database.query"

    result = comp.parse("|json.parse")
    assert isinstance(result, comp.FunctionReference)
    assert result.name == "json.parse"

    result = comp.parse("|math.sqrt")
    assert isinstance(result, comp.FunctionReference)
    assert result.name == "math.sqrt"

    result = comp.parse("|http.get.request")
    assert isinstance(result, comp.FunctionReference)
    assert result.name == "http.get.request"


def test_parse_module_functions():
    """Functions with module references using slash notation."""
    result = comp.parse("|query/database")
    assert isinstance(result, comp.FunctionReference)
    assert result.name == "query/database"

    result = comp.parse("|parse/json")
    assert isinstance(result, comp.FunctionReference)
    assert result.name == "parse/json"

    result = comp.parse("|validate/auth")
    assert isinstance(result, comp.FunctionReference)
    assert result.name == "validate/auth"


def test_parse_full_functions():
    """Functions with both hierarchy and module references."""
    result = comp.parse("|database.query.select/persistence")
    assert isinstance(result, comp.FunctionReference)
    assert result.name == "database.query.select/persistence"

    result = comp.parse("|json.parse.stream/parser")
    assert isinstance(result, comp.FunctionReference)
    assert result.name == "json.parse.stream/parser"

    result = comp.parse("|user.auth.validate/security")
    assert isinstance(result, comp.FunctionReference)
    assert result.name == "user.auth.validate/security"


# ============================================================================
# UNIFIED PATTERN TESTS
# ============================================================================


def test_unified_pattern_consistency():
    """All three reference types should follow identical patterns."""
    # Simple references
    tag = comp.parse("#status")
    shape = comp.parse("~status")
    func = comp.parse("|status")

    assert isinstance(tag, comp.TagReference)
    assert isinstance(shape, comp.ShapeReference)
    assert isinstance(func, comp.FunctionReference)

    assert tag.name == "status"
    assert shape.name == "status"
    assert func.name == "status"

    # Hierarchical references
    tag_hier = comp.parse("#error.status")
    shape_hier = comp.parse("~error.status")
    func_hier = comp.parse("|error.status")

    assert tag_hier.name == "error.status"
    assert shape_hier.name == "error.status"
    assert func_hier.name == "error.status"

    # Module references
    tag_mod = comp.parse("#status/std")
    shape_mod = comp.parse("~status/std")
    func_mod = comp.parse("|status/std")

    assert tag_mod.name == "status/std"
    assert shape_mod.name == "status/std"
    assert func_mod.name == "status/std"

    # Full references
    tag_full = comp.parse("#error.status/std")
    shape_full = comp.parse("~error.status/std")
    func_full = comp.parse("|error.status/std")

    assert tag_full.name == "error.status/std"
    assert shape_full.name == "error.status/std"
    assert func_full.name == "error.status/std"


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

        assert isinstance(tag, comp.TagReference)
        assert isinstance(shape, comp.ShapeReference)
        assert isinstance(func, comp.FunctionReference)

        assert tag.name == pattern
        assert shape.name == pattern
        assert func.name == pattern


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


def test_invalid_identifier_characters():
    """References with invalid identifier characters should raise ParseError."""
    invalid_chars = [
        "#user@name",  # @ not allowed
        "~user$name",  # $ not allowed
        "|user%name",  # % not allowed
        "#user name",  # Space not allowed
        "~user\tname",  # Tab not allowed
        "|user\nname",  # Newline not allowed
        "#user=value",  # = not allowed
        "~user*strong",  # * not allowed
        "|user?weak",  # ? not allowed (except in boolean naming)
    ]

    for invalid in invalid_chars:
        with pytest.raises(comp.ParseError):
            comp.parse(invalid)


def test_reserved_sigils():
    """Other sigils should not be valid for references."""
    reserved_sigils = [
        "@local",  # @ reserved for local scope
        "$scope",  # $ reserved for scopes
        "^arg",  # ^ reserved for arguments
        "!directive",  # ! reserved for directives
        "&privacy",  # & reserved for privacy structures
        "%template",  # % reserved for templates
        "??fallback",  # ?? reserved for fallback
    ]

    for reserved in reserved_sigils:
        with pytest.raises(comp.ParseError):
            comp.parse(reserved)


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
    assert isinstance(tag_result, comp.TagReference)
    assert tag_result.name == "active"

    shape_result = comp.parse("~num")
    assert isinstance(shape_result, comp.ShapeReference)
    assert shape_result.name == "num"

    func_result = comp.parse("|connect")
    assert isinstance(func_result, comp.FunctionReference)
    assert func_result.name == "connect"


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
        assert hasattr(result, "name")
        assert isinstance(result.name, str)
        assert len(result.name) > 0


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
