"""Test structure literal evaluation."""

from src.comp.engine.engine import Engine
from src.comp.engine.ast import (
    Structure, FieldOp, SpreadOp,
    Number, String, Identifier, ScopeField, TokenField, IndexField, ComputeField,
    ArithmeticOp
)
from src.comp.engine.value import Value, Unnamed


def test_empty_structure():
    """Test empty structure literal {}."""
    engine = Engine()

    expr = Structure([])
    result = engine.run(expr)

    assert result.is_struct
    assert result.struct == {}
    print("✓ Empty structure works")


def test_single_named_field():
    """Test {x = 5}."""
    engine = Engine()

    expr = Structure([
        FieldOp(
            value=Number(5),
            key=String("x")
        )
    ])

    result = engine.run(expr)
    assert result.is_struct
    assert Value("x") in result.struct
    assert result.struct[Value("x")] == Value(5)
    print("✓ Single named field works")


def test_multiple_named_fields():
    """Test {x = 5, y = 10, z = 15}."""
    engine = Engine()

    expr = Structure([
        FieldOp(Number(5), key=String("x")),
        FieldOp(Number(10), key=String("y")),
        FieldOp(Number(15), key=String("z")),
    ])

    result = engine.run(expr)
    assert result.is_struct
    assert result.struct[Value("x")] == Value(5)
    assert result.struct[Value("y")] == Value(10)
    assert result.struct[Value("z")] == Value(15)
    print("✓ Multiple named fields work")


def test_unnamed_fields():
    """Test {1 2 3} - unnamed fields."""
    engine = Engine()

    expr = Structure([
        FieldOp(Number(1)),
        FieldOp(Number(2)),
        FieldOp(Number(3)),
    ])

    result = engine.run(expr)
    assert result.is_struct
    assert len(result.struct) == 3

    # Get all values (unnamed fields)
    values = list(result.struct.values())
    assert values[0] == Value(1)
    assert values[1] == Value(2)
    assert values[2] == Value(3)
    print("✓ Unnamed fields work")


def test_mixed_fields():
    """Test {x=5 10 y=15} - mix of named and unnamed."""
    engine = Engine()

    expr = Structure([
        FieldOp(Number(5), key=String("x")),
        FieldOp(Number(10)),
        FieldOp(Number(15), key=String("y")),
    ])

    result = engine.run(expr)
    assert result.is_struct
    assert result.struct[Value("x")] == Value(5)
    assert result.struct[Value("y")] == Value(15)

    # Check unnamed field exists
    unnamed_values = [v for k, v in result.struct.items() if isinstance(k, Unnamed)]
    assert len(unnamed_values) == 1
    assert unnamed_values[0] == Value(10)
    print("✓ Mixed named and unnamed fields work")


def test_spread_operator():
    """Test {..base y=3} - spreading another struct."""
    engine = Engine()

    # First create base struct: {x=1 y=2}
    base_struct = Structure([
        FieldOp(Number(1), key=String("x")),
        FieldOp(Number(2), key=String("y")),
    ])

    base_value = engine.run(base_struct)
    engine.set_scope('unnamed', base_value)

    # Now create: {..@unnamed y=3} to override y (using scope field)
    expr = Structure([
        SpreadOp(Identifier([ScopeField("@")])),  # @local scope
        FieldOp(Number(3), key=String("y")),
    ])

    # Actually, let's use the 'local' scope which maps from '@'
    engine.set_scope('local', base_value)

    result = engine.run(expr)
    assert result.is_struct
    assert result.struct[Value("x")] == Value(1)
    assert result.struct[Value("y")] == Value(3)  # Overridden
    print("✓ Spread operator works")


def test_nested_structure():
    """Test {point = {x=10 y=20}}."""
    engine = Engine()

    expr = Structure([
        FieldOp(
            Structure([
                FieldOp(Number(10), key=String("x")),
                FieldOp(Number(20), key=String("y")),
            ]),
            key=String("point")
        )
    ])

    result = engine.run(expr)
    assert result.is_struct

    point = result.struct[Value("point")]
    assert point.is_struct
    assert point.struct[Value("x")] == Value(10)
    assert point.struct[Value("y")] == Value(20)
    print("✓ Nested structure works")


def test_unparse():
    """Test unparsing structure literals."""
    expr = Structure([
        FieldOp(Number(5), key=String("x")),
        FieldOp(Number(10)),
    ])

    unparsed = expr.unparse()
    assert "x" in unparsed
    assert "=" in unparsed
    assert "5" in unparsed
    assert "10" in unparsed
    print(f"✓ Unparse works: {unparsed}")


def test_deep_assignment_simple():
    """Test {one.two = 5} creates nested structure."""
    engine = Engine()

    expr = Structure([
        FieldOp(
            Number(5),
            key=[String("one"), String("two")]
        )
    ])

    result = engine.run(expr)
    assert result.is_struct

    # Check outer level has "one"
    one_key = Value("one")
    assert one_key in result.struct

    # Check inner level has "two" = 5
    one_struct = result.struct[one_key]
    assert one_struct.is_struct
    two_key = Value("two")
    assert two_key in one_struct.struct
    assert one_struct.struct[two_key] == Value(5)
    print("✓ Deep assignment (one.two = 5) works")


def test_deep_assignment_three_levels():
    """Test {one.two.three = 5} creates three-level nesting."""
    engine = Engine()

    expr = Structure([
        FieldOp(
            Number(5),
            key=[String("one"), String("two"), String("three")]
        )
    ])

    result = engine.run(expr)

    # Navigate through three levels
    one = result.struct[Value("one")]
    assert one.is_struct
    two = one.struct[Value("two")]
    assert two.is_struct
    three_value = two.struct[Value("three")]
    assert three_value == Value(5)
    print("✓ Deep assignment (one.two.three = 5) works")


def test_deep_assignment_multiple_paths():
    """Test {one.two=1 one.three=2} builds tree."""
    engine = Engine()

    expr = Structure([
        FieldOp(Number(1), key=[String("one"), String("two")]),
        FieldOp(Number(2), key=[String("one"), String("three")]),
    ])

    result = engine.run(expr)

    # Check both paths exist under "one"
    one = result.struct[Value("one")]
    assert one.struct[Value("two")] == Value(1)
    assert one.struct[Value("three")] == Value(2)
    print("✓ Deep assignment multiple paths works")


def test_deep_assignment_mixed_with_simple():
    """Test {x=1 one.two=2 y=3} mixes simple and deep."""
    engine = Engine()

    expr = Structure([
        FieldOp(Number(1), key=String("x")),
        FieldOp(Number(2), key=[String("one"), String("two")]),
        FieldOp(Number(3), key=String("y")),
    ])

    result = engine.run(expr)

    # Check simple fields
    assert result.struct[Value("x")] == Value(1)
    assert result.struct[Value("y")] == Value(3)

    # Check deep field
    one = result.struct[Value("one")]
    assert one.struct[Value("two")] == Value(2)
    print("✓ Deep assignment mixed with simple works")


def test_deep_assignment_with_index():
    """Test {one=1 two=2 #1.nested=99} - IndexField in path."""
    engine = Engine()

    expr = Structure([
        FieldOp(Number(1), key=String("one")),
        FieldOp(Number(2), key=String("two")),
        # Use IndexField to refer to second field (two), add nested to it
        FieldOp(Number(99), key=[IndexField(1), String("nested")]),
    ])

    result = engine.run(expr)

    # Check original fields exist
    assert result.struct[Value("one")] == Value(1)

    # The second field (two) should now be a struct with nested
    two = result.struct[Value("two")]
    assert two.is_struct
    assert two.struct[Value("nested")] == Value(99)
    print("✓ Deep assignment with IndexField works")


def test_deep_assignment_overwrite_simple():
    """Test {one=1 one.two=2} - deep overwrites simple value."""
    engine = Engine()

    expr = Structure([
        FieldOp(Number(1), key=String("one")),
        FieldOp(Number(2), key=[String("one"), String("two")]),
    ])

    result = engine.run(expr)

    # "one" should be a struct now (not 1)
    one = result.struct[Value("one")]
    assert one.is_struct
    assert one.struct[Value("two")] == Value(2)
    print("✓ Deep assignment overwrites simple value")


def test_deep_assignment_with_compute():
    """Test {x.[1+1] = 99} - ComputeField in path."""
    engine = Engine()

    # Create: {x.[1+1] = 99}
    # The computed field [1+1] evaluates to 2, so creates key Value(2)
    expr = Structure([
        FieldOp(
            Number(99),
            key=[
                String("x"),
                ComputeField(ArithmeticOp("+", Number(1), Number(1)))
            ]
        )
    ])

    result = engine.run(expr)

    # Check x.2 = 99 (where 2 is computed from 1+1)
    x = result.struct[Value("x")]
    assert x.is_struct
    assert x.struct[Value(2)] == Value(99)
    print("✓ Deep assignment with ComputeField works")


if __name__ == "__main__":
    test_empty_structure()
    test_single_named_field()
    test_multiple_named_fields()
    test_unnamed_fields()
    test_mixed_fields()
    test_spread_operator()
    test_nested_structure()
    test_unparse()
    test_deep_assignment_simple()
    test_deep_assignment_three_levels()
    test_deep_assignment_multiple_paths()
    test_deep_assignment_mixed_with_simple()
    test_deep_assignment_with_index()
    test_deep_assignment_overwrite_simple()
    test_deep_assignment_with_compute()
    print("\n✅ All structure tests passed!")
