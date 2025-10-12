"""Tests for shape mask operations (^ and ^*)."""

import runtest

import comp


def test_permissive_mask_basic():
    """Test basic permissive mask (^) filtering."""
    # Create a shape with named fields
    code = "!shape ~test = {user ~str session ~str}"
    module = runtest.module_from_code(code)
    shape_def = module.shapes["test"]
    shape_ref = comp.run.ShapeRef(("test",))
    shape_ref._resolved = shape_def

    # Create value with matching and extra fields
    data = comp.run.Value({
        "user": "alice",
        "session": "abc123",
        "debug": True,
        "admin": "secret"
    })

    # Apply permissive mask
    result = comp.run.mask(data, shape_ref)

    # Should succeed with only matching fields
    assert result.success
    assert result.value.is_struct
    assert len(result.value.struct) == 2
    assert result.value.struct[comp.run.Value("user")].str == "alice"
    assert result.value.struct[comp.run.Value("session")].str == "abc123"
    assert comp.run.Value("debug") not in result.value.struct
    assert comp.run.Value("admin") not in result.value.struct

    # Score should reflect matched fields
    assert result.named_matches == 2


def test_permissive_mask_missing_fields():
    """Test permissive mask with missing fields (no defaults applied)."""
    # Shape with three fields, one with default
    code = "!shape ~test = {user ~str session ~str timeout ~num = 30}"
    module = runtest.module_from_code(code)
    shape_def = module.shapes["test"]
    shape_ref = comp.run.ShapeRef(("test",))
    shape_ref._resolved = shape_def

    # Value with only one field
    data = comp.run.Value({"user": "bob"})

    # Apply permissive mask
    result = comp.run.mask(data, shape_ref)

    # Should succeed with only the one matching field
    assert result.success
    assert len(result.value.struct) == 1
    assert result.value.struct[comp.run.Value("user")].str == "bob"

    # Should NOT have session or timeout (no defaults in permissive mask)
    assert comp.run.Value("session") not in result.value.struct
    assert comp.run.Value("timeout") not in result.value.struct

    # Score reflects only one match
    assert result.named_matches == 1


def test_permissive_mask_no_overlap():
    """Test permissive mask with no overlapping fields."""
    # Shape with certain fields
    code = "!shape ~test = {x ~num y ~num}"
    module = runtest.module_from_code(code)
    shape_def = module.shapes["test"]
    shape_ref = comp.run.ShapeRef(("test",))
    shape_ref._resolved = shape_def

    # Value with completely different fields
    data = comp.run.Value({"a": 1, "b": 2, "c": 3})

    # Apply permissive mask
    result = comp.run.mask(data, shape_ref)

    # Should succeed but with empty result
    assert result.success
    assert result.value.is_struct
    assert len(result.value.struct) == 0
    assert result.named_matches == 0


def test_permissive_mask_empty_value():
    """Test permissive mask with empty struct."""
    code = "!shape ~test = {x ~num}"
    module = runtest.module_from_code(code)
    shape_def = module.shapes["test"]
    shape_ref = comp.run.ShapeRef(("test",))
    shape_ref._resolved = shape_def

    # Empty struct
    data = comp.run.Value({})

    result = comp.run.mask(data, shape_ref)

    assert result.success
    assert len(result.value.struct) == 0
    assert result.named_matches == 0


def test_permissive_mask_non_struct_fails():
    """Test that permissive mask fails for non-struct values."""
    code = "!shape ~test = {x ~num}"
    module = runtest.module_from_code(code)
    shape_def = module.shapes["test"]
    shape_ref = comp.run.ShapeRef(("test",))
    shape_ref._resolved = shape_def

    # Try to mask a number
    data = comp.run.Value(5)
    result = comp.run.mask(data, shape_ref)

    assert not result.success

    # Try to mask a string
    data = comp.run.Value("hello")
    result = comp.run.mask(data, shape_ref)

    assert not result.success


def test_strict_mask_basic_success():
    """Test basic strict mask (^*) validation with defaults."""
    # Shape with required and optional fields
    code = "!shape ~test = {host ~str port ~num timeout ~num = 30}"
    module = runtest.module_from_code(code)
    shape_def = module.shapes["test"]
    shape_ref = comp.run.ShapeRef(("test",))
    shape_ref._resolved = shape_def

    # Value with required fields only
    data = comp.run.Value({"host": "localhost", "port": 8080})

    # Apply strict mask
    result = comp.run.strict_mask(data, shape_ref)

    # Should succeed with defaults applied
    assert result.success
    assert len(result.value.struct) == 3
    assert result.value.struct[comp.run.Value("host")].str == "localhost"
    assert result.value.struct[comp.run.Value("port")].num == 8080
    assert result.value.struct[comp.run.Value("timeout")].num == 30


def test_strict_mask_extra_fields_fail():
    """Test that strict mask fails on extra fields."""
    code = "!shape ~test = {host ~str port ~num}"
    module = runtest.module_from_code(code)
    shape_def = module.shapes["test"]
    shape_ref = comp.run.ShapeRef(("test",))
    shape_ref._resolved = shape_def

    # Value with extra field
    data = comp.run.Value({
        "host": "localhost",
        "port": 8080,
        "debug": True
    })

    # Apply strict mask
    result = comp.run.strict_mask(data, shape_ref)

    # Should fail due to extra field
    assert not result.success


def test_strict_mask_missing_required_fails():
    """Test that strict mask fails on missing required fields."""
    code = "!shape ~test = {host ~str port ~num}"
    module = runtest.module_from_code(code)
    shape_def = module.shapes["test"]
    shape_ref = comp.run.ShapeRef(("test",))
    shape_ref._resolved = shape_def

    # Value missing required field
    data = comp.run.Value({"host": "localhost"})

    # Apply strict mask
    result = comp.run.strict_mask(data, shape_ref)

    # Should fail due to missing 'port'
    assert not result.success


def test_strict_mask_type_mismatch_fails():
    """Test that strict mask fails on type mismatches."""
    code = "!shape ~test = {port ~num}"
    module = runtest.module_from_code(code)
    shape_def = module.shapes["test"]
    shape_ref = comp.run.ShapeRef(("test",))
    shape_ref._resolved = shape_def

    # Value with wrong type
    data = comp.run.Value({"port": "not-a-number"})

    # Apply strict mask
    result = comp.run.strict_mask(data, shape_ref)

    # Should fail due to type mismatch
    assert not result.success


def test_permissive_mask_preserves_values():
    """Test that permissive mask preserves original field values."""
    code = "!shape ~test = {data ~str}"
    module = runtest.module_from_code(code)
    shape_def = module.shapes["test"]
    shape_ref = comp.run.ShapeRef(("test",))
    shape_ref._resolved = shape_def

    # Create complex nested value
    nested = comp.run.Value({"inner": "value"})
    data = comp.run.Value({"data": nested, "extra": "removed"})

    result = comp.run.mask(data, shape_ref)

    assert result.success
    assert len(result.value.struct) == 1
    # Should preserve the nested value
    filtered_data = result.value.struct[comp.run.Value("data")]
    assert filtered_data.is_struct
    assert comp.run.Value("inner") in filtered_data.struct
    assert filtered_data.struct[comp.run.Value("inner")].str == "value"


def test_permissive_mask_ignores_unnamed_fields():
    """Test that permissive mask ignores unnamed fields."""
    code = "!shape ~test = {x ~num}"
    module = runtest.module_from_code(code)
    shape_def = module.shapes["test"]
    shape_ref = comp.run.ShapeRef(("test",))
    shape_ref._resolved = shape_def

    # Value with named and unnamed fields
    data = comp.run.Value({})
    data.struct = {
        comp.run.Value("x"): comp.run.Value(5),
        comp.run.Unnamed(): comp.run.Value(10),
        comp.run.Value("y"): comp.run.Value(15)
    }

    result = comp.run.mask(data, shape_ref)

    # Should only keep named field 'x'
    assert result.success
    assert len(result.value.struct) == 1
    assert result.value.struct[comp.run.Value("x")].num == 5


def test_strict_mask_allows_positional_if_shape_has_positional():
    """Test that strict mask allows unnamed fields if shape has positional fields."""
    code = "!shape ~test = {~num x ~num}"
    module = runtest.module_from_code(code)
    shape_def = module.shapes["test"]
    shape_ref = comp.run.ShapeRef(("test",))
    shape_ref._resolved = shape_def

    # Value with unnamed field
    data = comp.run.Value({})
    data.struct = {
        comp.run.Unnamed(): comp.run.Value(5),
        comp.run.Value("x"): comp.run.Value(10)
    }

    result = comp.run.strict_mask(data, shape_ref)

    # Should succeed (unnamed field is OK because shape has positional)
    assert result.success


def test_strict_mask_rejects_positional_if_shape_only_named():
    """Test that strict mask rejects unnamed fields if shape only has named fields."""
    code = "!shape ~test = {x ~num}"
    module = runtest.module_from_code(code)
    shape_def = module.shapes["test"]
    shape_ref = comp.run.ShapeRef(("test",))
    shape_ref._resolved = shape_def

    # Value with unnamed field
    data = comp.run.Value({})
    data.struct = {
        comp.run.Unnamed(): comp.run.Value(5),
        comp.run.Value("x"): comp.run.Value(10)
    }

    result = comp.run.strict_mask(data, shape_ref)

    # Should fail (unnamed field not allowed)
    assert not result.success


def test_mask_with_shape_def_directly():
    """Test that mask works with ShapeDef directly (not just ShapeRef)."""
    # Create a shape definition
    code = "!shape ~test = {user ~str}"
    module = runtest.module_from_code(code)
    shape_def = module.shapes["test"]

    data = comp.run.Value({"user": "alice", "extra": "data"})

    # Test with shape def directly (not wrapped in ShapeRef)
    result = comp.run.mask(data, shape_def)

    assert result.success
    assert len(result.value.struct) == 1
    assert result.value.struct[comp.run.Value("user")].str == "alice"


def test_strict_mask_with_all_defaults():
    """Test strict mask where all fields have defaults."""
    code = "!shape ~test = {x ~num = 1 y ~num = 2}"
    module = runtest.module_from_code(code)
    shape_def = module.shapes["test"]
    shape_ref = comp.run.ShapeRef(("test",))
    shape_ref._resolved = shape_def

    # Empty value
    data = comp.run.Value({})

    result = comp.run.strict_mask(data, shape_ref)

    # Should succeed with all defaults
    assert result.success
    assert len(result.value.struct) == 2
    assert result.value.struct[comp.run.Value("x")].num == 1
    assert result.value.struct[comp.run.Value("y")].num == 2


def test_permissive_mask_with_nested_shape():
    """Test permissive mask with nested shape references."""
    code = """
    !shape ~inner = {value ~num}
    !shape ~outer = {data ~inner name ~str}
    """
    module = runtest.module_from_code(code)
    shape_def = module.shapes["outer"]
    shape_ref = comp.run.ShapeRef(("outer",))
    shape_ref._resolved = shape_def

    # Value with matching and extra fields
    data = comp.run.Value({
        "data": {"value": 42},
        "name": "test",
        "extra": "removed"
    })

    result = comp.run.mask(data, shape_ref)

    # Should filter to only 'data' and 'name'
    assert result.success
    assert len(result.value.struct) == 2
    assert comp.run.Value("data") in result.value.struct
    assert comp.run.Value("name") in result.value.struct
    assert comp.run.Value("extra") not in result.value.struct


if __name__ == "__main__":
    # Run all tests
    import pytest
    pytest.main([__file__, "-v"])
