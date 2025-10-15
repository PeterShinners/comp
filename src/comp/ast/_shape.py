"""AST nodes for shape definitions and references."""

__all__ = ["ShapeDef", "ShapeFieldDef", "ShapeRef", "ShapeUnion", "BlockShape"]

import comp

from . import _base
from ._tag import ModuleOp


class ShapeDef(ModuleOp):
    """Shape definition: !shape ~path.to.name = {...}

    Defines a structural type with named/positional fields, defaults, and type constraints.
    Shapes use hierarchical paths like tags, with the definition path in normal order.

    Examples:
        !shape ~point = {x ~num y ~num}
        !shape ~geometry.point.2d = {x ~num y ~num}
        !shape ~user = {name ~str email ~str age ~num = 0}
        !shape ~pair = {~num ~num}  # Positional fields

    Args:
        path: Full path as list, e.g., ["geometry", "point", "2d"]
        fields: List of field definitions
    """

    def __init__(self, path: list[str], fields: list['ShapeFieldDef']):
        if not isinstance(path, list):
            raise TypeError("Shape path must be a list")
        if not path:
            raise ValueError("Shape path cannot be empty")
        if not all(isinstance(p, str) for p in path):
            raise TypeError("Shape path must be list of strings")
        if not isinstance(fields, list):
            raise TypeError("Shape fields must be a list")
        if not all(isinstance(f, ShapeFieldDef) for f in fields):
            raise TypeError("All fields must be ShapeFieldDef instances")

        self.path = path
        self.fields = fields

    def evaluate(self, frame):
        """Register this shape in the module.

        1. Get module from module scope
        2. Evaluate field definitions (expanding spreads)
        3. Register shape in module
        """
        # Get module from scope
        module = frame.scope('module')
        if module is None:
            return comp.fail("ShapeDef requires module scope")

        # Process field definitions, expanding spreads
        shape_fields = []
        for field_def in self.fields:
            # Check if this is a spread field
            if field_def.is_spread:
                # Evaluate the shape reference to get the shape to spread
                if field_def.shape_ref is None:
                    return comp.fail("Spread field must have shape reference")

                spread_shape = yield comp.Compute(field_def.shape_ref)
                if frame.is_fail(spread_shape):
                    return spread_shape

                # Add all fields from the spread shape
                # NOTE: spread_shape should be a ShapeDefinition
                if hasattr(spread_shape, 'fields'):
                    shape_fields.extend(spread_shape.fields)
                else:
                    return comp.fail(f"Cannot spread non-shape: {spread_shape}")
            else:
                # Regular field - evaluate it
                field = yield comp.Compute(field_def)
                if frame.is_fail(field):
                    return field
                shape_fields.append(field)

        # Register shape
        module.define_shape(self.path, shape_fields)

        return comp.Value(True)

    def unparse(self) -> str:
        """Convert back to source code."""
        fields_str = " ".join(f.unparse() for f in self.fields)
        path_str = ".".join(self.path)
        return f"!shape ~{path_str} = {{{fields_str}}}"

    def __repr__(self):
        path_str = ".".join(self.path)
        return f"ShapeDef(~{path_str}, {len(self.fields)} fields)"


class ShapeFieldDef(_base.AstNode):
    """Field definition within a shape.

    Examples:
        x ~num              # Named field, required
        x ~num = 0          # Named field with default
        ~num                # Positional field
        ..~other-shape      # Spread another shape
        items ~str[]        # Array field
        items ~str[1-5]     # Array with constraints

    Args:
        name: Optional field name (None for positional)
        shape_ref: Shape/type constraint (ShapeRef, tag ref, etc.)
        default: Optional default value expression
        is_spread: True for spread fields (..~shape)
        is_array: True if field is an array
        array_min: Minimum array length
        array_max: Maximum array length
    """

    def __init__(self, name: str | None = None, shape_ref: _base.AstNode | None = None,
                 default: _base.ValueNode | None = None, is_spread: bool = False,
                 is_array: bool = False, array_min: int | None = None,
                 array_max: int | None = None):
        if name is not None and not isinstance(name, str):
            raise TypeError("Field name must be string or None")
        if shape_ref is not None and not isinstance(shape_ref, _base.AstNode):
            raise TypeError("Shape ref must be AstNode or None")
        if default is not None and not isinstance(default, _base.ValueNode):
            raise TypeError("Default must be ValueNode or None")
        if is_spread and (name is not None or default is not None):
            raise ValueError("Spread fields cannot have names or defaults")

        self.name = name
        self.shape_ref = shape_ref
        self.default = default
        self.is_spread = is_spread
        self.is_array = is_array
        self.array_min = array_min
        self.array_max = array_max

    def evaluate(self, frame):
        """Evaluate field definition to create ShapeField.

        NOTE: Spread fields (is_spread=True) should NOT be evaluated this way.
        They are handled directly by ShapeDef.evaluate() which expands them.

        Returns a ShapeField object (not a Value - these are intermediate structures).
        """
        if self.is_spread:
            # Spread fields should be handled by ShapeDef, not evaluated directly
            return comp.fail("Spread fields cannot be evaluated directly")

        # Evaluate shape reference if present
        shape = None
        if self.shape_ref is not None:
            shape = yield comp.Compute(self.shape_ref)
            if frame.is_fail(shape):
                return shape

        # Evaluate default value if present
        default_val = None
        if self.default is not None:
            default_val = yield comp.Compute(self.default)
            if frame.is_fail(default_val):
                return default_val

        # Create _module.ShapeField - this is NOT a Value, it's a _module.ShapeField object
        # NOTE: No is_spread parameter - spreads are expanded at definition time
        field = comp.ShapeField(
            name=self.name,
            shape=shape,
            default=default_val,
            is_array=self.is_array,
            array_min=self.array_min,
            array_max=self.array_max
        )

        # HACK: Return ShapeField directly - ShapeDef expects this
        # This breaks the evaluate() contract but works for now
        return field
        yield  # Make this a generator

    def unparse(self) -> str:
        """Convert back to source code."""
        if self.is_spread:
            return f"..{self.shape_ref.unparse() if self.shape_ref else ''}"

        parts = []
        if self.name:
            parts.append(self.name)

        if self.shape_ref:
            parts.append(self.shape_ref.unparse())

        array_str = ""
        if self.is_array:
            if self.array_min is not None or self.array_max is not None:
                min_str = str(self.array_min) if self.array_min is not None else ""
                max_str = str(self.array_max) if self.array_max is not None else ""
                array_str = f"[{min_str}-{max_str}]"
            else:
                array_str = "[]"

        if self.default:
            parts.append("=")
            parts.append(self.default.unparse())

        return " ".join(parts) + array_str

    def __repr__(self):
        if self.is_spread:
            return f"..{self.shape_ref}"
        name_part = f"{self.name} " if self.name else ""
        return f"ShapeFieldDef({name_part}{self.shape_ref})"


class ShapeRef(_base.ShapeNode):
    """Shape reference: ~path.to.shape or ~path.to.shape/namespace

    References a defined shape for use in field types, morphing, etc.
    References use reversed paths (leaf first) like tags, e.g., ~2d.point.geometry

    Examples:
        ~point          # Reference to shape (single element path)
        ~2d.point       # Reference with reversed path (leaf first)
        ~user           # Reference in field type
        ~point/geometry # Reference from geometry namespace
        data ~point     # Morph operation

    Args:
        path: Reversed partial path (leaf first), e.g., ["2d", "point"]
        namespace: Optional namespace for cross-module references

    Attributes:
        _resolved: Pre-resolved ShapeDefinition (set by Module.prepare())
    """

    def __init__(self, path: list[str], namespace: str | None = None):
        if not isinstance(path, list):
            raise TypeError("Shape path must be a list")
        if not path:
            raise ValueError("Shape path cannot be empty")
        if not all(isinstance(p, str) for p in path):
            raise TypeError("Shape path must be list of strings")
        if namespace is not None and not isinstance(namespace, str):
            raise TypeError("Shape namespace must be string or None")

        self.path = path
        self.namespace = namespace
        self._resolved = None  # Pre-resolved definition (set by Module.prepare())

    def evaluate(self, frame):
        """Look up shape in module.

        Returns the ShapeDefinition object (not a Value).

        Uses pre-resolved definition if available (from Module.prepare()),
        otherwise falls back to runtime lookup.

        If namespace is provided (/namespace), searches only in that namespace.
        Otherwise, searches local module first, then all imported namespaces.
        """
        # Fast path: use pre-resolved definition if available
        if self._resolved is not None:
            return self._resolved
            yield  # Unreachable but makes this a generator

        # Slow path: runtime lookup (for modules not prepared)
        # Get module from scope
        module = frame.scope('module')
        if module is None:
            return comp.fail("Shape references require module scope")

        # Look up shape with namespace support
        try:
            shape_def = module.lookup_shape_with_namespace(self.path, self.namespace)
        except ValueError as e:
            # Ambiguous reference
            return comp.fail(str(e))

        if shape_def is None:
            path_str = ".".join(reversed(self.path))
            if self.namespace:
                return comp.fail(f"Shape not found: ~{path_str}/{self.namespace}")
            return comp.fail(f"Shape not found: ~{path_str}")

        # HACK: Return ShapeDefinition directly
        # This breaks evaluate() contract but matches our usage
        return shape_def
        yield  # Unreachable but makes this a generator

    def unparse(self) -> str:
        """Convert back to source code."""
        path_str = ".".join(reversed(self.path))
        ref = f"~{path_str}"
        if self.namespace:
            ref += "/" + self.namespace
        return ref

    def __repr__(self):
        path_str = ".".join(reversed(self.path))
        if self.namespace:
            return f"ShapeRef(~{path_str}/{self.namespace})"
        return f"ShapeRef(~{path_str})"


class ShapeUnion(_base.ShapeNode):
    """Shape union: ~shape1 | ~shape2 | ~shape3

    Represents a union of multiple shapes for morphing operations.
    During morphing, tries each shape and uses specificity ranking to pick best match.

    Examples:
        ~success | ~error
        ~user | ~admin | ~guest
        data ~(~user | ~admin)

    Args:
        members: List of shape references
    """

    def __init__(self, members: list[_base.ShapeNode]):
        if not isinstance(members, list):
            raise TypeError("Union members must be a list")
        if len(members) < 2:
            raise ValueError("Union must have at least 2 members")
        if not all(isinstance(m, _base.ShapeNode) for m in members):
            raise TypeError("All members must be ShapeNode instances")

        self.members = members

    def evaluate(self, frame):
        """Evaluate union by resolving all member shapes.

        Returns a special union marker structure.
        """
        # Resolve all member shapes
        resolved = []
        for member in self.members:
            shape = yield comp.Compute(member)
            if frame.is_fail(shape):
                return shape
            resolved.append(shape)

        # HACK: Return a marker structure indicating this is a union
        # The morphing system will need to handle this specially
        return {"__union__": resolved}
        yield  # Make this a generator

    def unparse(self) -> str:
        """Convert back to source code."""
        return " | ".join(m.unparse() for m in self.members)

    def __repr__(self):
        return f"ShapeUnion({len(self.members)} members)"


class BlockShape(_base.ShapeNode):
    """Block type shape: ~:{input-shape}

    Represents the type of a block (deferred computation) with a specified input shape.
    The shape describes the structure that must be provided when the block is invoked.

    Examples:
        ~:{~str ~str}        # Block accepting two positional strings
        ~:{x ~num y ~num}    # Block accepting named fields x and y
        op ~:{~str ~str}     # Field of block type

    Args:
        fields: List of field definitions describing the input shape

    Note:
        BlockShape is used in shape definitions to declare block-typed fields.
        At runtime, ephemeral blocks (:{...}) are morphed with a BlockShape to create
        typed blocks (BlockValue) that can be invoked with the |: operator.
    """

    def __init__(self, fields: list['ShapeFieldDef']):
        if not isinstance(fields, list):
            raise TypeError("Block shape fields must be a list")
        if not all(isinstance(f, ShapeFieldDef) for f in fields):
            raise TypeError("All fields must be ShapeFieldDef instances")

        self.fields = fields

    def evaluate(self, frame):
        """Evaluate block shape to create a block type descriptor.

        Returns a BlockShapeDefinition entity (not wrapped in Value).
        This is used during morphing to type raw blocks.
        """
        # Process field definitions, similar to ShapeDef
        shape_fields = []
        for field_def in self.fields:
            if field_def.is_spread:
                # Handle spread fields
                if field_def.shape_ref is None:
                    return comp.fail("Spread field must have shape reference")

                spread_shape = yield comp.Compute(field_def.shape_ref)
                if frame.is_fail(spread_shape):
                    return spread_shape

                if hasattr(spread_shape, 'fields'):
                    shape_fields.extend(spread_shape.fields)
                else:
                    return comp.fail(f"Cannot spread non-shape: {spread_shape}")
            else:
                # Regular field - evaluate it
                field = yield comp.Compute(field_def)
                if frame.is_fail(field):
                    return field
                shape_fields.append(field)

        # Create and return BlockShapeDefinition entity (unwrapped, like ShapeRef does)
        block_shape_def = comp.BlockShapeDefinition(shape_fields)
        return block_shape_def
        yield  # Make this a generator

    def unparse(self) -> str:
        """Convert back to source code."""
        fields_str = " ".join(f.unparse() for f in self.fields)
        return f"~:{{{fields_str}}}"

    def __repr__(self):
        return f"BlockShape({len(self.fields)} fields)"
