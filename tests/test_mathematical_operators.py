"""Tests for Mathematical Operators

Tests mathematical operators including arithmetic, comparison, logical operators,
and parentheses for expression parsing. This phase focuses on the mathematical
foundation that will be common across programming languages.
"""

import pytest

import comp


def test_basic_arithmetic_operators_parse():
    """Test that basic arithmetic operators parse correctly"""
    # Test addition - should create BinaryOperation AST
    result = comp.parse("1 + 2")
    _assert_binary(result, "+", 1, 2)

    # Test multiplication with higher precedence than addition
    # 1 + 2 * 3 should parse as 1 + (2 * 3), so root is addition
    result = comp.parse("1 + 2 * 3")
    _assert_binary(result, "+", 1, None)  # Root is addition, left operand is 1
    _assert_binary(result.right, "*", 2, 3)  # Right operand is (2 * 3)


def test_comparison_operators_parse():
    """Test comparison operators == != < <= > >="""
    # Test equality operators
    result = comp.parse("x == 5")
    _assert_binary(result, "==", "ident=x", 5)

    result = comp.parse('"Bob" != "Alice"')
    _assert_binary(result, "!=", "Bob", "Alice")

    # Test ordering operators
    result = comp.parse("age > limit")
    _assert_binary(result, ">", "ident=age", "ident=limit")

    result = comp.parse('"<html>" <= "</html>"')
    _assert_binary(result, "<=", "<html>", "</html>")

    result = comp.parse("count >= 0")
    _assert_binary(result, ">=", "ident=count", 0)


def test_logical_operators_parse():
    """Test logical operators && || !!"""
    result = comp.parse("!!active")
    _assert_unary(result, "!!", "ident=active")

    result = comp.parse("x > 0 && y < 10")
    _assert_binary(result, "&&", None, None)
    _assert_binary(result.left, ">", "ident=x", 0)
    _assert_binary(result.right, "<", "ident=y", 10)

    result = comp.parse("ready == 1 || force == 1")
    _assert_binary(result, "||", None, None)
    _assert_binary(result.left, "==", "ident=ready", 1)
    _assert_binary(result.right, "==", "ident=force", 1)

    result = comp.parse("!!error && (ready || force)")
    _assert_binary(result, "&&", None, None)
    _assert_unary(result.left, "!!", "ident=error")
    # _assert_binary(result.right, "||", "ident=ready", "ident=force")


def test_operator_precedence():
    """Test mathematical operator precedence rules"""
    # Test that multiplication has higher precedence than addition
    # 1 + 2 * 3 should parse as 1 + (2 * 3), not (1 + 2) * 3
    result = comp.parse("1 + 2 * 3")
    _assert_binary(result, "+", 1, None)

    # Test that power operator has higher precedence and is right-associative
    # 2 ** 3 ** 2 should parse as 2 ** (3 ** 2) = 512, not (2 ** 3) ** 2 = 64
    result = comp.parse("2 ** 3 ** 2")
    _assert_binary(result, "**", 2, None)

    # Test unary operators have high precedence
    # -x + 3 should be (-x) + 3, not -(x + 3)
    result = comp.parse("-x + 3")
    _assert_binary(result, "+", None, 3)

    # Test parentheses override precedence
    # (1 + 2) * 3 should be 9, not 7
    result = comp.parse("(1 + 2) * 3")
    _assert_binary(result, "*", None, 3)


def _assert_binary(node, operator, left, right):
    """Helper to assert a BinaryOperation node structure"""
    assert isinstance(node, comp.BinaryOperation)
    assert node.operator == operator
    _check_value(node.left, left, "left ")
    _check_value(node.right, right, "right ")


def _assert_unary(node, operator, value):
    """Helper to assert a UnaryOperation node structure"""
    assert isinstance(node, comp.UnaryOperation)
    assert node.operator == operator
    _check_value(node.operand, value, "")


def _check_value(operand, expected, side):
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
