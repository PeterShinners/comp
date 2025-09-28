"""
Main parser interface for the Comp language.

This module provides the primary parse() function that handles single expressions.
It uses a unified Lark grammar with transformers for clean AST construction.

DESIGN GOALS:
- Simple public API: parse(text) → ASTNode
- Clear error messages with source location
- Extensible for all future language features
- Single parser instance for efficiency

ARCHITECTURAL STRATEGY:
The parser acts as "glue" that understands how to route different grammar patterns
to the appropriate AST node factories, but stays out of the processing business itself.

- TRANSFORMER METHODS: Minimal routing logic that calls AST factory methods
- AST NODE FACTORIES: Heavy lifting (validation, token processing, construction)
- SEPARATION OF CONCERNS: Parser handles coordination, AST nodes handle processing
- CONSISTENT PATTERN: All complex parsing logic uses factory methods (fromToken, fromScopeTokens, etc.)

This keeps the parser focused on grammar-to-AST mapping while co-locating
processing logic with the data structures it creates.

CURRENT CAPABILITIES:
- Number literals (all formats)
- String literals (with escape sequences)
- Mathematical expressions with proper precedence
- Logical operators (&&, ||, !)
- Comparison operators (==, !=, <, >, <=, >=)
- Comments (;)
- Structure literals ({field=value})
- Pipeline operators (fallback ??, pipe |, etc.)
- Scope references ($ctx, @local, ^timeout)
- Field access operations (dot notation, scope field access)
- All basic language constructs
"""

__all__ = ["parse"]

from pathlib import Path

from lark import Lark, ParseError, Transformer, UnexpectedCharacters

from . import _ast

# Global parser instance (singleton)
_lark_parser: Lark | None = None


def parse(text: str) -> list | _ast.ASTNode:
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
        start="expression",
        parser="lalr",
        import_paths=[lark_path],
        transformer=_CompTransformer(),
    )

    return _lark_parser


class _CompTransformer(Transformer):
    """
    Lark transformer to convert parse trees into AST nodes.

    ARCHITECTURAL PRINCIPLE:
    This transformer acts as "glue" that routes grammar patterns to appropriate
    AST node factory methods. It should stay out of the processing business itself.

    TRANSFORMER METHODS SHOULD:
    - Be minimal (ideally 1-2 lines)
    - Route tokens to AST factory methods (fromToken, fromScopeTokens, etc.)
    - Handle simple token extraction/normalization only
    - NOT contain complex validation, parsing logic, or construction

    HEAVY LIFTING SHOULD BE IN:
    - AST node factory methods (@classmethod def fromToken, etc.)
    - This keeps processing logic co-located with data structures
    - Makes testing easier and responsibilities clearer

    Method names correspond to the rule names in the grammar.
    """

    # Core transformer methods for unified grammar
    def binary_operation(self, tokens):
        """Transform binary_operation rule into BinaryOperation AST node."""
        # For comparison operators, extract the actual operator string
        if (
            len(tokens) >= 3
            and hasattr(tokens[1], "data")
            and tokens[1].data == "comp_op"
        ):
            # Extract the actual operator from the comp_op tree
            operator = str(tokens[1].children[0])
            # Rebuild tokens with the extracted operator for fromToken
            normalized_tokens = [tokens[0], operator, tokens[2]]
            return _ast.BinaryOperation.fromToken(normalized_tokens)
        else:
            # Regular operator - can use fromToken directly
            return _ast.BinaryOperation.fromToken(tokens)

    def unary_operation(self, tokens):
        """Transform unary_operation rule into UnaryOperation AST node."""
        return _ast.UnaryOperation.fromToken(tokens)

    def comp_op(self, tokens):
        """Transform comp_op rule - extract comparison operator."""
        return tokens[0]

    def atom(self, tokens):
        """Transform atom rule."""
        if len(tokens) == 3 and str(tokens[0]) == "(" and str(tokens[2]) == ")":
            # Parenthesized expression: (expression)
            return tokens[1]
        else:
            # Regular atom: pass through
            return tokens[0]

    # AST node creation methods
    def number(self, tokens):
        """Transform number rule into NumberLiteral AST node."""
        # The numbers grammar imports create AST nodes, but sometimes raw tokens come through
        token = tokens[0]
        if isinstance(token, _ast.NumberLiteral):
            return token
        else:
            return _ast.NumberLiteral.fromToken(token)

    def string(self, tokens):
        """Transform string rule into StringLiteral AST node."""
        # The strings grammar imports create AST nodes, but sometimes raw tokens come through
        token = tokens[0]
        if isinstance(token, _ast.StringLiteral):
            return token
        else:
            return _ast.StringLiteral.fromToken(token)

    def identifier(self, tokens):
        """Transform identifier rule into Identifier AST node."""
        # The identifiers grammar imports create AST nodes, but sometimes raw tokens come through
        token = tokens[0]
        if isinstance(token, _ast.Identifier):
            return token
        else:
            return _ast.Identifier.fromToken(token)

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

    def scope_reference(self, tokens):
        """Transform scope_reference rule into appropriate scope AST node.

        EXAMPLE OF ARCHITECTURAL PATTERN:
        - Parser method is minimal - just routes to AST factory
        - All complex logic (validation, scope checking, construction) is in
          FieldAccessOperation.fromScopeTokens() where it belongs
        """
        return _ast.FieldAccessOperation.fromScopeTokens(tokens)

    def assignment_operation(self, tokens):
        """Transform assignment_operation rule into AssignmentOperation AST node."""
        target = tokens[0]
        operator = tokens[1]
        expression = tokens[2]
        return _ast.AssignmentOperation(target, operator, expression)

    def fallback_operation(self, tokens):
        """Transform fallback_operation rule into FallbackOperation AST node."""
        return _ast.FallbackOperation.fromToken(tokens)

    def shape_union_operation(self, tokens):
        """Transform shape_union_operation rule into ShapeUnionOperation AST node."""
        return _ast.ShapeUnionOperation.fromToken(tokens)

    def pipeline_failure_operation(self, tokens):
        """Transform pipeline_failure_operation rule into PipelineFailureOperation AST node."""
        return _ast.PipelineFailureOperation.fromToken(tokens)

    def pipeline_modifier_operation(self, tokens):
        """Transform pipeline_modifier_operation rule into PipelineModifierOperation AST node."""
        return _ast.PipelineModifierOperation.fromToken(tokens)

    def field_access_operation(self, tokens):
        """Transform field_access_operation rule into FieldAccessOperation AST node.

        ARCHITECTURAL PATTERN:
        - Complex token parsing (dots, scopes, indexes, computed fields) delegated
          to FieldAccessOperation.fromFieldTokens() factory method
        - Parser stays focused on grammar-to-factory routing
        """
        return _ast.FieldAccessOperation.fromFieldTokens(tokens)

    def computed_expression(self, tokens):
        """Transform bare computed expression ('expr') into the inner expression."""
        # tokens: [quote, expression, quote]
        _, expression, _ = tokens
        # For bare computed expressions, just return the inner expression
        # The single quotes indicate it should be computed, but as a standalone
        # expression it evaluates to its contents
        return expression

    def private_attach_operation(self, tokens):
        """Transform private_attach_operation rule into PrivateAttachOperation AST node."""
        return _ast.PrivateAttachOperation.fromToken(tokens)

    def private_access_operation(self, tokens):
        """Transform private_access_operation rule into PrivateAccessOperation AST node."""
        return _ast.PrivateAccessOperation.fromToken(tokens)

    def block_invoke_operation(self, tokens):
        """Transform block_invoke_operation rule into BlockInvokeOperation AST node."""
        return _ast.BlockInvokeOperation.fromToken(tokens)

    def named_block_operation(self, tokens):
        """Transform named_block_operation rule into NamedBlockOperation AST node."""
        # tokens: [name, BLOCK_START, expression, RBRACE]
        name = tokens[0]
        expression = tokens[2]  # Skip BLOCK_START and get expression
        # Create a BlockDefinition wrapper for the expression
        block = _ast.BlockDefinition(expression)
        return _ast.NamedBlockOperation.fromToken([name, None, block])  # Use None for DOT placeholder

    # Structure handling
    def structure(self, tokens):
        """Transform structure rule into StructureLiteral AST node."""
        # Extract fields from the structure
        fields = []
        for token in tokens:
            if isinstance(token, _ast.ASTNode):
                fields.append(token)

        return _ast.StructureLiteral.fromToken(fields)

    def structure_field(self, tokens):
        """Transform structure_field rule."""
        return tokens[0]

    def named_field(self, tokens):
        """Transform named_field rule into NamedField AST node."""
        # tokens: [identifier, ASSIGN, expression]
        key = tokens[0]
        value = tokens[2]  # Skip the ASSIGN token
        return _ast.NamedField.fromToken([key, value])

    def scope_assignment(self, tokens):
        """Transform scope_assignment rule into StructureOperation AST node."""
        return _ast.StructureOperation.fromToken(tokens)

    def field_assignment(self, tokens):
        """Transform field_assignment rule into StructureOperation AST node."""
        return _ast.StructureOperation.fromToken(tokens)

    def spread_operation(self, tokens):
        """Transform spread_operation rule into StructureOperation AST node."""
        # tokens: [SPREAD, expression]
        target = _ast.SpreadTarget.fromToken([])  # Use fromToken for consistency
        operator = ".."  # Spread operator
        expression = tokens[1]  # Skip the SPREAD token
        return _ast.StructureOperation.fromToken([target, operator, expression])

    def scope_target(self, tokens):
        """Transform scope_target rule into ScopeTarget AST node."""
        return _ast.ScopeTarget.fromToken(tokens)

    def field_target(self, tokens):
        """Transform field_target rule into FieldTarget AST node."""
        return _ast.FieldTarget.fromToken(tokens)

    def field_path(self, tokens):
        """Transform field_path rule into list of field names."""
        # tokens: identifier (DOT identifier)*
        path = []
        for token in tokens:
            if isinstance(token, _ast.Identifier):
                path.append(token.name)
            elif hasattr(token, "value"):
                path.append(token.value)
            else:
                path.append(str(token))
        return path

    def assignment_op(self, tokens):
        """Transform assignment_op rule into operator string."""
        return tokens[0]

    def positional_field(self, tokens):
        """Transform positional_field rule into StructureOperation AST node."""
        # Positional field has no target and implicit "=" operator
        return _ast.StructureOperation.fromToken([None, "=", tokens[0]])

    def spread_field(self, tokens):
        """Transform spread_field rule into SpreadField AST node."""
        return _ast.SpreadField.fromToken(tokens)

    # Special constructs
    def index_reference(self, tokens):
        """Transform index_reference rule into FieldAccessOperation with IndexReference."""
        # Create the IndexReference from the tokens
        index_ref = _ast.IndexReference.fromToken(tokens)
        # Wrap it in a FieldAccessOperation with Placeholder object and IndexReference in fields
        return _ast.FieldAccessOperation(_ast.Placeholder(), index_ref)

    def block_definition(self, tokens):
        """Transform block_definition rule into BlockDefinition AST node."""
        return _ast.BlockDefinition.fromToken(tokens)

    def placeholder(self, tokens):
        """Transform placeholder rule into Placeholder AST node."""
        return _ast.Placeholder.fromToken(tokens)

    def array_type(self, tokens):
        """Transform array_type rule into ArrayType AST node."""
        return _ast.ArrayType.fromToken(tokens)

    def field_name(self, tokens):
        """Transform field_name rule into FieldName AST node."""
        return _ast.FieldName.fromToken(tokens)
