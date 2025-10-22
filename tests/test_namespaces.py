"""Tests for module namespaces and cross-module references."""

import comp


def test_tag_lookup_with_namespace():
    """Test looking up a tag from an imported namespace."""
    lib_module = comp.Module()
    lib_module.define_tag(["status", "ok"], comp.Value(200))

    main_module = comp.Module()
    main_module.add_namespace("lib", lib_module)

    # Lookup with explicit namespace
    tag_def = main_module.lookup_tag(["status", "ok"], namespace="lib")
    assert tag_def.value.data == 200


def test_tag_lookup_fallback_to_namespace():
    """Test that tags fall back to checking namespaces."""
    lib_module = comp.Module()
    lib_module.define_tag(["status", "ok"], comp.Value(200))

    main_module = comp.Module()
    main_module.add_namespace("lib", lib_module)

    # Lookup without namespace should find it in lib
    tag_def = main_module.lookup_tag(["status", "ok"])
    assert tag_def.value.data == 200


def test_tag_local_overrides_namespace():
    """Test that local tags override namespace tags."""
    lib_module = comp.Module()
    lib_module.define_tag(["status", "ok"], comp.Value(200))

    main_module = comp.Module()
    main_module.define_tag(["status", "ok"], comp.Value(999))
    main_module.add_namespace("lib", lib_module)

    # Lookup without namespace should find local first
    tag_def = main_module.lookup_tag(["status", "ok"])
    assert tag_def.value.data == 999

    # Explicit namespace should find lib version
    tag_def_lib = main_module.lookup_tag(["status", "ok"], namespace="lib")
    assert tag_def_lib.value.data == 200


def test_shape_lookup_with_namespace():
    """Test looking up a shape from an imported namespace."""
    lib_module = comp.Module()
    lib_module.define_shape(["point"], [
        comp.ShapeField(name="x"),
        comp.ShapeField(name="y"),
    ])

    main_module = comp.Module()
    main_module.add_namespace("lib", lib_module)

    # Lookup with explicit namespace
    shape_def = main_module.lookup_shape(["point"], namespace="lib")
    assert shape_def.name == "point"


def test_shape_lookup_fallback_to_namespace():
    """Test that shapes fall back to checking namespaces."""
    lib_module = comp.Module()
    lib_module.define_shape(["point"], [comp.ShapeField(name="x")])

    main_module = comp.Module()
    main_module.add_namespace("lib", lib_module)

    # Lookup without namespace should find it in lib
    shape_def = main_module.lookup_shape(["point"])
    assert shape_def.name == "point"


def test_function_lookup_with_namespace():
    """Test looking up a function from an imported namespace."""
    lib_module = comp.Module()
    lib_module.define_function(["double"], body=None)

    main_module = comp.Module()
    main_module.add_namespace("lib", lib_module)

    # Lookup with explicit namespace
    func_def = main_module.lookup_function(["double"], namespace="lib")
    assert func_def is not None


def test_function_lookup_fallback_to_namespace():
    """Test that functions fall back to checking namespaces."""
    lib_module = comp.Module()
    lib_module.define_function(["helper"], body=None)

    main_module = comp.Module()
    main_module.add_namespace("lib", lib_module)

    # Lookup without namespace should find it in lib
    func_def = main_module.lookup_function(["helper"])
    assert func_def is not None


def test_namespace_not_found():
    """Test referencing a non-existent namespace."""
    main_module = comp.Module()

    # Lookup with namespace that doesn't exist should raise
    try:
        main_module.lookup_tag(["test"], namespace="nonexistent")
        raise AssertionError("Expected ValueError")
    except ValueError:
        pass  # Expected


def test_multiple_namespaces():
    """Test resolving references with multiple imported namespaces."""
    lib1 = comp.Module()
    lib1.define_tag(["status", "ok"], comp.Value(1))

    lib2 = comp.Module()
    lib2.define_tag(["status", "error"], comp.Value(2))

    main_module = comp.Module()
    main_module.add_namespace("lib1", lib1)
    main_module.add_namespace("lib2", lib2)

    # Lookup without namespace should find in namespace
    tag_def = main_module.lookup_tag(["status", "ok"])
    assert tag_def.value.data == 1
