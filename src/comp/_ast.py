"""
AST node definitions and exceptions for Comp language.

This module defines the Abstract Syntax Tree nodes used to represent parsed Comp code.
Currently supports number and string literals, identifiers, and reference literals.
"""

__all__ = [
    "ASTNode",
    "NumberLiteral",
    "StringLiteral",
    "Identifier",
    "TagReference",
    "ShapeReference",
    "FunctionReference",
    "StructureLiteral",
    "StructureOperation",
    "NamedField",
    "PositionalField",
    "BinaryOperation",
    "UnaryOperation",
    "AssignmentOperation",
    "FallbackOperation",
    "ShapeUnionOperation",
    "PipelineFailureOperation",
    "PipelineBlockOperation",
    "PipelineModifierOperation",
    "FieldAccessOperation",
    "IndexAccessOperation",
    "IndexReference",
    "PrivateAttachOperation",
    "PrivateAccessOperation",
    "BlockInvokeOperation",
    "NamedBlockOperation",
    "BlockDefinition",
    "SpreadField",
    "WeakNamedField",
    "StrongNamedField",
    "SpreadNamedField",
    "WeakSpreadNamedField",
    "StrongSpreadNamedField",
    "Placeholder",
    "ArrayType",
    "FieldName",
    "ScopeAssignment",
    "FieldAssignment",
    "ScopeTarget",
    "FieldTarget",
    "ParseError",
]

import ast
import decimal
from typing import Any


class ParseError(Exception):
    """Raised when parsing fails due to invalid syntax."""

    def __init__(
        self, message: str, line: int | None = None, column: int | None = None
    ):
        super().__init__(message)
        self.line = line
        self.column = column


class ASTNode:
    """Base class for all AST nodes."""

    def __init__(self):
        # Location information for error reporting (future)
        self.line: int | None = None
        self.column: int | None = None

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(...)"

    @classmethod
    def fromToken(cls, tokens):
        """
        Default fromToken implementation for simple AST nodes.

        This base implementation works for classes with no constructor parameters
        (other than self). Subclasses with parameters should override this method.
        """
        return cls()


class NumberLiteral(ASTNode):
    """AST node representing a number literal."""

    def __init__(self, value: decimal.Decimal):
        super().__init__()
        self.value = value

    @classmethod
    def fromToken(cls, token):
        """Create NumberLiteral from a Lark token."""
        try:
            # Handle based integers (0x, 0b, 0o) with ast.literal_eval
            # Check for both old and new token type names (with mathematical_operators prefix)
            if token.type == "BASED" or token.type.endswith("__BASED"):
                python_int = ast.literal_eval(str(token))
                decimal_value = decimal.Decimal(python_int)
            else:  # DECIMAL types
                decimal_value = decimal.Decimal(str(token))

            return cls(decimal_value)

        except SyntaxError as err:
            # Pass through literal_eval's better error messages
            raise ParseError(f"Invalid number: {err.args[0]}") from err
        except (decimal.InvalidOperation, ValueError) as err:
            raise ParseError(f"Invalid number syntax: {token}") from err

    def __repr__(self) -> str:
        return f"NumberLiteral({self.value})"

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, NumberLiteral):
            return False
        return self.value == other.value

    def __hash__(self) -> int:
        return hash(self.value)


class StringLiteral(ASTNode):
    """AST node representing a string literal."""

    def __init__(self, value: str):
        super().__init__()
        self.value = value

    @classmethod
    def fromToken(cls, token):
        """Create StringLiteral from a Lark token."""
        string_text = str(token)

        try:
            # Use Python's built-in string literal parsing
            processed = ast.literal_eval(string_text)
            return cls(processed)

        except (ValueError, SyntaxError) as err:
            raise ParseError(f"Invalid string literal: {string_text}") from err

    def __repr__(self) -> str:
        return f"StringLiteral({self.value!r})"

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, StringLiteral):
            return False
        return self.value == other.value

    def __hash__(self) -> int:
        return hash(self.value)


class Identifier(ASTNode):
    """AST node representing an identifier (variable name, etc)."""

    def __init__(self, name: str):
        super().__init__()
        self.name = name

    def __repr__(self) -> str:
        return f"Identifier({self.name!r})"

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Identifier):
            return False
        return self.name == other.name

    def __hash__(self) -> int:
        return hash(self.name)

    @classmethod
    def fromToken(cls, token):
        """Create Identifier from a Lark token."""
        return cls(str(token))


class TagReference(ASTNode):
    """AST node representing a tag reference (#tag)."""

    def __init__(self, name: str):
        super().__init__()
        self.name = name

    @classmethod
    def fromToken(cls, token):
        """Create TagReference from a Lark token (without the # sigil)."""
        # Token contains the identifier path without the sigil
        return cls(str(token))

    def __repr__(self) -> str:
        return f"TagReference({self.name!r})"

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, TagReference):
            return False
        return self.name == other.name

    def __hash__(self) -> int:
        return hash(self.name)


class ShapeReference(ASTNode):
    """AST node representing a shape reference (~shape)."""

    def __init__(self, name: str):
        super().__init__()
        self.name = name

    @classmethod
    def fromToken(cls, token):
        """Create ShapeReference from a Lark token (without the ~ sigil)."""
        # Token contains the identifier path without the sigil
        return cls(str(token))

    def __repr__(self) -> str:
        return f"ShapeReference({self.name!r})"

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, ShapeReference):
            return False
        return self.name == other.name

    def __hash__(self) -> int:
        return hash(self.name)


class FunctionReference(ASTNode):
    """AST node representing a function reference (|function)."""

    def __init__(self, name: str):
        super().__init__()
        self.name = name

    @classmethod
    def fromToken(cls, token):
        """Create FunctionReference from a Lark token (without the | sigil)."""
        # Token contains the identifier path without the sigil
        return cls(str(token))

    def __repr__(self) -> str:
        return f"FunctionReference({self.name!r})"

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, FunctionReference):
            return False
        return self.name == other.name

    def __hash__(self) -> int:
        return hash(self.name)


class StructureLiteral(ASTNode):
    """AST node representing a structure literal {...}."""

    def __init__(self, operations: list["StructureOperation"]):
        super().__init__()
        self.operations = operations

    @classmethod
    def fromToken(cls, tokens):
        """Create StructureLiteral from a list of operation tokens."""
        return cls(tokens)

    def __repr__(self) -> str:
        return f"StructureLiteral({self.operations!r})"

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, StructureLiteral):
            return False
        return self.operations == other.operations

    def __hash__(self) -> int:
        return hash(tuple(self.operations))


class StructureOperation(ASTNode):
    """AST node representing a single operation within a structure.

    Each operation has:
    - target: field/scope reference (or None for unnamed/positional)
    - operator: assignment operator (=, *=, ?=, ..=)
    - expression: any expression (literal, pipeline, etc.)
    """

    def __init__(self, target: ASTNode | None, operator: str, expression: ASTNode):
        super().__init__()
        self.target = target  # ScopeTarget, FieldTarget, or None for positional
        self.operator = operator  # "=", "*=", "?=", "..="
        self.expression = expression  # Any expression

    @classmethod
    def fromToken(cls, tokens):
        """Create StructureOperation from tokens: [target, operator, expression]."""
        if len(tokens) == 3:
            target, operator, expression = tokens
            return cls(target, str(operator), expression)
        else:
            raise ValueError(
                f"Expected 3 tokens for StructureOperation, got {len(tokens)}"
            )

    def __repr__(self) -> str:
        if self.target is None:
            return f"StructureOperation(None, {self.operator!r}, {self.expression!r})"
        return f"StructureOperation({self.target!r}, {self.operator!r}, {self.expression!r})"

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, StructureOperation):
            return False
        return (
            self.target == other.target
            and self.operator == other.operator
            and self.expression == other.expression
        )

    def __hash__(self) -> int:
        return hash((self.target, self.operator, self.expression))


class NamedField(ASTNode):
    """AST node representing a named field in a structure (key=value)."""

    def __init__(self, name: str, value: ASTNode):
        super().__init__()
        self.name = name
        self.value = value

    @classmethod
    def fromToken(cls, tokens):
        """Create NamedField from key and value tokens."""
        # tokens[0] is the key (identifier or string), tokens[1] is the value
        key = tokens[0]
        value = tokens[1]

        # Extract the name from the key AST node
        if isinstance(key, Identifier):
            name = key.name
        elif isinstance(key, StringLiteral):
            name = key.value
        else:
            raise ParseError(f"Invalid field name type: {type(key)}")

        return cls(name, value)

    def __repr__(self) -> str:
        return f"NamedField({self.name!r}, {self.value!r})"

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, NamedField):
            return False
        return self.name == other.name and self.value == other.value

    def __hash__(self) -> int:
        return hash((self.name, self.value))


class PositionalField(ASTNode):
    """AST node representing a positional field in a structure (value)."""

    def __init__(self, value: ASTNode):
        super().__init__()
        self.value = value

    @classmethod
    def fromToken(cls, tokens):
        """Create PositionalField from value token."""
        # tokens[0] is the value expression
        value = tokens[0]
        return cls(value)

    def __repr__(self) -> str:
        return f"PositionalField({self.value!r})"

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, PositionalField):
            return False
        return self.value == other.value

    def __hash__(self) -> int:
        return hash(self.value)


class BinaryOperation(ASTNode):
    """AST node representing a binary operation (left operator right)."""

    def __init__(self, left: ASTNode, operator: str, right: ASTNode):
        super().__init__()
        self.left = left
        self.operator = operator
        self.right = right

    @classmethod
    def fromToken(cls, tokens):
        """Create BinaryOperation from tokens: [left, operator, right]."""
        left, operator, right = tokens
        return cls(left, str(operator), right)

    def __repr__(self) -> str:
        return f"BinaryOperation({self.left!r}, {self.operator!r}, {self.right!r})"

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, BinaryOperation):
            return False
        return (
            self.left == other.left
            and self.operator == other.operator
            and self.right == other.right
        )

    def __hash__(self) -> int:
        return hash((self.left, self.operator, self.right))


class UnaryOperation(ASTNode):
    """AST node representing a unary operation (operator operand)."""

    def __init__(self, operator: str, operand: ASTNode):
        super().__init__()
        self.operator = operator
        self.operand = operand

    @classmethod
    def fromToken(cls, tokens):
        """Create UnaryOperation from tokens: [operator, operand]."""
        operator, operand = tokens
        return cls(str(operator), operand)

    def __repr__(self) -> str:
        return f"UnaryOperation({self.operator!r}, {self.operand!r})"

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, UnaryOperation):
            return False
        return self.operator == other.operator and self.operand == other.operand

    def __hash__(self) -> int:
        return hash((self.operator, self.operand))


class AssignmentOperation(ASTNode):
    """AST node representing an assignment operation (target = value)."""

    def __init__(self, target: str, operator: str, value: ASTNode):
        super().__init__()
        self.target = target
        self.operator = operator
        self.value = value

    @classmethod
    def fromToken(cls, tokens):
        """Create AssignmentOperation from tokens: [target, operator, value]."""
        target, operator, value = tokens
        # Extract target name from identifier
        target_name = target.name if isinstance(target, Identifier) else str(target)
        return cls(target_name, str(operator), value)

    def __repr__(self) -> str:
        return (
            f"AssignmentOperation({self.target!r}, {self.operator!r}, {self.value!r})"
        )


class FallbackOperation(ASTNode):
    """AST node representing a fallback operation (left ?? right)."""

    def __init__(self, left: ASTNode, operator: str, right: ASTNode):
        super().__init__()
        self.left = left
        self.operator = operator
        self.right = right

    @classmethod
    def fromToken(cls, tokens):
        """Create FallbackOperation from tokens: [left, operator, right]."""
        left, operator, right = tokens
        return cls(left, str(operator), right)

    def __repr__(self) -> str:
        return f"FallbackOperation({self.left!r}, {self.operator!r}, {self.right!r})"


class ShapeUnionOperation(ASTNode):
    """AST node representing a shape union operation (left | right)."""

    def __init__(self, left: ASTNode, right: ASTNode):
        super().__init__()
        self.left = left
        self.right = right

    @classmethod
    def fromToken(cls, tokens):
        """Create ShapeUnionOperation from tokens: [left, right]."""
        left, _, right = tokens  # Middle token is the | operator
        return cls(left, right)

    def __repr__(self) -> str:
        return f"ShapeUnionOperation({self.left!r}, {self.right!r})"


class PipelineFailureOperation(ASTNode):
    """AST node representing a pipeline failure operation (operation |? fallback)."""

    def __init__(self, operation: ASTNode, fallback: ASTNode):
        super().__init__()
        self.operation = operation
        self.fallback = fallback

    @classmethod
    def fromToken(cls, tokens):
        """Create PipelineFailureOperation from tokens."""
        operation, _, fallback = tokens  # Middle token is |?
        return cls(operation, fallback)

    def __repr__(self) -> str:
        return f"PipelineFailureOperation({self.operation!r}, {self.fallback!r})"


class PipelineModifierOperation(ASTNode):
    """AST node representing a pipeline modifier operation (pipeline |<< modifier)."""

    def __init__(self, pipeline: ASTNode, modifier: ASTNode):
        super().__init__()
        self.pipeline = pipeline
        self.modifier = modifier

    @classmethod
    def fromToken(cls, tokens):
        """Create PipelineModifierOperation from tokens."""
        pipeline, _, modifier = tokens  # Middle token is |<<
        return cls(pipeline, modifier)

    def __repr__(self) -> str:
        return f"PipelineModifierOperation({self.pipeline!r}, {self.modifier!r})"


class PipelineBlockOperation(ASTNode):
    """AST node representing a pipeline block operation (process |{} transform)."""

    def __init__(self, process: ASTNode, transform: ASTNode, block: ASTNode):
        super().__init__()
        self.process = process
        self.transform = transform
        self.block = block

    @classmethod
    def fromToken(cls, tokens):
        """Create PipelineBlockOperation from tokens."""
        process, _, block, _, transform = tokens  # |{}, }
        return cls(process, transform, block)

    def __repr__(self) -> str:
        return f"PipelineBlockOperation({self.process!r}, {self.transform!r}, {self.block!r})"


class FieldAccessOperation(ASTNode):
    """AST node representing a field access operation (object.field)."""

    def __init__(self, object: ASTNode, field: str):
        super().__init__()
        self.object = object
        self.field = field

    @classmethod
    def fromToken(cls, tokens):
        """Create FieldAccessOperation from tokens."""
        object, _, field = tokens  # Middle token is .
        field_name = field.name if isinstance(field, Identifier) else str(field)
        return cls(object, field_name)

    def __repr__(self) -> str:
        return f"FieldAccessOperation({self.object!r}, {self.field!r})"


class IndexAccessOperation(ASTNode):
    """AST node representing an index access operation (object#index)."""

    def __init__(self, object: ASTNode, index: ASTNode):
        super().__init__()
        self.object = object
        self.index = index

    @classmethod
    def fromToken(cls, tokens):
        """Create IndexAccessOperation from tokens."""
        if len(tokens) == 3:
            # Old syntax: object # index
            object, _, index = tokens  # Middle token is #
        elif len(tokens) == 4:
            # New dotted syntax: object . # index_number
            object, _, _, index_token = tokens  # Middle tokens are . and #
            # Convert INDEX_NUMBER token to NumberLiteral
            from decimal import Decimal

            index = NumberLiteral(Decimal(index_token.value))
        else:
            raise ValueError(
                f"Unexpected token count for IndexAccessOperation: {len(tokens)}"
            )
        return cls(object, index)

    def __repr__(self) -> str:
        return f"IndexAccessOperation({self.object!r}, {self.index!r})"


class IndexReference(ASTNode):
    """AST node representing a standalone index reference (#1)."""

    def __init__(self, index: ASTNode):
        super().__init__()
        self.index = index

    @classmethod
    def fromToken(cls, tokens):
        """Create IndexReference from tokens."""
        _, index = tokens  # First token is #
        return cls(index)

    def __repr__(self) -> str:
        return f"IndexReference({self.index!r})"


class PrivateAttachOperation(ASTNode):
    """AST node representing a private data attachment (object&{data})."""

    def __init__(self, object: ASTNode, private_data: ASTNode):
        super().__init__()
        self.object = object
        self.private_data = private_data

    @classmethod
    def fromToken(cls, tokens):
        """Create PrivateAttachOperation from tokens."""
        object, _, private_data = tokens  # Middle token is &
        return cls(object, private_data)

    def __repr__(self) -> str:
        return f"PrivateAttachOperation({self.object!r}, {self.private_data!r})"


class PrivateAccessOperation(ASTNode):
    """AST node representing a private field access (object&.field)."""

    def __init__(self, object: ASTNode, field: str):
        super().__init__()
        self.object = object
        self.field = field

    @classmethod
    def fromToken(cls, tokens):
        """Create PrivateAccessOperation from tokens."""
        object, _, field = tokens  # Middle token is &.
        field_name = field.name if isinstance(field, Identifier) else str(field)
        return cls(object, field_name)

    def __repr__(self) -> str:
        return f"PrivateAccessOperation({self.object!r}, {self.field!r})"


class BlockInvokeOperation(ASTNode):
    """AST node representing a block invocation (|.block)."""

    def __init__(self, block: ASTNode):
        super().__init__()
        self.block = block

    @classmethod
    def fromToken(cls, tokens):
        """Create BlockInvokeOperation from tokens."""
        _, block = tokens  # First token is |.
        return cls(block)

    def __repr__(self) -> str:
        return f"BlockInvokeOperation({self.block!r})"


class NamedBlockOperation(ASTNode):
    """AST node representing a named block operation (name.{expression})."""

    def __init__(self, name: ASTNode, block: ASTNode):
        super().__init__()
        self.name = name
        self.block = block

    @classmethod
    def fromToken(cls, tokens):
        """Create NamedBlockOperation from tokens."""
        name, _, block = tokens  # name DOT block_definition
        return cls(name, block)

    def __repr__(self) -> str:
        return f"NamedBlockOperation({self.name!r}, {self.block!r})"


class BlockDefinition(ASTNode):
    """AST node representing a block definition (.{expression})."""

    def __init__(self, expression: ASTNode):
        super().__init__()
        self.expression = expression

    @classmethod
    def fromToken(cls, tokens):
        """Create BlockDefinition from tokens."""
        _, expression, _ = tokens  # .{, expression, }
        return cls(expression)

    def __repr__(self) -> str:
        return f"BlockDefinition({self.expression!r})"


class SpreadField(ASTNode):
    """AST node representing a spread field in a structure (..expression)."""

    def __init__(self, expression: ASTNode):
        super().__init__()
        self.expression = expression

    @classmethod
    def fromToken(cls, tokens):
        """Create SpreadField from tokens."""
        _, expression = tokens  # First token is ..
        return cls(expression)

    def __repr__(self) -> str:
        return f"SpreadField({self.expression!r})"


class WeakNamedField(NamedField):
    """AST node representing a weak assignment named field (name ?= value)."""

    def __init__(self, name: str, value: ASTNode):
        super().__init__(name, value)
        self.operator = "?="

    def __repr__(self) -> str:
        return f"WeakNamedField({self.name!r}, {self.value!r})"


class StrongNamedField(NamedField):
    """AST node representing a strong assignment named field (name *= value)."""

    def __init__(self, name: str, value: ASTNode):
        super().__init__(name, value)
        self.operator = "*="

    def __repr__(self) -> str:
        return f"StrongNamedField({self.name!r}, {self.value!r})"


class SpreadNamedField(NamedField):
    """AST node representing a spread assignment named field (name ..= value)."""

    def __init__(self, name: str, value: ASTNode):
        super().__init__(name, value)
        self.operator = "..="

    def __repr__(self) -> str:
        return f"SpreadNamedField({self.name!r}, {self.value!r})"


class WeakSpreadNamedField(NamedField):
    """AST node representing a weak spread assignment named field (name ?..= value)."""

    def __init__(self, name: str, value: ASTNode):
        super().__init__(name, value)
        self.operator = "?..="

    def __repr__(self) -> str:
        return f"WeakSpreadNamedField({self.name!r}, {self.value!r})"


class StrongSpreadNamedField(NamedField):
    """AST node representing a strong spread assignment named field (name *..= value)."""

    def __init__(self, name: str, value: ASTNode):
        super().__init__(name, value)
        self.operator = "*..="

    def __repr__(self) -> str:
        return f"StrongSpreadNamedField({self.name!r}, {self.value!r})"


class Placeholder(ASTNode):
    """AST node representing a placeholder operator (???)."""

    def __init__(self):
        super().__init__()

    @classmethod
    def fromToken(cls, tokens):
        """Create Placeholder from tokens."""
        return cls()

    def __repr__(self) -> str:
        return "Placeholder()"


class ArrayType(ASTNode):
    """AST node representing an array type (base_type[])."""

    def __init__(self, base_type: ASTNode):
        super().__init__()
        self.base_type = base_type

    @classmethod
    def fromToken(cls, tokens):
        """Create ArrayType from tokens."""
        base_type, _, _ = tokens  # base_type, [, ]
        return cls(base_type)

    def __repr__(self) -> str:
        return f"ArrayType({self.base_type!r})"


class FieldName(ASTNode):
    """AST node representing a field name expression ('name')."""

    def __init__(self, name: str):
        super().__init__()
        self.name = name

    @classmethod
    def fromToken(cls, tokens):
        """Create FieldName from tokens."""
        _, name, _ = tokens  # ', name, '
        name_str = name.name if isinstance(name, Identifier) else str(name)
        return cls(name_str)

    def __repr__(self) -> str:
        return f"FieldName({self.name!r})"


class ScopeAssignment(ASTNode):
    """AST node representing scope assignments (@local = expr, $out.field = expr)."""

    def __init__(self, target: "ScopeTarget", operator: str, value: ASTNode):
        super().__init__()
        self.target = target
        self.operator = operator
        self.value = value

    @classmethod
    def fromToken(cls, tokens):
        """Create ScopeAssignment from tokens: [target, operator, value]."""
        target, operator, value = tokens
        return cls(target, str(operator), value)

    def __repr__(self) -> str:
        return f"ScopeAssignment({self.target!r}, {self.operator!r}, {self.value!r})"


class FieldAssignment(ASTNode):
    """AST node representing field assignments (field = expr, field.nested = expr)."""

    def __init__(self, target: "FieldTarget", operator: str, value: ASTNode):
        super().__init__()
        self.target = target
        self.operator = operator
        self.value = value

    @classmethod
    def fromToken(cls, tokens):
        """Create FieldAssignment from tokens: [target, operator, value]."""
        target, operator, value = tokens
        return cls(target, str(operator), value)

    def __repr__(self) -> str:
        return f"FieldAssignment({self.target!r}, {self.operator!r}, {self.value!r})"


class ScopeTarget(ASTNode):
    """AST node representing scope assignment targets (@local, $out.field)."""

    def __init__(self, scope_type: str, name: str, field_path: list[str] | None = None):
        super().__init__()
        self.scope_type = scope_type  # "@" or "$"
        self.name = name
        self.field_path = field_path or []

    @classmethod
    def fromToken(cls, tokens):
        """Create ScopeTarget from tokens: [scope_type, identifier, ...optional field_path]."""
        scope_type = str(tokens[0])  # @ or $
        name = tokens[1].name if hasattr(tokens[1], "name") else str(tokens[1])

        field_path = []
        if len(tokens) > 3:  # Has DOT and field_path
            field_path = tokens[3]  # field_path result

        return cls(scope_type, name, field_path)

    def __repr__(self) -> str:
        if self.field_path:
            path = ".".join([self.name] + self.field_path)
            return f"ScopeTarget({self.scope_type!r}, {path!r})"
        return f"ScopeTarget({self.scope_type!r}, {self.name!r})"


class SpreadTarget(ASTNode):
    """AST node representing spread operation target (no specific field, spreads into structure)."""

    def __init__(self):
        super().__init__()

    def __repr__(self) -> str:
        return "SpreadTarget()"


class FieldTarget(ASTNode):
    """AST node representing field assignment targets (field, field.nested)."""

    def __init__(self, name: str, field_path: list[str] | None = None):
        super().__init__()
        self.name = name
        self.field_path = field_path or []

    @classmethod
    def fromToken(cls, tokens):
        """Create FieldTarget from tokens: [identifier/string/'expr', ...optional field_path]."""
        first_token = tokens[0]

        if hasattr(first_token, "name"):  # Identifier
            name = first_token.name
        elif hasattr(first_token, "value"):  # StringLiteral
            name = first_token.value
        elif hasattr(first_token, "type") and first_token.type == "SINGLE_QUOTE":
            # Handle 'expression' case: [SINGLE_QUOTE, expression, SINGLE_QUOTE]
            expression = tokens[1]
            name = f"<computed:{expression}>"
        else:
            name = str(first_token)

        field_path = []
        if len(tokens) > 2 and not (
            hasattr(tokens[0], "type") and tokens[0].type == "SINGLE_QUOTE"
        ):
            # Has DOT and field_path (but not for 'expression' case)
            field_path = tokens[2]  # field_path result

        return cls(name, field_path)

    def __repr__(self) -> str:
        if self.field_path:
            path = ".".join([self.name] + self.field_path)
            return f"FieldTarget({path!r})"
        return f"FieldTarget({self.name!r})"
