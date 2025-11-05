"""Tests for shape morphing operations."""

import comp
import comptest


def test_morph_with_defaults():
    """Test that morph applies default values for missing fields."""
    shape = comptest.make_shape("config",
        ("host", "str", None),
        ("port", "num", None),
        ("timeout", "num", 30),
    )
    data = comp.Value({"host": "localhost", "port": 8080})
    result = comp.morph(data, shape)
    assert result.success
    comptest.assert_value(result.value, timeout=30)
    assert len(result.value.data) == 3


def test_morph_missing_required_field():
    """Test that morph fails when required field is missing."""
    shape = comptest.make_shape("user",
        ("name", "str", None),
        ("email", "str", None),
    )
    data = comp.Value({"name": "Alice"})
    result = comp.morph(data, shape)
    assert not result.success
    assert result.value is None


def test_morph_type_mismatch():
    """Test that morph fails on type mismatch."""
    shape = comptest.make_shape("user",
        ("age", "num", None),
    )
    data = comp.Value({"age": "not a number"})
    result = comp.morph(data, shape)
    assert not result.success
    assert result.value is None


def test_morph_allows_extra_fields():
    """Test that normal morph allows extra fields not in shape."""
    shape = comptest.make_shape("user",
        ("name", "str", None),
    )
    data = comp.Value({"name": "Alice", "extra": "allowed"})
    result = comp.morph(data, shape)
    assert result.success
    comptest.assert_value(result.value, name="Alice", extra="allowed")
    assert len(result.value.data) == 2  # Both fields preserved


def test_strong_morph_rejects_extra_fields():
    """Test that strong morph fails when extra fields present."""
    shape = comptest.make_shape("user",
        ("name", "str", None),
    )
    data = comp.Value({"name": "Alice", "extra": "not allowed"})
    result = comp.strong_morph(data, shape)
    assert not result.success
    assert result.value is None


def test_strong_morph_with_defaults():
    """Test strong morph applies defaults and succeeds when no extra fields."""
    shape = comptest.make_shape("config",
        ("host", "str", None),
        ("port", "num", None),
        ("timeout", "num", 30),
    )
    data = comp.Value({"host": "localhost", "port": 3000})
    result = comp.strong_morph(data, shape)
    assert result.success
    comptest.assert_value(result.value, host="localhost", port=3000, timeout=30)
    assert len(result.value.data) == 3


def test_weak_filters_to_intersection():
    """Test mask returns only fields in both value and shape."""
    shape = comptest.make_shape("config",
        ("user", "str", None),
        ("session", "str", None),
    )
    data = comp.Value({"user": "alice",
                      "session": "abc123",
                      "debug": True,
                      "admin": "secret"})
    result = comp.weak_morph(data, shape)
    assert result.success
    comptest.assert_value(result.value, user="alice", session="abc123")
    assert len(result.value.data) == 2


def test_weak_with_missing_fields():
    """Test mask with missing fields (no defaults applied)."""
    shape = comptest.make_shape("config",
        ("user", "str", None),
        ("session", "str", None),
        ("timeout", "num", 30),
    )
    data = comp.Value({"user": "bob"})
    result = comp.weak_morph(data, shape)
    assert result.success
    comptest.assert_value(result.value, user="bob")
    assert len(result.value.data) == 1
    # Should NOT have timeout (weak morph doesn't apply defaults)


def test_morph_positional_fields():
    """Test morphing with positional (unnamed) fields."""
    shape = comptest.make_shape("config",
        (None, "num", None),
        (None, "num", None),
    )

    data = comp.Value([5, 10])
    result = comp.morph(data, shape)
    assert result.success
    assert len(result.value.data) == 2
    # Check if to_python() returns list (for unnamed fields) or dict
    py_value = result.value.to_python()
    if isinstance(py_value, list):
        assert py_value == [5, 10]
    else:
        assert list(py_value.values()) == [5, 10]


def test_morph_primitive_unwrapping():
    """Test that morphing primitives unwraps correctly."""
    builtin = comp.builtin.get_builtin_module()
    num_shape = builtin.shapes["num"]

    # Test direct number
    data = comp.Value(42)
    result = comp.morph(data, num_shape)

    assert result.success
    assert result.value.is_number
    assert result.value.data == 42


def test_morph_mixed_named_and_unnamed_fields():
    """Test morphing with mixed named and unnamed fields.
    
    Phase 3 of morphing should pair remaining unnamed value fields
    with unfilled named shape fields in definition order.
    Example: {a=1 2 c=3} ~{a~num b~num c~num} should fill b=2
    """
    shape = comptest.make_shape("config",
        ("a", "num", None),
        ("b", "num", None),
        ("c", "num", None),
    )
    # {a=1 2 c=3}
    data = comp.Value({"a": 1, comp.Unnamed(): 2, "c": 3})
    result = comp.morph(data, shape)
    assert result.success
    comptest.assert_value(result.value, {"a": 1, "b": 2, "c": 3})

    # {1 2 b=3}
    data = comp.Value({comp.Unnamed(): 1, comp.Unnamed(): 2, "b": 3})
    result = comp.morph(data, shape)
    assert result.success
    comptest.assert_value(result.value, {"a": 1, "b": 3, "c": 2})

