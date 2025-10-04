"""Tests for assignment operators in definitions."""

import comp


class TestAssignmentOperators:
    """Test assignment operators for tag, shape, and function definitions."""

    def test_tag_default_assign(self):
        """Test tag with default = operator."""
        source = "!tag #status = {#active #inactive}"
        mod = comp.parse_module(source)
        tag = mod.kids[0]
        assert isinstance(tag, comp.ast.TagDefinition)
        assert tag.assign_op == "="

    def test_shape_default_assign(self):
        """Test shape with default = operator."""
        source = "!shape ~point = {x ~num y ~num}"
        mod = comp.parse_module(source)
        shape = mod.kids[0]
        assert isinstance(shape, comp.ast.ShapeDefinition)
        assert shape.assign_op == "="

    def test_function_default_assign(self):
        """Test function with default = operator."""
        source = "!func |add ~num ^{b ~num} = {@ + b}"
        mod = comp.parse_module(source)
        func = mod.kids[0]
        assert isinstance(func, comp.ast.FunctionDefinition)
        assert func.assign_op == "="

    def test_function_strong_assign(self):
        """Test function with =* operator."""
        source = "!func |strict ~num =* {@ * 2}"
        mod = comp.parse_module(source)
        func = mod.kids[0]
        assert isinstance(func, comp.ast.FunctionDefinition)
        assert func.assign_op == "=*"

    def test_function_weak_assign(self):
        """Test function with =? operator."""
        source = "!func |maybe ~num =? {@ + 1}"
        mod = comp.parse_module(source)
        func = mod.kids[0]
        assert isinstance(func, comp.ast.FunctionDefinition)
        assert func.assign_op == "=?"

    def test_function_unparse_preserves_assign_op(self):
        """Test that unparsing preserves the assignment operator."""
        source = "!func |test ~num =* {@ * 2}"
        mod = comp.parse_module(source)
        func = mod.kids[0]
        unparsed = func.unparse()
        assert "=*" in unparsed
        assert func.assign_op == "=*"
