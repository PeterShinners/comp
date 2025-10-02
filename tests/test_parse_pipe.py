"""
Test cases for pipeline operations.

SPECIFICATION:
- Pipelines are used within structure assignments: {x = data |process}
- Pipeline operators: | (basic), |? (fallback), |<< (wrench/modifier)
- All assignments must be within {} braces

PARSER EXPECTATIONS:
- comptest.parse_value("{x = data}", comp.Structure) → Structure with StructAssign
- Structure assignments contain Pipeline nodes for piped values
- Tests should use unparse() for string matching rather than deep tree inspection

AST NODES: Structure, StructAssign, Pipeline, PipelineOp
"""

import pytest

import comp
import comptest


def test_pipeline_in_struct():
    """Test pipeline without explicit seed (starts with pipe operator)."""
    struct = comptest.parse_value("{x = ( |process)}", comp.Structure)
    comptest.roundtrip(struct)
    key, value = comptest.structure_field(struct, 0, comp.Pipeline)
    assert key == "x"
    # Pipeline without seed should have EmptyPipelineSeed as first child
    assert isinstance(value.seed, comp.EmptyPipelineSeed)
    assert isinstance(value.operations[0], comp.PipeFunc)
    assert "|process" in value.unparse()


def test_pipeline_with_seed():
    """Test pipeline with explicit seed expression."""
    struct = comptest.parse_value("{x = data |process}", comp.Structure)
    key, value = comptest.structure_field(struct, 0, comp.Pipeline)
    assert key == "x"
    # Pipeline with seed should have the seed expression as first child (not EmptyPipelineSeed)
    assert isinstance(value.seed, comp.Identifier)
    assert value.seed.unparse() == "data"
    assert isinstance(value.operations[0], comp.PipeFunc)
    assert "data" in value.unparse()
    assert "|process" in value.unparse()
    comptest.roundtrip(struct)


def test_multi_stage_pipeline():
    """Test pipeline with multiple stages."""
    struct = comptest.parse_value("{x = data |validate |transform}", comp.Structure)
    key, value = comptest.structure_field(struct, 0, comp.Pipeline)
    # Check it has multiple stages
    unparsed = value.unparse()
    assert "data" in unparsed
    assert "validate" in unparsed
    assert "transform" in unparsed
    comptest.roundtrip(struct)


def test_pipeline_with_scope():
    """Test pipeline using scope references."""
    struct = comptest.parse_value("{x = $in |process}", comp.Structure)
    key, value = comptest.structure_field(struct, 0, comp.Pipeline)
    unparsed = value.unparse()
    assert "$in" in unparsed
    assert "process" in unparsed
    comptest.roundtrip(struct)


def test_pipeline_with_numbers():
    """Test pipeline starting with number literal."""
    struct = comptest.parse_value("{x = 42 |double}", comp.Structure)
    key, value = comptest.structure_field(struct, 0, comp.Pipeline)
    assert "42" in value.unparse()
    comptest.roundtrip(struct)


def test_pipeline_with_strings():
    """Test pipeline starting with string literal."""
    struct = comptest.parse_value('{x = "hello" |upper}', comp.Structure)
    key, value = comptest.structure_field(struct, 0, comp.Pipeline)
    assert "hello" in value.unparse()
    comptest.roundtrip(struct)


def test_pipeline_with_field_access():
    """Test pipeline with field access (dot notation)."""
    struct = comptest.parse_value("{x = obj.field |process}", comp.Structure)
    key, value = comptest.structure_field(struct, 0, comp.Pipeline)
    assert key == "x"
    unparsed = value.unparse()
    assert "obj" in unparsed
    assert "field" in unparsed
    assert "." in unparsed
    comptest.roundtrip(struct)


def test_pipeline_failure_operator():
    """Test pipeline failure operator |?"""
    struct = comptest.parse_value("{x = data |? fallback}", comp.Structure)
    key, value = comptest.structure_field(struct, 0, comp.Pipeline)
    assert key == "x"
    unparsed = value.unparse()
    assert "|?" in unparsed
    assert "data" in unparsed
    assert "fallback" in unparsed
    comptest.roundtrip(struct)


@pytest.mark.skip(reason="Wrench not ready for parsing")
def test_pipeline_wrench_operator():
    """Test pipeline wrench/modifier operator |<<"""
    struct = comptest.parse_value("{x = data |<< modifier}", comp.Structure)
    key, value = comptest.structure_field(struct, 0, comp.Pipeline)
    assert key == "x"
    unparsed = value.unparse()
    assert "|<<" in unparsed
    assert "data" in unparsed
    assert "modifier" in unparsed
    comptest.roundtrip(struct)


@pytest.mark.skip(reason="Wrench not ready for parsing")
def test_chained_wrench_operator():
    """Test chained wrench operations."""
    struct = comptest.parse_value("{x = data |<< optimize |<< debug}", comp.Structure)
    key, value = comptest.structure_field(struct, 0, comp.Pipeline)
    assert key == "x"
    unparsed = value.unparse()
    assert "|<<" in unparsed
    assert "optimize" in unparsed
    assert "debug" in unparsed
    comptest.roundtrip(struct)


@pytest.mark.skip(reason="Wrench not ready for parsing")
def test_wrench_with_field_access():
    """Test wrench operator with field access on left side."""
    struct = comptest.parse_value("{x = obj.field |<< modifier}", comp.Structure)
    key, value = comptest.structure_field(struct, 0, comp.Pipeline)
    assert key == "x"
    unparsed = value.unparse()
    assert "obj.field" in unparsed or ("obj" in unparsed and "field" in unparsed)
    assert "|<<" in unparsed
    comptest.roundtrip(struct)


@pytest.mark.skip(reason="Wrench not ready for parsing")
def test_combined_pipeline_failure_and_wrench():
    """Test combining |? and |<< operators."""
    struct = comptest.parse_value("{x = data |? fallback |<< debug}", comp.Structure)
    key, value = comptest.structure_field(struct, 0, comp.Pipeline)
    assert key == "x"
    unparsed = value.unparse()
    assert "data" in unparsed
    assert "fallback" in unparsed
    assert "debug" in unparsed
    comptest.roundtrip(struct)


def test_pipeline_with_regular_and_failure():
    """Test regular pipeline with failure fallback."""
    struct = comptest.parse_value("{x = data |process |? fallback}", comp.Structure)
    key, value = comptest.structure_field(struct, 0, comp.Pipeline)
    assert key == "x"
    unparsed = value.unparse()
    assert "data" in unparsed
    assert "process" in unparsed
    assert "|?" in unparsed
    assert "fallback" in unparsed
    comptest.roundtrip(struct)


def test_pipeline_with_struct_literal():
    """Test pipeline with struct literal."""
    struct = comptest.parse_value("{x = data |{field = value}}", comp.Structure)
    key, value = comptest.structure_field(struct, 0, comp.Pipeline)
    assert key == "x"
    unparsed = value.unparse()
    assert "data" in unparsed
    assert "field" in unparsed
    comptest.roundtrip(struct)


def test_pipeline_with_block_literal():
    """Test pipeline with block literal :{...}"""
    struct = comptest.parse_value("{x = :{expression}}", comp.Structure)
    key, value = comptest.structure_field(struct, 0)
    assert key == "x"
    unparsed = value.unparse()
    assert ":{" in unparsed or ": {" in unparsed
    assert "expression" in unparsed
    comptest.roundtrip(struct)


@pytest.mark.skip(reason="Comma-separated assignments not yet supported")
def test_multiple_assignments_with_pipelines():
    """Test multiple assignments in same structure."""
    struct = comptest.parse_value("{x = data |process, y = $in |validate}", comp.Structure)
    assert len(struct.kids) >= 2  # At least 2 assignments
    unparsed = struct.unparse()
    assert "x" in unparsed
    assert "y" in unparsed
    assert "data" in unparsed
    assert "$in" in unparsed
    comptest.roundtrip(struct)


def test_nested_structures_with_pipelines():
    """Test nested structures containing pipelines."""
    struct = comptest.parse_value("{outer = {inner = data |process}}", comp.Structure)
    unparsed = struct.unparse()
    assert "outer" in unparsed
    assert "inner" in unparsed
    assert "data" in unparsed
    comptest.roundtrip(struct)


@pytest.mark.skip(reason="FALLBACK operator ?? not yet supported in pipeline context")
def test_pipeline_precedence_with_operators():
    """Test that pipeline binds correctly with other operators."""
    # Pipeline should bind tighter than fallback (??)
    struct = comptest.parse_value("{x = data |process ?? fallback}", comp.Structure)
    key, value = comptest.structure_field(struct, 0, comp.Pipeline)
    assert key == "x"
    unparsed = value.unparse()
    # Should have both pipeline and fallback
    assert "|" in unparsed
    assert "??" in unparsed
    comptest.roundtrip(struct)


def test_long_pipeline_chain():
    """Test a long chain of pipeline operations."""
    struct = comptest.parse_value("{x = data |func1 |func2 |func3 |func4 |func5}", comp.Structure)
    key, value = comptest.structure_field(struct, 0, comp.Pipeline)
    assert key == "x"
    unparsed = value.unparse()
    assert "data" in unparsed
    assert "func1" in unparsed
    assert "func5" in unparsed
    comptest.roundtrip(struct)


def test_pipeline_roundtrip():
    """Test that pipelines can be unparsed and reparsed."""
    original = "{x = data |process |validate}"
    struct1 = comptest.parse_value(original, comp.Structure)
    unparsed = struct1.unparse()
    struct2 = comptest.parse_value(unparsed, comp.Structure)

    # Both should have pipelines as values
    key1, value1 = comptest.structure_field(struct1, 0, comp.Pipeline)
    key2, value2 = comptest.structure_field(struct2, 0, comp.Pipeline)
    comptest.roundtrip(struct1)


def test_empty_pipeline():
    """Test assignment without pipeline (just a value)."""
    struct = comptest.parse_value("{x = 42}", comp.Structure)
    key, value = comptest.structure_field(struct, 0, comp.Number)
    assert key == "x"
    comptest.roundtrip(struct)


def test_pipeline_with_tag():
    """Test pipeline with tag reference."""
    struct = comptest.parse_value("{x = #mytag |process}", comp.Structure)
    key, value = comptest.structure_field(struct, 0, comp.Pipeline)
    assert key == "x"
    unparsed = value.unparse()
    assert "#mytag" in unparsed or "#my" in unparsed
    assert "process" in unparsed
    comptest.roundtrip(struct)


def test_pipeline_with_parenthesized_expression():
    """Test pipeline starting with parenthesized expression."""
    struct = comptest.parse_value("{x = (a + b) |double}", comp.Structure)
    key, value = comptest.structure_field(struct, 0, comp.Pipeline)
    assert key == "x"
    unparsed = value.unparse()
    # Note: parentheses are not preserved in unparse (they're structural, not textual)
    assert "+" in unparsed
    assert "double" in unparsed
    comptest.roundtrip(struct)


@pytest.mark.skip(reason="Wrench not ready for parsing")
def test_complex_pipeline_expression():
    """Test complex pipeline with multiple operator types."""
    struct = comptest.parse_value("{result = $in |filter |? backup |<< progressbar}", comp.Structure)
    key, value = comptest.structure_field(struct, 0, comp.Pipeline)
    assert key == "result"
    unparsed = value.unparse()
    assert "$in" in unparsed
    assert "filter" in unparsed
    assert "backup" in unparsed
    assert "progressbar" in unparsed
    comptest.roundtrip(struct)


# Error cases - these should raise ParseError
def test_assignment_without_struct_fails():
    """Assignments outside of structures should fail."""
    comptest.invalid_parse("x = data")


def test_assignment_with_pipeline_without_struct_fails():
    """Pipeline assignments outside of structures should fail."""
    comptest.invalid_parse("x = data |process")


if __name__ == "__main__":
    # Run a few smoke tests
    print("Testing basic pipeline parsing...")
    test_pipeline_in_struct()
    test_pipeline_with_seed()
    test_multi_stage_pipeline()
    test_pipeline_failure_operator()
    print("All smoke tests passed!")



