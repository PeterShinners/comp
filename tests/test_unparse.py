"""Test unparse() methods on new AST nodes."""

import comp


def test_literals():
    """Test unparsing literal values."""
    assert comp.ast.Number(42).unparse() == "42"
    assert comp.ast.Number(3.14).unparse() == "3.14"
    assert comp.ast.String("hello").unparse() == '"hello"'
    assert comp.ast.String('say "hi"').unparse() == '"say \\"hi\\""'


def test_operators():
    """Test unparsing operators."""
    # Arithmetic
    expr = comp.ast.ArithmeticOp("+", comp.ast.Number(1), comp.ast.Number(2))
    assert expr.unparse() == "(1 + 2)"

    # Comparison
    expr = comp.ast.ComparisonOp("==", comp.ast.Number(5), comp.ast.Number(5))
    assert expr.unparse() == "(5 == 5)"

    # Boolean
    expr = comp.ast.BooleanOp("&&", comp.ast.Number(1), comp.ast.Number(2))
    assert expr.unparse() == "(1 && 2)"

    # Unary
    expr = comp.ast.UnaryOp("-", comp.ast.Number(42))
    assert expr.unparse() == "-42"

    # Nested
    expr = comp.ast.ArithmeticOp("*",
        comp.ast.ArithmeticOp("+", comp.ast.Number(1), comp.ast.Number(2)),
        comp.ast.Number(3)
    )
    assert expr.unparse() == "((1 + 2) * 3)"


def test_identifiers():
    """Test unparsing identifiers and fields."""
    # Simple scope reference
    ident = comp.ast.Identifier([comp.ast.ScopeField("@")])
    assert ident.unparse() == "@"

    # Scope with field
    ident = comp.ast.Identifier([comp.ast.ScopeField("@"), comp.ast.TokenField("user")])
    assert ident.unparse() == "@.user"

    # Multiple fields
    ident = comp.ast.Identifier([
        comp.ast.ScopeField("@"),
        comp.ast.TokenField("user"),
        comp.ast.TokenField("account"),
        comp.ast.TokenField("name")
    ])
    assert ident.unparse() == "@.user.account.name"

    # Index field
    ident = comp.ast.Identifier([comp.ast.ScopeField("$in"), comp.ast.IndexField(0)])
    assert ident.unparse() == "$in#0"

    # Computed field
    ident = comp.ast.Identifier([
        comp.ast.ScopeField("@"),
        comp.ast.ComputeField(comp.ast.String("key"))
    ])
    assert ident.unparse() == '@.["key"]'


def test_complex():
    """Test unparsing complex nested expressions."""
    # ((@.x + @.y) * 2)
    expr = comp.ast.ArithmeticOp("*",
        comp.ast.ArithmeticOp("+",
            comp.ast.Identifier([comp.ast.ScopeField("@"), comp.ast.TokenField("x")]),
            comp.ast.Identifier([comp.ast.ScopeField("@"), comp.ast.TokenField("y")])
        ),
        comp.ast.Number(2)
    )
    assert expr.unparse() == "((@.x + @.y) * 2)"

