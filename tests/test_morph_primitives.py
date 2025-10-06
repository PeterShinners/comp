"""Tests for morphing primitive types (~num, ~str)."""

import pytest
import comp
from comp.run import ShapeDefRef, morph, Value


class TestNumMorph:
    """Test morphing with ~num shape."""

    def test_num_accepts_number(self):
        """~num should accept a number value."""
        num_val = Value(42)
        shape = ShapeDefRef("num")

        result = morph(num_val, shape)

        assert result.success
        assert result.value.num == 42
        assert result.named_matches == 1

    def test_num_accepts_wrapped_number(self):
        """~num should unwrap a single-item struct containing a number."""
        # Create a struct with one unnamed field containing a number
        from comp.run._struct import Unnamed
        struct_val = Value({})
        struct_val.struct = {Unnamed(): Value(99)}

        shape = ShapeDefRef("num")
        result = morph(struct_val, shape)

        assert result.success
        assert result.value.num == 99

    def test_num_rejects_string(self):
        """~num should reject a string value."""
        str_val = Value("hello")
        shape = ShapeDefRef("num")

        result = morph(str_val, shape)

        assert not result.success
        assert result.value is None

    def test_num_rejects_multi_field_struct(self):
        """~num should reject a struct with multiple fields."""
        struct_val = Value({"x": 1, "y": 2})
        shape = ShapeDefRef("num")

        result = morph(struct_val, shape)

        assert not result.success

    def test_num_rejects_named_field_struct(self):
        """~num should reject a struct with a named field (even if single)."""
        struct_val = Value({"value": 42})
        shape = ShapeDefRef("num")

        result = morph(struct_val, shape)

        assert not result.success


class TestStrMorph:
    """Test morphing with ~str shape."""

    def test_str_accepts_string(self):
        """~str should accept a string value."""
        str_val = Value("hello")
        shape = ShapeDefRef("str")

        result = morph(str_val, shape)

        assert result.success
        assert result.value.str == "hello"
        assert result.named_matches == 1

    def test_str_accepts_wrapped_string(self):
        """~str should unwrap a single-item struct containing a string."""
        from comp.run._struct import Unnamed
        struct_val = Value({})
        struct_val.struct = {Unnamed(): Value("world")}

        shape = ShapeDefRef("str")
        result = morph(struct_val, shape)

        assert result.success
        assert result.value.str == "world"

    def test_str_rejects_number(self):
        """~str should reject a number value."""
        num_val = Value(42)
        shape = ShapeDefRef("str")

        result = morph(num_val, shape)

        assert not result.success
        assert result.value is None

    def test_str_rejects_multi_field_struct(self):
        """~str should reject a struct with multiple fields."""
        struct_val = Value({"x": "a", "y": "b"})
        shape = ShapeDefRef("str")

        result = morph(struct_val, shape)

        assert not result.success


class TestPrimitiveInStructs:
    """Test primitive type constraints within struct shapes."""

    def test_struct_with_num_fields(self):
        """Test morphing a struct where fields have ~num constraints."""
        code = """
        !shape ~point = {
            x ~num
            y ~num
        }
        """

        module_ast = comp.parse_module(code)
        runtime_mod = comp.run.Module("test")
        runtime_mod.process_ast(module_ast)
        runtime_mod.resolve_all()

        # Get the shape
        shape_def = runtime_mod.shapes["point"]
        shape_ref = ShapeDefRef("point")
        shape_ref._resolved = shape_def

        # Create a value to morph
        value = Value({"x": 10, "y": 20})

        # Morph it
        result = morph(value, shape_ref)

        # Should succeed
        assert result.success
        assert result.named_matches == 2

        # Check values
        x_key = next((k for k in result.value.struct.keys() if hasattr(k, 'str') and k.str == "x"), None)
        y_key = next((k for k in result.value.struct.keys() if hasattr(k, 'str') and k.str == "y"), None)
        assert x_key is not None
        assert y_key is not None

        # Values should be numbers
        x_value = result.value.struct[x_key]
        y_value = result.value.struct[y_key]

        # Handle potential wrapping
        if x_value.num is not None:
            assert x_value.num == 10
        elif x_value.struct is not None:
            # Wrapped - extract inner value
            inner = list(x_value.struct.values())[0]
            assert inner.num == 10
        else:
            assert False, f"x value is neither num nor struct: {x_value}"

        if y_value.num is not None:
            assert y_value.num == 20
        elif y_value.struct is not None:
            inner = list(y_value.struct.values())[0]
            assert inner.num == 20
        else:
            assert False, f"y value is neither num nor struct: {y_value}"

    def test_struct_with_str_field(self):
        """Test morphing a struct with ~str field constraint."""
        code = """
        !shape ~person = {
            name ~str
        }
        """

        module_ast = comp.parse_module(code)
        runtime_mod = comp.run.Module("test")
        runtime_mod.process_ast(module_ast)
        runtime_mod.resolve_all()

        shape_def = runtime_mod.shapes["person"]
        shape_ref = ShapeDefRef("person")
        shape_ref._resolved = shape_def

        value = Value({"name": "Alice"})
        result = morph(value, shape_ref)

        assert result.success
        assert result.named_matches == 1

        name_key = next((k for k in result.value.struct.keys() if hasattr(k, 'str') and k.str == "name"), None)
        assert name_key is not None

        name_value = result.value.struct[name_key]
        # Handle potential wrapping
        if name_value.str is not None:
            assert name_value.str == "Alice"
        elif name_value.struct is not None:
            inner = list(name_value.struct.values())[0]
            assert inner.str == "Alice"
        else:
            assert False, f"name value is neither str nor struct: {name_value}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
