"""Code analysis and definition extraction from COP trees."""

__all__ = ["extract_definitions"]

import comp


def extract_definitions(cop_module, module_id):
    """Extract definitions from a COP tree.

    This is a pure function that creates Definition objects without
    instantiating Block/Shape/Tag values.

    Args:
        cop_module: mod.define COP node
        module_id: Module token string (e.g., "./cart#a1b2")

    Returns:
        dict: {qualified_name: Definition} definitions

    Raises:
        CodeError: If tree is malformed
    """
    definitions = {}
    overloads = {}
    for kid in comp.cop_kids(cop_module):
        identifier, definition, uniqueify = _module_definition(kid, module_id)
        if uniqueify:
            counter = overloads.get(identifier, 0) + 1
            overloads[identifier] = counter
            identifier = f"{identifier}.i{counter:03d}"
            # Update definition with uniquified name and mark as auto-suffixed
            definition.qualified = identifier
            definition.auto_suffix = True

        definitions[identifier] = definition
    return definitions


def _module_definition(cop, module_id):
    """Generate identifier and Definition for mod.namefield cop.

    Args:
        cop: mod.namefield COP node
        module_id: Module token string

    Returns:
        tuple: (identifier, Definition, uniqueify)
    """
    kid_tag = comp.cop_tag(cop)
    if kid_tag != "mod.namefield":
        raise comp.CodeError(f"Unexpected cop node in mod.define: {kid_tag}")

    cop_identifier, cop_value = comp.cop_kids(cop)
    identifier = _assign_identifier(cop_identifier)
    value_tag = comp.cop_tag(cop_value)
    _validate_assignment(identifier, value_tag)

    private = False  # Wait for language to define privacy rules
    uniqueify = False

    # Determine definition shape from COP tag
    match value_tag:
        case "value.block":
            # Blocks (functions)
            shape = comp.shape_block
            uniqueify = True
        case "shape.define":
            # Shape definitions
            shape = comp.shape_shape
        # What about unions, literals, ?
        case _:
            #raise comp.CodeError(f"Invalid module value: {value_tag} for {identifier}")
            # All types are temporarily helpful for quick and minimal testing
            shape = comp.shape_struct

    # Create Definition with original COP node
    # No Block/Shape creation here - that happens during constant folding
    definition = comp.Definition(identifier, module_id, cop_value, shape)

    return identifier, definition, uniqueify


def _assign_identifier(identifier_cop):
    """Extract name from value.identifier like 'add' or 'server.host'."""
    parts = []
    for kid in comp.cop_kids(identifier_cop):
        kid_tag = comp.cop_tag(kid)
        if kid_tag in ("ident.token", "ident.text"):
            parts.append(kid.field("value").data)
        else:
            raise comp.CodeError(f"Module assignment cannot use {kid_tag} identifiers")
    if not parts:
        raise comp.CodeError(f"Module assignment cannot have empty identifier")
    return '.'.join(parts)


def _validate_assignment(identifier, value_tag):
    """Validate module assignment rules."""
    if identifier.startswith("pkg."):
        # Accept constant values (literals and pre-folded constants)
        if value_tag not in ("value.constant", "value.text", "value.number", "value.nil"):
            raise comp.CodeError(f"Module assignment to {identifier} must be constant")
    elif identifier.startswith("startup."):
        if value_tag != "value.block":
            raise comp.CodeError(f"Module assignment to {identifier} must be a function")
    elif identifier.startswith("tag."):
        if value_tag not in ("value.shape", "shape.define"):
            raise comp.CodeError(f"Module assignment to {identifier} must be a shape")
