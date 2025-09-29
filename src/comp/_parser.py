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

import decimal
from pathlib import Path

from lark import Lark, ParseError, Transformer, UnexpectedCharacters

from . import _ast

# Global parser instance (singleton)
_lark_parser: Lark | None = None


def _post_process_ast(node):
    """Post-process AST to handle pipeline conversions and argument collection."""
    if isinstance(node, _ast.AssignmentOperation):
        # Process assignment values for pipelines
        processed_pipeline = _post_process_ast(node.pipeline)
        if processed_pipeline != node.pipeline:
            return _ast.AssignmentOperation(node.target, node.operator, processed_pipeline)

    elif isinstance(node, _ast.PipelineOperation):
        # Process pipeline stages recursively
        processed_stages = [_post_process_ast(stage) for stage in node.stages]
        if processed_stages != node.stages:
            return _ast.PipelineOperation(processed_stages)

    elif isinstance(node, _ast.StructureLiteral):
        # Process structure operations (this calls our existing argument collection)
        processed_ops = _collect_function_arguments_global(node.operations)
        if processed_ops != node.operations:
            return _ast.StructureLiteral(processed_ops)

    # Recursively process other node types
    elif hasattr(node, '__dict__'):
        changed = False
        new_attrs = {}
        for attr_name, attr_value in node.__dict__.items():
            if isinstance(attr_value, _ast.ASTNode):
                processed_attr = _post_process_ast(attr_value)
                new_attrs[attr_name] = processed_attr
                if processed_attr != attr_value:
                    changed = True
            elif isinstance(attr_value, list):
                processed_list = [_post_process_ast(item) if isinstance(item, _ast.ASTNode) else item for item in attr_value]
                new_attrs[attr_name] = processed_list
                if processed_list != attr_value:
                    changed = True
            else:
                new_attrs[attr_name] = attr_value

        if changed:
            # Create new instance with processed attributes
            new_node = type(node).__new__(type(node))
            for attr_name, attr_value in new_attrs.items():
                setattr(new_node, attr_name, attr_value)
            return new_node

    return node


def _collect_function_arguments_global(fields):
    """Global version of function argument collection (extracted from structure logic)."""
    if not fields:
        return fields

    processed = []
    i = 0

    while i < len(fields):
        field = fields[i]

        # Check if this is a positional field containing a pipeline with function call
        if (isinstance(field, _ast.StructureOperation) and
            field.target is None and
            field.operator == "=" and
            isinstance(field.expression, _ast.PipelineOperation)):

            pipeline = field.expression
            # Check if last stage is a PipelineFunctionOperation without arguments
            if (len(pipeline.stages) >= 2 and
                isinstance(pipeline.stages[-1], _ast.PipelineFunctionOperation) and
                pipeline.stages[-1].args is None):

                # Collect subsequent positional fields as arguments
                function_op = pipeline.stages[-1]
                args = []
                j = i + 1

                # Collect following positional fields as arguments
                while (j < len(fields) and
                       isinstance(fields[j], _ast.StructureOperation) and
                       fields[j].target is None and
                       fields[j].operator == "="):
                    args.append(fields[j].expression)
                    j += 1

                # If we collected arguments, create a StructureLiteral to hold them
                if args:
                    # Convert arguments to StructureOperations (positional fields)
                    arg_operations = []
                    for arg in args:
                        arg_op = _ast.StructureOperation(None, "=", arg)
                        arg_operations.append(arg_op)

                    # Create new StructureLiteral containing the arguments
                    args_struct = _ast.StructureLiteral(arg_operations)
                    function_op.args = args_struct
                    processed.append(field)  # Add the modified field
                    i = j  # Skip the collected arguments
                    continue

        # No argument collection needed, add field as-is
        processed.append(field)
        i += 1

    return processed


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

        # Post-process the AST to handle pipeline conversions
        result = _post_process_ast(result)

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



    def assignment_operation(self, tokens):
        """Transform assignment_operation rule into AssignmentOperation AST node."""
        return _ast.AssignmentOperation.fromToken(tokens)

    def fallback_operation(self, tokens):
        """Transform fallback_operation rule into FallbackOperation AST node."""
        return _ast.FallbackOperation.fromToken(tokens)

    def pipeline_operation(self, tokens):
        """Transform pipeline_operation rule into PipelineOperation AST node."""
        # tokens: [left, PIPE, right] - create pipeline from left and right
        left, _, right = tokens

        # Convert right side to PipelineFunctionOperation if it's a simple identifier
        if isinstance(right, _ast.FieldAccessOperation) and right.object is None and len(right.fields) == 1:
            if isinstance(right.fields[0], _ast.Identifier):
                func_name = right.fields[0].name
                function_ref = _ast.FunctionReference(func_name)
                right = _ast.PipelineFunctionOperation.fromFunctionReference(function_ref)

        # Flatten nested pipelines to create a single pipeline with all stages
        if isinstance(left, _ast.PipelineOperation):
            # Extend existing pipeline with the new stage
            stages = left.stages + [right]
            return _ast.PipelineOperation(stages)
        else:
            # Create new pipeline with left and right as stages
            return _ast.PipelineOperation([left, right])

    def pipeline_function_call_operation(self, tokens):
        """Transform pipeline_function_call_operation rule into PipelineOperation with function call."""
        # tokens: [left, PIPE, identifier, arg1, arg2, ...]
        left = tokens[0]
        # Skip the PIPE token (tokens[1])
        func_name = tokens[2]  # The identifier
        arguments = tokens[3:]  # All the function arguments

        # Create function reference
        function_ref = _ast.FunctionReference(func_name.name)

        # Create arguments structure from the argument list
        if arguments:
            # Convert function arguments to StructureLiteral with proper StructureOperations
            structure_ops = self._ensure_structure_operations(arguments)
            args_structure = _ast.StructureLiteral(structure_ops)
            func_operation = _ast.PipelineFunctionOperation(function_ref, args_structure)
        else:
            func_operation = _ast.PipelineFunctionOperation.fromFunctionReference(function_ref)

        # Flatten nested pipelines to create a single pipeline with all stages
        if isinstance(left, _ast.PipelineOperation):
            # Extend existing pipeline with the function call stage
            stages = left.stages + [func_operation]
            return _ast.PipelineOperation(stages)
        else:
            # Create new pipeline with left and function call as stages
            return _ast.PipelineOperation([left, func_operation])

    def function_field_assignment(self, tokens):
        """Transform function_field_assignment rule into StructureOperation AST node."""
        # This is similar to field_assignment but for function arguments
        return _ast.StructureOperation.fromToken(tokens)

    def function_argument(self, tokens):
        """Transform function_argument rule into appropriate AST node."""
        if len(tokens) == 1:
            # Simple expression argument
            return tokens[0]
        else:
            # Field assignment argument - delegate to function_field_assignment
            return _ast.StructureOperation.fromToken(tokens)

    def _ensure_structure_operations(self, items):
        """Convert a list of items to StructureOperations, wrapping raw expressions as needed."""
        operations = []
        for item in items:
            if isinstance(item, _ast.StructureOperation):
                # Already a StructureOperation
                operations.append(item)
            else:
                # Raw expression - convert to StructureOperation with no field name
                operations.append(_ast.StructureOperation(None, '=', item))
        return operations

    def pipeline_failure_operation(self, tokens):
        """Transform pipeline_failure_operation rule into extended PipelineOperation."""
        # tokens: [left, PIPELINE_FAILURE, right]
        left, _, right = tokens

        # Create a PipelineFailureOperation stage with a placeholder operation
        # We'll use the right (fallback) value as both operation and fallback for now
        fallback_stage = _ast.PipelineFailureOperation(right, right)

        # If left is already a pipeline, extend it with the fallback stage
        if isinstance(left, _ast.PipelineOperation):
            stages = left.stages + [fallback_stage]
            return _ast.PipelineOperation(stages)
        else:
            # Create new pipeline with left as first stage and fallback as second
            return _ast.PipelineOperation([left, fallback_stage])

    def pipeline_modifier_operation(self, tokens):
        """Transform pipeline_modifier_operation rule into PipelineModifierOperation AST node."""
        return _ast.PipelineModifierOperation.fromToken(tokens)

    def pipeline_block_operation(self, tokens):
        """Transform pipeline_block_operation rule into PipelineBlockOperation AST node."""
        return _ast.PipelineBlockOperation.fromToken(tokens)

    def pipeline_struct_operation(self, tokens):
        """Transform pipeline_struct_operation rule into pipeline stage operation."""
        expression = tokens[0]
        # Skip the |{ token and get the structure fields (exclude closing })
        structure_fields = tokens[2:-1]

        # Create a structure literal as the pipeline stage
        # Use StructureLiteral instead of PipelineStructOperation for the stage
        structure_ops = self._ensure_structure_operations(structure_fields)
        struct_literal = _ast.StructureLiteral(structure_ops)

        # If expression is already a pipeline, extend it with this stage
        if hasattr(expression, 'stages'):
            new_stages = expression.stages + [struct_literal]
            return _ast.PipelineOperation(new_stages)
        else:
            # Create new pipeline with expression as first stage and struct as second
            return _ast.PipelineOperation([expression, struct_literal])

    def pipeline_block_invoke_operation(self, tokens):
        """Transform pipeline_block_invoke_operation rule into PipelineBlockInvokeOperation AST node."""
        expression = tokens[0]
        # Skip the |: token and get the target tokens
        target_tokens = tokens[2:]

        # Transform the target using existing field access logic
        if len(target_tokens) == 1:
            # Simple identifier: |:block
            target = _ast.FieldAccessOperation(None, target_tokens[0])
        elif len(target_tokens) == 2:
            # @ identifier or ^ identifier: |:@scope or |:^scope
            if target_tokens[0].type == "AT":
                target = _ast.FieldAccessOperation(_ast.Scope("@"), target_tokens[1])
            elif target_tokens[0].type == "CARET":
                target = _ast.FieldAccessOperation(_ast.Scope("^"), target_tokens[1])
            else:
                target = _ast.FieldAccessOperation(None, target_tokens[0])
        elif len(target_tokens) == 3:
            # @ # number or ^ # number: |:@#4 or |:^#2
            if target_tokens[0].type == "AT":
                number_value = int(target_tokens[2].value) if hasattr(target_tokens[2], 'value') else int(str(target_tokens[2]))
                number_node = _ast.NumberLiteral(decimal.Decimal(number_value))
                index_ref = _ast.IndexReference(number_node)
                target = _ast.FieldAccessOperation(_ast.Scope("@"), index_ref)
            elif target_tokens[0].type == "CARET":
                number_value = int(target_tokens[2].value) if hasattr(target_tokens[2], 'value') else int(str(target_tokens[2]))
                number_node = _ast.NumberLiteral(decimal.Decimal(number_value))
                index_ref = _ast.IndexReference(number_node)
                target = _ast.FieldAccessOperation(_ast.Scope("^"), index_ref)
            else:
                target = _ast.FieldAccessOperation(None, target_tokens[0])
        else:
            target = _ast.FieldAccessOperation(None, target_tokens[0])

        # Create a PipelineBlockInvokeOperation stage with the target
        block_invoke_stage = _ast.PipelineBlockInvokeOperation(target, target)  # Use target for both operation and target for now

        # If expression is already a pipeline, extend it with the block invoke stage
        if isinstance(expression, _ast.PipelineOperation):
            stages = expression.stages + [block_invoke_stage]
            return _ast.PipelineOperation(stages)
        else:
            # Create new pipeline with expression as first stage and block invoke as second
            return _ast.PipelineOperation([expression, block_invoke_stage])

    def pipeline_block_invoke_literal(self, tokens):
        """Transform pipeline_block_invoke_literal rule into PipelineBlockInvokeOperation with block literal."""
        expression = tokens[0]
        # Skip the |: and :{ tokens and get structure fields (exclude the final RBRACE)
        structure_fields = [t for t in tokens[3:-1] if not isinstance(t, str)]

        # Create the block literal
        block_literal = _ast.BlockLiteral(structure_fields)

        # Create a PipelineBlockInvokeOperation stage with the block literal
        block_invoke_stage = _ast.PipelineBlockInvokeOperation(block_literal, block_literal)

        # If expression is already a pipeline, extend it with the block invoke stage
        if isinstance(expression, _ast.PipelineOperation):
            stages = expression.stages + [block_invoke_stage]
            return _ast.PipelineOperation(stages)
        else:
            # Create new pipeline with expression as first stage and block invoke as second
            return _ast.PipelineOperation([expression, block_invoke_stage])

    # === STANDALONE PIPELINE OPERATIONS ===

    def standalone_block_invoke_operation(self, tokens):
        """Transform standalone_block_invoke_operation rule into StandaloneBlockInvokeOperation AST node."""
        # tokens: [BLOCK_INVOKE, qualified_identifier]
        target = tokens[1]  # Skip the |: token
        return _ast.StandaloneBlockInvokeOperation(target)

    def standalone_failure_operation(self, tokens):
        """Transform standalone_failure_operation rule into StandaloneFailureOperation AST node."""
        # tokens: [PIPELINE_FAILURE, or_expr]
        fallback = tokens[1]  # Skip the |? token
        return _ast.StandaloneFailureOperation(fallback)

    def standalone_modifier_operation(self, tokens):
        """Transform standalone_modifier_operation rule into StandaloneModifierOperation AST node."""
        # tokens: [PIPELINE_MODIFIER, or_expr]
        modifier = tokens[1]  # Skip the |<< token
        return _ast.StandaloneModifierOperation(modifier)

    def standalone_struct_operation(self, tokens):
        """Transform standalone_struct_operation rule into StandaloneStructOperation AST node."""
        # tokens: [PIPELINE_BLOCK_START, structure_field*, RBRACE]
        structure_fields = tokens[1:-1]  # Skip |{ and } tokens
        return _ast.StandaloneStructOperation(structure_fields)

    def field_access_operation(self, tokens):
        """Transform field_access_operation rule into FieldAccessOperation AST node.

        ARCHITECTURAL PATTERN:
        - Complex token parsing (dots, scopes, indexes, computed fields) delegated
          to FieldAccessOperation.fromFieldTokens() factory method
        - Parser stays focused on grammar-to-factory routing
        """
        return _ast.FieldAccessOperation.fromFieldTokens(tokens)

    def field_reference(self, tokens):
        """Transform field_reference rule into proper field chain."""
        # Handle different field_reference patterns:
        # - identifier -> single identifier
        # - identifier DOT field_path -> FieldAccessOperation with field chain
        # - string -> string literal
        # - field_name -> field name
        # - computed_field_name -> computed field name
        # - index_reference -> index reference

        if len(tokens) == 1:
            # Simple case: single identifier/string/etc
            return tokens[0]
        elif len(tokens) == 3:
            # Complex case: identifier DOT field_path
            base_identifier = tokens[0]  # identifier
            # tokens[1] is DOT
            field_path = tokens[2]  # field_path (list of identifiers)

            # Build complete field chain: [base_identifier] + field_path
            all_fields = [base_identifier] + field_path
            return _ast.FieldAccessOperation(None, all_fields)
        else:
            # Fallback: return first token
            return tokens[0]

    def computed_field_name(self, tokens):
        """Transform computed_field_name ('expr') into ComputedFieldName AST node."""
        # tokens: [quote, expression, quote]
        _, expression, _ = tokens
        return _ast.ComputedFieldName(expression)

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



    # Structure handling
    def structure(self, tokens):
        """Transform structure rule into StructureLiteral AST node."""
        # Extract fields from the structure
        fields = []
        for token in tokens:
            if isinstance(token, _ast.ASTNode):
                fields.append(token)

        # Post-process to collect function arguments
        processed_fields = self._collect_function_arguments(fields)

        # Ensure all fields are StructureOperations
        structure_ops = self._ensure_structure_operations(processed_fields)
        return _ast.StructureLiteral(structure_ops)

    def block(self, tokens):
        """Transform block rule into BlockLiteral AST node."""
        # Extract fields from the block (same logic as structure but returns BlockLiteral)
        fields = []
        for token in tokens:
            if isinstance(token, _ast.ASTNode):
                fields.append(token)

        # Post-process to collect function arguments
        processed_fields = self._collect_function_arguments(fields)

        # Ensure all fields are StructureOperations
        structure_ops = self._ensure_structure_operations(processed_fields)
        return _ast.BlockLiteral(structure_ops)

    def block_literal(self, tokens):
        """Transform block_literal rule into BlockLiteral AST node."""
        # Extract fields from the block
        fields = []
        for token in tokens:
            if isinstance(token, _ast.ASTNode):
                fields.append(token)

        # Post-process to collect function arguments
        processed_fields = self._collect_function_arguments(fields)

        # Ensure all fields are StructureOperations
        structure_ops = self._ensure_structure_operations(processed_fields)
        return _ast.BlockLiteral(structure_ops)

    def named_block_literal(self, tokens):
        """Transform named_block_literal rule into StructureOperation with BlockLiteral."""
        # First token is the target identifier, rest are the block contents
        target = tokens[0]
        fields = tokens[1:]

        # Create the BlockLiteral from the fields
        block_fields = []
        for token in fields:
            if isinstance(token, _ast.ASTNode):
                block_fields.append(token)

        # Post-process to collect function arguments
        processed_fields = self._collect_function_arguments(block_fields)

        # Ensure all fields are StructureOperations
        structure_ops = self._ensure_structure_operations(processed_fields)
        block_literal = _ast.BlockLiteral(structure_ops)

        # Wrap in StructureOperation
        return _ast.StructureOperation(target, '=', block_literal)

    def _collect_function_arguments(self, fields):
        """Collect positional arguments for pipeline functions in structure operations."""
        if not fields:
            return fields

        processed = []
        i = 0

        while i < len(fields):
            field = fields[i]

            # Check if this is a positional field containing a pipeline with function call
            if (isinstance(field, _ast.StructureOperation) and
                field.target is None and
                field.operator == "=" and
                isinstance(field.expression, _ast.PipelineOperation)):

                pipeline = field.expression
                # Check if last stage is a PipelineFunctionOperation without arguments
                if (len(pipeline.stages) >= 2 and
                    isinstance(pipeline.stages[-1], _ast.PipelineFunctionOperation) and
                    pipeline.stages[-1].args is None):

                    # Collect subsequent positional fields as arguments
                    function_op = pipeline.stages[-1]
                    args = []
                    j = i + 1

                    # Collect following positional fields as arguments
                    while (j < len(fields) and
                           isinstance(fields[j], _ast.StructureOperation) and
                           fields[j].target is None and
                           fields[j].operator == "="):
                        args.append(fields[j].expression)
                        j += 1

                    # If we collected arguments, create a StructureLiteral to hold them
                    if args:
                        # Convert arguments to StructureOperations (positional fields)
                        arg_operations = []
                        for arg in args:
                            arg_op = _ast.StructureOperation(None, "=", arg)
                            arg_operations.append(arg_op)

                        # Create new StructureLiteral containing the arguments
                        args_struct = _ast.StructureLiteral(arg_operations)
                        function_op.args = args_struct
                        processed.append(field)  # Add the modified field
                        i = j  # Skip the collected arguments
                        continue

            # No argument collection needed, add field as-is
            processed.append(field)
            i += 1

        return processed

    def structure_field(self, tokens):
        """Transform structure_field rule."""
        return tokens[0]

    def named_field(self, tokens):
        """Transform named_field rule into NamedField AST node."""
        # tokens: [identifier, ASSIGN, expression]
        key = tokens[0]
        value = tokens[2]  # Skip the ASSIGN token
        return _ast.NamedField.fromToken([key, value])

    def assignment_field(self, tokens):
        """Transform assignment_field rule into StructureOperation AST node."""
        # tokens: [qualified_identifier, assignment_op, *expressions]

        # Convert the target to appropriate type for structure operations
        raw_target = tokens[0]
        operator = str(tokens[1])

        # Convert FieldAccessOperation to FieldTarget for structure contexts
        if isinstance(raw_target, _ast.FieldAccessOperation):
            if raw_target.object is None and len(raw_target.fields) == 1:
                # Simple field reference like "x" -> convert to FieldTarget
                field = raw_target.fields[0]
                if isinstance(field, _ast.Identifier):
                    target = _ast.FieldTarget(field.name)
                else:
                    # For more complex field types, keep the original structure
                    target = raw_target
            elif raw_target.object is None and len(raw_target.fields) > 1:
                # Dotted field reference like "x.y.z" -> convert to FieldTarget with path
                first_field = raw_target.fields[0]
                if isinstance(first_field, _ast.Identifier):
                    field_path = []
                    for field in raw_target.fields[1:]:
                        if isinstance(field, _ast.Identifier):
                            field_path.append(field.name)
                        else:
                            # Complex field path, keep original
                            target = raw_target
                            break
                    else:
                        target = _ast.FieldTarget(first_field.name, field_path)
                else:
                    target = raw_target
            else:
                target = raw_target
        else:
            target = raw_target

        if len(tokens) == 3:
            # Single expression - create StructureOperation directly
            expression = tokens[2]
            # Convert ShapeUnionOperation to PipelineOperation like AssignmentOperation does
            if isinstance(expression, _ast.ShapeUnionOperation):
                expression = _ast.PipelineOperation.fromValue(expression)
            return _ast.StructureOperation(target, operator, expression)
        else:
            # Multiple expressions - create a pipeline with arguments
            target = tokens[0]
            operator = str(tokens[1])
            expressions = tokens[2:]

            # If first expression is a pipeline and we have more expressions,
            # collect them as arguments
            if len(expressions) >= 2:
                first_expr = expressions[0]
                remaining_exprs = expressions[1:]

                # Check if first expression is a pipeline that can take arguments
                if isinstance(first_expr, _ast.PipelineOperation) and len(first_expr.stages) >= 2:
                    last_stage = first_expr.stages[-1]
                    if isinstance(last_stage, _ast.FieldAccessOperation) and last_stage.object is None:
                        # Convert the last FieldAccessOperation to PipelineFunctionOperation with args
                        field = last_stage.fields[0] if last_stage.fields else None
                        func_name = field.name if isinstance(field, _ast.Identifier) else "unknown"
                        function_ref = _ast.FunctionReference(func_name)

                        # Create arguments structure from remaining expressions
                        arg_operations = []
                        for expr in remaining_exprs:
                            arg_op = _ast.StructureOperation(None, "=", expr)
                            arg_operations.append(arg_op)

                        args_struct = _ast.StructureLiteral(arg_operations)
                        func_with_args = _ast.PipelineFunctionOperation(function_ref, args_struct)

                        # Create new pipeline with the function that has arguments
                        new_stages = first_expr.stages[:-1] + [func_with_args]
                        combined_pipeline = _ast.PipelineOperation(new_stages)

                        return _ast.StructureOperation(target, operator, combined_pipeline)

                # Fallback: create a shape union chain for post-processing to handle
                combined_expr = expressions[0]
                for expr in expressions[1:]:
                    combined_expr = _ast.ShapeUnionOperation(combined_expr, expr)

                return _ast.StructureOperation(target, operator, combined_expr)
            else:
                # Single additional expression - wrap in shape union for consistency
                expr = expressions[0]
                return _ast.StructureOperation(target, operator, expr)

    def qualified_identifier(self, tokens):
        """Transform qualified_identifier rule by returning the single target."""
        # tokens: [qualified_identifier] (either scope_identifier or field_identifier)
        return tokens[0]

    def scope_assignment(self, tokens):
        """Transform scope_assignment rule into StructureOperation AST node."""
        return _ast.StructureOperation.fromToken(tokens)

    def field_assignment(self, tokens):
        """Transform field_assignment rule into StructureOperation AST node."""
        # tokens: [field_identifier, assignment_op, *expressions]
        if len(tokens) == 3:
            # Single expression - use existing logic
            return _ast.StructureOperation.fromToken(tokens)
        else:
            # Multiple expressions - create a pipeline with arguments
            target = tokens[0]
            operator = str(tokens[1])
            expressions = tokens[2:]

            # If first expression is a pipeline and we have more expressions,
            # collect them as arguments
            if len(expressions) >= 2:
                first_expr = expressions[0]
                remaining_exprs = expressions[1:]

                # Check if first expression is a pipeline that can take arguments
                if isinstance(first_expr, _ast.PipelineOperation) and len(first_expr.stages) >= 2:
                    last_stage = first_expr.stages[-1]
                    if isinstance(last_stage, _ast.FieldAccessOperation) and last_stage.object is None:
                        # Convert the last FieldAccessOperation to PipelineFunctionOperation with args
                        field = last_stage.fields[0] if last_stage.fields else None
                        func_name = field.name if isinstance(field, _ast.Identifier) else "unknown"
                        function_ref = _ast.FunctionReference(func_name)

                        # Create arguments structure from remaining expressions
                        arg_operations = []
                        for expr in remaining_exprs:
                            arg_op = _ast.StructureOperation(None, "=", expr)
                            arg_operations.append(arg_op)

                        args_struct = _ast.StructureLiteral(arg_operations)
                        func_with_args = _ast.PipelineFunctionOperation(function_ref, args_struct)

                        # Create new pipeline with the function that has arguments
                        new_stages = first_expr.stages[:-1] + [func_with_args]
                        combined_pipeline = _ast.PipelineOperation(new_stages)

                        return _ast.StructureOperation(target, operator, combined_pipeline)

                # Fallback: create a shape union chain for post-processing to handle
                combined_expr = expressions[0]
                for expr in expressions[1:]:
                    combined_expr = _ast.ShapeUnionOperation(combined_expr, expr)

                return _ast.StructureOperation(target, operator, combined_expr)
            else:
                # Single expression case (shouldn't happen with + in grammar, but safety)
                return _ast.StructureOperation(target, operator, expressions[0])

    def spread_operation(self, tokens):
        """Transform spread_operation rule into StructureOperation AST node."""
        # tokens: [SPREAD, expression]
        target = _ast.SpreadTarget.fromToken([])  # Use fromToken for consistency
        operator = ".."  # Spread operator
        expression = tokens[1]  # Skip the SPREAD token
        return _ast.StructureOperation.fromToken([target, operator, expression])

    def scope_identifier(self, tokens):
        """Transform scope_identifier rule into FieldAccessOperation AST node."""
        # tokens: [scope_symbol, field_reference] or [scope_symbol, identifier] or [scope_symbol]
        scope_symbol = tokens[0]

        if len(tokens) == 1:
            # Bare scope like @ or ^
            return _ast.FieldAccessOperation(_ast.Scope(str(scope_symbol)))

        # Check if this is a DOLLAR identifier case (special handling)
        if str(scope_symbol) == "$":
            if len(tokens) == 2:
                # DOLLAR identifier case: $mod, $out, etc.
                identifier = tokens[1]
                if hasattr(identifier, 'name'):
                    scope_name = f"${identifier.name}"
                else:
                    scope_name = f"${identifier}"
                return _ast.FieldAccessOperation(_ast.Scope(scope_name))
            elif len(tokens) == 4:
                # DOLLAR identifier DOT field_reference case: $mod.export.field
                identifier = tokens[1]
                # tokens[2] is DOT
                field_ref = tokens[3]

                # Create scope with $identifier format
                if hasattr(identifier, 'name'):
                    scope_name = f"${identifier.name}"
                else:
                    scope_name = f"${identifier}"
                scope_obj = _ast.Scope(scope_name)

                # Handle field_reference
                if isinstance(field_ref, _ast.FieldAccessOperation):
                    return _ast.FieldAccessOperation(scope_obj, *field_ref.fields)
                else:
                    return _ast.FieldAccessOperation(scope_obj, field_ref)

        # Has field_reference (complex case)
        field_ref = tokens[1]

        # Create scope object
        scope_obj = _ast.Scope(str(scope_symbol))

        # If field_ref is already a FieldAccessOperation, extract its fields
        if isinstance(field_ref, _ast.FieldAccessOperation):
            # Combine scope with the field access chain
            return _ast.FieldAccessOperation(scope_obj, *field_ref.fields)
        else:
            # Simple field reference
            return _ast.FieldAccessOperation(scope_obj, field_ref)

    def field_identifier(self, tokens):
        """Transform field_identifier rule into FieldAccessOperation AST node."""
        # tokens: [field_reference]
        field_ref = tokens[0]

        # If field_ref is already a FieldAccessOperation, return it as-is
        if isinstance(field_ref, _ast.FieldAccessOperation):
            return field_ref
        else:
            # Simple field reference - wrap in FieldAccessOperation
            return _ast.FieldAccessOperation(None, field_ref)

    def field_path(self, tokens):
        """Transform field_path rule into list of field identifiers."""
        # tokens: identifier (DOT identifier)*
        # Keep identifiers as AST nodes, not strings
        path = []
        for token in tokens:
            if isinstance(token, _ast.Identifier):
                path.append(token)  # Keep as Identifier node
            elif hasattr(token, "type") and token.type == "DOT":
                # Skip DOT tokens
                continue
            elif hasattr(token, "value"):
                # Convert other token types to Identifiers
                path.append(_ast.Identifier(token.value))
            else:
                # Convert string tokens to Identifiers
                path.append(_ast.Identifier(str(token)))
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
        # Wrap it in a FieldAccessOperation with None object and IndexReference in fields
        return _ast.FieldAccessOperation(None, index_ref)

    def placeholder(self, tokens):
        """Transform placeholder rule into Placeholder AST node."""
        return _ast.Placeholder.fromToken(tokens)

    def array_type(self, tokens):
        """Transform array_type rule into ArrayType AST node."""
        return _ast.ArrayType.fromToken(tokens)

    def field_name(self, tokens):
        """Transform field_name rule into FieldName AST node."""
        return _ast.FieldName.fromToken(tokens)
