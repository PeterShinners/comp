"""
Clean parser and transformer for Comp language.

Simple, consistent design with minimal complexity.
Uses the clean AST nodes for consistent naming and structure.
"""

__all__ = ["parse_module", "parse_expr", "grammar_module", "grammar_expr"]

import functools
from pathlib import Path

import lark

from . import _ast

# Global parser instances
_module_parser: lark.Lark | None = None
_expr_parser: lark.Lark | None = None


def parse_module(text: str) -> _ast.Module:
    """Parse a complete Comp module.

    Parses module-level statements including tag definitions, function
    definitions, imports, and entry points.

    Args:
        text: Module source code

    Returns:
        Module AST node containing all module statements

    Raises:
        ParseError: If the text contains invalid syntax
    """
    try:
        parser = _get_module_parser()
        tree = parser.parse(text)
        module = _create_node([].append, tree, _ast.Module)
        ast = generate_ast(module, tree.children)
        return ast
    except lark.exceptions.LarkError as e:
        error_msg = str(e)
        # Improve error messages for common cases
        if "DUBQUOTE" in error_msg and "$END" in error_msg:
            error_msg = "Unterminated string literal"
        raise _ast.ParseError(error_msg) from e


def parse_expr(text: str) -> _ast.Root:
    """Parse a single Comp expression.

    Parses expression-level constructs like numbers, strings, structures,
    pipelines, and operators. Used for REPL, testing, and embedded contexts.

    Args:
        text: Expression source code

    Returns:
        Root AST node containing the expression

    Raises:
        ParseError: If the text contains invalid syntax
    """
    try:
        parser = _get_expr_parser()
        tree = parser.parse(text)
        root = _create_node([].append, tree, _ast.Root)
        ast = generate_ast(root, tree.children)
        return ast
    except lark.exceptions.LarkError as e:
        error_msg = str(e)
        # Improve error messages for common cases
        if "DUBQUOTE" in error_msg and "$END" in error_msg:
            error_msg = "Unterminated string literal"
        raise _ast.ParseError(error_msg) from e


def generate_ast(parent: _ast.AstNode, children: list[lark.Tree | lark.Token]) -> _ast.AstNode:
    """Convert Lark parse tree children to Comp AST.

    Args:
        parent: AstNode to add children to
        children: List of lark.Tree or lark.Token objects to process

    Returns:
        The parent node with children added
    """
    for child in children:
        if isinstance(child, lark.Token):
            continue

        # child is a lark.Tree - determine which AST node to create
        assert isinstance(child, lark.Tree)
        kids = child.children
        _node = functools.partial(_create_node, parent.kids.append, child)
        match child.data:
            # Skips
            case 'start' | 'module':
                # Pass through to children
                return generate_ast(parent, child.children)
            case 'expression_start':
                # Expression entry point - pass through
                return generate_ast(parent, child.children)
            case 'paren_expr':
                # LPAREN expression RPAREN
                # Just unwrap and process the middle child
                middle_child = child.children[1]
                generate_ast(parent, [middle_child])
                continue
            case 'pipeline_expr':
                # LBRACKET [seed] pipeline RBRACKET
                # Create a Pipeline node and process children
                _node(_ast.Pipeline, walk=kids)
            case 'atom_field':
                # atom_field: atom_in_expr "." identifier_next_field
                # This is field access on an expression: (expr).field
                # Children: [expr_tree, DOT, field_tree]
                _node(_ast.FieldAccess, walk=kids)

            # Tag definitions
            case 'tag_definition':
                _node(_ast.TagDefinition, walk=kids)
            case 'tag_generator':
                generate_ast(parent, kids)  # pass through function or block ref
                continue
            case 'tag_body':
                _node(_ast.TagBody, walk=kids)
            case 'tag_child':
                _node(_ast.TagChild, walk=kids)
            case 'tag_value' | 'tag_arithmetic' | 'tag_term' | 'tag_bitwise' | 'tag_comparison' | 'tag_unary' | 'tag_atom':
                generate_ast(parent, kids)  # pass through value literals (and exprs)
                continue
            case 'tag_path':
                pass  # ignored

            # Shape definitions
            case 'shape_definition':
                _node(_ast.ShapeDefinition, walk=kids)
            case 'shape_body':
                # shape_body: LBRACE shape_field* RBRACE | shape_type
                # If it's a body with braces, pass through children (shape_field nodes)
                # If it's a simple type reference/union, that will be handled as a child
                generate_ast(parent, kids)
                continue
            case 'shape_field_def':
                # shape_field_def: TOKEN QUESTION? shape_type? (ASSIGN expression)?
                _node(_ast.ShapeField, walk=kids)
            case 'shape_spread':
                # shape_spread: SPREAD shape_type
                _node(_ast.ShapeSpread, walk=kids)
            case 'shape_path':
                # This is handled by ShapeDefinition.fromGrammar
                # Should not appear as standalone in AST
                pass

            # Function definitions
            case 'function_definition':
                _node(_ast.FunctionDefinition, walk=kids)
            case 'function_path':
                # This is handled by FunctionDefinition.fromGrammar
                # Should not appear as standalone in AST
                pass
            case 'function_shape':
                # function_shape: shape_type - just pass through the type
                generate_ast(parent, kids)
                continue
            case 'arg_shape':
                # arg_shape: CARET shape_body
                # Convert shape_body content into a Structure node
                # The shape_body will have ShapeField children which we wrap in Structure
                _node(_ast.Structure, walk=kids)
                continue

            case 'shape_union':
                # shape_union: shape_type_atom (PIPE shape_type_atom)+
                # Creates a ShapeUnion with all atoms as direct children
                _node(_ast.ShapeUnion, walk=kids)
            case 'shape_inline':
                # shape_inline: TILDE LBRACE shape_field* RBRACE
                # Creates a ShapeInline with all fields as children
                _node(_ast.ShapeInline, walk=kids)
            case 'morph_inline':
                # morph_inline: LBRACE shape_field* RBRACE (without ~)
                # Creates a ShapeInline for morph context
                _node(_ast.ShapeInline, walk=kids)
            case 'shape_type' | 'shape_type_atom':
                # Just pass through - the actual nodes are created by their specific rules
                generate_ast(parent, kids)
                continue

            # Leafs
            case 'string':
                _node(_ast.String)
            case 'number':
                _node(_ast.Number)
            case 'placeholder':
                _node(_ast.Placeholder)

            # References
            case 'tag_reference':
                _node(_ast.TagRef)
            case 'shape_reference':
                _node(_ast.ShapeRef)
            case 'function_reference':
                _node(_ast.FuncRef)
            case 'reference_identifiers':
                # Used in morph_type to build a ShapeRef without the ~ prefix
                _node(_ast.ShapeRef, walk=kids)

            # Identifiers - need custom handling to process fields
            case 'identifier':
                _node(_ast.Identifier, walk=kids)
            case 'tokenfield':
                _node(_ast.TokenField)
            case 'indexfield':
                _node(_ast.IndexField)
            case 'string':
                _node(_ast.StringField)
            case 'localscope' | 'argscope' | 'namescope':
                _node(_ast.ScopeField)
            case 'computefield':
                # computefield: "'" expression "'" - create node and process expression
                _node(_ast.ComputeField, walk=child.children)

            # General Operators (not including assignment)
            case 'binary_op':
                _node(_ast.BinaryOp, walk=kids)
            case 'unary_op':
                _node(_ast.UnaryOp, walk=kids)

            # Shape morph operators
            case 'morph_op' | 'strong_morph_op' | 'weak_morph_op':
                _node(_ast.MorphOp, walk=kids)

            # Morph type handling
            case 'morph_type':
                # morph_type: reference_identifiers reference_namespace? | tag_reference | shape_inline | morph_union
                # If it's just reference_identifiers, create a ShapeRef
                if len(kids) >= 1 and kids[0].data == 'reference_identifiers':
                    # This is a shape reference (without the ~ prefix)
                    _node(_ast.ShapeRef, walk=kids)
                else:
                    # tag_reference, shape_inline, or morph_union - pass through
                    generate_ast(parent, kids)
                    continue
            case 'morph_union':
                # morph_union: morph_type (PIPE morph_type)+
                _node(_ast.ShapeUnion, walk=kids)

            # Structures (including function arguments)
            case 'block':
                _node(_ast.Block, walk=kids)
            case 'structure' | 'function_arguments':
                _node(_ast.Structure, walk=kids)
            case 'structure_assign':
                _node(_ast.StructAssign, walk=kids)
            case 'structure_unnamed':
                _node(_ast.StructUnnamed, walk=kids)
            case 'structure_spread':
                _node(_ast.StructSpread, walk=kids)

            # Pipelines
            case 'pipeline_expr':
                # LBRACKET [seed] pipeline RBRACKET
                # Pipeline node created above in atom section
                pass
            case 'pipeline':
                # This is just a container for pipe operations - pass through children
                # The Pipeline node is created by pipeline_expr
                generate_ast(parent, kids)
            case 'pipe_fallback':
                _node(_ast.PipeFallback, walk=kids)
            case 'pipe_struct':
                _node(_ast.PipeStruct, walk=kids)
            case 'pipe_block':
                _node(_ast.PipeBlock, walk=kids)
            case 'pipe_func':
                _node(_ast.PipeFunc, walk=kids)
            case 'pipe_wrench':
                _node(_ast.PipeWrench, walk=kids)

            case _:
                raise ValueError(f"Unimplemented grammar rule {child.data} at {parent}")

    return parent


def _create_node(parent_append, tree: lark.Tree, cls, walk=None):
    """Helper to create ast nodes and recurse"""
    node = cls.fromGrammar(tree)
    meta = tree.meta
    if tree.children:
        node.position = ((meta.line, meta.column), (meta.end_line, meta.end_column))
    if walk:
        generate_ast(node, walk)
    parent_append(node)
    return node


def grammar_module(code: str):
    """
    Debug utility: Parse module and pretty print the raw Lark tree.

    This bypasses AST transformation to show the raw grammar structure,
    useful for debugging module-level grammar issues.

    Args:
        code: The module code to parse

    Returns:
        lark.Tree: The raw Lark parse tree, or None if parsing failed
    """
    grammar_path = Path(__file__).parent / "lark" / "comp.lark"
    parser = lark.Lark(
        grammar_path.read_text(encoding="utf-8"),
        parser='lalr',
        start='module',
        keep_all_tokens=True,
    )

    print(f"Parsing module: {code}")
    try:
        tree = parser.parse(code)
        _pretty_print_lark_tree(tree)
        return None
    except Exception as e:
        print(f"Parse error: {e}")
        return None


def grammar_expr(expression: str):
    """
    Debug utility: Parse expression and pretty print the raw Lark tree.

    This bypasses AST transformation to show the raw grammar structure,
    useful for debugging expression-level grammar issues.

    Args:
        expression: The expression to parse

    Returns:
        lark.Tree: The raw Lark parse tree, or None if parsing failed
    """
    grammar_path = Path(__file__).parent / "lark" / "comp.lark"
    parser = lark.Lark(
        grammar_path.read_text(encoding="utf-8"),
        parser='lalr',
        start='expression_start',
        keep_all_tokens=True,
    )

    print(f"Parsing expression: {expression}")
    try:
        tree = parser.parse(expression)
        _pretty_print_lark_tree(tree)
        return None
    except Exception as e:
        print(f"Parse error: {e}")
        return None


def _pretty_print_lark_tree(tree, indent=0):
    """Pretty print a Lark tree in a readable hierarchical format."""
    spaces = "  " * indent

    if hasattr(tree, 'data'):
        # This is a Tree node
        print(f"{spaces}{tree.data}")
        for child in tree.children:
            _pretty_print_lark_tree(child, indent + 1)
    else:
        # This is a Token
        if hasattr(tree, 'type'):
            print(f"{spaces}[{tree.type}] '{tree.value}'")
        else:
            print(f"{spaces}'{tree}'")


def _get_module_parser() -> lark.Lark:
    """Get the singleton Lark parser instance for module parsing."""
    global _module_parser
    if _module_parser is None:
        grammar_path = Path(__file__).parent / "lark" / "comp.lark"
        _module_parser = lark.Lark(
            grammar_path.read_text(encoding="utf-8"),
            parser="lalr",
            start="module",
            propagate_positions=True,
            keep_all_tokens=True,
        )
    return _module_parser


def _get_expr_parser() -> lark.Lark:
    """Get the singleton Lark parser instance for expression parsing."""
    global _expr_parser
    if _expr_parser is None:
        grammar_path = Path(__file__).parent / "lark" / "comp.lark"
        _expr_parser = lark.Lark(
            grammar_path.read_text(encoding="utf-8"),
            parser="lalr",
            start="expression_start",
            propagate_positions=True,
            keep_all_tokens=True,
        )
    return _expr_parser

