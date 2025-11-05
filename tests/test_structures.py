"""Test structure literal evaluation."""

import comp
import comptest


def test_empty_structure():
    """Test empty structure literal {}."""
    expr = comp.ast.Structure([])
    result = comptest.run_ast(expr)
    comptest.assert_value(result, {})


def test_single_named_field():
    """Test {x = 5}."""
    expr = comp.ast.Structure([
        comp.ast.FieldOp(
            value=comp.ast.Number(5),
            key=comp.ast.String("x")
        )
    ])
    result = comptest.run_ast(expr)
    comptest.assert_value(result, 5)


def test_multiple_named_fields():
    """Test {x = 5, y = 10, z = 15}."""
    expr = comp.ast.Structure([
        comp.ast.FieldOp(comp.ast.Number(5), key=comp.ast.String("x")),
        comp.ast.FieldOp(comp.ast.Number(10), key=comp.ast.String("y")),
        comp.ast.FieldOp(comp.ast.Number(15), key=comp.ast.String("z")),
    ])
    result = comptest.run_ast(expr)
    comptest.assert_value(result, x=5, y=10, z=15)


def test_unnamed_fields():
    """Test {1 2 3} - unnamed fields."""
    expr = comp.ast.Structure([
        comp.ast.FieldOp(comp.ast.Number(1)),
        comp.ast.FieldOp(comp.ast.Number(3)),
        comp.ast.FieldOp(comp.ast.Number(2)),
    ])
    result = comptest.run_ast(expr)
    values = comptest.assert_value(result)
    # Check if to_python() returns list (for unnamed fields) or dict
    py_value = result.to_python()
    if isinstance(py_value, list):
        assert py_value == [1, 3, 2]
    else:
        assert list(py_value.values()) == [1, 3, 2]


def test_mixed_fields():
    """Test {x=5 10 y=15} - mix of named and unnamed."""
    expr = comp.ast.Structure([
        comp.ast.FieldOp(comp.ast.Number(5), key=comp.ast.String("x")),
        comp.ast.FieldOp(comp.ast.Number(10)),
        comp.ast.FieldOp(comp.ast.Number(15), key=comp.ast.String("y")),
    ])
    result = comptest.run_ast(expr)
    values = comptest.assert_value(result, x=5, y=15)
    assert list(values.values()) == [5, 10, 15]


def test_spread_operator():
    """Test {..$var y=3} - spreading another struct."""
    # {..$var y=3} to override y (using scope field)
    expr = comp.ast.Structure([
        comp.ast.SpreadOp(comp.ast.Identifier([comp.ast.ScopeField("var")])),  # $var scope
        comp.ast.FieldOp(comp.ast.Number(3), key=comp.ast.String("y")),
    ])
    result = comptest.run_ast(expr, var={"x": 1, "y": 2})
    comptest.assert_value(result, x=1, y=3)


def test_deep_assignment_three_levels():
    """Test {one.two.three = 5} creates three-level nesting."""
    expr = comp.ast.Structure([
        comp.ast.FieldOp(
            comp.ast.Number(5),
            key=[comp.ast.TokenField("one"), comp.ast.TokenField("two"), comp.ast.TokenField("three")]
        )
    ])
    result = comptest.run_ast(expr)
    comptest.assert_value(result, {"one": {"two": {"three": 5}}})


def test_deep_assignment_multiple_paths():
    """Test {one.two=1 one.three=2} builds tree."""
    expr = comp.ast.Structure([
        comp.ast.FieldOp(comp.ast.Number(1), key=[comp.ast.TokenField("one"), comp.ast.TokenField("two")]),
        comp.ast.FieldOp(comp.ast.Number(2), key=[comp.ast.TokenField("one"), comp.ast.TokenField("three")]),
    ])
    result = comptest.run_ast(expr)
    comptest.assert_value(result, {"one": {"two": 1, "three": 2}})


# def test_deep_assignment_mixed_with_simple():
#     """Test {x=1 one.two=2 y=3} mixes simple and deep."""
#     expr = comp.ast.Structure([
#         comp.ast.FieldOp(comp.ast.Number(1), key=comp.ast.TokenField("x")),
#         comp.ast.FieldOp(comp.ast.Number(2), key=[comp.ast.TokenField("one"), comp.ast.TokenField("two")]),
#         comp.ast.FieldOp(comp.ast.Number(3), key=comp.ast.TokenField("y")),
#     ])
#     result = comptest.run_ast(expr)
#     comptest.assert_value(result, {"x": 1, "y": 3, "one": {"two": 2}})


# def test_deep_assignment_with_index():
#     """Test {one=1 two=2 #1.nested=99} - IndexField in path."""
#     expr = comp.ast.Structure([
#         comp.ast.FieldOp(comp.ast.Number(1), key=comp.ast.TokenField("one")),
#         comp.ast.FieldOp(comp.ast.Number(2), key=comp.ast.TokenField("two")),
#         # Use IndexField to refer to second field (two), add nested to it
#         comp.ast.FieldOp(comp.ast.Number(99), key=[comp.ast.IndexField(1), comp.ast.TokenField("nested")]),
#     ])
#     result = comptest.run_ast(expr)
#     comptest.assert_value(result, {"one": 1, "two": {"nested": 99}})


# def test_deep_assignment_overwrite_simple():
#     """Test {one=1 one.two=2} - deep overwrites simple value."""
#     expr = comp.ast.Structure([
#         comp.ast.FieldOp(comp.ast.Number(1), key=comp.ast.TokenField("one")),
#         comp.ast.FieldOp(comp.ast.Number(2), key=[comp.ast.TokenField("one"), comp.ast.TokenField("two")]),
#     ])
#     result = comptest.run_ast(expr)
#     comptest.assert_value(result, {"one": {"two": 2}})


def test_deep_assignment_with_compute():
    """Test {x.'1+1' = 99} - comp.ComputeField in path."""
    expr = comp.ast.Structure([
        comp.ast.FieldOp(
            comp.ast.Number(99),
            key=[
                comp.ast.TokenField("x"),
                comp.ast.ComputeField(comp.ast.ArithmeticOp("+", comp.ast.Number(1), comp.ast.Number(1)))
            ]
        )
    ])
    result = comptest.run_ast(expr)
    comptest.assert_value(result, {"x": {2: 99}})


