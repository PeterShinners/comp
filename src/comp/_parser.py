"""
Clean parser and transformer for Comp language.

Simple, consistent design with minimal complexity.
Uses the clean AST nodes for consistent naming and structure.
"""

__all__ = ["parse", "grammar"]

from pathlib import Path

import lark

from . import _ast

# Global parser instance
_lark_parser: lark.Lark | None = None



class MiniAst:
    def __init__(self, name, kids=None, **kwargs):
        self.name = name
        self.kids = kids or []
        self.attrs = kwargs

    def __repr__(self):
        attrs = [f"{k}={v}" for k, v in self.attrs.items()]
        if self.kids:
            attrs.insert(0, f"*{len(self.kids)}")
        return f"{self.name}({' '.join(attrs)})"

    def tree(self, indent=0):
        print(f"{'  '*indent}{self!r}")
        for kid in self.kids:
            kid.tree(indent + 1)


def parse(text: str):
    """Parse Comp code and return an AST node."""
    try:
        parser = _get_parser()
        tree = parser.parse(text)
        root = MiniAst("root")
        ast = lark_to_ast(root, tree.children)
        return ast
    except lark.ParseError as e:
        raise _ast.ParseError(str(e)) from e


def lark_to_ast(parent: MiniAst, children: list[lark.Tree | lark.Token]) -> MiniAst:
    """Convert Lark parse tree children to Comp AST.

    Args:
        parent: MiniAst node to add children to
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
        node = None  # Fill out either node or nodes (or both?)
        nodes = []
        match child.data:
            # Skips
            case 'start':  #  Defensive, normally skipped at entry
                return lark_to_ast(parent, child.children)
            case 'paren_expr':
                # LPAREN expression RPAREN - just unwrap and process the middle child
                # Don't return early - we need to continue processing siblings
                lark_to_ast(parent, [child.children[1]])
                continue
            case 'atom_field':
                # atom_field: atom_in_expr "." identifier_field
                # This is field access on an expression: (expr).field
                # Children: [expr_tree, DOT, field_tree]
                node = MiniAst('field_access')
                # Process the left side (the expression being accessed)
                lark_to_ast(node, [kids[0]])
                # Process the right side (the field) - try to use field helper
                field_tree = kids[2]  # Skip DOT token
                field_node = _create_field_node(field_tree)
                if field_node:
                    node.kids.append(field_node)
                else:
                    # Not a simple field, recurse
                    lark_to_ast(node, [field_tree])

            # Leafs
            case 'string':
                node = MiniAst('string', value=kids[1] if len(kids) == 3 else "")
            case 'number':
                node = MiniAst('number', value=str(kids[0]))
            case 'placeholder':
                node = MiniAst('placeholder', value="???")

            case 'localscope':
                node = MiniAst("scope", value="@")
            case 'argscope':
                node = MiniAst("scope", value="^")
            case 'namescope':
                node = MiniAst("scope", value=f"${kids[0].value}")

            case 'tokenfield' | 'indexfield' | 'stringfield' | 'computefield':
                # All field types handled by the helper
                node = _create_field_node(child)

            # Parents
            case 'identifier':
                node = MiniAst('identifier')
                lark_to_ast(node, kids)
            case 'scope':
                # scope wraps localscope/argscope/namescope - create identifier
                node = MiniAst('identifier')
                lark_to_ast(node, kids)
            case 'binary_op':
                node = MiniAst('binary_op', op=kids[1].value)
                lark_to_ast(node, kids)
            case 'unary_op':
                node = MiniAst('unary_op', op=kids[0].value)
                lark_to_ast(node, kids)

            # Structures
            case 'structure':
                node = MiniAst('structure')
                lark_to_ast(node, kids)
            case 'block':
                # block: COLON_BLOCK_START _structure_content RBRACE
                # Same as structure but with :{ instead of {
                node = MiniAst('block')
                lark_to_ast(node, kids)
            case 'structure_assign':
                # structure_assign: _qualified _assignment_op expression
                # child.children[0] is identifier/qualified, [1] is Token(=), [2] is expression
                # Find the assignment operator token
                op_token = next((k for k in kids if isinstance(k, lark.Token)), None)
                node = MiniAst('assign', op=op_token.value if op_token else '=')
                lark_to_ast(node, kids)
            case 'structure_unnamed':
                # structure_unnamed: expression - just an unnamed value
                node = MiniAst('unnamed')
                lark_to_ast(node, kids)
            case 'structure_spread':
                # structure_spread: SPREAD expression - ..expr
                node = MiniAst('spread')
                lark_to_ast(node, kids)

            # Pipelines
            case 'expr_pipeline':
                # expr_pipeline: expression pipeline - left side pipes through operations
                node = MiniAst('pipeline')
                lark_to_ast(node, kids)
            case 'pipeline':
                # pipeline: (pipe_func | pipe_struct | pipe_block | pipe_wrench | pipe_fallback)+
                # Just a container for pipe operations - process children directly
                lark_to_ast(parent, kids)
                return parent
            case 'pipe_fallback':
                # pipe_fallback: PIPE_FALLBACK expression
                node = MiniAst('pipe_op', op='|?')
                lark_to_ast(node, kids)
            case 'pipe_struct':
                # pipe_struct: PIPE_STRUCT structure_op* RBRACE
                node = MiniAst('pipe_op', op='|{')
                lark_to_ast(node, kids)
            case 'pipe_block':
                # pipe_block: PIPE_BLOCK _qualified
                node = MiniAst('pipe_op', op='|:')
                lark_to_ast(node, kids)
            case 'pipe_func':
                # pipe_func: _function_piped function_arguments
                node = MiniAst('pipe_op', op='|')
                lark_to_ast(node, kids)
            case 'pipe_wrench':
                # pipe_wrench: PIPE_WRENCH _function_piped
                node = MiniAst('pipe_op', op='|<<')
                lark_to_ast(node, kids)

            # References
            case 'reference_identifiers':
                # reference_identifiers: TOKEN ("." TOKEN)* - dotted path like foo.bar.baz
                # Collect all the TOKEN values
                tokens = [t.value for t in kids if isinstance(t, lark.Token) and t.type == 'TOKEN']
                node = MiniAst('ref_path', path='.'.join(tokens))
            case 'reference_namespace':
                # reference_namespace: "/" TOKEN? - optional namespace like /ns or just /
                if len(kids) > 1 and isinstance(kids[1], lark.Token):
                    node = MiniAst('ref_namespace', ns=kids[1].value)
                else:
                    node = MiniAst('ref_namespace', ns='')
            case 'tag_reference':
                # tag_reference: "#" _reference_path
                node = MiniAst('tag_ref')
                lark_to_ast(node, kids)
            case 'shape_reference':
                # shape_reference: "~" _reference_path
                node = MiniAst('shape_ref')
                lark_to_ast(node, kids)
            case 'function_reference':
                # function_reference: "|" _reference_path
                node = MiniAst('func_ref')
                lark_to_ast(node, kids)

            # Function arguments
            case 'function_arguments':
                # function_arguments: functionstructure_op* - container, process children
                lark_to_ast(parent, kids)
                return parent
            case 'function_structure_assign':
                # function_structure_assign: _qualified _assignment_op _prepipeline_expression
                op_token = next((k for k in kids if isinstance(k, lark.Token)), None)
                node = MiniAst('arg_assign', op=op_token.value if op_token else '=')
                lark_to_ast(node, kids)
            case 'function_structure_unnamed':
                # function_structure_unnamed: _prepipeline_expression
                node = MiniAst('arg_unnamed')
                lark_to_ast(node, kids)
            case 'function_structure_spread':
                # function_structure_spread: SPREAD _prepipeline_expression
                node = MiniAst('arg_spread')
                lark_to_ast(node, kids)

            case _:
                raise ValueError(f"Unimplemented rule: {child.data}")

        if node:
            parent.kids.append(node)
        if nodes:
            parent.kids.extend(nodes)

        # # Set position metadata from tree
        # if node and hasattr(tree, 'meta'):
        #     node.start = (tree.meta.line, tree.meta.column)
        #     node.end = (tree.meta.end_line, tree.meta.end_column)

    return parent


def _create_field_node(child: lark.Tree) -> MiniAst | None:
    """Create a field node from a lark Tree.

    This has two users; literal fields (one.two) and fields on expressions (|fancy).two
    """
    kids = child.children
    match child.data:
        case 'tokenfield':
            return MiniAst("tokenfield", value=kids[0].value)
        case 'indexfield':
            return MiniAst("indexfield", value=int(kids[0].value[1:]))
        case 'stringfield':
            # stringfield contains a string tree: [QUOTE, content, QUOTE]
            string_tree = kids[0]
            string_kids = string_tree.children
            value = string_kids[1].value if len(string_kids) == 3 else ""
            return MiniAst("stringfield", value=value)
        case 'computefield':
            # computefield: "'" expression "'" - create node and process expression
            node = MiniAst("computefield")
            lark_to_ast(node, kids)
            return node
        case _:
            return None


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

