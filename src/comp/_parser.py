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


def parse(text: str):
    """Parse Comp code and return an AST node."""
    try:
        parser = _get_parser()
        return parser.parse(text)
    except lark.ParseError as e:
        raise _ast.ParseError(str(e)) from e



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
        maybe_placeholders=False
    )

    print(f"Parsing: {expression}")
    print("=" * 60)

    try:
        tree = parser.parse(expression)
        _pretty_print_lark_tree(tree)
        return tree
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
            transformer=CompTransformer(),
        )
    return _lark_parser


class CompTransformer(lark.Transformer):
    """Thin transformer that routes Lark trees to AST node fromLark methods."""

    # Start rule - just pass through the expression
    def start(self, children):
        return children[0]

    # Numbers - route tokens directly to _ast.Number.fromLark
    def INTBASE(self, token):
        return _ast.Number.fromLark(token)

    def DECIMAL(self, token):
        return _ast.Number.fromLark(token)

    def number(self, children):
        # number rule just passes through the token
        return children[0]

    # Strings - handle the content tokens from short and long strings
    def SHORT_STRING_CONTENT(self, token):
        return _ast.String.fromLark(token)

    def LONG_STRING_CONTENT(self, token):
        return _ast.String.fromLark(token)

    def string(self, children):
        # string rule just passes through the content
        return children[0] if children else _ast.String("", '"')

    # Basic tokens
    def TOKEN(self, token):
        # TOKEN becomes a TokenField
        return _ast.TokenField(str(token))

    def INDEXFIELD(self, token):
        # INDEXFIELD token like #0, #1
        index_str = str(token)[1:]  # Remove #
        return _ast.IndexField(int(index_str))

    def field_name(self, children):
        # field_name: "'" TOKEN "'"
        # Creates a NameField
        token = children[0]
        # Token might be a TokenField or a raw token
        if isinstance(token, _ast.TokenField):
            return _ast.NameField(token.name)
        else:
            return _ast.NameField(str(token))

    def computefield(self, children):
        # computefield: "'" atom "'"
        # Creates a ComputedField
        expr = children[0]
        return _ast.ComputedField(expr)

    # Placeholder
    def PLACEHOLDER(self, token):
        return _ast.Placeholder()

    # Grammar rules
    def paren_expr(self, children):
        # paren_expr: LPAREN expression RPAREN | LPAREN pipeline RPAREN
        # Strip the parentheses and return just the inner expression/pipeline
        # Children: [LPAREN token, expression/pipeline, RPAREN token]
        return children[1]

    def identifier(self, children):
        return _ast.Identifier.fromLark(children)

    def scope(self, children):
        return _ast.Scope.fromLark(children)

    # Reference intermediate rules
    def reference_identifiers(self, children):
        # Extract name strings from the path
        # Children might be TOKEN tokens, Field subclasses, or Identifiers
        tokens = []
        for child in children:
            if hasattr(child, 'type') and child.type == 'TOKEN':
                # Raw TOKEN
                tokens.append(str(child))
            elif isinstance(child, _ast.TokenField):
                # TokenField - extract the name
                tokens.append(child.name)
            elif isinstance(child, _ast.Field):
                # Other Field subclass - try to get a string representation
                tokens.append(child.repr())
            elif isinstance(child, _ast.Identifier):
                # Transformed Identifier - extract the first field's value
                if child.fields and isinstance(child.fields[0], _ast.TokenField):
                    tokens.append(child.fields[0].name)
            elif isinstance(child, str):
                tokens.append(child)
        return tokens

    def reference_namespace(self, children):
        # Returns "/" or "/namespace"
        if not children:
            return "/"
        return "/" + str(children[0]) if children else "/"

    # References
    def tag_reference(self, children):
        # children: [reference_identifiers, reference_namespace?]
        path = children[0] if children else []
        namespace = children[1] if len(children) > 1 else None
        return _ast.TagRef(path, namespace)

    def shape_reference(self, children):
        path = children[0] if children else []
        namespace = children[1] if len(children) > 1 else None
        return _ast.ShapeRef(path, namespace)

    def function_reference(self, children):
        path = children[0] if children else []
        namespace = children[1] if len(children) > 1 else None
        return _ast.FunctionRef(path, namespace)

    # Structures
    def structure(self, children):
        return _ast.Structure.fromLark(children)

    def block(self, children):
        return _ast.Block.fromLark(children)

    # Field access operations
    def atom_field(self, children):
        # atom_in_expr "." field_follower
        # Extends an Identifier or Scope with an additional field
        obj = children[0]
        new_field = children[1]

        if isinstance(obj, _ast.Identifier):
            # Add field to identifier
            return _ast.Identifier(obj.fields + [new_field])
        elif isinstance(obj, _ast.Scope):
            # Add field to scope
            return _ast.Scope(obj.scope_type, obj.fields + [new_field])
        else:
            # For other types, we'd need a different approach
            # For now, just return the original
            return obj

    def atom_fallback(self, children):
        # atom_in_expr "??" expression
        # This is the fallback operator
        left = children[0]
        right = children[1]
        return _ast.BinaryOp(left, "??", right)

    # Operations
    def binary_op(self, children):
        return _ast.BinaryOp.fromLark(children)

    def unary_op(self, children):
        return _ast.UnaryOp.fromLark(children)

    # Pipeline operations with specific operators
    def pipeline_fallback(self, children):
        return _ast.Pipeline(children[0], "??", children[1])

    def pipeline_pipe(self, children):
        return _ast.Pipeline(children[0], "|", children[1])

    def pipeline_block_invoke(self, children):
        return _ast.Pipeline(children[0], "|>", children[1])

    def pipeline_op(self, children):
        return _ast.Pipeline.fromLark(children)
