"""Tests for generator-based evaluation engine."""

import pytest
from .context import EvalContext
from .nodes import Number, String, BinaryOp, UnaryOp
from .value import Value, TRUE, FALSE


class TestLiterals:
    """Test literal evaluation."""
    
    def test_number_literal(self):
        ctx = EvalContext()
        expr = Number(42)
        result = ctx.evaluate(expr)
        assert result.data == 42
        assert result.is_number
    
    def test_string_literal(self):
        ctx = EvalContext()
        expr = String("hello")
        result = ctx.evaluate(expr)
        assert result.data == "hello"
        assert result.is_string
    
    def test_float_literal(self):
        ctx = EvalContext()
        expr = Number(3.14)
        result = ctx.evaluate(expr)
        assert result.data == 3.14


class TestArithmetic:
    """Test arithmetic operations."""
    
    def test_addition(self):
        ctx = EvalContext()
        expr = BinaryOp("+", Number(2), Number(3))
        result = ctx.evaluate(expr)
        assert result.data == 5
    
    def test_subtraction(self):
        ctx = EvalContext()
        expr = BinaryOp("-", Number(10), Number(3))
        result = ctx.evaluate(expr)
        assert result.data == 7
    
    def test_multiplication(self):
        ctx = EvalContext()
        expr = BinaryOp("*", Number(4), Number(5))
        result = ctx.evaluate(expr)
        assert result.data == 20
    
    def test_division(self):
        ctx = EvalContext()
        expr = BinaryOp("/", Number(20), Number(4))
        result = ctx.evaluate(expr)
        assert result.data == 5.0
    
    def test_division_by_zero(self):
        ctx = EvalContext()
        expr = BinaryOp("/", Number(10), Number(0))
        result = ctx.evaluate(expr)
        assert result.tag == ctx.fail_type
        assert "zero" in result.data["message"].lower()
    
    def test_nested_arithmetic(self):
        # (2 + 3) * 4 = 20
        ctx = EvalContext()
        expr = BinaryOp("*", 
            BinaryOp("+", Number(2), Number(3)),
            Number(4)
        )
        result = ctx.evaluate(expr)
        assert result.data == 20
    
    def test_deeply_nested(self):
        # ((1 + 2) + (3 + 4)) + 5 = 15
        ctx = EvalContext()
        expr = BinaryOp("+",
            BinaryOp("+",
                BinaryOp("+", Number(1), Number(2)),
                BinaryOp("+", Number(3), Number(4))
            ),
            Number(5)
        )
        result = ctx.evaluate(expr)
        assert result.data == 15


class TestUnaryOps:
    """Test unary operations."""
    
    def test_negation(self):
        ctx = EvalContext()
        expr = UnaryOp("-", Number(5))
        result = ctx.evaluate(expr)
        assert result.data == -5
    
    def test_double_negation(self):
        ctx = EvalContext()
        expr = UnaryOp("-", UnaryOp("-", Number(5)))
        result = ctx.evaluate(expr)
        assert result.data == 5


class TestComparison:
    """Test comparison operations."""
    
    def test_equality(self):
        ctx = EvalContext()
        expr = BinaryOp("==", Number(5), Number(5))
        result = ctx.evaluate(expr)
        assert result.tag == TRUE
    
    def test_inequality(self):
        ctx = EvalContext()
        expr = BinaryOp("!=", Number(5), Number(3))
        result = ctx.evaluate(expr)
        assert result.tag == TRUE
    
    def test_less_than(self):
        ctx = EvalContext()
        expr = BinaryOp("<", Number(3), Number(5))
        result = ctx.evaluate(expr)
        assert result.tag == TRUE
    
    def test_greater_than(self):
        ctx = EvalContext()
        expr = BinaryOp(">", Number(5), Number(3))
        result = ctx.evaluate(expr)
        assert result.tag == TRUE


class TestTypeErrors:
    """Test type error handling."""
    
    def test_arithmetic_type_error(self):
        ctx = EvalContext()
        expr = BinaryOp("+", Number(5), String("hello"))
        result = ctx.evaluate(expr)
        assert result.tag == ctx.fail_type
        assert "number" in result.data["message"].lower()


class TestShortCircuit:
    """Test short-circuit behavior with skip values."""
    
    def test_failure_propagates_left(self):
        """If left operand fails, right is never evaluated."""
        ctx = EvalContext()
        # Divide by zero on left, right should not be evaluated
        expr = BinaryOp("+",
            BinaryOp("/", Number(1), Number(0)),  # Fails
            Number(99)  # Should not evaluate
        )
        result = ctx.evaluate(expr)
        assert result.tag == ctx.fail_type
        assert "zero" in result.data["message"].lower()
    
    def test_failure_propagates_right(self):
        """If right operand fails, result is failure."""
        ctx = EvalContext()
        expr = BinaryOp("+",
            Number(5),
            BinaryOp("/", Number(1), Number(0))  # Fails
        )
        result = ctx.evaluate(expr)
        assert result.tag == ctx.fail_type
    
    def test_nested_failure_propagation(self):
        """Failures propagate through deep nesting."""
        ctx = EvalContext()
        # ((1 + 2) + (fail)) + 5
        expr = BinaryOp("+",
            BinaryOp("+",
                BinaryOp("+", Number(1), Number(2)),  # 3
                BinaryOp("/", Number(1), Number(0))   # Fail!
            ),
            Number(5)
        )
        result = ctx.evaluate(expr)
        assert result.tag == ctx.fail_type


class TestStackless:
    """Test stackless execution mode."""
    
    def test_stackless_simple(self):
        ctx = EvalContext(use_stackless=True)
        expr = BinaryOp("+", Number(2), Number(3))
        result = ctx.evaluate(expr)
        assert result.data == 5
    
    def test_stackless_nested(self):
        ctx = EvalContext(use_stackless=True)
        expr = BinaryOp("*", 
            BinaryOp("+", Number(2), Number(3)),
            Number(4)
        )
        result = ctx.evaluate(expr)
        assert result.data == 20
    
    def test_stackless_failure_propagation(self):
        ctx = EvalContext(use_stackless=True)
        expr = BinaryOp("+",
            Number(5),
            BinaryOp("/", Number(1), Number(0))
        )
        result = ctx.evaluate(expr)
        assert result.tag == ctx.fail_type
    
    def test_deep_recursion_stackless(self):
        """Build a very deep expression tree to test stackless depth."""
        ctx = EvalContext(use_stackless=True)
        
        # Build: 1 + 1 + 1 + ... + 1 (100 times)
        expr = Number(1)
        for _ in range(99):
            expr = BinaryOp("+", expr, Number(1))
        
        result = ctx.evaluate(expr)
        assert result.data == 100


class TestRecursiveVsStackless:
    """Compare recursive and stackless execution."""
    
    def test_both_produce_same_result(self):
        expr = BinaryOp("*",
            BinaryOp("+", Number(2), Number(3)),
            BinaryOp("-", Number(10), Number(2))
        )
        
        ctx_recursive = EvalContext(use_stackless=False)
        result_recursive = ctx_recursive.evaluate(expr)
        
        ctx_stackless = EvalContext(use_stackless=True)
        result_stackless = ctx_stackless.evaluate(expr)
        
        assert result_recursive.data == result_stackless.data
        assert result_recursive.data == 40  # (2+3) * (10-2) = 5 * 8


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
