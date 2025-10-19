"""AST nodes for morph operations - shape-based transformations."""

__all__ = ["MorphOp"]

import comp

from . import _base


class MorphOp(_base.ValueNode):
    """Shape morph operation: expr ~ shape, expr ~* shape, expr ~? shape

    Transforms a value to match a shape specification using the morphing algorithm.

    The morph modes control strictness and behavior:
    - normal (~): Apply defaults, allow extra fields, validate types
    - strong (~*): No extra fields allowed, strict matching with validation
    - weak (~?): Filter to field intersection, no defaults, no validation

    Examples:
        data ~ ~point              # Normal morph
        {x=1 y=2 z=3} ~* ~point    # Strong morph (fails if point doesn't have z)
        partial ~? ~user           # Weak morph (filter to matching fields)

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
        if frame.bypass_value(value):
            return value

        # Step 2: Resolve the shape
        # NOTE: Shape resolution returns ShapeDefinition objects, not Values
        # This breaks the evaluate() contract but matches current engine architecture
        shape_def = yield comp.Compute(self.shape)
        if frame.bypass_value(shape_def):
            return shape_def

        # Step 3: Perform morphing based on mode
        if self.mode == "strong":
            result = comp.strong_morph(value, shape_def)
        elif self.mode == "weak":
            result = comp.weak_morph(value, shape_def)
        else:
            result = comp.morph(value, shape_def)

        # Step 4: Return result or fail
        if result.success:
            return result.value
        else:
            # Morphing failed - return a failure
            # TODO: Better error messages with details about what didn't match
            return comp.fail("Failed to morph value to shape")
        yield  # Unreachable, but makes this a proper generator

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
