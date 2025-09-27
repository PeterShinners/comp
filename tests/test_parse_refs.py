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

# Valid reference test cases - comprehensive coverage
valid_reference_cases = [
    # Tags - simple, kebab-case, hierarchical, module, full
    ("#true", "TagReference", "true"),
    ("#active", "TagReference", "active"),
    ("#123", "IndexReference", "123"),  # Numeric index reference
    ("#user-name", "TagReference", "user-name"),
    ("#error-status", "TagReference", "error-status"),
    ("#timeout.error", "TagReference", "timeout.error"),
    ("#timeout.error.status", "TagReference", "timeout.error.status"),
    ("#error/std", "TagReference", "error/std"),
    ("#status/user-auth", "TagReference", "status/user-auth"),
    ("#timeout.error.status/std", "TagReference", "timeout.error.status/std"),
    ("#primary.button.ui/components", "TagReference", "primary.button.ui/components"),
    # Shapes - same patterns as tags
    ("~num", "ShapeReference", "num"),
    ("~bool", "ShapeReference", "bool"),
    ("~user-profile", "ShapeReference", "user-profile"),
    ("~api-response", "ShapeReference", "api-response"),
    ("~database.record", "ShapeReference", "database.record"),
    ("~ui.component", "ShapeReference", "ui.component"),
    ("~record/database", "ShapeReference", "record/database"),
    ("~user/auth", "ShapeReference", "user/auth"),
    ("~database.record/persistence", "ShapeReference", "database.record/persistence"),
    ("~button.primary.ui/components", "ShapeReference", "button.primary.ui/components"),
    # Functions - same patterns as tags
    ("|connect", "FunctionReference", "connect"),
    ("|validate", "FunctionReference", "validate"),
    ("|parse-config", "FunctionReference", "parse-config"),
    ("|send-email", "FunctionReference", "send-email"),
    ("|database.query", "FunctionReference", "database.query"),
    ("|json.parse", "FunctionReference", "json.parse"),
    ("|query/database", "FunctionReference", "query/database"),
    ("|validate/auth", "FunctionReference", "validate/auth"),
    (
        "|database.query.select/persistence",
        "FunctionReference",
        "database.query.select/persistence",
    ),
    (
        "|user.auth.validate/security",
        "FunctionReference",
        "user.auth.validate/security",
    ),
    # Mixed naming conventions (test one of each type)
    ("#with_underscores", "TagReference", "with_underscores"),
    ("~mixedCase", "ShapeReference", "mixedCase"),
    ("|用户名", "FunctionReference", "用户名"),  # Unicode
    ("#naïve", "TagReference", "naïve"),  # Accented
]


@pytest.mark.parametrize(
    "input_text,expected_type,expected_name",
    valid_reference_cases,
    ids=[f"{case[1][:-9].lower()}-{case[2]}" for case in valid_reference_cases],
)
def test_valid_references(input_text, expected_type, expected_name):
    """Test all valid reference patterns: tags, shapes, functions with various naming conventions."""
    result = comp.parse(input_text)
    assert type(result).__name__ == expected_type

    # IndexReference uses 'index' attribute, others use 'name'
    if expected_type == "IndexReference":
        assert int(result.index.value) == int(expected_name)
    else:
        assert result.name == expected_name


# Invalid reference test cases
invalid_reference_cases = [
    # Empty references
    ("#", "empty tag"),
    ("~", "empty shape"),
    ("|", "empty function"),
    # Invalid start characters
    ("#-invalid", "tag starts with hyphen"),
    ("~-invalid", "shape starts with hyphen"),
    ("|-invalid", "function starts with hyphen"),
    # Invalid hierarchy
    ("#.invalid", "tag starts with dot"),
    ("~invalid.", "shape ends with dot"),
    ("|..double", "function double dots"),
    ("#invalid..dot", "tag double dots in middle"),
    # Invalid module syntax
    ("#/empty", "tag missing identifier before slash"),
    ("~invalid/", "shape missing module after slash"),
    ("|invalid//", "function double slashes"),
    ("#/", "tag just slash"),
    # Invalid characters in identifiers
    ("#user@name", "tag with @"),
    ("~user$name", "shape with $"),
    ("#user=value", "tag with ="),
    # Reserved sigils
    ("@local", "@ reserved for local scope"),
    ("$scope", "$ reserved for scopes"),
    ("^arg", "^ reserved for arguments"),
    ("!directive", "! reserved for directives"),
    ("&privacy", "& reserved for privacy"),
    ("%template", "% reserved for templates"),
    ("??fallback", "?? reserved for fallback"),
]


@pytest.mark.parametrize(
    "invalid_input,description",
    invalid_reference_cases,
    ids=[case[1] for case in invalid_reference_cases],
)
def test_invalid_references(invalid_input, description):
    """Test that invalid reference syntax raises parse errors."""
    with pytest.raises(Exception) as exc_info:
        comp.parse(invalid_input)

    error_msg = str(exc_info.value).lower()
    assert (
        "syntax error" in error_msg
        or "parse" in error_msg
        or "unexpected" in error_msg
        or "invalid" in error_msg
        or "expected single expression" in error_msg
    ), f"Expected parse error for {description}: {invalid_input}"


def test_integration_with_other_literals():
    """References should work alongside other literal types."""
    # Test all literal types work together
    examples = [
        ("42", "NumberLiteral", 42),
        ('"hello"', "StringLiteral", "hello"),
        ("#active", "TagReference", "active"),
        ("~user", "ShapeReference", "user"),
        ("|connect", "FunctionReference", "connect"),
    ]

    for input_text, expected_type, expected_value in examples:
        result = comp.parse(input_text)
        assert type(result).__name__ == expected_type
        if hasattr(result, "value"):
            assert result.value == expected_value
        elif hasattr(result, "name"):
            assert result.name == expected_value


def test_reference_equality():
    """References should support equality comparison."""
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
    assert tag1 != shape != func
