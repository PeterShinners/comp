"""Parser for converting Lark parse trees to engine AST nodes.

This parser is designed for the engine's AST nodes which require:
- Children to be converted before parent nodes are created
- More runtime-focused node structure vs grammar structure
"""

__all__ = ["parse_module", "parse_expr", "parse_shape"]

import decimal
import pathlib

import lark

import comp

# Global parser instances (cached by start rule)
_parsers: dict[str, lark.Lark] = {}

# Current filename being parsed (for position tracking)
_current_filename: str | None = None


def parse_module(text, filename=None):
    """Parse a complete Comp module.

    Args:
        text: Module source code
        filename: Optional source filename for error messages and debugging

    Returns:
        Module AST node containing all module statements

    Raises:
        comp.ParseError: If the text contains invalid syntax
    """
    global _current_filename
    _current_filename = filename
    try:
        parser = _get_parser("module")
        tree = parser.parse(text)
        ops = _convert_children(tree.children)
        return comp.ast.Module(ops)
    except lark.exceptions.LarkError as e:
        error_msg = str(e)
        # Improve error messages for common cases
        if "DUBQUOTE" in error_msg and "$END" in error_msg:
            error_msg = "Unterminated string literal"
        raise comp.ParseError(error_msg) from e
    finally:
        _current_filename = None


def parse_expr(text, filename=None):
    """Parse a single Comp expression.

    Args:
        text: Expression source code
        filename: Optional source filename for error messages and debugging

    Returns:
        The expression AST node

    Raises:
        comp.ParseError: If the text contains invalid syntax
    """
    global _current_filename
    _current_filename = filename
    try:
        parser = _get_parser("expression_start")
        tree = parser.parse(text)
        # expression_start has one child: the actual expression
        if tree.children:
            result = _convert_tree(tree.children[0])
            return result
        return None
    except lark.exceptions.LarkError as e:
        error_msg = str(e)
        # Improve error messages for common cases
        if "DUBQUOTE" in error_msg and "$END" in error_msg:
            error_msg = "Unterminated string literal"
        raise comp.ParseError(error_msg) from e
    finally:
        _current_filename = None


def parse_shape(text, module=None, filename=None):
    """Parse a shape expression and return a ShapeDefinition.

    This is useful for defining shapes programmatically (e.g., in builtin functions)
    without needing to manually construct ShapeField objects.

    Args:
        text: Shape expression, e.g., "~{count~num=2}" or "~num"
        module: Module to use for shape/tag lookups (default: builtin module)
        filename: Optional source filename for error messages

    Returns:
        ShapeDefinition: The evaluated shape definition

    Raises:
        comp.ParseError: If the text contains invalid syntax
        ValueError: If the shape cannot be evaluated

    Examples:
        >>> parse_shape("~num")  # Returns num shape from builtin
        >>> parse_shape("~{x~num y~num}")  # Returns inline shape with two fields
        >>> parse_shape("~{count~num=0}")  # Field with default value
    """
    global _current_filename
    _current_filename = filename
    try:
        # Parse using shape_type grammar rule
        parser = _get_parser("shape_type")
        tree = parser.parse(text)

        # Convert the parse tree to AST
        if tree.children:
            shape_ast = _convert_tree(tree.children[0])
        else:
            raise ValueError(f"Empty shape expression: {text!r}")
    except lark.exceptions.LarkError as e:
        error_msg = str(e)
        if "DUBQUOTE" in error_msg and "$END" in error_msg:
            error_msg = "Unterminated string literal"
        raise comp.ParseError(error_msg) from e
    finally:
        _current_filename = None

    # Get or create module for evaluation context
    if module is None:
        module = comp.builtin.get_builtin_module()

    # Create engine and evaluate the shape AST
    engine = comp.Engine()
    try:
        result = engine.run(shape_ast, module=module)
    except Exception as e:
        raise ValueError(f"Failed to evaluate shape {text!r}: {e}") from e

    # The result should be a ShapeDefinition or HandleDefinition
    if not isinstance(result, (comp.ShapeDefinition, comp.HandleDefinition)):
        raise ValueError(
            f"Shape expression {text!r} did not evaluate to ShapeDefinition or HandleDefinition, "
            f"got {type(result).__name__}"
        )

    return result


def _convert_tree(tree):
    """Convert a single Lark tree/token to an AST node.

    This is the main dispatcher that handles all grammar rules.
    Children are converted before the parent node is created.

    Args:
        tree: Lark Tree or Token to convert

    Returns:
        AST node instance
    """
    # Handle tokens (terminals)
    if isinstance(tree, lark.Token):
        match tree.type:
            case 'NUMBER' | 'INTBASE' | 'decimal.DECIMAL':
                return _convert_number(tree)
            case 'TOKEN':
                return tree.value
            case 'INDEXFIELD':
                # Extract number from #123 format
                return int(tree.value[1:])
            case _:
                # Most tokens are just passed as strings
                return tree.value

    # Handle trees (non-terminals)
    assert isinstance(tree, lark.Tree)
    kids = tree.children

    match tree.data:
        # Pass-through rules (no node created, just process children)
        case 'start' | 'module' | 'expression_start':
            if kids:
                return _convert_tree(kids[0]) if len(kids) == 1 else _convert_children(kids)
            return []

        case 'paren_expr':
            # LPAREN expression RPAREN - return the expression
            return _convert_tree(kids[1])

        # === NUMBER LITERALS ===
        case 'number':
            node = comp.ast.Number(_convert_number(kids[0]))
            return _apply_position(node, tree)

        # === STRING LITERALS ===
        case 'string' | '_short_string' | '_long_string':
            node = comp.ast.String(_convert_string(kids))
            return _apply_position(node, tree)

        # === PLACEHOLDER ===
        case 'placeholder':
            node = comp.ast.Placeholder()
            return _apply_position(node, tree)

        # === IDENTIFIERS ===
        case 'identifier':
            fields = _convert_identifier_fields(kids)
            # Always create an Identifier node - no conversion here
            node = comp.ast.Identifier(fields)
            return _apply_position(node, tree)
        
        case 'atom_identifier':
            # In atom context: convert simple tokens to string literals
            # This enables: {USERNAME USER LOGNAME} → {"USERNAME" "USER" "LOGNAME"}
            # But preserves: $var.name, foo.bar, #(expr) as identifiers
            identifier = _convert_tree(kids[0])  # kids[0] is the identifier
            
            # Check if it's a simple single-token identifier (no dots, no scope)
            if (isinstance(identifier, comp.ast.Identifier) and
                len(identifier.fields) == 1 and
                isinstance(identifier.fields[0], comp.ast.TokenField)):
                # Convert: foo → "foo"
                node = comp.ast.String(identifier.fields[0].name)
                return _apply_position(node, tree)
            
            # Otherwise keep as identifier: $var.name, foo.bar, #(expr), etc.
            return identifier

        case 'tokenfield':
            node = comp.ast.TokenField(_convert_tree(kids[0]))
            return _apply_position(node, tree)

        case 'indexfield':
            # Can be either: INDEXFIELD token (#0, #1, etc) or "#" "(" expression ")"
            if len(kids) == 1 and isinstance(kids[0], lark.Token) and kids[0].type == 'INDEXFIELD':
                # Literal index like #0, #1
                index = int(kids[0].value[1:])  # Strip the # prefix
                return comp.ast.IndexField(index)
            else:
                # Expression form: # ( expression )
                # kids should be: [Token("#"), Token("("), expression_tree, Token(")")]
                # Expression is at index 2
                expr = _convert_tree(kids[2])
                return comp.ast.IndexField(expr)

        case 'stringfield':
            # String used as a field - convert the string content
            string_content = _convert_string(kids[0].children)
            return comp.ast.TokenField(string_content)

        case 'computefield':
            # "'" expression "'" - extract the expression (middle child)
            expr = _convert_tree(kids[1])
            return comp.ast.ComputeField(expr)

        case 'privatefield':
            # AMPERSAND - just & (switches to private data context)
            return comp.ast.PrivateField()

        case 'scope':
            # "$" TOKEN - extract the scope name
            scope_name = kids[1].value if len(kids) > 1 else "unknown"
            return comp.ast.ScopeField(scope_name)

        # === REFERENCES ===
        case 'tag_reference':
            # "#" _reference_path
            path, namespace = _extract_reference_path(kids)
            node = comp.ast.TagValueRef(path, namespace)
            return _apply_position(node, tree)

        case 'handle_reference':
            # "@" _reference_path
            path, namespace = _extract_reference_path(kids)
            node = comp.ast.HandleValueRef(path, namespace)
            return _apply_position(node, tree)

        case 'shape_reference':
            # "~" _reference_path
            # Shape references are used in: function shapes, arg shapes, field types, morph/mask operations
            path, namespace = _extract_reference_path(kids)
            node = comp.ast.ShapeRef(path, namespace)
            return _apply_position(node, tree)

        case 'function_reference' | '_function_piped':
            # "|" _reference_path - Function references aren't valid as standalone values
            # They can only be used in pipeline operations
            raise comp.ParseError("Function reference cannot be used as a standalone value")

        # === OPERATORS ===
        case 'binary_op':
            left = _convert_tree(kids[0])
            op = _extract_operator(kids[1])
            right = _convert_tree(kids[2])
            return _create_binary_op(op, left, right)

        case 'unary_op':
            op = _extract_operator(kids[0])
            operand = _convert_tree(kids[1])
            return _create_unary_op(op, operand)

        case 'atom_fallback':
            # atom_in_expr FALLBACK expression
            left = _convert_tree(kids[0])
            right = _convert_tree(kids[2])
            return comp.ast.FallbackOp(left, right)

        # === MORPH OPERATORS ===
        case 'morph_op':
            expr = _convert_tree(kids[0])
            # kids[1] is TILDE/WEAK_MORPH token, kids[2] is reference_identifiers or morph_type
            shape = _convert_tree(kids[2])
            return comp.ast.MorphOp(expr, shape, mode="normal")

        case 'strong_morph_op':
            expr = _convert_tree(kids[0])
            shape = _convert_tree(kids[2])
            return comp.ast.MorphOp(expr, shape, mode="strong")

        case 'weak_morph_op':
            expr = _convert_tree(kids[0])
            shape = _convert_tree(kids[2])
            return comp.ast.MorphOp(expr, shape, mode="weak")

        # === HANDLE OPERATIONS ===
        case 'grab_atom':
            # "!grab" handle_reference
            handle_ref = _convert_tree(kids[1])
            node = comp.ast.GrabOp(handle_ref)
            return _apply_position(node, tree)

        case 'drop_op':
            # "!drop" _qualified
            target = _convert_tree(kids[1])
            node = comp.ast.DropOp(target)
            return _apply_position(node, tree)

        case 'reference_identifiers':
            # Simple dotted identifier path (e.g., "num" or "http.request")
            # Used in morph operations for shape references
            # Collect all TOKEN children
            path = []
            for kid in kids:
                if isinstance(kid, lark.Token) and kid.type == 'TOKEN':
                    path.append(kid.value)
            # Return as ShapeRef with natural path order
            return comp.ast.ShapeRef(path)

        # === STRUCTURES ===
        case 'structure':
            # LBRACE structure_op* RBRACE
            # Filter out the braces (tokens) and convert the structure_op children
            ops = [_convert_tree(kid) for kid in kids if isinstance(kid, lark.Tree)]
            return comp.ast.Structure(ops)

        case 'block_structure':
            # COLON_BLOCK_START structure_op* RBRACE
            # Similar to structure, but creates a Block node for deferred execution
            ops = [_convert_tree(kid) for kid in kids if isinstance(kid, lark.Tree)]
            structure = comp.ast.Structure(ops)
            return comp.ast.Block(structure)
        
        case 'block_pipeline':
            # COLON_PIPELINE_BLOCK pipeline RBRACKET
            # Shorthand for :[pipeline] which desugars to :{[pipeline]}
            # A block containing a single unnamed pipeline expression
            # kids[0] is the pipeline Tree, filter out tokens (COLON_PIPELINE_BLOCK, RBRACKET)
            pipeline_tree = [kid for kid in kids if isinstance(kid, lark.Tree)][0]
            pipeline = _convert_tree(pipeline_tree)
            structure = comp.ast.Structure([comp.ast.FieldOp(pipeline, None)])
            return comp.ast.Block(structure)

        case 'structure_assign':
            # _qualified _assignment_op expression
            # For field assignments, convert identifier to String (simple) or list of Strings (deep path)
            key = _convert_field_assignment_key(kids[0])
            # Skip assignment operator (kids[1])
            value = _convert_tree(kids[2])
            return comp.ast.FieldOp(value, key)

        case 'structure_unnamed':
            # expression
            value = _convert_tree(kids[0])
            return comp.ast.FieldOp(value, None)

        case 'structure_spread':
            # SPREAD expression
            expr = _convert_tree(kids[1])
            return comp.ast.SpreadOp(expr)

        # === PIPELINES ===
        case 'pipeline_seeded':
            # LBRACKET _prepipeline_expression pipeline RBRACKET
            seed = _convert_tree(kids[1])
            ops = _convert_children(kids[2].children)
            node = comp.ast.Pipeline(seed, ops)
            return _apply_position(node, tree)

        case 'pipeline_unseeded':
            # LBRACKET pipeline RBRACKET
            ops = _convert_children(kids[1].children)
            node = comp.ast.Pipeline(None, ops)
            return _apply_position(node, tree)

        case 'pipe_func':
            # function_reference function_arguments
            # Extract the function path directly without converting (function_reference isn't a value node)
            func_path, func_namespace = _extract_reference_path(kids[0].children)
            func_name = ".".join(func_path)
            # function_arguments contains structure_op* - convert to Structure if non-empty
            if len(kids) > 1 and kids[1].children:
                ops = [_convert_tree(op) for op in kids[1].children]
                args = comp.ast.Structure(ops)
            else:
                args = None
            node = comp.ast.PipeFunc(func_name, args, func_namespace)
            return _apply_position(node, tree)

        case 'pipe_struct':
            # PIPE_STRUCT structure_op* RBRACE
            ops = _convert_children(kids[1:-1])  # Skip PIPE_STRUCT and RBRACE
            struct = comp.ast.Structure(ops)
            return comp.ast.PipeStruct(struct)

        case 'pipe_block':
            # PIPE_BLOCK _qualified
            block_ref = _convert_tree(kids[1])
            return comp.ast.PipeBlock(block_ref)

        case 'pipe_fallback':
            # PIPE_FALLBACK expression
            fallback = _convert_tree(kids[1])
            return comp.ast.PipeFallback(fallback)

        # === SHAPE DEFINITIONS ===
        case 'shape_definition':
            # BANG_SHAPE shape_path ASSIGN shape_body
            path, is_private = _extract_path_and_privacy_from_tree(kids[1])
            fields_or_type = _convert_shape_body(kids[3])
            
            # If fields_or_type is a single shape type (not a list), wrap it as a positional field
            # This handles type aliases like: !shape ~alias = ~other or !shape ~nil-block = ~:{}
            if not isinstance(fields_or_type, list):
                # Create a ShapeFieldDef with no name (positional) and the type as the shape_ref
                fields = [comp.ast.ShapeFieldDef(name=None, shape_ref=fields_or_type, default=None)]
            else:
                fields = fields_or_type
            
            return comp.ast.ShapeDef(path, fields, is_private=is_private)

        case 'shape_field_def':
            # TOKEN QUESTION? shape_type? (ASSIGN expression)?
            name = None
            shape_ref = None
            default = None
            optional = False

            i = 0
            if i < len(kids) and isinstance(kids[i], lark.Token) and kids[i].type == 'TOKEN':
                name = kids[i].value
                i += 1

            if i < len(kids) and isinstance(kids[i], lark.Token) and kids[i].type == 'QUESTION':
                optional = True
                i += 1

            # Look for shape_type (could be various shape-related rules)
            if i < len(kids) and isinstance(kids[i], lark.Tree):
                if kids[i].data in ('shape_type', 'shape_type_atom', 'shape_reference',
                                   'tag_reference', 'shape_inline', 'shape_union'):
                    shape_ref = _convert_tree(kids[i])
                    i += 1

            # Look for ASSIGN token and default value
            if i < len(kids) and isinstance(kids[i], lark.Token) and kids[i].type == 'ASSIGN':
                i += 1
                if i < len(kids):
                    default = _convert_tree(kids[i])

            return comp.ast.ShapeFieldDef(name, shape_ref, default, optional)

        case 'shape_spread':
            # SPREAD shape_type
            # For now, we'll handle spreads as a special kind of field
            # The actual spread expansion happens at runtime
            shape = _convert_tree(kids[1])
            return comp.ast.ShapeFieldDef(None, shape, None, is_spread=True)  # Spread field

        case 'shape_reference':
            # Already handled above, but repeated for completeness
            path, namespace = _extract_reference_path(kids)
            return comp.ast.ShapeRef(path, namespace)

        case 'shape_inline':
            # TILDE LBRACE shape_field* RBRACE
            # Empty inline shape ~{} matches only empty structs (equivalent to ~nil)
            # Non-empty inline shapes define expected struct fields
            fields = _convert_children(kids[2:-1]) if len(kids) > 3 else []  # Skip TILDE, LBRACE, RBRACE
            if not fields:
                # Empty shape ~{} - equivalent to ~nil (matches only empty structs)
                return comp.ast.ShapeRef(["nil"])
            # Non-empty inline shape - create InlineShape node
            return comp.ast.InlineShape(fields)

        case 'shape_block':
            # TILDE COLON_BLOCK_START shape_field* RBRACE
            # Represents a block type ~:{input-shape}
            # The fields describe the input structure the block expects
            fields = _convert_children(kids[2:-1]) if len(kids) > 3 else []  # Skip TILDE, COLON_BLOCK_START, RBRACE
            # Create a BlockShape node to represent this type
            return comp.ast.BlockShape(fields)

        case 'morph_inline':
            # LBRACE shape_field* RBRACE (no tilde)
            # For morph operations with inline shape
            fields = _convert_children(kids[1:-1]) if len(kids) > 2 else []  # Skip LBRACE, RBRACE
            if not fields:
                # Empty shape {} in morph context
                return comp.ast.ShapeRef(["any"])
            # Create InlineShape for morphing with inline shape definition
            return comp.ast.InlineShape(fields)

        case 'morph_block':
            # ":" LBRACE shape_field* RBRACE (no tilde)
            # For morph operations with inline block shape
            # Example: $var ~:{name~str age~num} or $var~:{name~str age~num}
            fields = _convert_children(kids[2:-1]) if len(kids) > 3 else []  # Skip ":", LBRACE, RBRACE
            # Create a BlockShape node to represent this type
            return comp.ast.BlockShape(fields)

        case 'shape_union':
            # shape_type_atom (PIPE shape_type_atom)+
            # Need to convert tag_reference to TagShape
            members = []
            for kid in kids:
                if isinstance(kid, lark.Tree):
                    # Check if this is a tag_reference that needs converting
                    if kid.data == 'tag_reference':
                        path, namespace = _extract_reference_path(kid.children)
                        node = comp.ast.TagShape(path, namespace)
                        members.append(_apply_position(node, kid))
                    else:
                        members.append(_convert_tree(kid))
            return comp.ast.ShapeUnion(members)

        case 'morph_union':
            # morph_type_base (PIPE morph_type_base)+
            # Same as shape_union but in morph context
            # Need to convert tag_reference to TagShape
            members = []
            for kid in kids:
                if isinstance(kid, lark.Tree):
                    # Check if this is a tag_reference that needs converting
                    if kid.data == 'tag_reference':
                        path, namespace = _extract_reference_path(kid.children)
                        node = comp.ast.TagShape(path, namespace)
                        members.append(_apply_position(node, kid))
                    else:
                        members.append(_convert_tree(kid))
            return comp.ast.ShapeUnion(members)

        # Pass-through for shape type wrappers
        case 'shape_type_atom' | 'morph_type_base':
            # Special handling: if child is a tag_reference, convert to TagShape
            if len(kids) == 1 and isinstance(kids[0], lark.Tree) and kids[0].data == 'tag_reference':
                # Extract path and namespace from tag_reference
                path, namespace = _extract_reference_path(kids[0].children)
                node = comp.ast.TagShape(path, namespace)
                return _apply_position(node, kids[0])
            # Special handling: if child is a handle_reference, convert to HandleShape
            if len(kids) == 1 and isinstance(kids[0], lark.Tree) and kids[0].data == 'handle_reference':
                # Extract path and namespace from handle_reference
                path, namespace = _extract_reference_path(kids[0].children)
                node = comp.ast.HandleShape(path, namespace)
                return _apply_position(node, kids[0])
            # Otherwise pass through
            if len(kids) == 1:
                return _convert_tree(kids[0])
            return _convert_children(kids)

        case 'shape_type' | 'shape_body' | 'morph_type':
            if len(kids) == 1:
                return _convert_tree(kids[0])
            # Multiple children means union or complex structure
            return _convert_children(kids)

        # === TAG DEFINITIONS ===
        case 'tag_definition' | 'tag_simple' | 'tag_extends_body' | 'tag_extends_simple' | 'tag_gen_val_body' | 'tag_gen_val' | 'tag_gen_body' | 'tag_val_body' | 'tag_val' | 'tag_body_only':
            return _convert_tag_definition(kids)

        case 'tag_child' | 'tagchild_simple' | 'tagchild_val_body' | 'tagchild_val' | 'tagchild_body':
            return _convert_tag_child(kids)

        # === HANDLE DEFINITIONS ===
        case 'handle_definition' | 'handle_simple':
            return _convert_handle_definition(kids)

        # === FUNCTION DEFINITIONS ===
        case 'function_definition' | 'func_with_args' | 'func_no_args':
            return _convert_function_definition(tree)

        # === MAIN AND ENTRY DEFINITIONS ===
        case 'main_definition':
            return _convert_main_definition(kids)

        case 'entry_definition':
            return _convert_entry_definition(kids)

        # === DOCUMENTATION STATEMENTS ===
        case 'doc_general' | 'doc_impl' | 'doc_module':
            return _convert_doc_statement(tree)

        # === IMPORT STATEMENTS ===
        case 'import_statement':
            return _convert_import_statement(kids)

        # === MODULE ASSIGNMENTS ===
        case 'module_assign':
            return _convert_module_assign(kids)

        # === PASS-THROUGH / UNWRAP ===
        case ('tag_value' | 'tag_arithmetic' | 'tag_term' | 'tag_bitwise' |
              'tag_comparison' | 'tag_unary' | 'tag_atom' | 'module_value' |
              'or_expr' | 'and_expr' | 'not_expr' | 'comparison' |
              'morph_expr' | 'arith_expr' | 'term' | 'unary' | 'power' |
              'atom_in_expr' | '_prepipeline_expression' | 'pipeline' |
              'function_arguments' | '_structure_content'):
            # These are just precedence/grouping rules - pass through
            if len(kids) == 1:
                return _convert_tree(kids[0])
            # If multiple children, it's an operator that should have been caught above
            return _convert_children(kids)

        case 'atom_field':
            # atom_in_expr "." identifier_next_field
            # This is a field access on an expression result
            # Recursively flatten: [base, field1, field2, ...]
            fields = []
            current = tree
            while current.data == 'atom_field':
                # Last child is the field
                field_tree = current.children[-1]
                field = _convert_identifier_next_field(field_tree)
                fields.append(field)
                current = current.children[0]

            # Current is now the base atom - convert it
            base_fields = []
            if current.data == 'identifier':
                # Base is already an identifier, extract its fields
                base_id = _convert_tree(current)
                base_fields = base_id.fields
            else:
                # Base is another expression - we need to treat this differently
                # For now, just return the base and field access
                # TODO: Handle this case properly
                base = _convert_tree(current)
                return base

            # Combine base fields with additional fields
            fields.reverse()
            all_fields = base_fields + fields
            return comp.ast.Identifier(all_fields)

        case _:
            raise ValueError(f"Unhandled grammar rule: {tree.data}")


def _convert_children(children):
    """Convert a list of Lark trees/tokens to AST nodes."""
    result = []
    for child in children:
        if isinstance(child, lark.Token):
            # Skip most tokens (they're handled in parent rules)
            continue
        converted = _convert_tree(child)
        if converted is not None:
            if isinstance(converted, list):
                result.extend(converted)
            else:
                result.append(converted)
    return result


def _apply_position(node, tree):
    """Apply source position information from Lark tree/token to AST node.
    
    Args:
        node: AST node to annotate with position
        tree: Lark tree or token containing position metadata
        
    Returns:
        The node (modified in place for convenience)
    """
    if isinstance(tree, lark.Tree) and hasattr(tree, 'meta'):
        meta = tree.meta
        node.position = comp.ast.SourcePosition(
            filename=_current_filename,
            start_line=getattr(meta, 'line', None),
            start_column=getattr(meta, 'column', None),
            end_line=getattr(meta, 'end_line', None),
            end_column=getattr(meta, 'end_column', None),
        )
    elif isinstance(tree, lark.Token):
        node.position = comp.ast.SourcePosition(
            filename=_current_filename,
            start_line=getattr(tree, 'line', None),
            start_column=getattr(tree, 'column', None),
            end_line=getattr(tree, 'end_line', None),
            end_column=getattr(tree, 'end_column', None),
        )
    return node


def _convert_number(token):
    """Convert a number token to decimal.Decimal."""
    value_str = token.value.replace('_', '')  # Remove underscores

    if value_str.startswith(('0x', '0X')):
        # Hexadecimal
        return decimal.Decimal(int(value_str, 16))
    elif value_str.startswith(('0b', '0B')):
        # Binary
        return decimal.Decimal(int(value_str, 2))
    elif value_str.startswith(('0o', '0O')):
        # Octal
        return decimal.Decimal(int(value_str, 8))
    else:
        # decimal.Decimal (including scientific notation)
        return decimal.Decimal(value_str)


def _convert_string(kids):
    """Extract string content from string children."""
    # Find the content token
    for kid in kids:
        if isinstance(kid, lark.Token):
            if kid.type in ('SHORT_STRING_CONTENT', 'LONG_STRING_CONTENT'):
                # Unescape the string content
                content = kid.value
                # Basic unescaping (can be expanded)
                content = content.replace('\\n', '\n')
                content = content.replace('\\t', '\t')
                content = content.replace('\\r', '\r')
                content = content.replace('\\"', '"')
                content = content.replace('\\\\', '\\')
                return content
    return ""


def _convert_identifier_fields(kids):
    """Convert identifier children to field nodes.
    
    When an AMPERSAND token is found, insert a PrivateField node before the next field.
    """
    fields = []
    for kid in kids:
        if isinstance(kid, lark.Token):
            if kid.type == 'TOKEN':
                fields.append(comp.ast.TokenField(kid.value))
            elif kid.type == 'INDEXFIELD':
                index = int(kid.value[1:])  # Remove '#'
                fields.append(comp.ast.IndexField(index))
            elif kid.type == 'AMPERSAND':
                # Insert a PrivateField node - the next field will follow
                fields.append(comp.ast.PrivateField())
            # Skip dots and other tokens
        else:
            # Tree node
            field = _convert_tree(kid)
            if field is not None:
                fields.append(field)
    return fields


def _convert_identifier_next_field(tree):
    """Convert an identifier_next_field to a field node."""
    if isinstance(tree, lark.Token):
        if tree.type == 'TOKEN':
            return comp.ast.TokenField(tree.value)
        elif tree.type == 'INDEXFIELD':
            return comp.ast.IndexField(int(tree.value[1:]))
    else:
        # Tree - could be string, computefield, etc.
        return _convert_tree(tree)


def _convert_field_assignment_key(tree):
    """Convert identifier to field assignment key.

    For simple identifiers like 'x', returns comp.ast.String("x").
    For scope identifiers like '@name', returns comp.ast.ScopeField("@") followed by fields.
    For deep paths like 'one.two.three', returns [comp.ast.String("one"), comp.ast.String("two"), comp.ast.String("three")].
    For complex fields (index, compute, string), returns appropriate list.
    """
    # The tree should be an identifier
    if not isinstance(tree, lark.Tree) or tree.data != 'identifier':
        # Fallback to regular conversion
        return _convert_tree(tree)

    # Check for scope markers first (scope only)
    scope_marker = None
    if tree.children and isinstance(tree.children[0], lark.Tree):
        first_child = tree.children[0]
        if first_child.data == 'scope':
            # $name format - extract just the name without $
            if len(first_child.children) > 1 and isinstance(first_child.children[1], lark.Token):
                scope_marker = first_child.children[1].value  # Just the name, not $name

    # Extract field keys from the identifier (skipping scope marker node)
    field_keys = []
    skip_first = scope_marker is not None  # Skip the scope marker node itself

    for kid in tree.children:
        # Skip the scope marker node
        if skip_first and isinstance(kid, lark.Tree) and kid.data == 'scope':
            skip_first = False
            continue

        if isinstance(kid, lark.Token):
            if kid.type == 'TOKEN':
                field_keys.append(comp.ast.TokenField(kid.value))
            elif kid.type == 'INDEXFIELD':
                index = int(kid.value[1:])  # Remove '#'
                field_keys.append(comp.ast.IndexField(index))
            elif kid.type == 'AMPERSAND':
                # & separator - insert PrivateField
                field_keys.append(comp.ast.PrivateField())
            # Skip dots
        elif isinstance(kid, lark.Tree):
            # Process tree nodes
            if kid.data == 'tokenfield':
                # tokenfield contains a TOKEN - extract it as a TokenField
                token = kid.children[0]
                if isinstance(token, lark.Token) and token.type == 'TOKEN':
                    field_keys.append(comp.ast.TokenField(token.value))
            elif kid.data == 'indexfield':
                # indexfield contains an integer - convert to IndexField
                index_node = _convert_tree(kid.children[0])
                if isinstance(index_node, comp.ast.Number):
                    field_keys.append(comp.ast.IndexField(int(index_node.value)))
                else:
                    field_keys.append(comp.ast.IndexField(index_node))
            elif kid.data == 'stringfield':
                # stringfield is a string used as field name
                string_content = _convert_string(kid.children[0].children)
                field_keys.append(comp.ast.String(string_content))
            elif kid.data == 'computefield':
                # computefield is an expression - keep as ComputeField
                expr = _convert_tree(kid.children[1])
                field_keys.append(comp.ast.ComputeField(expr))
            elif kid.data == 'privatefield':
                # privatefield is &  - keep as PrivateField
                field_keys.append(comp.ast.PrivateField())
            # Skip other nodes

    # If we have a scope marker, prepend it as a ScopeField and return a list
    # (scope assignments are handled specially by FieldOp and expect a list)
    if scope_marker:
        field_keys.insert(0, comp.ast.ScopeField(scope_marker))
        return field_keys

    # For simple single-token identifiers (e.g., name = value) return an
    # Identifier node rather than a plain list or String. The evaluator will
    # treat Identifier keys specially when performing assignments.
    if len(field_keys) == 1 and isinstance(field_keys[0], comp.ast.TokenField):
        return comp.ast.Identifier([field_keys[0]])

    # Fallback: return the list of field nodes for deep paths or complex keys
    return field_keys


def _extract_reference_path(kids):
    """Extract path and namespace from reference children.

    Returns:
        (path, namespace) where path is list of strings, namespace is optional str or ValueNode
    """
    path = []
    namespace = None

    for kid in kids:
        if isinstance(kid, lark.Token):
            if kid.type == 'TOKEN':
                path.append(kid.value)
        elif isinstance(kid, lark.Tree):
            if kid.data == 'reference_identifiers':
                # Extract tokens (skip dots)
                for child in kid.children:
                    if isinstance(child, lark.Token) and child.type == 'TOKEN':
                        path.append(child.value)
            elif kid.data == 'reference_namespace':
                # "/" TOKEN? or "/" "(" identifier ")"
                if len(kid.children) > 1:
                    # Check if it's dynamic (with parens) or static namespace
                    # Dynamic: "/" "(" identifier ")" - children[1] is "("
                    # Static: "/" TOKEN - children[1] is TOKEN
                    if len(kid.children) >= 4:
                        # Dynamic namespace dispatch: "/" "(" identifier ")"
                        # kid.children[0] = "/" token
                        # kid.children[1] = "(" token
                        # kid.children[2] = identifier tree
                        # kid.children[3] = ")" token
                        identifier_tree = kid.children[2]
                        namespace = _convert_tree(identifier_tree)
                    else:
                        # Static namespace: "/" TOKEN
                        # kid.children[0] = "/" token
                        # kid.children[1] = TOKEN
                        child = kid.children[1]
                        if isinstance(child, lark.Token):
                            namespace = child.value

    return path, namespace


def _extract_path_from_tree(tree):
    """Extract a dotted path from a tree (tag_path, shape_path, function_path)."""
    path = []
    for kid in tree.children:
        if isinstance(kid, lark.Tree) and kid.data == 'reference_identifiers':
            for child in kid.children:
                if isinstance(child, lark.Token) and child.type == 'TOKEN':
                    path.append(child.value)
        elif isinstance(kid, lark.Token) and kid.type == 'TOKEN':
            path.append(kid.value)
    return path


def _extract_path_and_privacy_from_tree(tree):
    """Extract dotted path and trailing private marker from a path tree.
    Returns (path, is_private)."""
    path = []
    is_private = False
    for kid in tree.children:
        if isinstance(kid, lark.Tree) and kid.data == 'reference_identifiers':
            for child in kid.children:
                if isinstance(child, lark.Token) and child.type == 'TOKEN':
                    path.append(child.value)
        elif isinstance(kid, lark.Token):
            if kid.type == 'TOKEN':
                path.append(kid.value)
            elif kid.type == 'AMPERSAND':
                is_private = True
    return path, is_private


def _extract_operator(token):
    """Extract operator string from token."""
    return token.value


def _create_binary_op(op, left, right):
    """Create appropriate binary operator node."""
    # Arithmetic operators (only +, -, *, / for now)
    if op in ('+', '-', '*', '/'):
        return comp.ast.ArithmeticOp(op, left, right)
    # Comparison operators
    elif op in ('<', '>', '<=', '>=', '==', '!='):
        return comp.ast.ComparisonOp(op, left, right)
    # Boolean operators
    elif op in ('&&', '||'):
        return comp.ast.BooleanOp(op, left, right)
    # Fallback operator
    elif op == '??':
        return comp.ast.FallbackOp(left, right)
    # Template operator
    elif op == '%':
        return comp.ast.TemplateOp(left, right)
    # Unsupported operators (may be added later)
    elif op in ('**', '+-'):
        raise comp.ParseError(f"Operator {op} not yet implemented")
    else:
        raise comp.ParseError(f"Unknown binary operator: {op}")


def _create_unary_op(op, operand):
    """Create appropriate unary operator node."""
    return comp.ast.UnaryOp(op, operand)


def _convert_shape_body(tree):
    """Convert shape_body to list of ShapeFieldDef nodes or a single shape type.
    
    Returns either:
    - list[ShapeFieldDef]: For shapes with explicit fields {field1 field2}
    - AST node: For type aliases (shape_type references like ~other or ~:{})
    """
    if tree.data == 'shape_body':
        # Could be LBRACE shape_field* RBRACE or shape_type
        if tree.children and isinstance(tree.children[0], lark.Token):
            # Has LBRACE - extract fields
            return _convert_children(tree.children[1:-1])
        else:
            # Just a shape_type reference - return the single converted type
            # This handles aliases like: !shape ~alias = ~other
            converted = _convert_children(tree.children)
            # If it's a single shape type reference, return it directly
            if len(converted) == 1:
                return converted[0]
            return converted
    return []


def _convert_tag_definition(kids):
    """Convert tag definition to TagDef node."""
    # Extract components based on what's present
    path = []
    value = None
    generator = None
    children = []
    extends_ref = None
    is_private = False

    for kid in kids:
        if isinstance(kid, lark.Tree):
            if kid.data == 'tag_path':
                path, is_private = _extract_path_and_privacy_from_tree(kid)
            elif kid.data == 'tag_value' or kid.data in ('tag_arithmetic', 'tag_atom'):
                value = _convert_tree(kid)
            elif kid.data == 'tag_generator':
                # Generator is either a function reference or block
                generator = _convert_tree(kid.children[0])
            elif kid.data == 'tag_reference':
                # This is the extends reference
                extends_ref = _convert_tree(kid)
            elif kid.data == 'tag_body':
                # Extract tag children
                children = _convert_children(kid.children[1:-1])  # Skip LBRACE, RBRACE

    return comp.ast.TagDef(path, value, children, generator, extends_ref, is_private=is_private)


def _convert_tag_child(kids):
    """Convert tag child to TagChild node."""
    path = []
    value = None
    children = []
    is_private = False

    for kid in kids:
        if isinstance(kid, lark.Tree):
            if kid.data == 'tag_path':
                path, is_private = _extract_path_and_privacy_from_tree(kid)
            elif kid.data == 'tag_value' or kid.data in ('tag_arithmetic', 'tag_atom'):
                value = _convert_tree(kid)
            elif kid.data == 'tag_body':
                children = _convert_children(kid.children[1:-1])

    return comp.ast.TagChild(path, value, children, is_private=is_private)


def _convert_handle_definition(kids):
    """Convert handle definition to HandleDef node.
    
    Simplified syntax (no body):
        !handle @path
        
    Drop behavior is now defined via |drop-handle function dispatch.
    """
    # Extract path and privacy
    path = []
    is_private = False

    for kid in kids:
        if isinstance(kid, lark.Tree):
            if kid.data == 'handle_path':
                path, is_private = _extract_path_and_privacy_from_tree(kid)

    return comp.ast.HandleDef(path, is_private=is_private)




def _convert_function_definition(tree):
    """Convert function definition to FuncDef node.
    
    Expected structure (with args):
        BANG_FUNC function_path function_shape ARG_KEYWORD shape_type _assignment_op structure
    Or (without args):
        BANG_FUNC function_path function_shape _assignment_op structure
    """
    path = []
    body = None
    input_shape = None
    arg_shape = None
    is_private = False
    
    # Track if we've seen ARG_KEYWORD to know if next shape_type is for args
    seen_arg_keyword = False

    kids = tree.children
    for kid in kids:
        if isinstance(kid, lark.Token):
            if kid.type == 'ARG_KEYWORD':
                seen_arg_keyword = True
        elif isinstance(kid, lark.Tree):
            if kid.data == 'function_path':
                path, is_private = _extract_path_and_privacy_from_tree(kid)
            elif kid.data == 'function_shape':
                # This is the input shape
                input_shape = _convert_tree(kid.children[0]) if kid.children else None
            elif kid.data == 'shape_type' and seen_arg_keyword:
                # This shape_type comes after ARG_KEYWORD, so it's the arg shape
                arg_shape = _convert_tree(kid)
            elif kid.data == 'structure':
                body = _convert_tree(kid)

    return comp.ast.FuncDef(path, body, input_shape, arg_shape, is_private=is_private)


def _convert_import_statement(kids):
    """Convert import statement to ImportDef node.

    Expected structure: !import /namespace = source "path"
    kids will contain: BANG_IMPORT, SLASH, TOKEN (namespace), ASSIGN, import_source (tree with TOKEN), string
    """
    namespace = None
    source = None
    path = None

    for kid in kids:
        if isinstance(kid, lark.Token):
            if kid.type == 'TOKEN':
                # This is the namespace
                namespace = kid.value
        elif isinstance(kid, lark.Tree):
            if kid.data == 'import_source':
                # import_source tree contains a single TOKEN for the source type
                if kid.children and isinstance(kid.children[0], lark.Token):
                    source = kid.children[0].value
            elif kid.data == 'string':
                # String literal for the path
                path = _convert_tree(kid)
                # Extract the string value from the String AST node
                if hasattr(path, 'value'):
                    path = path.value

    if namespace is None or source is None or path is None:
        raise comp.ParseError("Invalid import statement: missing namespace, source, or path")

    return comp.ast.ImportDef(namespace, source, path)


def _convert_module_assign(kids):
    """Convert module assignment to ModuleAssign node.

    Expected structure: identifier _assignment_op tag_value
    kids will contain: identifier tree, assignment operator token, tag_value tree
    """
    # First child is the identifier (the path being assigned to)
    identifier_tree = kids[0]

    # Convert the identifier to a field path
    # We need to extract the fields from the identifier
    path = _convert_module_assign_path(identifier_tree)

    # Third child is the value expression (tag_value)
    value = _convert_tree(kids[2])

    return comp.ast.ModuleAssign(path, value)


def _convert_module_assign_path(tree):
    """Convert identifier to a list of field nodes for module assignment.

    The path should start with a ScopeField ($mod) and continue with field nodes.
    Returns a list of field nodes (ScopeField, TokenField, IndexField, ComputeField, etc.)
    """
    if not isinstance(tree, lark.Tree) or tree.data != 'identifier':
        raise comp.ParseError(f"Module assignment path must be an identifier, got {tree.data}")

    # Convert identifier fields to field nodes
    fields = []
    for kid in tree.children:
        if isinstance(kid, lark.Token):
            if kid.type == 'TOKEN':
                fields.append(comp.ast.TokenField(kid.value))
            elif kid.type == 'INDEXFIELD':
                index = int(kid.value[1:])  # Remove '#'
                fields.append(comp.ast.IndexField(index))
            # Skip dots
        elif isinstance(kid, lark.Tree):
            # Process tree nodes
            if kid.data == 'scope':
                # $name format - extract the scope name
                if len(kid.children) > 1 and isinstance(kid.children[1], lark.Token):
                    scope_name = kid.children[1].value
                    fields.append(comp.ast.ScopeField(scope_name))
            elif kid.data == 'tokenfield':
                # tokenfield contains a TOKEN
                token = kid.children[0]
                if isinstance(token, lark.Token) and token.type == 'TOKEN':
                    fields.append(comp.ast.TokenField(token.value))
            elif kid.data == 'indexfield':
                # indexfield - convert to IndexField
                if len(kid.children) == 1 and isinstance(kid.children[0], lark.Token) and kid.children[0].type == 'INDEXFIELD':
                    # Literal index like #0, #1
                    index = int(kid.children[0].value[1:])
                    fields.append(comp.ast.IndexField(index))
                else:
                    # Expression form: #(expr)
                    expr = _convert_tree(kid.children[2])
                    fields.append(comp.ast.IndexField(expr))
            elif kid.data == 'stringfield':
                # stringfield is a string used as field name
                string_content = _convert_string(kid.children[0].children)
                fields.append(comp.ast.TokenField(string_content))
            elif kid.data == 'computefield':
                # computefield is an expression
                expr = _convert_tree(kid.children[1])
                fields.append(comp.ast.ComputeField(expr))

    return fields


def _convert_main_definition(kids):
    """Convert main definition to MainDef node.

    Expected structure: BANG_MAIN _assignment_op structure
    kids will contain: BANG_MAIN token, assignment operator token, structure tree
    """
    # Third child is the structure (the main body)
    body = _convert_tree(kids[2])
    return comp.ast.MainDef(body)


def _convert_entry_definition(kids):
    """Convert entry definition to EntryDef node.

    Expected structure: BANG_ENTRY _assignment_op structure
    kids will contain: BANG_ENTRY token, assignment operator token, structure tree
    """
    # Third child is the structure (the entry body)
    body = _convert_tree(kids[2])
    return comp.ast.EntryDef(body)


def _convert_doc_statement(tree):
    """Convert documentation statement to DocStatement node.

    Three forms:
    - doc_module: BANG_DOC MODULE_KEYWORD string
    - doc_impl: BANG_DOC IMPL_KEYWORD string
    - doc_general: BANG_DOC string
    """
    kids = tree.children
    is_impl = tree.data == 'doc_impl'
    is_module = tree.data == 'doc_module'

    # For doc_impl and doc_module, string is the third child (after BANG_DOC and keyword)
    # For doc_general, string is the second child (after BANG_DOC)
    string_index = 2 if (is_impl or is_module) else 1

    # Convert the string node
    string_node = _convert_tree(kids[string_index])

    # Extract the string value
    if hasattr(string_node, 'value'):
        doc_text = string_node.value
    else:
        raise comp.ParseError(f"Expected string for documentation, got {type(string_node)}")

    return comp.ast.DocStatement(doc_text, is_impl=is_impl, is_module=is_module)


def _get_parser(start):
    """Get a cached Lark parser instance for the given start rule.

    Args:
        start (str): Grammar start rule (e.g., "module", "expression_start", "shape_type")

    Returns:
        lark.Lark: Cached Lark parser instance
    """
    if start not in _parsers:
        grammar_path = pathlib.Path(__file__).parent / "comp.lark"
        _parsers[start] = lark.Lark(
            grammar_path.read_text(encoding="utf-8"),
            parser="lalr",
            start=start,
            propagate_positions=True,
            keep_all_tokens=True,
        )
    return _parsers[start]
