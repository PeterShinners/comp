"""Asst base nodes and types"""

__all__ = [
    "Node",
    "Root",
    "Module",
    "Placeholder",
    "Number",
    "String",
]

import decimal
import ast as python_ast
import comp


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


class Module(Node):
    """Root of grammar Ast for modules."""

    @property
    def statements(self) -> list['Node']:
        """Access module statements (alias for kids)."""
        return self.kids

    def unparse(self) -> str:
        return "\n".join(kid.unparse() for kid in self.kids)


class Number(Node):
    """Numeric literal."""

    def __init__(self, value: decimal.Decimal = decimal.Decimal(0)):
        self.value = value
        super().__init__()

    def unparse(self) -> str:
        return str(self.value)

    @classmethod
    def from_grammar(cls, tree):
        """Parse number from Lark tree: number -> INTBASE | DECIMAL"""
        token = tree.children[0]
        try:
            if token.type == "INTBASE":
                python_int = int(token.value, 0)  # Auto-detect base
                value = decimal.Decimal(python_int)
            else:  # DECIMAL
                value = decimal.Decimal(token.value)
            return cls(value=value)
        except (ValueError, decimal.InvalidOperation) as e:
            raise comp.ParseError(f"Invalid number: {token.value}") from e


class String(Node):
    """String literal."""

    def __init__(self, value: str = ""):
        self.value = value
        super().__init__()

    def unparse(self) -> str:
        # Use repr() for proper escaping, but force double quotes
        # repr() may choose single quotes if the string contains double quotes,
        # so we need to handle that case
        r = repr(self.value)
        if r.startswith("'"):
            # repr chose single quotes, convert to double quotes
            # Remove outer single quotes and escape inner double quotes
            # Must also unescape single quotes since \' is not valid in double-quoted strings
            inner = r[1:-1].replace('"', '\\"').replace("\\'", "'")
            return f'"{inner}"'
        else:
            # Already using double quotes
            return r

    @classmethod
    def from_grammar(cls, tree):
        # [QUOTE, content, QUOTE] or [QUOTE, QUOTE] for empty string
        kids = tree.children
        if len(kids) == 3:
            # Use Python's ast.literal_eval to decode escape sequences
            # Wrap the content in quotes to make it a valid Python string literal
            raw_value = kids[1].value
            python_string = f'"{raw_value}"'
            try:
                decoded = python_ast.literal_eval(python_string)
            except (ValueError, SyntaxError) as e:
                # Check if this is a unicode escape error
                error_msg = str(e)
                if "unicode" in error_msg.lower() or "escape" in error_msg.lower():
                    raise comp.ParseError(f"Invalid unicode escape sequence in string: {error_msg}") from e
                # For other errors, keep the raw value
                decoded = raw_value
            return cls(value=decoded)
        else:
            return cls(value="")


class BaseRef(Node):
    """Base class for references: TagRef, ShapeRef, FuncRef."""

    SYMBOL = "?"
    def __init__(self, tokens:list[str]|None=None, namespace:str|None=None):
        self.tokens = tokens
        self.namespace = namespace
        super().__init__()

    def unparse(self) -> str:
        path = ".".join(self.tokens)
        full = "/".join((path, self.namespace)) if self.namespace else path
        return f"{self.SYMBOL}{full}"

    @classmethod
    def from_grammar(cls, tree):
        """Parse from Lark tree: tag_reference -> "#" _reference_path"""
        tokens = []
        namespace = None
        for token in tree.children[1].children:
            value = token.value
            if value != ".":
                tokens.append(value)
        if len(tree.children) > 2:
            namespace = tree.children[2].children[1].value
        return cls(tokens=tuple(tokens), namespace=namespace)

