"""Tests for module-private data system using & syntax."""

import pytest

import comp


def test_module_identifier_default():
    """Test that modules get unique identifiers by default."""
    mod1 = comp.Module()
    mod2 = comp.Module()
    
    # Each module should have a unique ID (using counter)
    assert isinstance(mod1.module_id, int)
    assert isinstance(mod2.module_id, int)
    assert mod1.module_id != mod2.module_id


def test_module_identifier_custom():
    """Test that modules can be created with custom identifiers."""
    mod1 = comp.Module(module_id="my_module")
    mod2 = comp.Module(module_id="stdlib.fs")
    
    # Custom IDs have counter appended
    assert mod1.module_id.startswith("my_module:")
    assert mod2.module_id.startswith("stdlib.fs:")
    # Still unique
    assert mod1.module_id != mod2.module_id


def test_module_identifier_human_readable():
    """Test that custom identifiers can include human-readable names."""
    mod = comp.Module(module_id="stdlib.fs")
    
    # Format is "name:counter"
    assert "stdlib.fs:" in mod.module_id
    parts = mod.module_id.split(":")
    assert len(parts) == 2
    assert parts[0] == "stdlib.fs"
    assert parts[1].isdigit()


def test_value_private_data_storage():
    """Test that Values can store module-private data."""
    value = comp.Value(42)
    
    # Initially no private data
    assert value.private == {}
    assert value.get_private("module1") is None
    
    # Set private data for a module (mutates in place)
    private_data = comp.Value({"fd": 3, "path": "/data.txt"})
    value.set_private("module1", private_data)
    
    # Value now has private data
    retrieved = value.get_private("module1")
    assert retrieved is not None
    assert retrieved.is_struct
    assert retrieved.data[comp.Value("fd")].data == 3
    assert retrieved.data[comp.Value("path")].data == "/data.txt"


def test_value_private_data_multiple_modules():
    """Test that Values can store private data for multiple modules."""
    value = comp.Value("shared_value")
    
    # Module 1 attaches its private data
    mod1_data = comp.Value({"fd": 3})
    value.set_private("module1", mod1_data)
    
    # Module 2 attaches different private data
    mod2_data = comp.Value({"handle": "abc123"})
    value.set_private("module2", mod2_data)
    
    # Both modules' data is preserved
    assert value.get_private("module1").data[comp.Value("fd")].data == 3
    assert value.get_private("module2").data[comp.Value("handle")].data == "abc123"


def test_value_private_data_replacement():
    """Test replacing private data entirely (immutable like all values)."""
    value = comp.Value("base")
    
    # Set initial private data
    private_data = comp.Value({
        "fd": 3,
        "path": "/data.txt",
        "bytes_read": 0
    })
    value.set_private("fs_module", private_data)
    
    # Replace with updated private data (the way assignment works in Comp)
    updated_private = comp.Value({
        "fd": 3,
        "path": "/data.txt",
        "bytes_read": 4096
    })
    value.set_private("fs_module", updated_private)
    
    # Check replaced value
    private = value.get_private("fs_module")
    assert private.data[comp.Value("bytes_read")].data == 4096
    assert private.data[comp.Value("fd")].data == 3
    assert private.data[comp.Value("path")].data == "/data.txt"


def test_value_private_data_copied_on_value_copy():
    """Test that private data is shared when Value is copied."""
    value1 = comp.Value(42)
    value1.set_private("mod1", comp.Value({"data": "secret"}))
    
    # Create new Value from existing (copy constructor)
    value2 = comp.Value(value1)
    
    # Both should have private data
    assert value1.get_private("mod1") is not None
    assert value2.get_private("mod1") is not None
    
    # They should point to the same private data dict
    # (shared reference for immutability)
    assert value1.get_private("mod1").data[comp.Value("data")].data == "secret"
    assert value2.get_private("mod1").data[comp.Value("data")].data == "secret"


def test_private_data_isolation():
    """Test that private data is isolated between modules."""
    value = comp.Value("handle")
    
    # Module 1 sets private data
    value.set_private("module1", comp.Value({"secret": "mod1_data"}))
    
    # Module 2 cannot see module 1's private data
    assert value.get_private("module2") is None
    
    # Module 2 sets its own private data
    value.set_private("module2", comp.Value({"secret": "mod2_data"}))
    
    # Each module only sees its own data
    assert value.get_private("module1").data[comp.Value("secret")].data == "mod1_data"
    assert value.get_private("module2").data[comp.Value("secret")].data == "mod2_data"


def test_handle_pattern_simulation():
    """Simulate the handle pattern: handle type + private data."""
    # In the future, this will be a Handle instance
    # For now, simulate with a tagged value
    
    mod_fs = comp.Module(module_id="stdlib.fs")
    
    # Create "handle" (for now just a value with a tag)
    handle = comp.Value(comp.TagRef(["filehandle"]))
    
    # Attach private data using module ID
    handle.set_private(mod_fs.module_id, comp.Value({
        "fd": 3,
        "path": "/data.txt",
        "mode": "r",
        "bytes_read": 0
    }))
    
    # Simulate |read operation - get private data
    private = handle.get_private(mod_fs.module_id)
    assert private.data[comp.Value("fd")].data == 3
    
    # Update bytes_read by replacing entire private data (immutable)
    updated_private = comp.Value({
        "fd": 3,
        "path": "/data.txt",
        "mode": "r",
        "bytes_read": 4096
    })
    handle.set_private(mod_fs.module_id, updated_private)
    
    # Verify update
    final_private = handle.get_private(mod_fs.module_id)
    assert final_private.data[comp.Value("bytes_read")].data == 4096
    
    # Other module cannot access fs module's private data
    assert handle.get_private("other_module") is None


def test_as_scalar_as_struct_preserves_identity():
    """Test that as_scalar and as_struct preserve object identity when no transformation needed."""
    # Scalar stays scalar
    v1 = comp.Value(5)
    v2 = v1.as_scalar()
    assert v1 is v2  # Same object
    
    # Struct stays struct
    v3 = comp.Value({"name": "test"})
    v4 = v3.as_struct()
    assert v3 is v4  # Same object


def test_as_scalar_as_struct_round_trip_identity():
    """Test that as_struct().as_scalar() round trip preserves identity for scalars."""
    v1 = comp.Value(5)
    v2 = v1.as_struct().as_scalar()
    assert v1 is v2  # Round trip returns same object!


def test_as_scalar_as_struct_preserves_private_data():
    """Test that as_scalar and as_struct preserve private data through transformations."""
    mod = comp.Module(module_id="test_mod")
    
    # Create scalar with private data
    value = comp.Value(42)
    value.set_private(mod.module_id, comp.Value({"secret": "data"}))
    
    # Wrap to struct - should preserve private data
    wrapped = value.as_struct()
    assert wrapped.get_private(mod.module_id) is not None
    assert wrapped.get_private(mod.module_id).data[comp.Value("secret")].data == "data"
    
    # Unwrap back to scalar - should preserve private data
    unwrapped = wrapped.as_scalar()
    assert unwrapped.get_private(mod.module_id) is not None
    assert unwrapped.get_private(mod.module_id).data[comp.Value("secret")].data == "data"


def test_as_struct_as_scalar_round_trip_preserves_private():
    """Test full round trip preserves private data."""
    mod = comp.Module(module_id="test_mod")
    
    # Scalar with private data
    v1 = comp.Value(99)
    v1.set_private(mod.module_id, comp.Value({"handle": "abc"}))
    
    # Round trip
    v2 = v1.as_struct().as_scalar()
    
    # Should be same object (identity preserved)
    assert v1 is v2
    
    # Private data should be intact
    assert v2.get_private(mod.module_id).data[comp.Value("handle")].data == "abc"


def test_value_copy_shares_private_data():
    """Test that Value copy constructor shares (not copies) private data."""
    mod = comp.Module(module_id="test")
    
    v1 = comp.Value(10)
    v1.set_private(mod.module_id, comp.Value({"data": "shared"}))
    
    # Copy via constructor
    v2 = comp.Value(v1)
    
    # Should share the same private dict reference (immutability!)
    assert v1.private is v2.private
    
    # Both see the same data
    assert v1.get_private(mod.module_id).data[comp.Value("data")].data == "shared"
    assert v2.get_private(mod.module_id).data[comp.Value("data")].data == "shared"
