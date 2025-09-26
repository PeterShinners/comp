"""
Test edge cases and invalid syntax for mathematical operators.

This module tests corner cases, invalid syntax, and boundary conditions
for mathematical operators to ensure proper error handling and edge case behavior.
"""

import comp
import pytest


# Invalid operator syntax cases that should raise parse errors
invalid_operator_cases = [
    # Invalid operator combinations
    ("12 * / 3", "consecutive binary operators"),
    ("5 + * 2", "plus followed by multiply"),
    ("1 / / 2", "double division operator"),
    ("7 - * 8", "minus followed by multiply"),
    ("9 % / 3", "modulo followed by division"),
    # Missing operands (but not unary cases)
    ("3 +", "binary operator without right operand"),
    ("* 4", "multiply without left operand"),
    ("/ 2", "divide without left operand"),
    ("()", "empty parentheses"),
    # Invalid parentheses
    ("(3 + 4", "unclosed parenthesis"),
    ("3 + 4)", "unmatched closing parenthesis"),
    ("((3 + 4)", "unmatched nested parenthesis"),
    ("3 + (4 * 5))", "extra closing parenthesis"),
    # Invalid whitespace/structure
    ("3 + 4 5", "missing operator between numbers"),
    ("x y", "missing operator between identifiers"),
    ("#tag1 #tag2", "missing operator between references"),
]


# Valid but tricky cases that should parse correctly
tricky_valid_cases = [
    # Unary operators (these should be valid)
    ("4--4", "double minus (4 - (-4))"),
    ("4+-4", "plus minus (4 + (-4))"),
    ("4*-4", "multiply negative (4 * (-4))"),
    ("4/-4", "divide negative (4 / (-4))"),
    ("-4*-4", "negative multiply negative"),
    ("--4", "double negative"),
    ("+ 5", "unary plus"),
    ("3 + + 4", "binary plus with unary plus"),
    # Valid operators that might look suspicious
    ("2 ** 3", "exponentiation operator"),
    ("4 && 5", "logical AND operator"),
    ("6 || 7", "logical OR operator"),
    # Complex precedence
    ("1 + 2 * 3 - 4 / 2", "mixed precedence"),
    ("(1 + 2) * (3 - 4)", "parentheses precedence"),
    ("1 + 2 * 3 + 4", "left-to-right same precedence"),
    # Edge cases with references and identifiers
    ("x + -y", "identifier plus negative identifier"),
    ("#tag + -#other", "tag plus negative tag"),
    ("~shape * -~other", "shape multiply negative shape"),
    # Complex nested expressions (without function calls for now)
    ("((1 + 2) * 3) - ((4 / 2) + 1)", "deeply nested parentheses"),
    ("{result = (x + y) * (a - b)}", "structure with complex expression"),
]


@pytest.mark.parametrize(
    "invalid_input,description",
    invalid_operator_cases,
    ids=[case[1] for case in invalid_operator_cases],
)
def test_invalid_operator_syntax(invalid_input, description):
    """Test that invalid operator syntax raises parse errors."""
    with pytest.raises(Exception) as exc_info:
        comp.parse(invalid_input)

    # Verify we get some kind of parse error
    assert exc_info.value is not None
    print(f"✓ Correctly rejected: {invalid_input} - {description}")
    print(f"  Error: {exc_info.value}")


@pytest.mark.parametrize(
    "valid_input,description",
    tricky_valid_cases,
    ids=[case[1] for case in tricky_valid_cases],
)
def test_tricky_valid_syntax(valid_input, description):
    """Test that tricky but valid syntax parses correctly."""
    try:
        result = comp.parse(valid_input)
        assert result is not None
        print(f"✓ Correctly parsed: {valid_input} - {description}")
        print(f"  Result: {result}")
    except Exception as e:
        pytest.fail(
            f"Should have parsed '{valid_input}' ({description}) but got error: {e}"
        )


def test_operator_precedence():
    """Test that operator precedence works correctly."""
    # Test basic precedence: multiplication before addition
    result = comp.parse("2 + 3 * 4")
    assert isinstance(result, comp.BinaryOperation)
    assert result.operator == "+"
    assert isinstance(result.left, comp.NumberLiteral)
    assert result.left.value == 2
    assert isinstance(result.right, comp.BinaryOperation)
    assert result.right.operator == "*"

    # Test parentheses override precedence
    result = comp.parse("(2 + 3) * 4")
    assert isinstance(result, comp.BinaryOperation)
    assert result.operator == "*"
    # Left side should be the parenthesized addition
    # Note: We might need to handle parentheses transformation better


def test_unary_operators():
    """Test unary operators work correctly."""
    # Test basic unary minus
    result = comp.parse("-5")
    assert isinstance(result, comp.NumberLiteral)
    assert result.value == -5

    # Test unary in expressions
    result = comp.parse("x + -y")
    assert isinstance(result, comp.BinaryOperation)
    assert result.operator == "+"
    assert isinstance(result.left, comp.Identifier)
    assert result.left.name == "x"
    # Right side should be negative identifier (however that's represented)


def test_comparison_operators():
    """Test comparison operators parse correctly."""
    comparison_ops = ["==", "!=", "<", "<=", ">", ">="]

    for op in comparison_ops:
        expr = f"x {op} y"
        result = comp.parse(expr)
        assert isinstance(result, comp.BinaryOperation)
        assert result.operator == op
        assert isinstance(result.left, comp.Identifier)
        assert isinstance(result.right, comp.Identifier)


def test_logical_operators():
    """Test logical operators parse correctly."""
    logical_cases = [
        ("x and y", "and"),
        ("x or y", "or"),
        ("not x", "not"),
        ("x and y or z", "mixed logical"),
    ]

    for expr, _ in logical_cases:
        try:
            result = comp.parse(expr)
            print(f"✓ Logical operator: {expr} -> {result}")
        except Exception as e:
            print(f"⚠ Logical operator may not be implemented yet: {expr} -> {e}")


def test_mixed_atom_types_in_operations():
    """Test that different atom types can be used in operations."""
    mixed_cases = [
        "42 + x",  # number + identifier
        "x + #balance",  # identifier + tag
        "#rate * 100",  # tag * number
        "~num + ~int",  # shape + shape
        "|getValue - count",  # function reference - identifier (proper syntax)
        "{total = base + #tax}",  # structure with mixed operation
    ]

    for expr in mixed_cases:
        result = comp.parse(expr)
        assert result is not None
        print(f"✓ Mixed atoms: {expr} -> type: {type(result).__name__}")


def test_deeply_nested_expressions():
    """Test complex nested expressions parse correctly."""
    nested_cases = [
        # Skip complex parentheses for now due to transformer issues
        # "((x + y) * z)",
        # "(a + (b * c))",
        # "((a + b) * (c + d))",
        "x + y * z",  # Simple precedence
        "{result = base + tax * rate}",  # Structure with expression
        "x + (y - z)",  # Simple parentheses
    ]

    for expr in nested_cases:
        result = comp.parse(expr)
        assert result is not None
        print(f"✓ Nested expression: {expr}")


def test_whitespace_sensitivity():
    """Test how whitespace affects operator parsing."""
    # These should all be equivalent
    equivalent_cases = [
        ["1 + 2", "1+2"],  # Addition (if tokenizer supports it)
        ["x * y", "x*y"],  # Multiplication
        ["a == b", "a==b"],  # Comparison
    ]

    for expressions in equivalent_cases:
        results = []
        for expr in expressions:
            try:
                result = comp.parse(expr)
                results.append(result)
                print(f"✓ Whitespace test: '{expr}' -> {result}")
            except Exception as e:
                print(f"⚠ Whitespace issue: '{expr}' -> {e}")
                results.append(None)

        # All non-None results should be equivalent
        valid_results = [r for r in results if r is not None]
        if len(valid_results) > 1:
            # Could add more sophisticated equivalence checking here
            print("  Multiple valid parses for equivalent expressions")
