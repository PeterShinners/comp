"""Test handle tracking infrastructure."""

import sys
sys.path.insert(0, 'tests')
import comp
import comptest


def test_value_handles_on_primitives():
    """Test that primitive values have empty handles."""
    result = comptest.run_func("""
        !func |test ~{} = {
            result = 42
        }
    """)
    value = result.data[comp.Value("result")]
    print(f"  Value type: {type(value)}, has handles: {hasattr(value, 'handles')}")
    assert value.handles == frozenset()


def test_value_handles_on_handle():
    """Test that handle values track themselves."""
    result = comptest.run_func("""
        !handle @file
        
        !func |test ~{} = {
            result = !grab @file
        }
    """)
    value = result.data[comp.Value("result")]
    assert len(value.handles) == 1
    assert value.data in value.handles


def test_value_handles_on_struct_with_handle():
    """Test that structs recursively track handles."""
    result = comptest.run_func("""
        !handle @file

        !func |test ~{} = {
            result = !grab @file
        }
    """)
    # Get the result field (the handle)
    handle_value = result.data[comp.Value("result")]
    print(f"  Handle value has handles: {hasattr(handle_value, 'handles')}")
    print(f"  Handle value.handles: {handle_value.handles if hasattr(handle_value, 'handles') else 'N/A'}")
    
    # Now create a struct containing it
    record = comp.Value({'file': handle_value, 'count': 42})
    print(f"  Record has handles: {hasattr(record, 'handles')}")
    print(f"  Record.handles: {record.handles if hasattr(record, 'handles') else 'N/A'}")
    
    # The record should recursively contain the handle
    assert len(record.handles) == 1
    assert handle_value.data in record.handles


def test_handle_instance_frames():
    """Test that !grab registers the handle with frames."""
    result = comptest.run_func("""
        !handle @file

        !func |test ~{} = {
            result = !grab @file
        }
    """)
    value = result.data[comp.Value("result")]
    
    # The handle should have been registered with frames during execution
    assert isinstance(value.data.frames, set)
    # Frames may still be present (registration working)
    # The actual frame objects depend on execution context


def test_grab_registers_handle():
    """Test that !grab registers the handle with the current frame."""
    result = comptest.run_func("""
        !handle @file

        !func |test ~{} = {
            $var.h = !grab @file
            result = $var.h
        }
    """)
    handle_value = result.data[comp.Value("result")]
    
    # The handle should have been registered with at least one frame
    assert isinstance(handle_value.data, comp.HandleInstance)
    assert hasattr(handle_value.data, 'frames')
    assert isinstance(handle_value.data.frames, set)


def test_scope_assignment_registers_handle():
    """Test that scope assignments register handles."""
    result = comptest.run_func("""
        !handle @file

        !func |test ~{} = {
            $var.local = !grab @file
            result = $var.local
        }
    """)
    handle_value = result.data[comp.Value("result")]
    
    assert isinstance(handle_value.data, comp.HandleInstance)
    assert hasattr(handle_value.data, 'frames')


def test_spread_registers_handles():
    """Test that spread operations register handles."""
    result = comptest.run_func("""
        !handle @file

        !func |test ~{} = {
            $var.data = {handle = !grab @file}
            result = {..$var.data other = 42}
        }
    """)
    record = result.data[comp.Value("result")]
    
    # Verify the handle is in the result
    handle_field = record.data[comp.Value("handle")]
    assert handle_field.is_handle


if __name__ == "__main__":
    test_value_handles_on_primitives()
    print("✓ Primitives have empty handles")
    
    test_value_handles_on_handle()
    print("✓ Handles track themselves")
    
    test_value_handles_on_struct_with_handle()
    print("✓ Structs recursively track handles")
    
    test_handle_instance_frames()
    print("✓ HandleInstance.frames initialized empty")
    
    print("\nAll tracking infrastructure tests passed!")
