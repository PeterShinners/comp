"""Module system for the engine - tracks definitions and provides namespaces."""

__all__ = ["Module", "TagDefinition", "HandleDefinition", "ShapeField", "ShapeDefinition"]


import comp

from . import _entity, _function


class ShapeField(_entity.Entity):
    """A single field in a shape definition.

    Inherits from Entity so it can be returned from evaluate() and passed through scopes.

    NOTE: Runtime ShapeField objects should NOT have spreads - those are expanded during
    shape definition. Only the AST nodes (ShapeFieldDef) should handle spreads.

    Attributes:
        name (str | None): Optional field name (None for positional fields)
        shape: Type constraint for this field (can be ShapeDefinition, tag, primitive type reference)
        default: Optional default value (None means field is required)
        is_array (bool): True if field accepts multiple values ([])
        array_min (int | None): Minimum array length (None for no minimum)
        array_max (int | None): Maximum array length (None for no maximum)
    """
    def __init__(self, name=None, shape=None, default=None,
                 is_array=False, array_min=None,
                 array_max=None):
        self.name = name
        self.shape = shape
        self.default = default
        self.is_array = is_array
        self.array_min = array_min
        self.array_max = array_max

    @property
    def is_named(self):
        """Check if this is a named field.
        
        Returns:
            bool: True if field has a name
        """
        return self.name is not None

    @property
    def is_positional(self):
        """Check if this is a positional field.
        
        Returns:
            bool: True if field is positional (no name)
        """
        return self.name is None

    @property
    def is_required(self):
        """Check if this field is required (no default value).
        
        Returns:
            bool: True if field has no default
        """
        return self.default is None

    def __repr__(self):
        name_part = f'"{self.name}": ' if self.name else ""
        shape_part = f"ShapeRef(~{self.shape} (unresolved))" if self.shape else "Any"
        array_part = "[]" if self.is_array else ""
        return f"ShapeField({name_part}{shape_part}){array_part}"


class TagDefinition(_entity.Entity):
    """A single tag definition in the module.

    Inherits from Entity so it can be returned from evaluate() and passed
    through scopes, similar to ShapeDefinition.

    Attributes:
        path (list[str]): Full path as list, e.g., ["status", "error", "timeout"]
        module (Module): The Module this tag is defined in
        value: Optional value for this tag (can be any Value)
    """
    def __init__(self, path, module, value=None, is_private: bool = False):
        self.path = path
        self.module = module
        self.value = value  # Will be engine.Value when evaluated
        self.is_private = is_private

    @property
    def name(self):
        """Get the tag's leaf name (last element of path).
        
        Returns:
            str: The tag's leaf name
        """
        return self.path[-1] if self.path else ""

    @property
    def full_name(self):
        """Get dot-separated full path.
        
        Returns:
            str: Full tag path joined with dots
        """
        return ".".join(self.path)

    @property
    def parent_path(self):
        """Get the parent's path, or None for root tags.
        
        Returns:
            list[str] | None: Parent path or None
        """
        if len(self.path) <= 1:
            return None
        return self.path[:-1]

    def matches_partial(self, partial):
        """Check if this tag matches a partial path (prefix match).

        Args:
            partial (list[str]): Partial path in natural order, e.g., ["error", "timeout"]
                    for #error.timeout or just ["timeout"] for leaf-only reference

        Returns:
            bool: True if tag's path ends with the partial path (prefix match on reversed path)
        """
        if len(partial) > len(self.path):
            return False
        # For prefix matching: partial matches if it equals the last N elements of our path
        # E.g., path=["status", "error"], partial=["error"] matches
        # E.g., path=["status", "error"], partial=["status", "error"] matches
        return self.path[-len(partial):] == partial


class HandleDefinition(_entity.Entity):
    """A single handle definition in the module.

    Inherits from Entity so it can be returned from evaluate() and passed
    through scopes, similar to ShapeDefinition and TagDefinition.

    Attributes:
        path (list[str]): Full path as list, e.g., ["file", "readonly", "text"]
        module (Module): The Module this handle is defined in
        drop_block: Optional AST node for the drop block (e.g., RawBlock)
    """
    def __init__(self, path, module, drop_block=None, is_private: bool = False):
        self.path = path
        self.module = module
        self.drop_block = drop_block
        self.is_private = is_private

    @property
    def name(self):
        """Get the handle's leaf name (last element of path).
        
        Returns:
            str: The handle's leaf name
        """
        return self.path[-1] if self.path else ""

    @property
    def full_name(self):
        """Get dot-separated full path.
        
        Returns:
            str: Full handle path joined with dots
        """
        return ".".join(self.path)

    @property
    def parent_path(self):
        """Get the parent's path, or None for root handles.
        
        Returns:
            list[str] | None: Parent path or None
        """
        return self.path[:-1] if len(self.path) > 1 else None

    @property
    def parent(self):
        """Get the parent HandleDefinition, or None for root handles.
        
        Returns:
            HandleDefinition | None: Parent handle definition or None
        """
        parent_path = self.parent_path
        if parent_path is None:
            return None
        return self.module.get_handle_by_full_path(parent_path)

    @property
    def children(self):
        """Get all direct children of this handle.
        
        Returns:
            list[HandleDefinition]: List of child handle definitions
        """
        children = []
        prefix = self.full_name + "."
        for handle_name, handle_def in self.module.handles.items():
            # Check if this is a direct child (one level deeper)
            if handle_name.startswith(prefix):
                # Count dots to ensure it's a direct child, not a grandchild
                remainder = handle_name[len(prefix):]
                if "." not in remainder:
                    children.append(handle_def)
        return children

    @property
    def descendants(self):
        """Get all descendants (children, grandchildren, etc.) of this handle.
        
        Returns:
            list[HandleDefinition]: List of all descendant handle definitions
        """
        descendants = []
        prefix = self.full_name + "."
        for handle_name, handle_def in self.module.handles.items():
            if handle_name.startswith(prefix):
                descendants.append(handle_def)
        return descendants

    @property
    def ancestors(self):
        """Get all ancestors (parent, grandparent, etc.) of this handle.
        
        Returns:
            list[HandleDefinition]: List of ancestor handle definitions, from parent to root
        """
        ancestors = []
        current = self.parent
        while current is not None:
            ancestors.append(current)
            current = current.parent
        return ancestors

    @property
    def is_root(self):
        """Check if this is a root handle (no parent).
        
        Returns:
            bool: True if this handle has no parent
        """
        return len(self.path) == 1

    @property
    def depth(self):
        """Get the depth of this handle in the hierarchy (root = 1).
        
        Returns:
            int: Depth level, starting at 1 for root handles
        """
        return len(self.path)

    def is_ancestor_of(self, other):
        """Check if this handle is an ancestor of another handle.
        
        Args:
            other (HandleDefinition): Another handle definition
            
        Returns:
            bool: True if this handle is an ancestor of other
        """
        if len(self.path) >= len(other.path):
            return False
        return other.path[:len(self.path)] == self.path

    def is_descendant_of(self, other):
        """Check if this handle is a descendant of another handle.
        
        Args:
            other (HandleDefinition): Another handle definition
            
        Returns:
            bool: True if this handle is a descendant of other
        """
        return other.is_ancestor_of(self)

    def matches_partial(self, partial):
        """Check if this handle matches a partial path (prefix match).

        Args:
            partial (list[str]): Partial path in natural order, e.g., ["file", "readonly"]
                    for @file.readonly or just ["readonly"] for leaf-only reference

        Returns:
            bool: True if handle's path ends with the partial path (prefix match on reversed path)
        """
        if len(partial) > len(self.path):
            return False
        # For prefix matching: partial matches if it equals the last N elements of our path
        # E.g., path=["file", "readonly"], partial=["readonly"] matches
        # E.g., path=["file", "readonly"], partial=["file", "readonly"] matches
        return self.path[-len(partial):] == partial


class ShapeDefinition(_entity.Entity):
    """A shape definition in the module.

    Shapes describe structure types with field names, types, and defaults.
    They are used for morphing operations and type validation.

    Inherits from Entity so it can be returned from evaluate() and passed
    through scopes.

    Attributes:
        path (list[str]): Full path as list, e.g., ["geometry", "point", "2d"]
        module (Module): The Module this shape is defined in
        fields (list[ShapeField]): List of field definitions
        is_union (bool): True if this is a union shape (combines multiple shapes)
        union_members (list): List of shape references for union shapes
    """
    def __init__(self, path, module, fields,
                 is_union=False, union_members=None, is_private: bool = False):
        self.path = path
        self.module = module
        self.fields = fields
        self.is_union = is_union
        self.union_members = union_members or []
        self.doc = None  # Documentation from !doc statement
        self.is_private = is_private

    @property
    def name(self):
        """Get the shape's leaf name (last element of path).
        
        Returns:
            str: The shape's leaf name
        """
        return self.path[-1] if self.path else ""

    @property
    def full_name(self):
        """Get dot-separated full path.
        
        Returns:
            str: Full shape path joined with dots
        """
        return ".".join(self.path)

    @property
    def parent_path(self):
        """Get the parent's path, or None for root shapes.
        
        Returns:
            list[str] | None: Parent path or None
        """
        return self.path[:-1] if len(self.path) > 1 else None

    def matches_partial(self, partial):
        """Check if this shape matches a partial path (prefix match).

        Args:
            partial (list[str]): Partial path in natural order, e.g., ["point", "2d"]
                    for ~point.2d or just ["2d"] for leaf-only reference

        Returns:
            bool: True if shape's path ends with the partial path (prefix match on reversed path)
        """
        if len(partial) > len(self.path):
            return False
        # For prefix matching: partial matches if it equals the last N elements of our path
        return self.path[-len(partial):] == partial

    @property
    def named_fields(self):
        """Get all named fields.
        
        Returns:
            list[ShapeField]: All fields with names
        """
        return [f for f in self.fields if f.is_named]

    @property
    def positional_fields(self):
        """Get all positional fields.
        
        Returns:
            list[ShapeField]: All positional fields
        """
        return [f for f in self.fields if f.is_positional]

    @property
    def required_fields(self):
        """Get all required fields (no defaults).
        
        Returns:
            list[ShapeField]: All fields without defaults
        """
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

    def unparse(self):
        """Convert shape definition to source-like representation.

        Returns:
            str: Human-readable shape definition string
        """
        if self.is_union and self.union_members:
            # Union shape: ~name = ~shape1 | ~shape2 | ~shape3
            members = []
            for member in self.union_members:
                if hasattr(member, 'full_name'):
                    members.append(f"~{member.full_name}")
                else:
                    members.append(str(member))
            return f"~{self.full_name} = {' | '.join(members)}"

        # Regular shape with fields
        if not self.fields:
            return f"~{self.full_name} = {{}}"

        # Build field definitions
        field_strs = []
        for field in self.fields:
            field_str = ""

            # Named field: name
            if field.is_named:
                field_str = field.name

            # Shape constraint
            if field.shape:
                if hasattr(field.shape, 'full_name'):
                    shape_name = field.shape.full_name
                elif hasattr(field.shape, 'data'):
                    # Tag reference
                    shape_name = f"#{field.shape.data}"
                else:
                    shape_name = str(field.shape)

                if field.is_named:
                    field_str += f" ~{shape_name}"
                else:
                    field_str = f"~{shape_name}"

            # Array modifier
            if field.is_array:
                field_str += "[]"
                if field.array_min is not None or field.array_max is not None:
                    min_str = str(field.array_min) if field.array_min is not None else ""
                    max_str = str(field.array_max) if field.array_max is not None else ""
                    if min_str or max_str:
                        field_str += f"[{min_str}:{max_str}]"

            # Default value
            if field.default is not None:
                if hasattr(field.default, 'unparse'):
                    default_str = field.default.unparse()
                else:
                    default_str = str(field.default)
                field_str += f" = {default_str}"

            field_strs.append(field_str)

        return f"~{self.full_name} = {{{' '.join(field_strs)}}}"


class Module(_entity.Entity):
    """Runtime module containing tag definitions and other module-level entities.

    This tracks all definitions made at module scope and provides lookup
    mechanisms for resolving references.

    Inherits from _entity.Entity, making it passable through scopes and returnable
    from evaluate() methods (though modules are not valid runtime values).

    Every module (except builtin itself) automatically has a 'builtin' namespace
    reference, providing access to core tags (#true, #false, #fail, etc),
    primitive shapes (~num, ~str, etc), and core functions (|print, |double, etc).

    Attributes:
        tags (dict): Flat dictionary of full_path -> TagDefinition
        shapes (dict): Dictionary of shape_name -> ShapeDefinition
        functions (dict): Dictionary of func_name -> list[FunctionDefinition] (for overloads)
        namespaces (dict): Dictionary of namespace_name -> Module (imported modules)
        package_info (dict): Optional package metadata
        is_builtin (bool): True if this is the builtin module (to avoid circular namespace refs)
    """

    # Class-level counter for unique module IDs
    _module_counter = 0

    def __init__(self, is_builtin=False, module_id=None):
        """Initialize a module.

        Args:
            is_builtin (bool): True if this is the builtin module
            module_id (str | None): Optional human-readable module identifier.
                If None, uses id(self) for uniqueness. This identifier is used
                for private data lookups (& syntax).
        """
        self.tags = {}  # full_path_str -> TagDefinition
        self.handles = {}  # full_path_str -> HandleDefinition
        self.shapes = {}  # full_path_str -> ShapeDefinition
        self.functions = {}  # full_path_str -> list of overloads
        self.namespaces = {}  # namespace -> imported Module
        self.package_info = {}
        self.is_builtin = is_builtin
        
        # Module identifier for private data lookups
        # Always unique - uses incrementing counter appended to optional name
        Module._module_counter += 1
        if module_id is not None:
            self._module_id = f"{module_id}:{Module._module_counter}"
        else:
            self._module_id = Module._module_counter

        # Module scope storage for $mod namespace
        # This is a Value with a struct containing module-level state
        from ._value import Value
        self.scope = Value({})  # Start with empty struct

        # Alias for mod_scope to match ModuleAssign usage
        self.mod_scope = self.scope

        # Entry points (stored as AST nodes, not in function registry)
        self.main_func = None  # AST node for !main body
        self.entry_func = None  # AST node for !entry body

        # Documentation
        self.doc = None  # Module-level documentation from !doc module

        # Pending documentation from !doc statements
        # Consumed by the next definition that's evaluated
        self.pending_doc = None  # General documentation
        self.pending_impl_doc = None  # Implementation-specific documentation

        # Add builtin namespace to all non-builtin modules
        if not is_builtin:
            # Import happens lazily to avoid circular dependency
            from .builtin import get_builtin_module
            self.namespaces['builtin'] = get_builtin_module()

    @property
    def module_id(self):
        """Get the unique module identifier used for private data lookups.
        
        This identifier is used as a key when accessing module-private data
        via the & syntax. Always unique - uses an incrementing counter.
        If a name is provided, it's formatted as "name:counter" for debugging.
        Otherwise, just the counter is used.
        
        Returns:
            int | str: Module identifier (hashable and unique)
        """
        return self._module_id

    def define_tag(self, path, value=None, is_private: bool = False):
        """Register a tag definition.

        Args:
            path (list[str]): Full path in definition order, e.g., ["status", "error", "timeout"]
            value: Optional value for this tag

        Returns:
            TagDefinition: The TagDefinition object

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
            tag_def = TagDefinition(path=path, module=self, value=value, is_private=is_private)
            self.tags[full_name] = tag_def

        return tag_def

    def define_handle(self, path, drop_block=None, is_private: bool = False):
        """Register a handle definition.

        Args:
            path (list[str]): Full path in definition order, e.g., ["file", "readonly", "text"]
            drop_block: Optional AST node for the drop block (e.g., RawBlock)

        Returns:
            HandleDefinition: The HandleDefinition object

        Notes:
            - Multiple definitions of the same handle merge
            - If drop_block is provided, it replaces any existing drop_block
        """
        full_name = ".".join(path)

        if full_name in self.handles:
            # Handle already exists - update drop_block if provided
            handle_def = self.handles[full_name]
            if drop_block is not None:
                handle_def.drop_block = drop_block
        else:
            # Create new handle definition
            handle_def = HandleDefinition(path=path, module=self, drop_block=drop_block, is_private=is_private)
            self.handles[full_name] = handle_def

        return handle_def

    def lookup_tag(self, partial_path, namespace=None, local_only=False):
        """Find tag by partial path, optionally in a specific namespace.

        Args:
            partial_path (list[str]): Partial path in natural order,
                         e.g., ["error", "timeout"] for #error.timeout
            namespace (str | None): Optional namespace to search in (e.g., "std" for /std)
            local_only (bool): If True, only search locally defined tags, not imported namespaces

        Returns:
            TagDefinition: TagDefinition if unique match found

        Raises:
            ValueError: If not found, ambiguous, or namespace not found

        Notes:
            - If namespace is provided, searches only that namespace
            - If namespace is None, searches local module first, then all namespaces
            - local_only is used when searching imported namespaces to avoid pollution
        """
        if namespace is not None:
            # Explicit namespace - look only there (with local_only=True to avoid recursion)
            ns_module = self.namespaces.get(namespace)
            if ns_module is None:
                partial_str = ".".join(partial_path)
                raise ValueError(f"Namespace not found: /{namespace} for tag #{partial_str}")
            return ns_module.lookup_tag(partial_path, local_only=True)

        # No namespace - check local first (only tags defined in THIS module)
        matches = [
            tag_def for tag_def in self.tags.values()
            if tag_def.module == self and tag_def.matches_partial(partial_path)
        ]

        if len(matches) == 1:
            return matches[0]
        elif len(matches) > 1:
            # Ambiguous in local module
            match_names = [t.full_name for t in matches]
            partial_str = ".".join(partial_path)
            raise ValueError(
                f"Ambiguous tag reference #{partial_str} matches: "
                f"{', '.join('#' + n for n in match_names)}"
            )

        # If local_only, don't search namespaces
        if local_only:
            partial_str = ".".join(partial_path)
            raise ValueError(f"Tag not found: #{partial_str}")

        # Not found locally - check all namespaces (with local_only=True for each)
        # IMPORTANT: Private definitions in namespaces will be excluded by the namespace's
        # lookup_tag with local_only=True
        found_results = []
        found_namespaces = []

        for ns_name, ns_module in self.namespaces.items():
            try:
                result = ns_module.lookup_tag(partial_path, local_only=True)
                # Additional check: exclude private definitions from other modules
                if result.is_private and result.module != self:
                    continue
                found_results.append(result)
                found_namespaces.append(ns_name)
            except ValueError:
                # Not found or ambiguous in that namespace - skip it
                continue

        if len(found_results) == 0:
            partial_str = ".".join(partial_path)
            raise ValueError(f"Tag not found: #{partial_str}")
        elif len(found_results) == 1:
            return found_results[0]
        else:
            # Found in multiple namespaces - ambiguous
            partial_str = ".".join(partial_path)
            ns_list = ", ".join(f"/{ns}" for ns in found_namespaces)
            raise ValueError(
                f"Ambiguous tag reference #{partial_str} found in multiple namespaces: {ns_list}"
            )

    def lookup_handle(self, partial_path, namespace=None, local_only=False):
        """Find handle by partial path, optionally in a specific namespace.

        Args:
            partial_path (list[str]): Partial path in natural order,
                         e.g., ["file", "readonly"] for @file.readonly
            namespace (str | None): Optional namespace to search in (e.g., "std" for /std)
            local_only (bool): If True, only search locally defined handles, not imported namespaces

        Returns:
            HandleDefinition: HandleDefinition if unique match found

        Raises:
            ValueError: If not found, ambiguous, or namespace not found

        Notes:
            - If namespace is provided, searches only that namespace
            - If namespace is None, searches local module first, then all namespaces
            - local_only is used when searching imported namespaces to avoid pollution
        """
        if namespace is not None:
            # Explicit namespace - look only there (with local_only=True to avoid recursion)
            ns_module = self.namespaces.get(namespace)
            if ns_module is None:
                partial_str = ".".join(partial_path)
                raise ValueError(f"Namespace not found: /{namespace} for handle @{partial_str}")
            return ns_module.lookup_handle(partial_path, local_only=True)

        # No namespace - check local first (only handles defined in THIS module)
        matches = [
            handle_def for handle_def in self.handles.values()
            if handle_def.module == self and handle_def.matches_partial(partial_path)
        ]

        if len(matches) == 1:
            return matches[0]
        elif len(matches) > 1:
            # Ambiguous in local module
            match_names = [h.full_name for h in matches]
            partial_str = ".".join(partial_path)
            raise ValueError(
                f"Ambiguous handle reference @{partial_str} matches: "
                f"{', '.join('@' + n for n in match_names)}"
            )

        # If local_only, don't search namespaces
        if local_only:
            partial_str = ".".join(partial_path)
            raise ValueError(f"Handle not found: @{partial_str}")

        # Not found locally - check all namespaces (with local_only=True for each)
        # IMPORTANT: Private definitions in namespaces will be excluded by the namespace's
        # lookup_handle with local_only=True
        found_results = []
        found_namespaces = []

        for ns_name, ns_module in self.namespaces.items():
            try:
                result = ns_module.lookup_handle(partial_path, local_only=True)
                # Additional check: exclude private definitions from other modules
                if result.is_private and result.module != self:
                    continue
                found_results.append(result)
                found_namespaces.append(ns_name)
            except ValueError:
                # Not found or ambiguous in that namespace - skip it
                continue

        if len(found_results) == 0:
            partial_str = ".".join(partial_path)
            raise ValueError(f"Handle not found: @{partial_str}")
        elif len(found_results) == 1:
            return found_results[0]
        else:
            # Found in multiple namespaces - ambiguous
            partial_str = ".".join(partial_path)
            ns_list = ", ".join(f"/{ns}" for ns in found_namespaces)
            raise ValueError(
                f"Ambiguous handle reference @{partial_str} found in multiple namespaces: {ns_list}"
            )

    def get_tag_by_full_path(self, path):
        """Get tag by exact full path.

        Args:
            path (list[str]): Full path in definition order, e.g., ["status", "error", "timeout"]

        Returns:
            TagDefinition | None: TagDefinition if found, None otherwise
        """
        full_name = ".".join(path)
        return self.tags.get(full_name)

    def get_handle_by_full_path(self, path):
        """Get handle by exact full path.

        Args:
            path (list[str]): Full path in definition order, e.g., ["file", "readonly", "text"]

        Returns:
            HandleDefinition | None: HandleDefinition if found, None otherwise
        """
        full_name = ".".join(path)
        return self.handles.get(full_name)

    def list_tags(self):
        """Get all tag definitions in the module.
        
        Returns:
            list[TagDefinition]: All tag definitions
        """
        return list(self.tags.values())

    def find_tags_by_value(self, value, parent_tag=None):
        """Find all tags whose value matches the given value.
        
        This searches for tags that have the exact same value. Useful for
        implementing value-to-tag morphing.
        
        Args:
            value: The value to search for (typically a comp.Value)
            parent_tag (TagDefinition | None): If provided, only search within
                this tag's descendants
        
        Returns:
            list[TagDefinition]: List of tags with matching values
        """
        import comp
        
        matches = []
        search_tags = self.tags.values()
        
        # If parent_tag is specified, only search its descendants
        if parent_tag is not None:
            search_tags = parent_tag.descendants
        
        for tag_def in search_tags:
            if tag_def.value is None:
                continue
            
            # Compare values - handle both Value objects and raw values
            tag_val = tag_def.value
            search_val = value
            
            # Normalize to comp.Value if needed
            if not isinstance(tag_val, comp.Value):
                tag_val = comp.Value(tag_val)
            if not isinstance(search_val, comp.Value):
                search_val = comp.Value(search_val)
            
            # Simple equality check - compare data
            # This could be enhanced with deep equality for structs
            if tag_val.is_number and search_val.is_number:
                if tag_val.data == search_val.data:
                    matches.append(tag_def)
            elif tag_val.is_string and search_val.is_string:
                if tag_val.data == search_val.data:
                    matches.append(tag_def)
            elif tag_val.is_tag and search_val.is_tag:
                if tag_val.data.tag_def == search_val.data.tag_def:
                    matches.append(tag_def)
        
        return matches

    def define_shape(self, path, fields,
                     is_union=False, union_members=None, is_private: bool = False):
        """Register a shape definition.

        Args:
            path (list[str]): Full path in definition order, e.g., ["geometry", "point", "2d"]
            fields (list[ShapeField]): List of field definitions
            is_union (bool): True if this is a union shape
            union_members (list | None): Shape references for union types

        Returns:
            ShapeDefinition: The created shape definition
            
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
                module=self,
                fields=fields,
                is_union=is_union,
                union_members=union_members or [],
                is_private=is_private
            )
            self.shapes[full_name] = shape_def
            return shape_def

    def list_shapes(self):
        """Get all shape definitions in the module.
        
        Returns:
            list[ShapeDefinition]: All shape definitions
        """
        return list(self.shapes.values())

    def define_function(self, path, body, input_shape=None,
                       arg_shape=None, is_pure=False,
                       doc=None, impl_doc=None, is_private: bool = False):
        """Register a function definition.

        Supports overloading - multiple definitions with the same path.
        Functions are matched by input shape specificity at call time.

        Args:
            path (list[str]): Full path in definition order, e.g., ["math", "geometry", "area"]
            body: Structure definition AST for function body
            input_shape: Shape for input structure (None for any)
            arg_shape: Shape for arguments (None for no args)
            is_pure (bool): True if function has no side effects
            doc (str | None): Documentation string (shared across overloads)
            impl_doc (str | None): Documentation for this specific implementation

        Returns:
            _function.FunctionDefinition: The FunctionDefinition object

        Notes:
            - Multiple definitions create overloads
            - Specificity matching determines which implementation runs
            - During module preparation, empty overload lists may exist as placeholders
              (cleared on first real definition)
        """
        full_name = ".".join(path)
        func_def = comp.FunctionDefinition(
            path=path,
            module=self,
            body=body,
            input_shape=input_shape,
            arg_shape=arg_shape,
            is_pure=is_pure,
            doc=doc,
            impl_doc=impl_doc,
            is_private=is_private
        )

        # Add to overload list
        if full_name not in self.functions:
            self.functions[full_name] = []
        
        # Check if we have a placeholder from prepare() (_placeholder flag)
        # If so, replace it IN PLACE (so pre-resolved references stay valid)
        existing = self.functions[full_name]
        if existing and len(existing) == 1 and getattr(existing[0], '_placeholder', False):
            # Replace placeholder with real definition (in place)
            existing[0] = func_def
        else:
            # Append as additional overload (true overloading)
            existing.append(func_def)

        return func_def

    def list_functions(self):
        """Get all function definitions (all overloads flattened).
        
        Returns:
            list[_function.FunctionDefinition]: All function definitions
        """
        result = []
        for overloads in self.functions.values():
            result.extend(overloads)
        return result

    def add_namespace(self, name, module):
        """Add an imported module to this module's namespace.

        Args:
            name (str): Namespace identifier (used in /namespace references)
            module (Module): The imported Module to reference

        Notes:
            - Used to implement imports
            - References can use /namespace to explicitly look in that module
            - Without namespace, lookups check local module then all namespaces
        """
        self.namespaces[name] = module

    def lookup_shape(self, partial_path, namespace=None, local_only=False):
        """Find shape by partial path, optionally in a specific namespace.

        Args:
            partial_path (list[str]): Partial path in natural order,
                         e.g., ["point", "2d"] for ~point.2d
            namespace (str | None): Optional namespace to search in (e.g., "std" for /std)
            local_only (bool): If True, only search locally defined shapes, not imported namespaces

        Returns:
            ShapeDefinition: ShapeDefinition if unique match found

        Raises:
            ValueError: If not found, ambiguous, or namespace not found

        Notes:
            - If namespace is provided, searches only that namespace
            - If namespace is None, searches local module first, then all namespaces
            - local_only is used when searching imported namespaces to avoid pollution
        """
        if namespace is not None:
            # Explicit namespace - look only there (with local_only=True to avoid recursion)
            ns_module = self.namespaces.get(namespace)
            if ns_module is None:
                partial_str = ".".join(partial_path)
                raise ValueError(f"Namespace not found: /{namespace} for shape ~{partial_str}")
            return ns_module.lookup_shape(partial_path, local_only=True)

        # No namespace - check local first (only shapes defined in THIS module)
        matches = [
            shape_def for shape_def in self.shapes.values()
            if shape_def.module == self and shape_def.matches_partial(partial_path)
        ]

        if len(matches) == 1:
            return matches[0]
        elif len(matches) > 1:
            # Ambiguous in local module
            match_names = [s.full_name for s in matches]
            partial_str = ".".join(partial_path)
            raise ValueError(
                f"Ambiguous shape reference ~{partial_str} matches: "
                f"{', '.join('~' + n for n in match_names)}"
            )

        # If local_only, don't search namespaces
        if local_only:
            partial_str = ".".join(partial_path)
            raise ValueError(f"Shape not found: ~{partial_str}")

        # Not found locally - check all namespaces (with local_only=True for each)
        # IMPORTANT: Private definitions in namespaces will be excluded by the namespace's
        # lookup_shape with local_only=True
        found_results = []
        found_namespaces = []

        for ns_name, ns_module in self.namespaces.items():
            try:
                result = ns_module.lookup_shape(partial_path, local_only=True)
                # Additional check: exclude private definitions from other modules
                if result.is_private and result.module != self:
                    continue
                found_results.append(result)
                found_namespaces.append(ns_name)
            except ValueError:
                # Not found or ambiguous in that namespace - skip it
                continue

        if len(found_results) == 0:
            partial_str = ".".join(partial_path)
            raise ValueError(f"Shape not found: ~{partial_str}")
        elif len(found_results) == 1:
            return found_results[0]
        else:
            # Found in multiple namespaces - ambiguous
            partial_str = ".".join(partial_path)
            ns_list = ", ".join(f"/{ns}" for ns in found_namespaces)
            raise ValueError(
                f"Ambiguous shape reference ~{partial_str} found in multiple namespaces: {ns_list}"
            )

    def lookup_function(self, partial_path,
                        namespace=None, local_only=False):
        """Find function by partial path, optionally in a specific namespace.

        Args:
            partial_path (list[str]): Partial path in natural order,
                         e.g., ["geometry", "area"] for |geometry.area
            namespace (str | None): Optional namespace to search in (e.g., "std" for /std)
            local_only (bool): If True, only search locally defined functions, not imported namespaces

        Returns:
            list[_function.FunctionDefinition]: List of FunctionDefinition overloads

        Raises:
            ValueError: If not found, ambiguous, or namespace not found

        Notes:
            - If namespace is provided, searches only that namespace
            - If namespace is None, searches local module first, then all namespaces
            - local_only is used when searching imported namespaces to avoid pollution
        """
        if namespace is not None:
            # Explicit namespace - look only there (with local_only=True to avoid recursion)
            ns_module = self.namespaces.get(namespace)
            if ns_module is None:
                partial_str = ".".join(partial_path)
                raise ValueError(f"Namespace not found: /{namespace} for function |{partial_str}")
            return ns_module.lookup_function(partial_path, local_only=True)

        # No namespace - check local first (only functions defined in THIS module)
        matches = []
        for _full_name, overloads in self.functions.items():
            # Check if any overload matches and is locally defined
            if overloads and overloads[0].module == self and overloads[0].matches_partial(partial_path):
                matches.append(overloads)

        if len(matches) == 1:
            return matches[0]
        elif len(matches) > 1:
            # Ambiguous in local module
            match_names = [funcs[0].full_name for funcs in matches]
            partial_str = ".".join(partial_path)
            raise ValueError(
                f"Ambiguous function reference |{partial_str} matches: "
                f"{', '.join('|' + n for n in match_names)}"
            )

        # If local_only, don't search namespaces
        if local_only:
            partial_str = ".".join(partial_path)
            raise ValueError(f"Function not found: |{partial_str}")

        # Not found locally - check all namespaces (with local_only=True for each)
        # IMPORTANT: Private definitions in namespaces will be excluded by the namespace's
        # lookup_function with local_only=True
        found_results = []
        found_namespaces = []

        for ns_name, ns_module in self.namespaces.items():
            try:
                result = ns_module.lookup_function(partial_path, local_only=True)
                # Additional check: exclude private definitions from other modules
                # For functions, result is a list of overloads; check the first one
                if result and result[0].is_private and result[0].module != self:
                    continue
                found_results.append(result)
                found_namespaces.append(ns_name)
            except ValueError:
                # Not found or ambiguous in that namespace - skip it
                continue

        if len(found_results) == 0:
            partial_str = ".".join(partial_path)
            raise ValueError(f"Function not found: |{partial_str}")
        elif len(found_results) == 1:
            return found_results[0]
        else:
            # Found in multiple namespaces - ambiguous
            partial_str = ".".join(partial_path)
            ns_list = ", ".join(f"/{ns}" for ns in found_namespaces)
            raise ValueError(
                f"Ambiguous function reference |{partial_str} found in multiple namespaces: {ns_list}"
            )

    def prepare(self, ast_module, engine=None):
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

    def _phase1_create_definitions(self, ast_module, engine):
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

            elif isinstance(op, ast.HandleDef):
                # Create handle definition
                # Skip if already exists (module was already evaluated)
                full_name = ".".join(op.path)
                if full_name not in self.handles:
                    self.define_handle(op.path)

            elif isinstance(op, ast.ShapeDef):
                # Create shape definition with empty fields initially
                # Fields will be resolved in phase 4
                # Skip if already exists (module was already evaluated)
                full_name = ".".join(op.path)
                if full_name not in self.shapes:
                    self.define_shape(op.path, fields=[])

            elif isinstance(op, ast.FuncDef):
                # Create placeholder function definition for pre-resolution
                # This will be replaced during module execution (FuncDef.evaluate())
                full_name = ".".join(op.path)
                if full_name not in self.functions:
                    # Create placeholder - marked with _placeholder flag
                    placeholder = comp.FunctionDefinition(
                        path=op.path,
                        module=self,
                        body=None,  # Body will be set during evaluation
                        input_shape=None,
                        arg_shape=None,
                        is_pure=op.is_pure,
                        doc=op.doc,
                        impl_doc=op.impl_doc,
                        _placeholder=True,  # Mark as placeholder
                        is_private=getattr(op, 'is_private', False)
                    )
                    self.functions[full_name] = [placeholder]

            # ImportDef is handled in phase 2

    def _phase2_prepare_imports(self, ast_module, engine):
        """Phase 2: Walk all imports and recursively prepare each imported module.

        This processes import statements and ensures all dependencies are prepared
        before we build the resolution namespace. This allows circular imports to work.

        Args:
            ast_module: AST Module node
            engine: Engine instance for loading modules
            
        Raises:
            ValueError: If any import fails to load
        """
        from . import ast
        import comp

        for op in ast_module.operations:
            if isinstance(op, ast.ImportDef):
                # Load the imported module
                imported_module = self._load_import(op, engine)

                # Check if import failed (returned a fail Value)
                if isinstance(imported_module, comp.Value) and imported_module.is_fail:
                    # Convert fail Value to Python exception to stop preparation immediately
                    # Extract the error message from the fail structure
                    try:
                        msg_key = comp.Value('message')
                        if isinstance(imported_module.data, dict) and msg_key in imported_module.data:
                            error_msg = imported_module.data[msg_key].to_python()  # type: ignore
                        else:
                            error_msg = "Unknown import error"
                    except Exception:
                        error_msg = "Unknown import error"
                    raise ValueError(f"Import failed: {error_msg}")

                # Module loaded successfully
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

    def _load_import(self, import_def, engine):
        """Load an imported module based on ImportDef.

        This handles different import sources (stdlib, comp, python, etc.)
        and returns the loaded Module or a fail Value.

        Args:
            import_def: ImportDef AST node
            engine: Engine for evaluation

        Returns:
            Loaded Module, or fail Value if loading failed
        """
        if import_def.source == "stdlib":
            from .corelib import get_stdlib_module
            try:
                return get_stdlib_module(import_def.path)
            except Exception as e:
                import comp
                return comp.fail(f"Failed to load stdlib module '{import_def.path}': {e}")

        elif import_def.source == "comp":
            from .ast import _loader
            try:
                return _loader.load_comp_module(import_def.path, engine)
            except Exception as e:
                import comp
                return comp.fail(f"Failed to load comp module '{import_def.path}': {e}")

        # Other sources not yet implemented
        import comp
        return comp.fail(f"Import source '{import_def.source}' not yet implemented")

    def _phase3_build_resolution_namespace(self):
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

    def _add_local_definitions_to_ns(self, resolution_ns):
        """Add all local definitions to the resolution namespace.

        For each definition, generates all possible partial references and
        adds them to the resolution namespace.

        Args:
            resolution_ns: Resolution namespace dictionary to populate
        """
        # Add tags - generate all possible partial prefixes
        for tag_def in self.tags.values():
            # Note: Private definitions ARE included in the local resolution namespace
            # They can be accessed within the module itself, but will be filtered out
            # when imported by other modules (in _add_namespace_definitions_to_ns)
                
            # Generate all partial paths (prefix matching from end)
            # E.g., ["status", "error", "timeout"] generates reference paths:
            #   ("timeout",)  - matches #timeout
            #   ("error", "timeout")  - matches #error.timeout
            #   ("status", "error", "timeout")  - matches #status.error.timeout
            # Note: tag_def.path is in definition order ["status", "error", "timeout"]
            # References are also in natural order, matching from end
            for i in range(len(tag_def.path)):
                # Take suffix of definition path (no reversing needed)
                partial = tuple(tag_def.path[i:])
                key = ('tag', partial, None)  # None = no explicit namespace

                if key in resolution_ns:
                    # Already exists - mark as ambiguous
                    if resolution_ns[key] != 'AMBIGUOUS':
                        resolution_ns[key] = 'AMBIGUOUS'
                else:
                    resolution_ns[key] = tag_def

        # Add shapes - generate all possible partial prefixes
        for shape_def in self.shapes.values():
            # Private definitions included in local namespace
                
            for i in range(len(shape_def.path)):
                partial = tuple(shape_def.path[i:])
                key = ('shape', partial, None)

                if key in resolution_ns:
                    if resolution_ns[key] != 'AMBIGUOUS':
                        resolution_ns[key] = 'AMBIGUOUS'
                else:
                    resolution_ns[key] = shape_def

        # Add functions - generate all possible partial prefixes
        for _func_name, func_overloads in self.functions.items():
            if func_overloads:
                func_def = func_overloads[0]  # Use first overload for path
                # Private definitions included in local namespace
                    
                for i in range(len(func_def.path)):
                    partial = tuple(func_def.path[i:])
                    key = ('function', partial, None)

                    if key in resolution_ns:
                        if resolution_ns[key] != 'AMBIGUOUS':
                            resolution_ns[key] = 'AMBIGUOUS'
                    else:
                        resolution_ns[key] = func_overloads  # Store all overloads

    def _add_namespace_definitions_to_ns(self, resolution_ns, ns_name, ns_module):
        """Add definitions from a namespace to the resolution namespace.

        Definitions from namespaces are added with lower priority than local definitions.
        They are added both with and without explicit namespace qualifiers.

        IMPORTANT: Only definitions that are locally defined in ns_module are added.
        Definitions inherited from ns_module's dependencies are NOT included to avoid
        namespace pollution (e.g., if loop.comp imports builtin, we don't want builtin's
        definitions appearing in the loop namespace when someone imports loop).

        Args:
            resolution_ns: Resolution namespace dictionary to populate
            ns_name: Name of the namespace
            ns_module: Module to import definitions from
        """
        # Add tags from namespace (only local definitions)
        for tag_def in ns_module.tags.values():
            # Skip definitions inherited from dependencies
            if tag_def.module != ns_module:
                continue
            
            # Skip private definitions - they're not exported
            if tag_def.is_private:
                continue
            
            # Add with explicit namespace qualifier
            for i in range(len(tag_def.path)):
                partial = tuple(tag_def.path[i:])

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

        # Add shapes from namespace (only local definitions)
        for shape_def in ns_module.shapes.values():
            # Skip definitions inherited from dependencies
            if shape_def.module != ns_module:
                continue
            
            # Skip private definitions
            if shape_def.is_private:
                continue
            
            for i in range(len(shape_def.path)):
                partial = tuple(shape_def.path[i:])

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

        # Add functions from namespace (only local definitions)
        for _func_name, func_overloads in ns_module.functions.items():
            if func_overloads:
                func_def = func_overloads[0]
                # Skip definitions inherited from dependencies
                if func_def.module != ns_module:
                    continue
                
                # Skip private definitions
                if func_def.is_private:
                    continue
                
                for i in range(len(func_def.path)):
                    partial = tuple(func_def.path[i:])

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

    def _phase4_preresolve_references(self, ast_module, resolution_ns):
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

    def _preresolve_tag_def(self, tag_def, resolution_ns):
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

    def _preresolve_shape_def(self, shape_def, resolution_ns):
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

    def _preresolve_func_def(self, func_def, resolution_ns):
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

    def _preresolve_node(self, node, resolution_ns):
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

        elif isinstance(node, ast.PipeFunc):
            # Pre-resolve pipeline function calls
            func_path = node.func_name.split('.')
            func_path_reversed = list(reversed(func_path))
            key = ('function', tuple(func_path_reversed), node.namespace)
            
            if key not in resolution_ns:
                ns_str = f"/{node.namespace}." if node.namespace else ""
                position = getattr(node, 'position', None)
                pos_str = f" {position}" if position else ""
                raise ValueError(f"Undefined function in pipeline: |{ns_str}{node.func_name}{pos_str}")

            resolved = resolution_ns[key]
            if resolved == 'AMBIGUOUS':
                position = getattr(node, 'position', None)
                pos_str = f" {position}" if position else ""
                raise ValueError(f"Ambiguous function reference in pipeline: |{node.func_name}{pos_str}")

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

