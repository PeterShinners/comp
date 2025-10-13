"""Tests for import system."""

import comp


def test_import_parse():
    """Test parsing of import statements."""
    source = '!import /test = comp "test"'
    result = comp.parse_module(source)

    assert isinstance(result, comp.ast.Module)
    assert len(result.operations) == 1

    import_op = result.operations[0]
    assert isinstance(import_op, comp.ast.ImportDef)
    assert import_op.namespace == "test"
    assert import_op.source == "comp"
    assert import_op.path == "test"


def test_import_unparse():
    """Test unparsing import statements back to source."""
    import_def = comp.ast.ImportDef("math", "std", "core/math")
    source = import_def.unparse()

    assert source == '!import /math = std "core/math"'


def test_import_evaluate():
    """Test evaluation of import statements loads modules."""
    engine = comp.Engine()

    source = '''
!import /test = comp "test"
'''

    module_ast = comp.parse_module(source)
    module = engine.run(module_ast)

    # Check that the import was registered
    assert "test" in module.namespaces
    imported = module.namespaces["test"]
    assert isinstance(imported, comp.Module)

    # Check that imported module has the expected tags
    greeting = imported.lookup_tag(["greeting"])
    assert greeting is not None


def test_import_namespace_access():
    """Test accessing definitions from imported namespaces."""
    engine = comp.Engine()

    source = '''
!import /test = comp "test"
'''

    module_ast = comp.parse_module(source)
    module = engine.run(module_ast)

    # Get the imported namespace
    assert "test" in module.namespaces
    imported = module.namespaces["test"]

    # Access tag from imported module directly
    greeting_tag = imported.lookup_tag(["greeting"])
    assert greeting_tag is not None

    # The module should have defined tags
    assert len(imported.list_tags()) > 0


def test_import_nonexistent_file():
    """Test importing a file that doesn't exist."""
    engine = comp.Engine()

    source = '!import /missing = comp "nonexistent/module"'

    module_ast = comp.parse_module(source)
    result = engine.run(module_ast)

    # Should return a failure
    assert engine.is_fail(result)


def test_import_unsupported_source():
    """Test importing from an unsupported source type."""
    engine = comp.Engine()

    source = '!import /py = python "numpy"'

    module_ast = comp.parse_module(source)
    result = engine.run(module_ast)

    # Should return a failure indicating unsupported source
    assert engine.is_fail(result)


def test_import_multiple():
    """Test multiple imports in one module."""
    engine = comp.Engine()

    source = '''
!import /test1 = comp "test"
!import /test2 = comp "test"
'''

    module_ast = comp.parse_module(source)
    module = engine.run(module_ast)

    # Check both imports are registered
    assert "test1" in module.namespaces
    assert "test2" in module.namespaces

    # Both should reference the same module content (loaded twice)
    imported1 = module.namespaces["test1"]
    imported2 = module.namespaces["test2"]
    assert imported1.lookup_tag(["greeting"]) is not None
    assert imported2.lookup_tag(["answer"]) is not None


def test_import_parse_errors():
    """Test that invalid import syntax raises errors."""
    # Missing namespace
    try:
        comp.parse_module('!import = comp "test"')
        assert False, "Should have raised ParseError"
    except comp.ParseError:
        pass

    # Missing source
    try:
        comp.parse_module('!import /test = "test"')
        assert False, "Should have raised ParseError"
    except comp.ParseError:
        pass

    # Missing path
    try:
        comp.parse_module('!import /test = comp')
        assert False, "Should have raised ParseError"
    except comp.ParseError:
        pass

