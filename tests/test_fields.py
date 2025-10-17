"""Tests for computed index field access."""

import comp
import comptest


def test_literal_index_access():
    """Test data.#1 - literal positional index"""
    value = comptest.run_func("""
    !func |test ~{} = {
        data = {10 20 30}
        result = data.#1
    }
    """)
    comptest.assert_value(value, result=20)


def test_computed_index_from_variable():
    """Test data.#(@index) - computed index from variable"""
    value = comptest.run_func("""
    !func |test ~{} = {
        @index = 1
        data = {10 20 30 40 50}
        result = data.#(@index + 1)
    }
    """)
    comptest.assert_value(value, result=30)


def test_computed_index_out_of_bounds():
    """Test that out of bounds computed index fails gracefully"""
    value = comptest.run_func("""
    !func |test ~{} = {
        @index = 1
        data = {10 20 30}
        result = data.#(@index + 10)
    }
    """)
    comptest.assert_fail(value, "bounds")


def test_computed_index_non_numeric():
    """Test that non-numeric computed index fails gracefully"""
    value = comptest.run_func("""
    !func |test ~{} = {
        @index = "not-a-number"
        data = {10 20 30}
        result = data.#(@index)
    }
    """)
    comptest.assert_fail(value, "number")


def test_scope_access():
    """Test accessing scopes."""
    expr = comp.ast.Identifier([comp.ast.ScopeField('@')])
    value = comptest.run_ast(expr, local={'x': 42})
    comptest.assert_value(value, x=42)


def test_field_access():
    """Test field navigation."""
    data = {"user": {"name": "Alice"}}

    expr = comp.ast.Identifier([
        comp.ast.ScopeField('@'),
        comp.ast.TokenField('user'),
        comp.ast.TokenField('name')
    ])
    value = comptest.run_ast(expr, local=data)
    comptest.assert_value(value, "Alice")

    expr.fields.pop()
    value = comptest.run_ast(expr, local=data)
    comptest.assert_value(value, name="Alice")

    expr.fields.pop()
    print("FINALFIELDS:", expr.fields)
    value = comptest.run_ast(expr, local=data)
    comptest.assert_value(value, data)


def test_complex_expression():
    """Test complex nested expression."""
    # (@x + @y) * 2
    expr = comp.ast.ArithmeticOp("*",
        comp.ast.ArithmeticOp("+",
            comp.ast.Identifier([comp.ast.ScopeField('@'), comp.ast.TokenField('x')]),
            comp.ast.Identifier([comp.ast.ScopeField('@'), comp.ast.TokenField('y')])
        ),
        comp.ast.Number(2)
    )

    value = comptest.run_ast(expr, local={'x': 10, 'y': 20})
    comptest.assert_value(value, 60)


