"""Tests for the module preparation system.

Tests the multi-phase module preparation process that pre-resolves all references
at build time, converting undefined lookups into build-time errors.
"""

import comp
import pytest
from comp import Engine, Module
from comp.ast import Module as AstModule, Number, TagDef, TagValueRef


def test_phase1_create_definitions():
    """Test Phase 1: Creating initial definitions from AST."""
    # Create AST with definitions
    ast_module = AstModule([
        TagDef(["status", "ok"], value=Number(200)),
    ])

    # Create and prepare module
    module = Module()
    engine = Engine()

    # Phase 1 should create initial definitions
    module._phase1_create_definitions(ast_module, engine)

    # Check that definitions were created
    assert "status.ok" in module.tags

    # Tag should have no value yet (Phase 1 doesn't evaluate)
    tag_def = module.tags["status.ok"]
    assert tag_def.path == ["status", "ok"]
    assert tag_def.value is None  # Not evaluated yet


def test_phase3_build_resolution_namespace():
    """Test Phase 3: Building complete resolution namespace."""
    module = Module()

    # Add some definitions
    module.define_tag(["status", "error", "timeout"], value=comp.Value(408))
    module.define_tag(["status", "ok"], value=comp.Value(200))
    module.define_shape(["point", "2d"], fields=[])

    # Build resolution namespace
    resolution_ns = module._phase3_build_resolution_namespace()

    # Check that partial paths were generated
    # For tag ["status", "error", "timeout"], should generate:
    # - ["timeout"] → ("timeout",)
    # - ["error", "timeout"] → ("timeout", "error")
    # - ["status", "error", "timeout"] → ("timeout", "error", "status")
    # (Note: references are reversed - leaf first)

    assert ('tag', ('timeout',), None) in resolution_ns
    assert ('tag', ('timeout', 'error'), None) in resolution_ns
    assert ('tag', ('timeout', 'error', 'status'), None) in resolution_ns

    # For tag ["status", "ok"], should generate:
    # - ["ok"] → ("ok",)
    # - ["status", "ok"] → ("ok", "status")
    assert ('tag', ('ok',), None) in resolution_ns
    assert ('tag', ('ok', 'status'), None) in resolution_ns

    # For shape ["point", "2d"], should generate:
    # - ["2d"] → ("2d",)
    # - ["point", "2d"] → ("2d", "point")
    assert ('shape', ('2d',), None) in resolution_ns
    assert ('shape', ('2d', 'point'), None) in resolution_ns


def test_phase3_ambiguity_detection():
    """Test that Phase 3 detects ambiguous references."""
    module = Module()

    # Add two tags with same leaf name
    module.define_tag(["status", "ok"], value=comp.Value(200))
    module.define_tag(["response", "ok"], value=comp.Value(True))

    # Build resolution namespace
    resolution_ns = module._phase3_build_resolution_namespace()

    # The partial path ["ok"] should be marked as AMBIGUOUS
    # Note: type: ignore for internal implementation testing
    assert resolution_ns.get(('tag', ('ok',), None)) == 'AMBIGUOUS'  # type: ignore

    # But longer paths should be unambiguous
    assert resolution_ns.get(('tag', ('status', 'ok'), None)) != 'AMBIGUOUS'  # type: ignore
    assert resolution_ns.get(('tag', ('response', 'ok'), None)) != 'AMBIGUOUS'  # type: ignore


def test_phase4_preresolve_tag_reference():
    """Test Phase 4: Pre-resolving tag references."""
    module = Module()

    # Define a tag
    tag_def = module.define_tag(["status", "ok"], value=comp.Value(200))

    # Create AST with tag reference
    tag_ref = TagValueRef(["ok"])  # Partial reference

    # Build resolution namespace
    resolution_ns = module._phase3_build_resolution_namespace()

    # Pre-resolve the reference
    module._preresolve_node(tag_ref, resolution_ns)

    # Check that reference was resolved
    assert tag_ref._resolved is not None
    assert tag_ref._resolved == tag_def
    assert tag_ref._resolved.path == ["status", "ok"]


def test_phase4_undefined_reference_error():
    """Test that Phase 4 raises error for undefined references."""
    module = Module()

    # Create AST with undefined reference
    tag_ref = TagValueRef(["nonexistent"])

    # Build resolution namespace (empty)
    resolution_ns = module._phase3_build_resolution_namespace()

    # Pre-resolve should raise error
    with pytest.raises(ValueError, match="Undefined tag reference: #nonexistent"):
        module._preresolve_node(tag_ref, resolution_ns)


def test_phase4_ambiguous_reference_error():
    """Test that Phase 4 raises error for ambiguous references."""
    module = Module()

    # Define two tags with same leaf name
    module.define_tag(["status", "ok"], value=comp.Value(200))
    module.define_tag(["response", "ok"], value=comp.Value(True))

    # Create AST with ambiguous reference
    tag_ref = TagValueRef(["ok"])  # Matches both tags

    # Build resolution namespace
    resolution_ns = module._phase3_build_resolution_namespace()

    # Pre-resolve should raise error
    with pytest.raises(ValueError, match="Ambiguous tag reference: #ok"):
        module._preresolve_node(tag_ref, resolution_ns)


def test_full_prepare_process():
    """Test the complete prepare() process."""
    # Create AST with definitions and references
    ast_module = AstModule([
        TagDef(["status", "ok"], value=Number(200)),
        TagDef(["test"], value=TagValueRef(["ok"])),  # Reference to #ok
    ])

    # Create and prepare module
    module = Module()
    engine = Engine()

    # This should complete without errors
    module.prepare(ast_module, engine)

    # Check that module is marked as prepared
    assert getattr(module, '_prepared', False) is True

    # Check that definitions exist
    assert "status.ok" in module.tags  # Path is in definition order
    assert "test" in module.tags

    # Check that the reference in test tag was pre-resolved
    # (We'd need to store the AST to verify this, but at minimum it shouldn't crash)


def test_prepare_with_namespace():
    """Test preparation with namespace imports."""
    # Create a module to import
    imported_ast = AstModule([
        TagDef(["imported", "tag"], value=Number(42)),
    ])
    imported_module = Module()
    imported_module._phase1_create_definitions(imported_ast, Engine())

    # Create main module that references imported tag
    main_module = Module()
    main_module.add_namespace("other", imported_module)

    # Define a tag that references the imported one
    main_module.define_tag(["local"], value=None)

    # Build resolution namespace
    resolution_ns = main_module._phase3_build_resolution_namespace()

    # Should be able to resolve with explicit namespace
    assert ('tag', ('tag', 'imported'), 'other') in resolution_ns

    # And without (since there's no conflict)
    assert ('tag', ('tag', 'imported'), None) in resolution_ns


def test_prepare_local_overrides_namespace():
    """Test that local definitions override namespace imports."""
    # Create imported module with a tag
    imported_module = Module()
    imported_module.define_tag(["ok"], value=comp.Value(100))

    # Create main module with same tag name
    main_module = Module()
    main_module.define_tag(["ok"], value=comp.Value(200))
    main_module.add_namespace("other", imported_module)

    # Build resolution namespace
    resolution_ns = main_module._phase3_build_resolution_namespace()

    # Local definition should take precedence for implicit reference
    # Note: type: ignore for internal implementation testing
    local_def = resolution_ns.get(('tag', ('ok',), None))  # type: ignore
    assert local_def != 'AMBIGUOUS'
    assert local_def.value.data == 200  # type: ignore # Local value

    # Explicit namespace should work
    imported_def = resolution_ns.get(('tag', ('ok',), 'other'))  # type: ignore
    assert imported_def.value.data == 100  # type: ignore # Imported value


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
