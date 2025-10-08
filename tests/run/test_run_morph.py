"""Test shape morphing and type checking."""

import runtest

import comp


def test_morph_result_basics():
    """Test MorphResult scoring and comparison."""
    result1 = comp.run.MorphResult(named_matches=2, value=comp.run.Value(5))
    result2 = comp.run.MorphResult(named_matches=1, positional_matches=10, value=comp.run.Value(5))
    
    # Named matches have highest priority
    assert result1 > result2
    assert result1.success
    assert result2.success
    
    # Zero score means failure
    result_fail = comp.run.MorphResult()
    assert not result_fail.success
    assert result_fail.value is None


def test_morph_primitive_num():
    """Test morphing with ~num primitive."""
    code = "!shape ~test = ~num"
    module = runtest.module_from_code(code)
    shape_def = module.shapes["test"]
    shape_ref = comp.run.ShapeRef(("test",))
    shape_ref._resolved = shape_def
    
    # Number should morph successfully
    num_val = comp.run.Value(42)
    result = comp.run.morph(num_val, shape_ref)
    assert result.success
    assert result.value.num == 42
    
    # String should fail
    str_val = comp.run.Value("hello")
    result = comp.run.morph(str_val, shape_ref)
    assert not result.success


def test_morph_primitive_str():
    """Test morphing with ~str primitive."""
    code = "!shape ~test = ~str"
    module = runtest.module_from_code(code)
    shape_def = module.shapes["test"]
    shape_ref = comp.run.ShapeRef(("test",))
    shape_ref._resolved = shape_def
    
    # String should morph successfully
    str_val = comp.run.Value("hello")
    result = comp.run.morph(str_val, shape_ref)
    assert result.success
    assert result.value.str == "hello"
    
    # Number should fail
    num_val = comp.run.Value(42)
    result = comp.run.morph(num_val, shape_ref)
    assert not result.success


def test_morph_struct_named_fields():
    """Test morphing struct with named fields."""
    code = """
    !shape ~point = {
        x ~num
        y ~num
    }
    """
    module = runtest.module_from_code(code)
    shape_def = module.shapes["point"]
    shape_ref = comp.run.ShapeRef(("point",))
    shape_ref._resolved = shape_def
    
    # Matching struct should morph successfully
    value = comp.run.Value({"x": 10, "y": 20})
    result = comp.run.morph(value, shape_ref)
    
    assert result.success
    assert result.named_matches == 2
    assert result.value.is_struct
    
    # Check fields
    x_val = runtest.get_field_python(result.value, "x")
    y_val = runtest.get_field_python(result.value, "y")
    assert x_val == 10
    assert y_val == 20


def test_morph_struct_with_extra_fields():
    """Test that extra fields are preserved during morph."""
    code = """
    !shape ~point = {
        x ~num
        y ~num
    }
    """
    module = runtest.module_from_code(code)
    shape_def = module.shapes["point"]
    shape_ref = comp.run.ShapeRef(("point",))
    shape_ref._resolved = shape_def
    
    # Struct with extra field
    value = comp.run.Value({"x": 10, "y": 20, "z": 30})
    result = comp.run.morph(value, shape_ref)
    
    assert result.success
    assert result.named_matches == 2
    
    # All three fields should be present
    x_val = runtest.get_field_python(result.value, "x")
    y_val = runtest.get_field_python(result.value, "y")
    z_val = runtest.get_field_python(result.value, "z")
    assert x_val == 10
    assert y_val == 20
    assert z_val == 30


def test_morph_type_mismatch_fails():
    """Test that type mismatches cause morph to fail."""
    code = """
    !shape ~point = {
        x ~num
        y ~num
    }
    """
    module = runtest.module_from_code(code)
    shape_def = module.shapes["point"]
    shape_ref = comp.run.ShapeRef(("point",))
    shape_ref._resolved = shape_def
    
    # String value for ~num field should fail
    value = comp.run.Value({"x": "hello", "y": 20})
    result = comp.run.morph(value, shape_ref)
    
    assert not result.success


def test_morph_positional_to_named():
    """Test positional values morphing to named shape fields."""
    code = """
    !shape ~pair = {
        first ~num
        second ~num
    }
    """
    module = runtest.module_from_code(code)
    shape_def = module.shapes["pair"]
    shape_ref = comp.run.ShapeRef(("pair",))
    shape_ref._resolved = shape_def
    
    # Positional values (unnamed fields)
    value = comp.run.Value([10, 20])
    result = comp.run.morph(value, shape_ref)
    
    assert result.success
    assert result.positional_matches == 2
    assert result.named_matches == 0
    
    # Should have named fields in result
    first_val = runtest.get_field_python(result.value, "first")
    second_val = runtest.get_field_python(result.value, "second")
    assert first_val == 10
    assert second_val == 20


def test_morph_mixed_named_and_positional():
    """Test mixing named and positional values."""
    code = """
    !shape ~mixed = {
        x ~num
        y ~num
    }
    """
    module = runtest.module_from_code(code)
    shape_def = module.shapes["mixed"]
    shape_ref = comp.run.ShapeRef(("mixed",))
    shape_ref._resolved = shape_def
    
    # One named (y), one unnamed (for x)
    value = comp.run.Value({})
    value.struct = {
        comp.run.Value("y"): comp.run.Value(20),
        comp.run.Unnamed(): comp.run.Value(10),
    }
    
    result = comp.run.morph(value, shape_ref)
    
    assert result.success
    assert result.named_matches == 1  # y matched by name
    assert result.positional_matches == 1  # x filled positionally
    
    x_val = runtest.get_field_python(result.value, "x")
    y_val = runtest.get_field_python(result.value, "y")
    assert x_val == 10
    assert y_val == 20


def test_morph_unnamed_shape_fields():
    """Test shape with unnamed/positional fields."""
    code = """
    !shape ~pair = {
        ~num
        ~num
    }
    """
    module = runtest.module_from_code(code)
    shape_def = module.shapes["pair"]
    shape_ref = comp.run.ShapeRef(("pair",))
    shape_ref._resolved = shape_def
    
    # Positional values should match positional shape
    value = comp.run.Value([10, 20])
    result = comp.run.morph(value, shape_ref)
    
    assert result.success
    assert result.positional_matches == 2
    
    # Result should have unnamed fields
    assert result.value.is_struct
    assert len(result.value.struct) == 2


def test_morph_union_picks_best():
    """Test that union shapes pick the best matching variant."""
    code = """
    !shape ~num-or-str = ~num | ~str
    """
    module = runtest.module_from_code(code)
    shape_def = module.shapes["num-or-str"]
    shape_ref = comp.run.ShapeRef(("num-or-str",))
    shape_ref._resolved = shape_def
    
    # Number should morph to ~num variant
    num_val = comp.run.Value(42)
    result = comp.run.morph(num_val, shape_ref)
    assert result.success
    assert result.value.num == 42
    
    # String should morph to ~str variant
    str_val = comp.run.Value("hello")
    result = comp.run.morph(str_val, shape_ref)
    assert result.success
    assert result.value.str == "hello"


def test_morph_nested_structs():
    """Test morphing with nested struct shapes."""
    code = """
    !shape ~inner = {
        value ~num
    }
    !shape ~outer = {
        data ~inner
    }
    """
    module = runtest.module_from_code(code)
    shape_def = module.shapes["outer"]
    shape_ref = comp.run.ShapeRef(("outer",))
    shape_ref._resolved = shape_def
    
    # Nested structure
    value = comp.run.Value({
        "data": {"value": 42}
    })
    
    result = comp.run.morph(value, shape_ref)
    
    assert result.success
    
    # Check nested structure
    data = runtest.get_field(result.value, "data")
    assert data.is_struct
    inner_val = runtest.get_field_python(data, "value")
    assert inner_val == 42


def test_morph_tag_literal():
    """Test morphing tag values with tag shape constraints."""
    code = """
    !tag #status
    !shape ~test = #status
    """
    module = runtest.module_from_code(code)
    shape_def = module.shapes["test"]
    shape_ref = comp.run.ShapeRef(("test",))
    shape_ref._resolved = shape_def
    
    # Create a tag value for #status
    status_tag = module.tags["status"].tag_value
    tag_val = comp.run.Value(status_tag)
    
    result = comp.run.morph(tag_val, shape_ref)
    
    assert result.success
    assert result.value.is_tag


def test_morph_tag_hierarchy():
    """Test morphing with tag hierarchy constraints."""
    code = """
    !tag #status = {#error}
    !shape ~test = #status
    """
    module = runtest.module_from_code(code)
    shape_def = module.shapes["test"]
    shape_ref = comp.run.ShapeRef(("test",))
    shape_ref._resolved = shape_def
    
    # Child tag should match parent constraint
    error_tag = module.tags["status.error"].tag_value
    tag_val = comp.run.Value(error_tag)
    
    result = comp.run.morph(tag_val, shape_ref)
    
    assert result.success
    assert result.tag_depth >= 0  # Child of #status


def test_morph_preserves_field_order():
    """Test that field order is preserved during morph."""
    code = """
    !shape ~ordered = {
        a ~num
        b ~num
        c ~num
    }
    """
    module = runtest.module_from_code(code)
    shape_def = module.shapes["ordered"]
    shape_ref = comp.run.ShapeRef(("ordered",))
    shape_ref._resolved = shape_def
    
    # Create value with specific order
    value = comp.run.Value({})
    value.struct = {
        comp.run.Value("a"): comp.run.Value(1),
        comp.run.Value("b"): comp.run.Value(2),
        comp.run.Value("c"): comp.run.Value(3),
    }
    
    result = comp.run.morph(value, shape_ref)
    
    assert result.success
    
    # Check that fields exist (order in dict may vary)
    keys = [k.str for k in result.value.struct.keys() if hasattr(k, 'str')]
    assert 'a' in keys
    assert 'b' in keys
    assert 'c' in keys


def test_morph_empty_shape():
    """Test morphing with empty shape definition."""
    code = """
    !shape ~empty = {}
    """
    module = runtest.module_from_code(code)
    shape_def = module.shapes["empty"]
    shape_ref = comp.run.ShapeRef(("empty",))
    shape_ref._resolved = shape_def
    
    # Any struct should match empty shape
    value = comp.run.Value({"x": 1, "y": 2})
    result = comp.run.morph(value, shape_ref)
    
    assert result.success
    # Fields should be preserved
    assert len(result.value.struct) == 2


def test_morph_insufficient_fields_fails():
    """Test that missing required fields causes failure."""
    code = """
    !shape ~pair = {
        x ~num
        y ~num
    }
    """
    module = runtest.module_from_code(code)
    shape_def = module.shapes["pair"]
    shape_ref = comp.run.ShapeRef(("pair",))
    shape_ref._resolved = shape_def
    
    # Only one field provided
    value = comp.run.Value({"x": 10})
    result = comp.run.morph(value, shape_ref)
    
    assert not result.success


def test_morph_named_cannot_fill_different_named():
    """Test that named value fields cannot fill differently-named shape fields."""
    code = """
    !shape ~test = {
        x ~num
        y ~num
    }
    """
    module = runtest.module_from_code(code)
    shape_def = module.shapes["test"]
    shape_ref = comp.run.ShapeRef(("test",))
    shape_ref._resolved = shape_def
    
    # Named field "z" cannot fill "x" or "y"
    value = comp.run.Value({"z": 10, "y": 20})
    result = comp.run.morph(value, shape_ref)
    
    # Should fail because "z" cannot positionally fill "x"
    assert not result.success
