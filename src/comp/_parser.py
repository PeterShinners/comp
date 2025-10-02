"""
Clean parser and transformer for Comp language.

Simple, consistent design with minimal complexity.
Uses the clean AST nodes for consistent naming and structure.
"""

__all__ = ["parse", "grammar"]

import functools
from pathlib import Path

import lark

from . import _ast

# Global parser instance
_lark_parser: lark.Lark | None = None


def parse(text: str):
    """Parse Comp code and return an AST node."""
    try:
        parser = _get_parser()
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
            case 'start':  #  Defensive, normally skipped at entry
                return generate_ast(parent, child.children)
            case 'paren_expr':
                # LPAREN (expression | pipeline) RPAREN
                # If it's a pipeline, wrap it in a Pipeline node
                # Otherwise just unwrap and process the middle child
                middle_child = child.children[1]
                if middle_child.data == 'pipeline':
                    _node(_ast.Pipeline, walk=[middle_child])
                else:
                    generate_ast(parent, [middle_child])
                continue
            case 'atom_field':
                # atom_field: atom_in_expr "." identifier_next_field
                # This is field access on an expression: (expr).field
                # Children: [expr_tree, DOT, field_tree]
                _node(_ast.FieldAccess, walk=kids)

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

            # Function arguments
            case 'function_arguments':
                _node(_ast.Structure, walk=kids)
            case 'function_structure_assign':
                _node(_ast.StructAssign, walk=kids)
            case 'function_structure_unnamed':
                _node(_ast.StructUnnamed, walk=kids)
            case 'function_structure_spread':
                _node(_ast.StructSpread, walk=kids)

            # Structures
            case 'block':
                _node(_ast.Block, walk=kids)
            case 'structure' | 'function_arguments':
                _node(_ast.Structure, walk=kids)
            case 'structure_assign' | 'function_structure_assign':
                _node(_ast.StructAssign, walk=kids)
            case 'structure_unnamed' | 'function_structure_unnamed':
                _node(_ast.StructUnnamed, walk=kids)
            case 'structure_spread' | 'function_structure_spread':
                _node(_ast.StructSpread, walk=kids)

            # Pipelines
            case 'expr_pipeline':
                _node(_ast.Pipeline, walk=kids)
            case 'pipeline':
                # This is just a container for pipe operations - pass through children
                # The Pipeline node is created by expr_pipeline or paren wrapping
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


def grammar(expression):
    """
    Debug utility: Reload Lark parser, parse expression, and pretty print the raw Lark tree.

    This bypasses AST transformation to show the raw grammar structure,
    useful for debugging grammar issues at the Lark level.

    Args:
        expression (str): The expression to parse

    Returns:
        lark.Tree: The raw Lark parse tree, or None if parsing failed
    """
    # Read and combine grammar files fresh each time
    grammar_dir = Path(__file__).parent / "lark"

    # Read main grammar
    with open(grammar_dir / "comp.lark") as f:
        comp_grammar = f.read()

    # Create fresh parser
    parser = lark.Lark(
        comp_grammar,
        parser='lalr',
        start='expression',
        keep_all_tokens=True,
        maybe_placeholders=False,
    )

    print(f"Parsing: {expression}")
    try:
        tree = parser.parse(expression)
        _pretty_print_lark_tree(tree)
        return None#tree
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


def _get_parser() -> lark.Lark:
    """Get the singleton Lark parser instance."""
    global _lark_parser
    if _lark_parser is None:
        grammar_path = Path(__file__).parent / "lark" / "comp.lark"
        _lark_parser = lark.Lark(
            grammar_path.read_text(encoding="utf-8"),
            parser="lalr",
            #transformer=CompTransformer(),
            propagate_positions=True,
            keep_all_tokens=True,
        )
    return _lark_parser

