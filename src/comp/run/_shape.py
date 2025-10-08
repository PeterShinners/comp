"""Build runtime shape structures from AST nodes."""

__all__ = ["ShapeDef", "ShapeField", "ShapeType", "ShapeRef", "ShapeTagRef", "ShapeInline", "ShapeUnion"]

import comp

from . import _value


class ShapeDef:
    """Shape definition - immutable, belongs to defining module."""

    def __init__(self, identifier):
        """Create a shape definition."""
        self.identifier = identifier
        self.name = ".".join(identifier)
        self.fields = {}
        self.shape = None
        self._resolved = False

    def resolve(self, module):
        """Resolve shape references and expand field definitions."""
        if self._resolved:
            return

        # Resolve the base shape if this is a non-structural shape
        if self.shape:
            self.shape.resolve(module)

        # Resolve each field's shape type
        for _field_name, field in list(self.fields.items()):
            if field.shape:
                field.shape.resolve(module)
                # Expand fields from referenced shapes
                self._expand_shape_fields(field.shape, module)

        self._resolved = True

    def _expand_shape_fields(self, shape_type, module):
        """Walk through shape references to expand fields."""
        if isinstance(shape_type, ShapeRef):
            # Follow reference to expand fields from that shape
            if shape_type._resolved:
                target_shape = shape_type._resolved
                if not target_shape._resolved:
                    # Need the appropriate module for resolution context
                    if shape_type.namespace and shape_type.namespace in module.mods:
                        # Cross-module reference
                        other_module = module.mods[shape_type.namespace]
                        target_shape.resolve(other_module)
                    else:
                        # Local reference
                        target_shape.resolve(module)
                # Copy fields from referenced shape
                for field_name, field in list(target_shape.fields.items()):
                    if field_name not in self.fields:
                        self.fields[field_name] = field

        elif isinstance(shape_type, ShapeTagRef):
            # Tags don't expand fields - they act as constraints
            pass

        elif isinstance(shape_type, ShapeInline):
            # Inline shapes may have nested shape types
            for _field_name, field_type in shape_type.fields.items():
                if isinstance(field_type, ShapeType):
                    self._expand_shape_fields(field_type, module)

        elif isinstance(shape_type, ShapeUnion):
            # Union: expand fields from all variants
            for variant in shape_type.variants:
                self._expand_shape_fields(variant, module)

    def __repr__(self):
        field_count = len(self.fields)
        status = " (resolved)" if self._resolved else ""
        return f"ShapeDef(~{self.name}, {field_count} fields{status})"


class ShapeField:
    """Field within a shape definition."""

    def __init__(self, name, shape: "ShapeType | None" = None):
        """Create a shape field.
        
        Args:
            name: Field name as a Value (or Unnamed for positional fields)
            shape: Optional shape type constraint for this field
        """
        self.name = name  # Value or Unnamed
        self.shape = shape

    def __repr__(self):
        shape_str = f": {self.shape}" if self.shape else ""
        return f"ShapeField({self.name!r}{shape_str})"


class ShapeType:
    """Base class for all shape representations."""

    def resolve(self, module):
        """Resolve forward references within module context."""
        pass

    def __repr__(self):
        pass


class ShapeRef(ShapeType):
    """Reference to a shape definition (local or cross-module).

    Can reference shapes in the current module (namespace=None) or in
    imported modules (namespace specified). The resolution logic handles
    both cases uniformly.
    """

    def __init__(self, name, namespace=None):
        self.name = name
        self.namespace = namespace
        self._resolved = None

    def resolve(self, module):
        if self._resolved:
            return

        if self.namespace is None:
            # Local reference - look in current module
            if self.name in module.shapes:
                self._resolved = module.shapes[self.name]
        else:
            # Cross-module reference - look in imported module
            if self.namespace in module.mods:
                other_mod = module.mods[self.namespace]
                if self.name in other_mod.shapes:
                    self._resolved = other_mod.shapes[self.name]

    def __repr__(self):
        namespace_str = f"/{self.namespace}" if self.namespace else ""
        status = f" -> {self._resolved}" if self._resolved else " (unresolved)"
        return f"ShapeRef(~{self.name}{namespace_str}{status})"


class ShapeTagRef(ShapeType):
    """Reference to a tag used as a shape constraint."""

    def __init__(self, name):
        self.name = name
        self._resolved = None

    def resolve(self, module):
        if not self._resolved:
            # Try to resolve tag using module's resolve_tag method
            # which searches both the current module and referenced modules
            tokens = self.name.split(".")
            self._resolved = module.resolve_tag(tokens, namespace=None)

    def __repr__(self):
        status = f" -> {self._resolved}" if self._resolved else " (unresolved)"
        return f"ShapeTagRef(#{self.name}{status})"


class ShapeInline(ShapeType):
    """Inline shape definition."""

    def __init__(self, fields=None):
        """Initialize inline shape.

        Args:
            fields: Dictionary mapping field keys (Value or Unnamed) to ShapeField objects
        """
        self.fields = fields or {}
        self._resolved = False

    def resolve(self, module):
        if self._resolved:
            return

        for _field_key, field_def in self.fields.items():
            if hasattr(field_def, "shape") and isinstance(field_def.shape, ShapeType):
                field_def.shape.resolve(module)

        self._resolved = True

    def __repr__(self):
        field_count = len(self.fields)
        status = " (resolved)" if self._resolved else ""
        return f"ShapeInline(~{{{field_count} fields}}{status})"


class ShapeUnion(ShapeType):
    """Union of multiple shape types."""

    def __init__(self, variants: list[ShapeType]):
        self.variants = variants
        self._resolved = False

    def resolve(self, module):
        if self._resolved:
            return

        for variant in self.variants:
            variant.resolve(module)

        self._resolved = True

    def __repr__(self):
        variant_reprs = " | ".join(repr(v) for v in self.variants)
        status = " (resolved)" if self._resolved else ""
        return f"ShapeUnion({variant_reprs}{status})"


def _build_shape_from_ast(shape_node: comp.ast.Node, mod) -> ShapeType:
    """Convert an AST shape node to a runtime ShapeType.

    Args:
        shape_node: AST node representing a shape (ShapeInline, ShapeRef, etc.)
        mod: The module context for resolving references

    Returns:
        Runtime ShapeType object
    """
    if isinstance(shape_node, comp.ast.ShapeInline):
        return _build_inline_shape(shape_node, mod)
    elif isinstance(shape_node, comp.ast.ShapeRef):
        # Create a shape reference (will be resolved later)
        # Extract the name from tokens (ShapeRef.tokens is a tuple of strings)
        name = shape_node.tokens[0] if shape_node.tokens else ""
        namespace = shape_node.namespace if hasattr(shape_node, "namespace") else None
        return ShapeRef(name, namespace)
    elif isinstance(shape_node, comp.ast.TagRef):
        # Create a tag reference
        # TagRef.tokens is a tuple of strings forming the tag identifier
        tag_name = ".".join(shape_node.tokens)
        return ShapeTagRef(tag_name)
    elif isinstance(shape_node, comp.ast.ShapeUnion):
        # Convert union variants recursively
        variants = [_build_shape_from_ast(variant, mod) for variant in shape_node.kids]
        return ShapeUnion(variants)
    else:
        return _fail(f"Unknown shape AST node type: {type(shape_node)}")


def _build_inline_shape(inline_node: comp.ast.ShapeInline, mod) -> ShapeInline:
    """Convert an AST ShapeInline to runtime ShapeInline with proper field keys.

    Args:
        inline_node: AST ShapeInline node
        mod: The module context

    Returns:
        Runtime ShapeInline with fields keyed by Value or Unnamed
    """
    fields = {}
    unnamed_count = 0

    # Process each field child
    for child in inline_node.kids:
        if isinstance(child, comp.ast.ShapeField):
            # Determine the field key
            if child.name is None:
                # Positional/unnamed field - use Unnamed() as key
                field_key = _value.Unnamed()
                unnamed_count += 1
            else:
                # Named field - use Value(name) as key
                field_key = _value.Value(child.name)

            # Build the shape type for this field (if it has one)
            field_shape = None
            if child.type_ref:
                field_shape = _build_shape_from_ast(child.type_ref, mod)

            # Create the ShapeField
            # The field_key determines how it's stored in the dict
            # The ShapeField.name is also the Value/Unnamed for consistency
            shape_field = ShapeField(field_key, field_shape)

            # Store with proper key type
            fields[field_key] = shape_field
        elif isinstance(child, comp.ast.ShapeSpread):
            # TODO: Handle shape spread (..~othershape)
            pass

    return ShapeInline(fields=fields)


def populate_shape_def_fields(shp_def, ast_node, mod):
    """Populate a ShapeDef's fields from its AST definition.

    Args:
        shp_def: The ShapeDef to populate
        ast_node: The AST ShapeDef node
        mod: The module context
    """
    # The ShapeDef.kids contains the shape fields directly
    # (shape_body just passes through its children)
    if not ast_node.kids:
        return

    # Check if this is a non-structural shape (single TagRef, ShapeRef, etc.)
    if len(ast_node.kids) == 1 and not isinstance(ast_node.kids[0], comp.ast.ShapeField):
        # This is a shape alias or tag constraint, not a structural definition
        # Store the actual shape type for morph to use
        shp_def.shape = _build_shape_from_ast(ast_node.kids[0], mod)
        return

    # The kids are shape fields directly (for braced shapes)
    # Build fields from the AST children
    fields = {}
    for child in ast_node.kids:
        if isinstance(child, comp.ast.ShapeField):
            # Extract field name (or use Unnamed)
            if child.name is None:
                field_key = _value.Unnamed()
            else:
                field_key = _value.Value(child.name)

            # Build the field's shape type
            field_shape = None
            if child.type_ref:
                field_shape = _build_shape_from_ast(child.type_ref, mod)

            # Create ShapeField object with Value/Unnamed as name
            fields[field_key] = ShapeField(name=field_key, shape=field_shape)
        # elif isinstance(child, comp.ast.ShapeSpread):
        #     # TODO: Handle shape spreads
        #     pass

    shp_def.fields.update(fields)



def _fail(msg):
    """Helper to create an operator failure value."""
    from . import builtin
    return _value.Value({
        _value.Unnamed(): builtin.fail_runtime,
        "message": msg,
    })
