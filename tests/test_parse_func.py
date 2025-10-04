"""Tests for parsing function definitions (Phase 13)."""

from comp import parse_module
from comp._ast import FunctionDefinition, ShapeRef, Structure


class TestFunctionDefinition:
    """Test parsing of function definitions."""

    def test_simple_function_no_args(self):
        """Test function with input shape but no arguments."""
        source = "!func |double ~num = {@  * 2}"
        mod = parse_module(source)

        assert len(mod.kids) == 1
        func = mod.kids[0]
        assert isinstance(func, FunctionDefinition)
        assert func.tokens == ["double"]
        assert func.name == "double"
        assert isinstance(func.shape, ShapeRef)
        assert func.args is None  # No args when not specified
        assert isinstance(func.body, Structure)

    def test_function_with_args(self):
        """Test function with both input shape and arguments."""
        source = "!func |add ~num ^{b ~num} = {@ + b}"
        mod = parse_module(source)

        assert len(mod.kids) == 1
        func = mod.kids[0]
        assert isinstance(func, FunctionDefinition)
        assert func.tokens == ["add"]
        assert func.name == "add"
        assert isinstance(func.shape, ShapeRef)
        assert isinstance(func.args, Structure)
        assert len(func.args.kids) > 0  # Has args
        assert isinstance(func.body, Structure)

    def test_function_no_input(self):
        """Test function with no input (uses ~nil)."""
        source = "!func |greet ~nil ^{name ~str} = {name}"
        mod = parse_module(source)

        assert len(mod.kids) == 1
        func = mod.kids[0]
        assert isinstance(func, FunctionDefinition)
        assert func.tokens == ["greet"]
        assert func.name == "greet"
        assert isinstance(func.shape, ShapeRef)
        assert isinstance(func.args, Structure)
        assert len(func.args.kids) > 0  # Has args
        assert isinstance(func.body, Structure)

    def test_function_dotted_path(self):
        """Test function with dotted name path."""
        source = "!func |math.add ~num ^{b ~num} = {@ + b}"
        mod = parse_module(source)

        assert len(mod.kids) == 1
        func = mod.kids[0]
        assert isinstance(func, FunctionDefinition)
        assert func.tokens == ["math", "add"]
        assert func.name == "math.add"
        assert isinstance(func.shape, ShapeRef)
        assert isinstance(func.args, Structure)
        assert len(func.args.kids) > 0  # Has args

    def test_function_unparse_no_args(self):
        """Test unparsing function without arguments."""
        source = "!func |double ~num = {@ * 2}"
        mod = parse_module(source)
        func = mod.kids[0]

        unparsed = func.unparse()
        assert "!func |double" in unparsed
        assert "~num" in unparsed
        assert "{" in unparsed  # Structure syntax

    def test_function_unparse_with_args(self):
        """Test unparsing function with arguments."""
        source = "!func |add ~num ^{b ~num} = {@ + b}"
        mod = parse_module(source)
        func = mod.kids[0]

        unparsed = func.unparse()
        assert "!func |add" in unparsed
        assert "~num" in unparsed
        assert "^{" in unparsed  # Arg shape
        assert "{" in unparsed  # Structure syntax

    def test_function_with_shape_reference_args(self):
        """Test function with args as a shape reference (^shape-ref syntax)."""
        source = "!func |stab ~stab-shape ^stab-args = {???}"
        mod = parse_module(source)

        assert len(mod.kids) == 1
        func = mod.kids[0]
        assert isinstance(func, FunctionDefinition)
        assert func.tokens == ["stab"]
        assert func.name == "stab"
        assert isinstance(func.shape, ShapeRef)
        # Args should be a ShapeRef now, not a Structure
        assert isinstance(func.args, ShapeRef)
        assert func.args.tokens == ["stab-args"]
        assert isinstance(func.body, Structure)

        # Test unparse
        unparsed = func.unparse()
        assert "!func |stab" in unparsed
        assert "~stab-shape" in unparsed
        assert "^~stab-args" in unparsed  # Should unparse with ~ prefix
        assert "???" in unparsed
