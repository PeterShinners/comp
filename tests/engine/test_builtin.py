"""Tests for the builtin module system."""

import comp.engine as comp


def test_builtin_module_creation():
    """Verify builtin module is created with all expected definitions."""
    builtin = comp.get_builtin_module()

    # Check that we got a Module
    assert isinstance(builtin, comp.Module)
    assert builtin.is_builtin is True


def test_builtin_core_tags():
    """Verify core tags are defined in builtin module."""
    builtin = comp.get_builtin_module()

    # Boolean tags
    assert "true" in builtin.tags
    assert "false" in builtin.tags

    # Failure tags
    assert "fail" in builtin.tags
    assert "fail.runtime" in builtin.tags
    assert "fail.type" in builtin.tags
    assert "fail.div_zero" in builtin.tags
    assert "fail.not_found" in builtin.tags
    assert "fail.ambiguous" in builtin.tags


def test_builtin_primitive_shapes():
    """Verify primitive shapes are defined in builtin module."""
    builtin = comp.get_builtin_module()

    assert "num" in builtin.shapes
    assert "str" in builtin.shapes
    assert "bool" in builtin.shapes
    assert "any" in builtin.shapes
    assert "tag" in builtin.shapes


def test_builtin_core_functions():
    """Verify core functions are defined in builtin module."""
    builtin = comp.get_builtin_module()

    assert "double" in builtin.functions
    assert "print" in builtin.functions
    assert "identity" in builtin.functions
    assert "add" in builtin.functions
    assert "wrap" in builtin.functions


def test_regular_modules_get_builtin_namespace():
    """Verify regular modules automatically have builtin namespace."""
    builtin = comp.get_builtin_module()
    module = comp.Module()

    assert "builtin" in module.namespaces
    assert module.namespaces["builtin"] is builtin
    assert module.is_builtin is False


def test_builtin_doesnt_reference_itself():
    """Verify builtin module doesn't have itself as namespace (avoid recursion)."""
    builtin = comp.get_builtin_module()

    assert "builtin" not in builtin.namespaces


def test_lookup_from_builtin_namespace():
    """Test that we can look up builtin definitions via namespace."""
    module = comp.Module()

    # Functions
    double_funcs = module.lookup_function_with_namespace(["double"], "builtin")
    assert double_funcs is not None
    assert len(double_funcs) > 0

    # Tags
    true_tag = module.lookup_tag_with_namespace(["true"], "builtin")
    assert true_tag is not None

    # Shapes
    num_shape = module.lookup_shape_with_namespace(["num"], "builtin")
    assert num_shape is not None


def test_fallback_to_builtin_namespace():
    """Test that lookups fallback to builtin namespace when not found locally."""
    module = comp.Module()

    # Function not in local module should fallback to builtin
    double_fallback = module.lookup_function_with_namespace(["double"], None)
    assert double_fallback is not None

    # Tag not in local module should fallback to builtin
    true_fallback = module.lookup_tag_with_namespace(["true"], None)
    assert true_fallback is not None

    # Shape not in local module should fallback to builtin
    num_fallback = module.lookup_shape_with_namespace(["num"], None)
    assert num_fallback is not None


def test_builtin_singleton():
    """Verify get_builtin_module returns the same instance."""
    builtin1 = comp.get_builtin_module()
    builtin2 = comp.get_builtin_module()

    assert builtin1 is builtin2


def test_local_definitions_override_builtin():
    """Verify local definitions take precedence over builtin."""
    module = comp.Module()

    # Define local function with same name as builtin
    module.define_function(["double"], body=None, doc="Local double")

    # Local lookup should find local version
    local_funcs = module.lookup_function(["double"])
    assert local_funcs is not None
    assert local_funcs[0].doc == "Local double"

    # Explicit builtin namespace should still find builtin version
    builtin_funcs = module.lookup_function_with_namespace(["double"], "builtin")
    assert builtin_funcs is not None
    assert builtin_funcs[0].doc != "Local double"
