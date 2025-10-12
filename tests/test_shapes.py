"""Tests for shape definitions and references."""

import comp


def test_entity_base_class_shapes():
    """Verify comp.ShapeField and ShapeDefinition work with module system."""
    module = comp.Module()

    # Define a simple shape
    fields = [
        comp.ShapeField(name="x", shape=None),  # ~num would go here
        comp.ShapeField(name="y", shape=None),
    ]
    shape_def = module.define_shape(["point"], fields)

    assert shape_def.name == "point"
    assert len(shape_def.fields) == 2


def test_module_shape_storage():
    """Verify Module can store and retrieve shapes."""
    module = comp.Module()

    fields = [comp.ShapeField(name="name", shape=None)]
    module.define_shape(["user"], fields)

    # Look up shape
    shape = module.lookup_shape(["user"])
    assert shape is not None
    assert shape.name == "user"

    # Non-existent shape
    assert module.lookup_shape(["nonexistent"]) is None


def test_simple_shape_definition():
    """Test defining a shape with named fields."""
    # Create shape definition: !shape ~point = {x ~num y ~num}
    # For now, skip the type refs and just test structure
    shape_def = comp.ast.ShapeDef(
        path=["point"],
        fields=[
            comp.ast.ShapeFieldDef(name="x"),
            comp.ast.ShapeFieldDef(name="y"),
        ]
    )

    # Module needs to be passed via mod_shapes scope
    module = comp.Module()

    # Wrap in test node that provides mod_shapes
    class TestWrapper(comp.ast.ValueNode):
        def evaluate(self, frame):
            result = yield comp.Compute(shape_def, mod_shapes=module)
            return result

        def unparse(self):
            return "test"

    engine = comp.Engine()
    result = engine.run(TestWrapper(), mod_shapes=module)

    # Should succeed
    assert result.to_python() == comp.TRUE

    # Shape should be in module
    shape = module.lookup_shape(["point"])
    assert shape is not None
    assert len(shape.fields) == 2


def test_shape_field_with_default():
    """Test shape field with default value."""
    field_def = comp.ast.ShapeFieldDef(
        name="age",
        default=comp.ast.Number(0)
    )

    # Evaluate to get comp.ShapeField
    module = comp.Module()

    class TestNode(comp.ast.ValueNode):
        def evaluate(self, frame):
            field = yield comp.Compute(field_def)
            # field is a comp.ShapeField, not a Value
            return comp.Value(True) if field.default else comp.Value(False)

        def unparse(self):
            return "test"

    engine = comp.Engine()
    result = engine.run(TestNode(), mod_shapes=module)

    assert result.to_python() == comp.TRUE


def test_positional_shape_fields():
    """Test shape with positional (unnamed) fields."""
    shape_def = comp.ast.ShapeDef(
        path=["pair"],
        fields=[
            comp.ast.ShapeFieldDef(),  # First positional
            comp.ast.ShapeFieldDef(),  # Second positional
        ]
    )

    module = comp.Module()

    class TestWrapper(comp.ast.ValueNode):
        def evaluate(self, frame):
            result = yield comp.Compute(shape_def, mod_shapes=module)
            return result

        def unparse(self):
            return "test"

    engine = comp.Engine()
    result = engine.run(TestWrapper(), mod_shapes=module)

    assert result.to_python() == comp.TRUE

    shape = module.lookup_shape(["pair"])
    assert shape is not None
    assert len(shape.positional_fields) == 2
    assert len(shape.named_fields) == 0


def test_shape_reference():
    """Test referencing a defined shape."""
    # Manually set up module with a shape
    module = comp.Module()
    fields = [comp.ShapeField(name="x"), comp.ShapeField(name="y")]
    module.define_shape(["point"], fields)

    # Create reference: ~point
    shape_ref = comp.ast.ShapeRef(["point"])

    # Evaluate reference
    class TestNode(comp.ast.ValueNode):
        def evaluate(self, frame):
            shape = yield comp.Compute(shape_ref)
            # shape is a ShapeDefinition
            return comp.Value(shape.name if shape else "none")

        def unparse(self):
            return "test"

    engine = comp.Engine()
    result = engine.run(TestNode(), mod_shapes=module)

    assert result.to_python() == "point"


def test_shape_reference_not_found():
    """Test that missing shapes are handled."""
    module = comp.Module()

    shape_ref = comp.ast.ShapeRef(["nonexistent"])

    class TestNode(comp.ast.ValueNode):
        def evaluate(self, frame):
            shape = yield comp.Compute(shape_ref)
            return shape

        def unparse(self):
            return "test"

    engine = comp.Engine()
    result = engine.run(TestNode(), mod_shapes=module)

    # Should be a failure
    assert result.tag == comp.FAIL


def test_spread_field():
    """Test shape field with spread operator."""
    field_def = comp.ast.ShapeFieldDef(
        is_spread=True,
        shape_ref=comp.ast.ShapeRef(["point"])
    )

    assert field_def.is_spread
    assert field_def.name is None  # Spread fields have no name


def test_spread_expansion():
    """Test that spread fields are expanded into the shape definition."""
    # Define base shape: !shape ~point-2d = {x ~num y ~num}
    point_2d = comp.ast.ShapeDef(
        path=["point-2d"],
        fields=[
            comp.ast.ShapeFieldDef(name="x"),
            comp.ast.ShapeFieldDef(name="y"),
        ]
    )

    # Define extended shape with spread: !shape ~point-3d = {..~point-2d z ~num}
    point_3d = comp.ast.ShapeDef(
        path=["point-3d"],
        fields=[
            comp.ast.ShapeFieldDef(is_spread=True, shape_ref=comp.ast.ShapeRef(["point-2d"])),
            comp.ast.ShapeFieldDef(name="z"),
        ]
    )

    module = comp.Module()

    class TestWrapper(comp.ast.ValueNode):
        def evaluate(self, frame):
            # Define base shape first
            result1 = yield comp.Compute(point_2d, mod_shapes=module)
            if frame.is_fail(result1):
                return result1

            # Then define extended shape with spread
            result2 = yield comp.Compute(point_3d, mod_shapes=module)
            return result2

        def unparse(self):
            return "test"

    engine = comp.Engine()
    result = engine.run(TestWrapper(), mod_shapes=module)

    assert result.to_python() == comp.TRUE

    # Check that point-3d has all three fields (spread was expanded)
    shape = module.lookup_shape(["point-3d"])
    assert shape is not None
    assert len(shape.fields) == 3, f"Expected 3 fields, got {len(shape.fields)}"

    # Verify field names
    field_names = [f.name for f in shape.named_fields]
    assert "x" in field_names
    assert "y" in field_names
    assert "z" in field_names

    # Verify no spread fields remain in runtime shape
    # (comp.ShapeField doesn't have is_spread attribute - only AST nodes do)
    assert all(hasattr(f, 'name') for f in shape.fields)


def test_array_field():
    """Test shape field with array notation."""
    field_def = comp.ast.ShapeFieldDef(
        name="items",
        is_array=True,
        array_min=1,
        array_max=5
    )

    assert field_def.is_array
    assert field_def.array_min == 1
    assert field_def.array_max == 5

    # Unparse should show array notation
    unparsed = field_def.unparse()
    assert "[1-5]" in unparsed


def test_shape_union_creation():
    """Test creating a union shape."""
    union = comp.ast.ShapeUnion([
        comp.ast.ShapeRef(["user"]),
        comp.ast.ShapeRef(["admin"]),
    ])

    assert len(union.members) == 2
    assert "user" in union.unparse()
    assert "|" in union.unparse()


def test_mixed_named_positional_fields():
    """Test shape with both named and positional fields."""
    shape_def = comp.ast.ShapeDef(
        path=["labeled"],
        fields=[
            comp.ast.ShapeFieldDef(),              # Positional
            comp.ast.ShapeFieldDef(name="label"),  # Named
        ]
    )

    module = comp.Module()

    class TestWrapper(comp.ast.ValueNode):
        def evaluate(self, frame):
            result = yield comp.Compute(shape_def, mod_shapes=module)
            return result

        def unparse(self):
            return "test"

    engine = comp.Engine()
    result = engine.run(TestWrapper(), mod_shapes=module)

    assert result.to_python() == comp.TRUE

    shape = module.lookup_shape(["labeled"])
    assert shape is not None
    assert len(shape.positional_fields) == 1
    assert len(shape.named_fields) == 1
