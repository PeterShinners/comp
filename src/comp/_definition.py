"""Module definition objects for the compilation pipeline.

A Definition represents a module-level assignment before it's been fully compiled.
It tracks the original COP node, resolved references, and eventual folded value.
"""

import comp

__all__ = ["Definition"]


class Definition:
    """A module-level definition that can be referenced.

    Definitions are created during the extraction phase and progressively
    enhanced through the compilation pipeline:
    1. Extract: Create with original_cop and shape
    2. Resolve: Populate resolved_cop with identifier references resolved
    3. Fold: Populate value with constant-folded Shape/Block/etc

    Args:
        qualified: Fully qualified name (e.g., "cart", "add.i001")
        module_id: Module token string (not reference)
        original_cop: The original COP node
        shape: Shape constant (comp.shape_block, comp.shape_shape, etc.)
    Attributes:
        qualified: (str) Fully qualified name (e.g., "cart", "add.i001")
        module_id: (str) Module token that owns this definition (avoids circular refs)
        original_cop: (Value) The original COP node from parsing
        resolved_cop: (Value | None) The resolved+folded+optimized COP node
        shape: (Shape) Shape constant indicating definition type
        value: (Value | None) The constant-folded value (Shape/Block/etc) if applicable

    """
    __slots__ = ("qualified", "module_id", "original_cop", "resolved_cop", "shape", "value")

    def __init__(self, qualified, module_id, original_cop, shape):
        self.qualified = qualified
        self.module_id = module_id
        self.original_cop = original_cop
        self.shape = shape
        self.resolved_cop = None  # Filled during identifier resolution
        self.value = None  # Filled during constant folding

    def __repr__(self):
        shape_name = self.shape.qualified #if hasattr(self.shape, "qualified") else str(self.shape)
        return f"Definition<{self.qualified}:{shape_name}>"

    def is_resolved(self):
        """(bool) Whether identifiers have been resolved."""
        return self.resolved_cop is not None

    def is_folded(self):
        """(bool) Whether constant folding has been performed."""
        return self.value is not None
