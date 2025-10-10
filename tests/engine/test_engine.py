"""Test the new Engine class with AST nodes."""

from comp.engine.engine import Engine
from comp.engine.ast import (
    ArithmeticOp,
    Identifier,
    Number,
    ScopeField,
    TokenField,
)
from comp.engine.value import Value


def test_simple_literal():
    """Test evaluating simple literals."""
    engine = Engine()

    result = engine.run(Number(42))
    assert result == Value(42)
    print("✓ Simple literal works")


def test_arithmetic():
    """Test arithmetic operations."""
    engine = Engine()

    # 1 + 2
    expr = ArithmeticOp("+", Number(1), Number(2))
    result = engine.run(expr)
    assert result == Value(3)

    # (5 * 3) - 10
    expr = ArithmeticOp("-",
        ArithmeticOp("*", Number(5), Number(3)),
        Number(10)
    )
    result = engine.run(expr)
    assert result == Value(5)

    print("✓ Arithmetic operations work")


def test_scope_access():
    """Test accessing scopes."""
    engine = Engine()

    # Set up a local scope with a value
    engine.set_scope('local', Value({Value('x'): Value(42)}))

    # @ (just get the scope)
    expr = Identifier([ScopeField('@')])
    result = engine.run(expr)
    assert result == engine.get_scope('local')

    print("✓ Scope access works")


def test_field_access():
    """Test field navigation."""
    engine = Engine()

    # Set up scope with nested structure
    engine.set_scope('local', Value({
        Value('user'): Value({
            Value('name'): Value('Alice')
        })
    }))

    # @.user.name
    expr = Identifier([
        ScopeField('@'),
        TokenField('user'),
        TokenField('name')
    ])
    result = engine.run(expr)
    assert result == Value('Alice')

    print("✓ Field navigation works")


def test_scope_frame():
    """Test scope frames for lexical scoping."""
    engine = Engine()

    # Set up initial scope
    engine.set_scope('local', Value({Value('z'): Value(0)}))
    initial_local = engine.get_scope('local')

    # Create a new local scope
    new_local = Value({Value('x'): Value(10)})

    with engine.scope_frame(local=new_local):
        # Should see new local
        assert engine.get_scope('local') == new_local

        # Nested frame
        nested_local = Value({Value('y'): Value(20)})
        with engine.scope_frame(local=nested_local):
            assert engine.get_scope('local') == nested_local

        # Back to outer frame
        assert engine.get_scope('local') == new_local

    # Back to original scope
    assert engine.get_scope('local') == initial_local

    print("✓ Scope frames work")


def test_set_scope_field():
    """Test mutating scope fields."""
    engine = Engine()

    # Start with empty local
    engine.set_scope('local', Value({}))

    # Set a field
    engine.set_scope_field('local', 'x', Value(42))

    # Verify it was set
    local = engine.get_scope('local')
    assert local.struct[Value('x')] == Value(42)

    # Update the field
    engine.set_scope_field('local', 'x', Value(100))
    assert local.struct[Value('x')] == Value(100)

    print("✓ Scope field mutation works")


def test_complex_expression():
    """Test complex nested expression."""
    engine = Engine()

    # Set up scope
    engine.set_scope('local', Value({
        Value('x'): Value(10),
        Value('y'): Value(20)
    }))

    # (@.x + @.y) * 2
    expr = ArithmeticOp("*",
        ArithmeticOp("+",
            Identifier([ScopeField('@'), TokenField('x')]),
            Identifier([ScopeField('@'), TokenField('y')])
        ),
        Number(2)
    )

    result = engine.run(expr)
    assert result == Value(60)

    print("✓ Complex expressions work")


def test_no_default_scopes():
    """Test that scopes must be explicitly set up."""
    engine = Engine()

    # Engine starts with no scopes
    assert engine.scopes == {}

    # Trying to access undefined scope fails at runtime
    expr = Identifier([ScopeField('$mod')])
    result = engine.run(expr)
    # Should get an error (fail value)
    assert 'not defined' in str(result.data).lower() or result.tag == engine.fail_type

    print("✓ No default scopes (errors appropriately)")


if __name__ == "__main__":
    test_simple_literal()
    test_arithmetic()
    test_scope_access()
    test_field_access()
    test_scope_frame()
    test_set_scope_field()
    test_complex_expression()
    test_no_default_scopes()
    print("\n✅ All Engine tests passed!")
