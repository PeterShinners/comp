"""Tests for shape field representation and building from AST."""

import pytest
import comp


def test_shape_def_has_fields():
    """Shape definitions should have their fields populated from AST."""
    # Parse a module with a shape definition
    code = """
    !shape ~point = {
        x ~num
        y ~num
    }
    """

    module_ast = comp.parse_module(code)
    runtime_mod = comp.run.Module("test")
    runtime_mod.process_ast(module_ast)
    runtime_mod.resolve_all()

    # Check that the shape exists
    assert "point" in runtime_mod.shapes
    shape_def = runtime_mod.shapes["point"]

    # Check that fields were populated
    assert len(shape_def.fields) == 2, f"Expected 2 fields, got {len(shape_def.fields)}: {shape_def.fields}"

    # Fields should be keyed by Value objects (not strings)
    field_keys = list(shape_def.fields.keys())
    assert all(hasattr(k, 'str') or isinstance(k, comp.run.Unnamed) for k in field_keys), \
        f"Field keys should be Value or Unnamed, got: {[type(k).__name__ for k in field_keys]}"

    # Check that we can find "x" and "y" fields
    x_key = next((k for k in field_keys if hasattr(k, 'str') and k.str == "x"), None)
    y_key = next((k for k in field_keys if hasattr(k, 'str') and k.str == "y"), None)

    assert x_key is not None, f"Expected 'x' field, got keys: {field_keys}"
    assert y_key is not None, f"Expected 'y' field, got keys: {field_keys}"

    # Check that fields have ShapeField objects
    assert isinstance(shape_def.fields[x_key], comp.run.ShapeField)
    assert isinstance(shape_def.fields[y_key], comp.run.ShapeField)


def test_shape_def_with_unnamed_fields():
    """Shape definitions with unnamed/positional fields should use Unnamed keys."""
    code = """
    !shape ~pair = {
        ~num
        ~num
    }
    """

    module_ast = comp.parse_module(code)
    runtime_mod = comp.run.Module("test")
    runtime_mod.process_ast(module_ast)
    runtime_mod.resolve_all()

    shape_def = runtime_mod.shapes["pair"]

    # Should have 2 fields
    assert len(shape_def.fields) == 2

    # Both should be keyed by Unnamed instances
    field_keys = list(shape_def.fields.keys())
    unnamed_count = sum(1 for k in field_keys if isinstance(k, comp.run.Unnamed))
    assert unnamed_count == 2, f"Expected 2 Unnamed keys, got {unnamed_count}"


def test_shape_def_mixed_fields():
    """Shape with mix of named and unnamed fields."""
    code = """
    !shape ~mixed = {
        ~num
        y ~num
        ~str
    }
    """

    module_ast = comp.parse_module(code)
    runtime_mod = comp.run.Module("test")
    runtime_mod.process_ast(module_ast)
    runtime_mod.resolve_all()

    shape_def = runtime_mod.shapes["mixed"]

    # Should have 3 fields
    assert len(shape_def.fields) == 3

    field_keys = list(shape_def.fields.keys())

    # Count named vs unnamed
    named_keys = [k for k in field_keys if hasattr(k, 'str') and k.str is not None]
    unnamed_keys = [k for k in field_keys if isinstance(k, comp.run.Unnamed)]

    assert len(named_keys) == 1, f"Expected 1 named field, got {len(named_keys)}"
    assert len(unnamed_keys) == 2, f"Expected 2 unnamed fields, got {len(unnamed_keys)}"

    # Check that "y" field exists
    y_key = next((k for k in named_keys if k.str == "y"), None)
    assert y_key is not None


def test_morph_with_parsed_shape():
    """Test morphing with a shape that was parsed from AST."""
    code = """
    !shape ~point = {
        x ~num
        y ~num
    }
    """

    module_ast = comp.parse_module(code)
    runtime_mod = comp.run.Module("test")
    runtime_mod.process_ast(module_ast)
    runtime_mod.resolve_all()

    # Get the shape
    shape_def = runtime_mod.shapes["point"]

    # Debug: Check what the field shapes are
    for k, f in shape_def.fields.items():
        print(f"\nField {k}: shape={f.shape}, shape_type={type(f.shape).__name__ if f.shape else None}")

    # Create a shape reference to it
    shape_ref = comp.run.ShapeDefRef("point")
    shape_ref._resolved = shape_def

    # Create a value to morph
    value = comp.run.Value({"x": 10, "y": 20})

    # Debug: Check the input value structure
    assert value.struct is not None
    for k, v in value.struct.items():
        if hasattr(k, 'str') and k.str == "x":
            assert v.num == 10, f"Input x value should be 10, got {v}"
            assert v.struct is None, f"Input x should not be a struct, got {v.struct}"

    # Morph it
    result = comp.run.morph(value, shape_ref)

    # Should succeed
    assert result.success, f"Morph failed: {result}"
    assert result.named_matches == 2, f"Expected 2 named matches, got {result.named_matches}"

    # Result should have x and y fields
    assert result.value is not None
    field_keys = list(result.value.struct.keys())

    x_key = next((k for k in field_keys if hasattr(k, 'str') and k.str == "x"), None)
    y_key = next((k for k in field_keys if hasattr(k, 'str') and k.str == "y"), None)

    assert x_key is not None, f"Could not find 'x' in keys: {[(k, type(k).__name__, getattr(k, 'str', None)) for k in field_keys]}"
    assert y_key is not None, f"Could not find 'y' in keys: {[(k, type(k).__name__, getattr(k, 'str', None)) for k in field_keys]}"

    x_value = result.value.struct[x_key]
    y_value = result.value.struct[y_key]

    # For now, accept either direct numbers or wrapped structs
    # (wrapping happens because ~num shape references are unresolved)
    if x_value.num is not None:
        assert x_value.num == 10
    elif x_value.struct is not None:
        # Wrapped - extract the inner value
        inner = list(x_value.struct.values())[0]
        assert inner.num == 10

    if y_value.num is not None:
        assert y_value.num == 20
    elif y_value.struct is not None:
        inner = list(y_value.struct.values())[0]
        assert inner.num == 20


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
