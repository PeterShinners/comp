"""Code analysis and definition extraction from COP trees.

This module provides functionality to walk COP trees and extract definitions as Values:
- Tag definitions (hierarchical)
- Function definitions (with unique names for overloads)
- Shape definitions
- Package assignments
- Module scope assignments
"""

import comp

__all__ = ["extract_definitions"]


def extract_definitions(module):
    """Extract definitions from a module's COP tree.

    Walks the COP tree, resolves COP nodes to Values, and populates module.definitions
    as a dict of {qualified_name: Value}.

    The Values have their .cop attribute set to the original COP node for debugging.

    Args:
        module: Module with _temp_cop_tree to analyze

    Returns:
        module (for chaining)

    Raises:
        CodeError: If module has no COP tree or tree is malformed
    """
    # Get cop_tree from temporary attribute
    cop_tree = getattr(module, '_temp_cop_tree', None)
    if cop_tree is None:
        raise comp.CodeError("Module has no COP tree - call load_definitions() first")

    # Get the root mod.define node
    cop = cop_tree
    tag_value = cop.positional(0)

    # Extract Tag from Value wrapper
    tag = tag_value.data if hasattr(tag_value, 'data') else tag_value

    if not isinstance(tag, comp.Tag) or tag.qualified != "mod.define":
        raise comp.CodeError(f"Expected mod.define root, got {tag}", cop)

    # Get the kids field containing module-level definitions
    kids_field = cop.field("kids")

    # Process each kid (mod.namefield or other top-level statements)
    for kid_item in kids_field.data.values():
        _extract_and_store_definition(module, kid_item)

    return module


def _extract_and_store_definition(module, node):
    """Extract a definition from a COP node and store it in the module.

    Args:
        module: Module to store definition in
        node: A COP node (typically mod.namefield)
    """
    tag_value = node.positional(0)
    tag = tag_value.data if hasattr(tag_value, 'data') else tag_value

    if not isinstance(tag, comp.Tag):
        return

    if tag.qualified == "mod.namefield":
        _extract_namefield(module, node)
    # TODO: Handle other module-level constructs


def _extract_namefield(module, node):
    """Extract a definition from a mod.namefield node and store in module.

    Args:
        module: Module to store definition in
        node: A mod.namefield COP node
    """
    # Get the name and value from kids field
    # mod.namefield has kids: n=name, v=value
    kids = node.field("kids")
    kids_list = list(kids.data.values())
    name_node = kids_list[0]  # 'n' field
    value_node = kids_list[1]  # 'v' field

    # Extract the qualified name from the identifier
    name = _assign_identifier(name_node)

    if name is None:
        raise comp.CodeError("Invalid identifier in mod.namefield", node)

    # Check if it's a pkg.* assignment - store in package dict
    if name.startswith('pkg.'):
        _extract_package_assignment(module, name, value_node)
        return

    # Determine if private (names starting with underscore)
    private = name.startswith('_')

    # Resolve the value node to a Value (creates temp Def objects with base name)
    value = _resolve_definition_value(name, value_node)

    # Generate qualified name (handle function overloads)
    qualified_name = _generate_qualified_name(module, name, value, private)

    # Update the qualified field on Def objects if needed
    if isinstance(value.data, (comp.Func, comp.Tag, comp.Shape)):
        value.data.qualified = qualified_name

    # Store in module definitions
    module.definitions[qualified_name] = value


def _extract_package_assignment(module, name, value_node):
    """Extract a pkg.* assignment and store in module.definitions.

    Args:
        module: Module to store in
        name: The pkg.* name
        value_node: The value COP node
    """
    # Try to resolve to a constant Value
    try:
        empty_namespace = comp.Value.from_python({})
        resolved_cop = comp.resolve(value_node, empty_namespace, no_fold=True)

        if isinstance(resolved_cop, comp.Value):
            tag_value = resolved_cop.positional(0)
            if tag_value is not None and hasattr(tag_value, 'data'):
                tag_data = tag_value.data
                if isinstance(tag_data, comp.Tag) and tag_data.qualified == "value.constant":
                    const_value = resolved_cop.field("value")
                    # Store as Value with cop attribute
                    if not hasattr(const_value, 'cop') or const_value.cop is None:
                        const_value.cop = value_node
                    module.definitions[name] = const_value
                    return
    except Exception:
        pass

    # Fallback: extract simple literals and wrap in Value
    tag_value = value_node.positional(0)
    tag = tag_value.data if hasattr(tag_value, 'data') else tag_value

    if isinstance(tag, comp.Tag):
        data = None
        if tag.qualified == "value.text":
            data = value_node.positional(1).data
        elif tag.qualified == "value.number":
            data = value_node.positional(1).data

        if data is not None:
            value = comp.Value.from_python(data)
            value.cop = value_node
            module.definitions[name] = value


def _resolve_definition_value(name, value_node):
    """Resolve a COP node into a Value for a definition.

    For blocks (functions), tags, and shapes, creates the appropriate Def object.
    For other values, uses resolve() to create constants.

    Args:
        name: Base name of the definition
        value_node: COP node to resolve

    Returns:
        Value: The resolved value with .cop attribute set
    """
    tag_value = value_node.positional(0)
    tag = tag_value.data if hasattr(tag_value, 'data') else tag_value

    if not isinstance(tag, comp.Tag):
        raise comp.CodeError(f"Expected tagged value node, got {type(tag)}", value_node)

    # Determine if private
    private = name.startswith('_')

    # Handle special cases that need Def objects
    if tag.qualified == "value.block":
        # Functions need unique qualified names, but we'll do that in the caller
        # For now, create with temporary name
        return comp.create_funcdef(name, private, value_node)

    elif tag.qualified == "value.tag":
        return comp.create_tagdef(name, private, value_node)

    elif tag.qualified == "value.shape":
        return comp.create_shapedef(name, private, value_node)

    # For everything else, use resolve()
    try:
        empty_namespace = comp.Value.from_python({})
        resolved_cop = comp.resolve(value_node, empty_namespace, no_fold=True)

        # Check if it resolved to a constant
        if isinstance(resolved_cop, comp.Value):
            tag_value = resolved_cop.positional(0)
            if tag_value is not None and hasattr(tag_value, 'data'):
                tag_data = tag_value.data
                if isinstance(tag_data, comp.Tag) and tag_data.qualified == "value.constant":
                    value = resolved_cop.field("value")
                    # Make sure cop is set
                    if not hasattr(value, 'cop') or value.cop is None:
                        value.cop = value_node
                    return value
    except Exception:
        pass

    # If resolve didn't work, just return the value_node as-is (it's already a Value)
    # Make sure cop is set
    if not hasattr(value_node, 'cop') or value_node.cop is None:
        value_node.cop = value_node
    return value_node


def _generate_qualified_name(module, base_name, value, private):
    """Generate a unique qualified name for a definition.

    For functions, appends .i001, .i002, etc. for overloads.
    For tags and shapes, uses the base name.

    Args:
        module: Module containing the definition
        base_name: Base name (e.g., "add")
        value: The Value being defined
        private: Whether the definition is private

    Returns:
        str: Qualified name
    """
    # Check if it's a function by looking at the value data
    if isinstance(value.data, comp.Func):
        # TODO: Track overloads properly and generate correct counter
        # For now, use simple .i001 suffix
        return f"{base_name}.i001"
    else:
        # Tags and shapes use their base name directly
        return base_name


def _assign_identifier(id_node):
    """Extract qualified name from value.identifier node for assignments.

    Returns string like "pkg.name" or "add" or "server.status.ok"
    """
    cop_tag = id_node.positional(0).data.qualified
    if cop_tag != "value.identifier":
        raise comp.CodeError(f"Assign identifier unexpected {cop_tag}")
    kids = id_node.field("kids")
    parts = []
    for kid in kids.data.values():
        kid_token = kid.positional(0).data.qualified
        if kid_token in ("ident.token", "ident.text"):
            part = kid.field("value").data
        else:
            raise comp.CodeError(f"Unable to assign to {kid_token} identifier")
        parts.append(part)
    return '.'.join(parts) if parts else None
