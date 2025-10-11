"""Base entity type for runtime objects.

Entity is the base class for all runtime objects that can be:
- Passed through scopes
- Returned from evaluate() methods
- Stored in frames

This includes:
- Value: Runtime values (numbers, strings, structures, tags)
- Module: Container for definitions (tags, functions, shapes)
- Future: Shape, Function, etc.

Entity provides a common type that allows the engine to work uniformly
with all runtime objects, while keeping the distinction that not all
entities are valid "values" in the language.
"""

__all__ = ["Entity"]


class Entity:
    """Base class for all runtime objects in the engine.

    Subclasses:
    - Value: Actual runtime values (numbers, strings, structures, tags)
    - Module: Container for module-level definitions
    - Future: Shape, Function, and other compile-time/definition entities

    This is a marker base class - it doesn't provide much functionality,
    but establishes a common type hierarchy for runtime objects.
    """
    pass
