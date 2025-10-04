"""
Test cases for tag definition generators - Phase 11 Extension.

SPECIFICATION:
- Tag generators support auto-generating child values
- Generator can be a function reference: !tag #color |name/tag = {#red #green}
- Generator can be an inline block: !tag #status :{[name |upper]} = {#active}

The generator is stored in the `generator` field of the TagDefinition AST node.

PARSER EXPECTATIONS:
- comp.parse_module("!tag #color |name/tag = {#red}") → TagDefinition with generator
- Generator should be FuncRef or Block node
- Round-trip: parse(code).unparse() should preserve the generator

AST NODES: TagDefinition (with generator field), FuncRef, Block
"""

import comp
import comptest


@comptest.params(
    "code",
    func_ref=("!tag #color |name/tag = {#red #green #blue}",),
    inline_block=("!tag #status :{[name |upper]} = {#active #inactive}",),
    complex_func=("!tag #error |bitflag/tag = {#timeout #network #parse}",),
)
def test_tag_generator_syntax(key, code):
    """Test that tag generators parse and round-trip correctly."""
    result = comp.parse_module(code)

    # Should parse as a Module
    assert isinstance(result, comp.Module)
    assert len(result.statements) == 1

    # First statement should be a TagDefinition
    tag_def = result.statements[0]
    assert isinstance(tag_def, comp.TagDefinition)

    # Should have a real generator (not Placeholder)
    assert not isinstance(tag_def.generator, comp.Placeholder), f"Expected real generator, got Placeholder for {code}"

    # Should have children (tag child definitions) in body_kids
    assert len(tag_def.body_kids) > 0, f"Expected children for {code}"

    # All body_kids should be TagChild nodes (not the generator, not TagDefinition)
    for kid in tag_def.body_kids:
        assert isinstance(kid, comp.TagChild), (
            f"Expected all body_kids to be TagChild, got {type(kid).__name__}"
        )

    # Round-trip test
    comptest.roundtrip(result)


def test_tag_generator_func_ref():
    """Test that function reference generators are FuncRef nodes."""
    code = "!tag #color |name/tag = {#red #green}"
    result = comp.parse_module(code)
    tag_def = result.statements[0]

    # Generator should be a FuncRef
    assert isinstance(tag_def.generator, comp.FuncRef)
    assert tag_def.generator.tokens == ('name',)
    assert tag_def.generator.namespace == 'tag'


def test_tag_generator_inline_block():
    """Test that inline block generators are Block nodes."""
    code = "!tag #status :{[name |upper]} = {#active #inactive}"
    result = comp.parse_module(code)
    tag_def = result.statements[0]

    # Generator should be a Block
    assert isinstance(tag_def.generator, comp.Block)
    # Block should have pipeline content
    assert len(tag_def.generator.kids) > 0


def test_tag_without_generator():
    """Test that tags without generators have generator=None."""
    code = "!tag #status = {#active #inactive}"
    result = comp.parse_module(code)
    tag_def = result.statements[0]

    # Should not have a generator (None, not Placeholder)
    assert tag_def.generator is None


def test_tag_generator_with_value():
    """Test tag with generator and explicit value."""
    code = "!tag #priority |sequential/tag = 10"
    result = comp.parse_module(code)
    tag_def = result.statements[0]

    # Should have a generator
    assert isinstance(tag_def.generator, comp.FuncRef)

    # Should have one child (the Number value) in body_kids
    assert len(tag_def.body_kids) == 1
    assert isinstance(tag_def.body_kids[0], comp.Number)

    # Round-trip
    comptest.roundtrip(result)


def test_nested_tags_preserve_generators():
    """Test that nested tag definitions don't interfere with generators."""
    code = "!tag #outer |gen/tag = {#inner = {#deep}}"
    result = comp.parse_module(code)
    tag_def = result.statements[0]

    # Outer tag should have generator
    assert isinstance(tag_def.generator, comp.FuncRef)

    # Should have children
    assert len(tag_def.kids) > 0

    # Round-trip
    comptest.roundtrip(result)


def test_multiple_generators():
    """Test module with multiple tags with generators."""
    code = """!tag #color |name/tag = {#red #green}
!tag #status :{[name |upper]} = {#active #inactive}"""

    result = comp.parse_module(code)
    assert len(result.statements) == 2

    # Both should have generators
    assert result.statements[0].generator is not None
    assert result.statements[1].generator is not None

    # Round-trip
    comptest.roundtrip(result)
