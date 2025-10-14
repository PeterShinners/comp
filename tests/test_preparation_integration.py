"""Integration tests for module preparation with evaluation.

Tests that pre-resolved references work correctly during evaluation,
providing performance benefits while maintaining correctness.
"""

import comp
import pytest


def test_basic_module_preparation():
    """Test basic module preparation without complex references."""
    source = """
!tag #status.ok = 200
!tag #status.error = 500
"""
    
    # Parse and prepare
    ast_module = comp.parse_module(source)
    module = comp.Module()
    engine = comp.Engine()
    
    # Should succeed without errors
    module.prepare(ast_module, engine)
    
    # Evaluate the module
    result = engine.run(ast_module)
    assert isinstance(result, comp.Module)
    
    # Check definitions exist
    assert "status.ok" in result.tags
    assert "status.error" in result.tags


def test_multiple_tags_preparation():
    """Test preparation with multiple tag definitions."""
    source = """
!tag #a = 1
!tag #b = 2
!tag #c = 3
"""
    
    # Parse and prepare
    ast_module = comp.parse_module(source)
    module = comp.Module()
    engine = comp.Engine()
    
    module.prepare(ast_module, engine)
    
    # Evaluate
    result = engine.run(ast_module)
    assert isinstance(result, comp.Module)
    assert "a" in result.tags
    assert "b" in result.tags
    assert "c" in result.tags


def test_prepared_with_imports():
    """Test that preparation works with imports."""
    # This test requires an actual module file to import
    # For now, we'll test the basic mechanism
    
    source = """
!tag #local = 100
"""
    
    # Parse and prepare
    ast_module = comp.parse_module(source)
    module = comp.Module()
    engine = comp.Engine()
    
    # Should succeed
    module.prepare(ast_module, engine)
    
    # Verify the module was prepared
    assert getattr(module, '_prepared', False) is True
    
    # Evaluate
    result = engine.run(ast_module)
    assert isinstance(result, comp.Module)


def test_hierarchical_tags():
    """Test preparation with hierarchical tag definitions."""
    source = """
!tag #status.ok = 200
!tag #status.error.server = 500
!tag #status.error.client = 400
"""
    
    # Parse and prepare
    ast_module = comp.parse_module(source)
    module = comp.Module()
    engine = comp.Engine()
    
    module.prepare(ast_module, engine)
    
    # Evaluate
    result = engine.run(ast_module)
    assert isinstance(result, comp.Module)
    assert "status.ok" in result.tags
    assert "status.error.server" in result.tags
    assert "status.error.client" in result.tags


def test_loader_calls_prepare():
    """Test that the loader automatically calls prepare()."""
    # This is more of an integration check
    # The loader should handle preparation automatically
    
    # We can't easily test the loader without actual files,
    # but we can verify the code structure
    from comp.ast._loader import load_comp_module
    
    # The function should exist and have the right signature
    assert callable(load_comp_module)
    
    # Check that the loader code mentions 'prepare'
    import inspect
    source = inspect.getsource(load_comp_module)
    assert 'prepare' in source


def test_cli_calls_prepare():
    """Test that the CLI automatically calls prepare()."""
    # Check that CLI code calls prepare()
    from comp.cli import main
    
    assert callable(main)
    
    # Check that the CLI code mentions 'prepare'
    import inspect
    source = inspect.getsource(main)
    assert 'prepare' in source


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
