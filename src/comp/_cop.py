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
    "cop_tag",
    "cop_kids",
    "cop_unparse",
    "cop_resolve",
    "resolve_identifiers",
]

import decimal
import comp


def create_cop(tag_name, kids, **fields):
    """Create a COP node with the given tag and children.

    Args:
        tag_name: String tag like "value.block" or "mod.define"
        kids: List of child COP nodes
        **fields: Additional named fields

    Returns:
        Value: The constructed COP node
    """
    # Get the Tag object from the cop internal module
    cop_module = comp.get_cop_module()
    tag_definition = cop_module.definitions().get(tag_name)
    if tag_definition is None:
        raise ValueError(f"Unknown COP tag: {tag_name}")

    tag = tag_definition.value.data  # Extract the Tag from the Definition

    data = {comp.Unnamed(): tag}
    for key, value in fields.items():
        data[key] = value
    data["kids"] = comp.Value.from_python(kids)
    value = comp.Value.from_python(data)
    return value


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
        # Extract the qualified name from the identifier
        name = None
        parts = []
        for kid in cop_kids(cop):
            kid_tag = cop_tag(kid)
            if kid_tag in ("ident.token", "ident.text"):
                try:
                    value = kid.field("value").data
                    parts.append(value)
                except (KeyError, AttributeError):
                    break
            else:
                # Complex identifiers not supported yet
                break
        if parts:
            name = '.'.join(parts)

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
                fields = {
                    "qualified": definition.qualified,
                    "module_id": definition.module_id
                }
                if import_namespace is not None:
                    fields["namespace"] = import_namespace
                try:
                    pos = cop.field("pos")
                    if pos is not None:
                        fields["pos"] = pos
                except (KeyError, AttributeError):
                    pass
                return create_cop("value.reference", [], **fields)

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
            return cop.to_python("identifier")
            # if not found, could fallback on definition.qualified
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


