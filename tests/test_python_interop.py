"""Test Python interop module with @py-handle."""

import comp
import comptest


def test_python_module_import():
    """Test that the python module can be imported from stdlib."""
    result = comptest.run_func("""
        !import /py = stdlib "python"
        
        !func |test ~{} = {
            ; Module imported successfully if this runs
            result = #true
        }
    """)
    
    assert not result.is_fail, f"Function failed: {result.to_python()}"
    result_value = result.data[comp.Value("result")]
    assert result_value.is_tag
    assert result_value.to_python() == True


def test_py_handle_exists():
    """Test that @py-handle is defined in python module."""
    result = comptest.run_func("""
        !import /py = stdlib "python"
        
        ; Re-export the handle so we can use it locally
        !handle @py-handle
        
        !func |test ~{} = {
            ; Try to grab a py-handle
            $var.obj = !grab @py-handle
            !drop $var.obj
            result = #true
        }
    """)
    
    assert not result.is_fail, f"Function failed: {result.to_python()}"
    result_value = result.data[comp.Value("result")]
    assert result_value.is_tag
    assert result_value.to_python() == True


def test_py_handle_drop_block_executes():
    """Test that py-handle drop-handle function is called."""
    result = comptest.run_func("""
        !import /py = stdlib "python"
        
        ; Re-export the handle so we can use it locally
        !handle @py-handle
        
        !func |test ~{} = {
            ; Create and drop a py-handle
            $var.obj = !grab @py-handle
            !drop $var.obj
            ; If we get here, drop-handle function didn't fail
            result = #true
        }
    """)
    
    assert not result.is_fail, f"Function failed: {result.to_python()}"
    result_value = result.data[comp.Value("result")]
    assert result_value.is_tag
    assert result_value.to_python() == True


def test_push():
    """Test converting Comp value to Python object (push)."""
    result = comptest.run_func("""
        !import /py = stdlib "python"
        
        !func |test ~{} = {
            ; Convert a simple Comp struct to Python (returns @py-handle)
            $var.comp_val = {name="Alice" age=30}
            $var.py_handle = [$var.comp_val |push/py]
            ; py_handle now contains a @py-handle wrapping the Python dict
            ; To verify, pull it back and check the values
            $var.back = [$var.py_handle |pull/py]
            result = $var.back
        }
    """)
    
    assert not result.is_fail, f"Function failed: {result.to_python()}"
    result = result.to_python()["result"]
    # The result should be the Comp struct converted back from Python
    assert isinstance(result, dict)
    assert result["name"] == "Alice"
    assert result["age"] == 30


def test_pull():
    """Test converting Python object back to Comp value (pull)."""
    result = comptest.run_func("""
        !import /py = stdlib "python"
        
        !func |test ~{} = {
            ; Create Python object
            $var.comp_val = {name="Bob" score=95}
            $var.py_obj = [$var.comp_val |push/py]
            ; Convert back to Comp
            $var.comp_val2 = [$var.py_obj |pull/py]
            result = $var.comp_val2
        }
    """)
    
    assert not result.is_fail, f"Function failed: {result.to_python()}"
    result_value = result.data[comp.Value("result")]
    assert result_value.is_struct
    # Check roundtrip conversion
    assert result_value.data[comp.Value("name")].data == "Bob"
    assert result_value.data[comp.Value("score")].data == 95


def test_roundtrip():
    """Test roundtrip conversion Comp -> Python -> Comp."""
    result = comptest.run_func("""
        !import /py = stdlib "python"
        
        !func |test ~{} = {
            $var.original = {
                name = "Charlie"
                items = {a=1 b=2 c=3}
                active = #true
            }
            ; Convert to Python and back
            $var.py_obj = [$var.original |push/py]
            $var.comp_copy = [$var.py_obj |pull/py]
            result = $var.comp_copy
        }
    """)
    
    assert not result.is_fail, f"Function failed: {result.to_python()}"
    result_value = result.data[comp.Value("result")]
    assert result_value.is_struct
    
    # Check nested structure
    assert result_value.data[comp.Value("name")].data == "Charlie"
    
    items = result_value.data[comp.Value("items")]
    assert items.data[comp.Value("a")].data == 1
    assert items.data[comp.Value("b")].data == 2
    assert items.data[comp.Value("c")].data == 3
    
    active = result_value.data[comp.Value("active")]
    assert active.is_tag
    assert active.to_python() == True

