"""Unit testing quality of life and readability helpers."""

import re
import pytest
import comp

def params(names, **cases):
    """Simplified parametrize decorator for test cases.

    Args:
        names: Space or comma-separated string of parameter names
        **cases: Named test cases where key is the test ID and value is
                either a single argument or tuple of arguments

    Returns:
        pytest.mark.parametrize decorator with 'key' as first parameter

    Example:
        @params("code count", empty=("{}", 0), pos1=("{42}", 1))
        def test_structures(key, code, count):
            struct = parse_value(code, comp.ast.Structure)
            assert len(struct.kids) == count
    """
    keys = list(cases)
    params = []
    for k, v in cases.items():
        # If value is a tuple, unpack it; otherwise keep as single value
        if isinstance(v, tuple):
            params.append((k, *v))
        else:
            params.append((k, v))

    columns = names.replace(",", " ").split()
    columns.insert(0, "key")
    return pytest.mark.parametrize(columns, params, ids=keys)


def invalid_parse(expression, match=None):
    """Assert parsing generates a ParseError and return exception message.

    Args:
        expression: String expression expected to fail parsing
        match: Optional regex pattern to match against error message

    Returns:
        The exception message from the ParseError

    Raises:
        pytest.fail: If parsing succeeds or regex doesn't match

    Example:
        msg = invalid_parse("{42=}")
        assert "expected" in msg.lower()

        invalid_parse("0b789", match="invalid.*binary")
    """
    try:
        comp.parse_expr(expression)
    except comp.ParseError as err:
        msg = err.args[0]
        if match:
            if not re.search(match, msg, re.IGNORECASE):
                pytest.fail(
                    f"Error message doesn't match pattern '{match}':\n"
                    f"  Expression: {expression}\n"
                    f"  Message: {msg}",
                    pytrace=False
                )
        return msg
    pytest.fail(f"Expected ParseError for '{expression}'", pytrace=False)


def roundtrip(ast):
    """Unparse and reparse an AST, asserting structural match.

    Args:
        ast: An Node to round-trip test (Root or any other node)

    Raises:
        AssertionError: If round-trip produces different structure

    Example:
        result = comp.parse_expr("{x=1}")
        roundtrip(result)  # Asserts result.matches(reparsed)

        struct = parse_value("{x=1}", comp.ast.Structure)
        roundtrip(struct)  # Also works with non-Root nodes
    """
    unparsed = ast.unparse()
    
    # Choose parser based on AST type
    if isinstance(ast, comp.ast.Module):
        reparsed = comp.parse_module(unparsed)
    else:
        reparsed = comp.parse_expr(unparsed)
    
        # If ast is not a Root node, wrap it in Root for comparison
        if not isinstance(ast, comp.ast.Root):
            root = comp.ast.Root()
            root.kids = [ast]
            ast = root

    assert ast.matches(reparsed), (
        f"Round-trip failed:\n"
        f"  Unparsed: {unparsed}\n"
        f"  Structures don't match"
    )


def parse_value(expression, cls=comp.ast.Node, index=0):
    """Parse expression and return the specified child of Root with type check.

    Args:
        expression: Source code to parse
        cls: Expected node type (default: any Node)
        index: Which child of Root to return (default: 0)

    Returns:
        The child node at the specified index

    Raises:
        AssertionError: If node is not an instance of cls

    Example:
        struct = parse_value("{x=1}", comp.ast.Structure)
        number = parse_value("42", comp.ast.Number)
        binop = parse_value("a + b", comp.BinaryOp)
    """
    result = comp.parse_expr(expression)
    node = result.kids[index] if result.kids else result
    assert isinstance(node, cls), (
        f"Expected {cls.__name__}, got {type(node).__name__}\n"
        f"  Expression: {expression}"
    )
    return node


def parse_number(expression, index=0):
    """Parse expression and extract a Number value, handling unary negation.

    Negative number literals like "-17" parse as UnaryOp("-", Number(17)),
    not as Number(-17). This helper unwraps that structure and returns
    the final numeric value.

    Args:
        expression: Source code to parse
        index: Which child of Root to return (default: 0)

    Returns:
        The Decimal value from the Number node (with sign applied)

    Raises:
        AssertionError: If node is not a Number or UnaryOp("-", Number)

    Example:
        value = parse_number("42")        # Returns Decimal('42')
        value = parse_number("-17")       # Returns Decimal('-17')
        value = parse_number("+3.14")     # Returns Decimal('3.14')
    """
    result = comp.parse_expr(expression)
    node = result.kids[index] if result.kids else result

    # Handle UnaryOp("-", Number) or UnaryOp("+", Number)
    if isinstance(node, comp.ast.UnaryOp):
        operand = node.kids[0]   # The Number node

        assert isinstance(operand, comp.ast.Number), (
            f"Expected UnaryOp operand to be Number, got {type(operand).__name__}\n"
            f"  Expression: {expression}"
        )

        if node.op == "-":
            return -operand.value
        else:  # "+" or other
            return operand.value

    # Handle direct Number
    assert isinstance(node, comp.ast.Number), (
        f"Expected Number or UnaryOp, got {type(node).__name__}\n"
        f"  Expression: {expression}"
    )
    return node.value


def assert_unparse(ast, expression):
    """Assert that AST unpars to expected expression string.

    Args:
        ast: Node to unparse
        expression: Expected unparsed string

    Raises:
        AssertionError: If unparsed output doesn't match

    Example:
        result = comp.parse_expr("a+b")
        assert_unparse(result, "a + b")  # Spaces normalized
    """
    unparsed = ast.unparse()
    assert unparsed == expression, (
        f"Unparsed output mismatch:\n"
        f"  Expected: {expression}\n"
        f"  Got:      {unparsed}"
    )


def structure_field(struct, index, cls=None):
    """Extract a field from a Structure node at the given index.

    Args:
        struct: A Structure node
        index: Zero-based field index (supports negative indexing)
        cls: Optional expected type for the value (default: no type check)

    Returns:
        Tuple of (key, value) where:
        - key is the field name string for StructAssign (or None for StructUnnamed)
        - value is the field value Node

    Raises:
        AssertionError: If struct is not a Structure, index out of range,
                       or value doesn't match cls type

    Example:
        struct = parse_value("{outer={inner=42}}", comp.ast.Structure)
        key, value = structure_field(struct, 0)
        assert key == "outer"
        assert isinstance(value, comp.ast.Structure)

        # With type checking:
        struct = parse_value("{x = data |process}", comp.ast.Structure)
        key, value = structure_field(struct, 0, comp.Pipeline)
        # Automatically asserts isinstance(value, comp.Pipeline)

        struct = parse_value("{1 {2 3} 4}", comp.ast.Structure)
        key, value = structure_field(struct, 1)
        assert key is None  # positional field
        assert isinstance(value, comp.ast.Structure)
    """
    assert isinstance(struct, comp.ast.Structure), (
        f"Expected Structure, got {type(struct).__name__}"
    )
    assert -len(struct.kids) <= index < len(struct.kids), (
        f"Field index {index} out of range for Structure with {len(struct.kids)} fields"
    )

    field = struct.kids[index]

    # StructAssign: kids[0] is key (Identifier), kids[1] is value
    # StructUnnamed: kids[0] is value
    if isinstance(field, comp.ast.StructAssign):
        key_node = field.kids[0]
        # Extract the string name from the Identifier
        key = key_node.kids[0].value if key_node.kids else None
        value = field.kids[1]
    elif isinstance(field, comp.ast.StructUnnamed):
        key = None
        value = field.kids[0]
    else:
        # Fallback for unexpected field types
        key = None
        value = field

    # Optional type check
    if cls is not None:
        assert isinstance(value, cls), (
            f"Expected value to be {cls.__name__}, got {type(value).__name__}\n"
            f"  Key: {key}"
        )

    return key, value
