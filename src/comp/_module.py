"""Module system for the engine - tracks definitions and provides namespaces."""

__all__ = ["Module", "TagDefinition", "ShapeDefinition", "ShapeField", "FunctionDefinition", "RawBlock", "Block", "BlockShapeDefinition"]

from dataclasses import dataclass
from typing import Any

from ._entity import Entity


class ShapeField(Entity):
    """A single field in a shape definition.

    Inherits from Entity so it can be returned from evaluate() and passed through scopes.

    NOTE: Runtime ShapeField objects should NOT have spreads - those are expanded during
    shape definition. Only the AST nodes (ShapeFieldDef) should handle spreads.

    Attributes:
        name: Optional field name (None for positional fields)
        shape: Type constraint for this field (can be ShapeDefinition, tag, primitive type reference)
        default: Optional default value (None means field is required)
        is_array: True if field accepts multiple values ([])
        array_min: Minimum array length (None for no minimum)
        array_max: Maximum array length (None for no maximum)
    """
    def __init__(self, name: str | None = None, shape: Any = None, default: Any = None,
                 is_array: bool = False, array_min: int | None = None,
                 array_max: int | None = None):
        self.name = name
        self.shape = shape
        self.default = default
        self.is_array = is_array
        self.array_min = array_min
        self.array_max = array_max

    @property
    def is_named(self) -> bool:
        """Check if this is a named field."""
        return self.name is not None

    @property
    def is_positional(self) -> bool:
        """Check if this is a positional field."""
        return self.name is None

    @property
    def is_required(self) -> bool:
        """Check if this field is required (no default value)."""
        return self.default is None

    def __repr__(self):
        name_part = f'"{self.name}": ' if self.name else ""
        shape_part = f"ShapeRef(~{self.shape} (unresolved))" if self.shape else "Any"
        array_part = "[]" if self.is_array else ""
        return f"ShapeField({name_part}{shape_part}){array_part}"


@dataclass
class TagDefinition:
    """A single tag definition in the module.

    Attributes:
        path: Full path as list, e.g., ["status", "error", "timeout"]
        value: Optional value for this tag (can be any Value)
    """
    path: list[str]
    value: Any = None  # Will be engine.Value when evaluated

    @property
    def name(self) -> str:
        """Get the tag's leaf name (last element of path)."""
        return self.path[-1] if self.path else ""

    @property
    def full_name(self) -> str:
        """Get dot-separated full path."""
        return ".".join(self.path)

    @property
    def parent_path(self) -> list[str] | None:
        """Get the parent's path, or None for root tags."""
        return self.path[:-1] if len(self.path) > 1 else None

    def matches_partial(self, partial: list[str]) -> bool:
        """Check if this tag matches a partial path (suffix match).

        Args:
            partial: Reversed partial path, e.g., ["timeout", "error"]
                    for #timeout.error (leaf first)

        Returns:
            True if tag's path ends with the partial path
        """
        if len(partial) > len(self.path):
            return False
        # Match from the end of our path (which is already in definition order)
        # partial is in reference order (reversed), so we need to reverse it
        partial_def_order = list(reversed(partial))
        return self.path[-len(partial):] == partial_def_order


class ShapeDefinition(Entity):
    """A shape definition in the module.

    Shapes describe structure types with field names, types, and defaults.
    They are used for morphing operations and type validation.

    Inherits from Entity so it can be returned from evaluate() and passed through scopes.

    Attributes:
        path: Full path as list, e.g., ["geometry", "point", "2d"]
        fields: List of field definitions
        is_union: True if this is a union shape (combines multiple shapes)
        union_members: List of shape references for union shapes
    """
    def __init__(self, path: list[str], fields: list[ShapeField],
                 is_union: bool = False, union_members: list[Any] | None = None):
        self.path = path
        self.fields = fields
        self.is_union = is_union
        self.union_members = union_members or []

    @property
    def name(self) -> str:
        """Get the shape's leaf name (last element of path)."""
        return self.path[-1] if self.path else ""

    @property
    def full_name(self) -> str:
        """Get dot-separated full path."""
        return ".".join(self.path)

    @property
    def parent_path(self) -> list[str] | None:
        """Get the parent's path, or None for root shapes."""
        return self.path[:-1] if len(self.path) > 1 else None

    def matches_partial(self, partial: list[str]) -> bool:
        """Check if this shape matches a partial path (suffix match).

        Args:
            partial: Reversed partial path, e.g., ["2d", "point"]
                    for ~2d.point (leaf first)

        Returns:
            True if shape's path ends with the partial path
        """
        if len(partial) > len(self.path):
            return False
        # Match from the end of our path (which is already in definition order)
        # partial is in reference order (reversed), so we need to reverse it
        partial_def_order = list(reversed(partial))
        return self.path[-len(partial):] == partial_def_order

    @property
    def named_fields(self) -> list[ShapeField]:
        """Get all named fields."""
        return [f for f in self.fields if f.is_named]

    @property
    def positional_fields(self) -> list[ShapeField]:
        """Get all positional fields."""
        return [f for f in self.fields if f.is_positional]

    @property
    def required_fields(self) -> list[ShapeField]:
        """Get all required fields (no defaults)."""
        return [f for f in self.fields if f.is_required]

    def __repr__(self):
        if self.is_union and self.union_members:
            members = " | ".join(str(m) for m in self.union_members)
            return f"~{self.full_name} = {members}"

        # Show fields as dict-like for named, list-like for positional
        field_strs = []
        for f in self.fields:
            if f.is_named:
                field_strs.append(f'"{f.name}": {f.shape}')
            else:
                field_strs.append(str(f.shape))

        resolved = "resolved" if self.fields else "unresolved"
        return f"ShapeDef(~{self.full_name}, {len(self.fields)} fields ({resolved}))"


class FunctionDefinition(Entity):
    """A function definition in the module.

    Functions transform input structures through pipelines and can accept arguments.
    They are lazy by default and support overloading through shape-based dispatch.

    Inherits from Entity so it can be returned from evaluate() and passed through scopes.

    Attributes:
        path: Full path as list, e.g., ["math", "geometry", "area"]
        input_shape: Shape defining expected input structure (or None for any)
        arg_shape: Shape defining function arguments (or None for no args)
        body: Structure definition AST node for the function body
        is_pure: True if function has no side effects
        doc: Optional documentation string
        impl_doc: Optional documentation for this specific implementation (overloads)
    """
    def __init__(self, path: list[str], body: Any, input_shape: Any = None,
                 arg_shape: Any = None, is_pure: bool = False,
                 doc: str | None = None, impl_doc: str | None = None):
        self.path = path
        self.input_shape = input_shape
        self.arg_shape = arg_shape
        self.body = body
        self.is_pure = is_pure
        self.doc = doc
        self.impl_doc = impl_doc

    @property
    def name(self) -> str:
        """Get the function's leaf name (last element of path)."""
        return self.path[-1] if self.path else ""

    @property
    def full_name(self) -> str:
        """Get dot-separated full path."""
        return ".".join(self.path)

    @property
    def parent_path(self) -> list[str] | None:
        """Get the parent's path, or None for root functions."""
        return self.path[:-1] if len(self.path) > 1 else None

    def matches_partial(self, partial: list[str]) -> bool:
        """Check if this function matches a partial path (suffix match).

        Args:
            partial: Reversed partial path, e.g., ["area", "geometry"]
                    for |area.geometry (leaf first)

        Returns:
            True if function's path ends with the partial path
        """
        if len(partial) > len(self.path):
            return False
        # Match from the end of our path (which is already in definition order)
        # partial is in reference order (reversed), so we need to reverse it
        partial_def_order = list(reversed(partial))
        return self.path[-len(partial):] == partial_def_order

    def __repr__(self):
        pure_str = "!pure " if self.is_pure else ""
        input_str = f" ~{self.input_shape}" if self.input_shape else ""
        arg_str = f" ^{self.arg_shape}" if self.arg_shape else ""
        return f"{pure_str}|{self.full_name}{input_str}{arg_str}"


class RawBlock(Entity):
    """An untyped block with captured definition context.

    Raw blocks are created with :{...} syntax and capture their definition context
    (scopes and module references) but have no input shape yet. They cannot be invoked
    until morphed with a BlockShape to create a Block.

    Raw blocks capture only what they need:
    - module: For looking up tags, shapes, and functions
    - function: Current function context (if defined in a function), for $arg access
    - ctx_scope: The $ctx scope at definition time
    - local_scope: The @local scope at definition time
    - block_ast: The Block AST node itself (operations to execute)

    Raw blocks do NOT capture:
    - $in: Set at invocation time
    - $out: Built during block execution
    - Full frame: Too heavy, only need specific scopes

    Attributes:
        block_ast: The Block AST node with operations
        module: Module reference for lookups
        function: FunctionDefinition if defined in function, None otherwise
        ctx_scope: Captured $ctx scope from definition
        local_scope: Captured @local scope from definition
    """
    def __init__(self, block_ast: Any, module: 'Module',
                 function: FunctionDefinition | None = None,
                 ctx_scope: Any = None, local_scope: Any = None):
        self.block_ast = block_ast
        self.module = module
        self.function = function
        self.ctx_scope = ctx_scope
        self.local_scope = local_scope

    def __repr__(self):
        func_str = f" in |{self.function.full_name}" if self.function else ""
        return f"RawBlock({len(self.block_ast.ops)} ops{func_str})"


class Block(Entity):
    """A typed block ready for invocation.

    Blocks are created by morphing a RawBlock with a BlockShape. They have:
    - An input shape that defines what structure they expect
    - All the captured context from the RawBlock
    - The ability to be invoked with the |: operator

    The Block holds a reference to the original RawBlock (for context and operations)
    plus the input shape that was applied through morphing.

    Attributes:
        raw_block: The RawBlock this was created from (contains ops and captured context)
        input_shape: The shape defining expected input structure
    """
    def __init__(self, raw_block: RawBlock, input_shape: Any):
        if not isinstance(raw_block, RawBlock):
            raise TypeError("Block requires a RawBlock")
        self.raw_block = raw_block
        self.input_shape = input_shape

    @property
    def block_ast(self):
        """Get the Block AST node from the raw block."""
        return self.raw_block.block_ast

    @property
    def module(self):
        """Get the module from the raw block."""
        return self.raw_block.module

    @property
    def function(self):
        """Get the function context from the raw block."""
        return self.raw_block.function

    @property
    def ctx_scope(self):
        """Get the captured $ctx scope from the raw block."""
        return self.raw_block.ctx_scope

    @property
    def local_scope(self):
        """Get the captured @local scope from the raw block."""
        return self.raw_block.local_scope

    def __repr__(self):
        func_str = f" in |{self.function.full_name}" if self.function else ""
        shape_str = f" ~:{self.input_shape}" if self.input_shape else ""
        return f"Block({len(self.block_ast.ops)} ops{shape_str}{func_str})"


class BlockShapeDefinition(Entity):
    """A block shape definition describing the input structure for blocks.

    BlockShapeDefinitions are created when BlockShape AST nodes are evaluated.
    They describe what input structure a block expects, similar to how
    ShapeDefinition describes struct layouts.

    Unlike regular shapes, BlockShapeDefinitions are specifically for block types
    and are used during morphing to convert RawBlock → Block.

    Attributes:
        fields: List of ShapeField describing the expected input structure
    """
    def __init__(self, fields: list[ShapeField]):
        if not isinstance(fields, list):
            raise TypeError("Fields must be a list")
        if not all(isinstance(f, ShapeField) for f in fields):
            raise TypeError("All fields must be ShapeField instances")
        self.fields = fields

    def __repr__(self):
        return f"BlockShapeDefinition({len(self.fields)} fields)"


class Module(Entity):
    """Runtime module containing tag definitions and other module-level entities.

    This tracks all definitions made at module scope and provides lookup
    mechanisms for resolving references.

    Inherits from Entity, making it passable through scopes and returnable
    from evaluate() methods (though modules are not valid runtime values).

    Every module (except builtin itself) automatically has a 'builtin' namespace
    reference, providing access to core tags (#true, #false, #fail, etc),
    primitive shapes (~num, ~str, etc), and core functions (|print, |double, etc).

    Attributes:
        tags: Flat dictionary of full_path -> TagDefinition
        shapes: Dictionary of shape_name -> ShapeDefinition
        functions: Dictionary of func_name -> list[FunctionDefinition] (for overloads)
        namespaces: Dictionary of namespace_name -> Module (imported modules)
        package_info: Optional package metadata
        is_builtin: True if this is the builtin module (to avoid circular namespace refs)
    """

    def __init__(self, is_builtin: bool = False):
        self.tags: dict[str, TagDefinition] = {}  # full_path_str -> TagDefinition
        self.shapes: dict[str, ShapeDefinition] = {}  # full_path_str -> ShapeDefinition
        self.functions: dict[str, list[FunctionDefinition]] = {}  # full_path_str -> list of overloads
        self.namespaces: dict[str, Module] = {}  # namespace -> imported Module
        self.package_info: dict[str, Any] = {}
        self.is_builtin = is_builtin

        # Module scope storage for $mod namespace
        # This is a Value with a struct containing module-level state
        from ._value import Value
        self.scope = Value(None)  # Empty struct initially
        if self.scope.struct is None:
            self.scope.struct = {}

        # Add builtin namespace to all non-builtin modules
        if not is_builtin:
            # Import happens lazily to avoid circular dependency
            from ._builtin import get_builtin_module
            self.namespaces['builtin'] = get_builtin_module()

    def define_tag(self, path: list[str], value: Any = None) -> TagDefinition:
        """Register a tag definition.

        Args:
            path: Full path in definition order, e.g., ["status", "error", "timeout"]
            value: Optional value for this tag

        Returns:
            The TagDefinition object

        Notes:
            - Multiple definitions of the same tag merge (last value wins)
            - Children can be added to existing tags
        """
        full_name = ".".join(path)

        if full_name in self.tags:
            # Tag already exists - update its value if provided
            tag_def = self.tags[full_name]
            if value is not None:
                tag_def.value = value
        else:
            # Create new tag definition
            tag_def = TagDefinition(path=path, value=value)
            self.tags[full_name] = tag_def

        return tag_def

    def lookup_tag(self, partial_path: list[str]) -> TagDefinition | None:
        """Find tag by partial path (suffix matching).

        Args:
            partial_path: Reversed partial path (leaf first),
                         e.g., ["timeout", "error"] for #timeout.error

        Returns:
            TagDefinition if unique match found, None if not found

        Raises:
            ValueError: If partial path matches multiple tags (ambiguous)
        """
        matches = [
            tag_def for tag_def in self.tags.values()
            if tag_def.matches_partial(partial_path)
        ]

        if len(matches) == 0:
            return None
        elif len(matches) == 1:
            return matches[0]
        else:
            # Ambiguous - multiple matches
            match_names = [t.full_name for t in matches]
            partial_str = ".".join(reversed(partial_path))
            raise ValueError(
                f"Ambiguous tag reference #{partial_str} matches: "
                f"{', '.join('#' + n for n in match_names)}"
            )

    def get_tag_by_full_path(self, path: list[str]) -> TagDefinition | None:
        """Get tag by exact full path.

        Args:
            path: Full path in definition order, e.g., ["status", "error", "timeout"]

        Returns:
            TagDefinition if found, None otherwise
        """
        full_name = ".".join(path)
        return self.tags.get(full_name)

    def list_tags(self) -> list[TagDefinition]:
        """Get all tag definitions in the module."""
        return list(self.tags.values())

    def define_shape(self, path: list[str], fields: list[ShapeField],
                     is_union: bool = False, union_members: list[Any] | None = None) -> ShapeDefinition:
        """Register a shape definition.

        Args:
            path: Full path in definition order, e.g., ["geometry", "point", "2d"]
            fields: List of field definitions
            is_union: True if this is a union shape
            union_members: List of shape refs for union shapes

        Returns:
            The ShapeDefinition object

        Notes:
            - If shape already exists (from prepare()), updates it in place
            - Otherwise creates a new ShapeDefinition
        """
        full_name = ".".join(path)
        
        # Check if shape already exists (from prepare())
        existing = self.shapes.get(full_name)
        if existing is not None:
            # Update existing shape in place so references remain valid
            existing.fields = fields
            existing.is_union = is_union
            existing.union_members = union_members or []
            return existing
        else:
            # Create new shape definition
            shape_def = ShapeDefinition(
                path=path,
                fields=fields,
                is_union=is_union,
                union_members=union_members or []
            )
            self.shapes[full_name] = shape_def
            return shape_def

    def lookup_shape(self, partial_path: list[str]) -> ShapeDefinition | None:
        """Find shape by partial path (suffix matching).

        Args:
            partial_path: Reversed partial path (leaf first),
                         e.g., ["2d", "point"] for ~2d.point

        Returns:
            ShapeDefinition if unique match found, None if not found

        Raises:
            ValueError: If partial path matches multiple shapes (ambiguous)
        """
        matches = [
            shape_def for shape_def in self.shapes.values()
            if shape_def.matches_partial(partial_path)
        ]

        if len(matches) == 0:
            return None
        elif len(matches) == 1:
            return matches[0]
        else:
            # Ambiguous - multiple matches
            match_names = [s.full_name for s in matches]
            partial_str = ".".join(reversed(partial_path))
            raise ValueError(
                f"Ambiguous shape reference ~{partial_str} matches: "
                f"{', '.join('~' + n for n in match_names)}"
            )

    def list_shapes(self) -> list[ShapeDefinition]:
        """Get all shape definitions in the module."""
        return list(self.shapes.values())

    def define_function(self, path: list[str], body: Any, input_shape: Any = None,
                       arg_shape: Any = None, is_pure: bool = False,
                       doc: str | None = None, impl_doc: str | None = None) -> FunctionDefinition:
        """Register a function definition.

        Supports overloading - multiple definitions with the same path.
        Functions are matched by input shape specificity at call time.

        Args:
            path: Full path in definition order, e.g., ["math", "geometry", "area"]
            body: Structure definition AST for function body
            input_shape: Shape for input structure (None for any)
            arg_shape: Shape for arguments (None for no args)
            is_pure: True if function has no side effects
            doc: Documentation string (shared across overloads)
            impl_doc: Documentation for this specific implementation

        Returns:
            The FunctionDefinition object

        Notes:
            - Multiple definitions create overloads
            - Specificity matching determines which implementation runs
        """
        full_name = ".".join(path)
        func_def = FunctionDefinition(
            path=path,
            body=body,
            input_shape=input_shape,
            arg_shape=arg_shape,
            is_pure=is_pure,
            doc=doc,
            impl_doc=impl_doc
        )

        # Add to overload list
        if full_name not in self.functions:
            self.functions[full_name] = []
        self.functions[full_name].append(func_def)

        return func_def

    def lookup_function(self, partial_path: list[str]) -> list[FunctionDefinition] | None:
        """Find function by partial path (suffix matching), returning all overloads.

        Args:
            partial_path: Reversed partial path (leaf first),
                         e.g., ["area", "geometry"] for |area.geometry

        Returns:
            List of FunctionDefinition overloads, or None if not found

        Raises:
            ValueError: If partial path matches multiple functions (ambiguous)
        """
        matches = []
        for _full_name, overloads in self.functions.items():
            # Check if any overload matches
            if overloads and overloads[0].matches_partial(partial_path):
                matches.append(overloads)

        if len(matches) == 0:
            return None
        elif len(matches) == 1:
            return matches[0]
        else:
            # Ambiguous - multiple matches
            match_names = [funcs[0].full_name for funcs in matches]
            partial_str = ".".join(reversed(partial_path))
            raise ValueError(
                f"Ambiguous function reference |{partial_str} matches: "
                f"{', '.join('|' + n for n in match_names)}"
            )

    def list_functions(self) -> list[FunctionDefinition]:
        """Get all function definitions (all overloads flattened)."""
        result = []
        for overloads in self.functions.values():
            result.extend(overloads)
        return result

    def add_namespace(self, name: str, module: 'Module') -> None:
        """Add an imported module to this module's namespace.

        Args:
            name: Namespace identifier (used in /namespace references)
            module: The imported Module to reference

        Notes:
            - Used to implement imports
            - References can use /namespace to explicitly look in that module
            - Without namespace, lookups check local module then all namespaces
        """
        self.namespaces[name] = module

    def lookup_tag_with_namespace(self, partial_path: list[str],
                                   namespace: str | None = None) -> TagDefinition | None:
        """Find tag by partial path, optionally in a specific namespace.

        Args:
            partial_path: Reversed partial path (leaf first)
            namespace: Optional namespace to search in (e.g., "std" for /std)

        Returns:
            TagDefinition if unique match found, None if not found

        Raises:
            ValueError: If partial path matches multiple tags (ambiguous)

        Notes:
            - If namespace is provided, searches only that namespace
            - If namespace is None, searches local module first, then all namespaces
        """
        if namespace is not None:
            # Explicit namespace - look only there
            ns_module = self.namespaces.get(namespace)
            if ns_module is None:
                return None
            return ns_module.lookup_tag(partial_path)

        # No namespace - check local first
        local_result = self.lookup_tag(partial_path)
        if local_result is not None:
            return local_result

        # Not found locally - check all namespaces
        # TODO: This is a simple linear search; will be optimized in two-pass bake
        found_results = []
        found_namespaces = []

        for ns_name, ns_module in self.namespaces.items():
            try:
                result = ns_module.lookup_tag(partial_path)
                if result is not None:
                    found_results.append(result)
                    found_namespaces.append(ns_name)
            except ValueError:
                # Ambiguous in that namespace - skip it
                continue

        if len(found_results) == 0:
            return None
        elif len(found_results) == 1:
            return found_results[0]
        else:
            # Found in multiple namespaces - ambiguous
            partial_str = ".".join(reversed(partial_path))
            ns_list = ", ".join(f"/{ns}" for ns in found_namespaces)
            raise ValueError(
                f"Ambiguous tag reference #{partial_str} found in multiple namespaces: {ns_list}"
            )

    def lookup_shape_with_namespace(self, partial_path: list[str],
                                     namespace: str | None = None) -> ShapeDefinition | None:
        """Find shape by partial path, optionally in a specific namespace.

        Args:
            partial_path: Reversed partial path (leaf first)
            namespace: Optional namespace to search in

        Returns:
            ShapeDefinition if found, None otherwise

        Raises:
            ValueError: If partial path matches multiple shapes (ambiguous)

        Notes:
            - If namespace is provided, searches only that namespace
            - If namespace is None, searches local module first, then all namespaces
        """
        if namespace is not None:
            # Explicit namespace - look only there
            ns_module = self.namespaces.get(namespace)
            if ns_module is None:
                return None
            return ns_module.lookup_shape(partial_path)

        # No namespace - check local first
        try:
            local_result = self.lookup_shape(partial_path)
            if local_result is not None:
                return local_result
        except ValueError:
            # Ambiguous in local - propagate the error
            raise

        # Not found locally - check all namespaces
        found_results = []
        found_namespaces = []

        for ns_name, ns_module in self.namespaces.items():
            try:
                result = ns_module.lookup_shape(partial_path)
                if result is not None:
                    found_results.append(result)
                    found_namespaces.append(ns_name)
            except ValueError:
                # Ambiguous in that namespace - skip it
                continue

        if len(found_results) == 0:
            return None
        elif len(found_results) == 1:
            return found_results[0]
        else:
            # Found in multiple namespaces - ambiguous
            partial_str = ".".join(reversed(partial_path))
            ns_list = ", ".join(f"/{ns}" for ns in found_namespaces)
            raise ValueError(
                f"Ambiguous shape reference ~{partial_str} found in multiple namespaces: {ns_list}"
            )

    def lookup_function_with_namespace(self, partial_path: list[str],
                                        namespace: str | None = None) -> list[FunctionDefinition] | None:
        """Find function by partial path, optionally in a specific namespace.

        Args:
            partial_path: Reversed partial path (leaf first)
            namespace: Optional namespace to search in

        Returns:
            List of FunctionDefinition overloads, or None if not found

        Raises:
            ValueError: If partial path matches multiple functions (ambiguous)

        Notes:
            - If namespace is provided, searches only that namespace
            - If namespace is None, searches local module first, then all namespaces
        """
        if namespace is not None:
            # Explicit namespace - look only there
            ns_module = self.namespaces.get(namespace)
            if ns_module is None:
                return None
            return ns_module.lookup_function(partial_path)

        # No namespace - check local first
        try:
            local_result = self.lookup_function(partial_path)
            if local_result is not None:
                return local_result
        except ValueError:
            # Ambiguous in local - propagate the error
            raise

        # Not found locally - check all namespaces
        found_results = []
        found_namespaces = []

        for ns_name, ns_module in self.namespaces.items():
            try:
                result = ns_module.lookup_function(partial_path)
                if result is not None:
                    found_results.append(result)
                    found_namespaces.append(ns_name)
            except ValueError:
                # Ambiguous in that namespace - skip it
                continue

        if len(found_results) == 0:
            return None
        elif len(found_results) == 1:
            return found_results[0]
        else:
            # Found in multiple namespaces - ambiguous
            partial_str = ".".join(reversed(partial_path))
            ns_list = ", ".join(f"/{ns}" for ns in found_namespaces)
            raise ValueError(
                f"Ambiguous function reference |{partial_str} found in multiple namespaces: {ns_list}"
            )

    def prepare(self, ast_module: Any, engine: Any = None) -> None:
        """Prepare the module by building its namespace and pre-resolving all references.

        This is a multi-phase process that builds up the module incrementally and
        ensures all references can be resolved at build time, making undefined lookups
        into build-time errors rather than runtime errors.

        The process:
        1. Walk all definitions in the AST and create initial Def nodes
        2. Walk all imports and recursively prepare() each imported module
        3. Build complete resolution namespace (all partial name hierarchies)
        4. Mark any ambiguous definitions
        5. Walk all AST nodes and pre-resolve all references
        6. Optionally discard the resolution namespace (no longer needed)

        Args:
            ast_module: The AST Module node containing all definitions
            engine: Optional Engine instance for evaluation (defaults to current)

        Raises:
            ValueError: If there are unresolved references or ambiguous definitions
        """
        if engine is None:
            from ._engine import Engine
            engine = Engine()

        # Phase 1: Create initial definitions from AST
        # This registers all tags, shapes, and functions in the module
        self._phase1_create_definitions(ast_module, engine)

        # Phase 2: Process imports recursively
        # Each imported module will also be prepared
        self._phase2_prepare_imports(ast_module, engine)

        # Phase 3: Build complete resolution namespace
        # This creates a lookup table for all possible partial references
        resolution_ns = self._phase3_build_resolution_namespace()

        # Phase 4: Walk AST nodes and pre-resolve all references
        self._phase4_preresolve_references(ast_module, resolution_ns)

        # Phase 5: Mark the module as prepared
        self._prepared = True

        # Note: We keep resolution_ns for now - it may be useful for debugging
        # In the future, step 6 could discard it to save memory
        self._resolution_ns = resolution_ns

    def _phase1_create_definitions(self, ast_module: Any, engine: Any) -> None:
        """Phase 1: Walk all definitions and create initial Def nodes.

        This scans the AST module and registers all tag, shape, and function
        definitions. The definitions are created but not fully resolved yet.

        Args:
            ast_module: AST Module node
            engine: Engine instance for evaluation
        """
        # Import here to avoid circular dependency
        from . import ast

        for op in ast_module.operations:
            if isinstance(op, ast.TagDef):
                # Create tag definition (value will be None initially)
                # Skip if already exists (module was already evaluated)
                full_name = ".".join(op.path)
                if full_name not in self.tags:
                    self.define_tag(op.path, value=None)

            elif isinstance(op, ast.ShapeDef):
                # Create shape definition with empty fields initially
                # Fields will be resolved in phase 4
                # Skip if already exists (module was already evaluated)
                full_name = ".".join(op.path)
                if full_name not in self.shapes:
                    self.define_shape(op.path, fields=[])

            elif isinstance(op, ast.FuncDef):
                # Create function definition with AST body (not evaluated)
                # Skip if already exists (module was already evaluated)
                full_name = ".".join(op.path)
                if full_name not in self.functions:
                    self.define_function(
                        path=op.path,
                        body=op.body,
                        input_shape=None,  # Will be resolved in phase 4
                        arg_shape=None,    # Will be resolved in phase 4
                        is_pure=op.is_pure,
                        doc=op.doc,
                        impl_doc=op.impl_doc
                    )

            # ImportDef is handled in phase 2

    def _phase2_prepare_imports(self, ast_module: Any, engine: Any) -> None:
        """Phase 2: Walk all imports and recursively prepare each imported module.

        This processes import statements and ensures all dependencies are prepared
        before we build the resolution namespace. This allows circular imports to work.

        Args:
            ast_module: AST Module node
            engine: Engine instance for loading modules
        """
        from . import ast

        for op in ast_module.operations:
            if isinstance(op, ast.ImportDef):
                # Load the imported module
                imported_module = self._load_import(op, engine)

                if imported_module is not None:
                    # Recursively prepare the imported module
                    # (this is safe even with circular imports due to the
                    # incremental definition creation in phase 1)
                    if not getattr(imported_module, '_prepared', False):
                        # The imported module needs its own AST to be prepared
                        # For now, we assume it's already prepared or will be
                        # prepared by the loader
                        pass

                    # Add to our namespaces
                    self.add_namespace(op.namespace, imported_module)

    def _load_import(self, import_def: Any, engine: Any) -> 'Module | None':
        """Load an imported module based on ImportDef.

        This handles different import sources (stdlib, comp, python, etc.)
        and returns the loaded Module.

        Args:
            import_def: ImportDef AST node
            engine: Engine for evaluation

        Returns:
            Loaded Module, or None if loading failed
        """
        if import_def.source == "stdlib":
            from .stdlib import get_stdlib_module
            try:
                return get_stdlib_module(import_def.path)
            except Exception:
                return None

        elif import_def.source == "comp":
            from .ast import _loader
            try:
                return _loader.load_comp_module(import_def.path, engine)
            except Exception:
                return None

        # Other sources not yet implemented
        return None

    def _phase3_build_resolution_namespace(self) -> dict[tuple[str, list[str]], Any]:
        """Phase 3: Build complete resolution namespace for all partial references.

        This creates a lookup table that maps all possible partial references to
        their definitions. For example:
        - Tag "#ok" might map to multiple definitions
        - Tag "#ok.status" might map to one specific definition
        - Tag "#ok/request" explicitly references the "request" namespace

        The resolution namespace includes:
        - All local definitions (tags, shapes, functions)
        - All definitions from imported namespaces
        - Tracks ambiguous references

        Returns:
            Dictionary mapping (type, partial_path, namespace) to definitions or ambiguity markers
        """
        resolution_ns = {}

        # Add local definitions first (they override namespace imports)
        self._add_local_definitions_to_ns(resolution_ns)

        # Add definitions from all namespaces
        for ns_name, ns_module in self.namespaces.items():
            self._add_namespace_definitions_to_ns(resolution_ns, ns_name, ns_module)

        return resolution_ns

    def _add_local_definitions_to_ns(self, resolution_ns: dict) -> None:
        """Add all local definitions to the resolution namespace.

        For each definition, generates all possible partial references and
        adds them to the resolution namespace.

        Args:
            resolution_ns: Resolution namespace dictionary to populate
        """
        # Add tags - generate all possible partial suffixes
        for tag_def in self.tags.values():
            # Generate all partial paths (suffix matching)
            # E.g., ["status", "error", "timeout"] generates reference paths (reversed):
            #   ("timeout",)  - matches #timeout
            #   ("timeout", "error")  - matches #timeout.error
            #   ("timeout", "error", "status")  - matches #timeout.error.status
            # Note: tag_def.path is in definition order ["status", "error", "timeout"]
            # But references are reversed ["timeout", "error", "status"]
            for i in range(len(tag_def.path)):
                # Take suffix of definition path, then reverse for reference notation
                partial = tuple(reversed(tag_def.path[i:]))
                key = ('tag', partial, None)  # None = no explicit namespace

                if key in resolution_ns:
                    # Already exists - mark as ambiguous
                    if resolution_ns[key] != 'AMBIGUOUS':
                        resolution_ns[key] = 'AMBIGUOUS'
                else:
                    resolution_ns[key] = tag_def

        # Add shapes - generate all possible partial suffixes
        for shape_def in self.shapes.values():
            for i in range(len(shape_def.path)):
                partial = tuple(reversed(shape_def.path[i:]))
                key = ('shape', partial, None)

                if key in resolution_ns:
                    if resolution_ns[key] != 'AMBIGUOUS':
                        resolution_ns[key] = 'AMBIGUOUS'
                else:
                    resolution_ns[key] = shape_def

        # Add functions - generate all possible partial suffixes
        for _func_name, func_overloads in self.functions.items():
            if func_overloads:
                func_def = func_overloads[0]  # Use first overload for path
                for i in range(len(func_def.path)):
                    partial = tuple(reversed(func_def.path[i:]))
                    key = ('function', partial, None)

                    if key in resolution_ns:
                        if resolution_ns[key] != 'AMBIGUOUS':
                            resolution_ns[key] = 'AMBIGUOUS'
                    else:
                        resolution_ns[key] = func_overloads  # Store all overloads

    def _add_namespace_definitions_to_ns(self, resolution_ns: dict, ns_name: str, ns_module: 'Module') -> None:
        """Add definitions from a namespace to the resolution namespace.

        Definitions from namespaces are added with lower priority than local definitions.
        They are added both with and without explicit namespace qualifiers.

        Args:
            resolution_ns: Resolution namespace dictionary to populate
            ns_name: Name of the namespace
            ns_module: Module to import definitions from
        """
        # Add tags from namespace
        for tag_def in ns_module.tags.values():
            # Add with explicit namespace qualifier
            for i in range(len(tag_def.path)):
                partial = tuple(reversed(tag_def.path[i:]))

                # Add explicit namespace reference: #tag/namespace
                key_explicit = ('tag', partial, ns_name)
                if key_explicit not in resolution_ns:
                    resolution_ns[key_explicit] = tag_def

                # Add implicit reference (no namespace) - lower priority
                key_implicit = ('tag', partial, None)
                if key_implicit not in resolution_ns:
                    # Local definitions already added, so this won't override
                    resolution_ns[key_implicit] = tag_def
                elif resolution_ns[key_implicit] != 'AMBIGUOUS' and resolution_ns[key_implicit] != tag_def:
                    # Different definition exists
                    # Check if it's a local definition - if so, don't mark as ambiguous
                    # (local definitions override imports)
                    existing = resolution_ns[key_implicit]
                    if existing in self.tags.values():
                        # Existing is local - skip (local wins)
                        pass
                    else:
                        # Both are from namespaces - mark as ambiguous
                        resolution_ns[key_implicit] = 'AMBIGUOUS'

        # Add shapes from namespace
        for shape_def in ns_module.shapes.values():
            for i in range(len(shape_def.path)):
                partial = tuple(reversed(shape_def.path[i:]))

                key_explicit = ('shape', partial, ns_name)
                if key_explicit not in resolution_ns:
                    resolution_ns[key_explicit] = shape_def

                key_implicit = ('shape', partial, None)
                if key_implicit not in resolution_ns:
                    resolution_ns[key_implicit] = shape_def
                elif resolution_ns[key_implicit] != 'AMBIGUOUS' and resolution_ns[key_implicit] != shape_def:
                    existing = resolution_ns[key_implicit]
                    if existing in self.shapes.values():
                        pass  # Local wins
                    else:
                        resolution_ns[key_implicit] = 'AMBIGUOUS'

        # Add functions from namespace
        for _func_name, func_overloads in ns_module.functions.items():
            if func_overloads:
                func_def = func_overloads[0]
                for i in range(len(func_def.path)):
                    partial = tuple(reversed(func_def.path[i:]))

                    key_explicit = ('function', partial, ns_name)
                    if key_explicit not in resolution_ns:
                        resolution_ns[key_explicit] = func_overloads

                    key_implicit = ('function', partial, None)
                    if key_implicit not in resolution_ns:
                        resolution_ns[key_implicit] = func_overloads
                    elif resolution_ns[key_implicit] != 'AMBIGUOUS' and resolution_ns[key_implicit] != func_overloads:
                        # Check if local definition exists
                        existing = resolution_ns[key_implicit]
                        if isinstance(existing, list) and any(f in overloads for overloads in self.functions.values() for f in overloads):
                            pass  # Local wins
                        else:
                            resolution_ns[key_implicit] = 'AMBIGUOUS'

    def _phase4_preresolve_references(self, ast_module: Any, resolution_ns: dict) -> None:
        """Phase 4: Walk all AST nodes and pre-resolve all references.

        This walks through all definitions and pre-resolves any TagRef, ShapeRef,
        and FuncRef nodes. The resolved information is stored directly on the AST
        nodes (or as an attribute).

        Args:
            ast_module: AST Module node
            resolution_ns: Complete resolution namespace from phase 3

        Raises:
            ValueError: If any reference cannot be resolved or is ambiguous
        """
        from . import ast

        # Walk all operations and resolve references in them
        for op in ast_module.operations:
            if isinstance(op, ast.TagDef):
                self._preresolve_tag_def(op, resolution_ns)

            elif isinstance(op, ast.ShapeDef):
                self._preresolve_shape_def(op, resolution_ns)

            elif isinstance(op, ast.FuncDef):
                self._preresolve_func_def(op, resolution_ns)

    def _preresolve_tag_def(self, tag_def: Any, resolution_ns: dict) -> None:
        """Pre-resolve all references in a tag definition.

        Args:
            tag_def: TagDef AST node
            resolution_ns: Resolution namespace

        Raises:
            ValueError: If any reference cannot be resolved
        """
        # Recursively walk the value expression and children
        if tag_def.value:
            self._preresolve_node(tag_def.value, resolution_ns)

        for child in tag_def.children:
            if child.value:
                self._preresolve_node(child.value, resolution_ns)
            # Recurse into child's children
            for subchild in child.children:
                if subchild.value:
                    self._preresolve_node(subchild.value, resolution_ns)

    def _preresolve_shape_def(self, shape_def: Any, resolution_ns: dict) -> None:
        """Pre-resolve all references in a shape definition.

        Args:
            shape_def: ShapeDef AST node
            resolution_ns: Resolution namespace

        Raises:
            ValueError: If any reference cannot be resolved
        """
        # Walk all field definitions
        for field_def in shape_def.fields:
            if field_def.shape_ref:
                self._preresolve_node(field_def.shape_ref, resolution_ns)
            if field_def.default:
                self._preresolve_node(field_def.default, resolution_ns)

    def _preresolve_func_def(self, func_def: Any, resolution_ns: dict) -> None:
        """Pre-resolve all references in a function definition.

        Args:
            func_def: FuncDef AST node
            resolution_ns: Resolution namespace

        Raises:
            ValueError: If any reference cannot be resolved
        """
        # Resolve input and arg shapes
        if func_def.input_shape:
            self._preresolve_node(func_def.input_shape, resolution_ns)
        if func_def.arg_shape:
            self._preresolve_node(func_def.arg_shape, resolution_ns)

        # Resolve body
        self._preresolve_node(func_def.body, resolution_ns)

    def _preresolve_node(self, node: Any, resolution_ns: dict) -> None:
        """Recursively pre-resolve all references in an AST node.

        This walks the AST tree and resolves TagRef, ShapeRef, and FuncRef nodes.
        The resolved definition is stored as a `_resolved` attribute on the node.

        Args:
            node: AST node to process
            resolution_ns: Resolution namespace

        Raises:
            ValueError: If any reference cannot be resolved or is ambiguous
        """
        from . import ast

        # Base case: handle reference nodes
        if isinstance(node, ast.TagValueRef):
            key = ('tag', tuple(node.path), node.namespace)
            if key not in resolution_ns:
                path_str = ".".join(reversed(node.path))
                ns_str = f"/{node.namespace}" if node.namespace else ""
                position = getattr(node, 'position', None)
                pos_str = f" {position}" if position else ""
                raise ValueError(f"Undefined tag reference: #{path_str}{ns_str}{pos_str}")

            resolved = resolution_ns[key]
            if resolved == 'AMBIGUOUS':
                path_str = ".".join(reversed(node.path))
                position = getattr(node, 'position', None)
                pos_str = f" {position}" if position else ""
                raise ValueError(f"Ambiguous tag reference: #{path_str}{pos_str}")

            # Store resolved definition on the node
            node._resolved = resolved

        elif isinstance(node, ast.ShapeRef):
            key = ('shape', tuple(node.path), node.namespace)
            if key not in resolution_ns:
                path_str = ".".join(reversed(node.path))
                ns_str = f"/{node.namespace}" if node.namespace else ""
                position = getattr(node, 'position', None)
                pos_str = f" {position}" if position else ""
                raise ValueError(f"Undefined shape reference: ~{path_str}{ns_str}{pos_str}")

            resolved = resolution_ns[key]
            if resolved == 'AMBIGUOUS':
                path_str = ".".join(reversed(node.path))
                ns_str = f"/{node.namespace}" if node.namespace else ""
                position = getattr(node, 'position', None)
                pos_str = f" {position}" if position else ""
                raise ValueError(f"Ambiguous shape reference: ~{path_str}{ns_str}{pos_str}")

            node._resolved = resolved

        elif isinstance(node, ast.FuncRef):
            key = ('function', tuple(node.path), node.namespace)
            if key not in resolution_ns:
                path_str = ".".join(reversed(node.path))
                ns_str = f"/{node.namespace}" if node.namespace else ""
                position = getattr(node, 'position', None)
                pos_str = f" {position}" if position else ""
                raise ValueError(f"Undefined function reference: |{path_str}{ns_str}{pos_str}")

            resolved = resolution_ns[key]
            if resolved == 'AMBIGUOUS':
                path_str = ".".join(reversed(node.path))
                position = getattr(node, 'position', None)
                pos_str = f" {position}" if position else ""
                raise ValueError(f"Ambiguous function reference: |{path_str}{pos_str}")

            node._resolved = resolved

        # Recursive case: walk child nodes
        # This is a simple visitor pattern - for more complex ASTs,
        # consider implementing a proper visitor
        for attr_name in dir(node):
            if attr_name.startswith('_'):
                continue

            attr = getattr(node, attr_name)

            # Handle lists of nodes
            if isinstance(attr, list):
                for item in attr:
                    if hasattr(item, 'evaluate'):  # Check if it's an AST node
                        self._preresolve_node(item, resolution_ns)

            # Handle single nodes
            elif hasattr(attr, 'evaluate'):  # Check if it's an AST node
                self._preresolve_node(attr, resolution_ns)

    def __repr__(self):
        parts = []
        if self.tags:
            parts.append(f"{len(self.tags)} tags")
        if self.shapes:
            parts.append(f"{len(self.shapes)} shapes")
        if self.functions:
            func_count = sum(len(overloads) for overloads in self.functions.values())
            parts.append(f"{func_count} functions")
        if self.namespaces:
            parts.append(f"{len(self.namespaces)} namespaces")
        return f"Module({', '.join(parts)})" if parts else "Module(empty)"

