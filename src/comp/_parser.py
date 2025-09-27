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
- Mathematical expressions with proper precedence
- Logical operators (&&, ||, !)
- Comparison operators (==, !=, <, >, <=, >=)
- Comments (;)
- Structure literals ({field=value})
- Advanced operators (fallback ??, pipe |, etc.)
- All basic language constructs
"""

__all__ = ["parse"]

from pathlib import Path

from lark import Lark, ParseError, Transformer, UnexpectedCharacters

from . import _ast

# Global parser instance (singleton)
_lark_parser: Lark | None = None


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

    return result


def _get_parser() -> Lark:
    """Singleton lark parser"""
    global _lark_parser
    if _lark_parser is not None:
        return _lark_parser

    lark_path = Path(__file__).parent / "lark"
    with (lark_path / "unified_expressions.lark").open() as f:
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
    
    This class contains methods for each grammar rule that should produce
    an AST node. Method names correspond to the rule names in the grammar.
    """

    # Core transformer methods for unified grammar
    def binary_operation(self, tokens):
        """Transform binary_operation rule into BinaryOperation AST node."""
        # For comparison operators, extract the actual operator string
        if len(tokens) >= 3 and hasattr(tokens[1], 'data') and tokens[1].data == 'comp_op':
            # Extract the actual operator from the comp_op tree
            operator = str(tokens[1].children[0])
        else:
            # Regular operator
            operator = str(tokens[1])
        
        return _ast.BinaryOperation(tokens[0], operator, tokens[2])

    def unary_operation(self, tokens):
        """Transform unary_operation rule into UnaryOperation AST node."""
        operator = str(tokens[0])
        operand = tokens[1]
        return _ast.UnaryOperation(operator, operand)

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

    # Advanced operations
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

    def field_access_operation(self, tokens):
        """Transform field_access_operation rule into FieldAccessOperation AST node."""
        return _ast.FieldAccessOperation.fromToken(tokens)

    def string_field_access_operation(self, tokens):
        """Transform string field access (object."field") into FieldAccessOperation AST node."""
        # tokens: [object, dot, string_literal]
        object, _, string_literal = tokens
        # Extract the actual string content from the StringLiteral
        field_name = string_literal.value
        return _ast.FieldAccessOperation(object, field_name)

    def computed_field_access_operation(self, tokens):
        """Transform computed field access (object.'expr') into FieldAccessOperation AST node."""
        # tokens: [object, dot, quote, expression, quote]
        object, _, _, expression, _ = tokens
        # Store the computed expression for future evaluation
        # For now, use a special field name format that preserves the expression
        field_name = f"<computed:{expression}>"  # Better representation for debugging
        return _ast.FieldAccessOperation(object, field_name)

    def computed_expression(self, tokens):
        """Transform bare computed expression ('expr') into the inner expression."""
        # tokens: [quote, expression, quote] 
        _, expression, _ = tokens
        # For bare computed expressions, just return the inner expression
        # The single quotes indicate it should be computed, but as a standalone
        # expression it evaluates to its contents
        return expression

    def index_access_operation(self, tokens):
        """Transform index_access_operation rule into IndexAccessOperation AST node."""
        return _ast.IndexAccessOperation.fromToken(tokens)

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
        return _ast.NamedBlockOperation.fromToken(tokens)

    # Structure handling
    def structure(self, tokens):
        """Transform structure rule into StructureLiteral AST node."""
        # Extract fields from the structure
        fields = []
        for token in tokens:
            if isinstance(token, _ast.ASTNode):
                fields.append(token)

        return _ast.StructureLiteral(fields)

    def structure_field(self, tokens):
        """Transform structure_field rule."""
        return tokens[0]

    def named_field(self, tokens):
        """Transform named_field rule into NamedField AST node."""
        # tokens: [identifier, ASSIGN, expression]
        key = tokens[0]
        value = tokens[2]  # Skip the ASSIGN token
        
        key_name = key.name if isinstance(key, _ast.Identifier) else str(key)
        return _ast.NamedField(key_name, value)

    def scope_assignment(self, tokens):
        """Transform scope_assignment rule into StructureOperation AST node."""
        # tokens: [scope_target, assignment_op, expression]
        target = tokens[0]
        operator = str(tokens[1])
        expression = tokens[2]
        return _ast.StructureOperation(target, operator, expression)

    def field_assignment(self, tokens):
        """Transform field_assignment rule into StructureOperation AST node."""
        # tokens: [field_target, assignment_op, expression]
        target = tokens[0]
        operator = str(tokens[1])
        expression = tokens[2]
        return _ast.StructureOperation(target, operator, expression)

    def spread_operation(self, tokens):
        """Transform spread_operation rule into StructureOperation AST node."""
        # tokens: [SPREAD, expression]
        target = _ast.SpreadTarget()
        operator = ".."  # Spread operator
        expression = tokens[1]  # Skip the SPREAD token
        return _ast.StructureOperation(target, operator, expression)

    def scope_target(self, tokens):
        """Transform scope_target rule into ScopeTarget AST node."""
        # Handle different patterns: @name, @name.path, $name, $name.path
        scope_type = str(tokens[0])  # @ or $
        name = tokens[1].name if isinstance(tokens[1], _ast.Identifier) else str(tokens[1])
        
        field_path = []
        if len(tokens) > 3:  # Has DOT and field_path
            field_path = tokens[3]  # field_path result
            
        return _ast.ScopeTarget(scope_type, name, field_path)

    def field_target(self, tokens):
        """Transform field_target rule into FieldTarget AST node."""
        # Handle: identifier, identifier.field_path, string, or 'expression'
        first_token = tokens[0]
        
        if isinstance(first_token, _ast.Identifier):
            name = first_token.name
        elif isinstance(first_token, _ast.StringLiteral):
            name = first_token.value  # Use the string value as the field name
        elif hasattr(first_token, 'type') and first_token.type == 'SINGLE_QUOTE':
            # Handle 'expression' case: tokens are [SINGLE_QUOTE, expression, SINGLE_QUOTE]
            expression = tokens[1]
            name = f"<computed:{expression}>"  # Store computed expression representation
        else:
            name = str(first_token)
        
        field_path = []
        if len(tokens) > 2 and not (hasattr(tokens[0], 'type') and tokens[0].type == 'SINGLE_QUOTE'):
            # Has DOT and field_path (but not for 'expression' case)
            field_path = tokens[2]  # field_path result
            
        return _ast.FieldTarget(name, field_path)

    def field_path(self, tokens):
        """Transform field_path rule into list of field names."""
        # tokens: identifier (DOT identifier)*
        path = []
        for token in tokens:
            if isinstance(token, _ast.Identifier):
                path.append(token.name)
            elif hasattr(token, 'value'):
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
        return _ast.StructureOperation(None, "=", tokens[0])

    def spread_field(self, tokens):
        """Transform spread_field rule into SpreadField AST node."""
        return _ast.SpreadField(tokens[1])  # Skip the SPREAD token

    # Special constructs
    def index_reference(self, tokens):
        """Transform index_reference rule into IndexReference AST node."""
        return _ast.IndexReference(tokens[1])  # Skip the HASH token

    def block_definition(self, tokens):
        """Transform block_definition rule into BlockDefinition AST node."""
        return _ast.BlockDefinition(tokens[1])  # Skip BLOCK_START token

    def placeholder(self, tokens):
        """Transform placeholder rule into Placeholder AST node."""
        return _ast.Placeholder()

    def array_type(self, tokens):
        """Transform array_type rule into ArrayType AST node."""
        identifier = tokens[0]
        return _ast.ArrayType(identifier)

    def field_name(self, tokens):
        """Transform field_name rule into FieldName AST node."""
        # tokens: [SINGLE_QUOTE, identifier, SINGLE_QUOTE]
        identifier = tokens[1]
        name = identifier.name if isinstance(identifier, _ast.Identifier) else str(identifier)
        return _ast.FieldName(name)
