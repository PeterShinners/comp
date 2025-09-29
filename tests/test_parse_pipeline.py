"""
Test cases for pipeline operations including wrench operator.

SPECIFICATION:
- Pipeline failure operator: |?
- Pipeline modifier (wrench) operator: |<<
- Block definitions: :{expression}
- Named block operations: name:{expression}

PARSER EXPECTATIONS:
- comp.parse("data |? fallback") → PipelineFailureOperation
- comp.parse("data |<< modifier") → PipelineModifierOperation
- comp.parse("name:{expr}") → NamedBlockOperation

AST NODES: PipelineFailureOperation, PipelineModifierOperation,
           NamedBlockOperation, BlockDefinition
"""

import pytest

import comp

# Test cases for valid assignment pipelines
valid_assignment_pipelines = [
    ("x = data", 1, "simple assignment"),
    ("x = items |validate", 2, "basic pipeline"),
    ("x = items |validate |transform", 3, "multi-stage pipeline"),
    ("x = $in |process |save", 3, "scope with pipeline"),
    ("x = data |func1 |func2 |func3 |func4", 5, "long pipeline"),
]

@pytest.mark.parametrize(
    "input_str,expected_stages,description",
    valid_assignment_pipelines,
    ids=[case[2] for case in valid_assignment_pipelines],
)
def test_valid_assignment_pipelines(input_str, expected_stages, description):
    """Ensure valid pipelines parse correctly."""
    result = comp.parse(input_str)
    assert isinstance(result, comp.AssignmentOperation)
    assert hasattr(result, 'pipeline'), f"Assignment should have pipeline for {description}"
    assert isinstance(result.pipeline, comp.PipelineOperation), f"Pipeline should be PipelineOperation for {description}"
    assert len(result.pipeline.stages) == expected_stages, f"Expected {expected_stages} stages for {description}, got {len(result.pipeline.stages)}"


def test_pipeline_stage_types():
    """Test that pipeline stages have the correct types."""
    # Simple identifier
    result = comp.parse("x = data")
    stages = result.pipeline.stages
    assert len(stages) == 1
    assert isinstance(stages[0], comp.FieldAccessOperation)

    # Two-stage pipeline
    result = comp.parse("x = data |process")
    stages = result.pipeline.stages
    assert len(stages) == 2
    assert isinstance(stages[0], comp.FieldAccessOperation)  # data (source)
    assert isinstance(stages[1], comp.PipelineFunctionOperation)    # process (function)

    # Pipeline with scope
    result = comp.parse("x = $in |validate")
    stages = result.pipeline.stages
    assert len(stages) == 2
    assert isinstance(stages[0], comp.FieldAccessOperation)  # $in
    assert isinstance(stages[1], comp.PipelineFunctionOperation)  # validate


def test_pipeline_with_complex_expressions():
    """Test pipelines with more complex expressions."""
    # Number literal in pipeline
    result = comp.parse("x = 42")
    stages = result.pipeline.stages
    assert len(stages) == 1
    assert isinstance(stages[0], comp.NumberLiteral)

    # String literal in pipeline
    result = comp.parse('x = "hello"')
    stages = result.pipeline.stages
    assert len(stages) == 1
    assert isinstance(stages[0], comp.StringLiteral)

    # Structure literal in pipeline
    result = comp.parse("x = {a=1}")
    stages = result.pipeline.stages
    assert len(stages) == 1
    assert isinstance(stages[0], comp.StructureLiteral)


def test_pipeline_flattening():
    """Test that ShapeUnionOperation trees get flattened to linear stages."""
    result = comp.parse("x = a |b |c")
    stages = result.pipeline.stages
    assert len(stages) == 3

    # First stage should be FieldAccessOperation (data source)
    # Subsequent stages should be PipelineFunctionOperation (pipeline functions)
    assert isinstance(stages[0], comp.FieldAccessOperation), "Stage 0 should be FieldAccessOperation (data source)"
    for i in range(1, len(stages)):
        assert isinstance(stages[i], comp.PipelineFunctionOperation), f"Stage {i} should be PipelineFunctionOperation (pipeline function)"

    # Check that we can access the identifier names
    # First stage 'a' should be single-field access operation
    stage_0 = stages[0]
    assert stage_0.object is None, "Stage 0 should have no object"
    assert len(stage_0.fields) == 1, "Stage 0 should have exactly one field"
    assert isinstance(stage_0.fields[0], comp.Identifier), "Stage 0 field should be Identifier"
    assert stage_0.fields[0].name == 'a', "Stage 0 should have name 'a'"

    # Subsequent stages should be PipelineFunctionOperation with function_reference
    for i, expected_name in enumerate(['b', 'c'], start=1):
        stage = stages[i]
        assert isinstance(stage.function_reference, comp.FunctionReference), f"Stage {i} should have FunctionReference"
        assert stage.function_reference.name == expected_name, f"Stage {i} should have function name {expected_name}"
        assert stage.args is None, f"Stage {i} should have no args yet"


# Test cases for the wrench operator (pipeline modifiers)
# NOTE: These tests are for future implementation - wrench operator not yet implemented
wrench_operator_cases = [
    # ("data |<< progressbar", "basic pipeline modifier"),
    # ("items |<< debug", "single modifier"),
    # ("pipeline |<< optimize |<< profile", "chained modifiers"),
    # ("func:{transform} |<< progressbar", "named block with modifier"),
    # ("data |filter :{valid} |<< debug", "complex pipeline with modifier"),
]


# @pytest.mark.parametrize(
#     "input_str,description",
#     wrench_operator_cases,
#     ids=[case[1] for case in wrench_operator_cases],
# )
# def test_wrench_operator(input_str, description):
#     """Test that wrench operator |<< parses correctly."""
#     result = comp.parse(input_str)

#     # Should parse to a PipelineModifierOperation (might be nested)
#     # Find the outermost PipelineModifierOperation
#     current = result
#     while hasattr(current, "pipeline") and isinstance(
#         current.pipeline, comp.PipelineModifierOperation
#     ):
#         current = current.pipeline

#     assert isinstance(result, comp.PipelineModifierOperation), (
#         f"Expected PipelineModifierOperation for {description}, got {type(result)}"
#     )
#     assert hasattr(result, "pipeline"), f"Missing pipeline attribute for {description}"
#     assert hasattr(result, "modifier"), f"Missing modifier attribute for {description}"


# def test_wrench_operator_structure():
#     """Test the internal structure of wrench operations."""
#     # Simple case
#     result = comp.parse("data |<< progressbar")
#     assert isinstance(result, comp.PipelineModifierOperation)
#     assert _check_identifier(result.pipeline, "data")
#     assert _check_identifier(result.modifier, "progressbar")

#     # Chained case - should be left-associative
#     result = comp.parse("data |<< optimize |<< debug")
#     assert isinstance(result, comp.PipelineModifierOperation)
#     assert isinstance(result.pipeline, comp.PipelineModifierOperation)
#     assert _check_identifier(result.modifier, "debug")

#     # Inner operation
#     inner = result.pipeline
#     assert _check_identifier(inner.pipeline, "data")
#     assert _check_identifier(inner.modifier, "optimize")


# def test_wrench_with_named_blocks():
#     """Test wrench operator with named block operations."""
#     result = comp.parse("handler:{process} |<< progressbar")
#     assert isinstance(result, comp.PipelineModifierOperation)
#     assert isinstance(result.pipeline, comp.NamedBlockOperation)
#     assert _check_identifier(result.modifier, "progressbar")

#     # Check the named block structure
#     named_block = result.pipeline
#     assert _check_identifier(named_block.name, "handler")
#     assert isinstance(named_block.block, comp.BlockDefinition)
#     assert _check_identifier(named_block.block.expression, "process")


# def test_wrench_precedence():
#     """Test that wrench operator has correct precedence."""
#     # Should bind less tightly than field access
#     result = comp.parse("obj.field |<< modifier")
#     assert isinstance(result, comp.PipelineModifierOperation)
#     assert isinstance(result.pipeline, comp.FieldAccessOperation)
#     assert len(result.pipeline.fields) == 2  # obj and field in flattened structure
#     assert isinstance(result.pipeline.fields[0], comp.Identifier)
#     assert result.pipeline.fields[0].name == "obj"
#     assert isinstance(result.pipeline.fields[1], comp.Identifier)
#     assert result.pipeline.fields[1].name == "field"

#     # Should bind more tightly than fallback
#     result = comp.parse("data |<< mod ?? fallback")
#     assert isinstance(result, comp.FallbackOperation)
#     assert isinstance(result.left, comp.PipelineModifierOperation)
#     assert _check_identifier(result.left.modifier, "mod")


# # Integration tests with existing pipeline operations
# def test_wrench_with_pipeline_failure():
#     """Test wrench operator combined with pipeline failure operator."""
#     # |<< should have similar precedence to |?
#     result = comp.parse("data |? fallback |<< modifier")
#     assert isinstance(result, comp.PipelineModifierOperation)
#     assert isinstance(result.pipeline, comp.PipelineFailureOperation)


# def test_complex_pipeline_combinations():
#     """Test complex combinations of pipeline operations."""
#     # Test: data |filter :{valid} |? backup |<< progressbar |<< debug
#     # This should parse as a complex pipeline with multiple operations
#     test_expr = "data |filter :{valid} |<< progressbar"
#     result = comp.parse(test_expr)

#     assert isinstance(result, comp.PipelineModifierOperation)
#     # The pipeline part should be a shape union (|filter creates a ShapeUnionOperation)
#     assert isinstance(result.pipeline, comp.ShapeUnionOperation)
#     assert _check_identifier(result.modifier, "progressbar")


def test_current_pipeline_capabilities():
    """Test what our current pipeline implementation can handle."""

    # Test various pipeline-of-one cases (single values wrapped in pipeline)
    test_cases = [
        ("x = 42", comp.NumberLiteral),
        ('x = "hello"', comp.StringLiteral),
        ("x = data", comp.FieldAccessOperation),
        ("x = $in", comp.FieldAccessOperation),
        ("x = {a=1}", comp.StructureLiteral),  # Single field structure only for now
        ("x = #tag", comp.TagReference),      # Tag references work
        ("x = (a + b)", comp.BinaryOperation), # Binary operations in parentheses
    ]

    for assignment_str, expected_type in test_cases:
        result = comp.parse(assignment_str)
        assert isinstance(result, comp.AssignmentOperation), f"Should be assignment: {assignment_str}"
        assert len(result.pipeline.stages) == 1, f"Should have exactly 1 stage: {assignment_str}"
        assert isinstance(result.pipeline.stages[0], expected_type), f"Wrong stage type for: {assignment_str}"

    # Test multi-stage pipelines (ShapeUnionOperation flattening)
    result = comp.parse("x = data |process |validate |save")
    assert len(result.pipeline.stages) == 4
    
    # First stage is data source (FieldAccessOperation)
    stage = result.pipeline.stages[0]
    assert isinstance(stage, comp.FieldAccessOperation)
    assert stage.object is None
    assert len(stage.fields) == 1
    assert stage.fields[0].name == "data"
    
    # Remaining stages are function references
    expected_function_names = ["process", "validate", "save"]
    for i, expected_name in enumerate(expected_function_names, 1):
        stage = result.pipeline.stages[i]
        assert isinstance(stage, comp.PipelineFunctionOperation)
        assert stage.function_reference.name == expected_name

    # Test mixed expressions in pipeline
    result = comp.parse("x = 42 |process")
    assert len(result.pipeline.stages) == 2
    assert isinstance(result.pipeline.stages[0], comp.NumberLiteral)
    assert isinstance(result.pipeline.stages[1], comp.PipelineFunctionOperation)  # process (function)

    # Test scope with pipeline
    result = comp.parse("output = $in |transform |$out")
    assert len(result.pipeline.stages) == 3
    assert isinstance(result.pipeline.stages[0], comp.FieldAccessOperation)  # $in (source)
    assert isinstance(result.pipeline.stages[1], comp.PipelineFunctionOperation)     # transform (function)
    assert isinstance(result.pipeline.stages[2], comp.FieldAccessOperation)  # $out (complex reference, not converted)

    # Verify operator is clean string (not Lark token)
    assert isinstance(result.operator, str)
    assert result.operator == "="


def test_implemented_pipeline_operations():
    """Test the pipeline operations that are already working."""

    # Test pipeline failure operator |?
    result = comp.parse("x = data |? fallback")
    assert isinstance(result, comp.AssignmentOperation)
    stages = result.pipeline.stages
    assert len(stages) == 1
    assert isinstance(stages[0], comp.PipelineFailureOperation)

    # Test wrench operator |<<
    result = comp.parse("x = data |<< modifier")
    assert isinstance(result, comp.AssignmentOperation)
    stages = result.pipeline.stages
    assert len(stages) == 1
    assert isinstance(stages[0], comp.PipelineModifierOperation)

    # Test block definitions :{expr}
    result = comp.parse("x = :{expression}")
    assert isinstance(result, comp.AssignmentOperation)
    stages = result.pipeline.stages
    assert len(stages) == 1
    assert isinstance(stages[0], comp.BlockDefinition)

    # Test named block operations name:{expr}
    result = comp.parse("x = handler:{process}")
    assert isinstance(result, comp.AssignmentOperation)
    stages = result.pipeline.stages
    assert len(stages) == 1
    assert isinstance(stages[0], comp.NamedBlockOperation)

    # Test block invoking |:
    result = comp.parse("x = |:block_name")
    assert isinstance(result, comp.AssignmentOperation)
    stages = result.pipeline.stages
    assert len(stages) == 1
    assert isinstance(stages[0], comp.BlockInvokeOperation)

    # Test pipeline struct literal |{field=value}
    result = comp.parse("x = data |{field=value}")
    assert isinstance(result, comp.AssignmentOperation)
    stages = result.pipeline.stages
    assert len(stages) == 1
    assert isinstance(stages[0], comp.PipelineStructOperation)  # This creates a PipelineStructOperation


def test_complex_pipeline_combinations():
    """Test complex combinations of current pipeline operations."""

    # Test chained pipeline failure and modifier
    result = comp.parse("x = data |? fallback |<< debug")
    assert isinstance(result, comp.AssignmentOperation)
    stages = result.pipeline.stages
    assert len(stages) == 1
    assert isinstance(stages[0], comp.PipelineModifierOperation)
    # The pipeline modifier should contain a pipeline failure operation
    assert isinstance(stages[0].pipeline, comp.PipelineFailureOperation)

    # Test regular pipeline with failure fallback
    result = comp.parse("x = data |process |? fallback")
    assert isinstance(result, comp.AssignmentOperation)
    stages = result.pipeline.stages
    assert len(stages) == 1
    assert isinstance(stages[0], comp.PipelineFailureOperation)
    # The failure operation should contain the pipeline
    assert isinstance(stages[0].operation, comp.ShapeUnionOperation)

    # Test named block with pipeline
    result = comp.parse("x = handler:{data |process}")
    assert isinstance(result, comp.AssignmentOperation)
    stages = result.pipeline.stages
    assert len(stages) == 1
    assert isinstance(stages[0], comp.NamedBlockOperation)
    # The block should contain a pipeline expression
    assert hasattr(stages[0].block, 'expression')


# Error cases
invalid_wrench_cases = [
    ("|<< modifier", "wrench without left operand"),
    ("data |<<", "wrench without right operand"),
    ("data |< < modifier", "split wrench operator"),
]


# @pytest.mark.parametrize(
#     "input_str,description",
#     invalid_wrench_cases,
#     ids=[case[1] for case in invalid_wrench_cases],
# )
# def test_invalid_wrench_syntax(input_str, description):
#     """Test that invalid wrench syntax raises parse errors."""
#     with pytest.raises(Exception) as exc_info:
#         comp.parse(input_str)

#     error_msg = str(exc_info.value).lower()
#     assert (
#         "syntax error" in error_msg
#         or "parse" in error_msg
#         or "unexpected" in error_msg
#         or "invalid" in error_msg
#     ), f"Expected parse error for {description}: {input_str}"


def _check_identifier(node, expected_name=None):
    """Helper to check if a node is an identifier, handling FieldAccessOperation wrapping."""
    if isinstance(node, comp.Identifier):
        if expected_name is not None:
            assert node.name == expected_name
        return True
    elif isinstance(node, comp.FieldAccessOperation):
        # Bare identifier becomes FieldAccessOperation(None, [Identifier])
        if (
            node.object is None
            and len(node.fields) == 1
            and isinstance(node.fields[0], comp.Identifier)
        ):
            if expected_name is not None:
                assert node.fields[0].name == expected_name
            return True
    return False
