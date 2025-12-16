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
    "COP_TAGS",
    "cop_module",
    "create_cop",
    "pos_from_lark",
]

import pathlib
import lark
import comp



def parse(source):
    """Parse source into cop structures."""
    parser = _lark_parser("comp")

    # The intermediate lark tree is not really exposed to the api, although
    # if there are parse errors we'll need to interpret them and make sure
    # they are well reported (probably needs a filename arg for messages)
    tree = parser.parse(source)
    cop = _convert_tree(tree)
    return cop


COP_TAGS = [
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


def create_cop(tag_name, **fields):
    """Construct a new cop node"""
    cop_module()
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

def _merge_pos(pos1, pos2):
    """Merge two positions to span both.
    
    Returns position from start of pos1 to end of pos2.
    """
    return (pos1[0], pos1[1], pos2[2], pos2[3])



def _parsed(tag, treetoken, **fields):
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
    cop = create_cop(tag, **fields)
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
            return _parsed("value.number", tree, value=kids[0].value)
        case 'text':
            return _parsed("value.text", tree, value=kids[1])

        # Operators
        case 'binary_op':
            left = _convert_tree(kids[0])
            right = _convert_tree(kids[2])
            op = kids[1].value
            if op in ("==", "!=", "<", "<=", ">", ">="):
                return _parsed("value.compare", tree, left=left, right=right, op=op)
            if op in ("||", "&&"):
                return _parsed("value.logical.binary", tree, left=left, right=right, op=op)
            if op == "??":
                return _parsed("value.fallback", tree, left=left, right=right, op=op)
            return _parsed("value.math.binary", tree, left=left, right=right, op=op)

        case 'unary_op':
            right = _convert_tree(kids[1])
            op = kids[0].value
            if op == "!!":
                return _parsed("value.logic.unary", tree, right=right, op=op)
            return _parsed("value.math.unary", tree, right=right, op=op)

        # Identifier and fields
        case 'identifier':
            fields = [_convert_tree(k) for k in kids[::2]]
            return _parsed("value.identifier", tree, fields=fields)
        
        case 'tokenfield':
            return _parsed("field.token", tree, value=kids[0].value)
        case 'textfield':
            text = kids[0].children[1]
            return _parsed("field.text", tree, value=text.value)
        case 'indexfield':
            return _parsed("field.index", tree, value=kids[1].value)
        case 'indexprfield':
            expr = _convert_tree(kids[2])
            return _parsed("field.indexpr", tree, value=expr)
        case 'exprfield':
            expr = _convert_tree(kids[1])
            return _parsed("field.expression", tree, value=expr)
        # case 'computefield':
        #     # "'" expression "'" - extract the expression (middle child)
        #     expr = _convert_tree(kids[1])
        #     return comp.ast.ComputeField(expr)


        # # === HANDLE OPERATIONS ===
        # case 'grab_atom':
        #     # "!grab" handle_reference
        #     handle_ref = _convert_tree(kids[1])
        #     node = comp.ast.GrabOp(handle_ref)
        #     return _apply_position(node, tree)

        # case 'drop_op':
        #     # "!drop" _qualified
        #     target = _convert_tree(kids[1])
        #     node = comp.ast.DropOp(target)
        #     return _apply_position(node, tree)

        # case 'disarm_op':
        #     # "!disarm" resource_expr
        #     expr = _convert_tree(kids[1])
        #     node = comp.ast.DisarmOp(expr)
        #     return _apply_position(node, tree)


        # # === STRUCTURES ===
        # case 'structure':
        #     # LBRACE structure_op* RBRACE
        #     # Filter out the braces (tokens) and convert the structure_op children
        #     ops = [_convert_tree(kid) for kid in kids if isinstance(kid, lark.Tree)]
        #     return comp.ast.Structure(ops)

        # case 'block_structure':
        #     # COLON_BLOCK_START structure_op* RBRACE
        #     # Similar to structure, but creates a Block node for deferred execution
        #     ops = [_convert_tree(kid) for kid in kids if isinstance(kid, lark.Tree)]
        #     structure = comp.ast.Structure(ops)
        #     return comp.ast.Block(structure)
        
        # case 'block_pipeline':
        #     # COLON_PIPELINE_BLOCK pipeline RBRACKET
        #     # Shorthand for :[pipeline] which desugars to :{[pipeline]}
        #     # A block containing a single unnamed pipeline expression
        #     # kids[0] is the pipeline Tree, filter out tokens (COLON_PIPELINE_BLOCK, RBRACKET)
        #     pipeline_tree = [kid for kid in kids if isinstance(kid, lark.Tree)][0]
        #     pipeline = _convert_tree(pipeline_tree)
        #     structure = comp.ast.Structure([comp.ast.FieldOp(pipeline, None)])
        #     return comp.ast.Block(structure)

        # case 'structure_assign':
        #     # _qualified _assignment_op expression
        #     # For field assignments, convert identifier to String (simple) or list of Strings (deep path)
        #     key = _convert_field_assignment_key(kids[0])
        #     # Skip assignment operator (kids[1])
        #     value = _convert_tree(kids[2])
        #     return comp.ast.FieldOp(value, key)

        # case 'structure_unnamed':
        #     # expression
        #     value = _convert_tree(kids[0])
        #     return comp.ast.FieldOp(value, None)

        # case 'structure_spread':
        #     # SPREAD expression
        #     expr = _convert_tree(kids[1])
        #     return comp.ast.SpreadOp(expr)

        # # === PIPELINES ===
        # case 'pipeline_seeded':
        #     # LBRACKET _prepipeline_expression pipeline RBRACKET
        #     seed = _convert_tree(kids[1])
        #     ops = _convert_children(kids[2].children)
        #     node = comp.ast.Pipeline(seed, ops)
        #     return _apply_position(node, tree)

        # case 'pipeline_unseeded':
        #     # LBRACKET pipeline RBRACKET
        #     ops = _convert_children(kids[1].children)
        #     node = comp.ast.Pipeline(None, ops)
        #     return _apply_position(node, tree)

        # case 'pipe_func':
        #     # function_reference function_arguments
        #     # Extract the function path directly without converting (function_reference isn't a value node)
        #     func_path, func_namespace = _extract_reference_path(kids[0].children)
        #     func_name = ".".join(func_path)
        #     # function_arguments contains structure_op* - convert to Structure if non-empty
        #     if len(kids) > 1 and kids[1].children:
        #         ops = [_convert_tree(op) for op in kids[1].children]
        #         args = comp.ast.Structure(ops)
        #     else:
        #         args = None
        #     node = comp.ast.PipeFunc(func_name, args, func_namespace)
        #     return _apply_position(node, tree)

        # case 'pipe_struct':
        #     # PIPE_STRUCT structure_op* RBRACE
        #     ops = _convert_children(kids[1:-1])  # Skip PIPE_STRUCT and RBRACE
        #     struct = comp.ast.Structure(ops)
        #     return comp.ast.PipeStruct(struct)

        # case 'pipe_fallback':
        #     # PIPE_FALLBACK expression
        #     fallback = _convert_tree(kids[1])
        #     return comp.ast.PipeFallback(fallback)

        # # === SHAPE DEFINITIONS ===
        # case 'shape_definition':
        #     # BANG_SHAPE shape_path ASSIGN shape_body
        #     path, is_private = _extract_path_and_privacy_from_tree(kids[1])
        #     fields_or_type = _convert_shape_body(kids[3])
            
        #     # If fields_or_type is a single shape type (not a list), wrap it as a positional field
        #     # This handles type aliases like: !shape ~alias = ~other or !shape ~nil-block = ~:{}
        #     if not isinstance(fields_or_type, list):
        #         # Create a ShapeFieldDef with no name (positional) and the type as the shape_ref
        #         fields = [comp.ast.ShapeFieldDef(name=None, shape_ref=fields_or_type, default=None)]
        #     else:
        #         fields = fields_or_type
            
        #     return comp.ast.ShapeDef(path, fields, is_private=is_private)

        # case 'shape_field_def':
        #     # TOKEN QUESTION? shape_type? (ASSIGN expression)?
        #     name = None
        #     shape_ref = None
        #     default = None
        #     optional = False

        #     i = 0
        #     if i < len(kids) and isinstance(kids[i], lark.Token) and kids[i].type == 'TOKEN':
        #         name = kids[i].value
        #         i += 1

        #     if i < len(kids) and isinstance(kids[i], lark.Token) and kids[i].type == 'QUESTION':
        #         optional = True
        #         i += 1

        #     # Look for shape_type (could be various shape-related rules)
        #     if i < len(kids) and isinstance(kids[i], lark.Tree):
        #         if kids[i].data in ('shape_type', 'shape_type_atom', 'shape_reference',
        #                            'tag_reference', 'shape_inline', 'shape_union'):
        #             shape_ref = _convert_tree(kids[i])
        #             i += 1

        #     # Look for ASSIGN token and default value
        #     if i < len(kids) and isinstance(kids[i], lark.Token) and kids[i].type == 'ASSIGN':
        #         i += 1
        #         if i < len(kids):
        #             default = _convert_tree(kids[i])

        #     return comp.ast.ShapeFieldDef(name, shape_ref, default, optional)

        # case 'shape_spread':
        #     # SPREAD shape_type
        #     # For now, we'll handle spreads as a special kind of field
        #     # The actual spread expansion happens at runtime
        #     shape = _convert_tree(kids[1])
        #     return comp.ast.ShapeFieldDef(None, shape, None, is_spread=True)  # Spread field

        # case 'shape_reference':
        #     # Already handled above, but repeated for completeness
        #     path, namespace = _extract_reference_path(kids)
        #     return comp.ast.ShapeRef(path, namespace)

        # case 'shape_inline':
        #     # TILDE LBRACE shape_field* RBRACE
        #     # Empty inline shape ~{} matches only empty structs (equivalent to ~nil)
        #     # Non-empty inline shapes define expected struct fields
        #     fields = _convert_children(kids[2:-1]) if len(kids) > 3 else []  # Skip TILDE, LBRACE, RBRACE
        #     if not fields:
        #         # Empty shape ~{} - equivalent to ~nil (matches only empty structs)
        #         return comp.ast.ShapeRef(["nil"])
        #     # Non-empty inline shape - create InlineShape node
        #     return comp.ast.InlineShape(fields)

        # case 'shape_block':
        #     # TILDE COLON_BLOCK_START shape_field* RBRACE
        #     # Represents a block type ~:{input-shape}
        #     # The fields describe the input structure the block expects
        #     fields = _convert_children(kids[2:-1]) if len(kids) > 3 else []  # Skip TILDE, COLON_BLOCK_START, RBRACE
        #     # Create a BlockShape node to represent this type
        #     return comp.ast.BlockShape(fields)

        # case 'shape_union':
        #     # shape_type_atom (PIPE shape_type_atom)+
        #     # Need to convert tag_reference to TagShape
        #     members = []
        #     for kid in kids:
        #         if isinstance(kid, lark.Tree):
        #             # Check if this is a tag_reference that needs converting
        #             if kid.data == 'tag_reference':
        #                 path, namespace = _extract_reference_path(kid.children)
        #                 node = comp.ast.TagShape(path, namespace)
        #                 members.append(_apply_position(node, kid))
        #             else:
        #                 members.append(_convert_tree(kid))
        #     return comp.ast.ShapeUnion(members)

        # # Pass-through for shape type wrappers
        # case 'shape_type_atom' | 'morph_type_base':
        #     # Special handling: if child is a tag_reference, convert to TagShape
        #     if len(kids) == 1 and isinstance(kids[0], lark.Tree) and kids[0].data == 'tag_reference':
        #         # Extract path and namespace from tag_reference
        #         path, namespace = _extract_reference_path(kids[0].children)
        #         node = comp.ast.TagShape(path, namespace)
        #         return _apply_position(node, kids[0])
        #     # Special handling: if child is a handle_reference, convert to HandleShape
        #     if len(kids) == 1 and isinstance(kids[0], lark.Tree) and kids[0].data == 'handle_reference':
        #         # Extract path and namespace from handle_reference
        #         path, namespace = _extract_reference_path(kids[0].children)
        #         node = comp.ast.HandleShape(path, namespace)
        #         return _apply_position(node, kids[0])
        #     # Otherwise pass through
        #     if len(kids) == 1:
        #         return _convert_tree(kids[0])
        #     return _convert_children(kids)

        # case 'shape_type' | 'shape_body' | 'morph_type':
        #     if len(kids) == 1:
        #         return _convert_tree(kids[0])
        #     # Multiple children means union or complex structure
        #     return _convert_children(kids)


        # # === PASS-THROUGH / UNWRAP ===
        # case ('tag_value' | 'tag_arithmetic' | 'tag_term' | 'tag_bitwise' |
        #       'tag_comparison' | 'tag_unary' | 'tag_atom' | 'module_value' |
        #       'or_expr' | 'and_expr' | 'not_expr' | 'comparison' |
        #       'morph_expr' | 'arith_expr' | 'term' | 'unary' | 'power' |
        #       'atom_in_expr' | '_prepipeline_expression' | 'pipeline' |
        #       'function_arguments' | '_structure_content'):
        #     # These are just precedence/grouping rules - pass through
        #     if len(kids) == 1:
        #         return _convert_tree(kids[0])
        #     # If multiple children, it's an operator that should have been caught above
        #     return _convert_children(kids)

        # case 'atom_field':
        #     # atom_in_expr "." identifier_next_field
        #     # This is a field access on an expression result
        #     # Recursively flatten: [base, field1, field2, ...]
        #     fields = []
        #     current = tree
        #     while current.data == 'atom_field':
        #         # Last child is the field
        #         field_tree = current.children[-1]
        #         field = _convert_identifier_next_field(field_tree)
        #         fields.append(field)
        #         current = current.children[0]

        #     # Current is now the base atom - convert it
        #     base_fields = []
        #     if current.data == 'identifier':
        #         # Base is already an identifier, extract its fields
        #         base_id = _convert_tree(current)
        #         base_fields = base_id.fields
        #     else:
        #         # Base is another expression - we need to treat this differently
        #         # For now, just return the base and field access
        #         # TODO: Handle this case properly
        #         base = _convert_tree(current)
        #         return base

        #     # Combine base fields with additional fields
        #     fields.reverse()
        #     all_fields = base_fields + fields
        #     return comp.ast.Identifier(all_fields)

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

