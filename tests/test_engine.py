"""Test the new Engine class with AST nodes."""

import comp
import comptest


def test_simple_literal():
    """Test evaluating simple literals."""
    value = comptest.run_ast(comp.ast.Number(42))
    comptest.assert_value(value, 42)

    value = comptest.run_ast(comp.ast.String("forty-two"))
    comptest.assert_value(value, "forty-two")


def test_arithmetic():
    """Test arithmetic operations."""
    # 1 + 2
    expr = comp.ast.ArithmeticOp("+", comp.ast.Number(1), comp.ast.Number(2))
    value = comptest.run_ast(expr)
    comptest.assert_value(value, 3)

    # (5 * 3) - 10
    expr = comp.ast.ArithmeticOp("-",
        comp.ast.ArithmeticOp("*", comp.ast.Number(5), comp.ast.Number(3)),
        comp.ast.Number(10)
    )
    value = comptest.run_ast(expr)
    comptest.assert_value(value, 5)

