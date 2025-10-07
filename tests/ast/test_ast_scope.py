"""
Test cases for scope reference parsing - Phase 01-08.

SPECIFICATION:
- Scope references: $ctx, $mod, $in, $out, $arg, ^, @
- Field access on scopes: $ctx.field, @local.value
- Scope references work in expressions and assignments

PARSER EXPECTATIONS:
- comp.parse_expr("$ctx") → Identifier with scope field
- comp.parse_expr("$ctx.session") → Identifier with scope and token fields
- comp.parse_expr("^timeout") → Identifier with scope field
- Scopes can be used anywhere identifiers can appear

AST NODES: Identifier with ScopeField, TokenField

NOTE: Scopes are implemented as special Identifier fields, not separate node types.
"""

import comp
import asttest


@asttest.params(
    "code",
    # Simple scope references
    ctx=("$ctx",),
    mod=("$mod",),
    in_=("$in",),
    out=("$out",),
    arg=("$arg",),
    caret=("^",),
    at=("@",),

    # Scope with single field
    ctx_field=("$ctx.session",),
    mod_field=("$mod.config",),
    in_field=("$in.data",),
    out_field=("$out.result",),
    arg_field=("$arg.value",),
    caret_field=("^timeout",),
    at_field=("@counter",),

    # Scope with multiple fields
    ctx_deep=("$ctx.database.connection",),
    mod_deep=("$mod.config.port",),
    at_deep=("@cache.user.id",),

    # Scopes in expressions
    scope_binary=("$ctx + ^timeout",),
    scope_comparison=("$in.value == @expected",),
    scope_in_struct=("{x = $ctx.session}",),

    # Scopes in assignments
    assign_to_scope=("{$ctx.session = token}",),
    assign_from_scope=("{result = $in.data}",),
)
def test_valid_scope_references(key, code):
    """Test that valid scope syntax parses and round-trips correctly."""
    result = comp.parse_expr(code)
    assert result is not None
    asttest.roundtrip(result)


@asttest.params(
    "code",
    # Nested scopes (not allowed)
    nested1=("$ctx.$mod",),
    nested2=("one.$ctx",),
    mixed1=("@^one",),
    mixed2=("@^",),
    mixed3=("^$out",),
)
def test_invalid_scope_syntax(key, code):
    """Test that invalid scope syntax fails to parse."""
    asttest.invalid_parse(code, match=r"unexpected token")


def test_scope_unparse_matches():
    """Test that scope references unparse identically to input."""
    cases = [
        "$ctx",
        "$mod",
        "$in.data",
        "$out.result",
        "$arg.value",
        "^timeout",
        "@counter",
        "$ctx.database.connection",
    ]

    for code in cases:
        result = comp.parse_expr(code)
        unparsed = result.kids[0].unparse() if result.kids else result.unparse()
        # Scopes should unparse identically
        assert unparsed == code, f"Expected '{code}', got '{unparsed}'"


def test_scope_in_binary_operations():
    """Test scopes work correctly in binary operations."""
    result = comp.parse_expr("$ctx + $mod")
    assert isinstance(result, comp.ast.Root)
    assert len(result.kids) == 1

    binary = result.kids[0]
    assert isinstance(binary, comp.ast.BinaryOp)

    # Both operands should be identifiers with scope fields
    assert isinstance(binary.kids[0], comp.ast.Identifier)
    assert isinstance(binary.kids[1], comp.ast.Identifier)

    asttest.roundtrip(result)


def test_scope_in_structures():
    """Test scopes work in structure assignments."""
    result = comp.parse_expr("{result = $in.data}")
    assert isinstance(result, comp.ast.Root)
    struct = result.kids[0]
    assert isinstance(struct, comp.ast.Structure)

    asttest.roundtrip(result)


if __name__ == "__main__":
    # Run basic smoke tests
    print("Testing scope references...")
    test_valid_scope_references("ctx", "$ctx")
    test_valid_scope_references("ctx_field", "$ctx.session")
    test_scope_unparse_matches()
    test_scope_in_binary_operations()
    print("All smoke tests passed!")


