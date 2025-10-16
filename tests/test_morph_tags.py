"""Tests for Phase 2: Tag field matching in morphing.

Tag fields in shapes should automatically match unnamed tag values during morphing.
This enables clean flag-style arguments and type-safe tag handling.
"""

import comp
import pytest
from decimal import Decimal


class ModuleHelper:
    """Helper for building test modules with code snippets."""
    
    def __init__(self):
        self.engine = comp.Engine()
        self.module = comp.Module()
        self.code_parts = []
    
    def add_code(self, code: str):
        """Add code to the module."""
        self.code_parts.append(code)
    
    def _prepare_module(self):
        """Parse and prepare all code."""
        full_code = "\n".join(self.code_parts)
        module_ast = comp.parse_module(full_code)
        self.module.prepare(module_ast, self.engine)
        # Run module to populate definitions
        module_result = self.engine.run(module_ast, module=self.module)
        if isinstance(module_result, comp.Module):
            self.module = module_result
    
    def get_shape(self, path: list[str]):
        """Get a shape by path."""
        self._prepare_module()
        shape = self.module.lookup_shape(path)
        if shape is None:
            raise ValueError(f"Shape not found: {path}")
        return shape
    
    def get_tag(self, path: list[str]):
        """Get a tag value by path.
        
        Note: Path is in reference order (reversed), e.g., ["active", "status"]
        for #status.active (which is written #active.status in code)
        """
        self._prepare_module()
        tag_def = self.module.lookup_tag(path)
        if tag_def is None:
            raise ValueError(f"Tag not found: {path}")
        # Create a tag value from the definition
        return comp.Value(comp.TagRef(tag_def))


def test_morph_single_tag_field():
    """Single tag field matches unnamed tag value."""
    helper = ModuleHelper()
    helper.add_code("""
        !tag #status = {#active #inactive}
        !shape ~test = {state #status}
    """)
    
    # Get the shape
    test_shape = helper.get_shape(["test"])
    
    # Create input with unnamed tag
    active_tag = helper.get_tag(["active", "status"])
    data = comp.Value({
        comp.Unnamed(): active_tag
    })
    
    # Morph should match the tag to the 'state' field
    result = comp.morph(data, test_shape)
    
    assert result.success
    assert result.value.is_struct
    
    # Should have 'state' field with the tag value
    state_key = comp.Value("state")
    assert state_key in result.value.struct
    assert result.value.struct[state_key] == active_tag


def test_morph_multiple_tag_fields():
    """Multiple tag fields match multiple unnamed tags."""
    helper = ModuleHelper()
    helper.add_code("""
        !tag #sort-order = {#asc #desc}
        !tag #stability = {#stable #unstable}
        
        !shape ~sort-args = {
            order #sort-order
            stability #stability
        }
    """)
    
    test_shape = helper.get_shape(["sort-args"])
    
    # Create input with two unnamed tags
    desc_tag = helper.get_tag(["desc", "sort-order"])
    stable_tag = helper.get_tag(["stable", "stability"])
    
    data = comp.Value({
        comp.Unnamed(): desc_tag,
        comp.Unnamed(): stable_tag
    })
    
    # Morph should match both tags to their respective fields
    result = comp.morph(data, test_shape)
    
    assert result.success
    order_val = result.value.struct.get(comp.Value("order"))
    stability_val = result.value.struct.get(comp.Value("stability"))
    
    assert order_val == desc_tag
    assert stability_val == stable_tag


def test_morph_tag_field_with_named_fields():
    """Tag field works alongside named fields."""
    helper = ModuleHelper()
    helper.add_code("""
        !tag #mode = {#read #write}
        !shape ~file-op = {
            path ~str
            mode #mode
        }
    """)
    
    test_shape = helper.get_shape(["file-op"])
    
    # Named field + unnamed tag
    write_tag = helper.get_tag(["write", "mode"])
    data = comp.Value({
        comp.Value("path"): comp.Value("/tmp/test.txt"),
        comp.Unnamed(): write_tag
    })
    
    result = comp.morph(data, test_shape)
    
    assert result.success
    assert result.value.struct[comp.Value("path")].data == "/tmp/test.txt"
    assert result.value.struct[comp.Value("mode")] == write_tag


def test_morph_tag_field_with_positional_fields():
    """Tag fields work with positional unnamed fields."""
    helper = ModuleHelper()
    helper.add_code("""
        !tag #direction = {#forward #backward}
        !shape ~move = {
            ~num           ; Distance (positional)
            dir #direction ; Direction (tag)
        }
    """)
    
    test_shape = helper.get_shape(["move"])
    
    # Positional number + unnamed tag
    forward_tag = helper.get_tag(["forward", "direction"])
    data = comp.Value({
        comp.Unnamed(): comp.Value(Decimal("10")),
        comp.Unnamed(): forward_tag
    })
    
    result = comp.morph(data, test_shape)
    
    assert result.success
    # First unnamed should match positional field
    # Second unnamed should match tag field
    assert result.value.struct[comp.Value("dir")] == forward_tag


@pytest.mark.skip(reason="Tag defaults not yet implemented")
def test_morph_tag_field_with_default():
    """Tag field default is used when tag not provided."""
    helper = ModuleHelper()
    helper.add_code("""
        !tag #status = {#active #inactive}
        !shape ~test = {
            name ~str
            state #status = #status.active
        }
    """)
    
    test_shape = helper.get_shape(["test"])
    
    # Only provide name, not tag
    data = comp.Value({
        comp.Value("name"): comp.Value("test")
    })
    
    result = comp.morph(data, test_shape)
    
    assert result.success
    # Default tag should be applied
    active_tag = helper.get_tag(["active", "status"])
    assert result.value.struct[comp.Value("state")] == active_tag


def test_morph_tag_hierarchy_matching():
    """Tags match fields with parent types in hierarchy."""
    helper = ModuleHelper()
    helper.add_code("""
        !tag #error = {
            #timeout
            #network
        }
        !shape ~error-handler = {
            error-type #error
        }
    """)
    
    test_shape = helper.get_shape(["error-handler"])
    
    # Provide specific error type (child tag)
    timeout_tag = helper.get_tag(["timeout", "error"])
    data = comp.Value({
        comp.Unnamed(): timeout_tag
    })
    
    # Should match - #timeout is a child of #error
    result = comp.morph(data, test_shape)
    
    assert result.success
    assert result.value.struct[comp.Value("error-type")] == timeout_tag


def test_morph_tag_field_ambiguity_error():
    """Multiple tag fields of same type should error on ambiguity."""
    helper = ModuleHelper()
    helper.add_code("""
        !tag #color = {#red #green #blue}
        !shape ~ambiguous = {
            primary #color
            secondary #color
        }
    """)
    
    test_shape = helper.get_shape(["ambiguous"])
    
    # Single unnamed tag - which field should it match?
    red_tag = helper.get_tag(["red", "color"])
    data = comp.Value({
        comp.Unnamed(): red_tag
    })
    
    # This should fail - ambiguous which field to fill
    result = comp.morph(data, test_shape)
    
    # TODO: Decide on behavior - fail or use some heuristic?
    # For now, document that we should fail
    assert not result.success


def test_morph_tag_field_wrong_hierarchy():
    """Tag from wrong hierarchy should not match."""
    helper = ModuleHelper()
    helper.add_code("""
        !tag #status = {#active #inactive}
        !tag #color = {#red #green}
        
        !shape ~test = {
            state #status
        }
    """)
    
    test_shape = helper.get_shape(["test"])
    
    # Provide tag from wrong hierarchy
    red_tag = helper.get_tag(["red", "color"])
    data = comp.Value({
        comp.Unnamed(): red_tag
    })
    
    # Should fail - #red is not in #status hierarchy
    result = comp.morph(data, test_shape)
    
    assert not result.success


@pytest.mark.skip(reason="Not yet implemented")
def test_morph_tag_specificity_scoring():
    """Tag depth affects specificity in union morphing."""
    helper = ModuleHelper()
    helper.add_code("""
        !tag #status = {#active #error}
        !tag #error.status = {#network.error #timeout.error}
        
        !shape ~generic = {state #status}
        !shape ~specific = {state #error.status}
        !shape ~very-specific = {state #network.error}
    """)
    
    # Test that more specific tag types score higher
    # This affects union morphing: ~generic | ~specific | ~very-specific
    pass
