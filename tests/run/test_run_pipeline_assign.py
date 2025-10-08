"""Test pipelines and assignments: basic pipes, nested assignment, index assignment."""

import runtest


def test_simple_pipeline():
    """Test basic pipeline."""
    code = """
    !func |double ~{x ~num} = {
        result = x * 2
    }
    
    !func |test ~_ = {
        value = [{x=5} |double]
    }
    """
    result = runtest.run_function(code, "test", {})
    value_field = runtest.get_field(result, "value")
    assert runtest.get_field_python(value_field, "result") == 10


def test_multi_stage_pipeline():
    """Test pipeline with multiple stages."""
    code = """
    !func |add-one ~{x ~num} = {
        result = x + 1
    }
    
    !func |double ~{result ~num} = {
        result = result * 2
    }
    
    !func |test ~_ = {
        value = [{x=5} |add-one |double]
    }
    """
    # {x=5} -> {result=6} -> {result=12}
    result = runtest.run_function(code, "test", {})
    value_field = runtest.get_field(result, "value")
    assert runtest.get_field_python(value_field, "result") == 12


@runtest.params(
    "code, expected",
    # Simple nested
    simple=("obj.x = 10", {"obj": {"x": 10}}),
    # Deep nested
    deep=("a.b.c = 42", {"a": {"b": {"c": 42}}}),
    # Multiple nested
    multi=("obj.x = 1\nobj.y = 2", {"obj": {"x": 1, "y": 2}}),
)
def test_nested_assignment(key, code, expected):
    """Test nested field assignment creates intermediate structures."""
    full_code = f"!func |test ~_ = {{\n{code}\n}}"
    result = runtest.run_function(full_code, "test", {})
    
    for field_name, field_value in expected.items():
        actual = runtest.get_field_python(result, field_name)
        assert actual == field_value
