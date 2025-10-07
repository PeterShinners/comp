"""Build runtime shape structures from AST nodes."""

from typing import Any

from .. import ast
from . import _module, _shape, _struct, _value
from ._struct import Unnamed
from ._value import Value


def build_shape_from_ast(shape_node: ast.Node, module: _module.Module) -> _shape.ShapeType:
    """Convert an AST shape node to a runtime ShapeType.

    Args:
        shape_node: AST node representing a shape (ShapeInline, ShapeRef, etc.)
        module: The module context for resolving references

    Returns:
        Runtime ShapeType object
    """
    if isinstance(shape_node, ast.ShapeInline):
        return _build_inline_shape(shape_node, module)
    elif isinstance(shape_node, ast.ShapeRef):
        # Create a shape reference (will be resolved later)
        # Extract the name from tokens (ShapeRef.tokens is a tuple of strings)
        name = shape_node.tokens[0] if shape_node.tokens else ""
        return _shape.ShapeDefRef(name)
    elif isinstance(shape_node, ast.TagRef):
        # Create a tag reference
        # TagRef.tokens is a tuple of strings forming the tag identifier
        tag_name = ".".join(shape_node.tokens)
        return _shape.ShapeTagRef(tag_name)
    elif isinstance(shape_node, ast.ShapeUnion):
        # Convert union variants recursively
        variants = [build_shape_from_ast(variant, module) for variant in shape_node.kids]
        return _shape.ShapeUnion(variants)
    else:
        raise ValueError(f"Unknown shape AST node type: {type(shape_node)}")


def _build_inline_shape(inline_node: ast.ShapeInline, module: _module.Module) -> _shape.ShapeInline:
    """Convert an AST ShapeInline to runtime ShapeInline with proper field keys.

    Args:
        inline_node: AST ShapeInline node
        module: The module context

    Returns:
        Runtime ShapeInline with fields keyed by Value or Unnamed
    """
    fields = {}
    unnamed_count = 0

    # Process each field child
    for child in inline_node.kids:
        if isinstance(child, ast.ShapeField):
            # Determine the field key
            if child.name is None:
                # Positional/unnamed field - use Unnamed() as key
                field_key = _struct.Unnamed()
                unnamed_count += 1
            else:
                # Named field - use Value(name) as key
                field_key = _value.Value(child.name)

            # Build the shape type for this field (if it has one)
            field_shape = None
            if child.type_ref:
                field_shape = build_shape_from_ast(child.type_ref, module)

            # Create the ShapeField
            # Note: We use the string name for ShapeField.name even for unnamed fields
            # The field_key (Value or Unnamed) is what goes in the dict
            field_name = child.name if child.name is not None else f"_{unnamed_count}"
            shape_field = _module.ShapeField(field_name, field_shape)

            # Store with proper key type
            fields[field_key] = shape_field
        elif isinstance(child, ast.ShapeSpread):
            # TODO: Handle shape spread (..~othershape)
            pass

    return _shape.ShapeInline(fields=fields)


def populate_shape_def_fields(shape_def: _module.ShapeDef, ast_node: ast.ShapeDef, module: _module.Module):
    """Populate a ShapeDef's fields from its AST definition.

    Args:
        shape_def: The ShapeDef to populate
        ast_node: The AST ShapeDef node
        module: The module context
    """
    # The ShapeDef.kids contains the shape fields directly
    # (shape_body just passes through its children)
    if not ast_node.kids:
        return

    # Check if this is a non-structural shape (single TagRef, ShapeRef, etc.)
    if len(ast_node.kids) == 1 and not isinstance(ast_node.kids[0], ast.ShapeField):
        # This is a shape alias or tag constraint, not a structural definition
        # Store the actual shape type for morph to use
        shape_def.shape = build_shape_from_ast(ast_node.kids[0], module)
        return

    # The kids are shape fields directly (for braced shapes)
    # Build fields from the AST children
    fields = {}
    for i, child in enumerate(ast_node.kids):
        if isinstance(child, ast.ShapeField):
            # Extract field name (or use Unnamed)
            if child.name is None:
                field_key = Unnamed()
            else:
                field_key = Value(child.name)

            # Build the field's shape type
            field_shape = None
            if child.type_ref:
                field_shape = build_shape_from_ast(child.type_ref, module)

            # Create ShapeField object
            fields[field_key] = _module.ShapeField(
                name=child.name or f"_{i+1}",
                shape=field_shape
            )
        # elif isinstance(child, ast.ShapeSpread):
        #     # TODO: Handle shape spreads
        #     pass

    shape_def.fields.update(fields)
