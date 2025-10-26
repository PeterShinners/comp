"""Test handle drop block execution."""

import comp
import comptest


def test_drop_block_executes():
    """Test that drop blocks are executed when handle is dropped."""
    result = comptest.run_func("""
        !handle @file = {
            drop = :{
                ; Drop block sets a marker in $var
                $var.dropped = #true
            }
        }
        
        !func |test ~{} = {
            $var.dropped = #false
            $var.f = !grab @file
            !drop $var.f
            result = $var.dropped
        }
    """)
    
    assert not result.is_fail, f"Function failed: {result.to_python()}"
    result_value = result.data[comp.Value("result")]
    assert result_value.is_tag
    assert result_value.as_scalar().to_python() == True  # Tags convert to Python bool


def test_drop_block_with_variable_access():
    """Test that drop blocks can access and modify $var."""
    result = comptest.run_func("""
        !handle @file = {
            drop = :{
                ; Drop block increments counter
                $var.count = $var.count + 1
            }
        }
        
        !func |test ~{} = {
            $var.count = 0
            $var.f1 = !grab @file
            $var.f2 = !grab @file
            !drop $var.f1
            !drop $var.f2
            result = $var.count
        }
    """)
    
    assert not result.is_fail, f"Function failed: {result.to_python()}"
    result_value = result.data[comp.Value("result")]
    assert result_value.as_scalar().to_python() == 2


def test_drop_block_idempotent():
    """Test that drop block only executes once even with multiple drops."""
    result = comptest.run_func("""
        !handle @file = {
            drop = :{
                $var.count = $var.count + 1
            }
        }
        
        !func |test ~{} = {
            $var.count = 0
            $var.f = !grab @file
            !drop $var.f
            !drop $var.f
            !drop $var.f
            result = $var.count
        }
    """)
    
    assert not result.is_fail, f"Function failed: {result.to_python()}"
    result_value = result.data[comp.Value("result")]
    # Should only execute once despite three drops
    assert result_value.as_scalar().to_python() == 1


def test_drop_block_failure():
    """Test that drop block failures are propagated."""
    result = comptest.run_func("""
        !handle @file = {
            drop = :{
                #fail "cleanup failed"
            }
        }
        
        !func |test ~{} = {
            $var.f = !grab @file
            !drop $var.f
            result = #true
        }
    """)
    
    assert result.is_fail
    # The failure should contain "cleanup failed" in the message
    fail_data = result.to_python()
    assert fail_data.get("message") == "cleanup failed" or "cleanup failed" in str(fail_data)


def test_no_drop_block():
    """Test that handles without drop blocks work normally."""
    result = comptest.run_func("""
        !handle @file = {}
        
        !func |test ~{} = {
            $var.f = !grab @file
            !drop $var.f
            result = $var.f
        }
    """)
    
    assert not result.is_fail, f"Function failed: {result.to_python()}"
    result_value = result.data[comp.Value("result")]
    assert result_value.is_handle
    assert result_value.data.is_dropped
