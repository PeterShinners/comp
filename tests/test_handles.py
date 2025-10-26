"""Tests for handle definitions, references, and morphing."""

import comp
import comptest


def test_handle_definition():
    """Test basic handle definition and lookup."""
    # Define handles using the actual syntax (separate declarations)
    code = """
    !handle @file
    !handle @file.readonly
    !handle @file.writable
    
    !func |test ~{} = {
        result = #true
    }
    """
    module_ast = comp.parse_module(code)
    engine = comp.Engine()
    module = comp.Module()
    module.prepare(module_ast, engine)
    
    # Check handles were defined
    assert "file" in module.handles
    assert "file.readonly" in module.handles
    assert "file.writable" in module.handles
    
    file_handle = module.handles["file"]
    assert file_handle.full_name == "file"
    # Children are separate definitions, not stored in parent


def test_handle_reference():
    """Test handle references create HandleRef values."""
    code = """
    !handle @file
    !handle @file.readonly
    
    !func |test ~any = {
        $var.h = !grab @file.readonly
        result = $var.h
    }
    """
    result = comptest.run_func(code)
    
    # Result should contain a handle
    assert not result.is_fail
    result_value = result.data[comp.Value("result")]
    assert result_value.is_handle
    assert result_value.data.full_name == "file.readonly"


def test_handle_shape_matching():
    """Test morphing handle values to handle shapes."""
    code = """
    !handle @file
    !handle @file.readonly
    !handle @file.writable
    
    !shape ~reader = {
        handle @file.readonly
    }
    
    !func |test ~any = {
        $var.h = !grab @file.readonly
        result = $var.h ~reader
    }
    """
    result = comptest.run_func(code)
    
    # Should successfully morph
    assert not result.is_fail
    result_value = result.data[comp.Value("result")]
    assert result_value.is_struct
    handle_val = result_value.data[comp.Value("handle")]
    assert handle_val.is_handle
    assert handle_val.data.full_name == "file.readonly"


def test_handle_hierarchy_matching():
    """Test that child handles match parent handle shapes."""
    code = """
    !handle @file
    !handle @file.readonly
    !handle @file.readonly.text
    !handle @file.readonly.binary
    
    !shape ~file_reader = {
        f @file.readonly
    }
    
    !func |test ~any = {
        $var.h = !grab @file.readonly.text
        result = {f=$var.h} ~file_reader
    }
    """
    result = comptest.run_func(code)
    
    # Child handle should match parent shape
    assert not result.is_fail
    result_value = result.data[comp.Value("result")]
    assert result_value.is_struct
    f_val = result_value.data[comp.Value("f")]
    assert f_val.is_handle
    assert f_val.data.full_name == "file.readonly.text"


def test_handle_mismatch():
    """Test that unrelated handles don't match."""
    code = """
    !handle @file
    !handle @file.readonly
    !handle @network
    !handle @network.socket
    
    !shape ~reader = {
        h @file.readonly
    }
    
    !func |test ~any = {
        $var.h = !grab @network.socket
        result = {h=$var.h} ~reader
    }
    """
    result = comptest.run_func(code)
    
    # Should fail to morph
    assert result.is_fail


def test_handle_no_value_morphing():
    """Test that handles cannot morph from primitive values."""
    code = """
    !handle @file
    !handle @file.readonly
    
    !shape ~reader = {
        h @file.readonly
    }
    
    !func |test ~any = {
        result = {h="some string"} ~reader
    }
    """
    result = comptest.run_func(code)
    
    # Should fail - handles don't have values
    assert result.is_fail


def test_handle_in_struct_greedy_matching():
    """Test that handles are matched before tags in structs."""
    code = """
    !handle @file
    !handle @file.readonly
    !tag #status
    !tag #status.ok
    
    !shape ~result = {
        file @file.readonly
        status #status.ok
    }
    
    !func |test ~any = {
        $var.h = !grab @file.readonly
        result = {file=$var.h status=#status.ok} ~result
    }
    """
    result = comptest.run_func(code)
    
    # Both should be matched correctly
    assert not result.is_fail
    result_value = result.data[comp.Value("result")]
    assert result_value.is_struct
    file_val = result_value.data[comp.Value("file")]
    status_val = result_value.data[comp.Value("status")]
    assert file_val.is_handle
    assert status_val.is_tag
    
    assert file_val.is_handle
    assert file_val.data.full_name == "file.readonly"
    
    assert status_val.is_tag
    assert status_val.data.full_name == "status.ok"
