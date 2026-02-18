"""COP tree optimization and constant folding.

This module handles compile-time evaluation of COP trees:
- Literal conversion: text/number nodes to value.constant
- Identifier resolution: value.identifier to value.reference
- Constant folding: Evaluate operators and structs at compile time
"""

__all__ = [
    "coptimize",
]

import decimal
import comp


def coptimize(cop, fold, namespace, references=None):
    """Optimize a COP tree with optional folding and identifier resolution.

    Always converts literal nodes (value.text, value.number) to value.constant.
    
    If namespace is provided, validates identifiers and converts them to
    value.reference nodes. Unresolved identifiers are left as-is for later
    error reporting.
    
    If fold is True, evaluates constant expressions at compile time:
    - Unary/binary math on constants
    - Struct literals with all constant fields
    - References to definitions with constant values

    Args:
        cop: (Value) COP tree to optimize
        fold: (bool) Whether to fold constant expressions
        namespace: (dict | None) Namespace for identifier resolution
        references: (set | None) If provided, collects qualified names of all
            resolved references discovered during optimization

    Returns:
        (Value) Optimized COP tree
    """
    if references is None:
        references = set()
    return _coptimize_walk(cop, fold, namespace, set(), references)


def _coptimize_walk(cop, fold, namespace, locals, references):
    """Internal recursive optimizer with local variable tracking.

    Args:
        cop: (Value) COP node to optimize
        fold: (bool) Whether to fold constants
        namespace: (dict | None) Namespace for lookups
        locals: (set) Local variable names to skip during resolution
        references: (set) Collects discovered reference names
    
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

    # --- Identifiers: resolve to references if namespace provided ---
    if tag == "value.identifier":
        ref = _resolve_identifier(cop, namespace, locals, references)
        if ref is cop:
            return cop  # No change
        # If we created a reference, try to fold it
        ref_tag = comp.cop_tag(ref)
        if fold and namespace is not None:
            if ref_tag == "value.reference":
                return _fold_reference(ref, namespace)
            if ref_tag == "value.field":
                # Recursively optimize the field access (which may fold)
                return _coptimize_walk(ref, fold, namespace, locals, references)
        return ref

    # --- References: record and optionally fold to constant ---
    if tag == "value.reference":
        _record_reference(cop, references)
        if fold and namespace is not None:
            return _fold_reference(cop, namespace)
        return cop

    # --- Blocks: track parameter names as locals ---
    if tag == "value.block":
        return _optimize_block(cop, fold, namespace, locals, references)

    # --- Named fields: only optimize value, not name ---
    if tag in ("mod.namefield", "struct.namefield"):
        return _optimize_namefield(cop, fold, namespace, locals, references)

    # --- Recursively optimize children ---
    kids = comp.cop_kids(cop)
    new_kids = []
    changed = False
    for kid in kids:
        new_kid = _coptimize_walk(kid, fold, namespace, locals, references)
        new_kids.append(new_kid)
        if new_kid is not kid:
            changed = True

    # --- Folding: evaluate constant expressions ---
    if fold:
        # A paren expression with a single constant field reduces to that constant.
        # This allows (four) to become 4 when four has been substituted inline.
        if tag == "statement.define":
            if len(new_kids) == 1 and comp.cop_tag(new_kids[0]) == "statement.field":
                field_kids = list(comp.cop_kids(new_kids[0]))
                if len(field_kids) == 1:
                    const = _get_constant(field_kids[0])
                    if const is not None:
                        return _make_constant(cop, const)

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

    if changed:
        return comp.cop_rebuild(cop, new_kids)
    return cop


def _resolve_identifier(cop, namespace, locals, references):
    """Convert value.identifier to value.reference if resolvable.

    If the full identifier (e.g., "pair.b") doesn't resolve, tries progressively
    shorter prefixes (e.g., "pair") and wraps in access nodes for remaining parts.

    Args:
        cop: (Value) Identifier COP node
        namespace: (dict | None) Namespace for lookups
        locals: (set) Local names to skip
        references: (set | None) Collects discovered reference names

    Returns:
        (Value) Reference node, access node, or original identifier
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

    # Skip if no namespace
    if namespace is None:
        return cop

    # Skip local variables (check first part only for locals)
    if resolvable_parts[0][0] in locals:
        return cop

    # Try full resolvable name first, then progressively shorter prefixes
    for prefix_len in range(len(resolvable_parts), 0, -1):
        name = ".".join(p[0] for p in resolvable_parts[:prefix_len])
        
        definition_set = namespace.get(name)
        if definition_set is None:
            continue
        
        # Found a match - create reference
        scalar = definition_set.scalar()
        invokables = definition_set.invokables() if scalar is None else None
        
        if scalar is not None:
            ref = _make_reference(cop, scalar.qualified, scalar.module_id)
            _record_reference(ref, references)
        elif invokables is not None and len(invokables) > 0:
            qualified_names = [d.qualified for d in invokables]
            module_id = invokables[0].module_id
            ref = _make_reference(cop, qualified_names, module_id)
            _record_reference(ref, references)
        else:
            continue  # Ambiguous, try shorter prefix
        
        # Collect remaining kids that need to become field access
        # This includes: unmatched resolvable parts + all non-resolvable parts
        remaining_kids = [p[1] for p in resolvable_parts[prefix_len:]]
        if first_non_resolvable_idx is not None:
            remaining_kids.extend(kids[first_non_resolvable_idx:])
        
        # If there are remaining parts, wrap in access node
        if remaining_kids:
            field_ident = comp.create_cop("value.identifier", remaining_kids)
            return comp.create_cop("value.field", [ref, field_ident])
        
        return ref

    # Nothing resolved - leave as identifier
    return cop


def _record_reference(cop, references):
    """Record reference qualified name(s) in the references set.

    Args:
        cop: (Value) Reference COP node
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


def _fold_reference(cop, namespace):
    """Fold a reference to its constant value if available.

    Args:
        cop: (Value) Reference COP node
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
                    return _make_constant(cop, defn.value)
    except (KeyError, AttributeError):
        pass
    return cop


def _optimize_block(cop, fold, namespace, locals, references):
    """Optimize a block, tracking parameter names as locals.

    Args:
        cop: (Value) Block COP node
        fold: (bool) Whether to fold
        namespace: (dict | None) Namespace
        locals: (set) Current locals
        references: (set | None) Collects discovered reference names

    Returns:
        (Value) Optimized block
    """
    kids = comp.cop_kids(cop)
    if len(kids) < 2:
        return cop

    signature_cop = kids[0]
    body_cop = kids[1]

    # Extract parameter names from signature
    block_locals = locals.copy()
    block_locals.add("input")
    block_locals.add("args")
    # TODO: Parse signature for actual param names

    new_body = _coptimize_walk(body_cop, fold, namespace, block_locals, references)

    if new_body is body_cop:
        return cop

    return comp.cop_rebuild(cop, [signature_cop, new_body])


def _optimize_namefield(cop, fold, namespace, locals, references):
    """Optimize a namefield, only processing the value child.

    Args:
        cop: (Value) Namefield COP node
        fold: (bool) Whether to fold
        namespace: (dict | None) Namespace
        locals: (set) Current locals
        references: (set | None) Collects discovered reference names

    Returns:
        (Value) Optimized namefield
    """
    kids = comp.cop_kids(cop)
    if len(kids) < 2:
        return cop

    name_cop = kids[0]
    value_cop = kids[1]

    new_value = _coptimize_walk(value_cop, fold, namespace, locals, references)

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


def _make_reference(original, qualified, module_id):
    """Create a value.reference COP node.

    Args:
        original: (Value) Original COP node for position
        qualified: (str | list) Qualified name(s)
        module_id: (str) Module identifier

    Returns:
        (Value) Reference COP node
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

