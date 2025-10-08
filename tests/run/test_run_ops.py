"""Test assignment operations"""

import decimal

import pytest
import runtest

import comp


@runtest.params(
    "expr, result",
    add=('4+4', 8),
    mul=('4*4', 16),
    sub=('1-4', -3),
    pow=('2**8', 256),
    div0=('10/0', None),
    str1=('"cat"*2', None),
    str2=('"5-"pig', None),  # Parse error - invalid syntax
    str3=('"cat"+"pig"', "catpig"),  # Temporarily works until string formatting is implemented
    div=('0/12', 0),
    bool=('#true+2', None),
    bool2=('#true-#false', None),  # Parse error - grammar limitation
)
def test_binary_math(key, expr, result, module, scopes):
    """Various assignment operations."""
    # Try to parse the expression
    try:
        ast = comp.parse_expr(expr)
    except comp.ParseError:
        # If parsing fails and we expect failure (result is None), that's OK
        if result is None:
            return  # Test passes - parse error was expected
        else:
            raise  # Test should fail - unexpected parse error
    
    ast = ast.find(comp.ast.BinaryOp)

    func = comp.run._eval.evaluate
    if result is None:
        # Parse succeeded but we expect runtime error
        val = comp.run._ops.evaluate_binary_op(ast, module, scopes, func)
        runtest.assert_fails(val)
    else:
        value = comp.run._ops.evaluate_binary_op(ast, module, scopes, func)
        expected = comp.run.Value(result)
        assert value == expected


@runtest.params(
    "expr, result",
    add=('+4', 4),
    mul=('-4', -4),
    sub=('*4', None),  # Parse error
    pow=('/4', None),  # Parse error
    str=('+"cat"', None),  # Unary + on non-number should error
    bool=('-#true', None),  # Unary - on non-number should error
)
def test_unary_math(key, expr, result, module, scopes):
    """Various assignment operations."""

    # Try to parse the expression
    try:
        ast = comp.parse_expr(expr)
    except comp.ParseError:
        # If parsing fails and we expect failure (result is None), that's OK
        if result is None:
            return  # Test passes - parse error was expected
        else:
            raise  # Test should fail - unexpected parse error
    
    ast = ast.find(comp.ast.UnaryOp)

    func = comp.run._eval.evaluate
    if result is None:
        # Parse succeeded but we expect runtime error
        val = comp.run._ops.evaluate_unary_op(ast, module, scopes, func)
        runtest.assert_fails(val)
    else:
        value = comp.run._ops.evaluate_unary_op(ast, module, scopes, func)
        expected = comp.run.Value(result)
        assert value == expected


@runtest.params(
    "expr, result",
    and1=('#true&&#true', True),
    and2=('#false&&#false', False),
    and3=('#false&&#true', False),
    and4=('#true&&#false', False),
    or1=('#true||#true', True),
    or2=('#false||#false', False),
    or3=('#false||#true', True),
    or4=('#true||#false', True),
    bad1=('1||0', None),  # Left operand fails - always checked
    bad2=('#true||2', True),  # Short-circuit: right not evaluated, returns #true
    bad2b=('#false||2', None),  # Right evaluated: type error
    bad3=('"cat"&&#false', None),  # Left operand fails - always checked
    bad4=('#false&&2', False),  # Short-circuit: right not evaluated, returns #false
    bad4b=('#true&&2', None),  # Right evaluated: type error
)
def test_binary_boolean(key, expr, result, module, scopes):
    """Various assignment operations."""
    ast = comp.parse_expr(expr)
    ast = ast.find(comp.ast.BinaryOp)

    func = comp.run._eval.evaluate
    if result is None:
        val = comp.run._ops.evaluate_binary_op(ast, module, scopes, func)
        runtest.assert_fails(val)
    else:
        value = comp.run._ops.evaluate_binary_op(ast, module, scopes, func)
        expected = comp.run.Value(result)
        assert value == expected


@runtest.params(
    "expr, result",
    untrue=('!!#true', False),
    unfalse=('!!#false', True),
    unzero=('!!0', None),
    unstr=('!!"cat"', None),
)
def test_unary_boolean(key, expr, result, module, scopes):
    """Various assignment operations."""
    ast = comp.parse_expr(expr)
    ast = ast.find(comp.ast.UnaryOp)

    func = comp.run._eval.evaluate
    if result is None:
        val = comp.run._ops.evaluate_unary_op(ast, module, scopes, func)
        runtest.assert_fails(val)
    else:
        value = comp.run._ops.evaluate_unary_op(ast, module, scopes, func)
        expected = comp.run.Value(result)
        assert value == expected


@runtest.params(
    "expr, result",
    booleq=('#true==#true', True),
    boolne=('#false!=#true', True),
    inteq=('100==100', True),
    intne=('1.5!=1.4', True),
    streq=('"cat"!="cat "', True),
    strne=('"cat"=="Cat"', False),
    mixeq=('1=="cat"', None),  # Different types: error
    mixne=('2==#true', None),  # Different types: error
)
def test_binary_equality(key, expr, result, module, scopes):
    """Various assignment operations."""
    ast = comp.parse_expr(expr)
    ast = ast.find(comp.ast.BinaryOp)

    func = comp.run._eval.evaluate
    if result is None:
        val = comp.run._ops.evaluate_binary_op(ast, module, scopes, func)
        runtest.assert_fails(val)
    else:
        value = comp.run._ops.evaluate_binary_op(ast, module, scopes, func)
        expected = comp.run.Value(result)
        assert value == expected


@runtest.params(
    "expr, result",
    boollt=('#true<#true', False),
    boollt2=('#false<#true', True),
    intlt=('100<100', False),
    intlt2=('1.5<1.4', False),
    intle=('100<=100', True),
    intle2=('1.5<=1.4', False),
    strlt=('"cat"<"dog "', True),
    strle=('"cat"<="Cat"', False),
    mixlt=('1<"cat"', True),
    mixle=('2<=#true', False),
)
def test_binary_sort(key, expr, result, module, scopes):
    """Various assignment operations."""
    ast = comp.parse_expr(expr)
    ast = ast.find(comp.ast.BinaryOp)

    func = comp.run._eval.evaluate
    if result is None:
        val = comp.run._ops.evaluate_binary_op(ast, module, scopes, func)
        runtest.assert_fails(val)
    else:
        value = comp.run._ops.evaluate_binary_op(ast, module, scopes, func)
        expected = comp.run.Value(result)
        assert value == expected


@runtest.params(
    "expr, result",
    mix1=('1 + 2 * 3 - 4', 3),
    mix2=('(1 + 2) * 3 < 3 + 4', False),
    una1=('4--4*+2', 12),
)
def test_precedence(key, expr, result, module, scopes):
    """Various assignment operations."""
    ast = comp.parse_expr(expr)
    ops = ast.kids[0]

    if result is None:
        val = comp.run.evaluate(ops, module, scopes)
        runtest.assert_fails(val)
    else:
        value = comp.run.evaluate(ops, module, scopes)
        expected = comp.run.Value(result)
        assert value == expected



@runtest.params(
    "expr, result",
    and1=('#false&&(0/0)', False),
    and2=('#true&&(0/0)', None),
    or1=('#true||(0/0)', True),
    or2=('#false||(0/0)', None),
)
def test_short_circuit(key, expr, result, module, scopes):
    """Various assignment operations."""
    ast = comp.parse_expr(expr)
    ast = ast.find(comp.ast.BinaryOp)

    func = comp.run._eval.evaluate
    if result is None:
        val = comp.run._ops.evaluate_binary_op(ast, module, scopes, func)
        runtest.assert_fails(val)
    else:
        value = comp.run._ops.evaluate_binary_op(ast, module, scopes, func)
        expected = comp.run.Value(result)
        assert value == expected


@runtest.params(
    "code, expr, result",
    # Tag identity equality - same tag compares equal
    same=("!tag #red", "#red == #red", True),
    different=("!tag #red\n!tag #blue", "#red == #blue", False),
    # Inequality
    not_equal=("!tag #red\n!tag #blue", "#red != #blue", True),
    # Tags with values still compare by identity, not value
    with_value=("!tag #active = 1\n!tag #inactive = 2", "#active != #inactive", True),
    # Partial name matching - unambiguous short names match full hierarchy
    partial_match=("!tag #animal.pet.cat", "#cat == #cat.pet.animal", True),
)
def test_tag_equality(key, code, expr, result, scopes):
    """Test tag equality comparison (== and !=)."""
    module_ast = comp.parse_module(code)
    mod = comp.run.Module("test")
    mod.process_builtins()
    mod.process_ast(module_ast)
    mod.resolve_all()
    
    expr_ast = comp.parse_expr(expr)
    
    value = comp.run.evaluate(expr_ast.kids[0], mod, scopes)
    expected = comp.run.Value(result)
    assert value == expected


@runtest.params(
    "code, expr, result",
    # Lexicographical ordering by leaf name
    simple=("!tag #active\n!tag #inactive", "#active < #inactive", True),
    reverse=("!tag #active\n!tag #inactive", "#inactive < #active", False),
    alpha=("!tag #red\n!tag #green\n!tag #blue", "#blue < #green", True),
    # Hierarchy comparison (leaf first, then walk up)
    # Note: Tag definition #status.error creates "status.error", referenced as #error.status
    siblings=(
        "!tag #status = {#error #warning}",
        "#error.status < #warning.status",
        True
    ),
    # Partial name matching works in comparisons
    partial=(
        "!tag #color.red\n!tag #color.blue",
        "#red < #blue",
        False  # "red" > "blue" lexicographically
    ),
)
def test_tag_ordering(key, code, expr, result, scopes):
    """Test tag lexicographical ordering (< and >)."""
    module_ast = comp.parse_module(code)
    mod = comp.run.Module("test")
    mod.process_builtins()
    mod.process_ast(module_ast)
    mod.resolve_all()
    
    expr_ast = comp.parse_expr(expr)
    
    value = comp.run.evaluate(expr_ast.kids[0], mod, scopes)
    expected = comp.run.Value(result)
    assert value == expected

