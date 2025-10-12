"""Test mask operator parsing and AST structure.

Tests for ^ (mask) and ^* (strong mask) operators.
"""

import comp
import asttest


@asttest.params(
    "expression",
    simple_mask=("data ^point",),
    strong_mask=("data ^* point",),
    inline_shape=("data ^{x ~num y ~num}",),
    strong_inline=("data ^* {x ~num y ~num}",),
    dotted_shape=("data ^geo.point",),
    strong_dotted=("data ^* geo.point",),
)
def test_mask_operators_parse(key, expression):
    """Test that mask operators parse correctly."""
    result = comp.parse_expr(expression)
    # Extract from Root wrapper
    result = result.kids[0] if result.kids else result
    assert isinstance(result, comp.ast.MaskOp)
    asttest.roundtrip(result)


def test_mask_operator_mode():
    """Test that mask operator mode is set correctly."""
    # Permissive mask ^
    result = comp.parse_expr("data ^point")
    result = result.kids[0] if result.kids else result
    assert isinstance(result, comp.ast.MaskOp)
    assert result.mode == "mask"

    # Strong mask ^*
    result = comp.parse_expr("data ^* point")
    result = result.kids[0] if result.kids else result
    assert isinstance(result, comp.ast.MaskOp)
    assert result.mode == "strong_mask"


def test_mask_operator_children():
    """Test that mask operator has correct children."""
    result = comp.parse_expr("value ^shape")
    result = result.kids[0] if result.kids else result

    assert isinstance(result, comp.ast.MaskOp)
    assert len(result.kids) == 2

    # First child is the expression
    assert result.expr is not None
    assert isinstance(result.expr, comp.ast.Ident)
    assert result.expr.name == "value"

    # Second child is the shape
    assert result.shape is not None
    assert isinstance(result.shape, comp.ast.ShapeRef)


@asttest.params(
    "expression",
    struct_mask=("{x=1 y=2 z=3} ^point",),
    struct_strong=("{x=1 y=2} ^* point",),
    nested_mask=("user.data ^profile",),
    call_result_mask=("get_data() ^validated",),
)
def test_mask_with_complex_expressions(key, expression):
    """Test mask operators with various expression types."""
    result = comp.parse_expr(expression)
    result = result.kids[0] if result.kids else result
    assert isinstance(result, comp.ast.MaskOp)
    asttest.roundtrip(result)


@asttest.params(
    "expression",
    union=("data ^success | ^error",),
    union_strong=("data ^* success | ^error",),
    multi_union=("value ^num | ^str | ^bool",),
)
def test_mask_with_union_shapes(key, expression):
    """Test mask operators with union shapes."""
    result = comp.parse_expr(expression)
    result = result.kids[0] if result.kids else result
    assert isinstance(result, comp.ast.MaskOp)

    # Shape should be a union
    assert isinstance(result.shape, comp.ast.ShapeUnion)
    asttest.roundtrip(result)


def test_mask_inline_shape_structure():
    """Test mask with inline shape has correct structure."""
    result = comp.parse_expr("data ^{x ~num y ~num}")
    result = result.kids[0] if result.kids else result

    assert isinstance(result, comp.ast.MaskOp)
    assert result.mode == "mask"

    # Shape should be inline
    assert isinstance(result.shape, comp.ast.ShapeInline)

    # Inline shape should have fields
    fields = [k for k in result.shape.kids if isinstance(k, comp.ast.ShapeField)]
    assert len(fields) == 2


@asttest.params(
    "expression",
    chained_mask=("data ^point ^validated",),
    mask_then_morph=("data ^point ~validated",),
    morph_then_mask=("data ~point ^validated",),
)
def test_chained_shape_operations(key, expression):
    """Test chaining mask with other shape operations."""
    result = comp.parse_expr(expression)
    result = result.kids[0] if result.kids else result

    # Should have nested shape operations
    assert isinstance(result, (comp.ast.MaskOp, comp.ast.MorphOp))
    asttest.roundtrip(result)


@asttest.params(
    "expression",
    mask_in_pipe=("data | ^point",),
    strong_in_pipe=("data | ^* point",),
    pipe_mask_pipe=("source | ^filter | process",),
)
def test_mask_in_pipeline(key, expression):
    """Test mask operators within pipeline expressions."""
    result = comp.parse_expr(expression)
    asttest.roundtrip(result)


def test_mask_unparse_simple():
    """Test unparsing simple mask operations."""
    # Permissive mask
    result = comp.parse_expr("data ^point")
    result = result.kids[0] if result.kids else result
    assert result.unparse() == "data ^point"

    # Strong mask
    result = comp.parse_expr("data ^* point")
    result = result.kids[0] if result.kids else result
    assert result.unparse() == "data ^* point"


def test_mask_unparse_inline_shape():
    """Test unparsing mask with inline shape."""
    code = "data ^{x ~num y ~num}"
    result = comp.parse_expr(code)
    result = result.kids[0] if result.kids else result

    unparsed = result.unparse()
    # Should contain the mask operator and inline shape syntax
    assert "^" in unparsed
    assert "{" in unparsed and "}" in unparsed
    assert "x" in unparsed and "y" in unparsed


@asttest.params(
    "code",
    mask_in_assignment=("result = data ^point",),
    strong_in_assignment=("filtered = data ^* validated",),
    mask_in_function=("!fn process = {data | ^schema | validate}",),
)
def test_mask_in_statements(key, code):
    """Test mask operators in various statement contexts."""
    result = comp.parse_module(code)
    assert isinstance(result, comp.ast.Module)
    asttest.roundtrip(result)


def test_mask_vs_morph_distinction():
    """Test that mask (^) and morph (~) are distinct operators."""
    mask_result = comp.parse_expr("data ^shape")
    mask_result = mask_result.kids[0] if mask_result.kids else mask_result

    morph_result = comp.parse_expr("data ~shape")
    morph_result = morph_result.kids[0] if morph_result.kids else morph_result

    assert isinstance(mask_result, comp.ast.MaskOp)
    assert isinstance(morph_result, comp.ast.MorphOp)
    assert type(mask_result) != type(morph_result)


def test_strong_mask_vs_strong_morph_distinction():
    """Test that strong mask (^*) and strong morph (~*) are distinct."""
    strong_mask = comp.parse_expr("data ^* shape")
    strong_mask = strong_mask.kids[0] if strong_mask.kids else strong_mask

    strong_morph = comp.parse_expr("data ~* shape")
    strong_morph = strong_morph.kids[0] if strong_morph.kids else strong_morph

    assert isinstance(strong_mask, comp.ast.MaskOp)
    assert strong_mask.mode == "strong_mask"

    assert isinstance(strong_morph, comp.ast.MorphOp)
    assert strong_morph.mode == "strong"

    assert type(strong_mask) != type(strong_morph)


@asttest.params(
    "expression",
    just_caret=("data ^",),
    double_caret=("data ^^shape",),
    caret_space_star=("data ^ * shape",),
    star_caret=("data *^ shape",),
)
def test_invalid_mask_syntax(key, expression):
    """Test that invalid mask syntax fails to parse."""
    asttest.invalid_parse(expression, match=r"parse error|unexpected")
