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
    "create_cop",
    "create_reference_cop",
    "cop_module",
    "cop_tag",
    "cop_kids",
    "cop_unparse",
    "cop_unparse_reference",
    "lark_parser",
]

import decimal
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


def cop_fold(cop, namespace=None):
    """Fold cop constants

    This is a lightweight optimizations that removes computations on constants.
    This will not modify any existing nodes, only edit copies. If there are
    no changes the original will be returned.

    Args:
        cop: (Value) Cop structure to resolve
        namespace: (dict) Optional namespace dict {name: DefinitionSet} for resolving references
    Returns:
        (Value) Modified cop structure
    """
    tag = cop.positional(0).data.qualified

    kids = []
    changed = False
    for kid in cop_kids(cop):
        res = cop_fold(kid, namespace)
        if res is not kid:
            kids.append(res)
            changed = True
        else:
            kids.append(kid)

    match tag:
        case "value.reference":
            # Try to fold reference to constant if definition has a value
            if namespace is not None:
                try:
                    qualified = cop.field("qualified").data
                    definition_set = namespace.get(qualified)
                    if definition_set is not None:
                        # Get scalar definition (unambiguous single definition)
                        defn = definition_set.scalar()
                        if defn is not None and defn.value is not None:
                            # Substitute with constant
                            return _make_constant(cop, defn.value)
                except (KeyError, AttributeError):
                    pass
            # Can't fold, return as-is
            return cop
        case "value.text":
            literal = cop.to_python("value")
            constant = comp.Value.from_python(literal)
            return _make_constant(cop, constant)
        case "value.number":
            literal = cop.to_python("value")
            value = decimal.Decimal(literal)
            constant = comp.Value.from_python(value)
            return _make_constant(cop, constant)
        case "value.math.unary":
            op = cop.to_python("op")
            if op == "+":
                return kids[0]
            value = _get_constant(kids[0])
            if value is not None:
                modified = comp.math_unary(op, value)
                return _make_constant(cop, modified)
        case "value.math.binary":
            op = cop.to_python("op")
            left = _get_constant(kids[0])
            right = _get_constant(kids[1])
            if left is not None and right is not None:
                modified = comp.math_binary(op, left, right)
                return _make_constant(cop, modified)
        case "struct.define":
            struct = {}
            for field_cop in kids:
                field_tag = field_cop.positional(0).data.qualified
                field_kids = cop_kids(field_cop)
                if field_tag == "struct.posfield":
                    key = comp.Unnamed()
                    value = _get_constant(field_kids[0])
                elif field_tag == "struct.namedfield":
                    key = _get_simple_identifier(field_kids[0])
                    value = _get_constant(field_kids[1])
                else:
                    key = value = None
                # else struct.decorators, no constant folding for now
                if value is None:
                    struct = None
                    break
                struct[key] = value
            if struct is not None:
                value = comp.Value(struct)
                return _make_constant(cop, value)
            # Can't fold - has non-constant fields, leave unchanged
        case "shape.define":
            # Build a Shape with FieldDefs from shape.field children
            # Or a ShapeUnion if it contains a single shape.union child
            if len(kids) == 1 and cop_tag(kids[0]) == "shape.union":
                # This is a union definition like ~(tree | nil)
                union_kids = cop_kids(kids[0])
                shape_union = comp.ShapeUnion(union_kids)
                value = comp.Value.from_python(shape_union)
                return _make_constant(cop, value)

            # Otherwise try to build a Shape struct
            shape = comp.Shape("", False)  # Anonymous inline shape
            for field_cop in kids:
                field_tag = cop_tag(field_cop)
                if field_tag == "shape.field":
                    field_name = field_cop.to_python("name")
                    field_kids = cop_kids(field_cop)
                    field_shape = field_kids[0]
                    field_default = field_kids[1] if len(field_kids) > 1 else None
                    field = comp._shape.ShapeField(name=field_name, shape=field_shape, default=field_default)
                    shape.fields.append(field)
                elif field_tag == "shape.union":
                    # Union types inside struct fields - can't fold yet
                    shape = None
                    break
                else:
                    # Unknown shape construct - skip folding
                    shape = None
                    break
            if shape is not None:
                # Wrap the shape definition in a Value
                value = comp.Value.from_python(shape)
                return _make_constant(cop, value)

    if not changed:
        return cop

    copied = dict(cop.data)
    if kids:
        copied[comp.Value("kids")] = comp.Value.from_python(kids)
    return comp.Value(copied)


def cop_resolve(cop, namespace):
    """Resolve cop structures into final form.

    Generate a new cop structure with references and literals resolved.
    This will not modify any existing nodes, only edit copies. If there are
    no changes the original will be returned.

    Args:
        cop: (Value) Cop structure to resolve
        namespace: (Value) Namespace to use for resolving identifiers
    Returns:
        (Value) Modified cop structure
    """
    tag = cop.positional(0).data.qualified

    kids = []
    changed = False
    for kid in cop_kids(cop):
        res = cop_resolve(kid, namespace)
        if res is not kid:
            kids.append(res)
            changed = True
        else:
            kids.append(kid)

    match tag:
        case "value.identifier":
            pass

    if not changed:
        return cop

    copied = dict(cop.data)
    if kids:
        copied[comp.Value("kids")] = comp.Value.from_python(kids)
    return comp.Value(copied)


def _make_constant(original, value):
    """Create a derived constant cop node."""
    value.cop = original
    cop = _resolved("value.constant", original, value=value)
    return cop


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
    # fields["pos"] = pos
    cop = create_cop(tag, [], **fields)
    return cop


def _get_constant(cop):
    """Check if a cop node is a constant value."""
    tag = cop.positional(0).data.qualified
    if tag == "value.constant":
        return cop.field("value")
    return None


def _get_simple_identifier(cop):
    """Get the simple name of a single named identifier"""
    tag = cop.positional(0).data.qualified
    if tag != "value.identifier":
        return None

    kids = list(cop.field("kids").data.values())
    if len(kids) != 1:
        return None

    name_cop = kids[0]
    name_tag = name_cop.positional(0).data.qualified
    match name_tag:
        case "ident.token":
            name = name_cop.field("value")
            return name
        case "ident.text" | "ident.expr":
            name_kids = cop_kids(name_cop)
            name = _get_constant(name_kids[0])
            if name is not None:
                return name
    return None


_astmodule = None
_tagnames = {}


def cop_module():
    """Create and populate the cop module"""
    global _astmodule
    if _astmodule is None:
        # Create a minimal ModuleSource for cop module
        source = type('obj', (object,), {'resource': 'cop', 'content': ''})()
        _astmodule = comp.Module(source)
        _astmodule._definitions = {}
        for name in COP_TAGS:
            tag_def = comp.Tag(name, False)
            tag_def.module = _astmodule
            # Wrap in Value and store in definitions
            value = comp.Value.from_python(tag_def)
            _astmodule._definitions[name] = value
            # Store Tag for cop node construction
            _tagnames[name] = tag_def
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


def create_reference_cop(definition, identifier_cop=None, import_namespace=None):
    """Create a value.reference COP node pointing to a Definition.

    Args:
        definition: Definition object to reference
        identifier_cop: Optional original identifier COP (for position and name preservation)
        import_namespace: Optional import namespace name (e.g., "pg" for imports)

    Returns:
        Value: COP node with tag value.reference
    """
    # Store qualified name and module_id as strings (not COP nodes)
    fields = {
        "qualified": definition.qualified,
        "module_id": definition.module_id
    }

    # Track import namespace if provided
    if import_namespace is not None:
        fields["namespace"] = import_namespace

    # Preserve position from original identifier if available
    if identifier_cop is not None and hasattr(identifier_cop, 'field'):
        try:
            pos = identifier_cop.field("pos")
            if pos is not None:
                fields["pos"] = pos
        except (KeyError, AttributeError):
            pass

    return create_cop("value.reference", [], **fields)


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

    cop = create_cop(tag, kids, **fields)
    return cop


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

        # Module-level field assignment
        case "mod_field":
            name = lark_to_cop(kids[0])
            op = kids[1].value
            value = lark_to_cop(kids[2])
            return _parsed(tree, "mod.namefield", {"n": name, "v": value}, op=op)

        # Shape definitions
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


_parsers = {}


def cop_tag(cop_node):
    """Get the qualified tag name from a COP node.

    Args:
        cop_node: Value representing a COP node

    Returns:
        str: Qualified tag name like "mod.define", or None if invalid
    """
    try:
        tag = cop_node.positional(0)
        return tag.data.qualified
    except (AttributeError, KeyError, TypeError):
        return None


def cop_kids(cop_node):
    """Get the kids dict from a COP node.

    Args:
        cop_node: Value representing a COP node

    Returns:
        list: Cop node kids or empty list
    """
    try:
        kids = cop_node.field("kids")
        return list(kids.data.values())
    except (KeyError, AttributeError, TypeError):
        return []


def cop_unparse(cop):
    """Convert COP node back to source text.

    Args:
        cop: COP node

    Returns:
        str: Source text representation
    """
    tag = cop_tag(cop)
    if not tag:
        return str(cop)
    match tag:
        case "mod.define":
            parts = []
            for kid in cop_kids(cop):
                parts.append(cop_unparse(kid))
            return '\n'.join(parts)

        case "mod.namefield":
            kids = cop_kids(cop)
            name = cop_unparse(kids[0])
            value = cop_unparse(kids[1])
            return f"{name} = {value}"

        case "value.identifier":
            parts = []
            for kid in cop_kids(cop):
                parts.append(cop_unparse(kid))
            return '.'.join(parts)

        case "ident.token" | "ident.text":
            return cop.field("value").data

        case "value.number":
            return str(cop.field("value").data)

        case "value.text":
            text = cop.field("value").data
            if '\n' in text:
                return f'"""{text}"""'
            return f'"{text}"'

        case "value.constant":
            value = cop.field("value")
            return value.format()

        case "value.reference":
            return cop_unparse_reference(cop)

        case "value.block":
            kids = cop_kids(cop)
            if len(kids) == 2:
                sig = cop_unparse(kids[0])
                body = cop_unparse(kids[1])
                return f":{sig} ({body})"
            return ":(...x)"

        case "shape.define":
            kids = cop_kids(cop)
            if not kids:
                return "~()"
            parts = []
            for kid in kids:
                parts.append(cop_unparse(kid))
            return f"~({' '.join(parts)})"

        case "shape.field":
            name = cop.to_python("name") or ""
            kids = cop_kids(cop)
            if cop_tag(kids[0]) != "value.constant" or kids[0].field("value").data is not comp.shape_any:
                shape = "~" + cop_unparse(kids[0])
            else:
                shape = ""
            if len(kids) > 1:
                default = cop_unparse(kids[1])
                return f"{name}{shape}={default}"
            return f"{name}{shape}"

        case "shape.union":
            kids = cop_kids(cop)
            parts = [cop_unparse(kid) for kid in kids]
            return '|'.join(parts)

        case "shape.identifier":
            kids = cop_kids(cop)
            return cop_unparse(kids[0]) if kids else ""

        case "struct.define":
            kids = cop_kids(cop)
            if not kids:
                return "()"
            parts = []
            for kid in kids:
                parts.append(cop_unparse(kid))
            return f"({' '.join(parts)})"

        case "struct.posfield":
            kids = cop_kids(cop)
            return cop_unparse(kids[0]) if kids else ""

        case "struct.namefield":
            kids = cop_kids(cop)
            name = cop_unparse(kids[0])
            value = cop_unparse(kids[1])
            return f"{name}={value}"

        case "struct.letassign":
            kids = cop_kids(cop)
            name = cop_unparse(kids[0])
            value = cop_unparse(kids[1])
            return f"!let {name} = {value}"

        case "struct.decorator":
            kids = cop_kids(cop)
            name = cop_unparse(kids[0])
            return f"|{name}"

        case "value.math.binary":
            op = cop.field("op").data
            kids = cop_kids(cop)
            left = cop_unparse(kids[0])
            right = cop_unparse(kids[1])
            return f"{left}{op}{right}"

        case "value.math.unary":
            op = cop.field("op").data
            kids = cop_kids(cop)
            return f"{op}{cop_unparse(kids[0])}"

        case "value.compare":
            op = cop.field("op").data
            kids = cop_kids(cop)
            left = cop_unparse(kids[0])
            right = cop_unparse(kids[1])
            return f"{left} {op} {right}"

        case "value.logic.binary":
            op = cop.field("op").data
            kids = cop_kids(cop)
            left = cop_unparse(kids[0])
            right = cop_unparse(kids[1])
            return f"{left} {op} {right}"

        case "value.logic.unary":
            op = cop.field("op").data
            kids = cop_kids(cop)
            return f"{op} {cop_unparse(kids[0])}"

        case "value.invoke":
            kids = cop_kids(cop)
            callable_part = cop_unparse(kids[0])
            args = ' '.join(cop_unparse(k) for k in kids[1:])
            return f"{callable_part}({args})" if args else f"{callable_part}()"

        case "value.pipe":
            kids = cop_kids(cop)
            parts = [cop_unparse(k) for k in kids]
            return ' | '.join(parts)

        case "stmt.assign":
            kids = cop_kids(cop)
            lvalue = cop_unparse(kids[0])
            rvalue = cop_unparse(kids[1])
            return f"{lvalue} = {rvalue}"

        case _:
            return f"<{tag}>"


def cop_unparse_reference(cop):
    """Unparse a value.reference COP node to show the referenced definition.

    Args:
        cop: value.reference COP node

    Returns:
        str: Formatted reference using qualified name or import namespace
    """
    try:
        # Get qualified name from the reference
        qualified = cop.field("qualified").data

        # Try to get import namespace first (e.g., "pg.display")
        try:
            namespace = cop.field("namespace")
            if namespace is not None:
                # Use namespace prefix for the reference
                return f"{namespace.data}.{qualified}"
        except (KeyError, AttributeError):
            pass

        # Otherwise just use qualified name
        return qualified

    except (KeyError, AttributeError):
        # Fallback if qualified name not found
        return "<?>"
