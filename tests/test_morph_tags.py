"""Tests for tag field matching in morphing."""

import decimal
import comp
import comptest


def _make_tag_value(module: comp.Module, path: list[str]) -> comp.Value:
    """Create a tag value from a tag definition."""
    tag_def = module.lookup_tag(path)
    return comp.Value(comp.TagRef(tag_def))


def test_morph_single_tag_field():
    """Single tag field matches unnamed tag value."""
    module = comptest.parse_module("""
        !tag #status = {#active #inactive}
        !shape ~test = {state #status}
    """)
    
    test_shape = module.lookup_shape(["test"])
    active_tag = _make_tag_value(module, ["status", "active"])
    data = comp.Value({comp.Unnamed(): active_tag})
    
    result = comp.morph(data, test_shape)
    
    assert result.success
    assert result.value.is_struct
    state_key = comp.Value("state")
    assert state_key in result.value.struct
    assert result.value.struct[state_key] == active_tag


def test_morph_multiple_tag_fields():
    """Multiple tag fields match multiple unnamed tags."""
    module = comptest.parse_module("""
        !tag #sort-order = {#asc #desc}
        !tag #stability = {#stable #unstable}
        !shape ~sort-args = {order #sort-order stability #stability}
    """)
    
    test_shape = module.lookup_shape(["sort-args"])
    desc_tag = _make_tag_value(module, ["sort-order", "desc"])
    stable_tag = _make_tag_value(module, ["stability", "stable"])
    
    data = comp.Value({
        comp.Unnamed(): desc_tag,
        comp.Unnamed(): stable_tag
    })
    
    result = comp.morph(data, test_shape)
    
    assert result.success
    order_val = result.value.struct.get(comp.Value("order"))
    stability_val = result.value.struct.get(comp.Value("stability"))
    assert order_val == desc_tag
    assert stability_val == stable_tag


def test_morph_tag_field_with_named_fields():
    """Tag field works alongside named fields."""
    module = comptest.parse_module("""
        !tag #mode = {#read #write}
        !shape ~file-op = {path ~str mode #mode}
    """)
    
    test_shape = module.lookup_shape(["file-op"])
    write_tag = _make_tag_value(module, ["mode", "write"])
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
    module = comptest.parse_module("""
        !tag #direction = {#forward #backward}
        !shape ~move = {~num dir #direction}
    """)
    
    test_shape = module.lookup_shape(["move"])
    forward_tag = _make_tag_value(module, ["direction", "forward"])
    data = comp.Value({
        comp.Unnamed(): comp.Value(decimal.Decimal("10")),
        comp.Unnamed(): forward_tag
    })
    
    result = comp.morph(data, test_shape)
    
    assert result.success
    assert result.value.struct[comp.Value("dir")] == forward_tag


def test_morph_tag_hierarchy_matching():
    """Tags match fields with parent types in hierarchy."""
    module = comptest.parse_module("""
        !tag #error = {#timeout #network}
        !shape ~error-handler = {error-type #error}
    """)
    
    test_shape = module.lookup_shape(["error-handler"])
    timeout_tag = _make_tag_value(module, ["error", "timeout"])
    data = comp.Value({comp.Unnamed(): timeout_tag})
    
    result = comp.morph(data, test_shape)
    
    assert result.success
    assert result.value.struct[comp.Value("error-type")] == timeout_tag


def test_morph_tag_field_ambiguity_error():
    """Multiple tag fields of same type should error on ambiguity."""
    module = comptest.parse_module("""
        !tag #color = {#red #green #blue}
        !shape ~ambiguous = {primary #color secondary #color}
    """)
    
    test_shape = module.lookup_shape(["ambiguous"])
    red_tag = _make_tag_value(module, ["color", "red"])
    data = comp.Value({comp.Unnamed(): red_tag})
    
    result = comp.morph(data, test_shape)
    
    # Ambiguous which field to fill - should fail
    assert not result.success


def test_morph_tag_field_wrong_hierarchy():
    """Tag from wrong hierarchy should not match."""
    module = comptest.parse_module("""
        !tag #status = {#active #inactive}
        !tag #color = {#red #green}
        !shape ~test = {state #status}
    """)
    
    test_shape = module.lookup_shape(["test"])
    red_tag = _make_tag_value(module, ["color", "red"])
    data = comp.Value({comp.Unnamed(): red_tag})
    
    result = comp.morph(data, test_shape)
    
    # #red is not in #status hierarchy - should fail
    assert not result.success
