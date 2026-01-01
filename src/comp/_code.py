"""Code analysis and definition extraction from COP trees."""

__all__ = ["extract_definitions"]

import comp


def extract_definitions(cop_module):
    """Extract definitions from a COP tree.

    Args:
        cop_module: mod.define COP node

    Returns:
        dict: {qualified_name: Value} definitions

    Raises:
        CodeError: If tree is malformed
    """
    definitions = {}
    overloads = {}
    for kid in comp.cop_kids(cop_module):
        identifier, value, uniqueify = _module_definition(kid)
        if uniqueify:
            counter = overloads.get(identifier, 0) + 1
            overloads[identifier] = counter
            identifier = f"{identifier}.i{counter:03d}"

        definitions[identifier] = value
    return definitions


def _module_definition(cop):
    """Generate identifier and value for mod.namefield cop."""
    kid_tag = comp.cop_tag(cop)
    if kid_tag != "mod.namefield":
        raise comp.CodeError(f"Unexpected cop node in mod.define: {kid_tag}")

    empty_ns = comp.Value.from_python({})
    cop_identifier, cop_value = comp.cop_kids(cop)
    identifier = _assign_identifier(cop_identifier)
    cop_value = comp._parse.cop_resolve(cop_value, empty_ns)
    value_tag = comp.cop_tag(cop_value)
    _validate_assignment(identifier, value_tag)

    cop_value_folded = comp._parse.cop_fold(cop_value)
    folded_tag = comp.cop_tag(cop_value_folded)

    private = False  # Wait for language to define privacy rules
    uniqueify = False

    # Special def objects
    match value_tag:
        case "value.constant":
            value = cop_value_folded.field("value")
        case "value.text" | "value.number" | "value.nil":
            # Literal values - extract from folded constant
            value = cop_value_folded.field("value")
        case "value.identifier":
            # Reference to another value - will be resolved during finalize
            # Wrap the COP in a Value and mark it for later resolution
            value = comp.Value.from_python(None)  # Placeholder
            value.cop = cop_value_folded
        case "value.block":
            uniqueify = True
            # Blocks need unfolded cop to parse signature (folding turns it into constant)
            # Check if folding created a constant (shouldn't happen for blocks currently)
            # This is a dumb temporary measure. Using the folded "constant" shape
            # is largely the most common situation and far better.
            if folded_tag == "value.constant":
                value = cop_value_folded.field("value")
            else:
                value = comp.create_funcdef(identifier, private, cop_value)
        case "shape.define":
            # Check if folding successfully created a Shape or ShapeUnion constant
            if folded_tag == "value.constant":
                # Use the pre-built shape/union from folding
                value = cop_value_folded.field("value")
                # Update qualified name and privacy for Shape (ShapeUnion doesn't have these)
                if isinstance(value.data, comp.Shape):
                    value.data.qualified = identifier
                    value.data.private = private
            else:
                # Folding failed (has complex constructs), build from unfolded cop
                value = comp.create_shapedef(identifier, private, cop_value)
        case _:
            raise comp.CodeError(f"Invalid module value: {value_tag} for {identifier}")

    return identifier, value, uniqueify


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
