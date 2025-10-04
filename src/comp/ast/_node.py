"""
AST node definitions for Comp language

This module defines a simplified Abstract Syntax Tree for the Comp language.

"""

__all__ = [
    "Node",
    "Root",
    "Placeholder",
]


class Node:
    """Base class for all AST nodes."""

    def __init__(self, kids: list["Node"] | None = None):
        """Initialize node with arbitrary attributes.

        The 'kids' attribute should be a list of child Node objects.
        Other attributes are node-specific (value, op, path, etc.).

        Args:
            kids: List of child nodes
            _lark_tree: Internal - Lark tree to extract position info from
        """
        self.kids = list(kids) if kids else []
        self.position = (None, None)

    def __repr__(self):
        """Compact representation showing type and key attributes."""
        attrs = []
        if self.kids:
            attrs.append(f'*{len(self.kids)}')
        for key, value in self.__dict__.items():
            if key not in ('kids', 'position'):
                attrs.append(f'{key}={value!r}')
        return f"{self.__class__.__name__}({' '.join(attrs)})"

    def tree(self, indent=0):
        """Print tree structure."""
        print(f"{'  '*indent}{self!r}")
        for kid in self.kids:
            kid.tree(indent + 1)

    def find(self, node_type):
        """Find first descendant of given type, including self."""
        if isinstance(self, node_type):
            return self
        for kid in self.kids:
            if result := kid.find(node_type):
                return result
        return None

    def find_all(self, node_type):
        """Find all descendants of given type, including self."""
        results = [self] if isinstance(self, node_type) else []
        for kid in self.kids:
            results.extend(kid.find_all(node_type))
        return results

    def matches(self, other) -> bool:
        """Hierarchical comparison of AST structure.

        Compares node types, attributes (excluding position), and recursively
        compares all children. Useful for testing round-trip parsing.

        Args:
            other: Another Node to compare against

        Returns:
            True if nodes have same type, attributes, and children structure
        """
        # Must be same type
        if not isinstance(other, type(self)):
            return False

        # Must have same number of children
        if len(self.kids) != len(other.kids):
            return False

        # Compare all attributes except kids and position
        for key in self.__dict__:
            if key in ('kids', 'position'):
                continue
            if key not in other.__dict__:
                return False
            if self.__dict__[key] != other.__dict__[key]:
                return False

        # Check other doesn't have extra attributes
        for key in other.__dict__:
            if key in ('kids', 'position'):
                continue
            if key not in self.__dict__:
                return False

        # Recursively compare all children
        for self_kid, other_kid in zip(self.kids, other.kids, strict=True):
            if not self_kid.matches(other_kid):
                return False

        return True

    def unparse(self) -> str:
        """Convert back to Comp source representation."""
        return "???"

    @classmethod
    def from_grammar(cls, lark_tree):
        """Create node from Lark parse tree.

        Default implementation for nodes that just need to collect children.
        Override for nodes with specific parsing logic.
        """
        return cls()


class Root(Node):
    """Root of grammar Ast for expressions."""
    def unparse(self) -> str:
        return " ".join(kid.unparse() for kid in self.kids)


class Placeholder(Node):
    """Placeholder: ??? for unknown values"""

    def __init__(self):
        super().__init__()

    def unparse(self) -> str:
        return "???"

