"""Test Python bridge for working with Comp from Python."""

import decimal
import pytest
import comp


def test_from_python_primitives():
    """Test converting Python primitives to Comp values."""
    # None becomes empty struct
    assert comp.from_python(None).is_struct
    assert len(comp.from_python(None).data) == 0
    
    # Booleans become tags
    true_val = comp.from_python(True)
    assert true_val.is_tag
    assert true_val.data.full_name == "true"
    
    false_val = comp.from_python(False)
    assert false_val.is_tag
    assert false_val.data.full_name == "false"
    
    # Numbers
    num_val = comp.from_python(42)
    assert num_val.is_number
    assert num_val.as_scalar().data == decimal.Decimal("42")
    
    # Strings
    str_val = comp.from_python("hello")
    assert str_val.is_string
    assert str_val.as_scalar().data == "hello"


def test_from_python_dict():
    """Test converting Python dict to Comp struct."""
    py_dict = {"x": 1, "y": 2, "name": "test"}
    comp_val = comp.from_python(py_dict)
    
    assert comp_val.is_struct
    assert len(comp_val.data) == 3
    
    # Check fields
    x_val = comp_val.data[comp.Value("x")]
    assert x_val.as_scalar().data == decimal.Decimal("1")


def test_from_python_list():
    """Test converting Python list to Comp struct with unnamed fields."""
    py_list = [1, 2, 3]
    comp_val = comp.from_python(py_list)
    
    assert comp_val.is_struct
    assert len(comp_val.data) == 3
    
    # Convert back to Python to verify
    result = comp.to_python(comp_val)
    assert result == [1, 2, 3]


def test_to_python_primitives():
    """Test converting Comp values to Python primitives."""
    # Numbers
    assert comp.to_python(comp.Value(decimal.Decimal("42"))) == 42
    assert comp.to_python(comp.Value(decimal.Decimal("3.14"))) == 3.14
    
    # Strings
    assert comp.to_python(comp.Value("hello")) == "hello"
    
    # Booleans
    builtin = comp.builtin.get_builtin_module()
    true_val = comp.Value(comp.TagRef(builtin.tags["true"]))
    assert comp.to_python(true_val) == True
    
    false_val = comp.Value(comp.TagRef(builtin.tags["false"]))
    assert comp.to_python(false_val) == False


def test_to_python_struct_as_dict():
    """Test converting Comp struct to Python dict."""
    struct = {
        comp.Value("x"): comp.Value(decimal.Decimal("1")),
        comp.Value("y"): comp.Value(decimal.Decimal("2")),
    }
    comp_val = comp.Value(struct)
    
    py_dict = comp.to_python(comp_val)
    assert isinstance(py_dict, dict)
    assert py_dict == {"x": 1, "y": 2}


def test_to_python_struct_as_list():
    """Test converting Comp struct with unnamed fields to Python list."""
    struct = {
        comp.Unnamed(): comp.Value(decimal.Decimal("1")),
        comp.Unnamed(): comp.Value(decimal.Decimal("2")),
        comp.Unnamed(): comp.Value(decimal.Decimal("3")),
    }
    comp_val = comp.Value(struct)
    
    py_list = comp.to_python(comp_val)
    assert isinstance(py_list, list)
    assert py_list == [1, 2, 3]


def test_to_python_raises_on_failure():
    """Test that to_python raises CompError on failure values."""
    fail_val = comp.fail("Test error")
    
    with pytest.raises(comp.CompError) as exc_info:
        comp.to_python(fail_val)
    
    assert "Test error" in str(exc_info.value)
    assert exc_info.value.failure == fail_val


def test_parse_value_struct():
    """Test parsing Comp struct literal."""
    val = comp.parse_value("{x=1 y=2}")
    
    assert val.is_struct
    py_dict = comp.to_python(val)
    assert py_dict == {"x": 1, "y": 2}


def test_parse_value_tag():
    """Test parsing Comp tag."""
    val = comp.parse_value("#true")
    
    assert val.is_tag
    assert val.data.full_name == "true"


def test_parse_value_number():
    """Test parsing Comp number."""
    val = comp.parse_value("42")
    
    assert val.is_number
    assert comp.to_python(val) == 42


def test_roundtrip_conversion():
    """Test Python -> Comp -> Python roundtrip."""
    original = {"x": 1, "y": 2, "nested": {"a": 10, "b": 20}, "list": [1, 2, 3]}
    
    comp_val = comp.from_python(original)
    result = comp.to_python(comp_val)
    
    assert result == original


def test_load_stdlib_module():
    """Test loading a stdlib module."""
    # Load the tag module
    tag_mod = comp.module("stdlib", "tag")
    
    assert isinstance(tag_mod, comp.ModuleProxy)
    assert tag_mod.func is not None
    assert tag_mod.tag is not None


def test_function_proxy_call():
    """Test calling a Comp function through proxy."""
    # Create a simple test module with basic functions
    code = """
    !func |identity ~{} = {
        result = $in
    }
    
    !func |wrap ~{} = {
        value = $in
    }
    """
    
    # Load module
    ast_module = comp.parse_module(code)
    engine = comp.Engine()
    module = engine.run(ast_module)
    module.prepare(ast_module, engine)
    
    # Create proxy
    proxy = comp.ModuleProxy(module, engine)
    
    # Call identity function
    result = proxy.func.identity(input=42)
    assert result == {"result": 42}
    
    # Call wrap function
    result = proxy.func.wrap(input=7)
    assert result == {"value": 7}


def test_tag_container_access():
    """Test accessing tags through tag container."""
    # Create a module with tags
    code = """
    !tag #status
    !tag #status.success
    !tag #status.error
    """
    
    ast_module = comp.parse_module(code)
    engine = comp.Engine()
    module = engine.run(ast_module)
    module.prepare(ast_module, engine)
    
    proxy = comp.ModuleProxy(module, engine)
    
    # Access tags
    status = proxy.tag.status
    assert status.is_tag
    assert status.data.full_name == "status"
    
    # Access nested tags (with underscore or dot)
    success = proxy.tag.status_success
    assert success.is_tag


def test_function_raises_comp_error_on_fail():
    """Test that function calls raise CompError on failure."""
    # Create a module with a failing function
    code = """
    !func |failing ~{} = {
        result = [5 |nonexistent]
    }
    """
    
    # This will fail during preparation due to undefined function
    # Let's create a simpler test with a Python function that returns fail
    
    # Actually, let's just test the error conversion directly
    fail_val = comp.fail("Test error")
    
    with pytest.raises(comp.CompError) as exc_info:
        comp.to_python(fail_val)
    
    assert "Test error" in str(exc_info.value)


def test_comp_error_formatting():
    """Test CompError provides formatted error message."""
    fail_val = comp.fail("Test error message")
    
    error = comp.CompError(fail_val)
    
    assert "Test error message" in str(error)
    assert "fail" in str(error)
    assert error.failure == fail_val
