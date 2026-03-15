"""COP name resolution — converts identifiers to resolved references.

This module is responsible for a single pass: resolving every value.identifier
in a COP tree to one of:

    value.local     — a name bound by op.my, op.ctx, or a block parameter
    value.namespace — a name found in the module/system namespace
    value.undefined — an unresolved name (grenade that explodes at codegen)

After cop_resolve_names() returns, NO value.identifier nodes remain.

This pass is independent of constant folding and optimization. It requires
only a namespace dict and produces a new COP tree with all names resolved.
"""

__all__ = [
    "cop_resolve_names",
]

import comp


def cop_resolve_names(cop, namespace):
    """Resolve all identifiers in a COP tree.

    Walks the tree and converts every value.identifier to value.local,
    value.namespace, or value.undefined.  No value.identifier nodes
    survive this pass.

    This function is safe to call on any COP tree — it does not require
    the tree to have been produced by a module import.  External code
    that builds its own COP nodes can call this to prepare them for
    codegen.

    Args:
        cop: (Value) COP tree to resolve
        namespace: (dict) Namespace dict {name: Callable}

    Returns:
        (Value) Resolved COP tree (same object when nothing changed)
    """
    if cop is None:
        return cop
    return _resolve_walk(cop, namespace, set())


def _resolve_walk(cop, namespace, locals):
    """Recursive resolution walk with local variable tracking.

    Args:
        cop: (Value) COP node to resolve
        namespace: (dict) Namespace for lookups
        locals: (set) Local variable names that resolve to value.local

    Returns:
        (Value) Resolved COP node
    """
    if cop is None:
        return cop

    tag = comp.cop_tag(cop)

    # --- Identifiers: the main target of this pass ---
    if tag == "value.identifier":
        return _resolve_identifier(cop, namespace, locals)

    # --- Already-resolved references pass through ---
    if tag in ("value.namespace", "value.reference",
               "value.constant", "value.undefined"):
        return cop

    # --- Blocks: track parameter names as locals ---
    if tag == "value.block":
        return _resolve_block(cop, namespace, locals)

    # --- Function definitions: body has implicit $ access ---
    if tag == "function.define":
        return _resolve_function(cop, namespace, locals)

    # --- Sequential containers: track op.my / named-field bindings ---
    if tag in ("statement.define", "struct.define"):
        return _resolve_sequential(cop, namespace, locals)

    # --- Named fields: only resolve value, not name ---
    if tag in ("mod.namefield", "struct.namefield"):
        return _resolve_namefield(cop, namespace, locals)

    # --- Let/ctx bindings: name child is declaration, not reference ---
    if tag in ("op.my", "op.ctx"):
        kids = comp.cop_kids(cop)
        if len(kids) >= 2:
            new_value = _resolve_walk(kids[1], namespace, locals)
            if new_value is not kids[1]:
                return comp.cop_rebuild(cop, [kids[0], new_value])
        return cop

    # --- Bindings: binding values are implicit block scopes with $ access ---
    if tag == "value.binding":
        return _resolve_binding(cop, namespace, locals)

    # --- Recursively resolve children ---
    kids = comp.cop_kids(cop)
    new_kids = []
    changed = False
    for kid in kids:
        new_kid = _resolve_walk(kid, namespace, locals)
        new_kids.append(new_kid)
        if new_kid is not kid:
            changed = True

    if changed:
        return comp.cop_rebuild(cop, new_kids)
    return cop


def _resolve_identifier(cop, namespace, locals):
    """Convert value.identifier to value.local, value.namespace, or value.undefined.

    Resolution order:
    1. If the first name part is in locals → value.local
    2. If the name (or prefix) is in the namespace → value.namespace
    3. Otherwise → value.undefined (grenade)

    Args:
        cop: (Value) Identifier COP node
        namespace: (dict) Namespace for lookups
        locals: (set) Local names

    Returns:
        (Value) Resolved node (never value.identifier)
    """
    kids = comp.cop_kids(cop)

    # Separate resolvable prefix from non-resolvable suffix
    resolvable_parts = []
    first_non_resolvable_idx = None

    for i, kid in enumerate(kids):
        kid_tag = comp.cop_tag(kid)
        if kid_tag in ("ident.token", "ident.text", "ident.input"):
            try:
                name = kid.field("value").data
                resolvable_parts.append((name, kid))
            except (KeyError, AttributeError):
                first_non_resolvable_idx = i
                break
        else:
            first_non_resolvable_idx = i
            break

    if not resolvable_parts:
        # No resolvable parts at all — leave as undefined
        return _make_undefined(cop, "?")

    # Check if first name part is a local variable
    first_name = resolvable_parts[0][0]
    if first_name in locals:
        remaining = [p[1] for p in resolvable_parts[1:]]
        if first_non_resolvable_idx is not None:
            remaining.extend(kids[first_non_resolvable_idx:])
        # Resolve expressions inside remaining kids (e.g. ident.indexpr)
        remaining = [_resolve_walk(k, namespace, locals) for k in remaining]
        return _make_local(cop, first_name, remaining)

    # Try namespace resolution (full name first, then shorter prefixes)
    if namespace is not None:
        for prefix_len in range(len(resolvable_parts), 0, -1):
            name = ".".join(p[0] for p in resolvable_parts[:prefix_len])

            definition_set = namespace.get(name)
            if definition_set is None:
                continue

            scalar = definition_set.scalar()
            invokables = definition_set.invokables() if scalar is None else None

            if scalar is not None:
                ref = _make_namespace(cop, scalar.qualified, scalar.module_id)
            elif invokables is not None and len(invokables) > 0:
                qualified_names = [d.qualified for d in invokables]
                module_id = invokables[0].module_id
                ref = _make_namespace(cop, qualified_names, module_id)
            elif hasattr(definition_set, "entries") and definition_set.entries:
                # Non-invokable, non-scalar set (e.g. tag with alias).
                # Pick the shortest qualified name as the canonical reference.
                defs_list = sorted(definition_set.entries,
                                   key=lambda d: len(d.qualified))
                ref = _make_namespace(cop, defs_list[0].qualified,
                                      defs_list[0].module_id)
            else:
                continue

            # Collect remaining kids that become field access
            remaining_kids = [p[1] for p in resolvable_parts[prefix_len:]]
            if first_non_resolvable_idx is not None:
                remaining_kids.extend(kids[first_non_resolvable_idx:])

            if remaining_kids:
                # Resolve expressions inside remaining kids (e.g. ident.indexpr)
                remaining_kids = [_resolve_walk(k, namespace, locals) for k in remaining_kids]
                field_ident = comp.create_cop("value.identifier", remaining_kids)
                return comp.create_cop("value.field", [ref, field_ident])

            return ref

    # Nothing resolved — create undefined grenade
    full_name = ".".join(p[0] for p in resolvable_parts)
    return _make_undefined(cop, full_name)


def _resolve_block(cop, namespace, locals):
    """Resolve a block, extracting parameter names as locals for the body.

    Args:
        cop: (Value) Block COP node (value.block)
        namespace: (dict) Namespace
        locals: (set) Inherited locals from outer scope

    Returns:
        (Value) Resolved block
    """
    kids = comp.cop_kids(cop)
    if len(kids) < 2:
        return cop

    signature_cop = kids[0]
    body_cop = kids[1]

    block_locals = locals.copy()

    sig_tag = comp.cop_tag(signature_cop)
    if sig_tag == "block.signature":
        for field_cop in comp.cop_kids(signature_cop):
            field_tag = comp.cop_tag(field_cop)
            if field_tag in ("signature.param",):
                try:
                    param_name = field_cop.to_python("name")
                    if param_name:
                        block_locals.add(param_name)
                except (KeyError, AttributeError):
                    pass

    # Conventional parameter names always available
    block_locals.update({"input", "args", "$", "$$", "$$$"})

    new_body = _resolve_walk(body_cop, namespace, block_locals)

    if new_body is body_cop:
        return cop

    return comp.cop_rebuild(cop, [signature_cop, new_body])


def _resolve_function(cop, namespace, locals):
    """Resolve a function.define, adding $ references to the body scope.

    Function bodies receive piped input at runtime, so $ / $$ / $$$
    must be in scope for the body even though there is no explicit
    block.signature declaring them.

    Args:
        cop: (Value) function.define COP node
        namespace: (dict) Namespace
        locals: (set) Inherited locals

    Returns:
        (Value) Resolved function node
    """
    kids = comp.cop_kids(cop)

    func_locals = locals.copy()
    func_locals.update({"input", "args", "$", "$$", "$$$"})

    new_kids = []
    changed = False
    for kid in kids:
        new_kid = _resolve_walk(kid, namespace, func_locals)
        new_kids.append(new_kid)
        if new_kid is not kid:
            changed = True

    if changed:
        return comp.cop_rebuild(cop, new_kids)
    return cop


def _resolve_sequential(cop, namespace, locals):
    """Resolve a sequential container, tracking bindings across children.

    Handles both statement.define (parenthesized blocks) and struct.define
    (brace blocks).  After each child is resolved, any name it binds
    (via op.my, op.ctx, or struct.namefield) is added to the locals set
    so subsequent siblings can see it.

    Args:
        cop: (Value) statement.define or struct.define COP node
        namespace: (dict) Namespace
        locals: (set) Inherited locals

    Returns:
        (Value) Resolved node
    """
    kids = comp.cop_kids(cop)
    current_locals = locals.copy()
    new_kids = []
    changed = False

    # If the first child is a block.signature, resolve it with the OUTER
    # locals (before param names are added) so that default expressions
    # see the enclosing scope, not the parameters being declared.
    if kids and comp.cop_tag(kids[0]) == "block.signature":
        sig_cop = kids[0]
        new_sig = _resolve_walk(sig_cop, namespace, current_locals)
        new_kids.append(new_sig)
        if new_sig is not sig_cop:
            changed = True
        for field_cop in comp.cop_kids(sig_cop):
            field_tag = comp.cop_tag(field_cop)
            if field_tag in ("signature.param",):
                try:
                    param_name = field_cop.to_python("name")
                    if param_name:
                        current_locals.add(param_name)
                except (KeyError, AttributeError):
                    pass
        current_locals.update({"input", "args", "$", "$$", "$$$"})

    for kid in kids:
        # Skip the signature — already resolved above
        if new_kids and kid is kids[0] and comp.cop_tag(kid) == "block.signature":
            continue
        new_kid = _resolve_walk(kid, namespace, current_locals)
        new_kids.append(new_kid)
        if new_kid is not kid:
            changed = True

        let_name = _extract_let_name(new_kid)
        if let_name:
            current_locals.add(let_name)

    if changed:
        return comp.cop_rebuild(cop, new_kids)
    return cop


def _resolve_namefield(cop, namespace, locals):
    """Resolve a namefield, only processing the value child.

    Args:
        cop: (Value) Namefield COP node
        namespace: (dict) Namespace
        locals: (set) Current locals

    Returns:
        (Value) Resolved namefield
    """
    kids = comp.cop_kids(cop)
    if len(kids) < 2:
        return cop

    name_cop = kids[0]
    value_cop = kids[1]

    new_value = _resolve_walk(value_cop, namespace, locals)

    if new_value is value_cop:
        return cop

    return comp.cop_rebuild(cop, [name_cop, new_value])


def _resolve_binding(cop, namespace, locals):
    """Resolve a value.binding node.

    The callable (first child) is resolved with the current locals.
    The bindings struct (second child) is resolved with $ references
    added to locals, because binding values are implicit block scopes
    that receive the piped input value at runtime.

    Args:
        cop: (Value) value.binding COP node
        namespace: (dict) Namespace
        locals: (set) Current locals

    Returns:
        (Value) Resolved binding node
    """
    kids = comp.cop_kids(cop)
    if len(kids) < 2:
        return _resolve_walk(cop, namespace, locals) if kids else cop

    callable_cop = kids[0]
    bindings_cop = kids[1]

    new_callable = _resolve_walk(callable_cop, namespace, locals)

    binding_locals = locals.copy()
    binding_locals.update({"input", "args", "$", "$$", "$$$"})
    new_bindings = _resolve_walk(bindings_cop, namespace, binding_locals)

    if new_callable is callable_cop and new_bindings is bindings_cop:
        return cop

    return comp.cop_rebuild(cop, [new_callable, new_bindings])


def _extract_let_name(cop):
    """Extract the bound variable name from a binding node.

    Only op.my and op.ctx create local variable bindings.
    struct.namefield contributes to the outgoing structure but does NOT
    create a local visible to subsequent siblings.

    Args:
        cop: (Value) COP node that may bind a name

    Returns:
        (str | None) The bound name, or None
    """
    tag = comp.cop_tag(cop)
    if tag == "statement.field":
        kids = comp.cop_kids(cop)
        if kids:
            return _extract_let_name(kids[0])
        return None
    if tag in ("op.my", "op.ctx"):
        kids = comp.cop_kids(cop)
        if kids:
            return _get_ident_name(kids[0])
    return None


def _get_ident_name(cop):
    """Get the string name from an ident.token or value.identifier COP node.

    Args:
        cop: (Value) COP node

    Returns:
        (str | None) The identifier name string, or None
    """
    tag = comp.cop_tag(cop)
    if tag == "ident.token":
        try:
            return cop.field("value").data
        except (KeyError, AttributeError):
            return None
    if tag == "value.identifier":
        kids = comp.cop_kids(cop)
        if kids and comp.cop_tag(kids[0]) == "ident.token":
            try:
                return kids[0].field("value").data
            except (KeyError, AttributeError):
                return None
    return None


def _make_local(original, name, remaining_kids):
    """Create a value.local COP node.

    Args:
        original: (Value) Original COP node for position
        name: (str) Local variable name
        remaining_kids: (list) Additional ident nodes for field access

    Returns:
        (Value) value.local COP node
    """
    fields = {"name": name}
    if original:
        try:
            pos = original.field("pos")
            if pos is not None:
                fields["pos"] = pos
        except (KeyError, AttributeError):
            pass
    return comp.create_cop("value.local", remaining_kids, **fields)


def _make_namespace(original, qualified, module_id):
    """Create a value.namespace COP node.

    Args:
        original: (Value) Original COP node for position
        qualified: (str | list) Qualified name(s)
        module_id: (str) Module identifier

    Returns:
        (Value) value.namespace COP node
    """
    fields = {"qualified": qualified, "module_id": module_id}
    if original:
        try:
            pos = original.field("pos")
            if pos is not None:
                fields["pos"] = pos
        except (KeyError, AttributeError):
            pass
    return comp.create_cop("value.namespace", [], **fields)


def _make_undefined(original, name):
    """Create a value.undefined COP node — grenade that explodes at codegen.

    Args:
        original: (Value) Original COP node for position
        name: (str) The unresolved identifier name

    Returns:
        (Value) value.undefined COP node
    """
    fields = {"name": name}
    if original:
        try:
            pos = original.field("pos")
            if pos is not None:
                fields["pos"] = pos
        except (KeyError, AttributeError):
            pass
    return comp.create_cop("value.undefined", [], **fields)
