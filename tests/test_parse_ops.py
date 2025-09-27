"""Tests for Operators

Tests language-specific operators including assignment, structure manipulation,
pipeline operations, block syntax, and special operators. def test_complex_advanced_expressions():
"""

import pytest

import comp


def test_assignment_expressions_direct():
    """Test that assignment expressions work directly (not in structures)"""
    # Test direct weak assignment
    result = comp.parse("config =? default-value")
    assert isinstance(result, comp._ast.AssignmentOperation)
    assert result.operator.value == "=?"
    assert result.target.name == "config"  # target is an Identifier object


def test_basic_assignment_operators_parse():
    """Test that basic assignment operators parse correctly"""
    # Basic assignment in structure context
    result = comp.parse("{x=42}")
    _assert_structure_with_named_field(result, "x", 42)

    # Weak assignment - only assigns if not defined
    result = comp.parse("{config =? default-value}")
    _assert_structure_with_named_field(result, "config", "ident=default-value", "=?")

    # Strong assignment - force assignment, persists beyond scope
    result = comp.parse("{data =* validated-value}")
    _assert_structure_with_named_field(result, "data", "ident=validated-value", "=*")


def test_spread_assignment_operators_parse():
    """Test spread assignment operators"""
    # Basic spread assignment
    result = comp.parse("{user ..= {verified=#true}}")
    _assert_structure_with_named_field(result, "user", None, "..=")

    # Weak spread assignment - only adds new fields
    result = comp.parse('{prefs ..=? {theme="dark"}}')
    _assert_structure_with_named_field(result, "prefs", None, "..=?")

    # Strong spread assignment - replaces entirely
    result = comp.parse("{state ..=* new-state}")
    _assert_structure_with_named_field(result, "state", "ident=new-state", "..=*")


def test_structure_operators_parse():
    """Test structure manipulation operators"""
    # Spread operator in structure literal
    result = comp.parse('{..defaults name="Alice"}')
    assert isinstance(result, comp.StructureLiteral)
    assert len(result.operations) == 2
    # First operation should be spread operator
    assert hasattr(result.operations[0], "expression")  # SpreadTarget
    # Second operation should be named field
    _assert_structure_with_named_field(result, "name", "Alice")

    # Field access operator
    result = comp.parse("user.name")
    _assert_field_access(result, "ident=user", "name")

    # Index access operator on object
    result = comp.parse("items.#0")
    _assert_index_access(result, "ident=items", 0)

    # Standalone index reference (like tag atoms but all digits)
    result = comp.parse("#1")
    _assert_index_reference(result, 1)

    # Private data attachment
    result = comp.parse('data&{session="abc"}')
    _assert_private_attach(result, "ident=data", None)

    # Private data access
    result = comp.parse("user&.session")
    _assert_private_access(result, "ident=user", "session")


def test_shape_union_operators_parse():
    """Test shape union operators"""
    # Shape union with pipe operator
    result = comp.parse("~string|~number")
    _assert_shape_union(result, "string", "number")

    # Multi-way union
    result = comp.parse("~int|~float|~string")
    _assert_shape_union(result, None, None)  # Complex union, just check structure


def test_pipeline_operators_parse():
    """Test pipeline operators"""
    # Pipeline failure handling
    result = comp.parse("risky-operation |? default-value")
    _assert_pipeline_failure(result, "ident=risky-operation", "ident=default-value")

    # Pipeline with block (TODO: implement pipeline block syntax)
    # result = comp.parse("process |{} transform")
    # _assert_pipeline_block(result, "ident=process", "ident=transform")


def test_block_operators_parse():
    """Test block definition and invocation operators"""
    # Block definition
    result = comp.parse(".{x + y}")
    _assert_block_definition(result, None)  # Contains expression inside

    # Block invocation - matches function invoke pattern |func
    result = comp.parse("|.block")
    _assert_block_invoke(result, "ident=block")


def test_fallback_operators_parse():
    """Test fallback operators ?? and |?"""
    # Basic fallback operator
    result = comp.parse("config.port ?? 8080")
    _assert_fallback(result, "??", None, 8080)

    # Alternative fallback operator
    result = comp.parse("primary |? secondary")
    _assert_failure(result, "|?", "ident=secondary")

    # Chained fallbacks
    result = comp.parse("config.port ?? env.PORT ?? 8080")
    _assert_fallback(result, "??", None, 8080)
    _assert_fallback(result.left, "??", None, None)


def test_special_operators_parse():
    """Test special operators"""
    # Placeholder operator
    result = comp.parse("???")
    _assert_placeholder(result)

    # Array type brackets
    result = comp.parse("tags[]")
    _assert_array_type(result, "ident=tags")

    # Single quote field naming
    result = comp.parse("'computed-key'")
    _assert_field_name(result, "computed-key")

    # Index operators - both forms
    result = comp.parse("list.#0")  # Object index access
    _assert_index_access(result, "ident=list", 0)

    result = comp.parse("#1")  # Standalone index reference
    _assert_index_reference(result, 1)

    # Using both in expression (object access + standalone reference)
    result = comp.parse("items.#0 + #1")
    _assert_binary(result, "+", None, None)  # Complex - just check structure


def test_comments_parse():
    """Test comment parsing"""
    # Single line comments should be stripped/ignored
    result = comp.parse("42 ; This is a comment")
    _assert_number(result, 42)

    # Comments at end of expressions
    result = comp.parse("x + y ; Calculate sum")
    _assert_binary(result, "+", "ident=x", "ident=y")


def test_advanced_operator_precedence():
    """Test operator precedence integration"""
    # Assignment has lower precedence than mathematical operators
    result = comp.parse("{result = x + y * z}")
    _assert_structure_with_named_field(result, "result", None)

    # Fallback has specific precedence
    result = comp.parse("x + y ?? z * w")
    _assert_fallback(result, "??", None, None)

    # Field access has high precedence
    result = comp.parse("user.age + 5")
    _assert_binary(result, "+", None, 5)


def test_complex_advanced_expressions():
    """Test complex expressions combining operators"""
    # Structure with individual operations (multi-op structures need more work)
    result = comp.parse("{..base}")
    assert isinstance(result, comp.StructureLiteral)
    assert len(result.operations) == 1

    result = comp.parse("{config =? defaults}")
    assert isinstance(result, comp.StructureLiteral)
    assert len(result.operations) == 1

    # Pipeline with fallback
    result = comp.parse("risky-op |? fallback ?? final-default")
    _assert_fallback(result, "??", None, "ident=final-default")

    # Block with field access
    result = comp.parse('.{user.name + " " + user.surname}')
    _assert_block_definition(result, None)


# Helper assertion functions


def _assert_structure_with_named_field(node, field_name, field_value, operator="="):
    """Helper to assert structure contains named field with specific assignment"""
    assert isinstance(node, comp.StructureLiteral)
    assert len(node.operations) >= 1

    # Find the operation with matching field name
    matching_op = None
    for op in node.operations:
        if (
            isinstance(op.target, comp.FieldTarget)
            and op.target.name == field_name
            and op.operator == operator
        ):
            matching_op = op
            break

    assert matching_op is not None, (
        f"No operation found with field '{field_name}' and operator '{operator}'"
    )

    # Check the value if specified
    if field_value is not None:
        _check_value(matching_op.expression, field_value)


def _assert_named_field(field, name, value, operator="="):
    """Helper to assert a StructureOperation with FieldTarget (legacy compatibility)"""
    assert isinstance(field, comp.StructureOperation)
    assert isinstance(field.target, comp.FieldTarget)
    assert field.target.name == name
    assert field.operator == operator
    if value is not None:
        _check_value(field.expression, value)


def _assert_field_access(node, object_ref, field_name):
    """Helper to assert field access operation"""
    assert isinstance(node, comp.FieldAccessOperation)
    _check_value(node.object, object_ref)
    assert node.field == field_name


def _assert_index_access(node, object_ref, index):
    """Helper to assert index access operation"""
    assert isinstance(node, comp.IndexAccessOperation)
    _check_value(node.object, object_ref)
    _check_value(node.index, index)


def _assert_index_reference(node, index):
    """Helper to assert standalone index reference (like #1)"""
    assert isinstance(node, comp.IndexReference)
    # node.index is a Token('INDEX_NUMBER', '1'), extract the value
    assert node.index.value == str(index)


def _assert_private_attach(node, object_ref, private_data):
    """Helper to assert private data attachment"""
    assert isinstance(node, comp.PrivateAttachOperation)
    _check_value(node.object, object_ref)
    if private_data is not None:
        _check_value(node.private_data, private_data)


def _assert_private_access(node, object_ref, field_name):
    """Helper to assert private field access"""
    assert isinstance(node, comp.PrivateAccessOperation)
    _check_value(node.object, object_ref)
    assert node.field == field_name


def _assert_shape_union(node, left_shape, right_shape):
    """Helper to assert shape union operation"""
    assert isinstance(node, comp.ShapeUnionOperation)
    if left_shape is not None:
        _check_shape_ref(node.left, left_shape)
    if right_shape is not None:
        _check_shape_ref(node.right, right_shape)


def _assert_pipeline_failure(node, operation, fallback):
    """Helper to assert pipeline failure handling"""
    assert isinstance(node, comp.PipelineFailureOperation)
    _check_value(node.operation, operation)
    _check_value(node.fallback, fallback)


def _assert_pipeline_block(node, process, transform):
    """Helper to assert pipeline with block"""
    assert isinstance(node, comp.PipelineBlock)
    _check_value(node.process, process)
    _check_value(node.transform, transform)


def _assert_block_definition(node, expression):
    """Helper to assert block definition"""
    assert isinstance(node, comp.BlockDefinition)
    if expression is not None:
        _check_value(node.expression, expression)


def _assert_block_invoke(node, block_ref):
    """Helper to assert block invocation"""
    assert isinstance(node, comp.BlockInvokeOperation)
    _check_value(node.block, block_ref)


def _assert_fallback(node, operator, left, right):
    """Helper to assert fallback operation"""
    assert isinstance(node, comp.FallbackOperation)
    assert node.operator == operator
    _check_value(node.left, left)
    _check_value(node.right, right)


def _assert_failure(node, operator, operand):
    """Helper to assert pipeline failure operation"""
    assert isinstance(node, comp.PipelineFailureOperation)
    # |? takes the fallback expression as its single value
    _check_value(node.fallback, operand)


def _assert_placeholder(node):
    """Helper to assert placeholder operator"""
    assert isinstance(node, comp.Placeholder)


def _assert_array_type(node, base_type):
    """Helper to assert array type operation"""
    assert isinstance(node, comp.ArrayType)
    _check_value(node.base_type, base_type)


def _assert_field_name(node, name):
    """Helper to assert field name expression"""
    assert isinstance(node, comp.FieldName)
    assert node.name == name


def _assert_binary(node, operator, left, right):
    """Helper to assert a BinaryOperation node structure"""
    assert isinstance(node, comp.BinaryOperation)
    assert node.operator == operator
    _check_value(node.left, left)
    _check_value(node.right, right)


def _assert_number(node, value):
    """Helper to assert a NumberLiteral"""
    assert isinstance(node, comp.NumberLiteral)
    assert node.value == value


def _check_value(operand, expected):
    """Check for literal or identifier value, or None to ignore"""
    if expected is None:
        return
    if isinstance(expected, str) and expected.startswith("ident="):
        expected_name = expected[6:]  # Remove "ident=" prefix
        assert isinstance(operand, comp.Identifier)
        assert operand.name == expected_name
    else:
        operand_value = operand.value  # type: ignore
        assert operand_value == expected


def _check_shape_ref(operand, shape_name):
    """Check for shape reference"""
    assert isinstance(operand, comp.ShapeReference)
    assert operand.name == shape_name
