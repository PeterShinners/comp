"""Test the fallback operator (??) with fail propagation."""

import comp.engine as comp


def test_fallback_left_succeeds():
    """When left succeeds, return left (don't evaluate right)."""
    engine = comp.Engine()

    # 5 ?? 10 should return 5
    expr = comp.ast.FallbackOp(
        left=comp.ast.Number(5),
        right=comp.ast.Number(10)
    )

    result = engine.run(expr)
    assert result.data == 5


def test_fallback_left_fails():
    """When left fails, return right."""
    engine = comp.Engine()

    # --- ?? 42 should return 42
    expr = comp.ast.FallbackOp(
        left=comp.ast.Placeholder(),
        right=comp.ast.Number(42)
    )

    result = engine.run(expr)
    assert result.data == 42


def test_fallback_both_fail():
    """When both fail, propagate the second fail."""
    engine = comp.Engine()

    # (1/0) ?? (2/0) should propagate second fail
    expr = comp.ast.FallbackOp(
        left=comp.ast.Placeholder(),
        right=comp.ast.ArithmeticOp("/", comp.ast.Number(2), comp.ast.Number(0))
    )

    result = engine.run(expr)
    assert engine.is_fail(result)
    assert "Division by zero" in result.data['message'].data


def test_fallback_nested():
    """Nested fallbacks work correctly."""
    engine = comp.Engine()

    # (1/0) ?? ((2/0) ?? 42) should return 42
    expr = comp.ast.FallbackOp(
        left=comp.ast.ArithmeticOp("/", comp.ast.Number(1), comp.ast.Number(0)),
        right=comp.ast.FallbackOp(
            left=comp.ast.ArithmeticOp("/", comp.ast.Number(2), comp.ast.Number(0)),
            right=comp.ast.Number(42)
        )
    )

    result = engine.run(expr)
    assert result.data == 42


def test_fallback_in_arithmetic():
    """Fallback can be used within larger expressions."""
    engine = comp.Engine()

    # ((1/0) ?? 5) + 10 should return 15
    expr = comp.ast.ArithmeticOp(
        "+",
        comp.ast.FallbackOp(
            left=comp.ast.ArithmeticOp("/", comp.ast.Number(1), comp.ast.Number(0)),
            right=comp.ast.Number(5)
        ),
        comp.ast.Number(10)
    )

    result = engine.run(expr)
    assert result.data == 15


def test_fallback_propagates_from_right():
    """If right fails, that propagates to parent."""
    engine = comp.Engine()

    # ((1/0) ?? (2/0)) + 10 should fail (right fails, propagates)
    expr = comp.ast.ArithmeticOp(
        "+",
        comp.ast.FallbackOp(
            left=comp.ast.ArithmeticOp("/", comp.ast.Number(1), comp.ast.Number(0)),
            right=comp.ast.ArithmeticOp("/", comp.ast.Number(2), comp.ast.Number(0))
        ),
        comp.ast.Number(10)
    )

    result = engine.run(expr)
    assert engine.is_fail(result)


def test_fail_prevents_further_evaluation():
    """Fail in complex expression prevents subsequent operations."""
    engine = comp.Engine()

    # (1 + (2/0)) + 10 should fail without evaluating the outer +10
    # We can verify this by the fact that it returns a fail, not a number
    expr = comp.ast.ArithmeticOp(
        "+",
        comp.ast.ArithmeticOp("+", comp.ast.Number(1), comp.ast.ArithmeticOp("/", comp.ast.Number(2), comp.ast.Number(0))),
        comp.ast.Number(10)
    )

    result = engine.run(expr)
    assert engine.is_fail(result)
    # The fail should be from the arithmetic operation, not division
    # because the comp.ast.ArithmeticOp receives the division fail and creates a new fail


def test_fallback_prevents_dangerous_evaluation():
    """Fallback prevents evaluation of operations after a fail."""
    engine = comp.Engine()

    # ((1/0) + 100) ?? 42 should return 42
    # The +100 should not be evaluated because (1/0) fails
    # and comp.ast.ArithmeticOp immediately fails when it gets a non-number
    expr = comp.ast.FallbackOp(
        left=comp.ast.ArithmeticOp("+", comp.ast.ArithmeticOp("/", comp.ast.Number(1), comp.ast.Number(0)), comp.ast.Number(100)),
        right=comp.ast.Number(42)
    )

    result = engine.run(expr)
    assert result.data == 42


def test_unparse():
    """Test unparsing fallback operators."""
    expr = comp.ast.FallbackOp(
        left=comp.ast.Number(1),
        right=comp.ast.Number(2)
    )
    assert expr.unparse() == "(1 ?? 2)"

