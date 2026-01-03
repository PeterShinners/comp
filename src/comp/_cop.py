"""COP (Compiler Operator) tree manipulation and transformation.

COP trees are the intermediate representation between parsing and code generation.
They are similar to AST structures but designed to be easy to manipulate, assemble,
and transform. COP objects are simple comp structures that are easy to serialize.

This module handles:
- COP node creation and inspection
- Identifier resolution (converting identifiers to references)
- Constant folding (compile-time evaluation)
- Definition folding with dependency tracking
- Unparsing (converting COP back to source text)
"""

__all__ = [
    "create_cop",
    "create_reference_cop",
    "cop_tag",
    "cop_kids",
    "cop_module",
    "cop_unparse",
    "cop_unparse_reference",
    "cop_fold",
    "cop_resolve",
    "resolve_identifiers",
    "fold_definitions",
]

import decimal
import comp
from comp._parse import _tagnames, cop_module as _cop_module_init


# COP Structure Functions

def cop_module():
    """Create an empty module COP node.

    Returns:
        Value: A mod.define COP node with no children
    """
    return create_cop("mod.define", [])


def create_cop(tag_name, kids, **fields):
    """Create a COP node with the given tag and children.

    Args:
        tag_name: String tag like "value.block" or "mod.define"
        kids: List of child COP nodes
        **fields: Additional named fields

    Returns:
        Value: The constructed COP node
    """
    _cop_module_init()  # Ensure tags are initialized
    tag = _tagnames[tag_name]
    data = {comp.Unnamed(): tag}
    for key, value in fields.items():
        data[key] = value
    data["kids"] = comp.Value.from_python(kids)
    value = comp.Value.from_python(data)
    return value


def create_reference_cop(definition, identifier_cop=None, import_namespace=None):
    """Create a value.reference COP node pointing to a definition.

    Args:
        definition: Definition object to reference
        identifier_cop: Optional original identifier COP (for position info)
        import_namespace: Optional import namespace string

    Returns:
        Value: A value.reference COP node
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


def cop_tag(cop_node):
    """Get the qualified tag name from a COP node.

    Args:
        cop_node: A COP Value node

    Returns:
        str: Qualified tag name like "mod.define", or None if invalid
    """
    try:
        tag = cop_node.positional(0)
        return tag.data.qualified
    except (AttributeError, KeyError, TypeError):
        return None


def cop_kids(cop_node):
    """Get the kids list from a COP node.

    Args:
        cop_node: A COP Value node

    Returns:
        list: List of child COP nodes (empty list if no kids)
    """
    try:
        kids = cop_node.field("kids")
        return list(kids.data.values())
    except (KeyError, AttributeError, TypeError):
        return []


# Identifier Resolution

def resolve_identifiers(definitions, namespace):
    """Resolve identifiers in definitions to value.reference nodes.

    This function walks all definition COP trees and replaces value.identifier
    nodes with value.reference nodes pointing to Definition objects.

    Args:
        definitions: Dict {qualified_name: Definition} to resolve
        namespace: Namespace dict {name: DefinitionSet}

    Returns:
        dict: The definitions dictionary (for chaining)

    Side effects:
        Populates definition.resolved_cop for each definition in definitions
    """
    # Resolve identifiers in each definition
    for qualified_name, definition in definitions.items():
        # Skip non-Definition objects (e.g., AST module Tags)
        if not isinstance(definition, comp.Definition):
            continue

        if definition.original_cop is None:
            continue

        # Skip if already resolved (e.g., SystemModule builtins)
        if definition.resolved_cop is not None:
            continue

        # Walk the COP tree and replace identifiers with references
        definition.resolved_cop = _resolve_to_references(
            definition.original_cop,
            namespace
        )

    return definitions


def _resolve_to_references(cop, namespace, param_names=None):
    """Walk a COP tree and replace value.identifier with value.reference nodes.

    Args:
        cop: The COP node to walk
        namespace: Module namespace dict {name: DefinitionSet}
        param_names: Set of parameter names to skip (handled by codegen)

    Returns:
        Potentially modified COP node
    """
    if cop is None:
        return cop

    param_names = param_names or set()
    tag = cop_tag(cop)

    # Handle value.identifier - replace with value.reference
    if tag == "value.identifier":
        name = _get_identifier_name(cop)

        # Skip if we couldn't extract a name
        if name is None:
            return cop

        # Skip parameter names (handled by codegen)
        if name in param_names:
            return cop

        # Try to resolve from namespace
        definition_set = namespace.get(name)
        if definition_set is not None:
            # Extract Definition from DefinitionSet
            definition = None
            import_namespace = None

            # Try to get a scalar (unambiguous) definition
            scalar_def = definition_set.scalar()
            if scalar_def is not None:
                # Single unambiguous definition
                definition = scalar_def
                # Check if this came from an import
                if hasattr(definition, '_import_namespace'):
                    import_namespace = definition._import_namespace
            else:
                # Multiple definitions (overloaded) - leave as identifier for build-time resolution
                return cop

            # Create value.reference node
            if definition is not None:
                return create_reference_cop(
                    definition,
                    identifier_cop=cop,
                    import_namespace=import_namespace
                )

        # Unresolved - leave as-is (will error at build time)
        return cop

    # Handle value.block - extract parameter names from signature
    elif tag == "value.block":
        kids_list = cop_kids(cop)
        if len(kids_list) >= 2:
            signature_cop = kids_list[0]
            body_cop = kids_list[1]

            # Extract parameter names from signature
            new_param_names = param_names.copy()
            # TODO: Parse signature to get actual param names
            # For now, assume 'input' and 'args' are standard
            new_param_names.add('input')
            new_param_names.add('args')

            # Recursively walk the body with updated param names
            new_body = _resolve_to_references(body_cop, namespace, new_param_names)

            # If body changed, create new block cop
            if new_body is not body_cop:
                kids_field = cop.field("kids")
                new_kids_dict = kids_field.data.copy()
                keys = list(new_kids_dict.keys())
                if len(keys) >= 2:
                    new_kids_dict[keys[1]] = new_body

                    # Reconstruct the cop
                    new_data = {}
                    for key, value in cop.data.items():
                        if isinstance(key, comp.Value) and key.data == "kids":
                            new_data[key] = comp.Value.from_python(new_kids_dict)
                        else:
                            new_data[key] = value

                    return comp.Value.from_python(new_data)

        return cop

    # Handle mod.namefield - only resolve the value child, not the name
    elif tag == "mod.namefield":
        try:
            modified = False
            new_kids_dict = {}
            for key, kid in cop.field("kids").data.items():
                # Check if this is the name field (n=) or value field (v=)
                # The name field should NOT be resolved
                if key.data == "n":
                    new_kids_dict[key] = kid
                else:
                    new_kid = _resolve_to_references(kid, namespace, param_names)
                    new_kids_dict[key] = new_kid
                    if new_kid is not kid:
                        modified = True

            # If any kids changed, create new cop
            if modified:
                new_data = {}
                for key, value in cop.data.items():
                    if isinstance(key, comp.Value) and key.data == "kids":
                        new_data[key] = comp.Value.from_python(new_kids_dict)
                    else:
                        new_data[key] = value

                return comp.Value.from_python(new_data)
        except (KeyError, AttributeError):
            pass

        return cop

    # For all other nodes, recursively walk kids
    else:
        try:
            modified = False
            new_kids_dict = {}
            for key, kid in cop.field("kids").data.items():
                new_kid = _resolve_to_references(kid, namespace, param_names)
                new_kids_dict[key] = new_kid
                if new_kid is not kid:
                    modified = True

            # If any kids changed, create new cop
            if modified:
                new_data = {}
                for key, value in cop.data.items():
                    if isinstance(key, comp.Value) and key.data == "kids":
                        new_data[key] = comp.Value.from_python(new_kids_dict)
                    else:
                        new_data[key] = value

                return comp.Value.from_python(new_data)
        except (KeyError, AttributeError):
            pass

    return cop


def _get_identifier_name(id_cop):
    """Extract the qualified name from a value.identifier COP node.

    Args:
        id_cop: A value.identifier COP node

    Returns:
        String like "add" or "server.host" or None if not a valid identifier
    """
    if cop_tag(id_cop) != "value.identifier":
        return None

    parts = []
    for kid in cop_kids(id_cop):
        kid_tag = cop_tag(kid)
        if kid_tag in ("ident.token", "ident.text"):
            try:
                value = kid.field("value").data
                parts.append(value)
            except (KeyError, AttributeError):
                return None
        else:
            # Complex identifiers not supported yet
            return None

    if not parts:
        return None

    return '.'.join(parts)


# Constant Folding

def cop_fold(cop, namespace=None):
    """Fold cop constants with compile-time evaluation.

    Args:
        cop: (Value) Cop structure to fold
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
                elif field_tag == "struct.namefield":
                    key_cop = field_kids[0]
                    value_cop = field_kids[1]
                    key = _get_simple_identifier(key_cop)
                    value = _get_constant(value_cop)
                else:
                    return cop
                if key is None or value is None:
                    return cop
                struct[key] = value
            constant = comp.Value.from_python(struct)
            return _make_constant(cop, constant)

    if changed:
        return create_cop(tag, kids)
    return cop


def cop_resolve(cop, namespace):
    """Resolve identifiers in a COP tree to references.

    This is a convenience wrapper around _resolve_to_references.

    Args:
        cop: COP node to resolve
        namespace: Namespace dict {name: DefinitionSet}

    Returns:
        Resolved COP node
    """
    return _resolve_to_references(cop, namespace)


def _make_constant(original, value):
    """Create a value.constant COP node preserving position info."""
    fields = {"value": value}
    try:
        pos = original.field("pos")
        if pos is not None:
            fields["pos"] = pos
    except (KeyError, AttributeError):
        pass
    return create_cop("value.constant", [], **fields)


def _get_constant(cop):
    """Extract constant value from a value.constant COP node."""
    if cop_tag(cop) == "value.constant":
        try:
            return cop.field("value")
        except (KeyError, AttributeError):
            pass
    return None


def _get_simple_identifier(cop):
    """Extract simple identifier string from COP node."""
    if cop_tag(cop) == "value.identifier":
        kids = cop_kids(cop)
        if len(kids) == 1 and cop_tag(kids[0]) == "ident.token":
            try:
                return kids[0].field("value").data
            except (KeyError, AttributeError):
                pass
    return None


# Definition Folding with Dependencies

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
            resolved_cop = _resolve_to_references(defn.original_cop, namespace)

            # Walk the entire tree to find all references and ensure they're folded
            def ensure_all_deps(node):
                tag = cop_tag(node)
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
                for kid in cop_kids(node):
                    ensure_all_deps(kid)

            ensure_all_deps(resolved_cop)
            # Now do normal folding with all dependencies ready
            folded_cop = cop_fold(resolved_cop, namespace)

            # Try to extract constant value
            if cop_tag(folded_cop) == "value.constant":
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


# Unparsing

def cop_unparse(cop):
    """Convert a COP tree back to source code text.

    Args:
        cop: COP node to unparse

    Returns:
        str: Source code representation
    """
    tag = cop_tag(cop)
    kids = cop_kids(cop)

    match tag:
        case "mod.define":
            parts = []
            for kid in kids:
                parts.append(cop_unparse(kid))
            return '\n'.join(parts)
        case "mod.namefield":
            if len(kids) >= 2:
                name = cop_unparse(kids[0])
                value = cop_unparse(kids[1])
                return f"{name} = {value}"
            return "<?>"
        case "value.identifier":
            parts = []
            for kid in kids:
                kid_tag = cop_tag(kid)
                if kid_tag in ("ident.token", "ident.text"):
                    parts.append(kid.field("value").data)
            return '.'.join(parts) if parts else "<?>"
        case "value.reference":
            return cop_unparse_reference(cop)
        case "value.constant":
            try:
                value = cop.field("value")
                return str(value.data)
            except (KeyError, AttributeError):
                return "<?>"
        case "value.number":
            try:
                return cop.field("value").data
            except (KeyError, AttributeError):
                return "<?>"
        case "value.text":
            try:
                text = cop.field("value").data
                # Escape quotes and backslashes
                escaped = text.replace('\\', '\\\\').replace('"', '\\"')
                return f'"{escaped}"'
            except (KeyError, AttributeError):
                return "<?>"
        case "value.nil":
            return "nil"
        case "value.math.unary":
            if kids:
                op = cop.to_python("op")
                return f"{op}{cop_unparse(kids[0])}"
            return "<?>"
        case "value.math.binary":
            if len(kids) >= 2:
                op = cop.to_python("op")
                return f"{cop_unparse(kids[0])}{op}{cop_unparse(kids[1])}"
            return "<?>"
        case "shape.union":
            parts = [cop_unparse(kid) for kid in kids]
            return ' | '.join(parts)
        case "struct.letassign":
            if len(kids) >= 2:
                name = cop_unparse(kids[0])
                value = cop_unparse(kids[1])
                return f"!let {name} = {value}"
            return "<?>"
        case _:
            return f"<{tag}>"


def cop_unparse_reference(cop):
    """Unparse a value.reference COP node.

    Args:
        cop: A value.reference COP node

    Returns:
        str: The reference name
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
