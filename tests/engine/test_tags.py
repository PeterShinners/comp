"""Tests for tag definitions and references."""

import comp.engine as comp
from comp.engine.ast._base import ValueNode
from comp.engine.ast._tag import Module as ModuleNode
from comp.engine.ast._tag import TagChild, TagDef, TagValueRef


def test_entity_base_class():
    """Verify Value and Module both inherit from Entity."""
    v = comp.Value(42)
    m = comp.Module()

    assert isinstance(v, comp.Entity)
    assert isinstance(m, comp.Entity)


def test_module_in_scope():
    """Verify Module can be passed through scopes."""
    module = comp.Module()

    # Define a simple tag
    module.define_tag(["status", "active"], comp.Value(1))

    # Create a simple AST that accesses mod_tags scope
    class TestNode(ValueNode):
        def evaluate(self, frame):
            mod = frame.scope('mod_tags')
            if mod is None:
                return comp.fail("No mod_tags scope")

            # Look up a tag
            tag_def = mod.get_tag_by_full_path(["status", "active"])
            if tag_def is None:
                return comp.fail("Tag not found")

            return tag_def.value
            yield  # Make this a generator (unreachable)

        def unparse(self):
            return "test_node"    # Run with module in scope
    engine = comp.Engine()
    result = engine.run(TestNode(), mod_tags=module)

    assert result.to_python() == 1


def test_simple_tag_definition():
    """Test defining a tag with a value."""
    # Create tag definition: !tag #active = 1
    tag_def = TagDef(
        path=["status", "active"],  # Definition order
        value=comp.ast.Number(1)
    )

    # Wrap in Module node
    module_node = ModuleNode([tag_def])

    # Evaluate
    engine = comp.Engine()
    result = engine.run(module_node)

    # Module evaluation returns #true for success
    assert result.to_python() == comp.TRUE


def test_tag_with_children():
    """Test defining tags with nested children."""
    # !tag #status = {
    #     #active = 1
    #     #inactive = 0
    # }
    tag_def = TagDef(
        path=["status"],
        children=[
            TagChild(path=["active"], value=comp.ast.Number(1)),
            TagChild(path=["inactive"], value=comp.ast.Number(0)),
        ]
    )

    module_node = ModuleNode([tag_def])

    engine = comp.Engine()
    result = engine.run(module_node)

    assert result.to_python() == comp.TRUE


def test_tag_reference():
    """Test referencing a defined tag."""
    # Manually set up the module
    module = comp.Module()
    module.define_tag(["status", "active"], comp.Value(1))

    # Create reference: #active (partial path)
    tag_ref = TagValueRef(path=["active"])

    # Evaluate the reference with module in scope
    engine = comp.Engine()
    result = engine.run(tag_ref, mod_tags=module)

    # Should return a struct with tag info
    assert isinstance(result.data, dict)
    # The struct has name and path fields
    assert len(result.data) >= 2


def test_partial_tag_matching():
    """Test that partial tag paths match correctly."""
    module = comp.Module()

    # Define: !tag #timeout.error.status = 1
    module.define_tag(["status", "error", "timeout"], comp.Value(1))

    # Reference with partial paths should all work
    # Full path: #timeout.error.status -> ["timeout", "error", "status"]
    tag_def = module.lookup_tag(["timeout", "error", "status"])
    assert tag_def is not None

    # Partial: #timeout.error -> ["timeout", "error"]
    tag_def = module.lookup_tag(["timeout", "error"])
    assert tag_def is not None

    # Partial: #timeout -> ["timeout"]
    tag_def = module.lookup_tag(["timeout"])
    assert tag_def is not None


def test_ambiguous_tag_reference():
    """Test that ambiguous references are detected."""
    module = comp.Module()

    # Define two tags with same suffix
    module.define_tag(["status", "error", "timeout"], comp.Value(1))
    module.define_tag(["network", "error", "timeout"], comp.Value(2))

    # Ambiguous reference: #timeout
    try:
        module.lookup_tag(["timeout"])
        raise AssertionError("Should have raised ValueError")
    except ValueError as e:
        assert "ambiguous" in str(e).lower()


def test_tag_not_found():
    """Test that missing tags return None."""
    module = comp.Module()

    tag_def = module.lookup_tag(["nonexistent"])
    assert tag_def is None
