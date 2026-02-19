"""Parse code into cop (comp operators) structure.

The cops are similar to an ast structure. They are designed to be easy to
manipulate, assemble, and transform. The cop objects are simple comp structures
and easy to serialize.

This data is usually generated from source with `comp.parse`. Each cop structure
tracks the position it was generated from in the original source string. Cop
data is built into executable code objects with `comp.generate_code_for_definition`.

Each cop node has a positional tag as its first child. There is also an optional
"kids" field which contains a struct of positional cop nodes. (the kids can be
named, but the name is ignored other than for diagnostic info). There is also a
recommended "pos" field which defines the 4 numbers defining the source span
defining the cop. There can be any number of additional named fields which
should have full Value types as values.
"""

__all__ = [
    "lark_parser",
]

import lark
import comp




@comp._internal.register_internal_module("cop")
def create_cop_module(module):
    """Create the 'cop' internal module with COP-related tags.

    Returns:
        InternalModule: The cop module
    """
    # Add all cop tags
    cop_tags = (
        "shape.identifier",  # (identifier, checks, array, default)
        "shape.union",  # (kids) list of shape.field alternatives
        "shape.define",  # (fields, checks, array)
        "shape.field",  # (kids) shape type and optional unit/limits/repeat/default
        "shape.unit",  # (kids) 1 kid - unit identifier
        "shape.value",  # (kids) 1 kid - exact value constraint
        "shape.limit",  # (kids) named limit constraint (1-2 kids: name and optional value)
        "shape.repeat",  # (kids) array/repetition specification (0-2 number children)
        "shape.default",  # (kids) 1 kid - default value
        "signature.input",  # (kids) 1 kid - function input shape
        "signature.param",  # (kids) 1 or 2 kids - :param declaration with shape and optional default
        "signature.block",  # (kids) 1 or 2 kids - :block declaration with shape and optional default
        "function.define",  # (sig, body) function definition with signature and body
        "function.signature",  # (kids) function signature (input shape)
        "function.body",  # (kids or sig+body) function body, may have block signature
        "block.signature",  # (kids) signature for block/statement (:param/:block declarations)
        "statement.define",  # (kids) sequence of statements
        "statement.field",  # (kids) single statement/expression in a sequence
        "op.let",  # (kids) 2 kids - name and value for !let assignment
        "op.on",  # (kids) expression and branches for !on dispatch
        "op.on.branch",  # (kids) 2 kids - shape and expression for an !on branch
        "struct.define",  # (kids)
        "struct.posfield",  # (kids) 1 kid
        "struct.namefield",  # (op, kids) 2 kids (name value)
        "struct.letassign",  # (name, kids) 1 kid (value) [DEPRECATED - use op.let]
        "mod.define",  # (kids)
        "mod.namefield",  # (op, kids) 2 kids (name value)
        "value.identassign",  # (kids)  same as identifier, but in an assignment
        "value.identifier",  # (kids)
        "value.reference",  # (definition qualified namespace)
        "value.constant",  # (value) Constant value
        "ident.token",  # (value)
        "ident.index",  # (value)
        "ident.indexpr",  # (value)
        "ident.expr",  # (value)
        "ident.text",  # (value)
        "value.number",  # (value)
        "value.text",  # (value)
        "value.block",  # (kids)  kids; signature, body - for :(...) block values
        "value.wrapper",  # (wrapper, kids) wrapper reference and wrapped value
        "value.binding",  # (callable, bindings) function call with parameter bindings
        "value.math.unary",  # (op, kids)  1 kid
        "value.math.binary",  # (op, kids)  2 kids
        "value.compare",  # (op, kids)  2 kids
        "value.logic.binary",  # (op, kids)  2 kids
        "value.logic.unary",  # (op, kids)  1 kids
        "value.invoke",  # (kids)  kids 2+ kids; callable, argsandblocks [DEPRECATED - will be removed]
        "value.pipeline",  # (kids) pipeline stages
        "value.fallback",  # (kids)
        "value.field",  # field access: (left, field)
        "value.on",  # (expr, branches) on-dispatch with expression and branch list
        "value.transact",  # (kids)
        "value.handle",  # (op, kids) grab/drop/pull/etc
        "value.constant",  # (value) precompiled constant value
        "stmt.assign",  # (kids) 2 kids (lvalue, rvalue)
    )
    for tag_name in cop_tags:
        module.add_tag(tag_name, private=False)


def lark_parser(name, start=None):
    """Get globally shared lark parser.

    Args:
        name: (str) name of the grammar file (without .lark)
        start: (str|None) optional start rule name (e.g., "start_import")

    Returns:
        (lark.Lark) Parser instance
    """
    # If start is specified, create a unique key for caching
    cache_key = f"{name}:{start}" if start else name

    parser = _parsers.get(cache_key)
    if parser is not None:
        return parser

    path = f"lark/{name}.lark"
    parser_kwargs = {
        "parser": "lalr",
        "propagate_positions": True
    }
    if start is not None:
        parser_kwargs["start"] = start

    parser = lark.Lark.open(path, rel_to=__file__, **parser_kwargs)
    _parsers[cache_key] = parser
    return parser



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
        # Check if meta has position info (optional rules might not)
        if hasattr(meta, 'line') and meta.line is not None:
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
            # text: STRING | LONG_STRING - just one token
            # Strip outer quotes from the value
            raw_value = kids[0].value
            text_value = raw_value[1:-1] if len(raw_value) >= 2 else raw_value
            return _parsed(tree, "value.text", [], value=text_value)

        # Operators
        case "binary_op":
            left = lark_to_cop(kids[0])
            right = lark_to_cop(kids[2])
            op = kids[1].value
            if op in ("||", "&&"):
                return _parsed(
                    tree, "value.logic.binary", {"l": left, "r": right}, op=op
                )
            if op == "??":
                return _parsed(tree, "value.fallback", {"l": left, "r": right}, op=op)
            return _parsed(tree, "value.math.binary", {"l": left, "r": right}, op=op)

        case "pipeline":
            # Collect all pipeline stages (skip the | operators which are Token objects)
            stages = [lark_to_cop(kid) for kid in kids if isinstance(kid, lark.Tree)]
            return _parsed(tree, "value.pipeline", stages)

        case "compare_op":
            left = lark_to_cop(kids[0])
            
            # Handle >= and <= operators which split into separate tokens
            # Since GE and LE are not defined in the grammar, >= becomes ANGLE_CLOSE + EQUALS
            # This allows shape syntax like ~num<min=1>=2 to parse without requiring spaces
            # We merge adjacent > + = into >= and < + = into <=
            if len(kids) == 4:
                # Split operator: kids[1] and kids[2] are the operator tokens
                op_token1 = kids[1]
                op_token2 = kids[2]
                op1 = op_token1.value
                op2 = op_token2.value
                
                # Check if tokens are adjacent (no whitespace)
                # If there's a gap, the user wrote something like "x > = 5" which is likely an error
                if hasattr(op_token1, "end_column") and hasattr(op_token2, "column"):
                    gap = op_token2.column - op_token1.end_column
                    if gap > 0:
                        # There's whitespace between the operators
                        raise comp.CodeError(
                            f"Unexpected space in comparison operator. "
                            f"Use '{op1}{op2}' not '{op1} {op2}'",
                            tree
                        )
                
                # Merge the tokens into a single operator
                if op1 == ">" and op2 == "=":
                    op = ">="
                elif op1 == "<" and op2 == "=":
                    op = "<="
                else:
                    # Shouldn't happen based on grammar, but handle gracefully
                    op = op1 + op2
                
                right = lark_to_cop(kids[3])
            else:
                # Single operator token (==, !=, <>, <, >)
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

        case "fieldaccess":
            # kids are (source data, dot literal, field)
            left = lark_to_cop(kids[0])
            field = lark_to_cop(kids[2])
            return _parsed(tree, "value.field", {"l": left, "f": field})

        case "postfield":
            fields = [lark_to_cop(k) for k in kids[::2]]
            # If single field, just return it directly
            if len(fields) == 1:
                return fields[0]
            # Multiple fields - return as identifier-like structure
            return _parsed(tree, "value.identifier", fields)

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

        case "statement":
            # statement: PAREN_OPEN statement_body PAREN_CLOSE
            # Skip parens, process body
            body_cop = lark_to_cop(kids[1])
            return body_cop

        case "statement_body":
            # statement_body: signature statement_item* | statement_item*
            # Check if first kid is signature
            start_idx = 0
            sig_cop = None
            if kids and isinstance(kids[0], lark.Tree) and kids[0].data == "signature":
                sig_cop = lark_to_cop(kids[0])
                start_idx = 1

            # Convert statement items - wrap each in statement.field
            field_cops = []
            for kid in kids[start_idx:]:
                item_cop = lark_to_cop(kid)
                field_cops.append(_parsed(tree, "statement.field", [item_cop]))

            # Create statement.define with optional block.signature
            if sig_cop:
                # Has signature - add block.signature to statement.define kids
                # sig_cop is already a shape.define with signature.param/signature.block kids
                # Convert it to block.signature
                block_sig = _parsed(tree, "block.signature", list(comp.cop_kids(sig_cop)))
                # Build kids dict with sig and positional fields
                kids_dict = {"sig": block_sig}
                for i, field in enumerate(field_cops):
                    kids_dict[str(i)] = field
                return _parsed(tree, "statement.define", kids_dict)
            else:
                # No signature - just statement.define
                return _parsed(tree, "statement.define", field_cops)

        case "statement_item":
            # statement_item: let_assign | expression
            return lark_to_cop(kids[0])

        case "structure":
            # structure: BRACE_OPEN structure_body BRACE_CLOSE
            # Skip braces, process body
            body_cop = lark_to_cop(kids[1])
            return body_cop

        case "structure_body":
            # structure_body: signature structure_item* | structure_item*
            # Check if first kid is signature
            start_idx = 0
            sig_cop = None
            if kids and isinstance(kids[0], lark.Tree) and kids[0].data == "signature":
                sig_cop = lark_to_cop(kids[0])
                start_idx = 1

            # Convert structure items and wrap positional values in struct.posfield
            items = []
            for kid in kids[start_idx:]:
                item = lark_to_cop(kid)
                # If item is not already a field wrapper (struct.namefield or op.let),
                # wrap it in struct.posfield
                item_tag = comp.cop_tag(item)
                if item_tag not in ("struct.namefield", "op.let"):
                    item = _parsed(kid, "struct.posfield", [item])
                items.append(item)

            if sig_cop:
                # Has signature - add block.signature to struct.define kids
                # sig_cop is shape.define, convert to block.signature
                block_sig = _parsed(tree, "block.signature", list(comp.cop_kids(sig_cop)))
                # Build kids dict with sig and positional fields
                kids_dict = {"sig": block_sig}
                for i, item in enumerate(items):
                    kids_dict[str(i)] = item
                return _parsed(tree, "struct.define", kids_dict)
            else:
                # No signature - just a structure
                return _parsed(tree, "struct.define", items)

        case "structure_item":
            # structure_item: let_assign | field_or_expr
            return lark_to_cop(kids[0])

        case "field_or_expr":
            # field_or_expr: TOKENFIELD EQUALS expression -> named_field | expression
            # This should just recurse to the child
            return lark_to_cop(kids[0])

        case "named_field":
            # named_field: TOKENFIELD EQUALS expression
            # kids[0] should be TOKENFIELD token
            name_token = kids[0]
            if isinstance(name_token, lark.Token):
                name = name_token.value
            else:
                # Wrapped in a tree - dig down
                while isinstance(name_token, lark.Tree) and name_token.children:
                    name_token = name_token.children[0]
                name = name_token.value if isinstance(name_token, lark.Token) else str(name_token)

            value_cop = lark_to_cop(kids[2])  # Skip EQUALS at kids[1]
            name_cop = _parsed(tree, "ident.token", [], value=name)
            return _parsed(tree, "struct.namefield", {"n": name_cop, "v": value_cop}, op="=")

        case "struct_field":
            if len(kids) == 1:
                value = lark_to_cop(kids[0])
                return _parsed(tree, "struct.posfield", [value])
            name = lark_to_cop(kids[0])
            op = kids[1].value
            value = lark_to_cop(kids[2])
            return _parsed(tree, "struct.namefield", {"n": name, "v": value}, op=op)

        case "let_assign":
            # let_assign: OP_LET identifier expression
            # kids[0] = OP_LET, kids[1] = identifier, kids[2] = expression
            name = lark_to_cop(kids[1])
            value = lark_to_cop(kids[2])
            return _parsed(tree, "op.let", [name, value])

        case "block":
            # Signature is shape_fields (all kids except first COLON and last structure)
            sig_fields = [lark_to_cop(kid) for kid in kids[1:-1]]
            # For blocks, use block.signature
            signature = _parsed(tree, "block.signature", sig_fields)

            # Get the structure (last kid) and check for wrappers
            structure = kids[-1]
            struct_kids = structure.children[1:-1]  # Skip PAREN_OPEN and PAREN_CLOSE

            # Separate struct_wrapper Lark nodes from regular body kids
            wrapper_lark_nodes = [k for k in struct_kids if isinstance(k, lark.Tree) and k.data == "struct_wrapper"]

            if wrapper_lark_nodes:
                # Build body without wrappers
                body_lark_nodes = [k for k in struct_kids if not (isinstance(k, lark.Tree) and k.data == "struct_wrapper")]
                body_cops = [lark_to_cop(kid) for kid in body_lark_nodes]
                body = _parsed(structure, "struct.define", body_cops)
            else:
                # No wrappers - use structure as-is
                body = lark_to_cop(structure)

            # Build the block
            block_cop = _parsed(tree, "value.block", {"s": signature, "b": body})
            
            if not wrapper_lark_nodes:
                return block_cop
            
            # Build wrap identifier node
            wrap_ident = _parsed(tree, "value.identifier", [
                _parsed(tree, "ident.token", [], value="wrap")
            ])
            
            # Wrap with each wrapper (innermost first, so reverse order)
            # :(|outer |inner body) becomes wrap((outer wrap((inner :(body)))))
            result = block_cop
            for wrapper_node in reversed(wrapper_lark_nodes):
                # Extract identifier from struct_wrapper: PIPE identifier
                wrapper_ident = lark_to_cop(wrapper_node.children[1])
                # Build args struct with two positional fields: wrapper and inner
                args_struct = _parsed(tree, "struct.define", [
                    _parsed(tree, "struct.posfield", [wrapper_ident]),
                    _parsed(tree, "struct.posfield", [result])
                ])
                # Build wrap(args_struct)
                result = _parsed(tree, "value.invoke", [wrap_ident, args_struct])
            return result

        case "mod_field":
            name = lark_to_cop(kids[0])
            op = kids[1].value
            value = lark_to_cop(kids[2])
            return _parsed(tree, "mod.namefield", {"n": name, "v": value}, op=op)

        case "shape":
            # TILDE shape_union shape_default?
            spec = lark_to_cop(kids[1])

            # Check for optional default
            if len(kids) > 2 and isinstance(kids[2], lark.Tree) and kids[2].data == "shape_default":
                # shape_default: EQUALS field_default_value
                default_value = lark_to_cop(kids[2].children[1])
                default_cop = _parsed(kids[2], "shape.default", [default_value])

                # If spec is already a list, append default; otherwise make it a list
                if isinstance(spec, list):
                    return spec + [default_cop]
                else:
                    return [spec, default_cop]

            return spec

        case "shape_union":
            # shape_atom (PIPE shape_atom)*
            # Could be just one shape_atom, or multiple with PIPE
            if len(kids) == 1:
                # Just a single shape_atom, pass it through
                return lark_to_cop(kids[0])
            else:
                # Multiple atoms with PIPE: shape_atom, PIPE, shape_atom, ...
                # Each alternative becomes a shape.field (without name)
                fields = []
                for kid in kids[::2]:  # Skip PIPE tokens
                    spec = lark_to_cop(kid)
                    # If spec is a list (base + extras), use it directly
                    if isinstance(spec, list):
                        field_cop = _parsed(kid, "shape.field", spec)
                    else:
                        field_cop = _parsed(kid, "shape.field", [spec])
                    fields.append(field_cop)
                return _parsed(tree, "shape.union", fields)

        case "shape_atom":
            # (identifier | paren_shape | brace_shape) unit_suffix? limit_suffix? array_suffix?
            # Returns a list: [base_type, optional shape.unit, optional shape.limit(s), optional shape.repeat]
            base = lark_to_cop(kids[0])
            extras = []

            for kid in kids[1:]:
                if isinstance(kid, lark.Tree):
                    if kid.data == "unit_suffix":
                        # unit_suffix: BRACKET_OPEN identifier BRACKET_CLOSE
                        unit_ident = lark_to_cop(kid.children[1])
                        unit_cop = _parsed(kid, "shape.unit", [unit_ident])
                        extras.append(unit_cop)
                    elif kid.data == "limit_suffix":
                        # limit_suffix: ANGLE_OPEN limit_field+ ANGLE_CLOSE
                        # Each limit_field becomes either shape.value or shape.limit
                        for limit_field in kid.children[1:-1]:  # Skip ANGLE_OPEN and ANGLE_CLOSE
                            if isinstance(limit_field, lark.Tree) and limit_field.data == "limit_field":
                                # limit_field: (identifier EQUALS)? simple_expr
                                limit_kids = []
                                for lf_kid in limit_field.children:
                                    if isinstance(lf_kid, lark.Tree):
                                        limit_kids.append(lark_to_cop(lf_kid))
                                    # Skip EQUALS token

                                # Distinguish between exact value and named limit
                                if len(limit_kids) == 1:
                                    # Just a value: ~num<12> or ~text<"cat">
                                    limit_cop = _parsed(limit_field, "shape.value", limit_kids)
                                else:
                                    # Named limit: ~num<min=1>
                                    limit_cop = _parsed(limit_field, "shape.limit", limit_kids)
                                extras.append(limit_cop)
                    elif kid.data == "array_suffix":
                        # array_suffix: STAR array_count?
                        # Determine the repeat type and create shape.repeat with 0-2 number children
                        repeat_kids = []
                        repeat_op = "*"  # Default: fully open ended

                        if len(kid.children) > 1:  # Has array_count
                            count_tree = kid.children[1]
                            count_result = lark_to_cop(count_tree)

                            # Determine the operator based on array_count structure
                            if isinstance(count_result, list):
                                # List means we have operator(s): could be + or - with numbers
                                # Filter out ident.token nodes, keep only numbers
                                for item in count_result:
                                    if comp.cop_tag(item) == "ident.token":
                                        op_val = item.field("value").data
                                        if op_val == "-":
                                            repeat_op = "-"  # range
                                        elif op_val == "+":
                                            repeat_op = "+"  # minimum
                                    else:
                                        # Keep number values
                                        repeat_kids.append(item)
                            else:
                                # Single value: exact count
                                repeat_kids = [count_result]
                                repeat_op = "="  # exact

                        repeat_cop = _parsed(kid, "shape.repeat", repeat_kids, op=repeat_op)
                        extras.append(repeat_cop)

            # Return list with base and extras, or just base if no extras
            if extras:
                return [base] + extras
            return base

        case "paren_shape":
            # PAREN_OPEN shape_content PAREN_CLOSE
            content = lark_to_cop(kids[1])
            return content

        case "brace_shape":
            # BRACE_OPEN shape_content BRACE_CLOSE
            content = lark_to_cop(kids[1])
            return content

        case "shape_content":
            # content_union | shape_field+
            fields = [lark_to_cop(kid) for kid in kids]
            if len(fields) == 1 and comp.cop_tag(fields[0]) == "shape.union":
                # It's a content_union, return it directly
                return fields[0]
            return _parsed(tree, "shape.define", fields)

        case "content_union":
            # shape_atom (PIPE shape_atom)+
            # Each alternative becomes a shape.field (without name)
            fields = []
            for kid in kids[::2]:  # Skip PIPE tokens
                spec = lark_to_cop(kid)
                # If spec is a list (base + extras), use it directly
                if isinstance(spec, list):
                    field_cop = _parsed(kid, "shape.field", spec)
                else:
                    field_cop = _parsed(kid, "shape.field", [spec])
                fields.append(field_cop)
            return _parsed(tree, "shape.union", fields)

        case "shape_field":
            # shape_field: (TOKENFIELD | shape | TOKENFIELD shape) shape_default?
            # Parse name, shape, and default
            field_name = None
            shape_parts = None
            default_cop = None

            # Check if first kid is TOKENFIELD (field name)
            idx = 0
            if idx < len(kids):
                kid = kids[idx]
                if isinstance(kid, lark.Token) and kid.type == "TOKENFIELD":
                    field_name = kid.value
                    idx += 1

            # Next kid should be shape
            if idx < len(kids):
                kid = kids[idx]
                if isinstance(kid, lark.Tree) and kid.data == "shape":
                    shape_result = lark_to_cop(kid)
                    # shape_atom might return a list [base, unit, limits, repeat] or just base
                    if isinstance(shape_result, list):
                        shape_parts = shape_result
                    else:
                        shape_parts = [shape_result]
                    idx += 1

            # Last kid might be shape_default
            if idx < len(kids):
                kid = kids[idx]
                if isinstance(kid, lark.Tree) and kid.data == "shape_default":
                    # shape_default: EQUALS field_default_value
                    # Extract the field_default_value and wrap in shape.default
                    default_value = lark_to_cop(kid.children[1])
                    default_cop = _parsed(kid, "shape.default", [default_value])

            # If no shape provided, default to any
            if shape_parts is None:
                shape_parts = [_parsed(None, "value.constant", [], value=comp.shape_any)]

            # Build shape.field with all components: base type, unit, limits, repeat, default
            field_kids = shape_parts
            if default_cop:
                field_kids = field_kids + [default_cop]
            return _parsed(tree, "shape.field", field_kids, name=field_name)

        # Import statements - handled by scan, skip in COP tree
        case "import_stmt":
            # Imports are extracted by the scan pass and used to build the namespace
            # They don't need to be in the COP tree since they're structural/metadata
            return None

        # Pass-through rules (no node created, just process children)
        case "start":
            cops = []
            for kid in kids:
                cop = lark_to_cop(kid)
                if cop is not None:  # Skip None (e.g., import statements)
                    cops.append(cop)
            return _parsed(tree, "mod.define", cops)

        # Entry point pass-through rules (extract first child)
        case "start_shape":
            # start_shape: shape
            # If shape returns a list (e.g., with default), wrap in shape.field
            result = lark_to_cop(kids[0])
            if isinstance(result, list):
                return _parsed(tree, "shape.field", result)
            return result

        case "start_func" | "start_startup" | "start_mod" | "start_package" | "start_import":
            # These are entry points that wrap the actual content
            # Just pass through to the first child
            return lark_to_cop(kids[0])

        case "start_tag":
            # start_tag: (BRACE_OPEN tag_item* BRACE_CLOSE)?
            # Build a simple list of tag identifiers
            if not kids:
                # Empty tag - return empty structure
                return _parsed(tree, "struct.define", [])
            # Skip BRACE_OPEN and BRACE_CLOSE, process tag_items
            tag_items = [lark_to_cop(kid) for kid in kids[1:-1]]
            return _parsed(tree, "struct.define", tag_items)

        case "tag_item":
            # tag_item: identifier (BRACE_OPEN tag_item* BRACE_CLOSE)?
            # For now, just convert identifier
            # TODO: Handle nested tag items
            return lark_to_cop(kids[0])

        case "func_body" | "startup_body":
            # func_body: shape wrapper* func_struct | wrapper+ func_struct | func_struct
            # startup_body: wrapper+ func_struct | func_struct
            # Separate into shape (optional), wrappers, and body
            shape_cop = None
            wrappers = []
            body_tree = None

            for kid in kids:
                if isinstance(kid, lark.Tree):
                    if kid.data == "shape":
                        shape_cop = lark_to_cop(kid)
                    elif kid.data == "wrapper":
                        wrappers.append(kid)
                    elif kid.data in ("func_struct", "statement", "structure"):
                        body_tree = kid

            # Convert body - this will be statement.define or struct.define
            body_cop = lark_to_cop(body_tree) if body_tree else _parsed(tree, "statement.define", [])

            # Apply wrappers to the body (not the entire function)
            if wrappers:
                for wrapper_tree in reversed(wrappers):
                    # Extract identifier from wrapper: AT identifier
                    wrapper_cop = lark_to_cop(wrapper_tree.children[1])
                    # Wrap the body
                    body_cop = _parsed(tree, "value.wrapper", [wrapper_cop, body_cop])

            # Build function signature from input shape if present
            # signature.input wraps shape.define which wraps the shape reference
            func_sig_cop = None
            if shape_cop:
                # If shape is a list (base + extras), wrap in shape.field first
                if isinstance(shape_cop, list):
                    shape_field = _parsed(tree, "shape.field", shape_cop)
                    shape_define = _parsed(tree, "shape.define", [shape_field])
                else:
                    shape_define = _parsed(tree, "shape.define", [shape_cop])
                sig_input_cop = _parsed(tree, "signature.input", [shape_define])
                func_sig_cop = _parsed(tree, "function.signature", [sig_input_cop])

            # Create function.define with signature and wrapped body
            if func_sig_cop:
                func_def = _parsed(tree, "function.define", {"sig": func_sig_cop, "body": body_cop})
            else:
                # No input signature - just body
                func_def = _parsed(tree, "function.define", {"body": body_cop})

            return func_def

        case "func_struct":
            # func_struct: statement | structure
            return lark_to_cop(kids[0])

        case "wrapper":
            # wrapper: AT identifier
            # Standalone wrapper - return as identifier with @ prefix
            ident_cop = lark_to_cop(kids[1])
            # Prepend @ to the identifier value
            if comp.cop_tag(ident_cop) == "value.identifier":
                first_token = list(comp.cop_kids(ident_cop))[0]
                if comp.cop_tag(first_token) == "ident.token":
                    token_value = first_token.field("value").data
                    new_token = _parsed(tree, "ident.token", [], value="@" + token_value)
                    return _parsed(tree, "value.identifier", [new_token])
            return ident_cop

        # Expression rules
        case "atom":
            # atom: wrapper* (number | text | identifier | shape) | statement | structure
            # Collect wrappers and the base value
            wrappers = []
            base_tree = None

            for kid in kids:
                if isinstance(kid, lark.Tree):
                    if kid.data == "wrapper":
                        wrappers.append(kid)
                    else:
                        base_tree = kid
                elif isinstance(kid, lark.Token):
                    # Shouldn't happen in atom
                    pass

            # Handle standalone wrappers (no base value)
            if base_tree is None:
                if not wrappers:
                    raise ValueError("atom has no base value or wrappers")
                # Standalone wrapper(s) - just convert the first wrapper
                # (Multiple wrappers without a base doesn't make semantic sense, but parse it anyway)
                return lark_to_cop(wrappers[0])

            # Convert base value
            base_cop = lark_to_cop(base_tree)

            # Apply wrappers if any
            if wrappers:
                result = base_cop
                for wrapper_tree in reversed(wrappers):
                    # Extract identifier from wrapper: AT identifier
                    wrapper_cop = lark_to_cop(wrapper_tree.children[1])
                    # Create value.wrapper node (kids as dict for named access)
                    result = _parsed(tree, "value.wrapper", {"w": wrapper_cop, "v": result})
                return result

            return base_cop

        case "binding_expr":
            # binding_expr: unary (COLON binding_value)*
            # If no bindings, just return the unary
            if len(kids) == 1:
                return lark_to_cop(kids[0])

            # Has bindings - build a binding node
            callable_cop = lark_to_cop(kids[0])

            # Collect binding values (skip COLON tokens)
            # Note: binding_value nodes may be inlined due to ? prefix in grammar
            binding_cops = []
            for i in range(1, len(kids)):
                kid = kids[i]
                # Skip COLON tokens
                if isinstance(kid, lark.Token) and kid.type == "COLON":
                    continue
                # Process tree nodes - may be binding_value or inlined content
                if isinstance(kid, lark.Tree):
                    if kid.data == "binding_value":
                        # Explicit binding_value node
                        binding_cops.append(lark_to_cop(kid))
                    else:
                        # Inlined binding value (single unary expression)
                        # Wrap it as a positional field
                        value_cop = lark_to_cop(kid)
                        binding_cops.append(_parsed(kid, "struct.posfield", [value_cop]))

            # Build bindings structure
            bindings_struct = _parsed(tree, "struct.define", binding_cops)

            # Build binding node (interpreter will determine if/when to invoke)
            # Kids as dict for named access
            return _parsed(tree, "value.binding", {"c": callable_cop, "b": bindings_struct})

        case "binding_value":
            # binding_value: identifier EQUALS unary | unary
            if len(kids) == 1:
                # Just a value - positional field
                value_cop = lark_to_cop(kids[0])
                return _parsed(tree, "struct.posfield", [value_cop])
            else:
                # Named binding
                name_cop = lark_to_cop(kids[0])
                value_cop = lark_to_cop(kids[2])  # Skip EQUALS
                return _parsed(tree, "struct.namefield", {"n": name_cop, "v": value_cop}, op="=")

        case "signature":
            # signature: (param_decl | block_decl)+
            # Convert to shape.define
            field_cops = [lark_to_cop(kid) for kid in kids]
            return _parsed(tree, "shape.define", field_cops)

        case "param_decl":
            # param_decl: OP_PARAM identifier shape (EQUALS simple_expr)?
            # kids[0] = OP_PARAM, kids[1] = identifier, kids[2] = shape, kids[3] = EQUALS (optional), kids[4] = simple_expr (optional)
            name_cop = lark_to_cop(kids[1])
            shape_cop = lark_to_cop(kids[2])

            # Check for default value
            default_cop = None
            if len(kids) > 3:
                # Has default value (skip EQUALS at kids[3])
                default_cop = lark_to_cop(kids[4])

            # Extract name as string for the field name
            # name_cop is a value.identifier, extract the token value
            name_str = None
            if comp.cop_tag(name_cop) == "value.identifier":
                first_kid = list(comp.cop_kids(name_cop))[0]
                if comp.cop_tag(first_kid) == "ident.token":
                    name_str = first_kid.field("value").data

            # Build signature.param field
            field_kids = [shape_cop]
            if default_cop:
                field_kids.append(default_cop)
            return _parsed(tree, "signature.param", field_kids, name=name_str)

        case "block_decl":
            # block_decl: OP_BLOCK identifier shape (EQUALS simple_expr)?
            # Similar to param_decl
            name_cop = lark_to_cop(kids[1])
            shape_cop = lark_to_cop(kids[2])

            # Check for default value
            default_cop = None
            if len(kids) > 3:
                # Has default value (skip EQUALS at kids[3])
                default_cop = lark_to_cop(kids[4])

            # Extract name
            name_str = None
            if comp.cop_tag(name_cop) == "value.identifier":
                first_kid = list(comp.cop_kids(name_cop))[0]
                if comp.cop_tag(first_kid) == "ident.token":
                    name_str = first_kid.field("value").data

            # Build signature.block field with optional default
            field_kids = [shape_cop]
            if default_cop:
                field_kids.append(default_cop)
            return _parsed(tree, "signature.block", field_kids, name=name_str)

        case "dollarfield":
            # dollarfield: DOLLAR3 | DOLLAR2 | DOLLAR
            # Field access now requires explicit DOT: $.field
            dollar_token = kids[0]
            # Map token type to value
            if dollar_token.type == "DOLLAR3":
                dollar_value = "$$$"
            elif dollar_token.type == "DOLLAR2":
                dollar_value = "$$"
            else:  # DOLLAR
                dollar_value = "$"
            return _parsed(tree, "ident.token", [], value=dollar_value)

        case "on_dispatch":
            # on_dispatch: OP_ON expression on_branch+
            # kids[0] = OP_ON, kids[1] = expression, kids[2+] = on_branches
            # Store all children in kids: first is expression, rest are branches
            expr_cop = lark_to_cop(kids[1])

            # Collect all branches
            branch_cops = []
            for kid in kids[2:]:
                if isinstance(kid, lark.Tree) and kid.data == "on_branch":
                    branch_cops.append(lark_to_cop(kid))

            # Create op.on node with expression and branches as positional kids
            all_kids = [expr_cop] + branch_cops
            return _parsed(tree, "op.on", all_kids)

        case "on_branch":
            # on_branch: shape expression
            # Each branch is a pair: (shape, expression)
            shape_lark = kids[0]
            expr_cop = lark_to_cop(kids[1])
            
            # Parse the shape and wrap it in shape.define
            # The shape rule extracts just the spec, so we need to wrap it
            shape_spec = lark_to_cop(shape_lark)
            
            # Wrap the spec in shape.define (if it's not already wrapped)
            if isinstance(shape_spec, list):
                shape_cop = _parsed(shape_lark, "shape.define", shape_spec)
            else:
                shape_cop = _parsed(shape_lark, "shape.define", [shape_spec])
            
            # Create an op.on.branch node with shape and expression as kids
            return _parsed(tree, "op.on.branch", [shape_cop, expr_cop])

        case "transaction":
            # transaction: OP_TRANSACT PAREN_OPEN identifier+ PAREN_CLOSE
            # TODO: Implement proper transaction COP structure
            # For now, return a placeholder
            return _parsed(tree, "value.constant", [], value=comp.shape_any)

        case "defer_expr":
            # defer_expr: OP_DEFER expression
            # TODO: Implement proper defer COP structure
            # For now, just return the expression
            return lark_to_cop(kids[1])

        case "handle_grab":
            # handle_grab: OP_GRAB expression
            # kids[0] = OP_GRAB token, kids[1] = expression (tag/identifier)
            target = lark_to_cop(kids[1])
            return _parsed(tree, "value.handle", [target], op="grab")

        case "handle_drop":
            # handle_drop: OP_DROP expression
            # kids[0] = OP_DROP token, kids[1] = handle expression
            target = lark_to_cop(kids[1])
            return _parsed(tree, "value.handle", [target], op="drop")

        case "handle_pull":
            # handle_pull: OP_PULL expression
            # kids[0] = OP_PULL token, kids[1] = handle expression
            target = lark_to_cop(kids[1])
            return _parsed(tree, "value.handle", [target], op="pull")

        case "handle_push":
            # handle_push: OP_PUSH expression expression
            # kids[0] = OP_PUSH token, kids[1] = handle expression, kids[2] = data expression
            target = lark_to_cop(kids[1])
            data = lark_to_cop(kids[2])
            return _parsed(tree, "value.handle", [target, data], op="push")

        case "limit_suffix":
            # limit_suffix: ANGLE_OPEN limit_field+ ANGLE_CLOSE
            # TODO: Handle limit constraints properly
            # For now, skip them (they're handled in shape_atom but currently ignored)
            return None

        case "limit_field":
            # limit_field: (identifier EQUALS)? simple_expr
            # TODO: Handle limit fields properly
            return None

        case "array_suffix":
            # array_suffix: STAR array_count?
            # TODO: Handle array annotations properly
            return None

        case "array_count":
            # array_count: number MINUS number | number PLUS | number
            # Convert all the children (numbers and operators)
            count_kids = []
            for kid in kids:
                if isinstance(kid, lark.Tree):
                    count_kids.append(lark_to_cop(kid))
                elif isinstance(kid, lark.Token) and kid.type in ("MINUS", "PLUS"):
                    # Store operator as a token
                    count_kids.append(_parsed(kid, "ident.token", [], value=kid.value))
            # Return as a simple list or single value
            if len(count_kids) == 1:
                return count_kids[0]
            return count_kids

        case _:
            raise ValueError(f"Unhandled grammar rule: {tree.data}")


# cached lark parsers
_parsers = {}

