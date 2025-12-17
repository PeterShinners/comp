"""Parse code into cop (comp operators) structure.

The cops are similar to an ast structure. They are designed to be easy
to manipulate, assemble, and transform. The cop objects are simple comp
structures and easy to serialize.

This data is usually generated from source with `comp.parse`. Each
cop structure tracks the position it was generated from in the original
source string. Cop data is built into executable code objects with `comp.build`.

Cop structures will eventually reference literals and other comp.Values
directory, but after parsing they will contain only other cop structures.

"""

__all__ = [
    "parse",
    "resolve",
    "COP_TAGS",
    "cop_module",
    "create_cop",
    "pos_from_lark",
]

import decimal
import pathlib
import lark
import comp



def parse(source):
    """Parse source into cop structures."""
    parser = _lark_parser("comp")

    # The intermediate lark tree is not really exposed to the api, although
    # if there are parse errors we'll need to interpret them and make sure
    # they are well reported (probably needs a filename arg for messages)
    # The lark tree is considered too unstable
    tree = parser.parse(source)
    cop = _convert_tree(tree)
    return cop


def resolve(cop, namespace):
    """Resolve cop structures into final form.

    Generate a new cop structure with references and literals resolved.
    This can also do lightweight optimizations, but those are intended to
    be done by separate cop transforms.

    Args:
        cop: (Value) Cop structure to resolve
        namespace: (Value) Namespace to use for resolving identifiers
    Returns:
        (Value) Modified cop structure
    """
    # Should this node just be swapped completely?
    tag = cop.positional(0).data.qualified

    kids = []
    changed = False
    for kid in _cop_kids(cop):
        res = resolve(kid, namespace)
        if res is not kid:
            kids.append(res)
            changed = True
        else:
            kids.append(kid)

    match tag:
        case "value.number":
            literal = cop.to_python("value")
            value = decimal.Decimal(literal)
            constant = comp.Value.from_python(value)
            return _resolved("value.constant", cop, value=constant)
        case "value.number":
            literal = cop.to_python("value")
            value = decimal.Decimal(literal)
            constant = comp.Value.from_python(value)
            return _resolved("value.constant", cop, value=constant)
        case "value.math.unary":
            op = cop.to_python("op")
            if op == "+":
                return kids[0]
            value = _get_constant(kids[0])
            if value is not None:
                modified = comp.math_unary(op, value)
                return _resolved("value.constant", cop, value=modified)
        case "value.math.binary":
            op = cop.to_python("op")
            left = _get_constant(kids[0])
            right = _get_constant(kids[1])
            if left is not None and right is not None:
                modified = comp.math_binary(op, left, right)
                return _resolved("value.constant", cop, value=modified)

    if not changed:
        return cop
    
    copied = dict(cop.data)
    if kids:
        copied[comp.Value("kids")] = comp.Value.from_python(kids)
    return comp.Value(copied)


def _cop_kids(cop):
    """Get kids of a cop node."""
    try:
        kids = list(cop.field("kids").data.values())
        return kids
    except KeyError:
        return []


def _resolved(tag, original, **fields):
    """Create a derived cop node with position from existing."""
    orig_tag = original.positional(0).data.qualified
    changed = tag != orig_tag
    for key, value in fields.items():
        if changed:
            break
        prev = original.field(key)
        changed = prev != value
    if not changed:
        return original

    # need to merge positions from original
    #fields["pos"] = pos
    cop = create_cop(tag, [], **fields)
    return cop


def _get_constant(cop):
    """Check if a cop node is a constant value."""
    tag = cop.positional(0).data.qualified
    if tag == "value.constant":
        return cop.field("value")
    return None


COP_TAGS = [
    "shape.identifier", # (identifier, checks, array, default)
    "shape.union", # (shapes, checks, array, default)
    "shape.define", # (fields, checks, array)
    "shape.field", # (name, shape, default)

    "struct.define", # (kids)
    "struct.field", # (name, op, kids) 1 kid

    "mod.field", # (name, op, kids) 1 kid

    "value.identifier", # (kids)
    "ident.token", # (value)
    "ident.index", # (value)
    "ident.indexpr", # (value)
    "ident.expr", # (value)
    "ident.text", # (value)

    "value.number", # (value)
    "value.text", # (value)
    "value.block", # (kids)  kids; signature, body
    "value.math.unary", # (op, kids)  1 kid
    "value.math.binary", # (op, kids)  2 kids
    "value.compare", # (op, kids)  2 kids
    "value.logic.binary", # (op, kids)  2 kids
    "value.logic.unary", # (op, kids)  1 kids
    "value.call", # (kids)  kids; callable, args
    "value.pipe", # (kids)
    "value.fallback", # (kids)
    "value.postfix", # (left, kids)

    "value.transact", # (kids)
    "value.handle", # (op, kids) grab/drop/pull/etc

    "value.constant", # (value) precompiled constant value
]


_astmodule = None
_tagnames = {}


def cop_module():
    """Create and populate the cop module"""
    global _astmodule
    if _astmodule is None:
        _astmodule = comp.Module('cop')
        for name in COP_TAGS:
            tag = comp.TagDef(name, False)
            _astmodule.publicdefs.append(tag)
            ref = comp.Tag(tag.qualified, 'cop', _astmodule)
            _tagnames[name] = ref
            # Eventually want real shapes to go with each of these,
            # but for now we freestyle it.

        _astmodule.finalize()
    return _astmodule


def create_cop(tag_name, kids, **fields):
    """Construct a new cop node"""
    cop_module()
    tag = _tagnames[tag_name]
    data = {comp.Unnamed(): tag}
    for key, value in fields.items():
        data[key] = value
    data["kids"] = comp.Value.from_python(kids)
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

def _merge_pos(pos1, pos2):
    """Merge two positions to span both.
    
    Returns position from start of pos1 to end of pos2.
    """
    return (pos1[0], pos1[1], pos2[2], pos2[3])



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
    elif isinstance(treetoken, lark.Tree):
        meta = treetoken.meta
        pos = (
            meta.line,
            meta.column,
            meta.end_line or meta.line,
            meta.end_column or meta.column,
        )

    fields["pos"] = pos
    cop = create_cop(tag, kids, **fields)
    return cop


def _convert_tree(tree):
    """Convert a single Lark tree/token to a cop node.

    This will often recurse into child nodes of the tree.
    Args:
        tree: Lark Tree or Token to convert
    Returns:
        cop node
    """
    # Handle tokens (terminals)
    if isinstance(tree, lark.Token):
        raise ValueError(f"Unhandled grammar token: {tree}")
        match tree.type:
            # case 'NUMBER' | 'INTBASE' | 'decimal.DECIMAL':
            #     return _convert_number(tree)
            # case 'TOKEN':
            #     return tree.value
            # case 'INDEXFIELD':
            #     # Extract number from #123 format
            #     return int(tree.value[1:])
            case _:
                # Most tokens are just passed as strings
                return tree.value

    # Handle trees (non-terminals)
    assert isinstance(tree, lark.Tree)
    kids = tree.children
    match tree.data:
        case 'paren_expr':
            # LPAREN expression RPAREN - return the expression
            return _convert_tree(kids[1])

        # Literals
        case 'number':
            return _parsed(tree, "value.number", [], value=kids[0].value)
        case 'text':
            return _parsed(tree, "value.text", [], value=kids[1])

        # Operators
        case 'binary_op':
            left = _convert_tree(kids[0])
            right = _convert_tree(kids[2])
            op = kids[1].value
            if op in ("==", "!=", "<", "<=", ">", ">="):
                return _parsed(tree, "value.compare", {"l":left, "r":right}, op=op)
            if op in ("||", "&&"):
                return _parsed(tree, "value.logical.binary", {"l":left, "r":right}, op=op)
            if op == "??":
                return _parsed(tree, "value.fallback", {"l":left, "r":right}, op=op)
            return _parsed(tree, "value.math.binary", {"l":left, "r":right}, op=op)

        case 'unary_op':
            right = _convert_tree(kids[1])
            op = kids[0].value
            if op == "!!":
                return _parsed(tree, "value.logic.unary", {"r": right}, op=op)
            return _parsed(tree, "value.math.unary", {"r": right}, op=op)

        # Identifier and fields
        case 'identifier':
            fields = [_convert_tree(k) for k in kids[::2]]
            return _parsed(tree, "value.identifier", [], fields=fields)
        
        case 'tokenfield':
            return _parsed(tree, "ident.token", [], value=kids[0].value)
        case 'textfield':
            text = kids[0].children[1]
            return _parsed(tree, "ident.text", [], value=text.value)
        case 'indexfield':
            return _parsed(tree, "ident.index", [], value=kids[1].value)
        case 'indexprfield':
            expr = _convert_tree(kids[2])
            return _parsed(tree, "ident.indexpr", [expr])
        case 'exprfield':
            expr = _convert_tree(kids[1])
            return _parsed(tree, "ident.expr", [expr])

        case 'structure':
            fields = [_convert_tree(kid) for kid in kids[1:-1]]
            return _parsed(tree, "struct.define", fields)

        case 'struct_field':
            if len(kids) == 1:
                name = None
                op = ""
                value = _convert_tree(kids[0])
            else:
                name = _convert_tree(kids[0])
                op = kids[1].value
                value = _convert_tree(kids[2])
            return _parsed(tree, "struct.field", value, name=name, op=op)


        # Pass-through rules (no node created, just process children)
        case 'start':
            if kids:
                return _convert_tree(kids[0]) if len(kids) == 1 else _convert_tree(kids)
            return []

        case _:
            raise ValueError(f"Unhandled grammar rule: {tree.data}")



_parsers = {}


def _lark_parser(name):
    """Get globally shared lark parser.
    Args:
        name (str): name of the grammar file (without .lark)
    Returns:
        lark.Parser
    """
    parser = _parsers.get(name)
    if parser is not None:
        return parser
        
    path = f"lark/{name}.lark"
    parser = lark.Lark.open(path, rel_to=__file__, parser="lalr", 
                propagate_positions=True)
    _parsers[name] = parser
    return parser

