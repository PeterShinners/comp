"""Scope handling for runtime execution."""

__all__ = ["ChainedScope"]

from typing import TYPE_CHECKING

from . import _struct, _value

if TYPE_CHECKING:
    pass


class ChainedScope:
    """A read-only scope that chains through multiple underlying scopes.

    Used for ^ scope which looks up: $arg -> $ctx -> $mod
    Acts like a Value with struct fields for evaluation purposes.
    """

    def __init__(self, *scopes: _value.Value):
        """Create a chained scope from multiple Value scopes.

        Args:
            *scopes: Values to chain in lookup order (first has priority)
        """
        self.scopes = scopes

    @property
    def is_num(self) -> bool:
        return False

    @property
    def is_str(self) -> bool:
        return False

    @property
    def is_tag(self) -> bool:
        return False

    @property
    def is_struct(self) -> bool:
        return True

    @property
    def struct(self) -> dict[_value.Value | _struct.Unnamed, _value.Value] | None:
        """Virtual struct that merges all scopes.

        Returns fields from first scope that has them.
        """
        # Create a merged view (later scopes first, so earlier scopes override)
        merged: dict[_value.Value | _struct.Unnamed, _value.Value] = {}

        for scope in reversed(self.scopes):
            if scope.is_struct and scope.struct:
                merged.update(scope.struct)

        return merged if merged else None

    def lookup_field(self, field_key: _value.Value) -> _value.Value | None:
        """Look up a field by walking through scopes.

        Args:
            field_key: The field key to look up

        Returns:
            Value from first scope that has the field, or None
        """
        for scope in self.scopes:
            if scope.is_struct and scope.struct:
                if field_key in scope.struct:
                    return scope.struct[field_key]
        return None

    def __repr__(self) -> str:
        return f"ChainedScope({len(self.scopes)} scopes)"
