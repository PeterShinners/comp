"""Describe module definitions for documentation and tooling.

Provides functions to gather structured information about named definitions
in a module and format them as human-readable markdown reports.

Main entry points:
    describe_name(module, name) -> dict | None
    format_describe_markdown(description) -> str

The description dict holds a ``"kind"`` field that drives formatting:

    "function" -- one or more !func / !pure overloads
    "shape"    -- a single !shape definition with optional recursive refs

The structure is designed to carry more info over time (references, return
shape analysis, compile errors) without breaking the formatting layer.
"""

__all__ = [
    "describe_name",
    "gather_statement_comments",
    "extract_input_shape",
    "extract_params",
    "extract_shape_info",
    "collect_type_refs",
    "format_describe_markdown",
]

import comp

# Type names treated as language primitives -- not followed for recursive display
_PRIMITIVE_TYPES = frozenset({"num", "text", "bool", "nil", "any", "func", "shape"})


def _cop_line_range(cop):
    """Extract (start_line, end_line) as ints from a cop node's pos field.

    Args:
        cop: (Value) COP node with an embedded "pos" struct

    Returns:
        (tuple | None) (start_line, end_line) as ints, or None if unavailable
    """
    try:
        pos_val = cop.field("pos")
        nums = [int(v.data) for v in pos_val.data.values()]
        return (nums[0], nums[2])  # start_line, end_line
    except Exception:
        return None


def _has_code_before(line_num, col, source_lines):
    """Return True if the source line has non-whitespace text before column col.

    Used to distinguish a suffix line comment (code precedes // on the same line)
    from a standalone comment (only whitespace before //).

    Args:
        line_num: (int) 1-based line number
        col: (int) 1-based column of the comment's start
        source_lines: (list) Source split by lines

    Returns:
        (bool) True when code precedes the comment
    """
    if line_num < 1 or line_num > len(source_lines):
        return False
    before = source_lines[line_num - 1][:col - 1]
    return bool(before.strip())


# ---------------------------------------------------------------------------
# Public gather API
# ---------------------------------------------------------------------------

def describe_name(module, name):
    """Gather a complete description for a named definition.

    Dispatches on definition kind -- shapes and function overloads each produce
    distinct description dicts, both accepted by format_describe_markdown.

    Args:
        module: (Module) The module to inspect
        name: (str) Base name to describe (e.g. "tree-insert", "tree", "total")

    Returns:
        (dict | None) Description dict, or None if the name is not found.

        Function description structure::

            {
                "kind": "function",
                "name": str,
                "module_resource": str,
                "overloads": [
                    {
                        "qualified": str,
                        "operator": str,           # "func" or "pure"
                        "pure": bool,
                        "pos": tuple,
                        "input_shape": str | None,
                        "params": [
                            {"kind", "name", "shape", "default"},
                            ...
                        ],
                        "comments": {"preceding", "internal", "suffix"},
                    },
                    ...
                ],
            }

        Shape description structure::

            {
                "kind": "shape",
                "name": str,
                "module_resource": str,
                "pos": tuple,
                "comments": {"preceding", "internal", "suffix"},
                "shape_info": {
                    "kind": "struct" | "union" | "other",
                    "raw": str,
                    "fields": [               # struct
                        {"name", "type_str", "modifiers", "default"},
                        ...
                    ],
                    "options": [              # union
                        {"type_str"},
                        ...
                    ],
                    "default": str | None,    # union default
                },
                "referenced_shapes": {        # named shapes used in fields/options
                    name: {
                        "pos": tuple,
                        "comments": {"preceding", "internal", "suffix"},
                        "shape_info": {...},
                    },
                    ...
                },
            }

        Each "doc" entry is a dict with keys "content", "type", "pos".
    """
    statements = module.statements()
    definitions = module.definitions()
    docs = module.scan().to_python("docs") or []

    # Check for a shape first
    shape_stmt = next(
        (s for s in statements if s.get("name") == name and s.get("operator") == "shape"),
        None,
    )
    if shape_stmt is not None:
        return _describe_shape(module, name, shape_stmt, definitions, docs, statements)

    # Fall back to func / pure overloads
    matching = [
        s for s in statements
        if s.get("name") == name and s.get("operator") in ("func", "pure")
    ]
    if not matching:
        return None

    overload_index = _build_overload_index(statements)

    overloads = []
    for stmt in matching:
        qualified = overload_index.get(id(stmt))
        if qualified is None:
            continue
        definition = definitions.get(qualified)

        pos = stmt.get("pos") or (0, 0, 0, 0)
        start_line = pos[0] if len(pos) > 0 else 0
        end_line = pos[2] if len(pos) > 2 else start_line

        comments = gather_statement_comments(docs, start_line, end_line)

        cop = definition.original_cop if definition else None
        input_shape = extract_input_shape(cop) if cop else None
        params = extract_params(cop) if cop else []

        overloads.append({
            "qualified": qualified,
            "operator": stmt.get("operator", "func"),
            "pure": stmt.get("operator") == "pure",
            "pos": pos,
            "input_shape": input_shape,
            "params": params,
            "comments": comments,
        })

    if not overloads:
        return None

    return {
        "kind": "function",
        "name": name,
        "module_resource": module.source.resource,
        "overloads": overloads,
    }


def _describe_shape(module, name, stmt, definitions, docs, statements):
    """Build the shape description dict.

    Args:
        module: (Module) The module
        name: (str) Shape name
        stmt: (dict) Statement dict from module.statements()
        definitions: (dict) module.definitions()
        docs: (list) All scan docs
        statements: (list) All statements (for line-range lookups)

    Returns:
        (dict) Shape description or None
    """
    definition = definitions.get(name)
    if definition is None:
        return None

    source_lines = module.source.content.splitlines()

    pos = stmt.get("pos") or (0, 0, 0, 0)
    start_line = pos[0] if len(pos) > 0 else 0
    end_line = pos[2] if len(pos) > 2 else start_line
    comments = gather_statement_comments(docs, start_line, end_line, source_lines)

    cop = definition.original_cop
    shape_info = extract_shape_info(cop) if cop else {"kind": "other", "raw": ""}
    annotate_field_comments(shape_info, docs, source_lines)

    # If the statement-level suffix comment was consumed by a field, suppress the
    # duplicate so it doesn't appear twice in the output.
    if comments.get("suffix"):
        suffix_content = comments["suffix"].get("content", "")
        if any(f.get("comment") == suffix_content for f in (shape_info.get("fields") or [])):
            comments["suffix"] = None

    # Collect referenced shape names (non-primitive identifiers) and resolve them
    refs = collect_type_refs(cop) if cop else set()
    refs.discard(name)  # drop self-reference

    referenced_shapes = {}
    for ref_name in sorted(refs):
        if ref_name in _PRIMITIVE_TYPES:
            continue
        ref_def = definitions.get(ref_name)
        if ref_def is None or ref_def.shape is not comp.shape_shape:
            continue
        # Find the statement for this shape to get its pos / comments
        ref_stmt = next(
            (s for s in statements
             if s.get("name") == ref_name and s.get("operator") == "shape"),
            None,
        )
        ref_pos = ref_stmt.get("pos") if ref_stmt else (0, 0, 0, 0)
        ref_start = ref_pos[0] if ref_pos and len(ref_pos) > 0 else 0
        ref_end = ref_pos[2] if ref_pos and len(ref_pos) > 2 else ref_start
        ref_comments = gather_statement_comments(docs, ref_start, ref_end, source_lines)
        ref_info = extract_shape_info(ref_def.original_cop) if ref_def.original_cop else {
            "kind": "other", "raw": ""
        }
        annotate_field_comments(ref_info, docs, source_lines)
        referenced_shapes[ref_name] = {
            "pos": ref_pos,
            "comments": ref_comments,
            "shape_info": ref_info,
        }

    return {
        "kind": "shape",
        "name": name,
        "module_resource": module.source.resource,
        "pos": pos,
        "comments": comments,
        "shape_info": shape_info,
        "referenced_shapes": referenced_shapes,
    }


def _build_overload_index(statements):
    """Return {id(stmt): qualified_name} mirroring Module._process_func_statement numbering.

    Args:
        statements: (list) From module.statements()

    Returns:
        (dict) {id(stmt): qualified_name}
    """
    counters = {}
    index = {}
    for stmt in statements:
        if stmt.get("operator") not in ("func", "pure"):
            continue
        name = stmt.get("name")
        if not name:
            continue
        n = counters.get(name, 0) + 1
        counters[name] = n
        index[id(stmt)] = f"{name}.i{n:03d}"
    return index


# ---------------------------------------------------------------------------
# Shape cop analysis
# ---------------------------------------------------------------------------

def extract_shape_info(cop):
    """Parse a shape cop node into a structured dict.

    Handles ``shape.define`` (struct), ``shape.union``, and falls back to
    a raw unparse for anything else.

    Args:
        cop: (Value) COP node, typically a shape.define or shape.union

    Returns:
        (dict) Shape info::

            {
                "kind":    "struct" | "union" | "other",
                "raw":     str,                # full cop_unparse
                "fields":  [                   # struct only
                    {
                        "name":      str,
                        "type_str":  str,
                        "modifiers": str,      # e.g. "*", "**", or ""
                        "default":   str | None,
                    },
                    ...
                ],
                "options": [                   # union only
                    {"type_str": str},
                    ...
                ],
                "default": str | None,         # union default value
            }
    """
    tag = comp.cop_tag(cop)
    raw = comp.cop_unparse(cop)

    if tag == "shape.define":
        fields = []
        for field_cop in comp.cop_kids(cop):
            if comp.cop_tag(field_cop) != "shape.field":
                continue
            fname = None
            try:
                fname = field_cop.to_python("name", None)
            except (KeyError, AttributeError):
                pass
            if fname is None:
                continue  # unnamed field in a union-style define -- skip

            kids = list(comp.cop_kids(field_cop))
            type_str = ""
            modifiers = ""
            default = None
            for k in kids:
                ktag = comp.cop_tag(k)
                if ktag == "value.identifier":
                    type_str = comp.cop_unparse(k)
                elif ktag == "shape.repeat":
                    try:
                        modifiers = k.to_python("op", "*")
                    except (KeyError, AttributeError):
                        modifiers = "*"
                elif ktag == "shape.default":
                    raw_default = comp.cop_unparse(k)
                    default = raw_default.strip().lstrip("=").strip()

            # Extract line range from cop pos for comment-matching later
            line_range = _cop_line_range(field_cop)
            fields.append({
                "name": fname,
                "type_str": type_str,
                "modifiers": modifiers,
                "default": default,
                "start_line": line_range[0] if line_range else None,
                "end_line": line_range[1] if line_range else None,
                "comment": None,  # populated by annotate_field_comments
            })
        return {"kind": "struct", "raw": raw, "display": raw, "fields": fields, "options": [], "default": None}

    if tag == "shape.union":
        options = []
        default = None
        for k in comp.cop_kids(cop):
            ktag = comp.cop_tag(k)
            if ktag == "shape.field":
                opt_kids = list(comp.cop_kids(k))
                type_str = comp.cop_unparse(opt_kids[0]) if opt_kids else "?"
                options.append({"type_str": type_str})
            elif ktag == "shape.default":
                raw_default = comp.cop_unparse(k)
                default = raw_default.strip().lstrip("=").strip()
        # Build a clean display string free of the shape.default-in-union artifact
        display = "~" + " | ".join(o["type_str"] for o in options)
        if default:
            display += f" = {default}"
        return {"kind": "union", "raw": raw, "display": display, "fields": [], "options": options, "default": default}

    return {"kind": "other", "raw": raw, "display": raw, "fields": [], "options": [], "default": None}


def collect_type_refs(cop):
    """Walk a shape cop node and collect referenced type identifier names.

    Only collects ``ident.token`` names found inside ``value.identifier``
    nodes.  Does not follow into nested function definitions.

    Args:
        cop: (Value) COP node to walk (typically a shape define/union)

    Returns:
        (set) String names referenced as types (e.g. {"branch", "num", "nil"})
    """
    refs = set()
    _walk_type_refs(cop, refs)
    return refs


def _walk_type_refs(cop, refs):
    """Recursive helper for collect_type_refs."""
    if cop is None:
        return
    tag = comp.cop_tag(cop)
    if tag == "value.identifier":
        for kid in comp.cop_kids(cop):
            if comp.cop_tag(kid) == "ident.token":
                try:
                    refs.add(kid.field("value").data)
                except (KeyError, AttributeError):
                    pass
        return  # don't recurse further into identifier internals
    for kid in comp.cop_kids(cop):
        _walk_type_refs(kid, refs)


def annotate_field_comments(shape_info, docs, source_lines):
    """Match suffix line comments to struct fields and store them on the field dict.

    Uses the rule: a line comment where code precedes ``//`` on the same source
    line is a suffix comment.  The comment attaches to the field whose
    ``end_line`` matches the comment's line -- i.e. the outermost thing ending
    there (fields don't nest, so there is at most one per line).

    Only operates on ``shape.define`` (struct) shape_info dicts.  Modifies
    field dicts in-place by setting their ``"comment"`` key.

    Args:
        shape_info: (dict) Result from extract_shape_info()
        docs: (list) Comment dicts from module.scan().to_python("docs")
        source_lines: (list) Source split by ``str.splitlines()``
    """
    if shape_info.get("kind") != "struct":
        return

    # Build a lookup: end_line -> field (only fields that have line info)
    line_to_field = {}
    for field in shape_info["fields"]:
        end_line = field.get("end_line")
        if end_line is not None:
            line_to_field[end_line] = field

    for doc in docs:
        if doc.get("type") != "line":
            continue
        pos = doc.get("pos") or (0, 0, 0, 0)
        doc_line = pos[0] if len(pos) > 0 else 0
        doc_col = pos[1] if len(pos) > 1 else 1
        if doc_line not in line_to_field:
            continue
        # Only attach if code precedes // on that line (suffix, not standalone)
        if _has_code_before(doc_line, doc_col, source_lines):
            field = line_to_field[doc_line]
            if field["comment"] is None:  # first match wins
                field["comment"] = doc["content"]


# ---------------------------------------------------------------------------
# Function cop analysis
# ---------------------------------------------------------------------------

def gather_statement_comments(docs, stmt_start_line, stmt_end_line, source_lines=None):
    """Categorize scan docs relative to a statement's line range.

    Comment categories:

    - **preceding**: comments whose end line is immediately adjacent to
      ``stmt_start_line``, forming an unbroken block (stops at a gap).
    - **internal**: comments entirely inside the statement's line range
      (not on the closing line).
    - **suffix**: a ``line`` comment on ``stmt_end_line`` that has code
      before it on the same source line (i.e. not standalone).

    Args:
        docs: (list) Comment dicts from ``module.scan().to_python("docs")``,
              each with "content", "type", "pos" (4-tuple).
        stmt_start_line: (int) First source line of the statement (1-based).
        stmt_end_line: (int) Last source line of the statement (1-based).
        source_lines: (list | None) Source split by splitlines(), used to
              distinguish suffix from standalone comments.

    Returns:
        (dict) With keys "preceding" (list), "internal" (list), "suffix" (dict | None).
    """
    before = []
    internal = []
    suffix = None

    for doc in docs:
        pos = doc.get("pos") or (0, 0, 0, 0)
        doc_start = pos[0] if len(pos) > 0 else 0
        doc_end = pos[2] if len(pos) > 2 else doc_start

        if doc_start == stmt_end_line and doc.get("type") == "line":
            # Suffix only when code precedes // on that line; standalone → internal
            doc_col = pos[1] if len(pos) > 1 else 1
            if source_lines is None or _has_code_before(doc_start, doc_col, source_lines):
                suffix = doc
                continue
        if doc_start >= stmt_start_line and doc_end <= stmt_end_line:
            internal.append(doc)
        elif doc_end < stmt_start_line:
            before.append(doc)

    # Walk backwards from stmt_start_line collecting adjacent comments
    preceding = []
    boundary = stmt_start_line
    for doc in reversed(before):
        pos = doc.get("pos") or (0, 0, 0, 0)
        doc_end = pos[2] if len(pos) > 2 else 0
        doc_start = pos[0] if len(pos) > 0 else 0
        if doc_end >= boundary - 1:
            preceding.insert(0, doc)
            boundary = doc_start
        else:
            break

    return {
        "preceding": preceding,
        "internal": internal,
        "suffix": suffix,
    }


def extract_input_shape(cop):
    """Extract the input shape string from a function.define cop node.

    Navigates: function.define -> function.signature -> signature.input
    and unparses the result.

    Args:
        cop: (Value) COP node -- typically a function.define

    Returns:
        (str | None) Unparsed shape text (e.g. "~nil", "~tree | nil"), or
        None when the function has no input-shape constraint.
    """
    if comp.cop_tag(cop) != "function.define":
        return None
    kids = list(comp.cop_kids(cop))
    if not kids:
        return None
    first = kids[0]
    if comp.cop_tag(first) != "function.signature":
        return None
    for sig_kid in comp.cop_kids(first):
        if comp.cop_tag(sig_kid) == "signature.input":
            return comp.cop_unparse(sig_kid)
    return None


def extract_params(cop):
    """Walk a cop node tree and collect all parameter / block declarations.

    Finds ``signature.param`` and ``signature.block`` nodes anywhere in the
    tree (typically inside the function body's block.signature).

    Args:
        cop: (Value) COP node to walk

    Returns:
        (list) Ordered list of dicts::

            {
                "kind":    "param" | "block",
                "name":    str,
                "shape":   str | None,
                "default": str | None,
            }
    """
    result = []
    _walk_params(cop, result)
    return result


def _walk_params(cop, result):
    """Recursively collect param/block info from a cop subtree."""
    if cop is None:
        return
    tag = comp.cop_tag(cop)

    if tag == "signature.param":
        _collect_param(cop, "param", result)
        return  # params don't nest
    if tag == "signature.block":
        _collect_param(cop, "block", result)
        return

    for kid in comp.cop_kids(cop):
        _walk_params(kid, result)


def _collect_param(cop, kind, result):
    """Append a single param/block entry to result."""
    name = None
    try:
        name = cop.to_python("name", None)
    except (KeyError, AttributeError):
        pass

    kids = list(comp.cop_kids(cop))

    shape_str = None
    default_str = None

    if kids:
        shape_str = comp.cop_unparse(kids[0])

    for kid in kids[1:]:
        tag = comp.cop_tag(kid)
        raw = comp.cop_unparse(kid)
        if tag == "shape.default":
            # strip " = " prefix baked into shape.default unparse
            default_str = raw.strip().lstrip("=").strip()
        else:
            default_str = raw

    result.append({
        "kind": kind,
        "name": name or "?",
        "shape": shape_str,
        "default": default_str,
    })


# ---------------------------------------------------------------------------
# Markdown formatter
# ---------------------------------------------------------------------------

def format_describe_markdown(description):
    """Format a describe_name() result as a markdown report.

    Dispatches to shape or function formatter based on description["kind"].

    Args:
        description: (dict | None) Result from describe_name()

    Returns:
        (str) Markdown text.
    """
    if description is None:
        return "_Name not found._"

    kind = description.get("kind", "function")
    if kind == "shape":
        return _format_shape_markdown(description)
    return _format_function_markdown(description)


def _format_function_markdown(description):
    """Render a function/pure description as markdown."""
    name = description["name"]
    resource = description["module_resource"]
    overloads = description["overloads"]
    n_overloads = len(overloads)

    out = []
    out.append(f"# `{name}`")

    # Module + overload count on one summary line
    header_parts = [f"`{resource}`"]
    if n_overloads > 1:
        header_parts.append(f"{n_overloads} overloads")
    out.append("module " + " \u00b7 ".join(header_parts))
    out.append("")

    for i, ov in enumerate(overloads):
        if n_overloads > 1:
            out.append(f"### `{ov['qualified']}`")
            out.append("")

        # Preceding doc comments as prose
        for doc in ov["comments"]["preceding"]:
            out.append(doc["content"])
        if ov["comments"]["preceding"]:
            out.append("")

        # One-line summary: kind · input · lines
        pos = ov["pos"] or (0, 0, 0, 0)
        summary_parts = [f"!{'pure' if ov['pure'] else 'func'}"]
        shape = ov["input_shape"]
        summary_parts.append(shape if shape else "~any")
        if pos[0]:
            end = pos[2]
            line_str = f"line {pos[0]}" if pos[0] == end else f"lines {pos[0]}\u2013{end}"
            summary_parts.append(line_str)
        out.append(" \u00b7 ".join(summary_parts))
        out.append("")

        # Parameters: one bullet per param/block
        params = ov["params"]
        if params:
            for p in params:
                parts = [f"  - :{p['kind']} {p['name']}"]
                if p["shape"]:
                    parts.append(f"~{p['shape']}")
                if p["default"]:
                    parts.append(f"= {p['default']}")
                out.append("  ".join(parts))
            out.append("")

        # Internal comments as // lines
        for doc in ov["comments"]["internal"]:
            out.append(f"  // {doc['content']}")
        if ov["comments"]["internal"]:
            out.append("")

        # Suffix comment on closing line
        suffix = ov["comments"]["suffix"]
        if suffix:
            out.append(f"  // {suffix['content']}")
            out.append("")

    return "\n".join(out)


def _format_shape_markdown(description):
    """Render a shape description as markdown."""
    name = description["name"]
    resource = description["module_resource"]
    pos = description.get("pos") or (0, 0, 0, 0)
    comments = description["comments"]
    shape_info = description["shape_info"]
    referenced_shapes = description.get("referenced_shapes") or {}

    out = []
    out.append(f"# `{name}`")

    # Module on one line
    out.append(f"module `{resource}`")
    out.append("")

    # Preceding comments as prose
    for doc in comments["preceding"]:
        out.append(doc["content"])
    if comments["preceding"]:
        out.append("")

    # One-line summary: kind · line · definition
    skind = shape_info["kind"]
    label = "struct" if skind == "struct" else "union" if skind == "union" else "shape"
    summary_parts = [f"!shape {label}"]
    if pos[0]:
        end = pos[2]
        summary_parts.append(f"line {pos[0]}" if pos[0] == end else f"lines {pos[0]}\u2013{end}")
    summary_parts.append(shape_info.get("display", shape_info["raw"]))
    out.append(" \u00b7 ".join(summary_parts))
    out.append("")

    # Struct fields: one bullet per field
    if skind == "struct" and shape_info["fields"]:
        for f in shape_info["fields"]:
            parts = [f"  - {f['name']}"]
            type_part = f"~{f['type_str']}"
            if f["modifiers"]:
                type_part += f["modifiers"]
            parts.append(type_part)
            if f["default"]:
                parts.append(f"= {f['default']}")
            line = "  ".join(parts)
            if f.get("comment"):
                line += f"  // {f['comment']}"
            out.append(line)
        out.append("")

    # Union variants: inline or one bullet per option
    elif skind == "union" and shape_info["options"]:
        for opt in shape_info["options"]:
            out.append(f"  - ~{opt['type_str']}")
        if shape_info["default"]:
            out.append(f"  default: {shape_info['default']}")
        out.append("")

    # Internal / suffix comments
    for doc in comments["internal"]:
        out.append(f"  // {doc['content']}")
    if comments["internal"]:
        out.append("")

    if comments["suffix"]:
        out.append(f"  // {comments['suffix']['content']}")
        out.append("")

    # Referenced shapes -- compact single-line header + fields, no sub-subheadings
    if referenced_shapes:
        out.append("## Referenced Shapes")
        out.append("")
        for ref_name, ref in referenced_shapes.items():
            ref_info = ref["shape_info"]
            ref_pos = ref.get("pos") or (0, 0, 0, 0)
            ref_label = (
                "struct" if ref_info["kind"] == "struct"
                else "union" if ref_info["kind"] == "union"
                else "shape"
            )

            # Preceding comment for the referenced shape (first line only, as a note)
            ref_preceding = ref["comments"]["preceding"]
            comment_note = ""
            if ref_preceding:
                first_line = ref_preceding[-1]["content"].split("\n")[0][:60]
                comment_note = f"  // {first_line}"

            # Summary line for this ref
            ref_summary_parts = [f"`{ref_name}`", f"!shape {ref_label}"]
            if ref_pos[0]:
                ref_end = ref_pos[2]
                ref_summary_parts.append(
                    f"line {ref_pos[0]}" if ref_pos[0] == ref_end
                    else f"lines {ref_pos[0]}\u2013{ref_end}"
                )
            ref_summary_parts.append(ref_info.get("display", ref_info["raw"]))
            out.append(" \u00b7 ".join(ref_summary_parts))
            if comment_note:
                out.append(comment_note)

            rskind = ref_info["kind"]
            if rskind == "struct" and ref_info["fields"]:
                for f in ref_info["fields"]:
                    parts = [f"  - {f['name']}"]
                    type_part = f"~{f['type_str']}"
                    if f["modifiers"]:
                        type_part += f["modifiers"]
                    parts.append(type_part)
                    if f["default"]:
                        parts.append(f"= {f['default']}")
                    line = "  ".join(parts)
                    if f.get("comment"):
                        line += f"  // {f['comment']}"
                    out.append(line)
            elif rskind == "union" and ref_info["options"]:
                for opt in ref_info["options"]:
                    out.append(f"  - ~{opt['type_str']}")
                if ref_info["default"]:
                    out.append(f"  default: {ref_info['default']}")
            out.append("")

    return "\n".join(out)
