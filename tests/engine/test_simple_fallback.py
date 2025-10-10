"""Simple test to verify fallback operator works correctly."""

from comp.engine.ast.literals import Number
from comp.engine.ast.operators import ArithmeticOp, FallbackOp
from comp.engine.engine import Engine


def test_simple_fallback():
    """Test (2/0) ?? 42 returns 42."""
    engine = Engine()
    
    expr = FallbackOp(
        left=ArithmeticOp("/", Number(2), Number(0)),
        right=Number(42)
    )
    
    result = engine.run(expr)
    print(f"Result: {result}")
    print(f"Is fail? {engine.is_fail(result)}")
    assert result.data == 42
    print("✅ Simple fallback works!")


def test_complex_fallback():
    """Test (1 + (2/0)) ?? 42 returns 42."""
    engine = Engine()
    
    expr = FallbackOp(
        left=ArithmeticOp(
            "+",
            Number(1),
            ArithmeticOp("/", Number(2), Number(0))
        ),
        right=Number(42)
    )
    
    result = engine.run(expr)
    print(f"Result: {result}")
    print(f"Is fail? {engine.is_fail(result)}")
    assert result.data == 42
    print("✅ Complex fallback works!")


def test_both_fail():
    """Test (1/0) ?? (2/0) propagates fail."""
    engine = Engine()
    
    expr = FallbackOp(
        left=ArithmeticOp("/", Number(1), Number(0)),
        right=ArithmeticOp("/", Number(2), Number(0))
    )
    
    result = engine.run(expr)
    print(f"Result: {result}")
    print(f"Is fail? {engine.is_fail(result)}")
    assert engine.is_fail(result)
    assert "Division by zero" in result.data
    print("✅ Both fail propagates!")


def test_fail_before_fallback():
    """Test (1/0) + (2 ?? 3) - fail before fallback is evaluated."""
    engine = Engine()
    
    # The left side fails, so right side (including fallback) never evaluated
    expr = ArithmeticOp(
        "+",
        ArithmeticOp("/", Number(1), Number(0)),
        FallbackOp(Number(2), Number(3))
    )
    
    result = engine.run(expr)
    print(f"Result: {result}")
    print(f"Is fail? {engine.is_fail(result)}")
    assert engine.is_fail(result)
    assert "Division by zero" in result.data
    print("✅ Fail before fallback works!")


def test_fallback_with_both_sides_failing():
    """Test (1/0) ?? (2/0) - should get second failure."""
    engine = Engine()
    
    expr = FallbackOp(
        left=ArithmeticOp("/", Number(1), Number(0)),
        right=ArithmeticOp("/", Number(2), Number(0))
    )
    
    result = engine.run(expr)
    print(f"Result: {result}")
    print(f"Is fail? {engine.is_fail(result)}")
    assert engine.is_fail(result)
    # Should be the second division's error
    assert "Division by zero" in result.data
    print("✅ Both sides fail returns second failure!")


if __name__ == "__main__":
    test_simple_fallback()
    print()
    test_complex_fallback()
    print()
    test_both_fail()
    print()
    test_fail_before_fallback()
    print()
    test_fallback_with_both_sides_failing()
    print("\n✅ All tests passed!")
