"""Base entity type for runtime objects."""

__all__ = ["Entity"]


class Entity:
    """Base class for all runtime objects in the engine.

    Subclasses:
    - Value: Actual runtime values (numbers, strings, structures, tags)
    - Module: Container for module-level definitions
    - ShapeDefinition: Shape definitions with fields
    - FunctionDefinition: Function definitions with bodies
    - ShapeField: Individual field definitions

    This is a marker base class - it doesn't provide much functionality,
    but establishes a common type hierarchy for runtime objects.
    """
    pass
