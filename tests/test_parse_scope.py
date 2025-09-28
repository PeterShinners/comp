"""
Test cases for scope reference and assignment parsing - Phase 01-08.

SPECIFICATION:
- Scope references: $ctx, $mod, $in, $out, $arg, ^, @ with field paths
- Special syntax: ^timeout (no dot), @local (no dot), $ctx.field (dot required)
- Assignment operators: =, =*, =? for scope assignments
- Deep field paths: $ctx.database.connection.pool-size (unlimited nesting)
- Mixed assignments: {$ctx.session = token, result.field = value, @temp = data}

PARSER EXPECTATIONS (Updated for flattened structure):
- comp.parse("$ctx") → ScopeReference(ScopeToken("$", "ctx"))
- comp.parse("$ctx.session") → ScopeReference(ScopeToken("$", "ctx"), Identifier("session"))
- comp.parse("^timeout") → ScopeReference(ScopeToken("^", None), Identifier("timeout"))
- comp.parse("@counter") → ScopeReference(ScopeToken("@", None), Identifier("counter"))
- comp.parse("$mod.two.three") → ScopeReference(ScopeToken("$", "mod"), Identifier("two"), Identifier("three"))
- comp.parse("{$ctx.session = token}") → StructureLiteral([ScopeAssignment(...)])

AST NODES: ScopeReference(scope_token, *field_identifiers),
           ScopeToken(scope_type, scope_name),
           ScopeTarget(scope_type, scope_name, field_path),
           ScopeAssignment(target, operator, value)

NOTE: This phase implements the foundation of Comp's explicit scoping system.
All scopes use explicit prefixes and have well-defined behavior for field lookup.
The flattened structure matches FieldAccessOperation for consistency.
"""

import pytest

import comp


@pytest.mark.parametrize("field,scope,field_count", [
    ("$ctx", "$ctx", 0),
    ("$mod", "$mod", 0),

    ("$in.child", "$in", 1),
    ("$out.#12", "$out", 1),
    ("$arg.'4+4'", "$arg", 1),

    ("@", "@", 0),
    ("@local-counter", "@", 1),
    ("^", "^", 0),
    ("^craft", "^", 1),
    ("^#4", "^", 1),
])
def test_valid_scopes(field, scope, field_count):
    """Test parsing of standalone scopes"""
    result = comp.parse(field)
    assert isinstance(result, comp.FieldAccessOperation)
    assert isinstance(result.object, comp.Scope)
    assert result.object.value == scope
    assert len(result.fields) == field_count


@pytest.mark.parametrize("field", [
    "$ctx.$mod",  # nested scope
    "one.$ctx",  # nested scope
    "$cat.dog",  # unknown scope
])
def test_invalid_scopes(field):
    """Test parsing of invalid standalong scopes"""
    with pytest.raises(comp.ParseError):
        comp.parse(field)


@pytest.mark.parametrize("field,left,right", [
    ("$ctx + ^two", "$ctx", "^"),
    ("$mod.#5 * @local", "$mod", "@"),
])
def test_binary_parsing(field, left, right):
    """Check operator precedence with simple expressions"""
    result = comp.parse(field)
    assert isinstance(result, comp.BinaryOperation)
    assert isinstance(result.left, comp.FieldAccessOperation)
    assert isinstance(result.right, comp.FieldAccessOperation)
    assert isinstance(result.left.object, comp.Scope)
    assert isinstance(result.right.object, comp.Scope)
    assert result.left.object.value == left
    assert result.right.object.value == right

