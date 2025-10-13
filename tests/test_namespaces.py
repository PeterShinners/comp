"""Tests for module namespaces and cross-module references."""

import comp


def test_add_namespace():
    """Test adding a namespace to a module."""
    main_module = comp.Module()
    imported_module = comp.Module()

    main_module.add_namespace("lib", imported_module)

    assert "lib" in main_module.namespaces
    assert main_module.namespaces["lib"] is imported_module


def test_tag_reference_with_namespace():
    """Test referencing a tag from an imported namespace."""
    # Create imported module with a tag
    lib_module = comp.Module()
    lib_module.define_tag(["status", "ok"], comp.Value(200))

    # Create main module and import lib
    main_module = comp.Module()
    main_module.add_namespace("lib", lib_module)

    # Create reference with explicit namespace: #ok.status/lib
    tag_ref = comp.ast.TagValueRef(["ok", "status"], namespace="lib")

    class TestNode(comp.ast.ValueNode):
        def evaluate(self, frame):
            tag = yield comp.Compute(tag_ref)
            return tag

        def unparse(self):
            return "test"

    engine = comp.Engine()
    result = engine.run(TestNode(), mod_tags=main_module)

    # Should find the tag from lib namespace and return its value
    assert result.data is not None
    assert result.is_number
    assert result.data == 200


def test_tag_fallback_to_namespace():
    """Test that tags fall back to checking namespaces."""
    # Create imported module with a tag
    lib_module = comp.Module()
    lib_module.define_tag(["status", "ok"], comp.Value(200))

    # Create main module (no local tag) and import lib
    main_module = comp.Module()
    main_module.add_namespace("lib", lib_module)

    # Create reference WITHOUT namespace: #ok.status
    # Should find it in lib since not in main
    tag_ref = comp.ast.TagValueRef(["ok", "status"])

    class TestNode(comp.ast.ValueNode):
        def evaluate(self, frame):
            tag = yield comp.Compute(tag_ref)
            return tag

        def unparse(self):
            return "test"

    engine = comp.Engine()
    result = engine.run(TestNode(), mod_tags=main_module)

    # Should find the tag from lib namespace via fallback
    assert result.data is not None


def test_tag_local_overrides_namespace():
    """Test that local tags override namespace tags."""
    # Create imported module with a tag
    lib_module = comp.Module()
    lib_module.define_tag(["status", "ok"], comp.Value(200))

    # Create main module with same tag (different value)
    main_module = comp.Module()
    main_module.define_tag(["status", "ok"], comp.Value(999))
    main_module.add_namespace("lib", lib_module)

    # Reference without namespace should find local first
    tag_ref = comp.ast.TagValueRef(["ok", "status"])

    class TestNode(comp.ast.ValueNode):
        def evaluate(self, frame):
            tag = yield comp.Compute(tag_ref)
            return tag

        def unparse(self):
            return "test"

    engine = comp.Engine()
    result = engine.run(TestNode(), mod_tags=main_module)

    # Should find local tag (value=999), not lib tag (value=200)
    # Tag references now return the value directly
    assert result.data is not None
    assert result.is_number
    assert result.data == 999


def test_shape_reference_with_namespace():
    """Test referencing a shape from an imported namespace."""
    # Create imported module with a shape
    lib_module = comp.Module()
    lib_module.define_shape(["point"], [
        comp.ShapeField(name="x"),
        comp.ShapeField(name="y"),
    ])

    # Create main module and import lib
    main_module = comp.Module()
    main_module.add_namespace("lib", lib_module)

    # Create reference with explicit namespace: ~point/lib
    shape_ref = comp.ast.ShapeRef(["point"], namespace="lib")

    class TestNode(comp.ast.ValueNode):
        def evaluate(self, frame):
            shape = yield comp.Compute(shape_ref)
            # shape is a ShapeDefinition
            return comp.Value(shape.name if shape else "none")

        def unparse(self):
            return "test"

    engine = comp.Engine()
    result = engine.run(TestNode(), mod_shapes=main_module)

    assert result.to_python() == "point"


def test_shape_fallback_to_namespace():
    """Test that shapes fall back to checking namespaces."""
    # Create imported module with a shape
    lib_module = comp.Module()
    lib_module.define_shape(["point"], [comp.ShapeField(name="x")])

    # Create main module (no local shape) and import lib
    main_module = comp.Module()
    main_module.add_namespace("lib", lib_module)

    # Reference without namespace should find it in lib
    shape_ref = comp.ast.ShapeRef(["point"])

    class TestNode(comp.ast.ValueNode):
        def evaluate(self, frame):
            shape = yield comp.Compute(shape_ref)
            return comp.Value(shape.name if shape else "none")

        def unparse(self):
            return "test"

    engine = comp.Engine()
    result = engine.run(TestNode(), mod_shapes=main_module)

    assert result.to_python() == "point"


def test_function_reference_with_namespace():
    """Test referencing a function from an imported namespace."""
    # Create imported module with a function
    lib_module = comp.Module()
    lib_module.define_function(["double"], body=None)

    # Create main module and import lib
    main_module = comp.Module()
    main_module.add_namespace("lib", lib_module)

    # Create reference with explicit namespace: |double/lib
    func_ref = comp.ast.FuncRef(["double"], namespace="lib")

    class TestNode(comp.ast.ValueNode):
        def evaluate(self, frame):
            func = yield comp.Compute(func_ref)
            return func

        def unparse(self):
            return "test"

    engine = comp.Engine()
    result = engine.run(TestNode(), mod_funcs=main_module)

    # Should find the function from lib namespace
    assert result.data is not None
    assert isinstance(result.data, dict)


def test_function_fallback_to_namespace():
    """Test that functions fall back to checking namespaces."""
    # Create imported module with a function
    lib_module = comp.Module()
    lib_module.define_function(["helper"], body=None)

    # Create main module (no local function) and import lib
    main_module = comp.Module()
    main_module.add_namespace("lib", lib_module)

    # Reference without namespace should find it in lib
    func_ref = comp.ast.FuncRef(["helper"])

    class TestNode(comp.ast.ValueNode):
        def evaluate(self, frame):
            func = yield comp.Compute(func_ref)
            return func

        def unparse(self):
            return "test"

    engine = comp.Engine()
    result = engine.run(TestNode(), mod_funcs=main_module)

    # Should find the function from lib namespace via fallback
    assert result.data is not None


def test_namespace_not_found():
    """Test referencing a non-existent namespace."""
    main_module = comp.Module()

    # Reference with namespace that doesn't exist
    tag_ref = comp.ast.TagValueRef(["test"], namespace="nonexistent")

    class TestNode(comp.ast.ValueNode):
        def evaluate(self, frame):
            tag = yield comp.Compute(tag_ref)
            return tag

        def unparse(self):
            return "test"

    engine = comp.Engine()
    result = engine.run(TestNode(), mod_tags=main_module)

    # Should fail - namespace not found
    assert engine.is_fail(result)


def test_reference_unparse_with_namespace():
    """Test unparsing references with namespaces."""
    tag_ref = comp.ast.TagValueRef(["status", "ok"], namespace="lib")
    assert tag_ref.unparse() == "#ok.status/lib"

    shape_ref = comp.ast.ShapeRef(["point"], namespace="geometry")
    assert shape_ref.unparse() == "~point/geometry"

    func_ref = comp.ast.FuncRef(["calculate"], namespace="math")
    assert func_ref.unparse() == "|calculate/math"


def test_multiple_namespaces():
    """Test resolving references with multiple imported namespaces."""
    # Create two imported modules
    lib1 = comp.Module()
    lib1.define_tag(["status", "ok"], comp.Value(1))

    lib2 = comp.Module()
    lib2.define_tag(["status", "error"], comp.Value(2))

    # Import both into main
    main_module = comp.Module()
    main_module.add_namespace("lib1", lib1)
    main_module.add_namespace("lib2", lib2)

    # Reference without namespace should find in first matching
    tag_ref = comp.ast.TagValueRef(["ok", "status"])

    class TestNode(comp.ast.ValueNode):
        def evaluate(self, frame):
            tag = yield comp.Compute(tag_ref)
            return tag

        def unparse(self):
            return "test"

    engine = comp.Engine()
    result = engine.run(TestNode(), mod_tags=main_module)

    # Should find the tag (from lib1)
    assert result.data is not None
