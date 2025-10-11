"""Test structure literal evaluation."""

import comp.engine as comp


def test_empty_structure():
    """Test empty structure literal {}."""
    engine = comp.Engine()

    expr = comp.ast.Structure([])
    result = engine.run(expr)

    assert result.is_struct
    assert result.struct == {}


def test_single_named_field():
    """Test {x = 5}."""
    engine = comp.Engine()

    expr = comp.ast.Structure([
        comp.ast.FieldOp(
            value=comp.ast.Number(5),
            key=comp.ast.String("x")
        )
    ])

    result = engine.run(expr)
    assert result.is_struct
    assert comp.Value("x") in result.struct
    assert result.struct[comp.Value("x")] == comp.Value(5)


def test_multiple_named_fields():
    """Test {x = 5, y = 10, z = 15}."""
    engine = comp.Engine()

    expr = comp.ast.Structure([
        comp.ast.FieldOp(comp.ast.Number(5), key=comp.ast.String("x")),
        comp.ast.FieldOp(comp.ast.Number(10), key=comp.ast.String("y")),
        comp.ast.FieldOp(comp.ast.Number(15), key=comp.ast.String("z")),
    ])

    result = engine.run(expr)
    assert result.is_struct
    assert result.struct[comp.Value("x")] == comp.Value(5)
    assert result.struct[comp.Value("y")] == comp.Value(10)
    assert result.struct[comp.Value("z")] == comp.Value(15)


def test_unnamed_fields():
    """Test {1 2 3} - unnamed fields."""
    engine = comp.Engine()

    expr = comp.ast.Structure([
        comp.ast.FieldOp(comp.ast.Number(1)),
        comp.ast.FieldOp(comp.ast.Number(2)),
        comp.ast.FieldOp(comp.ast.Number(3)),
    ])

    result = engine.run(expr)
    assert result.is_struct
    assert len(result.struct) == 3

    # Get all values (unnamed fields)
    values = list(result.struct.values())
    assert values[0] == comp.Value(1)
    assert values[1] == comp.Value(2)
    assert values[2] == comp.Value(3)


def test_mixed_fields():
    """Test {x=5 10 y=15} - mix of named and unnamed."""
    engine = comp.Engine()

    expr = comp.ast.Structure([
        comp.ast.FieldOp(comp.ast.Number(5), key=comp.ast.String("x")),
        comp.ast.FieldOp(comp.ast.Number(10)),
        comp.ast.FieldOp(comp.ast.Number(15), key=comp.ast.String("y")),
    ])

    result = engine.run(expr)
    assert result.is_struct
    assert result.struct[comp.Value("x")] == comp.Value(5)
    assert result.struct[comp.Value("y")] == comp.Value(15)

    # Check unnamed field exists
    unnamed_values = [v for k, v in result.struct.items() if isinstance(k, comp.Unnamed)]
    assert len(unnamed_values) == 1
    assert unnamed_values[0] == comp.Value(10)


def test_spread_operator():
    """Test {..base y=3} - spreading another struct."""
    engine = comp.Engine()

    # First create base struct: {x=1 y=2}
    base_struct = comp.ast.Structure([
        comp.ast.FieldOp(comp.ast.Number(1), key=comp.ast.String("x")),
        comp.ast.FieldOp(comp.ast.Number(2), key=comp.ast.String("y")),
    ])

    base_value = engine.run(base_struct)

    # Now create: {..@ y=3} to override y (using scope field)
    # The '@' will reference the 'local' scope we pass in
    expr = comp.ast.Structure([
        comp.ast.SpreadOp(comp.ast.Identifier([comp.ast.ScopeField("@")])),  # @local scope
        comp.ast.FieldOp(comp.ast.Number(3), key=comp.ast.String("y")),
    ])

    result = engine.run(expr, local=base_value)
    assert result.is_struct
    assert result.struct[comp.Value("x")] == comp.Value(1)
    assert result.struct[comp.Value("y")] == comp.Value(3)  # Overridden


def test_nested_structure():
    """Test {point = {x=10 y=20}}."""
    engine = comp.Engine()

    expr = comp.ast.Structure([
        comp.ast.FieldOp(
            comp.ast.Structure([
                comp.ast.FieldOp(comp.ast.Number(10), key=comp.ast.String("x")),
                comp.ast.FieldOp(comp.ast.Number(20), key=comp.ast.String("y")),
            ]),
            key=comp.ast.String("point")
        )
    ])

    result = engine.run(expr)
    assert result.is_struct

    point = result.struct[comp.Value("point")]
    assert point.is_struct
    assert point.struct[comp.Value("x")] == comp.Value(10)
    assert point.struct[comp.Value("y")] == comp.Value(20)


def test_unparse():
    """Test unparsing structure literals."""
    expr = comp.ast.Structure([
        comp.ast.FieldOp(comp.ast.Number(5), key=comp.ast.String("x")),
        comp.ast.FieldOp(comp.ast.Number(10)),
    ])

    unparsed = expr.unparse()
    assert "x" in unparsed
    assert "=" in unparsed
    assert "5" in unparsed
    assert "10" in unparsed


def test_deep_assignment_simple():
    """Test {one.two = 5} creates nested structure."""
    engine = comp.Engine()

    expr = comp.ast.Structure([
        comp.ast.FieldOp(
            comp.ast.Number(5),
            key=[comp.ast.String("one"), comp.ast.String("two")]
        )
    ])

    result = engine.run(expr)
    assert result.is_struct

    # Check outer level has "one"
    one_key = comp.Value("one")
    assert one_key in result.struct

    # Check inner level has "two" = 5
    one_struct = result.struct[one_key]
    assert one_struct.is_struct
    two_key = comp.Value("two")
    assert two_key in one_struct.struct
    assert one_struct.struct[two_key] == comp.Value(5)


def test_deep_assignment_three_levels():
    """Test {one.two.three = 5} creates three-level nesting."""
    engine = comp.Engine()

    expr = comp.ast.Structure([
        comp.ast.FieldOp(
            comp.ast.Number(5),
            key=[comp.ast.String("one"), comp.ast.String("two"), comp.ast.String("three")]
        )
    ])

    result = engine.run(expr)

    # Navigate through three levels
    one = result.struct[comp.Value("one")]
    assert one.is_struct
    two = one.struct[comp.Value("two")]
    assert two.is_struct
    three_value = two.struct[comp.Value("three")]
    assert three_value == comp.Value(5)


def test_deep_assignment_multiple_paths():
    """Test {one.two=1 one.three=2} builds tree."""
    engine = comp.Engine()

    expr = comp.ast.Structure([
        comp.ast.FieldOp(comp.ast.Number(1), key=[comp.ast.String("one"), comp.ast.String("two")]),
        comp.ast.FieldOp(comp.ast.Number(2), key=[comp.ast.String("one"), comp.ast.String("three")]),
    ])

    result = engine.run(expr)

    # Check both paths exist under "one"
    one = result.struct[comp.Value("one")]
    assert one.struct[comp.Value("two")] == comp.Value(1)
    assert one.struct[comp.Value("three")] == comp.Value(2)


def test_deep_assignment_mixed_with_simple():
    """Test {x=1 one.two=2 y=3} mixes simple and deep."""
    engine = comp.Engine()

    expr = comp.ast.Structure([
        comp.ast.FieldOp(comp.ast.Number(1), key=comp.ast.String("x")),
        comp.ast.FieldOp(comp.ast.Number(2), key=[comp.ast.String("one"), comp.ast.String("two")]),
        comp.ast.FieldOp(comp.ast.Number(3), key=comp.ast.String("y")),
    ])

    result = engine.run(expr)

    # Check simple fields
    assert result.struct[comp.Value("x")] == comp.Value(1)
    assert result.struct[comp.Value("y")] == comp.Value(3)

    # Check deep field
    one = result.struct[comp.Value("one")]
    assert one.struct[comp.Value("two")] == comp.Value(2)


def test_deep_assignment_with_index():
    """Test {one=1 two=2 #1.nested=99} - IndexField in path."""
    engine = comp.Engine()

    expr = comp.ast.Structure([
        comp.ast.FieldOp(comp.ast.Number(1), key=comp.ast.String("one")),
        comp.ast.FieldOp(comp.ast.Number(2), key=comp.ast.String("two")),
        # Use IndexField to refer to second field (two), add nested to it
        comp.ast.FieldOp(comp.ast.Number(99), key=[comp.ast.IndexField(1), comp.ast.String("nested")]),
    ])

    result = engine.run(expr)

    # Check original fields exist
    assert result.struct[comp.Value("one")] == comp.Value(1)

    # The second field (two) should now be a struct with nested
    two = result.struct[comp.Value("two")]
    assert two.is_struct
    assert two.struct[comp.Value("nested")] == comp.Value(99)


def test_deep_assignment_overwrite_simple():
    """Test {one=1 one.two=2} - deep overwrites simple value."""
    engine = comp.Engine()

    expr = comp.ast.Structure([
        comp.ast.FieldOp(comp.ast.Number(1), key=comp.ast.String("one")),
        comp.ast.FieldOp(comp.ast.Number(2), key=[comp.ast.String("one"), comp.ast.String("two")]),
    ])

    result = engine.run(expr)

    # "one" should be a struct now (not 1)
    one = result.struct[comp.Value("one")]
    assert one.is_struct
    assert one.struct[comp.Value("two")] == comp.Value(2)


def test_deep_assignment_with_compute():
    """Test {x.[1+1] = 99} - comp.ComputeField in path."""
    engine = comp.Engine()

    # Create: {x.[1+1] = 99}
    # The computed field [1+1] evaluates to 2, so creates key comp.Value(2)
    expr = comp.ast.Structure([
        comp.ast.FieldOp(
            comp.ast.Number(99),
            key=[
                comp.ast.String("x"),
                comp.ast.ComputeField(comp.ast.ArithmeticOp("+", comp.ast.Number(1), comp.ast.Number(1)))
            ]
        )
    ])

    result = engine.run(expr)

    # Check x.2 = 99 (where 2 is computed from 1+1)
    x = result.struct[comp.Value("x")]
    assert x.is_struct
    assert x.struct[comp.Value(2)] == comp.Value(99)

