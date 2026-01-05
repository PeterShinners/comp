"""Parse code into cop (comp operators) structure.

The cops are similar to an ast structure. They are designed to be easy to
manipulate, assemble, and transform. The cop objects are simple comp structures
and easy to serialize.

This data is usually generated from source with `comp.parse`. Each cop structure
tracks the position it was generated from in the original source string. Cop
data is built into executable code objects with `comp.build`.

Each cop node has a positional tag as its first child. There is also an optional
"kids" field which contains a struct of positional cop nodes. (the kids can be
named, but the name is ignored other than for diagnostic info). There is also a
recommended "pos" field which defines the 4 numbers defining the source span
defining the cop. There can be any number of additional named fields which
should have full Value types as values.
"""

__all__ = [
    "COP_TAGS",
    "cop_module",
    "lark_parser",
]

import lark
import comp


COP_TAGS = [
    "shape.identifier",  # (identifier, checks, array, default)
    "shape.union",  # (shapes, checks, array, default)
    "shape.define",  # (fields, checks, array)
    "shape.field",  # (kids) 1 or 2 kids, shape and optional default
    "struct.define",  # (kids)
    "struct.posfield",  # (kids) 1 kid
    "struct.namefield",  # (op, kids) 2 kids (name value)
    "struct.letassign",  # (name, kids) 1 kid (value)
    "struct.decorator",  # (op, kids) 1 kid (name/identifier/ref)
    "mod.define",  # (kids)
    "mod.namefield",  # (op, kids) 2 kids (name value)
    "value.identassign",  # (kids)  same as identifier, but in an assignment
    "value.identifier",  # (kids)
    "value.reference",  # (definition, identifier, namespace, pos) Reference to a Definition
    "value.constant",  # (value) Constant value
    "ident.token",  # (value)
    "ident.index",  # (value)
    "ident.indexpr",  # (value)
    "ident.expr",  # (value)
    "ident.text",  # (value)
    "value.number",  # (value)
    "value.text",  # (value)
    "value.block",  # (kids)  kids; signature, body
    "value.math.unary",  # (op, kids)  1 kid
    "value.math.binary",  # (op, kids)  2 kids
    "value.compare",  # (op, kids)  2 kids
    "value.logic.binary",  # (op, kids)  2 kids
    "value.logic.unary",  # (op, kids)  1 kids
    "value.invoke",  # (kids)  kids 2+ kids; callable, argsandblocks
    "value.pipe",  # (kids)
    "value.fallback",  # (kids)
    "value.postfix",  # (left, kids)
    "value.transact",  # (kids)
    "value.handle",  # (op, kids) grab/drop/pull/etc
    "value.constant",  # (value) precompiled constant value
    "stmt.assign",  # (kids) 2 kids (lvalue, rvalue)
]


def lark_parser(name):
    """Get globally shared lark parser.

    Args:
        name: (str) name of the grammar file (without .lark)

    Returns:
        (lark.Lark) Parser instance
    """
    parser = _parsers.get(name)
    if parser is not None:
        return parser

    path = f"lark/{name}.lark"
    parser = lark.Lark.open(
        path, rel_to=__file__, parser="lalr", propagate_positions=True
    )
    _parsers[name] = parser
    return parser


_copmodule = None
_tagnames = {}


def cop_module():
    """Create and populate the cop module"""
    global _copmodule
    if _copmodule is None:
        # Create a minimal ModuleSource for cop module
        source = type('obj', (object,), {'resource': 'cop', 'content': ''})()
        _copmodule = comp.Module(source)
        _copmodule._definitions = {}
        for name in COP_TAGS:
            tag_def = comp.Tag(name, False)
            tag_def.module = _copmodule
            # Wrap in Value and store in definitions
            value = comp.Value.from_python(tag_def)
            _copmodule._definitions[name] = value
            # Store Tag for cop node construction
            _tagnames[name] = tag_def
            # Eventually want real shapes to go with each of these,
            # but for now we freestyle it.

        _copmodule.finalize()
    return _copmodule


def _parsed(treetoken, tag, kids, **fields):
    """Create a cop node with position from tree/token."""
    if isinstance(treetoken, lark.Token):
        token = treetoken
        pos = (
            token.line,
            token.column,
            token.end_line or token.line,
            token.end_column or token.column,
        )
        fields["pos"] = pos
    elif isinstance(treetoken, lark.Tree):
        meta = treetoken.meta
        pos = (
            meta.line,
            meta.column,
            meta.end_line or meta.line,
            meta.end_column or meta.column,
        )
        fields["pos"] = pos

    return comp.create_cop(tag, kids, **fields)


def lark_to_cop(tree):
    """Convert a single Lark tree/token to a cop node.

    This will often recurse into child nodes of the tree.

    Args:
        tree: (lark.Tree | lark.Token) Lark Tree or Token to convert

    Returns:
        (Value) cop node
    """
    # Handle tokens (terminals)
    if isinstance(tree, lark.Token):
        raise ValueError(f"Unhandled grammar token: {tree}")

    # Handle trees (non-terminals)
    assert isinstance(tree, lark.Tree)
    kids = tree.children  # type : [lark.Tree | lark.Token]
    match tree.data:
        case "paren_expr":
            # LPAREN expression RPAREN - return the expression
            return lark_to_cop(kids[1])

        # Literals
        case "number":
            return _parsed(tree, "value.number", [], value=kids[0].value)
        case "text":
            return _parsed(tree, "value.text", [], value=kids[1].value)

        # Operators
        case "binary_op":
            left = lark_to_cop(kids[0])
            right = lark_to_cop(kids[2])
            op = kids[1].value
            if op in ("||", "&&"):
                return _parsed(
                    tree, "value.logical.binary", {"l": left, "r": right}, op=op
                )
            if op == "??":
                return _parsed(tree, "value.fallback", {"l": left, "r": right}, op=op)
            return _parsed(tree, "value.math.binary", {"l": left, "r": right}, op=op)

        case "compare_op":
            left = lark_to_cop(kids[0])
            right = lark_to_cop(kids[2])
            op = kids[1].value
            return _parsed(tree, "value.compare", {"l": left, "r": right}, op=op)

        case "unary_op":
            right = lark_to_cop(kids[1])
            op = kids[0].value
            if op == "!!":
                return _parsed(tree, "value.logic.unary", {"r": right}, op=op)
            return _parsed(tree, "value.math.unary", {"r": right}, op=op)

        case "invoke":
            fields = [lark_to_cop(kid) for kid in kids]
            return _parsed(tree, "value.invoke", fields)

        # # Postfix operations (calls and field access)
        # case "postfix":
        #     # postfix: atom call_suffix*
        #     # Build left-to-right: atom, then apply each suffix
        #     result = lark_to_cop(kids[0])  # Start with the atom
        #     for suffix in kids[1:]:
        #         result = _apply_postfix_suffix(tree, result, suffix)
        #     return result

        # case "field_access":
        #     # Handled by _apply_postfix_suffix
        #     raise ValueError("field_access should be handled in postfix context")

        # case "call_struct":
        #     # Handled by _apply_postfix_suffix
        #     raise ValueError("call_struct should be handled in postfix context")

        # case "call_block":
        #     # Handled by _apply_postfix_suffix
        #     raise ValueError("call_block should be handled in postfix context")

        # Identifier and fields
        case "identifier":
            fields = [lark_to_cop(k) for k in kids[::2]]
            return _parsed(tree, "value.identifier", fields)

        case "tokenfield":
            return _parsed(tree, "ident.token", [], value=kids[0].value)
        case "textfield":
            text = kids[0].children[1]
            return _parsed(tree, "ident.text", [], value=text.value)
        case "indexfield":
            return _parsed(tree, "ident.index", [], value=kids[1].value)
        case "indexprfield":
            expr = lark_to_cop(kids[2])
            return _parsed(tree, "ident.indexpr", [expr])
        case "exprfield":
            expr = lark_to_cop(kids[1])
            return _parsed(tree, "ident.expr", [expr])

        case "structure":
            fields = [lark_to_cop(kid) for kid in kids[1:-1]]
            return _parsed(tree, "struct.define", fields)

        case "struct_field":
            if len(kids) == 1:
                value = lark_to_cop(kids[0])
                return _parsed(tree, "struct.posfield", [value])
            name = lark_to_cop(kids[0])
            op = kids[1].value
            value = lark_to_cop(kids[2])
            return _parsed(tree, "struct.namefield", {"n": name, "v": value}, op=op)

        case "struct_decorator":
            name = lark_to_cop(kids[1])
            return _parsed(tree, "struct.decorator", [name])

        case "let_assign":
            name = lark_to_cop(kids[1])
            op = kids[2].value
            value = lark_to_cop(kids[3])
            return _parsed(tree, "struct.letassign", {"n": name, "v": value}, op=op)

        case "block":
            # Signature is shape_fields (all kids except first COLON and last structure)
            sig_fields = [lark_to_cop(kid) for kid in kids[1:-1]]
            signature = _parsed(tree, "shape.define", sig_fields)
            body = lark_to_cop(kids[-1])
            return _parsed(tree, "value.block", {"s": signature, "b": body})

        case "mod_field":
            name = lark_to_cop(kids[0])
            op = kids[1].value
            value = lark_to_cop(kids[2])
            return _parsed(tree, "mod.namefield", {"n": name, "v": value}, op=op)

        case "shape":
            # TILDE shape_spec
            spec = lark_to_cop(kids[1])
            return spec

        case "shape_spec":
            # (identifier | paren_shape) guard_suffix? array_suffix?
            base = lark_to_cop(kids[0])
            # TODO: handle guard_suffix and array_suffix
            return base

        case "paren_shape":
            # PAREN_OPEN shape_content PAREN_CLOSE
            content = lark_to_cop(kids[1])
            return content

        case "shape_content":
            # shape_union | shape_field*
            fields = [lark_to_cop(kid) for kid in kids]
            return _parsed(tree, "shape.define", fields)

        case "shape_union":
            # shape_spec (PIPE shape_spec)+
            # Kids alternate: shape_spec, PIPE, shape_spec, PIPE, ...
            specs = [lark_to_cop(kid) for kid in kids[::2]]  # Skip PIPE tokens
            return _parsed(tree, "shape.union", specs)

        case "shape_field":
            if isinstance(kids[0], lark.Token) and kids[0].type == "TOKENFIELD":
                field_name = kids[0].value
            else:
                field_name = None
            shape_cop = None
            default_cop = None
            # (TOKENFIELD | shape | TOKENFIELD shape) (ASSIGN field_default_value)?
            if len(kids) == 1:  # just name or shape
                if field_name is None:
                    shape_cop = lark_to_cop(kids[0])
            elif len(kids) == 2:  # name and shape
                shape_cop = lark_to_cop(kids[1])
            elif len(kids) == 3:  # name and default value
                if field_name is None:
                    shape_cop = lark_to_cop(kids[0])
                default_cop = lark_to_cop(kids[2])
            elif len(kids) == 4:  # name and shape and default# TOKENFIELD shape ASSIGN default (name, type, and default)
                shape_cop = lark_to_cop(kids[1])
                default_cop = lark_to_cop(kids[3])
            else:
                pass  # Maybe an exception better?
            if shape_cop is None:
                shape_cop = _parsed(None, "value.constant", [], value=comp.shape_any)
                #shape_cop = _make_constant(None, comp.shape_any)
            field_kids = [shape_cop]
            if default_cop:
                field_kids.append(default_cop)
            return _parsed(tree, "shape.field", field_kids, name=field_name)

        # Pass-through rules (no node created, just process children)
        case "start":
            cops = []
            for kid in kids:
                cop = lark_to_cop(kid)
                cops.append(cop)
            return _parsed(tree, "mod.define", cops)
        case _:
            raise ValueError(f"Unhandled grammar rule: {tree.data}")


# cached lark parsers
_parsers = {}

