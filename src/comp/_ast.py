"""
AST node definitions for Comp language - Clean Redesign

This module defines a simplified Abstract Syntax Tree for the Comp language.
Focuses on clean, consistent naming and minimal complexity.

Design principles:
- Clear, consistent naming (no abbreviations or legacy terminology)
- Minimal node types (combine similar concepts)
- Simple construction (no complex factory methods)
- Consistent structure across all nodes
"""

__all__ = [
    "ParseError",
    "ASTNode",
    "Field",
    "TokenField",
    "IndexField",
    "NameField",
    "ComputedField",
    "StringField",
    "Number",
    "String",
    "Identifier",
    "Scope",
    "Placeholder",
    "TagRef",
    "ShapeRef",
    "FunctionRef",
    "Structure",
    "Block",
    "Pipeline",
    "BinaryOp",
    "UnaryOp",
]

import decimal
import lark

from . import _parser


class ParseError(Exception):
    """Exception raised for parsing errors."""

    def __init__(self, message: str, position: int | None = None):
        self.message = message
        self.position = position
        super().__init__(f"Parse error: {message}")


class ASTNode:
    """Base class for all AST nodes.

    Simple design with minimal magic - just stores attributes and provides
    standard __repr__ and __eq__ implementations.
    """

    def __init__(self, **kwargs):
        self.start = None
        self.end = None
        for key, value in kwargs.items():
            setattr(self, key, value)

    def __repr__(self):
        attrs = []
        for key, value in self.__dict__.items():
            if not key.startswith("_") and key not in ("start", "end"):
                if isinstance(value, str):
                    attrs.append(f'{key}="{value}"')
                else:
                    attrs.append(f"{key}={value}")
        return f"{self.__class__.__name__}({', '.join(attrs)})"

    def __eq__(self, other):
        return isinstance(other, self.__class__) and self.__dict__ == other.__dict__

    def unparse(self) -> str:
        """Convert back to minimal Comp source representation."""
        # Default implementation - subclasses should override
        return "???"

    def children(self) -> list["ASTNode"]:
        """Get immediate child AST nodes (non-recursive).

        Returns a flat list of all direct child nodes, extracting nodes from
        both single-node attributes and list attributes.
        """
        result = []
        for attr_value in self.__dict__.values():
            if isinstance(attr_value, ASTNode):
                result.append(attr_value)
            elif isinstance(attr_value, list):
                for item in attr_value:
                    if isinstance(item, ASTNode):
                        result.append(item)
        return result

    def find(self, node_type) -> "ASTNode | None":
        """Find first child node of the specified type (depth-first search)."""
        # Check if this node matches
        if isinstance(self, node_type):
            return self

        # Search through immediate children recursively
        for child in self.children():
            result = child.find(node_type)
            if result is not None:
                return result

        return None

    def find_all(self, node_type) -> list["ASTNode"]:
        """Find all child nodes of the specified type (depth-first search)."""
        results = []

        # Check if this node matches
        if isinstance(self, node_type):
            results.append(self)

        # Search through immediate children recursively
        for child in self.children():
            results.extend(child.find_all(node_type))

        return results

    def print_tree(self, indent: int = 0, prefix: str = "", show_attrs: bool = True):
        """Print a visual tree representation of the AST.

        Args:
            indent: Current indentation level (for internal use)
            prefix: Line prefix for tree structure (for internal use)
            show_attrs: Whether to show node attributes
        """
        # Node type and key attributes
        node_name = self.__class__.__name__

        # Build attribute string
        attrs_str = ""
        if show_attrs:
            attrs = []
            for key, value in self.__dict__.items():
                if key.startswith("_") or key in ("start", "end"):
                    continue

                # Skip ASTNode attributes (they're shown as children)
                if isinstance(value, ASTNode):
                    continue

                # Handle lists
                if isinstance(value, list):
                    # Check if it's a list of AST nodes
                    if value and isinstance(value[0], ASTNode):
                        continue  # Will be shown as children
                    # Show simple list inline
                    if len(str(value)) > 30:
                        attrs.append(f'{key}=[{len(value)} items]')
                    else:
                        attrs.append(f'{key}={value}')
                # Show simple values inline
                elif isinstance(value, str):
                    if len(value) > 30:
                        attrs.append(f'{key}="{value[:27]}..."')
                    else:
                        attrs.append(f'{key}="{value}"')
                else:
                    attrs.append(f"{key}={value}")
            if attrs:
                attrs_str = f" ({', '.join(attrs)})"

        # Print this node
        print(f"{prefix}{node_name}{attrs_str}")

        # Get children
        children_nodes = []
        for key, value in self.__dict__.items():
            if isinstance(value, ASTNode):
                children_nodes.append((key, value))
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    if isinstance(item, ASTNode):
                        children_nodes.append((f"{key}[{i}]", item))

        # Print children with tree structure
        for i, (key, child) in enumerate(children_nodes):
            is_last = i == len(children_nodes) - 1

            # Tree structure characters (ASCII-safe for Windows)
            if is_last:
                child_prefix = prefix + "`-- "
                continuation = prefix + "    "
            else:
                child_prefix = prefix + "|-- "
                continuation = prefix + "|   "

            # Print attribute name
            print(f"{child_prefix}{key}:")

            # Recursively print child
            child.print_tree(indent + 1, continuation, show_attrs)

    def _position_from_token(self, token):
        """Extract position from a token if available."""
        self.start = Position(token.line, token.column)
        self.end = Position(token.end_line, token.end_column)
        return self

    def _position_from_tree(self, tree):
        """Extract position from a tree if available."""
        if isinstance(tree, list):
            children = tree
        else:
            children = tree.children
        if len(children):
            self.start = Position(children[0].line, children[0].column)
            self.end = Position(children[-1].end_line, children[-1].end_column)
        return self


# === LITERALS AND BASIC VALUES ===


class Number(ASTNode):
    """Numeric literal (integer, decimal, float)."""

    def __init__(self, value: decimal.Decimal | int | float):
        self.value = value

    def unparse(self) -> str:
        return str(self.value)

    @classmethod
    def fromTree(cls, tree):
        token = tree.children[0]
        try:
            if token.type == "INTBASE":
                python_int = int(token.value, 0)  # 0 means auto-detect base
                value = decimal.Decimal(python_int)
            else:  # DECIMAL type
                value = decimal.Decimal(token.value)
            return cls(value)
        except (ValueError, decimal.InvalidOperation) as e:
            raise ParseError(f"Invalid number syntax: {token.value}") from e


class String(ASTNode):
    """String literal with quote information."""

    def __init__(self, value: str):
        self.value = value

    def unparse(self) -> str:
        return f'"{self.value.replace('"', '\\"')}"'

    @classmethod
    def fromTree(cls, tree):
        if len(tree.children) == 2:
            self = cls("")
        elif len(tree.children) == 3:
            self = cls(tree.children[1])
        return self._position_from_tree(tree)


class Field(ASTNode):
    """Base class for field components in a field access chain.

    Represents one element of a dotted field access like user.name.#0.'field'
    Subclasses handle different field types.
    """


class TokenField(Field):
    """Simple token field like 'name' or 'value'."""

    def __init__(self, name: str):
        self.name = name

    def unparse(self) -> str:
        return self.name


class IndexField(Field):
    """Numeric index field like #0, #1, #42."""

    def __init__(self, index: int):
        self.index = index

    def unparse(self) -> str:
        return f"#{self.index}"


class NameField(Field):
    """Quoted field name like 'field-name' or 'some field'."""

    def __init__(self, name: str):
        self.name = name

    def unparse(self) -> str:
        return f"'{self.name}'"


class ComputedField(Field):
    """Computed field like '(a + b)' - contains an expression."""

    def __init__(self, expression):
        self.expression = expression

    def unparse(self) -> str:
        expr_repr = self.expression.unparse() if hasattr(self.expression, 'unparse') else str(self.expression)
        return f"'{expr_repr}'"


class StringField(Field):
    """String literal used as field like \"http://\"."""

    def __init__(self, string):
        self.string = string

    def unparse(self) -> str:
        return self.string.unparse() if hasattr(self.string, 'unparse') else f'"{self.string}"'


class ScopeField(Field):
    """Scope markers: @ (local), ^ (args), or $name (named scope)."""

    def __init__(self, scope_type: str, name: str | None = None):
        self.scope_type = scope_type  # '@', '^', or '$'
        self.name = name  # None for @ and ^, token for $name

    def unparse(self) -> str:
        if self.scope_type == '$':
            return f"${self.name}"
        return self.scope_type


class Identifier(ASTNode):
    """Field access chain without scope prefix."""

    def __init__(self, fields: list):
        self.fields = fields

    def unparse(self) -> str:
        return ".".join(f.unparse() for f in self.fields)

    @classmethod
    def fromTree(cls, tree):
        self = cls([])
        for child in tree:
            field = None
            if isinstance(child, String):
                field = StringField(child.value)
                field.start = child.start
                field.end = child.end
            elif isinstance(child, lark.Token):
                if child.type == "TOKEN":
                    field = TokenField(child.value)
                elif child.type == "INDEXFIELD":
                    index = int(child.value[1:])
                    field = IndexField(index)
                else:
                    raise ParseError("Unknown field in identifier")
                field._position_from_token(child)
            elif isinstance(child, lark.Tree):
                if child.data == "computefield":
                    field = ComputedField(child)
                else:
                    raise ParseError("Unknown field in identifier")
                field._position_from_tree(child)
            else:
                raise ParseError("Unknown field in identifier")

            self.fields.append(field)
        return self

    @classmethod
    def fromLark(cls, children):
        """Create Identifier from Lark parse tree.

        Grammar: identifier: field_leader ("." field_follower)*
        Children will be field components (dots are filtered out by grammar).
        """
        fields = []
        for child in children:
            # Skip literal dots
            if isinstance(child, str) and child == ".":
                continue

            # If it's already a Field subclass, use it
            if isinstance(child, Field):
                fields.append(child)
            # If it's an AST node, wrap it as appropriate field type
            elif isinstance(child, ASTNode):
                if isinstance(child, String):
                    fields.append(StringField(child))
                else:
                    # Other nodes become computed fields
                    fields.append(ComputedField(child))
            # If it's a token, convert it
            else:
                token_type = getattr(child, 'type', None)
                if token_type == "TOKEN":
                    fields.append(TokenField(str(child)))
                elif token_type == "INDEXFIELD":
                    index_str = str(child)[1:]  # Remove #
                    fields.append(IndexField(int(index_str)))
                else:
                    # Unknown, treat as token
                    fields.append(TokenField(str(child)))

        return cls(fields)

    @classmethod
    def fromLarkIdentifier(cls, children):
        """Create Identifier from identifier grammar rule.

        Grammar: identifier: field_leader ("." field_follower)*
        This is just an alias to fromLark for clarity.
        """
        return cls.fromLark(children)

    @classmethod
    def fromLarkScope(cls, children):
        """Create Identifier from scope grammar rule.

        Grammar: scope: LOCALSCOPE | LOCALSCOPE field_follower | ...
        Children: [LOCALSCOPE/ARGSCOPE/NAMESCOPE, optional field_follower]
        The scope tokens should already be converted to ScopeField by transformer.
        """
        scope_field = children[0]  # This is a ScopeField from token handlers
        fields = [scope_field]
        if len(children) > 1:
            # Has additional field follower
            fields.append(children[1])
        return cls(fields)


class Placeholder(ASTNode):
    """Placeholder token (???)."""

    def unparse(self) -> str:
        return "???"

    def __repr__(self):
        return "Placeholder(???)"

    @classmethod
    def fromTree(cls, tree):
        return cls()._position_from_tree(tree)


# === REFERENCES ===


class TagRef(ASTNode):
    """Tag reference (#name or #name.path/namespace)."""

    def __init__(self, path: list[str], namespace: str | None = None):
        """Create tag reference.

        Args:
            path: List of name components (e.g., ["error", "timeout"])
            namespace: Optional namespace (e.g., "/http")
        """
        self.path = path
        self.namespace = namespace

    def unparse(self) -> str:
        """Convert back to minimal Comp representation."""
        path_str = ".".join(self.path)
        if self.namespace:
            return f"#{path_str}{self.namespace}"
        return f"#{path_str}"

    @classmethod
    def fromLark(cls, children):
        """Create TagRef from tag_reference rule children.

        Grammar: tag_reference: "#" _reference_path
        _reference_path: reference_identifiers reference_namespace?
        reference_identifiers: TOKEN ("." TOKEN)*
        reference_namespace: "/" TOKEN?
        """
        # Extract path and namespace from children
        path = []
        namespace = None

        for child in children:
            if isinstance(child, str):
                if child == "#" or child == ".":
                    continue
                elif child.startswith("/"):
                    namespace = child
            else:
                token_type = getattr(child, 'type', None)
                if token_type == "TOKEN":
                    path.append(str(child))

        if not path:
            raise ParseError("TagRef requires at least one name component")
        return cls(path, namespace)


class ShapeRef(ASTNode):
    """Shape reference (~name or ~name.path/namespace)."""

    def __init__(self, path: list[str], namespace: str | None = None):
        """Create shape reference.

        Args:
            path: List of name components (e.g., ["database", "record"])
            namespace: Optional namespace (e.g., "/std")
        """
        self.path = path
        self.namespace = namespace

    def unparse(self) -> str:
        """Convert back to minimal Comp representation."""
        path_str = ".".join(self.path)
        if self.namespace:
            return f"~{path_str}{self.namespace}"
        return f"~{path_str}"

    @classmethod
    def fromLark(cls, children):
        """Create ShapeRef from shape_reference rule children."""
        path = []
        namespace = None

        for child in children:
            if isinstance(child, str):
                if child == "~" or child == ".":
                    continue
                elif child.startswith("/"):
                    namespace = child
            else:
                token_type = getattr(child, 'type', None)
                if token_type == "TOKEN":
                    path.append(str(child))

        if not path:
            raise ParseError("ShapeRef requires at least one name component")
        return cls(path, namespace)


class FunctionRef(ASTNode):
    """Function reference (|name or |name.path/namespace)."""

    def __init__(self, path: list[str], namespace: str | None = None):
        """Create function reference.

        Args:
            path: List of name components (e.g., ["database", "query"])
            namespace: Optional namespace (e.g., "/std")
        """
        self.path = path
        self.namespace = namespace

    def unparse(self) -> str:
        """Convert back to minimal Comp representation."""
        path_str = ".".join(self.path)
        if self.namespace:
            return f"|{path_str}{self.namespace}"
        return f"|{path_str}"

    @classmethod
    def fromLark(cls, children):
        """Create FunctionRef from function_reference rule children."""
        path = []
        namespace = None

        for child in children:
            if isinstance(child, str):
                if child == "|" or child == ".":
                    continue
                elif child.startswith("/"):
                    namespace = child
            else:
                token_type = getattr(child, 'type', None)
                if token_type == "TOKEN":
                    path.append(str(child))

        if not path:
            raise ParseError("FunctionRef requires at least one name component")
        return cls(path, namespace)


# === COMPLEX STRUCTURES ===


class Structure(ASTNode):
    """Structure literal { field: value, ... }."""

    def __init__(self, operations: list):
        """Create structure.

        Args:
            operations: List of operations (spreads, assignments, unnamed values)
        """
        self.operations = operations

    def unparse(self) -> str:
        """Convert back to minimal Comp representation."""
        op_reprs = []
        for op in self.operations:
            if hasattr(op, "unparse"):
                op_reprs.append(op.unparse())
            else:
                op_reprs.append(str(op))
        return "{" + " ".join(op_reprs) + "}"

    @classmethod
    def fromLark(cls, children):
        """Create Structure from structure rule children."""
        return cls(list(children))


class Block(ASTNode):
    """Block literal { statement; statement; ... }."""

    def __init__(self, statements: list):
        self.statements = statements

    def unparse(self) -> str:
        """Convert back to minimal Comp representation."""
        stmt_reprs = []
        for stmt in self.statements:
            if hasattr(stmt, "unparse"):
                stmt_reprs.append(stmt.unparse())
            else:
                stmt_reprs.append(str(stmt))
        return "{" + "; ".join(stmt_reprs) + "}"

    @classmethod
    def fromLark(cls, children):
        """Create Block from block rule children."""
        return cls(list(children))


# Operations
class Pipeline(ASTNode):
    """Pipeline operation (|>, |, etc)."""

    def __init__(self, left, operator: str, right):
        self.left = left
        self.operator = operator
        self.right = right

    def unparse(self) -> str:
        """Convert back to minimal Comp representation."""
        left_repr = self.left.unparse() if hasattr(self.left, "unparse") else str(self.left)
        right_repr = (
            self.right.unparse() if hasattr(self.right, "unparse") else str(self.right)
        )
        return f"{left_repr} {self.operator} {right_repr}"

    @classmethod
    def fromLark(cls, children):
        """Create Pipeline from various pipeline rule children."""
        if len(children) == 3:
            left, op, right = children
            return cls(left, str(op), right)
        elif len(children) == 2:
            # Special pipeline rules like pipeline_fallback, etc.
            left, right = children
            # The specific operator will be determined by the rule name
            # For now, assume it's passed in via context or handled elsewhere
            return cls(left, "??", right)  # Default fallback
        else:
            raise ParseError(f"Invalid pipeline children: {children}")


class BinaryOp(ASTNode):
    """Binary operation (+, -, *, etc)."""

    def __init__(self, left, operator: str, right):
        self.left = left
        self.operator = operator
        self.right = right

    def unparse(self) -> str:
        """Convert back to minimal Comp representation."""
        # Handle operator precedence with minimal parentheses
        left_repr = self.left.unparse() if hasattr(self.left, "unparse") else str(self.left)
        right_repr = (
            self.right.unparse() if hasattr(self.right, "unparse") else str(self.right)
        )
        return f"{left_repr}{self.operator}{right_repr}"

    @classmethod
    def fromLark(cls, children):
        """Create BinaryOp from binary operation rule children."""
        left, op, right = children
        return cls(left, str(op), right)


class UnaryOp(ASTNode):
    """Unary operation (-, +, !, etc)."""

    def __init__(self, operator: str, operand):
        self.operator = operator
        self.operand = operand

    def unparse(self) -> str:
        """Convert back to minimal Comp representation."""
        operand_repr = (
            self.operand.unparse() if hasattr(self.operand, "unparse") else str(self.operand)
        )
        return f"{self.operator}{operand_repr}"

    @classmethod
    def fromLark(cls, children):
        """Create UnaryOp from unary operation rule children."""
        op, operand = children
        return cls(str(op), operand)


class Scope(ASTNode):
    """Scope reference with optional field access.

    Examples:
        - @ -> Scope("@", [])
        - $mod -> Scope("$mod", [])
        - $mod.config -> Scope("$mod", [Field("token", "config")])
        - ^timeout -> Scope("^", [Field("token", "timeout")])
    """

    def __init__(self, scope_type: str, fields: list[Field] | None = None):
        self.scope_type = scope_type
        self.fields = fields or []

    def unparse(self) -> str:
        """Convert back to minimal Comp representation."""
        if self.fields:
            field_repr = ".".join(f.unparse() for f in self.fields)
            return f"{self.scope_type}.{field_repr}"
        return self.scope_type

    @classmethod
    def fromLark(cls, children):
        """Create Scope from Lark parse tree.

        Grammar allows various forms:
            scope: LOCALSCOPE | LOCALSCOPE field_follower | ARGSCOPE | ARGSCOPE field_follower | NAMESCOPE | NAMESCOPE "." field_follower
        """
        if len(children) == 0:
            raise ParseError("Scope requires at least one child")

        first = children[0]
        token_type = getattr(first, 'type', None)

        # Determine scope type
        if token_type == "LOCALSCOPE":
            scope_type = "@"
        elif token_type == "ARGSCOPE":
            scope_type = "^"
        elif token_type == "NAMESCOPE":
            # NAMESCOPE includes the $ and name like "$mod"
            scope_type = str(first)
        else:
            raise ParseError(f"Unknown scope token type: {token_type}")

        # Collect fields from remaining children
        fields = []
        for child in children[1:]:
            # Skip literal dots
            if isinstance(child, str) and child == ".":
                continue

            # Convert to appropriate Field subclass
            if isinstance(child, Field):
                # Already a Field subclass
                fields.append(child)
            elif isinstance(child, ASTNode):
                if isinstance(child, String):
                    fields.append(StringField(child))
                else:
                    fields.append(ComputedField(child))
            else:
                token_type = getattr(child, 'type', None)
                if token_type == "TOKEN":
                    fields.append(TokenField(str(child)))
                elif token_type == "INDEXFIELD":
                    index_str = str(child)[1:]
                    fields.append(IndexField(int(index_str)))
                else:
                    fields.append(TokenField(str(child)))

        return cls(scope_type, fields)
