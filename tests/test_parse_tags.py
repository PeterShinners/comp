"""
Test cases for tag definition parsing.

SPECIFICATION:
- Simple definitions: !tag #status
- Nested definitions: !tag #status = {#active #inactive}
- Flat definitions: !tag #status.error.timeout
- Tag values: !tag #status = 42, !tag #calc = 1 + 2
- Tag generators: !tag #color |name/tag = {#red}
- Multiple definitions in a module

This comprehensive test suite covers:
1. Basic tag syntax (simple, nested, flat)
2. Tag values (literals and expressions)
3. Tag generators (function references and inline blocks)
4. Invalid syntax cases

PARSER EXPECTATIONS:
- comp.parse_module("!tag #status") → Module with TagDefinition
- comp.parse_module("!tag #status = {#active}") → TagDefinition with children
- comp.parse_module("!tag #count = 42") → TagDefinition with value
- Round-trip: parse(code).unparse() should preserve structure

AST NODES: Module, TagDefinition, TagReference, Number, String, BinaryOp, UnaryOp, FuncRef, Block
"""

import comp
import comptest


# === BASIC TAG DEFINITIONS ===

@comptest.params(
    "code",
    simple=("!tag #status",),
    nested=("!tag #status = {#active #inactive}",),
    deep_nested=("!tag #status = {#error = {#timeout #network}}",),
    flat=("!tag #status.error.timeout",),
)
def test_valid_tag_definitions(key, code):
    """Test that valid tag definition syntax parses and round-trips correctly."""
    result = comp.parse_module(code)

    # Should parse as a Module
    assert isinstance(result, comp.ast.Module), (
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
    assert isinstance(first_stmt, comp.ast.TagDefinition), (
        f"Expected TagDefinition, got {type(first_stmt).__name__}\n"
        f"  Code: {code}"
    )

    # Round-trip test
    comptest.roundtrip(result)


# === TAG VALUES (LITERALS) ===

@comptest.params(
    "code",
    number=("!tag #count = 42",),
    float_num=("!tag #ratio = 3.14",),
    hex_num=("!tag #mask = 0xFF",),
    binary_num=("!tag #flags = 0b1010",),
    string=('!tag #name = "Alice"',),
)
def test_tag_literal_values(key, code):
    """Test tag definitions with literal values."""
    result = comp.parse_module(code)
    tag_def = result.statements[0]

    assert isinstance(tag_def, comp.ast.TagDefinition)

    # Should have exactly one child (the value) in body_kids
    assert len(tag_def.body_kids) == 1, f"Expected 1 value child, got {len(tag_def.body_kids)}"

    # Value should be Number or String
    value = tag_def.body_kids[0]
    assert isinstance(value, (comp.ast.Number, comp.ast.String)), (
        f"Expected Number or String, got {type(value).__name__}"
    )

    # Round-trip
    comptest.roundtrip(result)


# === TAG VALUES (EXPRESSIONS) ===

@comptest.params(
    "code",
    addition=("!tag #sum = 9 + 9",),
    subtraction=("!tag #diff = 100 - 42",),
    multiplication=("!tag #product = 6 * 7",),
    division=("!tag #ratio = 100 / 4",),
    bit_shift_left=("!tag #flag1 = 1 << 0",),
    bit_shift_right=("!tag #shifted = 128 >> 3",),
    bitwise_and=("!tag #mask = 0xFF & 0x0F",),
    bitwise_or=("!tag #combined = 1 | 2",),
    bitwise_xor=("!tag #toggled = 5 ^ 3",),
    comparison_lt=("!tag #check = 5 < 10",),
    comparison_gt=("!tag #check = 10 > 5",),
    comparison_eq=("!tag #check = 42 == 42",),
    unary_minus=("!tag #negative = -100",),
    unary_plus=("!tag #positive = +42",),
    complex_expr=("!tag #calc = (1 + 2) * 3",),
    precedence=("!tag #result = 1 + 2 * 3",),
)
def test_tag_expression_values(key, code):
    """Test tag definitions with expression values."""
    result = comp.parse_module(code)
    tag_def = result.statements[0]

    assert isinstance(tag_def, comp.ast.TagDefinition)

    # Should have at least one child (the expression) in body_kids
    assert len(tag_def.body_kids) >= 1, f"Expected at least 1 child, got {len(tag_def.body_kids)}"

    # First body child should be an expression node (BinaryOp, UnaryOp) or literal
    value = tag_def.body_kids[0]
    assert isinstance(value, (comp.ast.BinaryOp, comp.ast.UnaryOp, comp.ast.Number, comp.ast.String)), (
        f"Expected expression node, got {type(value).__name__}"
    )

    # Round-trip
    comptest.roundtrip(result)


# === TAG VALUES WITH CHILDREN ===

@comptest.params(
    "code",
    value_and_children=("!tag #status = 1 {#active #inactive}",),
    expr_and_children=("!tag #flags = 1<<0 {#read #write}",),
    nested_values=("!tag #permissions = {#read = 1<<0 #write = 1<<1 #execute = 1<<2}",),
)
def test_tag_values_with_children(key, code):
    """Test tag definitions with both values and child tags."""
    result = comp.parse_module(code)
    tag_def = result.statements[0]

    assert isinstance(tag_def, comp.ast.TagDefinition)

    # Should have multiple children (value + tag children) in body_kids
    assert len(tag_def.body_kids) > 1, f"Expected multiple children, got {len(tag_def.body_kids)}"

    # Round-trip
    comptest.roundtrip(result)


# === TAG GENERATORS ===

@comptest.params(
    "code",
    func_ref=("!tag #color |name/tag = {#red #green #blue}",),
    inline_block=("!tag #status :{[name |upper]} = {#active #inactive}",),
    complex_func=("!tag #error |bitflag/tag = {#timeout #network #parse}",),
    gen_with_value=("!tag #priority |sequential/tag = 10",),
    gen_with_expr=("!tag #flags |gen = 1<<0 {#read #write}",),
)
def test_tag_generators(key, code):
    """Test that tag generators parse and round-trip correctly."""
    result = comp.parse_module(code)
    tag_def = result.statements[0]

    assert isinstance(tag_def, comp.ast.TagDefinition)

    # Should have a generator (FuncRef or Block, not Placeholder)
    assert not isinstance(tag_def.generator, comp.ast.Placeholder), f"Expected real generator, got Placeholder for {code}"

    # Generator should be FuncRef or Block
    assert isinstance(tag_def.generator, (comp.ast.FuncRef, comp.ast.Block)), (
        f"Expected FuncRef or Block, got {type(tag_def.generator).__name__}"
    )

    # Should have children (values or tag children) in body_kids
    assert len(tag_def.body_kids) > 0, f"Expected children for {code}"

    # Round-trip test
    comptest.roundtrip(result)


def test_tag_generator_func_ref():
    """Test that function reference generators are FuncRef nodes."""
    code = "!tag #color |name/tag = {#red #green}"
    result = comp.parse_module(code)
    tag_def = result.statements[0]

    # Generator should be a FuncRef
    assert isinstance(tag_def.generator, comp.ast.FuncRef)
    assert tag_def.generator.tokens == ('name',)
    assert tag_def.generator.namespace == 'tag'


def test_tag_generator_inline_block():
    """Test that inline block generators are Block nodes."""
    code = "!tag #status :{[name |upper]} = {#active #inactive}"
    result = comp.parse_module(code)
    tag_def = result.statements[0]

    # Generator should be a Block
    assert isinstance(tag_def.generator, comp.ast.Block)
    # Block should have pipeline content
    assert len(tag_def.generator.kids) > 0


def test_tag_without_generator():
    """Test that tags without generators have generator=None."""
    code = "!tag #status = {#active #inactive}"
    result = comp.parse_module(code)
    tag_def = result.statements[0]

    # Should not have a generator (None, not Placeholder)
    assert tag_def.generator is None


# === INVALID TAG SYNTAX ===

@comptest.params(
    "code",
    no_tag_reference=("!tag",),
    empty_braces=("!tag #status = {}",),
    missing_equals=("!tag #status {#active}",),
    invalid_tag_name=("!tag #123invalid",),
    nested_no_tag=("!tag #status = {active}",),
    structure_value=("!tag #bad = {x = 1}",),  # Structures not allowed as tag values
    block_value=("!tag #bad = {[x]}",),  # Blocks not allowed as tag values
)
def test_invalid_tag_definitions(key, code):
    """Test that invalid tag definition syntax fails to parse."""
    comptest.invalid_parse(code, match=r"parse error|unexpected|syntax error|expected")


# === MULTIPLE TAGS ===

def test_multiple_tag_definitions():
    """Test parsing multiple tag definitions in a single module."""
    code = """!tag #status
!tag #priority"""

    result = comp.parse_module(code)
    assert isinstance(result, comp.ast.Module)
    assert len(result.statements) == 2

    # Both should be TagDefinitions
    for stmt in result.statements:
        assert isinstance(stmt, comp.ast.TagDefinition)

    comptest.roundtrip(result)


def test_multiple_tags_with_values():
    """Test multiple tags with different value types."""
    code = """!tag #count = 42
!tag #name = "Alice"
!tag #flags = 1 << 2"""

    result = comp.parse_module(code)
    assert len(result.statements) == 3

    # All should be TagDefinitions
    for stmt in result.statements:
        assert isinstance(stmt, comp.ast.TagDefinition)
        # Each should have a value
        assert len(stmt.kids) >= 1

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


# === COMPLEX CASES ===

def test_tag_definition_with_nested_hierarchy():
    """Test that nested tag definitions create proper hierarchy."""
    code = "!tag #status = {#active #inactive #error = {#timeout}}"

    result = comp.parse_module(code)
    tag_def = result.statements[0]

    assert isinstance(tag_def, comp.ast.TagDefinition)
    assert tag_def.tokens is not None
    assert len(tag_def.body_kids) == 3  # active, inactive, error

    # The third child (#error) should itself have children (as TagChild)
    error_child = tag_def.body_kids[2]
    assert isinstance(error_child, comp.ast.TagChild)
    assert len(error_child.body_kids) == 1  # timeout


def test_nested_tags_preserve_generators():
    """Test that nested tag definitions don't interfere with generators."""
    code = "!tag #outer |gen/tag = {#inner = {#deep}}"
    result = comp.parse_module(code)
    tag_def = result.statements[0]

    # Outer tag should have generator
    assert isinstance(tag_def.generator, comp.ast.FuncRef)

    # Should have children in body_kids
    assert len(tag_def.body_kids) > 0

    # Round-trip
    comptest.roundtrip(result)


def test_bit_flags_realistic_example():
    """Test a realistic bit flags use case."""
    code = """!tag #permissions = {
    #read = 1<<0
    #write = 1<<1
    #execute = 1<<2
}"""

    result = comp.parse_module(code)
    tag_def = result.statements[0]

    assert isinstance(tag_def, comp.ast.TagDefinition)
    assert len(tag_def.body_kids) == 3

    # Each child should have a bit shift expression (as TagChild)
    for child in tag_def.body_kids:
        assert isinstance(child, comp.ast.TagChild)
        assert len(child.body_kids) == 1
        assert isinstance(child.body_kids[0], comp.ast.BinaryOp)
        assert child.body_kids[0].op == "<<"

    comptest.roundtrip(result)


def test_tag_all_features_combined():
    """Test tag with generator, expression value, and children."""
    code = "!tag #perms |bitflag/gen = 1<<0 {#read #write #execute}"
    result = comp.parse_module(code)
    tag_def = result.statements[0]

    # Should have generator
    assert isinstance(tag_def.generator, comp.ast.FuncRef)

    # Should have value (1<<0) plus 3 children in body_kids
    assert len(tag_def.body_kids) == 4

    # First body kid is the expression
    assert isinstance(tag_def.body_kids[0], comp.ast.BinaryOp)

    # Rest are tag children (TagChild nodes)
    for kid in tag_def.body_kids[1:]:
        assert isinstance(kid, comp.ast.TagChild)

    comptest.roundtrip(result)

