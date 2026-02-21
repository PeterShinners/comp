"""COP tree optimization and constant folding.

This module handles compile-time evaluation of COP trees:
- Literal conversion: text/number nodes to value.constant
- Identifier resolution: value.identifier to value.local or value.namespace
- Constant folding: Evaluate operators and structs at compile time

After coptimize runs, every value.identifier in the original tree has been
resolved to one of:
  value.local     -- a name bound by op.let or a block parameter
  value.namespace -- a name found in the module/system namespace
  value.identifier -- unresolved (namespace was None, or name not found)

The last case is intentionally left as value.identifier so that a separate
validation pass can report it cleanly without mixing concerns into the
optimization walk.
"""

__all__ = [
    "coptimize",
]

import decimal
import comp


def coptimize(cop, fold, namespace, references=None, locals_defined=None):
    """Optimize a COP tree with optional folding and identifier resolution.

    Always converts literal nodes (value.text, value.number) to value.constant.

    If namespace is provided, resolves identifiers:
      - Names in the local scope (op.let bindings, block params) become value.local
      - Names found in the namespace become value.namespace
      - Unresolved names remain as value.identifier

    If fold is True, evaluates constant expressions at compile time:
    - Unary/binary math on constants
    - Struct literals with all constant fields
    - References to definitions with constant values

    Args:
        cop: (Value) COP tree to optimize
        fold: (bool) Whether to fold constant expressions
        namespace: (dict | None) Namespace for identifier resolution
        references: (set | None) If provided, collects qualified names of all
            resolved namespace references discovered during optimization
        locals_defined: (set | None) If provided, collects names of all local
            variables defined by op.let statements in the tree

    Returns:
        (Value) Optimized COP tree
    """
    if references is None:
        references = set()
    return _coptimize_walk(cop, fold, namespace, set(), references, locals_defined)


def _coptimize_walk(cop, fold, namespace, locals, references, locals_defined=None):
    """Internal recursive optimizer with local variable tracking.

    Args:
        cop: (Value) COP node to optimize
        fold: (bool) Whether to fold constants
        namespace: (dict | None) Namespace for lookups
        locals: (set) Local variable names to resolve as value.local
        references: (set) Collects discovered namespace reference names
        locals_defined: (set | None) Collects names defined by op.let

    Returns:
        (Value) Optimized COP node
    """
    if cop is None:
        return cop

    tag = comp.cop_tag(cop)

    # --- Literals: always convert to constants ---
    if tag == "value.text":
        literal = cop.to_python("value")
        return _make_constant(cop, comp.Value.from_python(literal))

    if tag == "value.number":
        literal = cop.to_python("value")
        value = decimal.Decimal(literal)
        return _make_constant(cop, comp.Value.from_python(value))

    # --- Identifiers: resolve to value.local, value.namespace, or leave as-is ---
    if tag == "value.identifier":
        ref = _resolve_identifier(cop, namespace, locals, references)
        if ref is cop:
            return cop  # Unresolved — leave as value.identifier
        # If we created a namespace reference, try to fold it
        ref_tag = comp.cop_tag(ref)
        if fold and namespace is not None:
            if ref_tag == "value.namespace":
                return _fold_namespace(ref, namespace)
            if ref_tag == "value.field":
                # Recursively optimize the field access (which may fold)
                return _coptimize_walk(ref, fold, namespace, locals, references, locals_defined)
        return ref

    # --- Already-resolved references: record and optionally fold ---
    if tag in ("value.reference", "value.namespace"):
        _record_reference(cop, references)
        if fold and namespace is not None:
            return _fold_namespace(cop, namespace)
        return cop

    # --- Blocks: track parameter names as locals ---
    if tag == "value.block":
        return _optimize_block(cop, fold, namespace, locals, references, locals_defined)

    # --- Sequential statements: track op.let bindings across statements ---
    if tag == "statement.define":
        return _optimize_sequential(cop, fold, namespace, locals, references, locals_defined)

    # --- Named fields: only optimize value, not name ---
    if tag in ("mod.namefield", "struct.namefield"):
        return _optimize_namefield(cop, fold, namespace, locals, references, locals_defined)

    # --- Recursively optimize children ---
    kids = comp.cop_kids(cop)
    new_kids = []
    changed = False
    for kid in kids:
        new_kid = _coptimize_walk(kid, fold, namespace, locals, references, locals_defined)
        new_kids.append(new_kid)
        if new_kid is not kid:
            changed = True

    # --- Folding: evaluate constant expressions ---
    if fold:
        if tag == "value.math.unary":
            op = cop.to_python("op")
            if op == "+":
                return new_kids[0]
            operand = _get_constant(new_kids[0])
            if operand is not None:
                result = comp.math_unary(op, operand)
                return _make_constant(cop, result)

        if tag == "value.math.binary":
            op = cop.to_python("op")
            left = _get_constant(new_kids[0])
            right = _get_constant(new_kids[1])
            if left is not None and right is not None:
                result = comp.math_binary(op, left, right)
                return _make_constant(cop, result)

        if tag == "value.logic.unary":
            op = cop.to_python("op")
            operand = _get_constant(new_kids[0])
            if operand is not None:
                result = comp.logic_unary(op, operand)
                return _make_constant(cop, result)

        if tag == "value.logic.binary":
            op = cop.to_python("op")
            left = _get_constant(new_kids[0])
            right = _get_constant(new_kids[1])
            if left is not None and right is not None:
                result = comp.logic_binary(op, left, right)
                return _make_constant(cop, result)

        if tag == "value.compare":
            op = cop.to_python("op")
            left = _get_constant(new_kids[0])
            right = _get_constant(new_kids[1])
            if left is not None and right is not None:
                result = comp.compare(op, left, right)
                return _make_constant(cop, result)

        if tag == "value.field":
            # Field access: struct.field or struct.#N
            # kids[0] is the struct, kids[1] is the identifier with field accessor(s)
            struct_val = _get_constant(new_kids[0])
            if struct_val is not None and struct_val.shape is comp.shape_struct:
                # Extract fields from identifier
                field_cop = new_kids[1]
                field_tag = comp.cop_tag(field_cop)

                # Handle single field vs identifier with multiple fields
                if field_tag == "value.identifier":
                    field_kids = comp.cop_kids(field_cop)
                else:
                    # Single field (ident.token, ident.index, etc.)
                    field_kids = [field_cop]

                # Chain field accesses
                result = struct_val
                for field_token in field_kids:
                    field_tag = comp.cop_tag(field_token)

                    if field_tag == "ident.token":
                        # Named field access
                        field_name = field_token.to_python("value")
                        field_key = comp.Value.from_python(field_name)
                        field_val = result.data.get(field_key)
                        if field_val is None:
                            break  # Field not found, can't fold
                        result = field_val
                    elif field_tag == "ident.index":
                        # Positional field access (0-based)
                        index_str = field_token.to_python("value")
                        index = int(index_str)
                        items = list(result.data.items())
                        if index < 0 or index >= len(items):
                            break  # Index out of range, can't fold
                        _, result = items[index]
                    else:
                        break  # Unsupported field type, can't fold
                else:
                    # Successfully extracted all fields
                    return _make_constant(cop, result)

        if tag == "struct.define":
            return _fold_struct(cop, new_kids)

        if tag == "op.on":
            cond_val = _get_constant(new_kids[0])
            if cond_val is not None:
                for branch_cop in new_kids[1:]:
                    result_cop = _try_fold_on_branch(cond_val, branch_cop)
                    if result_cop is not None:
                        return result_cop

    if changed:
        return comp.cop_rebuild(cop, new_kids)
    return cop


def _optimize_sequential(cop, fold, namespace, locals, references, locals_defined):
    """Optimize a statement.define, tracking op.let bindings across statements.

    Each statement.field is processed in order. After a field containing an
    op.let, the bound name is added to the active locals set so that subsequent
    statements in the same sequence resolve that identifier as value.local.

    Args:
        cop: (Value) statement.define COP node
        fold: (bool) Whether to fold
        namespace: (dict | None) Namespace
        locals: (set) Inherited locals from outer scope
        references: (set) Collects discovered namespace reference names
        locals_defined: (set | None) Collects names defined by op.let

    Returns:
        (Value) Optimized statement.define node
    """
    kids = comp.cop_kids(cop)
    current_locals = locals.copy()
    new_kids = []
    changed = False

    for kid in kids:
        new_kid = _coptimize_walk(kid, fold, namespace, current_locals, references, locals_defined)
        new_kids.append(new_kid)
        if new_kid is not kid:
            changed = True

        # After processing, check if this statement binds a new local name
        let_name = _extract_let_name(new_kid)
        if let_name:
            current_locals.add(let_name)
            if locals_defined is not None:
                locals_defined.add(let_name)

    # Apply statement.define constant folding
    if fold:
        if len(new_kids) == 1 and comp.cop_tag(new_kids[0]) == "statement.field":
            field_kids = list(comp.cop_kids(new_kids[0]))
            if len(field_kids) == 1:
                const = _get_constant(field_kids[0])
                if const is not None:
                    return _make_constant(cop, const)

    if changed:
        return comp.cop_rebuild(cop, new_kids)
    return cop


def _extract_let_name(cop):
    """Extract the bound variable name from an op.let node, possibly inside statement.field.

    Args:
        cop: (Value) COP node (op.let or statement.field wrapping one)

    Returns:
        (str | None) The bound name, or None if not an op.let
    """
    tag = comp.cop_tag(cop)
    if tag == "statement.field":
        kids = comp.cop_kids(cop)
        if kids:
            return _extract_let_name(kids[0])
        return None
    if tag in ("op.let", "op.ctx"):
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


def _resolve_identifier(cop, namespace, locals, references):
    """Convert value.identifier to value.local, value.namespace, or leave unchanged.

    Resolution order:
    1. If the first name part is in `locals`, create a value.local node.
       Remaining parts (field access) are kept as kids on the local node.
    2. If the full (or prefix) name is in the namespace, create a value.namespace
       node and record the qualified name in `references`.
    3. Otherwise return cop unchanged (stays as value.identifier).

    For namespace lookup, progressively shorter prefixes are tried so that
    "pair.b" resolves to a value.namespace for "pair" plus a field access on "b".

    Args:
        cop: (Value) Identifier COP node
        namespace: (dict | None) Namespace for lookups
        locals: (set) Local names that resolve to value.local
        references: (set | None) Collects discovered namespace reference names

    Returns:
        (Value) value.local, value.namespace, value.field, or original cop
    """
    # Extract name parts from identifier
    # Only ident.token and ident.text can be part of namespace resolution
    # Other field types (ident.index, ident.indexpr, ident.expr) must become access
    kids = comp.cop_kids(cop)

    # Separate resolvable prefix from non-resolvable suffix
    resolvable_parts = []  # (name_string, kid_cop) tuples
    first_non_resolvable_idx = None

    for i, kid in enumerate(kids):
        kid_tag = comp.cop_tag(kid)
        if kid_tag in ("ident.token", "ident.text"):
            try:
                name = kid.field("value").data
                resolvable_parts.append((name, kid))
            except (KeyError, AttributeError):
                first_non_resolvable_idx = i
                break
        else:
            # Hit a non-resolvable field type (index, indexpr, expr)
            first_non_resolvable_idx = i
            break

    if not resolvable_parts:
        return cop

    # Check if first name part is a local variable
    first_name = resolvable_parts[0][0]
    if first_name in locals:
        # Remaining kids become field access on the local
        remaining = [p[1] for p in resolvable_parts[1:]]
        if first_non_resolvable_idx is not None:
            remaining.extend(kids[first_non_resolvable_idx:])
        return _make_local(cop, first_name, remaining)

    # Skip namespace resolution if no namespace provided
    if namespace is None:
        return cop

    # Try full resolvable name first, then progressively shorter prefixes
    for prefix_len in range(len(resolvable_parts), 0, -1):
        name = ".".join(p[0] for p in resolvable_parts[:prefix_len])

        definition_set = namespace.get(name)
        if definition_set is None:
            continue

        # Found a match - create namespace reference
        scalar = definition_set.scalar()
        invokables = definition_set.invokables() if scalar is None else None

        if scalar is not None:
            ref = _make_namespace(cop, scalar.qualified, scalar.module_id)
            _record_reference(ref, references)
        elif invokables is not None and len(invokables) > 0:
            qualified_names = [d.qualified for d in invokables]
            module_id = invokables[0].module_id
            ref = _make_namespace(cop, qualified_names, module_id)
            _record_reference(ref, references)
        else:
            continue  # Ambiguous, try shorter prefix

        # Collect remaining kids that need to become field access
        remaining_kids = [p[1] for p in resolvable_parts[prefix_len:]]
        if first_non_resolvable_idx is not None:
            remaining_kids.extend(kids[first_non_resolvable_idx:])

        # If there are remaining parts, wrap in access node
        if remaining_kids:
            field_ident = comp.create_cop("value.identifier", remaining_kids)
            return comp.create_cop("value.field", [ref, field_ident])

        return ref

    # Nothing resolved — leave as value.identifier
    return cop


def _record_reference(cop, references):
    """Record reference qualified name(s) in the references set.

    Args:
        cop: (Value) value.reference or value.namespace COP node
        references: (set) Set to add to
    """
    try:
        qualified = cop.field("qualified").data
        if isinstance(qualified, list):
            references.update(qualified)
        elif isinstance(qualified, str):
            references.add(qualified)
    except (KeyError, AttributeError):
        pass


def _fold_namespace(cop, namespace):
    """Fold a namespace reference to its constant value if available.

    Works for both value.reference (legacy) and value.namespace nodes.
    Only folds true constant values (numbers, strings, tags, shapes).
    Does NOT fold callable values (Block, InternalCallable) since those
    need to remain as references for proper invocation.

    Args:
        cop: (Value) Reference/namespace COP node
        namespace: (dict) Namespace for lookups

    Returns:
        (Value) Constant node or original reference
    """
    try:
        qualified_val = cop.field("qualified")
        # Skip overloaded references (list of names)
        if isinstance(qualified_val.data, (dict, list)):
            return cop
        qualified = qualified_val.data
        definition_set = namespace.get(qualified)
        if definition_set is not None:
            defn = definition_set.scalar()
            if defn is not None:
                if defn.value is not None:
                    # Only fold non-callable constant values
                    val_data = defn.value.data
                    if isinstance(val_data, (comp.Block, comp.InternalCallable)):
                        return cop
                    return _make_constant(cop, defn.value)
    except (KeyError, AttributeError):
        pass
    return cop


def _optimize_block(cop, fold, namespace, locals, references, locals_defined=None):
    """Optimize a block, extracting parameter names as locals for the body.

    Args:
        cop: (Value) Block COP node (value.block)
        fold: (bool) Whether to fold
        namespace: (dict | None) Namespace
        locals: (set) Inherited locals from outer scope
        references: (set | None) Collects discovered namespace reference names
        locals_defined: (set | None) Collects all locally-defined names

    Returns:
        (Value) Optimized block
    """
    kids = comp.cop_kids(cop)
    if len(kids) < 2:
        return cop

    signature_cop = kids[0]
    body_cop = kids[1]

    # Build a fresh locals set for the block body, inherited from outer scope
    block_locals = locals.copy()

    # Extract parameter names from the block signature (block.signature node)
    # Its children are signature.param and signature.block nodes, each with a
    # `name` attribute holding the parameter name string.
    sig_tag = comp.cop_tag(signature_cop)
    if sig_tag == "block.signature":
        for field_cop in comp.cop_kids(signature_cop):
            field_tag = comp.cop_tag(field_cop)
            if field_tag in ("signature.param", "signature.block"):
                try:
                    param_name = field_cop.to_python("name")
                    if param_name:
                        block_locals.add(param_name)
                        if locals_defined is not None:
                            locals_defined.add(param_name)
                except (KeyError, AttributeError):
                    pass

    # Ensure the conventional parameter names are always available as locals
    # even when the signature uses positional forms without explicit names.
    block_locals.add("input")
    block_locals.add("args")
    block_locals.add("$")
    block_locals.add("$$")
    block_locals.add("$$$")

    new_body = _coptimize_walk(body_cop, fold, namespace, block_locals, references, locals_defined)

    if new_body is body_cop:
        return cop

    return comp.cop_rebuild(cop, [signature_cop, new_body])


def _optimize_namefield(cop, fold, namespace, locals, references, locals_defined=None):
    """Optimize a namefield, only processing the value child.

    Args:
        cop: (Value) Namefield COP node
        fold: (bool) Whether to fold
        namespace: (dict | None) Namespace
        locals: (set) Current locals
        references: (set | None) Collects discovered namespace reference names
        locals_defined: (set | None) Collects all locally-defined names

    Returns:
        (Value) Optimized namefield
    """
    kids = comp.cop_kids(cop)
    if len(kids) < 2:
        return cop

    name_cop = kids[0]
    value_cop = kids[1]

    new_value = _coptimize_walk(value_cop, fold, namespace, locals, references, locals_defined)

    if new_value is value_cop:
        return cop

    return comp.cop_rebuild(cop, [name_cop, new_value])


def _fold_struct(cop, kids):
    """Fold a struct literal if all fields are constants.

    Args:
        cop: (Value) Struct COP node
        kids: (list) Already-optimized children

    Returns:
        (Value) Constant node if all fields are constants, otherwise rebuilt node
    """
    struct = {}
    for field_cop in kids:
        field_tag = comp.cop_tag(field_cop)
        field_kids = comp.cop_kids(field_cop)

        if field_tag == "struct.posfield":
            key = comp.Unnamed()
            value = _get_constant(field_kids[0]) if field_kids else None
        elif field_tag == "struct.namefield":
            if len(field_kids) < 2:
                return comp.cop_rebuild(cop, kids)
            key_cop = field_kids[0]
            value_cop = field_kids[1]
            # Extract name from identifier
            key = None
            if comp.cop_tag(key_cop) == "value.identifier":
                ident_kids = comp.cop_kids(key_cop)
                if len(ident_kids) == 1 and comp.cop_tag(ident_kids[0]) == "ident.token":
                    try:
                        key = ident_kids[0].field("value").data
                    except (KeyError, AttributeError):
                        pass
            value = _get_constant(value_cop)
        else:
            return comp.cop_rebuild(cop, kids)

        if key is None or value is None:
            return comp.cop_rebuild(cop, kids)
        struct[key] = value

    return _make_constant(cop, comp.Value.from_python(struct))


def _make_constant(original, value):
    """Create a value.constant COP node preserving position info.

    Args:
        original: (Value) Original COP node for position
        value: (Value) Constant value

    Returns:
        (Value) Constant COP node
    """
    fields = {"value": value}
    if original:
        try:
            pos = original.field("pos")
            if pos is not None:
                fields["pos"] = pos
        except (KeyError, AttributeError):
            pass
    return comp.create_cop("value.constant", [], **fields)


def _make_local(original, name, remaining_kids):
    """Create a value.local COP node for a resolved local variable reference.

    Args:
        original: (Value) Original identifier COP node for position
        name: (str) Local variable name
        remaining_kids: (list) Additional ident.token etc. nodes for field access

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
    """Create a value.namespace COP node for a resolved namespace reference.

    Args:
        original: (Value) Original COP node for position
        qualified: (str | list) Qualified name(s) of the definition(s)
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


def _make_reference(original, qualified, module_id):
    """Create a value.reference COP node (legacy — used by cop_resolve).

    Prefer _make_namespace for new code; this exists for backward compatibility
    with cop_resolve in _cop.py.

    Args:
        original: (Value) Original COP node for position
        qualified: (str | list) Qualified name(s)
        module_id: (str) Module identifier

    Returns:
        (Value) value.reference COP node
    """
    fields = {"qualified": qualified, "module_id": module_id}
    if original:
        try:
            pos = original.field("pos")
            if pos is not None:
                fields["pos"] = pos
        except (KeyError, AttributeError):
            pass
    return comp.create_cop("value.reference", [], **fields)


def _try_fold_on_branch(cond_val, branch_cop):
    """Try to constant-fold one op.on branch against a known condition value.

    Works when the branch pattern is a simple shape.define wrapping a single
    constant Tag or Shape (e.g. ~true, ~false, ~text) that has already been
    folded by _fold_namespace.

    Args:
        cond_val: (Value) The constant condition value
        branch_cop: (Value) The op.on.branch COP node (already walked)

    Returns:
        (Value | None) The result COP node if the branch matches, else None
    """
    branch_kids = comp.cop_kids(branch_cop)
    if len(branch_kids) < 2:
        return None
    pattern_cop, result_cop = branch_kids[0], branch_kids[1]

    # Only handle shape.define patterns
    if comp.cop_tag(pattern_cop) != "shape.define":
        return None
    shape_kids = comp.cop_kids(pattern_cop)
    if len(shape_kids) != 1:
        return None  # Structural shape with multiple fields — skip

    inner_val = _get_constant(shape_kids[0])
    if inner_val is None:
        return None  # Pattern not folded to a constant — can't fold at compile time

    pattern_data = inner_val.data
    if not isinstance(pattern_data, (comp.Tag, comp.Shape, comp.ShapeUnion)):
        return None

    # morph() works with frame=None for Tag and primitive Shape patterns
    # (frame is only used for struct default values, which aren't involved here)
    try:
        morph_result = comp._morph.morph(cond_val, pattern_data, None)
        if not morph_result.failure_reason:
            return result_cop
    except (AttributeError, TypeError):
        pass

    return None


def _get_constant(cop):
    """Extract constant value from a value.constant COP node.

    Args:
        cop: (Value) COP node

    Returns:
        (Value | None) Constant value or None
    """
    if comp.cop_tag(cop) == "value.constant":
        try:
            return cop.field("value")
        except (KeyError, AttributeError):
            pass
    return None
