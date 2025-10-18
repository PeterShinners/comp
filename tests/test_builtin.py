"""Tests for the builtin module system."""

import comp
import comptest


def test_builtin_module_creation():
    """Verify builtin module is created with all expected definitions."""
    builtin = comp.builtin.get_builtin_module()

    # Check that we got a Module
    assert isinstance(builtin, comp.Module)
    assert builtin.is_builtin is True

    # Singleton check
    builtin2 = comp.builtin.get_builtin_module()
    assert builtin is builtin2

    # Non recursive self-reference check
    assert not builtin.namespaces

    # Several expected tags
    assert "true" in builtin.tags
    assert "false" in builtin.tags
    assert "fail" in builtin.tags
    assert "fail.type" in builtin.tags
    assert "fail.not_found" in builtin.tags

    # Several expected shapes
    assert "num" in builtin.shapes
    assert "str" in builtin.shapes
    assert "bool" in builtin.shapes
    assert "any" in builtin.shapes

    # Expected functions, these are placeholders
    assert "print" in builtin.functions


def test_regular_modules_get_builtin_namespace():
    """Verify regular modules automatically have builtin namespace."""
    builtin = comp.builtin.get_builtin_module()
    module = comp.Module()

    assert "builtin" in module.namespaces
    assert module.namespaces["builtin"] is builtin
    assert module.is_builtin is False


def test_builtin_doesnt_reference_itself():
    """Verify builtin module doesn't have itself as namespace (avoid recursion)."""
    builtin = comp.builtin.get_builtin_module()

    assert "builtin" not in builtin.namespaces


def test_lookup_from_builtin_namespace():
    """Test that we can look up builtin definitions via namespace."""
    module = comp.Module()

    # Functions
    double_funcs = module.lookup_function(["double"], namespace="builtin")
    assert double_funcs is not None
    assert len(double_funcs) > 0

    # Tags
    true_tag = module.lookup_tag(["true"], namespace="builtin")
    assert true_tag is not None

    # Shapes
    num_shape = module.lookup_shape(["num"], namespace="builtin")
    assert num_shape is not None


def test_fallback_to_builtin_namespace():
    """Test that lookups fallback to builtin namespace when not found locally."""
    module = comp.Module()

    # Function not in local module should fallback to builtin
    double_fallback = module.lookup_function(["double"], namespace=None)
    assert double_fallback is not None

    # Tag not in local module should fallback to builtin
    true_fallback = module.lookup_tag(["true"], namespace=None)
    assert true_fallback is not None

    # Shape not in local module should fallback to builtin
    num_fallback = module.lookup_shape(["num"], namespace=None)
    assert num_fallback is not None


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
    builtin_funcs = module.lookup_function(["double"], namespace="builtin")
    assert builtin_funcs is not None
    assert builtin_funcs[0].doc != "Local double"


def test_if_with_true_tag():
    """Test [5 |if #true 10 20] → 10"""
    value = comptest.run_func("""
    !func |test ~{} = {
        result = [5 |if #true 10 20]
    }
    """)
    comptest.assert_value(value, result=10)


def test_if_with_false_tag():
    """Test [5 |if #false 10 20] → 20"""
    value = comptest.run_func("""
    !func |test ~{} = {
        result = [5 |if #false 10 20]
    }
    """)
    comptest.assert_value(value, result=20)


def test_if_without_else():
    """Test [5 |if #false 10] → 5 (returns input when no else branch)"""
    value = comptest.run_func("""
    !func |test ~{} = {
        result = [5 |if #false 10]
    }
    """)
    comptest.assert_value(value, result=5)


def test_if_passes_input_to_branches():
    """Test that branches receive $in from pipeline"""
    value = comptest.run_func("""
    !func |test ~{} = {
        result = [5 |if #true {double = $in * 2} {half = $in / 2}]
    }
    """)
    comptest.assert_value(value, result=10)  # 5 * 2
