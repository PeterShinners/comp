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
    "lark_parse",
    "lark_to_cop",
]

import lark
import comp
import os as _os
import re as _re
import time as _time


def lark_parse(text, grammar, rule=None, line_offset=1, col_offset=0):
    """Parse text into grammar tree.

    The grammar tree is most likely handed off to be converted to cop nodes, but
    can be introspected along the way. The parsed structure is also version
    specific and may change from release to release, the cop nodes should
    provide more stability.

    The parsed grammar tree contains the starting positions and line offsets for
    the tokens. An alternative start and offset can be provided to provide
    context for the parsed text within a larger file.

    Comp provides two primary lark grammars. The rule can be either "comp" or
    "scan" to select between the two grammars. Each grammar has its own default
    starting rule, or an alternative entry point can be picked with the rule
    argument, like `start_import`.
    
    Args:
        text: (str) the code to be parsed
        grammar: (str) grammar to be used
        rule: (str|None) optional start rule (e.g., "start_import")
        line_offset: (int) Line number offset for parsed positions
        col_offset: (int) Column position offset for the first line

    Returns:
        (lark.Tree) Parsed grammar tree

    Raises:
        comp.ParseError: When the source text cannot be parsed, with
            user-friendly context showing the offending line and position.
    """
    # If start is specified, create a unique key for caching
    cache_key = f"{grammar}:{rule}" if rule else grammar
    global _time_grammar_init, _time_parse
    parser = _parsers.get(cache_key)
    if parser is None:
        path = f"lark/{grammar}.lark"
        # Cache key -> safe filename: "comp:start_import" -> "comp_start_import"
        cache_filename = cache_key.replace(":", "_") + ".lark.cache"
        cache_dir = _os.path.join(_os.path.dirname(__file__), "lark")
        cache_path = _os.path.join(cache_dir, cache_filename)
        parser_kwargs = {
            "parser": "lalr",
            "propagate_positions": True,
            "cache": cache_path,
        }
        if rule is not None:
            parser_kwargs["start"] = rule
        _gi0 = _time.perf_counter()
        parser = lark.Lark.open(path, rel_to=__file__, **parser_kwargs)
        _time_grammar_init += _time.perf_counter() - _gi0
        _parsers[cache_key] = parser


    padded = "\n" * (line_offset - 1) + " " * col_offset + text
    _p0 = _time.perf_counter()
    try:
        tree = parser.parse(padded)
    except lark.exceptions.UnexpectedInput as e:
        raise _format_lark_error(e, text, line_offset) from None
    finally:
        _time_parse += _time.perf_counter() - _p0
    return tree


def _format_lark_error(exc, source_text, line_offset):
    """Convert a Lark parse error into a user-friendly comp.ParseError.

    Produces output similar to CodeError/EvalError formatting: a summary
    line, the source context with line number, and a caret pointing to the
    problem character(s).

    Args:
        exc: (lark.exceptions.UnexpectedInput) The Lark exception
        source_text: (str) Original source text (before padding)
        line_offset: (int) Line offset applied during parsing

    Returns:
        (comp.ParseError) Formatted parse error
    """
    source_lines = source_text.split("\n")

    # Extract position from the Lark exception
    line = getattr(exc, "line", None)
    col = getattr(exc, "column", None)

    # Build summary — just show the unexpected token, not expected list
    if isinstance(exc, lark.exceptions.UnexpectedToken):
        token = getattr(exc, "token", None)
        if token is not None and str(token).strip():
            summary = f"Unexpected `{str(token)[:30]}`"
        elif token is not None:
            summary = "Unexpected end of input"
        else:
            summary = "Unexpected token"
    elif isinstance(exc, lark.exceptions.UnexpectedCharacters):
        char = getattr(exc, "char", None)
        if char == "\"":
            summary = "Text literal missing closing quote"
        elif char == "!" and line is not None and col is not None:
            # Try to extract the operator name after !
            src_line = source_lines[line - 1] if line <= len(source_lines) else ""
            rest = src_line[col - 1:]  # from ! onward
            m = _re.match(r"!([a-zA-Z][\w-]*)", rest)
            if m:
                summary = f"Unknown operator `!{m.group(1)}`"
            else:
                summary = f"Unexpected character `{char}`"
        elif char:
            summary = f"Unexpected character `{char}`"
        else:
            summary = "Unexpected character"
    elif isinstance(exc, lark.exceptions.UnexpectedEOF):
        summary = "Unexpected end of input"
    else:
        summary = str(exc).split("\n")[0]

    # Build context display
    parts = [f"Parse failure; {summary}"]

    if line is not None and col is not None:
        parts.append(f"  --> line {line}, col {col}")

        # Show the source line with caret
        # The line number from lark is in the padded text coordinates
        src_line_idx = line - line_offset
        if 0 <= src_line_idx < len(source_lines):
            src_line = source_lines[src_line_idx].rstrip("\n")
            parts.append(f"   | {src_line}")
            caret_pos = max(0, col - 1)
            parts.append(f"   | {' ' * caret_pos}^")

    message = "\n".join(parts)
    position = ((line or 0) - 1) * 1000 + (col or 0) if line else None
    return comp.ParseError(message, position=position)


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

    return comp.create_cop("cop-type." + tag, kids, **fields)


def _identifier_to_string(ident_cop):
    """Extract dotted name string from a value.identifier COP node."""
    parts = []
    for kid in comp.cop_kids(ident_cop):
        kid_tag = comp.cop_tag(kid)
        if kid_tag in ("ident.token", "ident.text"):
            parts.append(kid.field("value").data)
    return ".".join(parts) if parts else ""


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
            if op in ("!or", "!and"):
                return _parsed(
                    tree, "value.logic.binary", [left, right], op=op
                )
            return _parsed(tree, "value.math.binary", [left, right], op=op)

        case "value_fallback":
            left = lark_to_cop(kids[0])
            right = lark_to_cop(kids[2])  # kids[1] is the ?? token
            # Flatten right-recursive nesting into a single chain
            if comp.cop_tag(right) == "value.fallback":
                all_kids = [left] + list(comp.cop_kids(right))
            else:
                all_kids = [left, right]
            return _parsed(tree, "value.fallback", all_kids, op="??")

        case "fail_expr":
            # fail_expr: OP_FAIL expression — kids[0]=token, kids[1]=expression
            expr_cop = lark_to_cop(kids[1])
            return _parsed(tree, "op.fail", [expr_cop])

        case "fail_shorthand":
            # fail_shorthand: OP_FAIL DOT identifier expression
            # Desugar !fail.TYPE expr into !fail {fail.TYPE message=expr}
            # kids: [OP_FAIL, DOT, identifier_tree, expression_tree]
            ident_cop = lark_to_cop(kids[2])
            ident_kids = list(comp.cop_kids(ident_cop))
            fail_token = _parsed(kids[0], "ident.token", [], value="fail")
            fail_ident = _parsed(tree, "value.identifier", [fail_token] + ident_kids)
            posfield = _parsed(tree, "struct.posfield", [fail_ident])
            msg_name = _parsed(tree, "ident.token", [], value="message")
            msg_value = lark_to_cop(kids[3])
            namefield = _parsed(tree, "struct.namefield", [msg_name, msg_value], op="=")
            struct = _parsed(tree, "struct.define", [posfield, namefield])
            return _parsed(tree, "op.fail", [struct])

        # pipeline, pipeline_body, pipe_start removed — pipelines now use paren_body/paren_pipeline

        case "pipe_stage":
            # pipe_stage: unary | unary pipe_arg+
            # Filter token children (shouldn't be any but be safe)
            expr_kids = [kid for kid in kids if isinstance(kid, lark.Tree)]
            if len(expr_kids) == 1:
                return lark_to_cop(expr_kids[0])
            # Has args — build a binding node
            callable_cop = lark_to_cop(expr_kids[0])
            binding_cops = [lark_to_cop(kid) for kid in expr_kids[1:]]
            bindings_struct = _parsed(tree, "struct.define", binding_cops)
            return _parsed(tree, "value.binding", [callable_cop, bindings_struct])

        case "named_binding":
            # named_binding: TOKENFIELD EQUALS unary
            name_str = kids[0].value  # TOKENFIELD token
            value_cop = lark_to_cop(kids[2])  # Skip EQUALS
            name_cop = _parsed(tree, "ident.token", [], value=name_str)
            return _parsed(tree, "struct.namefield", [name_cop, value_cop], op="=")

        case "str_named_binding":
            # str_named_binding: text EQUALS unary  (e.g. "key"=val in pipe args)
            name_cop = lark_to_cop(kids[0])
            value_cop = lark_to_cop(kids[2])
            return _parsed(tree, "struct.namefield", [name_cop, value_cop], op="=")

        case "bare_binding":
            # bare_binding: non_shape_atom
            value_cop = lark_to_cop(kids[0])
            return _parsed(tree, "struct.posfield", [value_cop])

        case "capture_expr":
            # capture_expr: COLON statement | COLON structure
            # Skip the COLON, process the statement/structure as a block value.
            # If the body is a statement.define with a leading block.signature,
            # hoist the signature to produce value.block([block.sig, stripped.define])
            # so that _build_block can use the standard 2-kid format.
            body_cop = lark_to_cop(kids[1])
            body_tag = comp.cop_tag(body_cop)
            if body_tag == "statement.define":
                body_kids = list(comp.cop_kids(body_cop))
                if body_kids and comp.cop_tag(body_kids[0]) == "block.signature":
                    sig_cop = body_kids[0]
                    stripped = comp.cop_rebuild(body_cop, body_kids[1:])
                    return _parsed(tree, "value.block", [sig_cop, stripped])
            return _parsed(tree, "value.block", [body_cop])

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
            
            return _parsed(tree, "value.compare", [left, right], op=op)

        case "unary_op":
            right = lark_to_cop(kids[1])
            op = kids[0].value
            if op == "!not":
                return _parsed(tree, "value.logic.unary", [right], op="!not")
            return _parsed(tree, "value.math.unary", [right], op=op)

        case "invoke":
            fields = [lark_to_cop(kid) for kid in kids]
            return _parsed(tree, "value.invoke", fields)

        case "fieldaccess":
            # kids are (source data, dot literal, field)
            left = lark_to_cop(kids[0])
            field = lark_to_cop(kids[2])
            return _parsed(tree, "value.field", [left, field])

        case "stashaccess":
            # postfix AMPERSAND TOKENFIELD -> stashaccess
            # kids: (target_expr, AMPERSAND, TOKENFIELD)
            left = lark_to_cop(kids[0])
            field_name = kids[2].value
            field_cop = _parsed(kids[2], "ident.token", [], value=field_name)
            return _parsed(tree, "value.stash", [left, field_cop])

        case "cast_unit":
            # postfix HASH identifier -> cast_unit
            # kids are (value, HASH, identifier)
            left = lark_to_cop(kids[0])
            unit_ident = lark_to_cop(kids[2])
            return _parsed(tree, "value.cast_unit", [left, unit_ident])

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
            # statement: PAREN_OPEN paren_body PAREN_CLOSE
            return lark_to_cop(kids[1])

        case "paren_body":
            # paren_body: signature paren_items | paren_items
            # Produces statement.define (grouping) or value.pipeline (when paren_pipeline present)
            sig_cop = None
            paren_items_tree = None
            for kid in kids:
                if isinstance(kid, lark.Tree):
                    if kid.data == "signature":
                        sig_cop = lark_to_cop(kid)
                    elif kid.data == "paren_items":
                        paren_items_tree = kid

            # Extract statement_items and optional paren_pipeline from paren_items
            item_trees = []
            pipeline_tree = None
            if paren_items_tree:
                for kid in paren_items_tree.children:
                    if isinstance(kid, lark.Tree):
                        if kid.data == "paren_pipeline":
                            pipeline_tree = kid
                        else:
                            item_trees.append(kid)  # statement_item trees

            # Convert statement items.
            # !my / !ctx become statement.my / statement.ctx (direct kids of statement.define)
            # Everything else is wrapped in statement.field
            item_cops = [lark_to_cop(t) for t in item_trees]
            field_cops = []
            for t, c in zip(item_trees, item_cops):
                c_tag = comp.cop_tag(c)
                if c_tag == "op.my":
                    field_cops.append(_parsed(t, "statement.my", list(comp.cop_kids(c))))
                elif c_tag == "op.ctx":
                    field_cops.append(_parsed(t, "statement.ctx", list(comp.cop_kids(c))))
                else:
                    field_cops.append(_parsed(t, "statement.field", [c]))

            if pipeline_tree:
                # Has pipeline tail: build value.pipeline
                # Items before the pipeline become the input (mirrors old pipe_start logic)
                if not field_cops and sig_cop is None:
                    # (| stage ...) — no input value
                    input_cop = None
                elif (len(field_cops) == 1 and sig_cop is None
                        and comp.cop_tag(field_cops[0]) == "statement.field"):
                    # Single bare expression, no signature — use directly as pipeline input
                    input_cop = item_cops[0]
                else:
                    # Multiple items or has signature — wrap in statement.define
                    if sig_cop:
                        block_sig = _parsed(tree, "block.signature", list(comp.cop_kids(sig_cop)))
                        input_cop = _parsed(tree, "statement.define", [block_sig] + field_cops)
                    else:
                        input_cop = _parsed(tree, "statement.define", field_cops)

                # Build stages from paren_pipeline:
                # PIPE pipe_stage (PIPE pipe_stage)* (PIPEFALLBACK pipe_stage)?
                stages = []
                has_fallback = False
                for kid in pipeline_tree.children:
                    if isinstance(kid, lark.Token):
                        if kid.type == "PIPEFALLBACK":
                            has_fallback = True
                        continue
                    if isinstance(kid, lark.Tree) and kid.data == "pipe_stage":
                        stage_cop = lark_to_cop(kid)
                        if has_fallback:
                            stage_cop = _parsed(kid, "value.pipeline_fallback", [stage_cop])
                            has_fallback = False
                        stages.append(stage_cop)

                all_stages = ([input_cop] if input_cop is not None else []) + stages
                return _parsed(tree, "value.pipeline", all_stages)

            else:
                # No pipeline — plain grouping: statement.define
                if sig_cop:
                    block_sig = _parsed(tree, "block.signature", list(comp.cop_kids(sig_cop)))
                    return _parsed(tree, "statement.define", [block_sig] + field_cops)
                else:
                    return _parsed(tree, "statement.define", field_cops)

        case "statement_item":
            # statement_item: my_expr | ctx_expr | stash_assign | field_or_expr
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
                # If item is not already a field wrapper (struct.namefield, op.my,
                # op.ctx, or op.stash), wrap it in struct.posfield
                item_tag = comp.cop_tag(item)
                if item_tag not in ("struct.namefield", "op.my", "op.ctx", "op.stash"):
                    item = _parsed(kid, "struct.posfield", [item])
                items.append(item)

            # Merge same-name struct.namefield entries whose values are both
            # struct.define (produced by deep assignment like one.a=1 + one.b=2
            # → one = {a:1, b:2}).  Simple non-struct values keep last-write semantics.
            items = _merge_same_name_namefields(items)

            if sig_cop:
                block_sig = _parsed(tree, "block.signature", list(comp.cop_kids(sig_cop)))
                return _parsed(tree, "struct.define", [block_sig] + items)
            else:
                return _parsed(tree, "struct.define", items)

        case "structure_item":
            # structure_item: let_assign | field_or_expr
            return lark_to_cop(kids[0])

        case "field_or_expr":
            # field_or_expr: TOKENFIELD EQUALS expression -> named_field | expression
            # This should just recurse to the child
            return lark_to_cop(kids[0])

        case "path_assign":
            # identifier EQUALS unary -> path_assign
            # Covers simple names (foo=val), dollar paths ($.field=val), etc.
            # kids[0] = identifier tree, kids[1] = EQUALS, kids[2] = unary
            name_cop = lark_to_cop(kids[0])
            value_cop = lark_to_cop(kids[2])
            return _parsed(tree, "struct.namefield", [name_cop, value_cop], op="=")

        case "text_field":
            # text EQUALS unary -> text_field  (e.g. "key" = value in structures)
            # kids[0] = text tree, kids[1] = EQUALS, kids[2] = unary
            name_cop = lark_to_cop(kids[0])
            value_cop = lark_to_cop(kids[2])
            return _parsed(tree, "struct.namefield", [name_cop, value_cop], op="=")

        case "deep_named_field":
            # deep_named_field: DOTTED_PATH EQUALS expression
            # kids[0] = DOTTED_PATH token  e.g. "one.two.three"
            # kids[1] = EQUALS token
            # kids[2] = expression
            path_str = str(kids[0])           # "one.two.three" (Token is a str subclass)
            segments = path_str.split(".")    # ["one", "two", "three"]
            value_cop = lark_to_cop(kids[2])

            # Build nested struct COPs from right to left so that
            #   one.two.three = val  becomes  struct.namefield(one, {two: {three: val}})
            current = value_cop
            for seg in reversed(segments[1:]):
                seg_cop = _parsed(kids[0], "ident.token", [], value=seg)
                namefield = _parsed(tree, "struct.namefield", [seg_cop, current], op="=")
                current = _parsed(tree, "struct.define", [namefield])

            root_cop = _parsed(kids[0], "ident.token", [], value=segments[0])
            return _parsed(tree, "struct.namefield", [root_cop, current], op="=")

        case "expr_named_field":
            # expr_named_field: QUOTE expression QUOTE EQUALS unary
            # kids: QUOTE, expression, QUOTE, EQUALS, unary
            expr_cop = lark_to_cop(kids[1])  # The expression between quotes
            value_cop = lark_to_cop(kids[4])  # The value after EQUALS
            name_cop = _parsed(tree, "ident.expr", [expr_cop])
            return _parsed(tree, "struct.namefield", [name_cop, value_cop], op="=")

        case "dotted_path_atom":
            # dotted_path_atom: DOTTED_PATH
            # kids[0] = DOTTED_PATH token  e.g. "one.two.three"
            # Represent as a value.identifier so codegen treats it as LoadLocal + GetField chain
            path_str = str(kids[0])
            segments = path_str.split(".")
            segment_cops = [_parsed(kids[0], "ident.token", [], value=seg) for seg in segments]
            return _parsed(tree, "value.identifier", segment_cops)

        case "struct_field":
            if len(kids) == 1:
                value = lark_to_cop(kids[0])
                return _parsed(tree, "struct.posfield", [value])
            name = lark_to_cop(kids[0])
            op = kids[1].value
            value = lark_to_cop(kids[2])
            return _parsed(tree, "struct.namefield", [name, value], op=op)

        case "my_expr":
            # my_expr: OP_MY field_or_expr
            # !my is a scope prefix on any expression (including assignments)
            # kids[0] = OP_MY token, kids[1] = field_or_expr tree
            inner_cop = lark_to_cop(kids[1])
            # Decompose struct.namefield (assignment form) → op.my(name, value)
            if comp.cop_tag(inner_cop) == "struct.namefield":
                return _parsed(tree, "op.my", list(comp.cop_kids(inner_cop)))
            return _parsed(tree, "op.my", [inner_cop])

        case "ctx_expr":
            # ctx_expr: OP_CTX field_or_expr
            # kids[0] = OP_CTX token, kids[1] = field_or_expr tree
            inner_cop = lark_to_cop(kids[1])
            if comp.cop_tag(inner_cop) == "struct.namefield":
                return _parsed(tree, "op.ctx", list(comp.cop_kids(inner_cop)))
            return _parsed(tree, "op.ctx", [inner_cop])

        case "stash_assign":
            # stash_assign: OP_STASH identifier AMPERSAND TOKENFIELD stash_deep* expression
            # kids: [OP_STASH, identifier, AMPERSAND, TOKENFIELD, *stash_deep, expression]
            target_cop = lark_to_cop(kids[1])
            key_str = kids[3].value  # TOKENFIELD after &
            key_cop = _parsed(kids[3], "ident.token", [], value=key_str)
            # kids[4:-1] are stash_deep trees; kids[-1]=expression
            deep_cops = []
            for kid in kids[4:-1]:
                if isinstance(kid, lark.Tree) and kid.data == "stash_deep":
                    field_name = kid.children[1].value  # DOT + TOKENFIELD
                    deep_cops.append(_parsed(kid, "ident.token", [], value=field_name))
            value_cop = lark_to_cop(kids[-1])
            all_kids = [target_cop, key_cop] + deep_cops + [value_cop]
            return _parsed(tree, "op.stash", all_kids)

        # "block" case removed — old grammar rule replaced by capture_expr

        case "mod_field":
            name = lark_to_cop(kids[0])
            op = kids[1].value
            value = lark_to_cop(kids[2])
            return _parsed(tree, "mod.namefield", [name, value], op=op)

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
            # Returns a list: [base_type, optional shape.unit, optional value.limit(s), optional shape.repeat]
            base = lark_to_cop(kids[0])
            extras = []

            for kid in kids[1:]:
                if isinstance(kid, lark.Tree):
                    if kid.data == "unit_suffix":
                        # unit_suffix: HASH identifier
                        unit_ident = lark_to_cop(kid.children[1])
                        unit_cop = _parsed(kid, "shape.unit", [unit_ident])
                        extras.append(unit_cop)
                    elif kid.data == "limit_suffix":
                        # limit_suffix: ANGLE_OPEN limit_field+ ANGLE_CLOSE
                        # Each limit_field becomes a value.limit node:
                        # 1 kid = bare name (e.g. integer), 2 kids = name + value (e.g. min=1)
                        for limit_field in kid.children[1:-1]:  # Skip ANGLE_OPEN and ANGLE_CLOSE
                            if isinstance(limit_field, lark.Tree) and limit_field.data == "limit_field":
                                # limit_field: (identifier EQUALS | DOTTED_PATH EQUALS)? simple_expr
                                limit_kids = []
                                for lf_kid in limit_field.children:
                                    if isinstance(lf_kid, lark.Token) and lf_kid.type == "DOTTED_PATH":
                                        # e.g. "limit.min" — build a value.identifier COP
                                        segments = str(lf_kid).split(".")
                                        seg_cops = [_parsed(lf_kid, "ident.token", [], value=s) for s in segments]
                                        limit_kids.append(_parsed(lf_kid, "value.identifier", seg_cops))
                                    elif isinstance(lf_kid, lark.Tree):
                                        limit_kids.append(lark_to_cop(lf_kid))
                                    # Skip EQUALS token

                                limit_cop = _parsed(limit_field, "value.limit", limit_kids)
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
            # If shape returns a list (e.g., with default), handle appropriately
            result = lark_to_cop(kids[0])
            if isinstance(result, list):
                # If first element is a shape.union, add extra kids (e.g. shape.default) into it
                if result and comp.cop_tag(result[0]) == "shape.union":
                    union_cop = result[0]
                    extra_kids = result[1:]
                    existing_kids = list(comp.cop_kids(union_cop))
                    return _parsed(kids[0], "shape.union", existing_kids + extra_kids)
                # Otherwise (single-type with unit/default/etc), wrap in a shape.field
                # inside a shape.define so the codegen shape handler sees the right structure.
                field = _parsed(tree, "shape.field", result)
                return _parsed(tree, "shape.define", [field])
            return result

        case "start_func" | "start_mod" | "start_package" | "start_import":
            # These are entry points that wrap the actual content
            # Just pass through to the first child
            return lark_to_cop(kids[0])

        case "start_startup":
            # start_startup: startup_deps func_struct | func_struct
            # Parse optional deps and body into a startup.define COP
            deps = []
            body_cop = None
            for kid in kids:
                if isinstance(kid, lark.Tree):
                    if kid.data == "startup_deps":
                        for dep_kid in kid.children:
                            if isinstance(dep_kid, lark.Tree) and dep_kid.data == "identifier":
                                dep_cop = lark_to_cop(dep_kid)
                                dep_name = _identifier_to_string(dep_cop)
                                if dep_name:
                                    deps.append(dep_name)
                    elif kid.data in ("func_struct", "statement", "structure"):
                        body_cop = lark_to_cop(kid)
            if body_cop is None:
                body_cop = _parsed(tree, "struct.define", [])
            return _parsed(tree, "startup.define", [body_cop], deps=deps)

        case "start_main":
            # start_main: main_deps func_struct | func_struct
            # Parse optional deps and body into a main.define COP
            deps = []
            body_tree = None
            for kid in kids:
                if isinstance(kid, lark.Tree):
                    if kid.data == "main_deps":
                        for dep_kid in kid.children:
                            if isinstance(dep_kid, lark.Tree) and dep_kid.data == "identifier":
                                dep_cop = lark_to_cop(dep_kid)
                                dep_name = _identifier_to_string(dep_cop)
                                if dep_name:
                                    deps.append(dep_name)
                    elif kid.data == "func_struct":
                        body_tree = kid
                    elif kid.data in ("statement", "structure"):
                        body_tree = kid
            body_cop = lark_to_cop(body_tree) if body_tree else _parsed(tree, "statement.define", [])
            # Wrap body in a function.define
            func_def = _parsed(tree, "function.define", [body_cop])
            return _parsed(tree, "main.define", [func_def], deps=deps)

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
            # tag_item: identifier AMPERSAND? (BRACE_OPEN tag_item* BRACE_CLOSE)?
            # For now, just convert identifier; nested tag items not yet supported
            is_private = any(
                isinstance(k, lark.Token) and k.type == "AMPERSAND"
                for k in kids
            )
            ident_cop = lark_to_cop(kids[0])
            if is_private:
                return _parsed(tree, "value.private_tag", [ident_cop])
            return ident_cop

        case "func_body":
            # func_body: shape wrapper* func_struct | wrapper+ func_struct | func_struct
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
                func_def = _parsed(tree, "function.define", [func_sig_cop, body_cop])
            else:
                # No input signature - just body
                func_def = _parsed(tree, "function.define", [body_cop])

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
                    result = _parsed(tree, "value.wrapper", [wrapper_cop, result])
                return result

            return base_cop

        # binding_expr and binding_value removed — replaced by binding/named_binding/bare_binding

        case "signature":
            # signature: signature_decl+
            # Convert to shape.define
            field_cops = [lark_to_cop(kid) for kid in kids]
            return _parsed(tree, "shape.define", field_cops)

        case "signature_decl":
            return lark_to_cop(kids[0])

        case "param_decl":
            # param_decl: OP_PARAM_DECL identifier shape (EQUALS field_default_value)?
            # kids[0] = OP_PARAM_DECL, kids[1] = identifier, kids[2] = shape, kids[3] = EQUALS (optional), kids[4] = value (optional)
            name_cop = lark_to_cop(kids[1])
            shape_cop = lark_to_cop(kids[2])

            # Check for default value
            default_cop = None
            if len(kids) > 3:
                # Has default value (skip EQUALS at kids[3])
                default_cop = lark_to_cop(kids[4])

            # Extract name as string for the field name
            name_str = None
            if comp.cop_tag(name_cop) == "value.identifier":
                first_kid = list(comp.cop_kids(name_cop))[0]
                if comp.cop_tag(first_kid) == "ident.token":
                    name_str = first_kid.field("value").data

            # Build signature.param field
            field_kids = list(shape_cop) if isinstance(shape_cop, list) else [shape_cop]
            if default_cop:
                field_kids.append(default_cop)
            return _parsed(tree, "signature.param", field_kids, name=name_str)

        case "depend_decl":
            name_cop = lark_to_cop(kids[1])
            shape_cop = lark_to_cop(kids[2])

            default_cop = None
            if len(kids) > 3:
                default_cop = lark_to_cop(kids[4])

            name_str = None
            if comp.cop_tag(name_cop) == "value.identifier":
                first_kid = list(comp.cop_kids(name_cop))[0]
                if comp.cop_tag(first_kid) == "ident.token":
                    name_str = first_kid.field("value").data

            field_kids = list(shape_cop) if isinstance(shape_cop, list) else [shape_cop]
            if default_cop:
                field_kids.append(default_cop)
            return _parsed(tree, "signature.depend", field_kids, name=name_str)

        case "delivers_decl":
            name_cop = lark_to_cop(kids[1])
            shape_cop = lark_to_cop(kids[2])

            name_str = None
            if comp.cop_tag(name_cop) == "value.identifier":
                first_kid = list(comp.cop_kids(name_cop))[0]
                if comp.cop_tag(first_kid) == "ident.token":
                    name_str = first_kid.field("value").data

            field_kids = list(shape_cop) if isinstance(shape_cop, list) else [shape_cop]
            return _parsed(tree, "signature.delivers", field_kids, name=name_str)

        case "deliver_expr":
            name_cop = lark_to_cop(kids[1])
            value_cop = lark_to_cop(kids[2])
            return _parsed(tree, "op.deliver", [name_cop, value_cop])

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
            return _parsed(tree, "ident.input", [], value=dollar_value)

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
            
            # Wrap the spec in shape.define (if it's not already wrapped).
            # Lists have extras (unit/limits/repeat) — put them inside shape.field
            # so _build_shape can find the repeat and emit BuildShapeCollection.
            if isinstance(shape_spec, list):
                shape_field = _parsed(shape_lark, "shape.field", shape_spec)
                shape_cop = _parsed(shape_lark, "shape.define", [shape_field])
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
            # Wraps the expression in op.defer so codegen produces an anonymous
            # Block that executes expr when called, rather than calling it now.
            inner_cop = lark_to_cop(kids[1])
            return _parsed(tree, "op.defer", [inner_cop])

        case "forward_expr":
            # forward_expr: OP_FORWARD
            # Re-dispatch to the next less-specific overload (no kids).
            return _parsed(tree, "op.forward", [])

        case "handle_grab":
            # handle_grab: OP_GRAB expression expression
            # kids[0] = OP_GRAB token, kids[1] = tag expression, kids[2] = initial private data
            target = lark_to_cop(kids[1])
            data = lark_to_cop(kids[2])
            return _parsed(tree, "value.handle", [target, data], op="grab")

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


def _merge_same_name_namefields(items):
    """Merge struct.namefield items sharing a name when both values are struct.define.

    Deep assignments like ``one.a = 1`` and ``one.b = 2`` each produce a
    ``struct.namefield(one, struct.define([...]))`` COP.  When two or more of
    these share the same base name, we combine their inner struct.define
    children into a single struct.define so the result is ``one = {a:1, b:2}``
    rather than last-write-wins ``one = {b:2}``.

    Non-struct or non-namefield items are left unchanged.  The merged item
    occupies the position of the FIRST occurrence of that name.
    """
    # Find names that appear more than once as struct.namefield with struct.define value
    name_positions = {}  # name → list of (index-in-result, item)
    for item in items:
        if comp.cop_tag(item) != "struct.namefield":
            continue
        item_kids = list(comp.cop_kids(item))
        if len(item_kids) < 2:
            continue
        name_kid = item_kids[0]
        if comp.cop_tag(name_kid) != "ident.token":
            continue
        if comp.cop_tag(item_kids[1]) != "struct.define":
            continue
        name = name_kid.to_python("value")
        name_positions.setdefault(name, []).append(item)

    # Only names with 2+ struct.define contributions need merging
    to_merge = {n: v for n, v in name_positions.items() if len(v) > 1}
    if not to_merge:
        return items

    # Build output: replace first occurrence of each mergeable name with the
    # combined item; drop subsequent occurrences.
    seen = set()
    result = []
    for item in items:
        if comp.cop_tag(item) == "struct.namefield":
            item_kids = list(comp.cop_kids(item))
            if (len(item_kids) >= 2
                    and comp.cop_tag(item_kids[0]) == "ident.token"
                    and comp.cop_tag(item_kids[1]) == "struct.define"):
                name = item_kids[0].to_python("value")
                if name in to_merge:
                    if name in seen:
                        continue  # skip duplicate; already merged into first
                    seen.add(name)
                    # Combine all struct.define children for this name
                    combined_kids = []
                    for src_item in to_merge[name]:
                        src_kids = list(comp.cop_kids(src_item))
                        combined_kids.extend(list(comp.cop_kids(src_kids[1])))
                    merged_struct = comp.create_cop("struct.define", combined_kids)
                    merged_item = comp.create_cop(
                        "struct.namefield", [item_kids[0], merged_struct], op="="
                    )
                    result.append(merged_item)
                    continue
        result.append(item)
    return result


# cached lark parsers
_parsers = {}
# Timing accumulators (seconds): grammar init vs actual parse
_time_grammar_init = 0.0
_time_parse = 0.0

