"""
Test cases for tag definition parsing - Phase 11.

SPECIFICATION:
- Simple definitions: !tag #status
- Nested definitions: !tag #status = {#active #inactive}
- Flat definitions: !tag #status.error.timeout
- Multiple definitions in a module

This is a minimal first pass to establish tag definition parsing.
Tag references (e.g., #status in expressions) are tested in test_parse_refs.py

PARSER EXPECTATIONS:
- comp.parse("!tag #status") → Module with TagDefinition
- comp.parse("!tag #status = {#active}") → TagDefinition with children
- Round-trip: parse(code).unparse() should preserve structure

AST NODES: Module, TagDefinition, TagReference

NOTE: Tag values (!tag #status = 1) are not yet implemented - future phase.
"""

import comp
import comptest


@comptest.params(
    "code",
    simple=("!tag #status",),
    nested=("!tag #status = {#active #inactive}",),
    deep_nested=("!tag #status = {#error = {#timeout #network}}",),
    flat=("!tag #status.error.timeout",),
)
def test_valid_tag_definitions(key, code):
    """Test that valid tag definition syntax parses and round-trips correctly."""
    result = comp.parse(code)

    # Should parse as a Module
    assert isinstance(result, comp.Module), (
        f"Expected Module, got {type(result).__name__}\n"
        f"  Code: {code}"
    )

    # Should have at least one statement
    assert len(result.statements) > 0, (
        f"Expected module to have statements\n"
        f"  Code: {code}"
    )

    # First statement should be a TagDefinition
    first_stmt = result.statements[0]
    assert isinstance(first_stmt, comp.TagDefinition), (
        f"Expected TagDefinition, got {type(first_stmt).__name__}\n"
        f"  Code: {code}"
    )

    # Round-trip test
    comptest.roundtrip(result)


@comptest.params(
    "code",
    no_tag_reference=("!tag",),
    empty_braces=("!tag #status = {}",),
    missing_equals=("!tag #status {#active}",),
    invalid_tag_name=("!tag #123invalid",),
    nested_no_tag=("!tag #status = {active}",),
)
def test_invalid_tag_definitions(key, code):
    """Test that invalid tag definition syntax fails to parse."""
    comptest.invalid_parse(code, match=r"parse error|unexpected|syntax error|expected")


def test_multiple_tag_definitions():
    """Test parsing multiple tag definitions in a single module."""
    code = """!tag #status
!tag #priority"""

    result = comp.parse(code)
    assert isinstance(result, comp.Module)
    assert len(result.statements) == 2

    # Both should be TagDefinitions
    for stmt in result.statements:
        assert isinstance(stmt, comp.TagDefinition)

    comptest.roundtrip(result)


def test_tag_definition_with_nested_hierarchy():
    """Test that nested tag definitions create proper hierarchy."""
    code = "!tag #status = {#active #inactive #error = {#timeout}}"

    result = comp.parse(code)
    tag_def = result.statements[0]

    assert isinstance(tag_def, comp.TagDefinition)
    assert tag_def.tag is not None
    assert tag_def.children is not None
    assert len(tag_def.children) == 3  # active, inactive, error

    # The third child (#error) should itself have children
    error_child = tag_def.children[2]
    assert isinstance(error_child, comp.TagDefinition)
    assert error_child.children is not None
    assert len(error_child.children) == 1  # timeout
