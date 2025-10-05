"""Tests for building runtime structures from AST."""

import comp


def test_build_tags_simple():
    """Test building a simple tag."""
    module = comp.parse_module("!tag #status")
    tags = comp.run.build_tags(module)

    assert len(tags) == 1
    assert tags[0].name == "#status"
    assert tags[0].identifier == ["status"]
    assert tags[0].namespace == "main"


def test_build_tags_nested():
    """Test building nested tags."""
    module = comp.parse_module("!tag #status.active")
    tags = comp.run.build_tags(module)

    # Should create both parent and child
    assert len(tags) == 2
    assert tags[0].name == "#status"
    assert tags[0].identifier == ["status"]
    assert tags[1].name == "#status.active"
    assert tags[1].identifier == ["status", "active"]


def test_build_tags_with_body():
    """Test building tags with body children."""
    module = comp.parse_module("""
        !tag #status = {
            #active
            #inactive
        }
    """)
    tags = comp.run.build_tags(module)

    # Should create: #status, #status.active, #status.inactive
    assert len(tags) == 3
    assert tags[0].name == "#status"
    assert tags[1].name == "#status.active"
    assert tags[2].name == "#status.inactive"


def test_build_tags_deeply_nested():
    """Test building deeply nested tags."""
    module = comp.parse_module("""
        !tag #ui.button = {
            #primary.enabled
            #primary.disabled
            #secondary
        }
    """)
    tags = comp.run.build_tags(module)

    # Should create:
    # #ui, #ui.button,
    # #ui.button.primary, #ui.button.primary.enabled, #ui.button.primary.disabled
    # #ui.button.secondary
    assert len(tags) == 6
    names = [t.name for t in tags]
    assert "#ui" in names
    assert "#ui.button" in names
    assert "#ui.button.primary" in names
    assert "#ui.button.primary.enabled" in names
    assert "#ui.button.primary.disabled" in names
    assert "#ui.button.secondary" in names


def test_build_tags_multiple_definitions():
    """Test building tags from multiple definitions."""
    module = comp.parse_module("""
        !tag #status
        !tag #priority.high
        !tag #priority.low
    """)
    tags = comp.run.build_tags(module)

    # Should create: #status, #priority, #priority.high, #priority.low
    assert len(tags) == 4
    names = [t.name for t in tags]
    assert "#status" in names
    assert "#priority" in names
    assert "#priority.high" in names
    assert "#priority.low" in names


def test_build_tags_custom_namespace():
    """Test building tags with custom namespace."""
    module = comp.parse_module("!tag #status")
    tags = comp.run.build_tags(module, namespace="myapp")

    assert len(tags) == 1
    assert tags[0].namespace == "myapp"


def test_build_tags_sorted_output():
    """Test that tags are returned in sorted order."""
    module = comp.parse_module("""
        !tag #zebra
        !tag #apple
        !tag #banana
    """)
    tags = comp.run.build_tags(module)

    names = [t.name for t in tags]
    assert names == ["#apple", "#banana", "#zebra"]
