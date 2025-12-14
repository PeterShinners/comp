"""AST node definitions as Value structures.

All AST nodes are represented as tagged Value structures. This allows the
AST itself to be manipulated as Comp data - serialized, pattern-matched,
transformed using normal Comp operations.

Source Position:
    Every AST node includes position info:
        start_line, start_col, end_line, end_col
    These map to Lark's Token.line, Token.column, Token.end_line, Token.end_column

"""

__all__ = [
    "TAG_NAMES",
    "ast_module",
    "ast_node",
    "pos_from_lark",
]

import lark
import comp


TAG_NAMES = [
    "value.number", # (value)
    "value.text", # (value)
    "value.identifier", # (fields)
    "value.struct", # (decorations, definitions)
    "value.shape.def", # (fields, checks, array)
    "value.shape.union", # (shapes, checks, array, default)
    "value.shape.ref", # (identifier, checks, array)
    "value.block", # (signature, struct)

    "definition.struct", # (name, op, value)
    "definition.mod", # (name, op, value)
    "definition.shape", # (name, op, shape, checks, array, default)

    "field.token", # (value)
    "field.index", # (value)
    "field.indexpr", # (value)
    "field.expression", # (value)
    "field.text", # (value)

    "value.math.unary", # (op, right)
    "value.math.binary", # (op, left, right)
    "value.compare", # (op, left, right)
    "value.logic.binary", # (op, left, right)
    "value.logic.unary", # (op, right)
    "value.call", # (value, args)
    "value.pipe", # (links)
    "value.fallback", # (left, right)
    "value.postfix", # (left, identifier)

    "value.transact", # (handles)
    "value.handle", # (op, values)
]


_astmodule = None
_tagnames = {}

def ast_module():
    """Create and populate the ast module"""
    global _astmodule
    if _astmodule is None:
        _astmodule = comp.Module('ast')
        for name in TAG_NAMES:
            tag = comp.TagDef(name, False)
            _astmodule.publicdefs.append(tag)
            ref = comp.Tag(tag.qualified, 'ast', _astmodule)
            _tagnames[name] = ref
            # Eventually want real shapes to go with each of these,
            # but for now we freestyle it.

        _astmodule.finalize()
    return _astmodule


def ast_node(tag_name, **fields):
    """Construct a new ast node"""
    ast_module()
    tag = _tagnames[tag_name]
    data = {comp.Unnamed(): tag}
    for key, value in fields.items():
        data[key] = value
    value = comp.Value.from_python(data)
    return value


def pos_from_lark(treetoken):
    """Create the position tuple from a lark Tree or Token value."""
    if isinstance(treetoken, lark.Token):
        token = treetoken
        return (
            token.line,
            token.column,
            token.end_line or token.line,
            token.end_column or token.column,
        )
    elif isinstance(treetoken, lark.Tree):
        meta = treetoken.meta
        return (
            meta.line,
            meta.column,
            meta.end_line or meta.line,
            meta.end_column or meta.column,
        )

def merge_pos(pos1, pos2):
    """Merge two positions to span both.
    
    Returns position from start of pos1 to end of pos2.
    """
    return (pos1[0], pos1[1], pos2[2], pos2[3])


