"""
Core operator parsing tests for mathematical and logical operators.

Tests arithmetic, comparison, logical, and fallback operators with focus on
operator behavior, precedence, and proper parsing.
"""

import comp
import comptest


@comptest.params(
    "expression, operator",
    add=("5 + 3", "+"),
    sub=("10 - 4", "-"),
    mult=("6 * 7", "*"),
    div=("20 / 5", "/"),
    mod=("17 % 5", "%"),
)
def test_arithmetic_operators(key, expression, operator):
    """Test basic arithmetic operators parse correctly."""
    result = comp.parse(expression)
    # Extract from Root wrapper
    result = result.kids[0] if result.kids else result
    assert isinstance(result, comp._ast.BinaryOp)
    assert result.op == operator


@comptest.params(
    "expression",
    plus=("+42",),
    minus=("-42",),
    pident=("+value",),
    mident=("-count",),
)
def test_unary_operators(key, expression):
    """Test unary operators parse correctly."""
    result = comp.parse(expression)
    # Extract from Root wrapper
    result = result.kids[0] if result.kids else result
    assert isinstance(result, comp._ast.UnaryOp)
    assert result.op in ["+", "-"]


@comptest.params(
    "expression, operator",
    equal=("a == b", "=="),
    not_equal=("a != b", "!="),
    less_than=("a < b", "<"),
    less_equal=("a <= b", "<="),
    greater_than=("a > b", ">"),
    greater_equal=("a >= b", ">="),
)
def test_comparison_operators(key, expression, operator):
    """Test comparison operators parse correctly."""
    result = comp.parse(expression)
    # Extract from Root wrapper
    result = result.kids[0] if result.kids else result
    assert isinstance(result, comp._ast.BinaryOp)
    assert result.op == operator


@comptest.params(
    "expression, operator",
    logical_and=("true && false", "&&"),
    logical_or=("true || false", "||"),
)
def test_logical_operators(key, expression, operator):
    """Test logical operators parse correctly."""
    result = comp.parse(expression)
    # Extract from Root wrapper
    result = result.kids[0] if result.kids else result
    assert isinstance(result, comp._ast.BinaryOp)
    assert result.op == operator


@comptest.params(
    "expression",
    mult_before_add=("2 + 3 * 4", ),
    parens_override=("(2 + 3) * 4", ),
    comparison_lower=("2 + 3 < 4 * 5", ),
    logical_lowest=("2 < 3 && 4 > 5", ),
)
def test_operator_precedence(key, expression):
    """Test operator precedence is handled correctly."""
    result = comp.parse(expression)
    comptest.roundtrip(result)


def test_addition_multiplication_precedence():
    """Verify 2 + 3 * 4 == 2 + (3 * 4), not (2 + 3) * 4."""
    result = comp.parse("2 + 3 * 4")
    # Extract from Root wrapper
    result = result.kids[0] if result.kids else result
    assert isinstance(result, comp._ast.BinaryOp)
    assert result.op == "+"
    # Right side should be multiplication
    assert isinstance(result.kids[1], comp._ast.BinaryOp)
    assert result.kids[1].op == "*"


def test_comparison_arithmetic_precedence():
    """Verify 2 + 3 < 4 * 5 == (2 + 3) < (4 * 5)."""
    result = comp.parse("2 + 3 < 4 * 5")
    # Extract from Root wrapper
    result = result.kids[0] if result.kids else result
    assert isinstance(result, comp._ast.BinaryOp)
    assert result.op == "<"
    # Both sides should be arithmetic
    assert isinstance(result.kids[0], comp._ast.BinaryOp)
    assert result.kids[0].op == "+"
    assert isinstance(result.kids[1], comp._ast.BinaryOp)
    assert result.kids[1].op == "*"


def test_logical_comparison_precedence():
    """Verify 2 < 3 && 4 > 5 == (2 < 3) && (4 > 5)."""
    result = comp.parse("2 < 3 && 4 > 5")
    # Extract from Root wrapper
    result = result.kids[0] if result.kids else result
    assert isinstance(result, comp._ast.BinaryOp)
    assert result.op == "&&"
    # Both sides should be comparisons
    assert isinstance(result.kids[0], comp._ast.BinaryOp)
    assert result.kids[0].op == "<"
    assert isinstance(result.kids[1], comp._ast.BinaryOp)
    assert result.kids[1].op == ">"


@comptest.params(
    "expression",
    chained_comparison=("a < b < c",),
    mixed_logical=("a && b || c",),
    arithmetic_chain=("a + b - c * d / e",),
)
def test_operator_combinations(key, expression):
    """Test complex combinations of operators parse correctly."""
    result = comp.parse(expression)
    comptest.roundtrip(result)


@comptest.params(
    "expression",
    double_unary=("--x",),
    nested_parens=("((((5))))",),
    whitespace_heavy=("a   +   b",),
    no_whitespace=("a+b*c-d",),
)
def test_operator_edge_cases(key, expression):
    """Test edge cases in operator parsing."""
    result = comp.parse(expression)
    comptest.roundtrip(result)


@comptest.params(
    "expression",
    triple_equal=("a === b",),
    single_and=("a & b",),
    bitshift_left=("a << b",),
    bitshift_right=("a >> b",),
    spaceship=("a <=> b",),
    arrow=("a -> b",),
    double_colon=("a :: b",),
)
def test_invalid_operator_syntax(key, expression):
    """Test that invalid operator syntax fails to parse."""
    comptest.invalid_parse(expression, match=r"parse error|unexpected")
