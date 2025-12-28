"""Code analysis and definition extraction from COP trees.

This module provides functionality to walk COP trees and extract:
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

    Walks the COP tree and populates the module's definition lists:
    - module.package: pkg.* assignments
    - module.publicdefs: Exported definitions (tags, funcs, shapes)
    - module.privatedefs: Private definitions

    Args:
        module: Module with cop_tree to analyze

    Returns:
        module (for chaining)

    Raises:
        ValueError: If module has no cop_tree
    """
    if module.cop_tree is None:
        raise ValueError("Module has no cop_tree - call get_cop() first")

    # Get the root mod.define node
    cop = module.cop_tree
    tag_value = cop.positional(0)

    # Extract Tag from Value wrapper
    tag = tag_value.data if hasattr(tag_value, 'data') else tag_value

    if not isinstance(tag, comp.Tag) or tag.qualified != "mod.define":
        raise ValueError(f"Expected mod.define root, got {tag}")

    # Get the kids field containing module-level definitions
    kids_field = cop.field('kids')

    # Process each kid (mod.namefield or other top-level statements)
    for kid_item in kids_field.data.values():
        _process_module_item(module, kid_item)

    return module


def _process_module_item(module, node):
    """Process a single module-level item (mod.namefield, etc.)."""
    tag_value = node.positional(0)
    tag = tag_value.data if hasattr(tag_value, 'data') else tag_value

    if not isinstance(tag, comp.Tag):
        return

    if tag.qualified == "mod.namefield":
        _process_namefield(module, node)
    # TODO: Handle other module-level constructs


def _process_namefield(module, node):
    """Process a mod.namefield assignment (name = value)."""
    # Get the name and value from kids
    kids = node.field('kids')
    name_node = kids.data.get(comp.Value.from_python('n'))
    value_node = kids.data.get(comp.Value.from_python('v'))

    if not name_node or not value_node:
        return

    # Extract the qualified name from the identifier
    name = _extract_identifier(name_node)

    if name is None:
        return

    # Check if it's a pkg.* assignment
    if name.startswith('pkg.'):
        _process_package_assignment(module, name, value_node)
    else:
        _process_definition(module, name, value_node)


def _extract_identifier(id_node):
    """Extract qualified name from value.identifier node.

    Returns string like "pkg.name" or "add" or "server.status.ok"
    """
    tag_value = id_node.positional(0)
    tag = tag_value.data if hasattr(tag_value, 'data') else tag_value

    if not isinstance(tag, comp.Tag) or tag.qualified != "value.identifier":
        return None

    # Get kids containing ident.token nodes
    kids = id_node.field('kids')

    parts = []
    for token_item in kids.data.values():
        token_tag_value = token_item.positional(0)
        token_tag = token_tag_value.data if hasattr(token_tag_value, 'data') else token_tag_value
        if isinstance(token_tag, comp.Tag) and token_tag.qualified == "ident.token":
            value = token_item.field('value').data
            parts.append(value)

    return '.'.join(parts) if parts else None


def _process_package_assignment(module, name, value_node):
    """Process a pkg.* assignment."""
    # Extract the value
    value = _extract_constant_value(value_node)

    if value is not None:
        module.package[name] = value


def _process_definition(module, name, value_node):
    """Process a module-level definition (function, tag, shape, etc.)."""
    value_tag_value = value_node.positional(0)
    value_tag = value_tag_value.data if hasattr(value_tag_value, 'data') else value_tag_value

    if not isinstance(value_tag, comp.Tag):
        return

    if value_tag.qualified == "value.block":
        _process_function_definition(module, name, value_node)
    # TODO: Handle tag definitions, shape definitions, etc.


def _process_function_definition(module, name, block_node):
    """Process a function definition (name = :(...))."""
    # Generate unique qualified name for this function
    # For now, use simple counter-based naming
    # TODO: Track overloads and generate proper unique names

    qualified_name = f"{name}.i001"

    # Create FuncDef
    func_def = comp.FuncDef(qualified_name, private=False)
    func_def.module = module

    # TODO: Parse the block signature and body
    # For now, just store the COP node
    func_def.body = block_node

    # Add to publicdefs
    module.publicdefs.append(func_def)


def _extract_constant_value(value_node):
    """Extract a constant value from a COP node.

    Returns Python value (str, int, float) or None if not a constant.
    """
    value_tag_value = value_node.positional(0)
    value_tag = value_tag_value.data if hasattr(value_tag_value, 'data') else value_tag_value

    if not isinstance(value_tag, comp.Tag):
        return None

    if value_tag.qualified == "value.text":
        return value_node.field('value').data
    elif value_tag.qualified == "value.number":
        return value_node.field('value').data
    # TODO: Handle other constant types

    return None
