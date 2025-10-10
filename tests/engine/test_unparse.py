"""Test unparse() methods on new AST nodes."""

from src.comp.engine.ast import (
    Number, String,
    ArithmeticOp, ComparisonOp, BooleanOp, UnaryOp,
    Identifier, ScopeField, TokenField, IndexField, ComputeField,
)


def test_literals():
    """Test unparsing literal values."""
    assert Number(42).unparse() == "42"
    assert Number(3.14).unparse() == "3.14"
    assert String("hello").unparse() == '"hello"'
    assert String('say "hi"').unparse() == '"say \\"hi\\""'
    print("✓ Literals unparse correctly")


def test_operators():
    """Test unparsing operators."""
    # Arithmetic
    expr = ArithmeticOp("+", Number(1), Number(2))
    assert expr.unparse() == "(1 + 2)"
    
    # Comparison
    expr = ComparisonOp("==", Number(5), Number(5))
    assert expr.unparse() == "(5 == 5)"
    
    # Boolean
    expr = BooleanOp("&&", Number(1), Number(2))
    assert expr.unparse() == "(1 && 2)"
    
    # Unary
    expr = UnaryOp("-", Number(42))
    assert expr.unparse() == "-42"
    
    # Nested
    expr = ArithmeticOp("*", 
        ArithmeticOp("+", Number(1), Number(2)),
        Number(3)
    )
    assert expr.unparse() == "((1 + 2) * 3)"
    
    print("✓ Operators unparse correctly")


def test_identifiers():
    """Test unparsing identifiers and fields."""
    # Simple scope reference
    ident = Identifier([ScopeField("@")])
    assert ident.unparse() == "@"
    
    # Scope with field
    ident = Identifier([ScopeField("@"), TokenField("user")])
    assert ident.unparse() == "@.user"
    
    # Multiple fields
    ident = Identifier([
        ScopeField("@"),
        TokenField("user"),
        TokenField("account"),
        TokenField("name")
    ])
    assert ident.unparse() == "@.user.account.name"
    
    # Index field
    ident = Identifier([ScopeField("$in"), IndexField(0)])
    assert ident.unparse() == "$in#0"
    
    # Computed field
    ident = Identifier([
        ScopeField("@"),
        ComputeField(String("key"))
    ])
    assert ident.unparse() == '@.["key"]'
    
    print("✓ Identifiers unparse correctly")


def test_complex():
    """Test unparsing complex nested expressions."""
    # ((@.x + @.y) * 2)
    expr = ArithmeticOp("*",
        ArithmeticOp("+",
            Identifier([ScopeField("@"), TokenField("x")]),
            Identifier([ScopeField("@"), TokenField("y")])
        ),
        Number(2)
    )
    assert expr.unparse() == "((@.x + @.y) * 2)"
    
    print("✓ Complex expressions unparse correctly")


if __name__ == "__main__":
    test_literals()
    test_operators()
    test_identifiers()
    test_complex()
    print("\n✅ All unparse tests passed!")
