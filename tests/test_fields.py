"""Tests for computed index field access."""

import comp
import comptest


def test_literal_index_access():
    """Test data.#1 - literal positional index"""
    value = comptest.run_func("""
    !func |test ~{} = {
        $var.data = {10 20 30}
        result = $var.data.#1
    }
    """)
    comptest.assert_value(value, result=20)


def test_computed_index_from_variable():
    """Test data.#($var.index) - computed index from variable"""
    value = comptest.run_func("""
    !func |test ~{} = {
        $var.index = 1
        $var.data = {10 20 30 40 50}
        result = $var.data.#($var.index + 1)
    }
    """)
    comptest.assert_value(value, result=30)


def test_computed_index_out_of_bounds():
    """Test that out of bounds computed index fails gracefully"""
    value = comptest.run_func("""
    !func |test ~{} = {
        $var.index = 1
        $var.data = {10 20 30}
        result = $var.data.#($var.index + 10)
    }
    """)
    comptest.assert_fail(value, "bounds")


def test_computed_index_non_numeric():
    """Test that non-numeric computed index fails gracefully"""
    value = comptest.run_func("""
    !func |test ~{} = {
        $var.index = "not-a-number"
        $var.data = {10 20 30}
        result = $var.data.#($var.index)
    }
    """)
    comptest.assert_fail(value, "number")


def test_scope_access():
    """Test accessing scopes."""
    expr = comp.ast.Identifier([comp.ast.ScopeField('var')])
    value = comptest.run_ast(expr, var={'x': 42})
    comptest.assert_value(value, x=42)


def test_field_access():
    """Test field navigation."""
    data = {"user": {"name": "Alice"}}

    expr = comp.ast.Identifier([
        comp.ast.ScopeField('var'),
        comp.ast.TokenField('user'),
        comp.ast.TokenField('name')
    ])
    value = comptest.run_ast(expr, var=data)
    comptest.assert_value(value, "Alice")

    expr.fields.pop()
    value = comptest.run_ast(expr, var=data)
    comptest.assert_value(value, name="Alice")

    expr.fields.pop()
    print("FINALFIELDS:", expr.fields)
    value = comptest.run_ast(expr, var=data)
    comptest.assert_value(value, data)


def test_complex_expression():
    """Test complex nested expression."""
    # ($var.x + $var.y) * 2
    expr = comp.ast.ArithmeticOp("*",
        comp.ast.ArithmeticOp("+",
            comp.ast.Identifier([comp.ast.ScopeField('var'), comp.ast.TokenField('x')]),
            comp.ast.Identifier([comp.ast.ScopeField('var'), comp.ast.TokenField('y')])
        ),
        comp.ast.Number(2)
    )

    value = comptest.run_ast(expr, var={'x': 10, 'y': 20})
    comptest.assert_value(value, 60)


