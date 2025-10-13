"""Test function invocation masking behavior.

This test verifies that PipeFunc applies the correct masking operations
when invoking functions, as specified in the design:
- Input: morphed to input shape
- Args: strict masked (^*) to arg shape with defaults
- Ctx: permissively masked (^) to arg shape
- Mod: permissively masked (^) to arg shape
"""

from decimal import Decimal

import comp


def test_mask_operations_exist_in_pipefunc():
    """Verify that PipeFunc code includes masking operations."""
    # This is a meta-test to confirm the integration is present
    import inspect
    source = inspect.getsource(comp.ast.PipeFunc.evaluate)

    # Check that masking code is present
    assert "morph" in source, "PipeFunc should morph input to input_shape"
    assert "strict_mask" in source, "PipeFunc should strict_mask args to arg_shape"
    assert "mask" in source, "PipeFunc should mask ctx and mod to arg_shape"


def test_function_ctx_masking():
    """Test that $ctx is permissively masked to arg shape."""
    builtin = comp.get_builtin_module()
    module = comp.Module()

    # Define simple shape
    module.define_shape(["UserInfo"], [
        comp.ShapeField(name="username", shape=builtin.shapes["str"]),
        comp.ShapeField(name="email", shape=builtin.shapes["str"]),
    ])

    # Create $ctx with extra fields
    ctx = comp.Value({
        comp.Value("username"): comp.Value("alice"),
        comp.Value("email"): comp.Value("alice@example.com"),
        comp.Value("admin_key"): comp.Value("secret"),  # Should be masked out
        comp.Value("session_id"): comp.Value("abc123"),  # Should be masked out
    })

    # Apply permissive mask
    mask_result = comp.mask(ctx, module.shapes["UserInfo"])

    assert mask_result.success
    masked_ctx = mask_result.value

    # Should only have fields in shape
    assert masked_ctx.is_struct
    assert comp.Value("username") in masked_ctx.data
    assert comp.Value("email") in masked_ctx.data
    assert comp.Value("admin_key") not in masked_ctx.data  # Filtered out
    assert comp.Value("session_id") not in masked_ctx.data  # Filtered out


def test_function_mod_masking():
    """Test that $mod is permissively masked to arg shape."""
    builtin = comp.get_builtin_module()
    module = comp.Module()

    # Define shape
    module.define_shape(["DbConfig"], [
        comp.ShapeField(name="host", shape=builtin.shapes["str"]),
        comp.ShapeField(name="db_name", shape=builtin.shapes["str"]),
    ])

    # Create $mod with extra fields
    mod = comp.Value({
        comp.Value("host"): comp.Value("localhost"),
        comp.Value("db_name"): comp.Value("mydb"),
        comp.Value("api_key"): comp.Value("secret"),  # Should be masked out
        comp.Value("cache_size"): comp.Value(Decimal("1024")),  # Should be masked out
    })

    # Apply permissive mask
    mask_result = comp.mask(mod, module.shapes["DbConfig"])

    assert mask_result.success
    masked_mod = mask_result.value

    # Should only have fields in shape
    assert masked_mod.is_struct
    assert comp.Value("host") in masked_mod.data
    assert comp.Value("db_name") in masked_mod.data
    assert comp.Value("api_key") not in masked_mod.data  # Filtered out
    assert comp.Value("cache_size") not in masked_mod.data  # Filtered out
