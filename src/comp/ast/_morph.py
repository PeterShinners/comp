"""AST nodes for morph and mask operations - shape-based transformations."""

__all__ = ["MorphOp", "MaskOp"]

from . import _base
import comp


class MorphOp(_base.ValueNode):
    """Shape morph operation: expr ~shape, expr ~* shape, expr ~? shape

    Transforms a value to match a shape specification using the morphing algorithm.

    The morph modes control strictness:
    - normal (~): Apply defaults, allow extra fields
    - strong (~*): No extra fields allowed, strict matching
    - weak (~?): Missing fields acceptable, partial matching

    Examples:
        data ~point              # Normal morph
        {x=1 y=2 z=3} ~* point   # Strong morph (fails if point doesn't have z)
        partial ~? user          # Weak morph (succeeds if some fields match)

    Args:
        expr: Expression to morph (ValueNode)
        shape: Target shape (ShapeNode)
        mode: "normal", "strong", or "weak"
    """

    def __init__(self, expr: _base.ValueNode, shape: _base.ShapeNode, mode: str = "normal"):
        if not isinstance(expr, _base.ValueNode):
            raise TypeError(f"MorphOp expr must be ValueNode, got {type(expr)}")
        if not isinstance(shape, _base.ShapeNode):
            raise TypeError(f"MorphOp shape must be ShapeNode, got {type(shape)}")
        if mode not in ("normal", "strong", "weak"):
            raise ValueError(f"MorphOp mode must be 'normal', 'strong', or 'weak', got {mode!r}")

        self.expr = expr
        self.shape = shape
        self.mode = mode

    def evaluate(self, frame):
        """Evaluate morph operation.

        1. Evaluate the expression to get a value
        2. Resolve the shape reference to get shape definition
        3. Call morph() from comp._morph with the value and shape
        4. Return morphed value or fail

        The morph function returns a MorphResult with:
        - score: Tuple of (named_matches, tag_depth, assignment_weight, positional_matches)
        - value: The morphed Value or None if morphing failed
        """
        # Step 1: Evaluate the expression
        value = yield comp.Compute(self.expr)
        if frame.is_fail(value):
            return value

        # Step 2: Resolve the shape
        # NOTE: Shape resolution returns ShapeDefinition objects, not Values
        # This breaks the evaluate() contract but matches current engine architecture
        shape_def = yield comp.Compute(self.shape)
        if frame.is_fail(shape_def):
            return shape_def

        # Step 3: Perform morphing
        # TODO: Implement strong and weak modes
        if self.mode != "normal":
            return comp.fail(f"Morph mode '{self.mode}' not yet implemented")

        # Get module context for tag value lookups
        # Try to get from any of the module scopes
        module = frame.scope('mod_tags') or frame.scope('mod_shapes') or frame.scope('mod_funcs')

        # Call morph function with module context
        result = comp.morph(value, shape_def, module)

        # Step 4: Return result or fail
        if result.success:
            return result.value
        else:
            # Morphing failed - return a failure
            # TODO: Better error messages with details about what didn't match
            return comp.fail("Failed to morph value to shape")

    def unparse(self) -> str:
        """Convert back to source code."""
        expr_str = self.expr.unparse()
        shape_str = self.shape.unparse()

        # Strip leading ~ from shape if present (since our operator includes it)
        if shape_str.startswith("~"):
            shape_str = shape_str[1:]

        if self.mode == "strong":
            return f"{expr_str} ~* {shape_str}"
        elif self.mode == "weak":
            return f"{expr_str} ~? {shape_str}"
        else:
            return f"{expr_str} ~{shape_str}"

    def __repr__(self):
        mode_str = f" mode={self.mode}" if self.mode != "normal" else ""
        return f"MorphOp({self.expr}, {self.shape}{mode_str})"


class MaskOp(_base.ValueNode):
    """Shape mask operation: expr ^ shape, expr ^* shape

    Filters a value to the intersection of its fields and the shape's fields.

    The mask modes control strictness:
    - normal (^): Return only fields in both value and shape (no defaults, no validation)
    - strict (^*): Exact match with defaults (equivalent to strong morph)

    Examples:
        data ^ {user ~str session ~str}    # Normal mask - filter to intersection
        args ^* config_shape               # Strict mask - validate and apply defaults

    Args:
        expr: Expression to mask (ValueNode)
        shape: Target shape (ShapeNode)
        mode: "normal" or "strict"
    """

    def __init__(self, expr: _base.ValueNode, shape: _base.ShapeNode, mode: str = "normal"):
        if not isinstance(expr, _base.ValueNode):
            raise TypeError(f"MaskOp expr must be ValueNode, got {type(expr)}")
        if not isinstance(shape, _base.ShapeNode):
            raise TypeError(f"MaskOp shape must be ShapeNode, got {type(shape)}")
        if mode not in ("normal", "strict"):
            raise ValueError(f"MaskOp mode must be 'normal' or 'strict', got {mode!r}")

        self.expr = expr
        self.shape = shape
        self.mode = mode

    def evaluate(self, frame):
        """Evaluate mask operation.

        1. Evaluate the expression to get a value
        2. Resolve the shape reference to get shape definition
        3. Call mask() or strict_mask() from comp._morph
        4. Return filtered value
        """
        # Step 1: Evaluate the expression
        value = yield comp.Compute(self.expr)
        if frame.is_fail(value):
            return value

        # Step 2: Resolve the shape
        shape_def = yield comp.Compute(self.shape)
        if frame.is_fail(shape_def):
            return shape_def

        # Step 3: Perform masking
        if self.mode == "strict":
            result = comp.strict_mask(value, shape_def)
        else:
            result = comp.mask(value, shape_def)

        # Step 4: Return result or fail
        if result.success:
            return result.value
        else:
            # Masking failed
            return comp.fail("Failed to mask value to shape")

    def unparse(self) -> str:
        """Convert back to source code."""
        expr_str = self.expr.unparse()
        shape_str = self.shape.unparse()

        # Strip leading ~ from shape if present
        if shape_str.startswith("~"):
            shape_str = shape_str[1:]

        if self.mode == "strict":
            return f"{expr_str} ^* {shape_str}"
        else:
            return f"{expr_str} ^{shape_str}"

    def __repr__(self):
        mode_str = f" mode={self.mode}" if self.mode != "normal" else ""
        return f"MaskOp({self.expr}, {self.shape}{mode_str})"
