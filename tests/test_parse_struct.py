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
- comp.parse("{}") → StructureLiteral([])
- comp.parse("{42}") → StructureLiteral([PositionalField(NumberLiteral(42))])
- comp.parse("{x=1}") → StructureLiteral([NamedField("x", NumberLiteral(1))])
- comp.parse("name:{5}") → NamedBlockOperation(name, BlockDefinition(5))

AST NODES: StructureLiteral(fields), NamedField(name, value), PositionalField(value),
           NamedBlockOperation(name, block), BlockDefinition(expression)

NOTE: This phase requires implementing StructureLiteral, NamedField, PositionalField,
NamedBlockOperation, and BlockDefinition AST nodes, plus extending the grammar to handle
structure syntax and named block operations.
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
    assert len(result.operations) == length


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
    """Test results for individual operations"""
    result = comp.parse('{max=3 "car" #true max={"cat"}}')
    assert isinstance(result, comp.StructureLiteral)
    assert len(result.operations) == 4

    # First operation: max=3 (FieldTarget)
    op0 = result.operations[0]
    assert isinstance(op0, comp.StructureOperation)
    assert isinstance(op0.target, comp.FieldTarget)
    assert op0.target.name == "max"
    assert op0.operator == "="
    assert isinstance(op0.expression, comp.NumberLiteral)
    assert op0.expression.value == 3

    # Second operation: "car" (positional - no specific target in our current unified model)
    op1 = result.operations[1]
    assert isinstance(op1, comp.StructureOperation)
    # This should be a positional expression - for now it's parsed as a regular expression
    assert isinstance(op1.expression, comp.StringLiteral)
    assert op1.expression.value == "car"

    # Third operation: #true (positional TagReference)
    op2 = result.operations[2]
    assert isinstance(op2, comp.StructureOperation)
    assert isinstance(op2.expression, comp.TagReference)
    assert op2.expression.name == "true"

    # Fourth operation: max={"cat"} (FieldTarget with nested structure)
    op3 = result.operations[3]
    assert isinstance(op3, comp.StructureOperation)
    assert isinstance(op3.target, comp.FieldTarget)
    assert op3.target.name == "max"
    assert op3.operator == "="
    assert isinstance(op3.expression, comp.StructureLiteral)


# Named Block Operation tests - now use assignment syntax
named_block_cases = [
    ("name=:{5}", "simple named block assignment with number"),
    ("handler=:{42 + 10}", "named block assignment with expression"),
    ("processor=:{user}", "named block assignment with identifier"),
    ('formatter=:{"hello"}', "named block assignment with string"),
    ("func=:{#true}", "named block assignment with tag reference"),
    ("transform=:{~str}", "named block assignment with shape reference"),
    ("pipeline=:{|process}", "named block assignment with function reference"),
]


@pytest.mark.parametrize(
    "input_str,description",
    named_block_cases,
    ids=[case[1] for case in named_block_cases],
)
def test_named_block_operations(input_str, description):
    """Test that named block assignments parse correctly."""
    result = comp.parse(input_str)
    assert isinstance(result, comp.AssignmentOperation), (
        f"Expected AssignmentOperation for {description}"
    )
    assert hasattr(result, "target"), (
        f"AssignmentOperation missing 'target' attribute for {description}"
    )
    assert hasattr(result, "pipeline"), (
        f"AssignmentOperation missing 'pipeline' attribute for {description}"
    )
    # Target should be a FieldAccessOperation
    assert isinstance(result.target, comp.FieldAccessOperation), (
        f"Expected target to be FieldAccessOperation for {description}"
    )
    # Pipeline should contain a BlockLiteral
    assert isinstance(result.pipeline, comp.PipelineOperation), (
        f"Expected pipeline to be PipelineOperation for {description}"
    )
    assert len(result.pipeline.stages) >= 1, (
        f"Expected pipeline to have stages for {description}"
    )
    assert isinstance(result.pipeline.stages[0], comp.BlockLiteral), (
        f"Expected first stage to be BlockLiteral for {description}"
    )


def test_named_block_structure():
    """Test the internal structure of named block assignments."""
    # Test simple case
    result = comp.parse("handler=:{42}")
    assert isinstance(result, comp.AssignmentOperation)
    assert isinstance(result.target, comp.FieldAccessOperation)
    assert result.target.object is None
    assert len(result.target.fields) == 1
    assert isinstance(result.target.fields[0], comp.Identifier)
    assert result.target.fields[0].name == "handler"
    assert isinstance(result.pipeline, comp.PipelineOperation)
    assert len(result.pipeline.stages) >= 1
    assert isinstance(result.pipeline.stages[0], comp.BlockLiteral)
    # Check the block content
    block = result.pipeline.stages[0]
    assert len(block.operations) == 1
    assert isinstance(block.operations[0], comp.StructureOperation)
    assert isinstance(block.operations[0].expression, comp.NumberLiteral)
    assert block.operations[0].expression.value == 42

    # Test with complex expression
    result = comp.parse("processor=:{10 + 5}")
    assert isinstance(result, comp.AssignmentOperation)
    assert isinstance(result.target, comp.FieldAccessOperation)
    assert result.target.object is None
    assert len(result.target.fields) == 1
    assert isinstance(result.target.fields[0], comp.Identifier)
    assert result.target.fields[0].name == "processor"
    assert isinstance(result.pipeline, comp.PipelineOperation)
    assert len(result.pipeline.stages) >= 1
    assert isinstance(result.pipeline.stages[0], comp.BlockLiteral)
    # Check the block content
    block = result.pipeline.stages[0]
    assert len(block.operations) == 1
    assert isinstance(block.operations[0], comp.StructureOperation)
    assert isinstance(block.operations[0].expression, comp.BinaryOperation)
    assert block.operations[0].expression.operator == "+"


# Test that named blocks are different from regular field access
def test_named_block_vs_field_access():
    """Test that named block assignments are distinguished from regular field access."""
    # Regular field access
    field_result = comp.parse("name.field")
    assert isinstance(field_result, comp.FieldAccessOperation)
    assert field_result.object is None  # Flattened structure
    assert len(field_result.fields) == 2  # Both "name" and "field"
    assert isinstance(field_result.fields[0], comp.Identifier)
    assert field_result.fields[0].name == "name"
    # The second field is also an Identifier due to field access flattening
    assert isinstance(field_result.fields[1], comp.Identifier)
    assert field_result.fields[1].name == "field"

    # Block assignment using assignment syntax (named blocks no longer exist)
    block_result = comp.parse("name=:{field}")
    assert isinstance(block_result, comp.AssignmentOperation)
    assert isinstance(block_result.target, comp.FieldAccessOperation)
    assert block_result.target.object is None
    assert len(block_result.target.fields) == 1
    assert isinstance(block_result.target.fields[0], comp.Identifier)
    assert block_result.target.fields[0].name == "name"
    assert isinstance(block_result.pipeline, comp.PipelineOperation)
    assert len(block_result.pipeline.stages) >= 1
    assert isinstance(block_result.pipeline.stages[0], comp.BlockLiteral)
