"""
Test cases for pipeline operations including wrench operator.

SPECIFICATION:
- Pipeline failure operator: |?
- Pipeline modifier (wrench) operator: |<<
- Block definitions: .{expression}
- Named block operations: name.{expression}

PARSER EXPECTATIONS:
- comp.parse("data |? fallback") → PipelineFailureOperation
- comp.parse("data |<< modifier") → PipelineModifierOperation
- comp.parse("name.{expr}") → NamedBlockOperation

AST NODES: PipelineFailureOperation, PipelineModifierOperation,
           NamedBlockOperation, BlockDefinition
"""

import pytest
import comp


# Test cases for the wrench operator (pipeline modifiers)
wrench_operator_cases = [
    ("data |<< progressbar", "basic pipeline modifier"),
    ("items |<< debug", "single modifier"),
    ("pipeline |<< optimize |<< profile", "chained modifiers"),
    ("func.{transform} |<< progressbar", "named block with modifier"),
    ("data |filter .{valid} |<< debug", "complex pipeline with modifier"),
]


@pytest.mark.parametrize(
    "input_str,description",
    wrench_operator_cases,
    ids=[case[1] for case in wrench_operator_cases],
)
def test_wrench_operator(input_str, description):
    """Test that wrench operator |<< parses correctly."""
    result = comp.parse(input_str)

    # Should parse to a PipelineModifierOperation (might be nested)
    # Find the outermost PipelineModifierOperation
    current = result
    while hasattr(current, "pipeline") and isinstance(
        current.pipeline, comp.PipelineModifierOperation
    ):
        current = current.pipeline

    assert isinstance(result, comp.PipelineModifierOperation), (
        f"Expected PipelineModifierOperation for {description}, got {type(result)}"
    )
    assert hasattr(result, "pipeline"), f"Missing pipeline attribute for {description}"
    assert hasattr(result, "modifier"), f"Missing modifier attribute for {description}"


def test_wrench_operator_structure():
    """Test the internal structure of wrench operations."""
    # Simple case
    result = comp.parse("data |<< progressbar")
    assert isinstance(result, comp.PipelineModifierOperation)
    assert isinstance(result.pipeline, comp.Identifier)
    assert result.pipeline.name == "data"
    assert isinstance(result.modifier, comp.Identifier)
    assert result.modifier.name == "progressbar"

    # Chained case - should be left-associative
    result = comp.parse("data |<< optimize |<< debug")
    assert isinstance(result, comp.PipelineModifierOperation)
    assert isinstance(result.pipeline, comp.PipelineModifierOperation)
    assert isinstance(result.modifier, comp.Identifier)
    assert result.modifier.name == "debug"

    # Inner operation
    inner = result.pipeline
    assert isinstance(inner.pipeline, comp.Identifier)
    assert inner.pipeline.name == "data"
    assert isinstance(inner.modifier, comp.Identifier)
    assert inner.modifier.name == "optimize"


def test_wrench_with_named_blocks():
    """Test wrench operator with named block operations."""
    result = comp.parse("handler.{process} |<< progressbar")
    assert isinstance(result, comp.PipelineModifierOperation)
    assert isinstance(result.pipeline, comp.NamedBlockOperation)
    assert isinstance(result.modifier, comp.Identifier)

    # Check the named block structure
    named_block = result.pipeline
    assert named_block.name.name == "handler"
    assert isinstance(named_block.block.expression, comp.Identifier)
    assert named_block.block.expression.name == "process"


def test_wrench_precedence():
    """Test that wrench operator has correct precedence."""
    # Should bind less tightly than field access
    result = comp.parse("obj.field |<< modifier")
    assert isinstance(result, comp.PipelineModifierOperation)
    assert isinstance(result.pipeline, comp.FieldAccessOperation)
    assert result.pipeline.field == "field"

    # Should bind more tightly than fallback
    result = comp.parse("data |<< mod ?? fallback")
    assert isinstance(result, comp.FallbackOperation)
    assert isinstance(result.left, comp.PipelineModifierOperation)
    assert result.left.modifier.name == "mod"


# Integration tests with existing pipeline operations
def test_wrench_with_pipeline_failure():
    """Test wrench operator combined with pipeline failure operator."""
    # |<< should have similar precedence to |?
    result = comp.parse("data |? fallback |<< modifier")
    assert isinstance(result, comp.PipelineModifierOperation)
    assert isinstance(result.pipeline, comp.PipelineFailureOperation)


def test_complex_pipeline_combinations():
    """Test complex combinations of pipeline operations."""
    # Test: data |filter .{valid} |? backup |<< progressbar |<< debug
    # This should parse as a complex pipeline with multiple operations
    test_expr = "data |filter .{valid} |<< progressbar"
    result = comp.parse(test_expr)

    assert isinstance(result, comp.PipelineModifierOperation)
    # The pipeline part should be a shape union (|filter creates a ShapeUnionOperation)
    assert isinstance(result.pipeline, comp.ShapeUnionOperation)
    assert result.modifier.name == "progressbar"


# Error cases
invalid_wrench_cases = [
    ("|<< modifier", "wrench without left operand"),
    ("data |<<", "wrench without right operand"),
    ("data |< < modifier", "split wrench operator"),
]


@pytest.mark.parametrize(
    "input_str,description",
    invalid_wrench_cases,
    ids=[case[1] for case in invalid_wrench_cases],
)
def test_invalid_wrench_syntax(input_str, description):
    """Test that invalid wrench syntax raises parse errors."""
    with pytest.raises(Exception) as exc_info:
        comp.parse(input_str)

    error_msg = str(exc_info.value).lower()
    assert (
        "syntax error" in error_msg
        or "parse" in error_msg
        or "unexpected" in error_msg
        or "invalid" in error_msg
    ), f"Expected parse error for {description}: {input_str}"
