"""Test function system."""

import comp
import comptest


def test_function_with_wrong_input_type():
    """Test function with wrong input type."""
    value = comptest.run_frame("double", "not a number", None)
    comptest.assert_fail(value, "expects num")


def test_function_missing_required_arg():
    """Test function with missing required argument."""
    value = comptest.run_frame("add", 5, None)
    comptest.assert_fail(value, "Missing required field 'n'")


def test_function_dispatch_by_shape():
    """Test that functions dispatch to most specific overload based on input shape."""
    code = """
!shape ~point = {x ~num y ~num}
!shape ~rect = {width ~num height ~num}

!func |area ~point = {
    result = "point"
}

!func |area ~rect = {
    result = $in.width * $in.height
}

!func |test ~{} = {
    point_result = [{x=5 y=10} |area]
    rect_result = [{width=5 height=10} |area]
}
"""
    result = comptest.run_func(code)
    comptest.assert_value(result, point_result="point", rect_result=50)


def test_function_dispatch_with_wildcard():
    """Test that wildcard (no shape) functions work as fallback.

    Note: Morphing wraps primitives to match struct shapes, so 42 will
    morph to {value=42} to match ~special. To test wildcard fallback,
    use a struct that doesn't match the specific shape.
    """
    code = """
!shape ~special = {value ~num}

!func |process ~special = {
    result = $in.value + 100
}

!func |process ~{} = {
    result = 999
}

!func |test ~{} = {
    special = [{value=5} |process]
    numeric = [42 |process]
    generic = [{other=42} |process]
}
"""
    result = comptest.run_func(code)
    comptest.assert_value(result, special=105, numeric=142, generic=999)
def test_function_dispatch_most_specific():
    """Test that most specific shape wins in dispatch."""
    code = """
!shape ~animal = {name ~str}
!shape ~dog = {..~animal breed ~str}

!func |describe ~animal = {
    result = "animal"
}

!func |describe ~dog = {
    result = "dog"
}

!func |test ~{} = {
    animalret = [{name="Generic"} |describe]
    dogret = [{name="Buddy" breed="Golden"} |describe]
}
"""
    result = comptest.run_func(code)
    comptest.assert_value(result, animalret="animal", dogret="dog")


def test_function_dispatch_no_match():
    """Test that dispatch fails when no overload matches."""
    code = """
!shape ~point = {x ~num y ~num}

!func |process ~point = {
    result = x + y
}

!func |test ~{} = {
    result = ["hello" |process]
}
"""
    result = comptest.run_func(code)
    comptest.assert_fail(result, "no overload matches")


def test_function_dispatch_score_ordering():
    """Test that dispatch uses score ordering based on field counts."""
    code = """
!shape ~basic = {value ~num}
!shape ~extended = {value ~num extra ~num}

!func |check ~basic = {
    result = "basic"
}

!func |check ~extended = {
    result = "extended"
}

!func |test ~{} = {
    basic_result = [{value=42} |check]
    extended_result = [{value=42 extra=10} |check]
}
"""
    result = comptest.run_func(code)
    comptest.assert_value(result, basic_result="basic", extended_result="extended")

