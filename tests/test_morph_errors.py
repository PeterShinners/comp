"""Tests for morph error messages."""

import comp
import comptest


def test_morph_missing_field_error():
    """Test that missing required field produces a descriptive error."""
    code = """
!shape ~user = {name ~str email ~str}

!func |test ~{} = {
    result = {name="Alice"} ~user
}
"""
    result = comptest.run_func(code)
    
    # Should be a fail value with message containing field name
    comptest.assert_fail(result, "Missing required field 'email'")


def test_morph_type_mismatch_error():
    """Test that type mismatch produces a descriptive error."""
    code = """
!shape ~user = {age ~num}

!func |test ~{} = {
    result = {age="not a number"} ~user
}
"""
    result = comptest.run_func(code)
    
    # Should be a fail value with type mismatch message
    comptest.assert_fail(result, "Wrong type")
    comptest.assert_fail(result, "'age'")
    comptest.assert_fail(result, "expected ~num")


def test_strong_morph_extra_field_error():
    """Test that strong morph with extra field produces a descriptive error."""
    code = """
!shape ~user = {name ~str}

!func |test ~{} = {
    result = {name="Alice" extra="not allowed"} ~* user
}
"""
    result = comptest.run_func(code)
    
    # Should be a fail value
    assert result.is_fail
    
    # Check the error message
    fail_struct = result.data
    message = fail_struct[comp.Value('message')]
    assert message.data == "Extra field 'extra' not allowed in strong morph"


def test_morph_nested_type_error():
    """Test that nested type errors propagate correctly."""
    code = """
!shape ~point = {x ~num y ~num}

!func |test ~{} = {
    result = {x="not a number" y=10} ~point
}
"""
    result = comptest.run_func(code)
    
    # Should be a fail value
    assert result.is_fail
    
    # Check the error message contains field information
    fail_struct = result.data
    message = fail_struct[comp.Value('message')]
    # Should mention the 'x' field
    assert "'x'" in message.data
    assert "expected ~num" in message.data


def test_morph_positional_type_error():
    """Test that positional field type errors are descriptive."""
    code = """
!shape ~pair = {~num ~num}

!func |test ~{} = {
    result = {"not a number" 42} ~pair
}
"""
    result = comptest.run_func(code)
    
    # Should be a fail value
    assert result.is_fail
    
    # Check the error message
    fail_struct = result.data
    message = fail_struct[comp.Value('message')]
    # Should mention positional field
    assert "positional field #0" in message.data.lower() or "field #0" in message.data
    assert "expected ~num" in message.data
