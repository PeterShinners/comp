"""Tests for handle grabbing and dropping (!grab and !drop operations)."""

import pytest
import comp
import comptest


def test_grab_handle_basic():
    """Test basic handle grabbing from owning module."""
    result = comptest.run_func("""
        !handle @file = {}
        
        !func |test ~{} = {
            $var.f = !grab @file
            result = $var.f
        }
    """)
    
    assert not result.is_fail
    
    # Should return a handle instance
    result_value = result.data[comp.Value("result")]
    assert result_value.is_handle
    handle_data = result_value.data
    assert isinstance(handle_data, comp.HandleInstance)
    assert not handle_data.is_dropped
    assert handle_data.full_name == "file"


def test_grab_handle_hierarchical():
    """Test grabbing nested handle from hierarchy."""
    result = comptest.run_func("""
        !handle @file
        !handle @file.readonly

        !func |test ~{} = {
            $var.f = !grab @file.readonly
            result = $var.f
        }
    """)
    assert not result.is_fail
    result_value = result.data[comp.Value("result")]
    assert result_value.is_handle
    
    handle_data = result_value.data
    assert isinstance(handle_data, comp.HandleInstance)
    assert handle_data.full_name == "file.readonly"


def test_drop_handle_basic():
    """Test basic handle dropping."""
    result = comptest.run_func("""
        !handle @file = {}
        
        !func |test ~{} = {
            $var.f = !grab @file
            !drop $var.f
            result = $var.f
        }
    """)
    
    assert not result.is_fail
    
    # Should return a dropped handle
    result_value = result.data[comp.Value("result")]
    assert result_value.is_handle
    handle_data = result_value.data
    assert isinstance(handle_data, comp.HandleInstance)
    assert handle_data.is_dropped


def test_drop_handle_idempotent():
    """Test that dropping a handle multiple times is safe."""
    result = comptest.run_func("""
        !handle @file = {}
        
        !func |test ~{} = {
            $var.f = !grab @file
            !drop $var.f
            !drop $var.f
            !drop $var.f
            result = $var.f
        }
    """)
    
    assert not result.is_fail
    
    result_value = result.data[comp.Value("result")]
    handle_data = result_value.data
    assert handle_data.is_dropped


def test_dropped_handle_fails_morph():
    """Test that dropped handles cannot be morphed."""
    result = comptest.run_func("""
        !handle @file = {}
        
        !shape ~output = {
            f @file
        }
        
        !func |test ~{} = {
            $var.f = !grab @file
            !drop $var.f
            result = {f=$var.f} ~output
        }
    """)
    
    # Should fail because handle is dropped
    assert result.is_fail
    # Result will be in one of the error field
    comptest.assert_fail(result, "dropped")


def test_handle_instance_vs_ref():
    """Test that handle instances can be dropped after grabbing."""
    result = comptest.run_func("""
        !handle @file = {}
        
        !func |test ~{} = {
            $var.grabbed = !grab @file
            !drop $var.grabbed
            result = $var.grabbed
        }
    """)
    
    # Should succeed - handle instance can be dropped
    assert not result.is_fail
    result_value = result.data[comp.Value("result")]
    assert result_value.is_handle
    assert result_value.data.is_dropped


def test_grab_handle_morph_to_parent():
    """Test that grabbed handles can morph to parent types."""
    result = comptest.run_func("""
        !handle @file
        !handle @file.readonly
        
        !shape ~output = {
            f @file
        }
        
        !func |test ~{} = {
            $var.f = !grab @file.readonly
            result = {f=$var.f} ~output
        }
    """)
    
    assert not result.is_fail
    
    # Should successfully morph child to parent
    result_value = result.data[comp.Value("result")]
    assert result_value.is_struct
    f_value = result_value.data[comp.Value("f")]
    assert f_value.is_handle
    assert f_value.data.full_name == "file.readonly"


def test_drop_non_handle():
    """Test that dropping non-handles fails."""
    result = comptest.run_func("""
        !func |test ~{} = {
            $var.x = 42
            !drop $var.x
            result = $var.x
        }
    """)
    
    # Should fail because $var.x is not a handle
    assert result.is_fail
    comptest.assert_fail(result, "handle")


def test_grab_undefined_handle():
    """Test that grabbing undefined handle fails."""
    result = comptest.run_func("""
        !func |test ~{} = {
            $var.f = !grab @undefined
            result = $var.f
        }
    """)
    
    # Should fail because @undefined doesn't exist
    assert result.is_fail
