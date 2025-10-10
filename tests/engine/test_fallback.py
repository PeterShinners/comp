"""Test the fallback operator (??) with fail propagation."""

from src.comp.engine.engine import Engine
from src.comp.engine.ast.literals import Number
from src.comp.engine.ast.operators import ArithmeticOp, FallbackOp
from src.comp.engine.value import Value


def test_fallback_left_succeeds():
    """When left succeeds, return left (don't evaluate right)."""
    engine = Engine()

    # 5 ?? 10 should return 5
    expr = FallbackOp(
        left=Number(5),
        right=Number(10)
    )

    result = engine.run(expr)
    assert result.data == 5


def test_fallback_left_fails():
    """When left fails, return right."""
    engine = Engine()

    # (1/0) ?? 42 should return 42
    expr = FallbackOp(
        left=ArithmeticOp("/", Number(1), Number(0)),
        right=Number(42)
    )

    result = engine.run(expr)
    assert result.data == 42


def test_fallback_both_fail():
    """When both fail, propagate the second fail."""
    engine = Engine()

    # (1/0) ?? (2/0) should propagate second fail
    expr = FallbackOp(
        left=ArithmeticOp("/", Number(1), Number(0)),
        right=ArithmeticOp("/", Number(2), Number(0))
    )

    result = engine.run(expr)
    assert engine.is_fail(result)
    assert "Division by zero" in result.data


def test_fallback_nested():
    """Nested fallbacks work correctly."""
    engine = Engine()

    # (1/0) ?? ((2/0) ?? 42) should return 42
    expr = FallbackOp(
        left=ArithmeticOp("/", Number(1), Number(0)),
        right=FallbackOp(
            left=ArithmeticOp("/", Number(2), Number(0)),
            right=Number(42)
        )
    )

    result = engine.run(expr)
    assert result.data == 42


def test_fallback_in_arithmetic():
    """Fallback can be used within larger expressions."""
    engine = Engine()

    # ((1/0) ?? 5) + 10 should return 15
    expr = ArithmeticOp(
        "+",
        FallbackOp(
            left=ArithmeticOp("/", Number(1), Number(0)),
            right=Number(5)
        ),
        Number(10)
    )

    result = engine.run(expr)
    assert result.data == 15


def test_fallback_propagates_from_right():
    """If right fails, that propagates to parent."""
    engine = Engine()

    # ((1/0) ?? (2/0)) + 10 should fail (right fails, propagates)
    expr = ArithmeticOp(
        "+",
        FallbackOp(
            left=ArithmeticOp("/", Number(1), Number(0)),
            right=ArithmeticOp("/", Number(2), Number(0))
        ),
        Number(10)
    )

    result = engine.run(expr)
    assert engine.is_fail(result)


def test_fail_prevents_further_evaluation():
    """Fail in complex expression prevents subsequent operations."""
    engine = Engine()

    # (1 + (2/0)) + 10 should fail without evaluating the outer +10
    # We can verify this by the fact that it returns a fail, not a number
    expr = ArithmeticOp(
        "+",
        ArithmeticOp("+", Number(1), ArithmeticOp("/", Number(2), Number(0))),
        Number(10)
    )

    result = engine.run(expr)
    assert engine.is_fail(result)
    # The fail should be from the arithmetic operation, not division
    # because the ArithmeticOp receives the division fail and creates a new fail


def test_fallback_prevents_dangerous_evaluation():
    """Fallback prevents evaluation of operations after a fail."""
    engine = Engine()

    # ((1/0) + 100) ?? 42 should return 42
    # The +100 should not be evaluated because (1/0) fails
    # and ArithmeticOp immediately fails when it gets a non-number
    expr = FallbackOp(
        left=ArithmeticOp("+", ArithmeticOp("/", Number(1), Number(0)), Number(100)),
        right=Number(42)
    )

    result = engine.run(expr)
    assert result.data == 42


def test_unparse():
    """Test unparsing fallback operators."""
    expr = FallbackOp(
        left=Number(1),
        right=Number(2)
    )
    assert expr.unparse() == "(1 ?? 2)"


if __name__ == "__main__":
    test_fallback_left_succeeds()
    print("✓ test_fallback_left_succeeds")

    test_fallback_left_fails()
    print("✓ test_fallback_left_fails")

    test_fallback_both_fail()
    print("✓ test_fallback_both_fail")

    test_fallback_nested()
    print("✓ test_fallback_nested")

    test_fallback_in_arithmetic()
    print("✓ test_fallback_in_arithmetic")

    test_fallback_propagates_from_right()
    print("✓ test_fallback_propagates_from_right")

    test_fail_prevents_further_evaluation()
    print("✓ test_fail_prevents_further_evaluation")

    test_fallback_prevents_dangerous_evaluation()
    print("✓ test_fallback_prevents_dangerous_evaluation")

    test_unparse()
    print("✓ test_unparse")

    print("\n✅ All fallback tests passed!")
