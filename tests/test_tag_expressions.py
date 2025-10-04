"""Tests for tag definition with expression values."""

import pytest
from comp._parser import parse_module
from comp._ast import Module, TagDefinition, TagChild, BinaryOp, UnaryOp, Number, Placeholder


class TestTagExpressions:
    """Test tag definitions with expression values."""

    def test_tag_arithmetic_addition(self):
        """Test tag with arithmetic addition."""
        code = "!tag #value = 9+9"
        result = parse_module(code)

        assert isinstance(result, Module)
        assert len(result.kids) == 1

        tag = result.kids[0]
        assert isinstance(tag, TagDefinition)
        assert tag.tokens == ["value"]
        assert tag.assign_op == "="

        # First body kid should be a BinaryOp
        assert len(tag.body_kids) == 1
        assert isinstance(tag.body_kids[0], BinaryOp)
        assert tag.body_kids[0].op == "+"

        # Round-trip
        assert result.unparse() == "!tag #value = 9 + 9"

    def test_tag_arithmetic_subtraction(self):
        """Test tag with arithmetic subtraction."""
        code = "!tag #delta = 100 - 42"
        result = parse_module(code)
        assert result.unparse() == "!tag #delta = 100 - 42"

    def test_tag_arithmetic_multiplication(self):
        """Test tag with arithmetic multiplication."""
        code = "!tag #product = 6 * 7"
        result = parse_module(code)
        assert result.unparse() == "!tag #product = 6 * 7"

    def test_tag_arithmetic_division(self):
        """Test tag with arithmetic division."""
        code = "!tag #ratio = 100 / 4"
        result = parse_module(code)
        assert result.unparse() == "!tag #ratio = 100 / 4"

    def test_tag_bitshift_left(self):
        """Test tag with left bit shift (useful for flags)."""
        code = "!tag #flag1 = 1 << 0"
        result = parse_module(code)

        tag = result.kids[0]
        assert isinstance(tag, TagDefinition)
        assert tag.tokens == ["flag1"]

        # First body kid should be a BinaryOp with << operator
        assert isinstance(tag.body_kids[0], BinaryOp)
        assert tag.body_kids[0].op == "<<"

        assert result.unparse() == "!tag #flag1 = 1 << 0"

    def test_tag_bitshift_right(self):
        """Test tag with right bit shift."""
        code = "!tag #shifted = 128 >> 3"
        result = parse_module(code)
        assert result.unparse() == "!tag #shifted = 128 >> 3"

    def test_tag_bitwise_and(self):
        """Test tag with bitwise AND."""
        code = "!tag #mask = 0xFF & 0x0F"
        result = parse_module(code)
        assert result.unparse() == "!tag #mask = 255 & 15"

    def test_tag_bitwise_or(self):
        """Test tag with bitwise OR."""
        code = "!tag #combined = 1 | 2"
        result = parse_module(code)
        assert result.unparse() == "!tag #combined = 1 | 2"

    def test_tag_bitwise_xor(self):
        """Test tag with bitwise XOR."""
        code = "!tag #toggled = 5 ^ 3"
        result = parse_module(code)
        assert result.unparse() == "!tag #toggled = 5 ^ 3"

    def test_tag_comparison_less_than(self):
        """Test tag with less than comparison."""
        code = "!tag #check = 5 < 10"
        result = parse_module(code)
        assert result.unparse() == "!tag #check = 5 < 10"

    def test_tag_comparison_greater_than(self):
        """Test tag with greater than comparison."""
        code = "!tag #check = 10 > 5"
        result = parse_module(code)
        assert result.unparse() == "!tag #check = 10 > 5"

    def test_tag_comparison_equal(self):
        """Test tag with equality comparison."""
        code = "!tag #check = 42 == 42"
        result = parse_module(code)
        assert result.unparse() == "!tag #check = 42 == 42"

    def test_tag_comparison_not_equal(self):
        """Test tag with not-equal comparison."""
        code = "!tag #check = 1 != 2"
        result = parse_module(code)
        assert result.unparse() == "!tag #check = 1 != 2"

    def test_tag_unary_plus(self):
        """Test tag with unary plus."""
        code = "!tag #positive = +42"
        result = parse_module(code)

        tag = result.kids[0]
        assert isinstance(tag.body_kids[0], UnaryOp)
        assert tag.body_kids[0].op == "+"

        assert result.unparse() == "!tag #positive = +42"

    def test_tag_unary_minus(self):
        """Test tag with unary minus."""
        code = "!tag #negative = -100"
        result = parse_module(code)

        tag = result.kids[0]
        assert isinstance(tag.body_kids[0], UnaryOp)
        assert tag.body_kids[0].op == "-"

        assert result.unparse() == "!tag #negative = -100"

    def test_tag_unary_not(self):
        """Test tag with unary not."""
        code = "!tag #inverted = !false"
        result = parse_module(code)
        assert result.unparse() == "!tag #inverted = !false"

    def test_tag_complex_expression(self):
        """Test tag with complex nested expression."""
        code = "!tag #complex = (1 + 2) * 3"
        result = parse_module(code)

        # Should parse and unparse
        unparsed = result.unparse()
        assert "1 + 2" in unparsed
        assert "* 3" in unparsed

    def test_tag_expression_with_children(self):
        """Test tag with expression value AND tag children."""
        code = "!tag #status = 1<<0 {#active #inactive}"
        result = parse_module(code)

        tag = result.kids[0]
        assert isinstance(tag, TagDefinition)
        assert tag.tokens == ["status"]

        # Should have 3 body kids: the value expression, and 2 child tags
        assert len(tag.body_kids) == 3
        assert isinstance(tag.body_kids[0], BinaryOp)  # 1<<0
        assert isinstance(tag.body_kids[1], TagChild)  # #active (TagChild, not TagDefinition)
        assert isinstance(tag.body_kids[2], TagChild)  # #inactive
        assert result.unparse() == "!tag #status = 1 << 0 {#active #inactive}"

    def test_tag_expression_with_generator_and_children(self):
        """Test tag with generator, expression value, and children."""
        code = "!tag #flags |gen/flag = 1<<0 {#read #write #execute}"
        result = parse_module(code)

        tag = result.kids[0]
        assert isinstance(tag, TagDefinition)
        assert not isinstance(tag.generator, Placeholder)

        # Should have value + 3 children in body_kids
        assert len(tag.body_kids) == 4
        assert isinstance(tag.body_kids[0], BinaryOp)  # 1<<0

        unparsed = result.unparse()
        assert "|gen/flag" in unparsed
        assert "1 << 0" in unparsed
        assert "#read" in unparsed

    def test_tag_multiple_bitflags(self):
        """Test realistic use case: multiple bit flag definitions."""
        code = """
!tag #permissions = {
    #read = 1<<0
    #write = 1<<1
    #execute = 1<<2
}
"""
        result = parse_module(code)

        tag = result.kids[0]
        assert isinstance(tag, TagDefinition)
        assert tag.tokens == ["permissions"]

        # Should have 3 child tag definitions in body_kids
        assert len(tag.body_kids) == 3

        # Each child should have a bit shift expression (TagChild nodes)
        for i, child in enumerate(tag.body_kids):
            assert isinstance(child, TagChild)
            assert isinstance(child.body_kids[0], BinaryOp)
            assert child.body_kids[0].op == "<<"
            assert isinstance(child.body_kids[0].left, Number)
            assert child.body_kids[0].left.value == 1
            assert isinstance(child.body_kids[0].right, Number)
            assert child.body_kids[0].right.value == i

    def test_tag_string_value_still_works(self):
        """Test that simple string values still work."""
        code = '!tag #name = "Alice"'
        result = parse_module(code)
        assert '!tag #name = "Alice"' in result.unparse()

    def test_tag_number_value_still_works(self):
        """Test that simple number values still work."""
        code = "!tag #count = 42"
        result = parse_module(code)
        assert result.unparse() == "!tag #count = 42"

    def test_tag_operator_precedence(self):
        """Test that operator precedence is respected in tag values."""
        code = "!tag #calc = 1 + 2 * 3"
        result = parse_module(code)

        # Should parse correctly with * having higher precedence
        # Unparse may add parentheses for clarity: 1 + (2 * 3)
        unparsed = result.unparse()
        assert "2 * 3" in unparsed or "2*3" in unparsed
        assert unparsed.startswith("!tag #calc = ")
