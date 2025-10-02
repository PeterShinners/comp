"""
Test cases for reference literal parsing.

Tests tag references with various naming conventions including:
- Simple identifiers: #active, #true
- Numeric indices: #123
- Kebab-case: #user-name
- Hierarchical: #timeout.error
- Module paths: #error/std
- Complex combinations: #timeout.error.status/std

Shape (~) and function (|) references are not yet available as general expressions.
"""

import comp
import comptest


@comptest.params(
    "expression",
    simple=("#active",),
    numeric=("#123",),
    kebab=("#user-name",),
    hierarchical=("#timeout.error",),
    deep_hierarchical=("#timeout.error.status",),
    module=("#error/std",),
    module_kebab=("#status/user-auth",),
    full_path=("#timeout.error.status/std",),
    complex=("#primary.button.ui/components",),
    underscore=("#with_underscores",),
    mixed_case=("#mixedCase",),
    unicode=("#用户名",),
    accented=("#naïve",),
)
def test_valid_tag_references(key, expression):
    """Test that valid tag references parse and round-trip correctly."""
    result = comp.parse_expr(expression)
    # Verify it parsed successfully and round-trips
    comptest.roundtrip(result)
    # Verify unparsing gives back the original
    comptest.assert_unparse(result, expression)


@comptest.params(
    "expression",
    empty=("#",),
    starts_hyphen=("#-invalid",),
    starts_dot=("#.invalid",),
    ends_dot=("#invalid.",),
    double_dots=("#invalid..dot",),
    empty_before_slash=("#/empty",),
    double_slash=("#invalid//",),
    just_slash=("#/",),
    with_at=("#user@name",),
    with_dollar=("#user$name",),
)
def test_invalid_tag_references(key, expression):
    """Test that invalid tag reference syntax fails to parse."""
    comptest.invalid_parse(expression, match=r"parse error|unexpected|syntax error")


@comptest.params(
    "expression",
    exclamation=("!directive",),
    ampersand=("&privacy",),
    percent=("%template",),
    double_question=("??fallback",),
)
def test_reserved_sigils(key, expression):
    """Test that reserved sigil characters are not valid reference prefixes."""
    comptest.invalid_parse(expression, match=r"parse error|unexpected|syntax error")


def test_tag_reference_with_other_literals():
    """Tag references should parse correctly alongside other literal types."""
    # Test that each literal type parses successfully
    literals = [
        "42",
        '"hello"',
        "#active",
    ]

    for expr in literals:
        result = comp.parse_expr(expr)
        comptest.roundtrip(result)

