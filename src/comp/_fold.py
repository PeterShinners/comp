"""Constant folding and definition folding operations.

This module handles compile-time evaluation of COP trees:
- Constant folding: Evaluate expressions at compile time
- Definition folding: Resolve and fold module-level definitions with dependency tracking
"""

__all__ = [
    "cop_fold",
    "fold_definitions",
]

import decimal
import comp


def cop_fold(cop, namespace=None):
    """Fold cop constants with compile-time evaluation.

    Args:
        cop: (Value) Cop structure to fold
        namespace: (dict) Optional namespace dict {name: DefinitionSet} for resolving references
    Returns:
        (Value) Modified cop structure
    """
    tag = comp.cop_tag(cop)

    kids = []
    changed = False
    for kid in comp.cop_kids(cop):
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
                field_kids = comp.cop_kids(field_cop)
                if field_tag == "struct.posfield":
                    key = comp.Unnamed()
                    value = _get_constant(field_kids[0])
                elif field_tag == "struct.namefield":
                    key_cop = field_kids[0]
                    value_cop = field_kids[1]
                    # Extract simple identifier string from key_cop
                    key = None
                    if comp.cop_tag(key_cop) == "value.identifier":
                        kids = comp.cop_kids(key_cop)
                        if len(kids) == 1 and comp.cop_tag(kids[0]) == "ident.token":
                            try:
                                key = kids[0].field("value").data
                            except (KeyError, AttributeError):
                                pass
                    value = _get_constant(value_cop)
                else:
                    return cop
                if key is None or value is None:
                    return cop
                struct[key] = value
            constant = comp.Value.from_python(struct)
            return _make_constant(cop, constant)

    if changed:
        return comp.create_cop(tag, kids)
    return cop


def _make_constant(original, value):
    """Create a value.constant COP node preserving position info."""
    fields = {"value": value}
    try:
        pos = original.field("pos")
        if pos is not None:
            fields["pos"] = pos
    except (KeyError, AttributeError):
        pass
    return comp.create_cop("value.constant", [], **fields)


def _get_constant(cop):
    """Extract constant value from a value.constant COP node."""
    if comp.cop_tag(cop) == "value.constant":
        try:
            return cop.field("value")
        except (KeyError, AttributeError):
            pass
    return None


def fold_definitions(definitions, namespace):
    """Fold definitions with dependency tracking.

    This ensures definitions are folded in dependency order, handling
    circular dependencies gracefully. Each definition is folded at most
    once (O(n) time complexity).

    Args:
        definitions: Dict {qualified_name: Definition} to fold
        namespace: Namespace dict {name: DefinitionSet}

    Returns:
        dict: The definitions dictionary (for chaining)

    Side effects:
        Populates definition.value for each foldable definition
    """
    folding_stack = set()  # Track what we're currently folding to detect cycles

    def ensure_folded(defn):
        """Recursively ensure a definition's value is folded."""
        if defn.value is not None:
            return  # Already folded

        if defn in folding_stack:
            return  # Cycle detected, can't fold

        folding_stack.add(defn)
        try:
            # First resolve identifiers to references
            resolved_cop = comp._cop._resolve_to_references(defn.original_cop, namespace)

            # Walk the entire tree to find all references and ensure they're folded
            def ensure_all_deps(node):
                tag = comp.cop_tag(node)
                if tag == "value.reference" and namespace is not None:
                    try:
                        qualified = node.field("qualified").data
                        def_set = namespace.get(qualified)
                        if def_set is not None:
                            dep_def = def_set.scalar()
                            if dep_def is not None:
                                # Recursively ensure dependency is folded
                                ensure_folded(dep_def)
                    except:
                        pass
                # Recursively check children
                for kid in comp.cop_kids(node):
                    ensure_all_deps(kid)

            ensure_all_deps(resolved_cop)
            # Now do normal folding with all dependencies ready
            folded_cop = cop_fold(resolved_cop, namespace)

            # Try to extract constant value
            if comp.cop_tag(folded_cop) == "value.constant":
                try:
                    defn.value = folded_cop.field("value")
                except:
                    pass
        finally:
            folding_stack.remove(defn)

    # Fold all definitions (dependencies will be folded recursively)
    for defn in definitions.values():
        if isinstance(defn, comp.Definition):
            ensure_folded(defn)

    return definitions
