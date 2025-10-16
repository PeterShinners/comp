"""Tests for shape morphing operations."""

import comp
from decimal import Decimal


def test_basic_structure_morph():
    """Test basic structure morphing with named fields."""
    builtin = comp.get_builtin_module()
    module = comp.Module()
    module.define_shape(["user"], [
        comp.ShapeField(name="name", shape=builtin.shapes["str"]),
        comp.ShapeField(name="age", shape=builtin.shapes["num"]),
    ])

    user_shape = module.shapes["user"]
    data = comp.Value({
        comp.Value("name"): comp.Value("Alice"),
        comp.Value("age"): comp.Value(Decimal("30"))
    })

    result = comp.morph(data, user_shape)

    assert result.success
    assert result.named_matches == 2
    assert result.value.is_struct
    assert len(result.value.data) == 2


def test_morph_with_defaults():
    """Test that morph applies default values for missing fields."""
    builtin = comp.get_builtin_module()
    module = comp.Module()
    module.define_shape(["config"], [
        comp.ShapeField(name="host", shape=builtin.shapes["str"]),
        comp.ShapeField(name="port", shape=builtin.shapes["num"]),
        comp.ShapeField(name="timeout", shape=builtin.shapes["num"], default=comp.Value(Decimal("30"))),
    ])

    config_shape = module.shapes["config"]
    data = comp.Value({
        comp.Value("host"): comp.Value("localhost"),
        comp.Value("port"): comp.Value(Decimal("8080"))
    })

    result = comp.morph(data, config_shape)

    assert result.success
    assert len(result.value.data) == 3

    # Check timeout was added with default value
    timeout_key = comp.Value("timeout")
    timeout_found = False
    for k, v in result.value.data.items():
        if hasattr(k, 'data') and k.data == "timeout":
            assert v.data == Decimal("30")
            timeout_found = True
    assert timeout_found


def test_morph_missing_required_field():
    """Test that morph fails when required field is missing."""
    builtin = comp.get_builtin_module()
    module = comp.Module()
    module.define_shape(["user"], [
        comp.ShapeField(name="name", shape=builtin.shapes["str"]),
        comp.ShapeField(name="email", shape=builtin.shapes["str"]),  # Required, no default
    ])

    user_shape = module.shapes["user"]
    data = comp.Value({
        comp.Value("name"): comp.Value("Alice")
        # Missing 'email'
    })

    result = comp.morph(data, user_shape)

    assert not result.success


def test_morph_type_mismatch():
    """Test that morph fails on type mismatch."""
    builtin = comp.get_builtin_module()
    module = comp.Module()
    module.define_shape(["user"], [
        comp.ShapeField(name="age", shape=builtin.shapes["num"]),
    ])

    user_shape = module.shapes["user"]
    data = comp.Value({
        comp.Value("age"): comp.Value("not a number")
    })

    result = comp.morph(data, user_shape)

    assert not result.success


def test_morph_allows_extra_fields():
    """Test that normal morph allows extra fields not in shape."""
    builtin = comp.get_builtin_module()
    module = comp.Module()
    module.define_shape(["user"], [
        comp.ShapeField(name="name", shape=builtin.shapes["str"]),
    ])

    user_shape = module.shapes["user"]
    data = comp.Value({
        comp.Value("name"): comp.Value("Alice"),
        comp.Value("extra"): comp.Value("allowed")
    })

    result = comp.morph(data, user_shape)

    assert result.success
    assert len(result.value.data) == 2  # Both fields preserved


def test_strong_morph_rejects_extra_fields():
    """Test that strong morph fails when extra fields present."""
    builtin = comp.get_builtin_module()
    module = comp.Module()
    module.define_shape(["user"], [
        comp.ShapeField(name="name", shape=builtin.shapes["str"]),
    ])

    user_shape = module.shapes["user"]
    data = comp.Value({
        comp.Value("name"): comp.Value("Alice"),
        comp.Value("extra"): comp.Value("not allowed")
    })

    result = comp.strong_morph(data, user_shape)

    assert not result.success


def test_strong_morph_with_defaults():
    """Test strong morph applies defaults and succeeds when no extra fields."""
    builtin = comp.get_builtin_module()
    module = comp.Module()
    module.define_shape(["config"], [
        comp.ShapeField(name="host", shape=builtin.shapes["str"]),
        comp.ShapeField(name="port", shape=builtin.shapes["num"]),
        comp.ShapeField(name="timeout", shape=builtin.shapes["num"], default=comp.Value(Decimal("30"))),
    ])

    config_shape = module.shapes["config"]
    data = comp.Value({
        comp.Value("host"): comp.Value("localhost"),
        comp.Value("port"): comp.Value(Decimal("3000"))
    })

    result = comp.strong_morph(data, config_shape)

    assert result.success
    assert len(result.value.data) == 3


def test_weak_morph_allows_missing():
    """Test weak morph succeeds with missing fields (no defaults)."""
    builtin = comp.get_builtin_module()
    module = comp.Module()
    module.define_shape(["user"], [
        comp.ShapeField(name="name", shape=builtin.shapes["str"]),
        comp.ShapeField(name="email", shape=builtin.shapes["str"]),
        comp.ShapeField(name="age", shape=builtin.shapes["num"], default=comp.Value(Decimal("0"))),
    ])

    user_shape = module.shapes["user"]
    data = comp.Value({
        comp.Value("name"): comp.Value("Alice")
        # Missing 'email' and 'age'
    })

    result = comp.weak_morph(data, user_shape)

    assert result.success
    assert result.named_matches == 1
    # Should NOT have email or age (no defaults in weak morph)
    assert len(result.value.data) == 1


def test_weak_morph_validates_present_fields():
    """Test weak morph validates types of present fields."""
    builtin = comp.get_builtin_module()
    module = comp.Module()
    module.define_shape(["user"], [
        comp.ShapeField(name="name", shape=builtin.shapes["str"]),
        comp.ShapeField(name="age", shape=builtin.shapes["num"]),
    ])

    user_shape = module.shapes["user"]
    data = comp.Value({
        comp.Value("name"): comp.Value(Decimal("123"))  # Wrong type
    })

    result = comp.weak_morph(data, user_shape)

    # Should succeed but exclude the invalid field
    assert result.success
    assert result.named_matches == 0
    assert len(result.value.data) == 0


def test_mask_filters_to_intersection():
    """Test mask returns only fields in both value and shape."""
    builtin = comp.get_builtin_module()
    module = comp.Module()
    module.define_shape(["test"], [
        comp.ShapeField(name="user", shape=builtin.shapes["str"]),
        comp.ShapeField(name="session", shape=builtin.shapes["str"]),
    ])

    test_shape = module.shapes["test"]
    data = comp.Value({
        comp.Value("user"): comp.Value("alice"),
        comp.Value("session"): comp.Value("abc123"),
        comp.Value("debug"): comp.Value("true"),
        comp.Value("admin"): comp.Value("secret")
    })

    result = comp.mask(data, test_shape)

    assert result.success
    assert result.named_matches == 2
    assert len(result.value.data) == 2

    # Check only user and session remain
    field_names = {k.data for k in result.value.data.keys() if hasattr(k, 'data')}
    assert field_names == {"user", "session"}


def test_mask_with_missing_fields():
    """Test mask with missing fields (no defaults applied)."""
    builtin = comp.get_builtin_module()
    module = comp.Module()
    module.define_shape(["test"], [
        comp.ShapeField(name="user", shape=builtin.shapes["str"]),
        comp.ShapeField(name="session", shape=builtin.shapes["str"]),
        comp.ShapeField(name="timeout", shape=builtin.shapes["num"], default=comp.Value(Decimal("30"))),
    ])

    test_shape = module.shapes["test"]
    data = comp.Value({
        comp.Value("user"): comp.Value("bob")
        # Missing session and timeout
    })

    result = comp.mask(data, test_shape)

    assert result.success
    assert result.named_matches == 1
    assert len(result.value.data) == 1
    # Should NOT have timeout (mask doesn't apply defaults)


def test_strict_mask_validates_exactly():
    """Test strict mask applies defaults and rejects extra fields."""
    builtin = comp.get_builtin_module()
    module = comp.Module()
    module.define_shape(["test"], [
        comp.ShapeField(name="host", shape=builtin.shapes["str"]),
        comp.ShapeField(name="port", shape=builtin.shapes["num"]),
        comp.ShapeField(name="timeout", shape=builtin.shapes["num"], default=comp.Value(Decimal("30"))),
    ])

    test_shape = module.shapes["test"]

    # Test success case with defaults
    data1 = comp.Value({
        comp.Value("host"): comp.Value("localhost"),
        comp.Value("port"): comp.Value(Decimal("8080"))
    })
    result1 = comp.strict_mask(data1, test_shape)
    assert result1.success
    assert len(result1.value.data) == 3

    # Test failure case with extra field
    data2 = comp.Value({
        comp.Value("host"): comp.Value("localhost"),
        comp.Value("port"): comp.Value(Decimal("8080")),
        comp.Value("extra"): comp.Value("not allowed")
    })
    result2 = comp.strict_mask(data2, test_shape)
    assert not result2.success


def test_morph_positional_fields():
    """Test morphing with positional (unnamed) fields."""
    builtin = comp.get_builtin_module()
    module = comp.Module()
    module.define_shape(["pair"], [
        comp.ShapeField(name=None, shape=builtin.shapes["num"]),  # Positional
        comp.ShapeField(name=None, shape=builtin.shapes["num"]),  # Positional
    ])

    pair_shape = module.shapes["pair"]
    data = comp.Value({
        comp.Unnamed(): comp.Value(Decimal("5")),
        comp.Unnamed(): comp.Value(Decimal("10"))
    })

    result = comp.morph(data, pair_shape)

    assert result.success
    assert result.positional_matches == 2


def test_morph_primitive_unwrapping():
    """Test that morphing primitives unwraps correctly."""
    builtin = comp.get_builtin_module()
    num_shape = builtin.shapes["num"]

    # Test direct number
    data = comp.Value(Decimal("42"))
    result = comp.morph(data, num_shape)

    assert result.success
    assert result.value.is_number
    assert result.value.data == Decimal("42")


def test_morph_mixed_named_and_unnamed_fields():
    """Test morphing with mixed named and unnamed fields.
    
    Phase 2.5 of morphing should pair remaining unnamed value fields
    with unfilled named shape fields in definition order.
    Example: {a=1 2 c=3} ~{a~num b~num c~num} should fill b=2
    """
    builtin = comp.get_builtin_module()
    module = comp.Module()
    module.define_shape(["test"], [
        comp.ShapeField(name="a", shape=builtin.shapes["num"]),
        comp.ShapeField(name="b", shape=builtin.shapes["num"]),
        comp.ShapeField(name="c", shape=builtin.shapes["num"]),
    ])

    test_shape = module.shapes["test"]
    
    # Input: {a=1 2 c=3} where unnamed 2 should fill field b
    data = comp.Value({
        comp.Value("a"): comp.Value(Decimal("1")),
        comp.Unnamed(): comp.Value(Decimal("2")),
        comp.Value("c"): comp.Value(Decimal("3"))
    })

    result = comp.morph(data, test_shape)

    assert result.success, "Morph should succeed with mixed named/unnamed fields"
    assert result.named_matches == 3, "Should match all 3 named fields (2 direct + 1 from unnamed)"
    
    # Check that b was filled with the unnamed value 2
    b_value = result.value.struct.get(comp.Value("b"))
    assert b_value is not None, "Field 'b' should be present"
    assert b_value.data == Decimal("2"), "Field 'b' should have value 2 from unnamed field"
    
    # Check a and c are still present
    a_value = result.value.struct.get(comp.Value("a"))
    assert a_value is not None and a_value.data == Decimal("1")
    c_value = result.value.struct.get(comp.Value("c"))
    assert c_value is not None and c_value.data == Decimal("3")
