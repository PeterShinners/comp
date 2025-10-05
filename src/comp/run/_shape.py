"""Shape type system for runtime type checking and dispatch."""

__all__ = ["ShapeType", "ShapeDefRef", "ShapeModRef", "ShapeTagRef", "ShapeInline", "ShapeUnion"]

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from . import _module, _value


class ShapeType(ABC):
    """Base class for all shape representations."""

    @abstractmethod
    def resolve(self, module: '_module.Module'):
        """Resolve forward references within module context."""
        pass

    @abstractmethod
    def matches(self, value: '_value.Value') -> tuple[int, int]:
        """Check if value matches this shape.

        Returns (specificity, quality) tuple. (0, 0) = no match.
        TODO: Implement full scoring from design/shape.md
        """
        pass

    @abstractmethod
    def __repr__(self) -> str:
        pass


class ShapeDefRef(ShapeType):
    """Reference to a ShapeDef in current module."""

    def __init__(self, name: str):
        self.name = name
        self._resolved: '_module.ShapeDef | None' = None

    def resolve(self, module: '_module.Module'):
        if not self._resolved and self.name in module.shapes:
            self._resolved = module.shapes[self.name]

    def matches(self, value: '_value.Value') -> tuple[int, int]:
        if not self._resolved:
            return (0, 0)
        return (1, 1)  # Placeholder

    def __repr__(self) -> str:
        status = f" -> {self._resolved}" if self._resolved else " (unresolved)"
        return f"ShapeDefRef(~{self.name}{status})"


class ShapeModRef(ShapeType):
    """Reference to shape in another module."""

    def __init__(self, namespace: str, name: str):
        self.namespace = namespace
        self.name = name
        self._resolved: '_module.ShapeDef | None' = None

    def resolve(self, module: '_module.Module'):
        if not self._resolved and self.namespace in module.mods:
            other_mod = module.mods[self.namespace]
            if self.name in other_mod.shapes:
                self._resolved = other_mod.shapes[self.name]

    def matches(self, value: '_value.Value') -> tuple[int, int]:
        if not self._resolved:
            return (0, 0)
        return (1, 1)  # Placeholder

    def __repr__(self) -> str:
        status = f" -> {self._resolved}" if self._resolved else " (unresolved)"
        return f"ShapeModRef(~{self.name}/{self.namespace}{status})"


class ShapeTagRef(ShapeType):
    """Reference to a tag used as a shape constraint."""

    def __init__(self, name: str):
        self.name = name
        self._resolved: _module.TagDef | None = None

    def resolve(self, module: '_module.Module'):
        if not self._resolved and self.name in module.tags:
            self._resolved = module.tags[self.name]

    def matches(self, value: '_value.Value') -> tuple[int, int]:
        """Check if value is or contains this tag."""
        if not self._resolved:
            return (0, 0)

        # Tag values match exactly
        if value.is_tag:
            # TODO: Check if value.data matches this tag
            return (2, 1)  # Higher specificity for exact tag match

        # Structures can contain tags
        if value.is_struct:
            # TODO: Check if structure has this tag in its fields
            return (1, 1)  # Lower specificity for structural match

        return (0, 0)  # No match

    def __repr__(self) -> str:
        status = f" -> {self._resolved}" if self._resolved else " (unresolved)"
        return f"ShapeTagRef(#{self.name}{status})"


class ShapeInline(ShapeType):
    """Inline shape definition."""

    def __init__(self, fields: dict[str, Any] | None = None):
        self.fields = fields or {}
        self._resolved = False

    def resolve(self, module: '_module.Module'):
        if self._resolved:
            return

        for _field_name, field_type in self.fields.items():
            if isinstance(field_type, ShapeType):
                field_type.resolve(module)

        self._resolved = True

    def matches(self, value: '_value.Value') -> tuple[int, int]:
        if not value.is_struct:
            return (0, 0)
        return (1, 1)  # Placeholder

    def __repr__(self) -> str:
        field_count = len(self.fields)
        status = " (resolved)" if self._resolved else ""
        return f"ShapeInline(~{{{field_count} fields}}{status})"


class ShapeUnion(ShapeType):
    """Union of multiple shape types."""

    def __init__(self, variants: list[ShapeType]):
        self.variants = variants
        self._resolved = False

    def resolve(self, module: '_module.Module'):
        if self._resolved:
            return

        for variant in self.variants:
            variant.resolve(module)

        self._resolved = True

    def matches(self, value: '_value.Value') -> tuple[int, int]:
        if not self.variants:
            return (0, 0)

        best_score = (0, 0)
        for variant in self.variants:
            score = variant.matches(value)
            if score > best_score:
                best_score = score

        return best_score

    def __repr__(self) -> str:
        variant_reprs = " | ".join(repr(v) for v in self.variants)
        status = " (resolved)" if self._resolved else ""
        return f"ShapeUnion({variant_reprs}{status})"
