"""Tests for module preparation and imports."""

import pytest

import comp
import comptest


def test_module_preparation():
    """Test module preparation resolves references."""
    # Create AST with definitions and references
    ast_module = comp.ast.Module([
        comp.ast.TagDef(["status", "ok"], value=comp.ast.Number(200)),
        comp.ast.TagDef(["test"], value=comp.ast.TagValueRef(["ok", "status"])),
    ])

    engine = comp.Engine()
    result = engine.run(ast_module)
    
    # Module evaluation returns Module
    assert isinstance(result, comp.Module)

    # Both tags should be defined
    ok_tag = result.lookup_tag(["ok", "status"])
    test_tag = result.lookup_tag(["test"])
    
    assert ok_tag.value.data == 200
    # #test is a tag reference that points to #ok.status
    assert test_tag.value.is_tag
    assert test_tag.value.data.tag_def == ok_tag


def test_import_statement():
    """Test evaluation of import statements loads modules."""
    module = comptest.parse_module('!import /test = comp "test"')

    # Check that the import was registered
    assert "test" in module.namespaces
    imported = module.namespaces["test"]
    assert isinstance(imported, comp.Module)

    # Check that imported module has the expected tags
    greeting = imported.lookup_tag(["greeting"])
    assert greeting is not None


def test_undefined():
    """Test preparing modules with undefined references"""
    engine = comp.Engine()

    fast = comp.parse_module("!func |nofunc ~any = {{1 2 [|skiperoo]}}")
    module = comp.Module()
    with pytest.raises(ValueError):
        module.prepare(fast, engine)

    sast = comp.parse_module("!func |nofunc ~any = {{1 2} ~skiperoo}")
    module = comp.Module()
    with pytest.raises(ValueError):
        module.prepare(sast, engine)

    tast = comp.parse_module("!func |nofunc ~any = {{1 #skiperoo}}")
    module = comp.Module()
    with pytest.raises(ValueError):
        module.prepare(tast, engine)


def test_import_parse_errors():
    """Test that invalid import syntax raises errors."""
    with comptest.pytest.raises(comp.ParseError):
        comp.parse_module('!import = comp "test"')

    with comptest.pytest.raises(comp.ParseError):
        comp.parse_module('!import /test = "test"')

    with comptest.pytest.raises(comp.ParseError):
        comp.parse_module('!import /test = comp')
