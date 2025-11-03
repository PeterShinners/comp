"""Tests for shape definitions and references."""

import pytest

import comp
import comptest


def test_simple_shape_definition():
    """Test defining a shape with named fields."""
    module = comptest.parse_module("""
        !shape ~point = {x ~num y ~num = 0}
    """)
    
    point_shape = module.lookup_shape(["point"])
    assert point_shape.name == "point"
    assert len(point_shape.fields) == 2


def test_shape_reference():
    """Test referencing a defined shape."""
    module = comp.Module()
    fields = [comp.ShapeField(name="x"), comp.ShapeField(name="y")]
    module.define_shape(["point"], fields)

    # Lookup should find the shape
    shape = module.lookup_shape(["point"])
    assert shape is not None
    assert shape.name == "point"
    assert len(shape.fields) == 2

    # Nonexistent shape should raise
    with pytest.raises(ValueError):
        module.lookup_shape(["nonexistent"])


def test_spread_expansion():
    """Test that spread fields are expanded into the shape definition."""
    module = comptest.parse_module("""
    !shape ~point-2d = {x ~num y ~num}
    !shape ~point-3d = {..~point-2d z ~num}
    """)
    
    # Check that point-3d has all three fields (spread was expanded)
    shape = module.lookup_shape(["point-3d"])
    assert shape is not None
    assert len(shape.fields) == 3, f"Expected 3 fields, got {len(shape.fields)}"

    # Verify field names
    field_names = [f.name for f in shape.named_fields]
    assert "x" in field_names
    assert "y" in field_names
    assert "z" in field_names


def test_array_field():
    """Test shape field with array notation (when implemented)."""
    # Array syntax not yet implemented in parser
    # This test documents the intended syntax
    with pytest.raises(comp.ParseError):
        comptest.parse_module("""
            !shape ~list = {items ~str[1-5]}
        """)


def test_mixed_named_positional_fields():
    """Test shape with both named and positional fields."""
    module = comptest.parse_module("!shape ~labeled = {~num label ~str}")
    
    shape = module.lookup_shape(["labeled"])
    assert shape is not None
    assert len(shape.positional_fields) == 1
    assert len(shape.named_fields) == 1

