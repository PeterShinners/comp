"""Tests for tag definitions and references."""

import pytest

import comp
import comptest


def test_simple_tag_definition():
    """Test defining a tag with a value."""
    # Create tag definition: !tag #active.status = 1  (in comp notation, reversed)
    module_node = comp.ast.Module([
        comp.ast.TagDef(
            path=["status", "active"],  # Definition order (parent first)
            value=comp.ast.Number(1)
        ),
    ])
    result = comptest.run_ast(module_node)

    # Module evaluation returns a Module entity
    assert isinstance(result, comp.Module)
    
    # Lookup with reversed path (leaf-first): ["active"] matches end of ["status", "active"]
    assert result.lookup_tag(["active"]).value.to_python() == 1
    
    # Lookup with full reversed path: ["active", "status"]
    assert result.lookup_tag(["active", "status"])
    
    # NOTE: Cannot lookup ["status"] - no tag defined with path ending in "status"
    # The defined tag is ["status", "active"] which ends with "active", not "status"


def test_tag_with_children():
    """Test defining tags with nested children."""
    # !tag #status = {#active=1 #inactive=0}
    module_node = comp.ast.Module([
        comp.ast.TagDef(path=["status"], children=[
            comp.ast.TagChild(path=["active"], value=comp.ast.Number(1)),
            comp.ast.TagChild(path=["inactive"], value=comp.ast.Number(0)),
        ]
        )
    ])
    result = comptest.run_ast(module_node)
    assert isinstance(result, comp.Module)
    assert result.lookup_tag(["active"]).value.to_python() == 1
    assert result.lookup_tag(["inactive"]).value.to_python() == 0
    assert result.lookup_tag(["active", "status"])
    assert result.lookup_tag(["status"]).value is None


def test_tag_reference():
    """Test referencing a defined tag."""
    module = comp.Module()
    module.define_tag(["status", "active"], comp.Value(1))

    tag_ref = comp.ast.TagValueRef(path=["active"])
    result = comptest.run_ast(tag_ref, module=module)

    # Should return the TagRef itself (not the tag's value)
    # Tag references evaluate to TagRef objects
    assert result.is_tag
    assert isinstance(result.data, comp.TagRef)
    assert result.data.tag_def.value.data == 1


def test_invalid_tag_reference():
    """Test that invalid references raise."""
    module = comp.Module()
    module.define_tag(["status", "error", "timeout"], comp.Value(1))
    module.define_tag(["network", "error", "timeout"], comp.Value(2))

    # Ambiguous reference: #timeout
    with pytest.raises(ValueError):
        module.lookup_tag(["timeout"])

    # Nonexistant
    with pytest.raises(ValueError):
        module.lookup_tag(["nonexistent"])

