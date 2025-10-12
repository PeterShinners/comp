"""Tests for strong morph (~*) and weak morph (~?) operations."""

import comp
import runtest


def test_strong_morph_success_with_defaults():
    """Test strong morph applies defaults and succeeds when no extra fields."""
    code = "!shape ~config = {host ~str port ~num timeout ~num = 30}"
    module = runtest.module_from_code(code)
    shape_def = module.shapes["config"]
    shape_ref = comp.run.ShapeRef(("config",))
    shape_ref._resolved = shape_def

    # Perfect match with defaults
    value = comp.run.Value({"host": "localhost", "port": 3000})
    result = comp.run.strong_morph(value, shape_ref)

    assert result.success
    assert comp.run.Value("host") in result.value.struct
    assert comp.run.Value("port") in result.value.struct
    assert comp.run.Value("timeout") in result.value.struct
    assert result.value.struct[comp.run.Value("timeout")].num == 30


def test_strong_morph_fails_with_extra_fields():
    """Test strong morph fails when extra fields present."""
    code = "!shape ~config = {host ~str port ~num}"
    module = runtest.module_from_code(code)
    shape_def = module.shapes["config"]
    shape_ref = comp.run.ShapeRef(("config",))
    shape_ref._resolved = shape_def

    # Has extra field 'timeout'
    value = comp.run.Value({"host": "localhost", "port": 3000, "timeout": 30})
    result = comp.run.strong_morph(value, shape_ref)

    assert not result.success


def test_strong_morph_fails_with_missing_required():
    """Test strong morph fails when required fields missing."""
    code = "!shape ~config = {host ~str port ~num}"
    module = runtest.module_from_code(code)
    shape_def = module.shapes["config"]
    shape_ref = comp.run.ShapeRef(("config",))
    shape_ref._resolved = shape_def

    # Missing required field 'port'
    value = comp.run.Value({"host": "localhost"})
    result = comp.run.strong_morph(value, shape_ref)

    assert not result.success


def test_strong_morph_accepts_exact_match():
    """Test strong morph succeeds with exact field match."""
    code = "!shape ~point = {x ~num y ~num}"
    module = runtest.module_from_code(code)
    shape_def = module.shapes["point"]
    shape_ref = comp.run.ShapeRef(("point",))
    shape_ref._resolved = shape_def

    # Exact match
    value = comp.run.Value({"x": 1, "y": 2})
    result = comp.run.strong_morph(value, shape_ref)

    assert result.success
    assert result.value.struct[comp.run.Value("x")].num == 1
    assert result.value.struct[comp.run.Value("y")].num == 2


def test_strong_morph_type_mismatch_fails():
    """Test strong morph fails on type mismatch."""
    code = "!shape ~config = {port ~num}"
    module = runtest.module_from_code(code)
    shape_def = module.shapes["config"]
    shape_ref = comp.run.ShapeRef(("config",))
    shape_ref._resolved = shape_def

    # Wrong type for 'port'
    value = comp.run.Value({"port": "not-a-number"})
    result = comp.run.strong_morph(value, shape_ref)

    assert not result.success


def test_weak_morph_allows_missing_fields():
    """Test weak morph succeeds with missing fields (no defaults)."""
    code = "!shape ~user = {name ~str email ~str age ~num = 0}"
    module = runtest.module_from_code(code)
    shape_def = module.shapes["user"]
    shape_ref = comp.run.ShapeRef(("user",))
    shape_ref._resolved = shape_def

    # Only 'name' present, missing 'email' and 'age'
    value = comp.run.Value({"name": "Alice"})
    result = comp.run.weak_morph(value, shape_ref)

    assert result.success
    assert comp.run.Value("name") in result.value.struct
    # Should NOT have email or age (no defaults applied)
    assert comp.run.Value("email") not in result.value.struct
    assert comp.run.Value("age") not in result.value.struct


def test_weak_morph_ignores_extra_fields():
    """Test weak morph ignores extra fields."""
    code = "!shape ~user = {name ~str}"
    module = runtest.module_from_code(code)
    shape_def = module.shapes["user"]
    shape_ref = comp.run.ShapeRef(("user",))
    shape_ref._resolved = shape_def

    # Extra field 'age' should be ignored
    value = comp.run.Value({"name": "Alice", "age": 30})
    result = comp.run.weak_morph(value, shape_ref)

    assert result.success
    assert comp.run.Value("name") in result.value.struct
    # Extra field should be ignored (not in result)
    assert comp.run.Value("age") not in result.value.struct


def test_weak_morph_validates_present_fields():
    """Test weak morph validates types of present fields."""
    code = "!shape ~user = {name ~str age ~num}"
    module = runtest.module_from_code(code)
    shape_def = module.shapes["user"]
    shape_ref = comp.run.ShapeRef(("user",))
    shape_ref._resolved = shape_def

    # 'name' present but wrong type
    value = comp.run.Value({"name": 123})
    result = comp.run.weak_morph(value, shape_ref)

    # Should fail because present field has wrong type
    assert not result.success


def test_weak_morph_partial_match():
    """Test weak morph with partial field match."""
    code = "!shape ~config = {host ~str port ~num debug ~bool = #false}"
    module = runtest.module_from_code(code)
    shape_def = module.shapes["config"]
    shape_ref = comp.run.ShapeRef(("config",))
    shape_ref._resolved = shape_def

    # Only host and port, missing debug
    value = comp.run.Value({"host": "localhost", "port": 3000})
    result = comp.run.weak_morph(value, shape_ref)

    assert result.success
    assert comp.run.Value("host") in result.value.struct
    assert comp.run.Value("port") in result.value.struct
    # No default for debug (weak morph doesn't add defaults)
    assert comp.run.Value("debug") not in result.value.struct


def test_weak_morph_empty_struct():
    """Test weak morph with empty struct (all fields missing)."""
    code = "!shape ~user = {name ~str email ~str}"
    module = runtest.module_from_code(code)
    shape_def = module.shapes["user"]
    shape_ref = comp.run.ShapeRef(("user",))
    shape_ref._resolved = shape_def

    # Empty struct - no fields match
    value = comp.run.Value({})
    result = comp.run.weak_morph(value, shape_ref)

    # Should succeed (weak morph allows missing fields)
    assert result.success
    assert len(result.value.struct) == 0


def test_strong_morph_vs_weak_morph_comparison():
    """Compare strong and weak morph behavior on same data."""
    code = "!shape ~user = {name ~str email ~str age ~num = 0}"
    module = runtest.module_from_code(code)
    shape_def = module.shapes["user"]
    shape_ref = comp.run.ShapeRef(("user",))
    shape_ref._resolved = shape_def

    # Partial data with extra field
    value = comp.run.Value({"name": "Alice", "extra": "data"})

    # Strong morph should fail (extra field)
    strong_result = comp.run.strong_morph(value, shape_ref)
    assert not strong_result.success

    # Weak morph should succeed (ignores extra, allows missing)
    weak_result = comp.run.weak_morph(value, shape_ref)
    assert weak_result.success
    assert comp.run.Value("name") in weak_result.value.struct
    assert comp.run.Value("extra") not in weak_result.value.struct
    assert comp.run.Value("email") not in weak_result.value.struct
    assert comp.run.Value("age") not in weak_result.value.struct


def test_normal_vs_strong_vs_weak_defaults():
    """Compare how normal, strong, and weak morph handle defaults."""
    code = "!shape ~config = {host ~str = \"localhost\" port ~num = 8080}"
    module = runtest.module_from_code(code)
    shape_def = module.shapes["config"]
    shape_ref = comp.run.ShapeRef(("config",))
    shape_ref._resolved = shape_def

    # Empty struct
    value = comp.run.Value({})

    # Normal morph applies defaults
    normal_result = comp.run.morph(value, shape_ref)
    assert normal_result.success
    assert len(normal_result.value.struct) == 2

    # Strong morph applies defaults
    strong_result = comp.run.strong_morph(value, shape_ref)
    assert strong_result.success
    assert len(strong_result.value.struct) == 2

    # Weak morph does NOT apply defaults
    weak_result = comp.run.weak_morph(value, shape_ref)
    assert weak_result.success
    assert len(weak_result.value.struct) == 0  # No defaults!


def test_strong_morph_with_nested_shapes():
    """Test strong morph with nested structures.

    Note: Strong morph currently checks extra fields at the top level only.
    Nested structures use normal morph rules (extra fields ignored).
    This keeps the implementation simple and predictable.
    """
    code = """
    !shape ~address = {city ~str zip ~num}
    !shape ~user = {name ~str address ~address}
    """
    module = runtest.module_from_code(code)
    user_shape = module.shapes["user"]
    shape_ref = comp.run.ShapeRef(("user",))
    shape_ref._resolved = user_shape

    # Perfect nested match
    value = comp.run.Value({
        "name": "Alice",
        "address": {"city": "NYC", "zip": 10001}
    })
    result = comp.run.strong_morph(value, shape_ref)

    assert result.success

    # With extra field at TOP level - should fail
    value_extra_top = comp.run.Value({
        "name": "Alice",
        "address": {"city": "NYC", "zip": 10001},
        "extra": "not-allowed"
    })
    result_extra_top = comp.run.strong_morph(value_extra_top, shape_ref)

    # Should fail due to extra field at top level
    assert not result_extra_top.success

    # With extra field in NESTED struct - currently uses normal morph rules
    value_extra_nested = comp.run.Value({
        "name": "Alice",
        "address": {"city": "NYC", "zip": 10001, "country": "USA"}
    })
    result_extra_nested = comp.run.strong_morph(value_extra_nested, shape_ref)

    # Currently succeeds (nested extra fields use normal morph)
    assert result_extra_nested.success


def test_weak_morph_with_nested_shapes():
    """Test weak morph with nested structures."""
    code = """
    !shape ~address = {city ~str zip ~num country ~str = "USA"}
    !shape ~user = {name ~str address ~address}
    """
    module = runtest.module_from_code(code)
    user_shape = module.shapes["user"]
    shape_ref = comp.run.ShapeRef(("user",))
    shape_ref._resolved = user_shape

    # Partial nested data (missing country)
    value = comp.run.Value({
        "name": "Alice",
        "address": {"city": "NYC"}
    })
    result = comp.run.weak_morph(value, shape_ref)

    # Should succeed (weak morph allows missing)
    assert result.success
    assert comp.run.Value("name") in result.value.struct

    # Check nested struct has city but not zip or country
    address = result.value.struct[comp.run.Value("address")]
    assert address.is_struct
    assert comp.run.Value("city") in address.struct
    assert comp.run.Value("zip") not in address.struct  # Missing, no default
    assert comp.run.Value("country") not in address.struct  # Missing, no default


def test_strong_morph_positional_fields():
    """Test strong morph with positional fields."""
    code = "!shape ~pair = {~num ~num}"
    module = runtest.module_from_code(code)
    shape_def = module.shapes["pair"]
    shape_ref = comp.run.ShapeRef(("pair",))
    shape_ref._resolved = shape_def

    # Create struct with positional fields
    value = comp.run.Value({})
    value.struct[comp.run.Unnamed()] = comp.run.Value(5)
    value.struct[comp.run.Unnamed()] = comp.run.Value(10)

    result = comp.run.strong_morph(value, shape_ref)

    assert result.success


def test_weak_morph_positional_fields():
    """Test weak morph with positional fields."""
    code = "!shape ~triple = {~num ~num ~num}"
    module = runtest.module_from_code(code)
    shape_def = module.shapes["triple"]
    shape_ref = comp.run.ShapeRef(("triple",))
    shape_ref._resolved = shape_def

    # Create struct with only one positional field (partial)
    value = comp.run.Value({})
    value.struct[comp.run.Unnamed()] = comp.run.Value(5)

    result = comp.run.weak_morph(value, shape_ref)

    # Should succeed with partial match
    assert result.success
    assert len([k for k in result.value.struct.keys() if isinstance(k, comp.run.Unnamed)]) == 1
