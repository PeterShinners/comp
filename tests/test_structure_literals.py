"""
Test cases for structure literal parsing - Phase 05.

SPECIFICATION:
- Basic structures: {}, {42}, {name="Alice"}
- Mixed fields: {x=10 "unnamed" y=20} - named and positional
- Nested structures: {1 {2 3} 4}, {user={name="Bob"}}
- All literal types: numbers, strings, references as values/keys
- Assignment operator: = for named fields

PARSER EXPECTATIONS:
- comp.parse("{}") → StructureLiteral([])
- comp.parse("{42}") → StructureLiteral([PositionalField(NumberLiteral(42))])
- comp.parse("{x=1}") → StructureLiteral([NamedField("x", NumberLiteral(1))])

AST NODES: StructureLiteral(fields), NamedField(name, value), PositionalField(value)

NOTE: This phase requires implementing StructureLiteral, NamedField, and PositionalField
AST nodes, plus extending the grammar to handle structure syntax.
"""

import pytest

import comp

# Valid structure literal test cases - should work when implemented
valid_structure_cases = [
    # Basic structures
    ("{}", 0, "empty structure"),
    ("{42}", 1, "single positional field"),
    ('{name="Alice"}', 1, "single named field"),
    # Multiple fields
    ("{1 2 3}", 3, "multiple positional fields"),
    ("{x=10 y=20}", 2, "multiple named fields"),
    ('{42 name="Bob" 3.14}', 3, "mixed positional fields"),
    # Mixed named and positional
    ('{x=10 "unnamed" y=20}', 3, "named and positional mixed"),
    ('{1 name="Alice" #false}', 3, "positional-named-positional"),
    # Nested structures
    ("{1 {2 3} 4}", 3, "nested positional structures"),
    ("{outer={inner=42}}", 1, "nested named structures"),
    ('{user={name="Bob" age=30}}', 1, "complex nested structure"),
    # All literal types
    ("{42 3.14 1e5 0xFF}", 4, "all number types"),
    ('{"hello" "world"}', 2, "multiple strings"),
    ("{foo bar baz}", 3, "multiple identifiers"),
    ('{count=42 name="Alice" valid=#true}', 3, "mixed types in named fields"),
    # Valid whitespacing
    ("{ -0\n}\n", 1, "newline"),
    ('{ day  = " Monday " }', 1, "extra spacing"),
    # String field names (supported in Phase 5)
    ('{"dog"="cat"}', 1, "string field name"),
]


@pytest.mark.parametrize(
    "input_str,length,description",
    valid_structure_cases,
    ids=[case[2] for case in valid_structure_cases],
)
def test_valid_structures(input_str, length, description):
    """Test that valid structure syntax parses successfully."""
    result = comp.parse(input_str)
    assert isinstance(result, comp.StructureLiteral)
    assert result is not None, f"Failed to parse {description}: {input_str}"
    assert len(result.fields) == length


# Invalid structure literal test cases - should fail
invalid_structure_cases = [
    # Malformed brackets
    ("{", "unclosed structure"),
    ("}", "unopened structure"),
    ("{{}", "unclosed inner structure"),
    # Invalid assignment syntax
    ("{=42}", "assignment without name"),
    ("{name=}", "assignment without value"),
    ("{x=y=42}", "chained assignment"),
    # Invalid field syntax
    ("{1,2}", "comma separators"),
    # Mixed syntax issues
    ("{42 x=}", "positional then incomplete named"),
    ("{=x 42}", "incomplete assignment then positional"),
    # Wrong name types
    ("{5=5}", "integer field name"),
    ("{+12e12=5}", "decimal field name"),
    ("{#true=#false}", "tag field name"),  # Will be valid future phase
    ("{{}=0}", "structure field name"),  # Will be valid future phase
]


@pytest.mark.parametrize(
    "input_str,description",
    invalid_structure_cases,
    ids=[case[1] for case in invalid_structure_cases],
)
def test_invalid_structures(input_str, description):
    """Test that invalid structure syntax raises parse errors."""
    with pytest.raises(Exception) as exc_info:
        comp.parse(input_str)

    error_msg = str(exc_info.value).lower()
    assert (
        "syntax error" in error_msg
        or "parse" in error_msg
        or "unexpected" in error_msg
        or "invalid" in error_msg
    ), f"Expected parse error for {description}: {input_str}"


def test_contents():
    """Test results for individual fields"""
    result = comp.parse('{max=3 "car" #true max={"cat"}}')
    assert isinstance(result, comp.StructureLiteral)
    assert len(result.fields) == 4

    assert isinstance(result.fields[0], comp.NamedField)
    assert result.fields[0].name == "max"
    assert result.fields[0].value.value == 3

    assert isinstance(result.fields[1], comp.PositionalField)
    assert result.fields[1].value.value == "car"

    assert isinstance(result.fields[2], comp.PositionalField)
    assert isinstance(result.fields[2].value, comp.TagReference)
    assert result.fields[2].value.name == "true"

    assert isinstance(result.fields[3], comp.NamedField)
    assert result.fields[3].name == "max"
    assert isinstance(result.fields[3].value, comp.StructureLiteral)
    assert len(result.fields[3].value.fields) == 1
