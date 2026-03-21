"""Compile module statements into Definitions.

Translates scanned statement dicts into Definition objects by parsing
statement bodies through Lark, converting to COP trees, and running
structural validation.  This module is the comp language's specific
compiler — other languages or formats would provide their own path to
produce Definition objects.

The functions here are pure: they create Definitions without mutating
any Module state.  The caller (Module.definitions) is responsible for
adopting the returned Definitions into the module.
"""

import comp


def compile_definition(stmt, module_id):
    """Compile a single statement into one or more Definitions.

    Parses the statement body, converts to COP, validates structure,
    and returns Definition objects.  Raises on any error.

    Tag statements may produce multiple definitions (parent hierarchy
    and child tags).  All other statement types produce exactly one.

    Args:
        stmt: (dict) Statement dict from the scanner with operator, name,
              body, pos, body_col keys
        module_id: (str) Module token string for the Definition

    Returns:
        (list) List of (qualified_name, Definition) tuples

    Raises:
        comp.ParseError: If the statement body fails to parse
        comp.CodeError: If COP structure validation fails or on duplicate names
    """
    operator = stmt.get("operator")
    if operator in ("func", "pure"):
        return _compile_func(stmt, module_id)
    elif operator == "tag":
        return _compile_tag(stmt, module_id)
    elif operator == "shape":
        return _compile_shape(stmt, module_id)
    elif operator == "startup":
        return _compile_startup(stmt, module_id)
    else:
        raise comp.CodeError(f"Unknown definition operator: {operator}")


def compile_mod_value(stmt):
    """Compile a !mod statement into a (name, cop_value) pair.

    Args:
        stmt: (dict) Statement dict with operator=="mod"

    Returns:
        (tuple) (name, cop_value)
    """
    name = stmt.get("name")
    body = stmt.get("body", "").strip()
    lark_tree = comp.lark_parse(body, "comp", rule="start_mod")
    cop_value = comp._parse.lark_to_cop(lark_tree)
    return name, cop_value


def compile_deferred(stmt):
    """Extract deferred alias/export info from a statement.

    Args:
        stmt: (dict) Statement dict with operator=="alias" or "export"

    Returns:
        (tuple) (kind, name, ref_string, is_private) or None if empty ref
    """
    operator = stmt.get("operator")
    raw_name = stmt.get("name")
    is_private = raw_name.endswith("&")
    name = raw_name[:-1] if is_private else raw_name
    ref = stmt.get("body", "").strip()
    if not ref:
        return None
    return (operator, name, ref, is_private)


# ---------------------------------------------------------------------------
# Statement compilers
# ---------------------------------------------------------------------------

def _parse_stmt_body(stmt, start_rule):
    """Parse a statement body through Lark and convert to COP.

    Args:
        stmt: (dict) Statement dict
        start_rule: (str) Lark grammar entry point

    Returns:
        (Value) COP node
    """
    body = stmt.get("body", "")
    line_offset = stmt.get("pos", [1])[0]
    col_offset = stmt.get("body_col", 0)
    tree = comp.lark_parse(body, "comp", start_rule,
                           line_offset=line_offset, col_offset=col_offset)
    cop = comp.lark_to_cop(tree)
    comp.cop_check_structure(cop)
    return cop


def _split_name(stmt):
    """Extract name and privacy flag from a statement.

    Returns:
        (tuple) (name, is_private)
    """
    raw_name = stmt.get("name")
    is_private = raw_name.endswith("&")
    name = raw_name[:-1] if is_private else raw_name
    return name, is_private


def _compile_func(stmt, module_id):
    """Compile a !func or !pure statement."""
    name, is_private = _split_name(stmt)
    cop = _parse_stmt_body(stmt, "start_func")

    shape = comp.shape_block
    if comp.cop_tag(cop) == "value.wrapper":
        try:
            inner_kids = comp.cop_kids(cop)
            if inner_kids:
                inner_tag = comp.cop_tag(inner_kids[0])
                if inner_tag not in ("function.define", "value.block"):
                    shape = comp.shape_struct
        except (KeyError, AttributeError):
            shape = comp.shape_struct

    definition = comp.Definition(name, module_id, cop, shape, private=is_private)
    if stmt.get("operator") == "pure":
        definition.pure = True

    return [(name, definition)]


def _compile_tag(stmt, module_id):
    """Compile a !tag statement into tag hierarchy definitions.

    Tag definitions produce multiple results: the main tag, any
    hierarchical parents, and child tags declared in the body.
    The Tag objects are created without a module reference — the
    caller must set tag.module after adoption.
    """
    name, is_private = _split_name(stmt)
    cop = _parse_stmt_body(stmt, "start_tag")

    results = []

    # Main tag
    tag = comp.Tag(name, private=False)
    main_def = comp.Definition(name, module_id, original_cop=cop,
                               shape=comp.shape_tag, private=is_private)
    main_def.value = comp.Value.from_python(tag)
    results.append((name, main_def))

    # Hierarchical parents (e.g. "a.b.c" → create "a", "a.b")
    parts = name.split(".")
    for i in range(1, len(parts)):
        parent_name = ".".join(parts[:i])
        parent_tag = comp.Tag(parent_name, private=False)
        parent_def = comp.Definition(parent_name, module_id,
                                     original_cop=None, shape=comp.shape_tag)
        parent_def.value = comp.Value.from_python(parent_tag)
        results.append((parent_name, parent_def))

    # Child tags from the body
    for child_cop in comp.cop_kids(cop):
        child_tag_name = comp.cop_tag(child_cop)
        child_private = is_private
        if child_tag_name == "value.private_tag":
            child_private = True
            inner = comp.cop_kids(child_cop)
            if inner:
                child_cop = inner[0]
                child_tag_name = comp.cop_tag(child_cop)
        if child_tag_name == "value.identifier":
            child_name = _cop_identifier_name(child_cop)
            child_qualified = f"{name}.{child_name}"
            child_tag_obj = comp.Tag(child_qualified, private=False)
            child_def = comp.Definition(child_qualified, module_id,
                                        original_cop=None, shape=comp.shape_tag,
                                        private=child_private)
            child_def.value = comp.Value.from_python(child_tag_obj)
            results.append((child_qualified, child_def))

    return results


def _compile_shape(stmt, module_id):
    """Compile a !shape statement."""
    name, is_private = _split_name(stmt)
    cop = _parse_stmt_body(stmt, "start_shape")
    definition = comp.Definition(name, module_id, cop, comp.shape_shape,
                                 private=is_private)
    return [(name, definition)]


def _compile_startup(stmt, module_id):
    """Compile a !startup statement."""
    name = stmt.get("name")
    cop = _parse_stmt_body(stmt, "start_startup")
    qualified = f"!startup.{name}"
    definition = comp.Definition(qualified, module_id, cop, comp.shape_block,
                                 private=True)
    definition.startup = True
    return [(qualified, definition)]


def _cop_identifier_name(identifier_cop):
    """Extract dotted name from a value.identifier COP node.

    Args:
        identifier_cop: (Value) COP node with tag value.identifier

    Returns:
        (str) Dotted name like "foo" or "server.host"
    """
    parts = []
    for kid in comp.cop_kids(identifier_cop):
        kid_tag = comp.cop_tag(kid)
        if kid_tag in ("ident.token", "ident.text"):
            parts.append(kid.field("value").data)
    return ".".join(parts) if parts else ""
