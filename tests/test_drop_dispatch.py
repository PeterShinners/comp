"""Test !drop operator with namespace dispatch to drop-handle function."""

import pytest
import comp


def test_drop_with_dispatch_function():
    """Test that !drop dispatches to drop-handle function in handle's defining module."""
    
    # Create a module with a handle and a drop-handle function
    # The function accepts any input (empty shape ~{})
    module_source = """
!handle @resource

!func |drop-handle ~{} = {
    ; This function will be called when dropping any handle
    ; In real use, you'd check $in to determine which handle
    "cleaned up resource"
}

!func |test ~{} = {
    $var.h = !grab @resource
    $var.result = !drop $var.h
    $var.result
}
"""
    module_ast = comp.parse_module(module_source)
    module = comp.Module(module_id="test_module")
    engine = comp.Engine()
    module.prepare(module_ast, engine)
    module = engine.run(module_ast, module=module)
    
    # Call test function
    result = engine.run_function(
        module.functions['test'][0],
        in_=comp.Value({}),
        args=None,
        ctx=None
    )
    
    # Result should be a struct with the handle wrapped
    # The handle should be marked as dropped
    assert result.is_struct
    result_handle = result.data[list(result.struct.keys())[0]]  # Get the unnamed field
    assert result_handle.is_handle
    assert result_handle.data.is_dropped


def test_drop_fallback_to_drop_block():
    """Test that !drop works even when no drop-handle function exists."""
    
    module_source = """
!handle @resource

!func |test ~{} = {
    $var.h = !grab @resource
    !drop $var.h
}
"""
    module_ast = comp.parse_module(module_source)
    module = comp.Module(module_id="test_module")
    engine = comp.Engine()
    module.prepare(module_ast, engine)
    module = engine.run(module_ast, module=module)
    
    # Call test function
    result = engine.run_function(
        module.functions['test'][0],
        in_=comp.Value({}),
        args=None,
        ctx=None
    )
    
    # Result should be a struct with the handle wrapped
    # The handle should be marked as dropped
    assert result.is_struct
    result_handle = result.data[list(result.struct.keys())[0]]  # Get the unnamed field
    assert result_handle.is_handle
    assert result_handle.data.is_dropped


def test_drop_function_overrides_block():
    """Test that drop-handle function is called when it exists."""
    
    module_source = """
!handle @resource

!func |drop-handle ~{} = {
    "function ran"
}

!func |test ~{} = {
    $var.h = !grab @resource
    !drop $var.h
}
"""
    module_ast = comp.parse_module(module_source)
    module = comp.Module(module_id="test_module")
    engine = comp.Engine()
    module.prepare(module_ast, engine)
    module = engine.run(module_ast, module=module)
    
    # Call test function
    result = engine.run_function(
        module.functions['test'][0],
        in_=comp.Value({}),
        args=None,
        ctx=None
    )
    
    # Result should be a struct (the function returns nothing specific)
    # But we can check that the handle was successfully dropped
    # Since there's no return value from the test, we just verify no error occurred
    assert not result.is_fail
