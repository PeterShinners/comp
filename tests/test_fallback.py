"""Test the fallback operator (??) with fail propagation."""

import comp
import comptest


def test_fallback_left_succeeds():
    """When left succeeds, return left (don't evaluate right)."""
    # 5 ?? 10 should return 5
    expr = comp.ast.FallbackOp(
        left=comp.ast.Number(5),
        right=comp.ast.Number(10)
    )
    value = comptest.run_ast(expr)
    comptest.assert_value(value, 5)


def test_fallback_left_fails():
    """When left fails, return right."""
    # --- ?? 42 should return 42
    expr = comp.ast.FallbackOp(
        left=comp.ast.Placeholder(),
        right=comp.ast.Number(42)
    )
    value = comptest.run_ast(expr)
    comptest.assert_value(value, 42)


def test_fallback_both_fail():
    """When both fail, propagate the second fail."""
    # (1/0) ?? (2/0) should propagate second fail
    expr = comp.ast.FallbackOp(
        left=comp.ast.Placeholder(),
        right=comp.ast.ArithmeticOp("/", comp.ast.Number(2), comp.ast.Number(0))
    )
    value = comptest.run_ast(expr)
    comptest.assert_fail(value, 'zero')


def test_fallback_nested():
    """Nested fallbacks work correctly."""
    # (1/0) ?? ((2/0) ?? 42) should return 42
    expr = comp.ast.FallbackOp(
        left=comp.ast.ArithmeticOp("/", comp.ast.Number(1), comp.ast.Number(0)),
        right=comp.ast.FallbackOp(
            left=comp.ast.ArithmeticOp("/", comp.ast.Number(2), comp.ast.Number(0)),
            right=comp.ast.Number(42)
        )
    )
    value = comptest.run_ast(expr)
    comptest.assert_value(value, 42)


def test_fallback_propagates_from_right():
    """If right fails, that propagates to parent."""
    # ((1/0) ?? (2/0)) + 10 should fail (right fails, propagates)
    expr = comp.ast.ArithmeticOp(
        "+",
        comp.ast.FallbackOp(
            left=comp.ast.ArithmeticOp("/", comp.ast.Number(1), comp.ast.Number(0)),
            right=comp.ast.ArithmeticOp("/", comp.ast.Number(2), comp.ast.Number(0))
        ),
        comp.ast.Number(10)
    )
    value = comptest.run_ast(expr)
    comptest.assert_fail(value, 'zero')

