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
    "Number",
    "String",
    "Identifier",
    "TagRef",
    "ShapeRef",
    "FunctionRef",
    "Structure",
    "Block",
    "Pipeline",
    "BinaryOp",
    "UnaryOp",
    "FieldAccess",
    "Scope",
    "Placeholder",
    "FieldName",
]

import decimal


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
        for key, value in kwargs.items():
            setattr(self, key, value)

    def __repr__(self):
        attrs = []
        for key, value in self.__dict__.items():
            if not key.startswith("_"):
                if isinstance(value, str):
                    attrs.append(f'{key}="{value}"')
                else:
                    attrs.append(f"{key}={value}")
        return f"{self.__class__.__name__}({', '.join(attrs)})"

    def __eq__(self, other):
        return isinstance(other, self.__class__) and self.__dict__ == other.__dict__

    def repr(self) -> str:
        """Convert back to minimal Comp source representation."""
        # Default implementation - subclasses should override
        return "???"

    def find(self, node_type) -> "ASTNode | None":
        """Find first child node of the specified type (depth-first search)."""
        # Check if this node matches
        if isinstance(self, node_type):
            return self

        # Search through all attributes that are AST nodes
        for _attr_name, attr_value in self.__dict__.items():
            if isinstance(attr_value, ASTNode):
                result = attr_value.find(node_type)
                if result is not None:
                    return result
            elif isinstance(attr_value, list):
                # Search through lists of AST nodes
                for item in attr_value:
                    if isinstance(item, ASTNode):
                        result = item.find(node_type)
                        if result is not None:
                            return result

        return None

    def find_all(self, node_type) -> list["ASTNode"]:
        """Find all child nodes of the specified type (depth-first search)."""
        results = []

        # Check if this node matches
        if isinstance(self, node_type):
            results.append(self)

        # Search through all attributes that are AST nodes
        for _attr_name, attr_value in self.__dict__.items():
            if isinstance(attr_value, ASTNode):
                results.extend(attr_value.find_all(node_type))
            elif isinstance(attr_value, list):
                # Search through lists of AST nodes
                for item in attr_value:
                    if isinstance(item, ASTNode):
                        results.extend(item.find_all(node_type))

        return results


# Literals and basic values
class Number(ASTNode):
    """Numeric literal (integer, decimal, float)."""

    def __init__(self, value: decimal.Decimal | int | float):
        self.value = value

    def repr(self) -> str:
        """Convert back to minimal Comp representation."""
        # Use raw if available, otherwise convert value back
        return str(self.value)

    @classmethod
    def fromLark(cls, token):
        """Create Number from a Lark token (DECIMAL or BASED)."""
        raw = str(token)
        try:
            if token.type == "BASED" or token.type.endswith("__BASED"):
                # Handle 0x, 0b, 0o formats
                python_int = int(raw, 0)  # 0 means auto-detect base
                value = decimal.Decimal(python_int)
            else:  # DECIMAL types
                value = decimal.Decimal(raw)
            return cls(value)
        except (ValueError, decimal.InvalidOperation) as e:
            raise ParseError(f"Invalid number syntax: {raw}") from e


class String(ASTNode):
    """String literal with quote information."""

    def __init__(
        self, value: str, quote_type: str | None = None):
        self.value = value
        self.quote_type = quote_type  # '"', "'", or '"""'

    def repr(self) -> str:
        """Convert back to minimal Comp representation."""
        return f'"{self.value}"'

    @classmethod
    def fromLark(cls, token):
        """Create String from a Lark token (SINGLE_STRING, DOUBLE_STRING, MULTILINE_STRING)."""
        raw = str(token)

        if token.type == "SINGLE_STRING":
            value = raw[1:-1]  # Remove single quotes
            return cls(value, "'")
        elif token.type == "DOUBLE_STRING":
            value = raw[1:-1]  # Remove double quotes
            return cls(value, '"')
        elif token.type == "MULTILINE_STRING":
            value = raw[3:-3]  # Remove triple quotes
            return cls(value, '"""')
        else:
            raise ParseError(f"Unknown string token type: {token.type}")


class Identifier(ASTNode):
    """Simple identifier (variable/function name)."""

    def __init__(self, name: str):
        self.name = name

    def repr(self) -> str:
        """Convert back to minimal Comp representation."""
        return self.name

    @classmethod
    def fromLark(cls, token):
        """Create Identifier from a Lark TOKEN."""
        return cls(str(token))


class Placeholder(ASTNode):
    """Placeholder token (???)."""

    def repr(self) -> str:
        """Convert back to minimal Comp representation."""
        return "???"


class FieldName(ASTNode):
    """Quoted field name ('field_name')."""

    def __init__(self, name: str):
        self.name = name

    def repr(self) -> str:
        """Convert back to minimal Comp representation."""
        return f"'{self.name}'"

    @classmethod
    def fromLark(cls, children):
        """Create FieldName from field_name rule children (quoted string)."""
        token = children[0]
        name = str(token)[1:-1]  # Remove quotes
        return cls(name)


# References
class TagRef(ASTNode):
    """Tag reference (#name)."""

    def __init__(self, name: str):
        self.name = name

    def repr(self) -> str:
        """Convert back to minimal Comp representation."""
        return f"#{self.name}"

    @classmethod
    def fromLark(cls, children):
        """Create TagRef from tag_reference rule children."""
        token = children[0]
        name = str(token)[1:]  # Remove #
        return cls(name)


class ShapeRef(ASTNode):
    """Shape reference (/name)."""

    def __init__(self, name: str):
        self.name = name

    def repr(self) -> str:
        """Convert back to minimal Comp representation."""
        return f"/{self.name}"

    @classmethod
    def fromLark(cls, children):
        """Create ShapeRef from shape_reference rule children."""
        token = children[0]
        name = str(token)[1:]  # Remove /
        return cls(name)


class FunctionRef(ASTNode):
    """Function reference (@name)."""

    def __init__(self, name: str):
        self.name = name

    def repr(self) -> str:
        """Convert back to minimal Comp representation."""
        return f"@{self.name}"

    @classmethod
    def fromLark(cls, children):
        """Create FunctionRef from function_reference rule children."""
        token = children[0]
        name = str(token)[1:]  # Remove @
        return cls(name)


# Complex structures
class Structure(ASTNode):
    """Structure literal { field: value, ... }."""

    def __init__(self, fields: list):
        self.fields = fields

    def repr(self) -> str:
        """Convert back to minimal Comp representation."""
        field_reprs = []
        for field in self.fields:
            if hasattr(field, 'repr'):
                field_reprs.append(field.repr())
            else:
                field_reprs.append(str(field))
        return "{" + " ".join(field_reprs) + "}"

    @classmethod
    def fromLark(cls, children):
        """Create Structure from structure rule children."""
        return cls(list(children))


class Block(ASTNode):
    """Block literal { statement; statement; ... }."""

    def __init__(self, statements: list):
        self.statements = statements

    def repr(self) -> str:
        """Convert back to minimal Comp representation."""
        stmt_reprs = []
        for stmt in self.statements:
            if hasattr(stmt, 'repr'):
                stmt_reprs.append(stmt.repr())
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

    def repr(self) -> str:
        """Convert back to minimal Comp representation."""
        left_repr = self.left.repr() if hasattr(self.left, 'repr') else str(self.left)
        right_repr = self.right.repr() if hasattr(self.right, 'repr') else str(self.right)
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

    def repr(self) -> str:
        """Convert back to minimal Comp representation."""
        # Handle operator precedence with minimal parentheses
        left_repr = self.left.repr() if hasattr(self.left, "repr") else str(self.left)
        right_repr = (
            self.right.repr() if hasattr(self.right, "repr") else str(self.right)
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

    def repr(self) -> str:
        """Convert back to minimal Comp representation."""
        operand_repr = (
            self.operand.repr() if hasattr(self.operand, "repr") else str(self.operand)
        )
        return f"{self.operator}{operand_repr}"

    @classmethod
    def fromLark(cls, children):
        """Create UnaryOp from unary operation rule children."""
        op, operand = children
        return cls(str(op), operand)


class FieldAccess(ASTNode):
    """Field access (obj.field, obj.'field', obj[expr])."""

    def __init__(self, object, field):
        self.object = object
        self.field = field

    def repr(self) -> str:
        """Convert back to minimal Comp representation."""
        obj_repr = (
            self.object.repr() if hasattr(self.object, "repr") else str(self.object)
        )
        field_repr = (
            self.field.repr() if hasattr(self.field, "repr") else str(self.field)
        )

        # Handle different field access styles
        if isinstance(self.field, FieldName):
            return f"{obj_repr}.{field_repr}"
        else:
            return f"{obj_repr}.{field_repr}"

    @classmethod
    def fromLark(cls, children):
        """Create FieldAccess from field access rule children."""
        obj, field = children
        return cls(obj, field)


class Scope(ASTNode):
    """Scope with variable assignments."""

    def __init__(self, assignments: list):
        self.assignments = assignments

    def repr(self) -> str:
        """Convert back to minimal Comp representation."""
        assignment_reprs = []
        for assignment in self.assignments:
            if hasattr(assignment, 'repr'):
                assignment_reprs.append(assignment.repr())
            else:
                assignment_reprs.append(str(assignment))
        return "{" + "; ".join(assignment_reprs) + "}"

    @classmethod
    def fromLark(cls, children):
        """Create Scope from scope rule children."""
        return cls(list(children))
