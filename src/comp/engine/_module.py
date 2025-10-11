"""Module system for the engine - tracks definitions and provides namespaces."""

__all__ = ["Module", "TagDefinition", "ShapeDefinition", "ShapeField", "FunctionDefinition"]

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
            - Multiple definitions of the same shape replace previous ones
        """
        full_name = ".".join(path)
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

