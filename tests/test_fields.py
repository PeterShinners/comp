"""Tests for computed index field access."""

import comp
import comptest


## First four tests migrated to ct_fields.comp using assert-/fail- prefixed functions


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


