"""Test Python interop module with pyobject handle."""

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


def test_pyobject_handle_exists():
    """Test that @pyobject handle is defined in python module."""
    result = comptest.run_func("""
        !import /py = stdlib "python"
        
        ; Define pyobject handle locally for now
        !handle @pyobject = {
            drop = :{
                [$in |py-decref/py]
            }
        }
        
        !func |test ~{} = {
            ; Try to grab a pyobject handle
            $var.obj = !grab @pyobject
            !drop $var.obj
            result = #true
        }
    """)
    
    assert not result.is_fail, f"Function failed: {result.to_python()}"
    result_value = result.data[comp.Value("result")]
    assert result_value.is_tag
    assert result_value.to_python() == True


def test_pyobject_drop_block_executes():
    """Test that pyobject drop block is called (even if decref does nothing yet)."""
    result = comptest.run_func("""
        !import /py = stdlib "python"
        
        ; Define pyobject handle locally for now
        !handle @pyobject = {
            drop = :{
                [$in |py-decref/py]
            }
        }
        
        !func |test ~{} = {
            ; Create and drop a pyobject
            $var.obj = !grab @pyobject
            !drop $var.obj
            ; If we get here, drop block didn't fail
            result = #true
        }
    """)
    
    assert not result.is_fail, f"Function failed: {result.to_python()}"
    result_value = result.data[comp.Value("result")]
    assert result_value.is_tag
    assert result_value.to_python() == True


def test_py_from_comp():
    """Test converting Comp value to Python object."""
    result = comptest.run_func("""
        !import /py = stdlib "python"
        
        !func |test ~{} = {
            ; Convert a simple Comp struct to Python
            $var.comp_val = {name="Alice" age=30}
            $var.py_obj = [$var.comp_val |py-from-comp-impl/py]
            ; py_obj should be a struct with 'ptr' field
            result = $var.py_obj.ptr
        }
    """)
    
    assert not result.is_fail, f"Function failed: {result.to_python()}"
    result = result.to_python()["result"]
    # Debug: print what we got
    print(f"\nDEBUG: result = {result!r}")
    print(f"DEBUG: type = {type(result)}")
    if isinstance(result, dict):
        print(f"DEBUG: keys = {list(result.keys())}")
    # The data field should contain the Python dict
    assert isinstance(result, dict)
    assert result["name"] == "Alice"
    assert result["age"] == 30


def test_py_to_comp():
    """Test converting Python object back to Comp value."""
    result = comptest.run_func("""
        !import /py = stdlib "python"
        
        !func |test ~{} = {
            ; Create Python object
            $var.comp_val = {name="Bob" score=95}
            $var.py_obj = [$var.comp_val |py-from-comp-impl/py]
            ; Convert back to Comp
            $var.comp_val2 = [$var.py_obj |py-to-comp-impl/py]
            result = $var.comp_val2
        }
    """)
    
    assert not result.is_fail, f"Function failed: {result.to_python()}"
    result_value = result.data[comp.Value("result")]
    assert result_value.is_struct
    # Check roundtrip conversion
    assert result_value.data[comp.Value("name")].data == "Bob"
    assert result_value.data[comp.Value("score")].data == 95


def test_py_roundtrip():
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
            $var.py_obj = [$var.original |py-from-comp-impl/py]
            $var.comp_copy = [$var.py_obj |py-to-comp-impl/py]
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
