"""
Test cases for structure literal parsing - Phase 05.

SPECIFICATION:
- Basic structures: {}, {42}, {name="Alice"}
- Mixed fields: {x=10 "unnamed" y=20} - named and positional
- Nested structures: {1 {2 3} 4}, {user={name="Bob"}}
- All literal types: numbers, strings, references as values/keys
- Assignment operator: = for named fields
- Named block operations: name:{expression} as shorthand

PARSER EXPECTATIONS:
- comp.parse_expr("{}") → Structure([])
- comp.parse_expr("{42}") → Structure with one unnamed field
- comp.parse_expr("{x=1}") → Structure with one assignment
- Round-trip: parse(code).unparse() should match structure

AST NODES: Structure, StructAssign, StructUnnamed, etc.

NOTE: Refactored to use asttest helpers and matches() for clean testing.
"""

import comp
import asttest


@asttest.params(
    "code count",
    empty=("{}", 0),
    pos1=("{42}", 1),
    name1=('{name="Alice"}', 1),
    pos3=("{1 2 3}", 3),
    name2=("{x=10 y=20}", 2),
    mixp=('{42 name="Bob" 3.14}', 3),
    pnp=('{x=10 "unnamed" y=20}', 3),
    pnp2=('{1 name="Alice" #false}', 3),
    nestp=("{1 {2 3} 4}", 3),
    nestn=("{outer={inner=42}}", 1),
    deep=('{user={name="Bob" age=30}}', 1),
    nums=("{42 3.14 1e5 0xFF}", 4),
    strs=('{"hello" "world"}', 2),
    ids=("{foo bar baz}", 3),
    mix=('{count=42 name="Alice" valid=#true}', 3),
    nl=("{ -0\n}\n", 1),
    space=('{ day  = " Monday " }', 1),
)
def test_valid_structures(key, code, count):
    """Test that valid structure syntax parses and round-trips correctly."""
    struct = asttest.parse_value(code, comp.ast.Structure)
    assert len(struct.kids) == count, (
        f"Expected {count} children in structure for {key}, got {len(struct.kids)}\n"
        f"  Code: {code}"
    )
    asttest.roundtrip(struct)

    match key:
        case 'nestn':
            key, value = asttest.structure_field(struct, 0)
            assert key == "outer"
            assert isinstance(value, comp.ast.Structure)
        case 'nestp':
            key, value = asttest.structure_field(struct, 1)
            assert key is None
            assert isinstance(value, comp.ast.Structure)


# Invalid structure literal test cases - should fail with parse errors
@asttest.params(
    "code",
    unc="{",
    unop="}",
    unci="{{}",
    nonam="{=42}",
    noval="{name=}",
    chain="{x=y=42}",
    comma="{1,2}",
    pinc="{42 x=}",
    incp="{=x 42}",
    intk="{5=5}",
    deck="{+12e12=5}",
    tagk="{#true=#false}",
    strk="{{} =0}",
    strf='{"dog"="cat"}',
)
def test_invalid_structures(key, code):
    """Test that invalid structure syntax raises parse errors."""
    error_msg = asttest.invalid_parse(code)

    # Just verify we got a parse error with reasonable message
    error_lower = error_msg.lower()
    assert any(
        word in error_lower
        for word in ["parse", "unexpected", "error", "invalid", "syntax"]
    ), f"Expected descriptive parse error for {key}: {code}\nGot: {error_msg}"


@asttest.params(
    "code count",
    empty=(":{}", 0),
    pos3=(":{1 2 3}", 3),
    mix=(':{count=42 name="Alice" valid=#true}', 3),
    nl=(":{ -0\n}\n", 1),
    nest=(":{:{1} :{:{2}}}", 2),
    stru=(":{{1} {:{2}}}", 2),
)
def test_valid_block(key, code, count):
    """Test that valid structure syntax parses and round-trips correctly."""
    # Parse the code
    struct = asttest.parse_value(code, comp.ast.Block)
    assert len(struct.kids) == count, (
        f"Expected {count} children in structure for {key}, got {len(struct.kids)}\n"
        f"  Code: {code}"
    )
    asttest.roundtrip(struct)


# Invalid structure literal test cases - should fail with parse errors
@asttest.params(
    "code",
    unc=":{",
    unci="{:{}",
    pinc="{42 x=}",
)
def test_invalid_block(key, code):
    """Test that invalid structure syntax raises parse errors."""
    error_msg = asttest.invalid_parse(code)
