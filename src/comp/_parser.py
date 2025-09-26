"""
Main parser interface for the Comp language.

This module provides the primary parse() function that handles single expressions.
It uses a unified Lark grammar with transformers for clean AST construction.

DESIGN GOALS:
- Simple public API: parse(text) → ASTNode
- Clear error messages with source location
- Extensible for all future language features
- Single parser instance for efficiency

CURRENT CAPABILITIES:
- Number literals (all formats)
- String literals (with escape sequences)

FUTURE CAPABILITIES:
- Reference literals (#tag, ~shape, |function)
- Structure literals ({field=value})
- Expressions
- Everything else
"""

__all__ = ["parse"]

from pathlib import Path

from lark import Lark, ParseError, Transformer, UnexpectedCharacters

from . import _ast

_lark_parser: Lark | None = None  # Singleton lark parser instance


def parse(text: str) -> _ast.ASTNode:
    """
    Parse a single Comp expression from text.

    Args:
        text: The source text to parse

    Returns:
        An AST node representing the parsed expression

    Raises:
        ParseError: If the text cannot be parsed

    Examples:
        >>> parse("42")
        NumberLiteral(42)
        >>> parse("0xFF")
        NumberLiteral(255)
        >>> parse('"hello"')
        StringLiteral('hello')
        >>> parse('"say \\"hi\\""')
        StringLiteral('say "hi"')
    """
    text = text.strip()
    if not text:
        raise _ast.ParseError("Empty input")

    parser = _get_parser()
    try:
        result = parser.parse(text)
        assert isinstance(result, list | _ast.ASTNode)
    except (ParseError, UnexpectedCharacters) as e:
        # Try to provide more user-friendly error messages for common cases
        error_msg = str(e)

        # Unterminated string literal
        if "No terminal matches '\"'" in error_msg and "BASIC_STRING" in error_msg:
            raise _ast.ParseError(
                "Unterminated string literal - missing closing quote"
            ) from e

        # Invalid characters (not at start) - after parsing some valid tokens
        if "No terminal matches" in error_msg and "Previous tokens:" in error_msg:
            # Extract the problematic character from error message
            lines = error_msg.split("\n")
            for line in lines:
                if "No terminal matches" in line:
                    # Extract character between quotes
                    start = line.find("'") + 1
                    end = line.find("'", start)
                    if start > 0 and end > start:
                        bad_char = line[start:end]
                        raise _ast.ParseError(
                            f"Invalid character '{bad_char}' in input"
                        ) from e
            # Fallback if we can't extract the character
            raise _ast.ParseError("Invalid character in input") from e

        # Invalid characters at start of input
        if "No terminal matches" in error_msg and "at line 1 col 1" in error_msg:
            if "invalid" in text.lower():
                raise _ast.ParseError("Invalid input - unrecognized characters") from e

        # Generic fallback
        raise _ast.ParseError(f"Syntax error: {e}") from e

    # If list with single item, return that item
    if isinstance(result, list):
        if len(result) == 1:
            result = result[0]
        elif len(result) == 0:
            raise _ast.ParseError("No valid expression found")
        raise _ast.ParseError(f"Expected single expression, got {len(result)} items")

    return result


def _get_parser() -> Lark:
    """Singleton lark parser"""
    global _lark_parser
    if _lark_parser is not None:
        return _lark_parser

    lark_path = Path(__file__).parent / "lark"
    with (lark_path / "comp.lark").open() as f:
        grammar = f.read()

    # Set up parser with import paths and transformer
    _lark_parser = Lark(
        grammar,
        start="start",
        parser="lalr",
        import_paths=[lark_path],
        transformer=_CompTransformer(),
    )
    return _lark_parser


class _CompTransformer(Transformer):
    """
    Transforms Lark parse trees into Comp AST nodes.

    This follows Lark's transformer pattern where methods named after grammar
    rules automatically receive the children of matching tree nodes.
    """

    def start(self, items):
        """Transform the start rule - return single item if only one."""
        if len(items) == 1:
            return items[0]
        return items

    def expression_list(self, items):
        """Transform list of expressions."""
        # Filter out None values (empty matches)
        filtered = [item for item in items if item is not None]
        if len(filtered) == 1:
            return filtered[0]
        return filtered

    def expression(self, items):
        """Transform expression rule - just pass through the contained expression."""
        return items[0]

    def number(self, tokens):
        """Transform number rule into NumberLiteral AST node."""
        token = tokens[0]
        return _ast.NumberLiteral.fromToken(token)

    def string(self, tokens):
        """Transform string rule into StringLiteral AST node."""
        token = tokens[0]
        return _ast.StringLiteral.fromToken(token)

    def identifier(self, tokens):
        """Transform identifier rule into Identifier AST node."""
        token = tokens[0]
        return _ast.Identifier(str(token))

    def tag_reference(self, tokens):
        """Transform tag_reference rule into TagReference AST node."""
        # tokens[0] is the IDENTIFIER_PATH token (sigil is consumed by grammar)
        identifier_path_token = tokens[0]
        return _ast.TagReference.fromToken(identifier_path_token)

    def shape_reference(self, tokens):
        """Transform shape_reference rule into ShapeReference AST node."""
        # tokens[0] is the IDENTIFIER_PATH token (sigil is consumed by grammar)
        identifier_path_token = tokens[0]
        return _ast.ShapeReference.fromToken(identifier_path_token)

    def function_reference(self, tokens):
        """Transform function_reference rule into FunctionReference AST node."""
        # tokens[0] is the IDENTIFIER_PATH token (sigil is consumed by grammar)
        identifier_path_token = tokens[0]
        return _ast.FunctionReference.fromToken(identifier_path_token)

    def structure(self, tokens):
        """Transform structure rule into StructureLiteral AST node."""
        return _ast.StructureLiteral.fromToken(tokens)

    def structure_field(self, tokens):
        """Transform structure_field rule - just pass through the field."""
        return tokens[0]

    def named_field(self, tokens):
        """Transform named_field rule into NamedField AST node."""
        return _ast.NamedField.fromToken(tokens)

    def positional_field(self, tokens):
        """Transform positional_field rule into PositionalField AST node."""
        return _ast.PositionalField.fromToken(tokens)

    def binary_operation(self, tokens):
        """Transform binary_operation rule into BinaryOperation AST node."""
        return _ast.BinaryOperation.fromToken(tokens)

    def unary_operation(self, tokens):
        """Transform unary_operation rule into UnaryOperation AST node."""
        return _ast.UnaryOperation.fromToken(tokens)

    def math_expression(self, tokens):
        """Transform math_expression rule - just pass through the expression."""
        return tokens[0]

    def atom(self, tokens):
        """Transform atom rule - just pass through the atom."""
        return tokens[0]

    # Mathematical operators transformer methods
    def mathematical_operators__atom(self, tokens):
        """Transform mathematical_operators__atom rule."""
        return tokens[0]

    def mathematical_operators__number(self, tokens):
        """Transform mathematical_operators__number rule into NumberLiteral AST node."""
        token = tokens[0]
        return _ast.NumberLiteral.fromToken(token)

    def mathematical_operators__string(self, tokens):
        """Transform mathematical_operators__string rule into StringLiteral AST node."""
        token = tokens[0]
        return _ast.StringLiteral.fromToken(token)

    def mathematical_operators__identifier(self, tokens):
        """Transform mathematical_operators__identifier rule into Identifier AST node."""
        token = tokens[0]
        return _ast.Identifier(str(token))

    def mathematical_operators__structure(self, tokens):
        """Transform mathematical_operators__structure rule into StructureLiteral AST node."""
        # tokens[0] is '{', tokens[-1] is '}', middle tokens are fields
        # Filter out the brace tokens and keep only the field nodes
        fields = [
            token
            for token in tokens[1:-1]
            if hasattr(token, "__class__") and hasattr(token.__class__, "__module__")
        ]
        return _ast.StructureLiteral(fields)

    def mathematical_operators__structure_field(self, tokens):
        """Transform mathematical_operators__structure_field rule."""
        return tokens[0]

    def mathematical_operators__named_field(self, tokens):
        """Transform mathematical_operators__named_field rule into NamedField AST node."""
        # tokens[0] is the key (identifier or string), tokens[1] is EQUALS, tokens[2] is the value
        # Skip the EQUALS token and pass just key and value
        return _ast.NamedField.fromToken([tokens[0], tokens[2]])

    def mathematical_operators__positional_field(self, tokens):
        """Transform mathematical_operators__positional_field rule into PositionalField AST node."""
        return _ast.PositionalField.fromToken(tokens)

    def mathematical_operators__tag_reference(self, tokens):
        """Transform mathematical_operators__tag_reference rule into TagReference AST node."""
        # tokens[0] is the IDENTIFIER_PATH token (sigil is consumed by grammar)
        identifier_path_token = tokens[0]
        return _ast.TagReference.fromToken(identifier_path_token)

    def mathematical_operators__shape_reference(self, tokens):
        """Transform mathematical_operators__shape_reference rule into ShapeReference AST node."""
        # tokens[0] is the IDENTIFIER_PATH token (sigil is consumed by grammar)
        identifier_path_token = tokens[0]
        return _ast.ShapeReference.fromToken(identifier_path_token)

    def mathematical_operators__function_reference(self, tokens):
        """Transform mathematical_operators__function_reference rule into FunctionReference AST node."""
        # tokens[0] is the IDENTIFIER_PATH token (sigil is consumed by grammar)
        identifier_path_token = tokens[0]
        return _ast.FunctionReference.fromToken(identifier_path_token)
