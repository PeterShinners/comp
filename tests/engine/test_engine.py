"""Test the new Engine class with AST nodes."""

import comp.engine as comp


def test_simple_literal():
    """Test evaluating simple literals."""
    engine = comp.Engine()

    result = engine.run(comp.ast.Number(42))
    assert result == comp.Value(42)


def test_arithmetic():
    """Test arithmetic operations."""
    engine = comp.Engine()

    # 1 + 2
    expr = comp.ast.ArithmeticOp("+", comp.ast.Number(1), comp.ast.Number(2))
    result = engine.run(expr)
    assert result == comp.Value(3)

    # (5 * 3) - 10
    expr = comp.ast.ArithmeticOp("-",
        comp.ast.ArithmeticOp("*", comp.ast.Number(5), comp.ast.Number(3)),
        comp.ast.Number(10)
    )
    result = engine.run(expr)
    assert result == comp.Value(5)


def test_scope_access():
    """Test accessing scopes."""
    engine = comp.Engine()

    # Set up a local scope with a value
    local_scope = comp.Value({comp.Value('x'): comp.Value(42)})

    # @ (just get the scope)
    expr = comp.ast.Identifier([comp.ast.ScopeField('@')])
    result = engine.run(expr, local=local_scope)
    assert result == local_scope


def test_field_access():
    """Test field navigation."""
    engine = comp.Engine()

    # Set up scope with nested structure
    local_scope = comp.Value({
        comp.Value('user'): comp.Value({
            comp.Value('name'): comp.Value('Alice')
        })
    })

    # @.user.name
    expr = comp.ast.Identifier([
        comp.ast.ScopeField('@'),
        comp.ast.TokenField('user'),
        comp.ast.TokenField('name')
    ])
    result = engine.run(expr, local=local_scope)
    assert result == comp.Value('Alice')


def test_complex_expression():
    """Test complex nested expression."""
    engine = comp.Engine()

    # Set up scope
    local_scope = comp.Value({
        comp.Value('x'): comp.Value(10),
        comp.Value('y'): comp.Value(20)
    })

    # (@.x + @.y) * 2
    expr = comp.ast.ArithmeticOp("*",
        comp.ast.ArithmeticOp("+",
            comp.ast.Identifier([comp.ast.ScopeField('@'), comp.ast.TokenField('x')]),
            comp.ast.Identifier([comp.ast.ScopeField('@'), comp.ast.TokenField('y')])
        ),
        comp.ast.Number(2)
    )

    result = engine.run(expr, local=local_scope)
    assert result == comp.Value(60)


