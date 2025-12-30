"""Module represents a module's namespace at runtime"""

import os

import comp


__all__ = ["Module", "OverloadSet", "Ambiguous"]


class Module:
    """A module in the Comp language.

    Namespaces are used to organize and scope identifiers in the language.
    They provide a way to group related definitions and prevent naming conflicts.

    Modules are immutable once finalized. The finalize() method must be called
    before any code from the module can be compiled or executed.

    Args:
        source: ModuleSource containing the module's location and content
                If None, creates a module without a source (e.g., system module)

    """

    _token_counter = os.getpid() & 0xFFFF

    def __init__(self, source):
        """Initialize a module from a ModuleSource.

        Args:
            source: ModuleSource containing the module's location and content

        Raises:
            TypeError: If source is not a ModuleSource
        """
        if not hasattr(source, 'resource'):
            raise TypeError(f"Module requires a ModuleSource, got {type(source)}")

        self.source = source
        token = source.resource

        # Module token is not attempting to be a secure id,
        # Just to help distinguish conflicting tokens with a non repeating id
        count = hash(token) & 0xFFFF ^ Module._token_counter
        Module._token_counter += 1
        self.token = f"{token}#{count:04x}"

        self.definitions = {}  # All module definitions {qualified_name: Value}

        # Populated by finalize()
        self.namespace = None  # Resolved namespace dict for lookups
        self._finalized = False

    @classmethod
    def from_source(cls, source):
        """Create a Module from a ModuleSource.

        The provided Module is not prepared or finalized. It will need the
        `load_definitions()` and `finalize()` to prepare its contents for use.
        
        Args:
            source: (str) raw text for module
        """
        modsrc = comp._import.ModuleSource(
            resource="source",
            location="source",
            source_type="from_source",
            etag="str",
            content=source,
            anchor="",
        )
        return cls(modsrc)

    def __repr__(self):
        return f"Module<{self.token}>"

    def __hash__(self):
        return id(self.token)

    @property
    def is_finalized(self):
        """(bool) Whether the module has been finalized."""
        return self._finalized

    def load_definitions(self):
        """Parse source and extract definitions into module.definitions dict.

        This method lazily parses and extracts definitions on first call.
        Subsequent calls are no-ops if definitions already populated.

        Returns:
            self (for chaining)

        Raises:
            ValueError: If module has no source to parse
            ParseError: If source cannot be parsed
            CodeError: If definitions extraction fails
        """
        # Skip if already loaded
        if self.definitions:
            return self

        if self.source is None:
            raise ValueError("Cannot load module without source")

        # Parse the source content into COP nodes
        cop_tree = comp.parse(self.source.content)

        # Temporarily store cop_tree for extract_definitions to use
        self._temp_cop_tree = cop_tree

        # Extract definitions - this populates self.definitions and self.package
        # We don't keep cop_tree stored - it's preserved in each Value's .cop attribute
        comp.extract_definitions(self)

        # Clean up temporary tree
        del self._temp_cop_tree

        return self

    def get_imports(self):
        """Get list of immediate import dependencies from scan metadata.

        Returns:
            List of (name, resource) tuples, where:
                name: The import binding name (e.g., 'cart')
                resource: The module resource string (e.g., './examples/cart')

        Returns empty list if no scan metadata or no imports.
        """
        if not hasattr(self, '_scan_metadata') or self._scan_metadata is None:
            return []

        try:
            imports_val = self._scan_metadata.field('imports')
        except (KeyError, AttributeError):
            return []

        if not hasattr(imports_val, 'data') or not isinstance(imports_val.data, dict):
            return []

        result = []
        for import_item in imports_val.data.values():
            try:
                name = import_item.field('name').data
                resource = import_item.field('source').data
                result.append((name, resource))
            except (KeyError, AttributeError):
                continue

        return result

    def get_package(self):
        """Extract package metadata (pkg.* assignments) from definitions.

        Returns:
            dict: {pkg_name: value} for all pkg.* definitions
        """
        package = {}
        for name, value in self.definitions.items():
            if name.startswith('pkg.'):
                # Extract the actual data from the Value
                package[name] = value.data if hasattr(value, 'data') else value
        return package

    def finalize(self, imports=None):
        """Finalize module and build namespace.

        This populates the namespace dictionary for fast lookup based on
        local definitions and imported module definitions. Then resolves
        all identifier references in COP trees to namespace values.

        Args:
            imports: Dict {import_name: Module} of resolved imports.
                     The Interpreter/loader is responsible for resolving
                     import resource strings to actual Module instances.

        The namespace contains (priority, value) tuples where:
        - priority: 0=imported, 1=local (for shadowing)
        - value: Value, OverloadSet, or Ambiguous

        Returns:
            self (for chaining)
        """
        if self._finalized:
            return self

        imports = imports or {}

        # Initialize empty namespace
        self.namespace = {}

        # First, add system module builtins with priority=-1 (lowest)
        # Skip this for SystemModule itself to avoid infinite recursion
        if not isinstance(self, SystemModule):
            system_module = SystemModule.get()
            for lookup_name, (_, value) in system_module.namespace.items():
                # Add with priority -1 (lower than imports which are 0)
                if lookup_name not in self.namespace:
                    self.namespace[lookup_name] = (-1, value)

        # Then, add all imported module definitions with priority=0
        for import_name, imported_module in imports.items():
            # Add all definitions from the imported module
            for qualified_name, value in imported_module.definitions.items():
                # Skip pkg.* definitions from imports
                if qualified_name.startswith('pkg.'):
                    continue

                _add_definition_to_namespace(
                    self.namespace,
                    qualified_name,
                    value,
                    import_prefix=import_name,
                    is_local=False
                )

        # Then, add local definitions with priority=1 (can shadow imports)
        for qualified_name, value in self.definitions.items():
            # Skip pkg.* definitions (not part of namespace)
            if qualified_name.startswith('pkg.'):
                continue

            # Skip tag.* definitions (they define tag unions, not namespace entries)
            # The individual tag values will be added by _populate_tag_union_values
            if qualified_name.startswith('tag.'):
                continue

            _add_definition_to_namespace(
                self.namespace,
                qualified_name,
                value,
                import_prefix=None,
                is_local=True
            )

        # Create Tag values for tag union definitions
        # Tag unions are Shapes with qualified names starting with "tag."
        _populate_tag_union_values(self)

        # Finally, resolve all identifier references in COP trees
        _resolve_identifier_references(self)

        self._finalized = True
        return self


class SystemModule(Module):
    """System module singleton with several builtin attributes"""

    _singleton = None

    def __init__(self):
        # Create a minimal ModuleSource for system module
        source = type('obj', (object,), {'resource': 'system', 'content': ''})()
        super().__init__(source)
        self.token = "system#0000"

        # Populate definitions dict with builtin tags and shapes as Value objects
        # These will be finalized and added to namespace

        # Builtin tags - wrap in Value objects
        self.definitions['nil'] = comp.Value.from_python(comp.tag_nil)
        self.definitions['bool'] = comp.Value.from_python(comp.tag_bool)
        self.definitions['bool.true'] = comp.Value.from_python(comp.tag_true)
        self.definitions['bool.false'] = comp.Value.from_python(comp.tag_false)
        self.definitions['true'] = comp.Value.from_python(comp.tag_true)
        self.definitions['false'] = comp.Value.from_python(comp.tag_false)
        self.definitions['fail'] = comp.Value.from_python(comp.tag_fail)

        # Builtin shapes - wrap in Value objects
        self.definitions['num'] = comp.Value.from_python(comp.shape_num)
        self.definitions['text'] = comp.Value.from_python(comp.shape_text)
        self.definitions['struct'] = comp.Value.from_python(comp.shape_struct)
        self.definitions['any'] = comp.Value.from_python(comp.shape_any)
        self.definitions['func'] = comp.Value.from_python(comp.shape_func)

        # Set convenience attributes for direct access
        self.bool = comp.tag_bool
        self.true = comp.tag_true
        self.false = comp.tag_false
        self.fail = comp.tag_fail
        self.num = comp.shape_num
        self.text = comp.shape_text
        self.struct = comp.shape_struct
        self.any = comp.shape_any
        self.func = comp.shape_func

        # Finalize to build namespace from definitions
        self.finalize()

    @classmethod
    def get(cls):
        """Get system module singleton."""
        # Constructed lazy for first interpreter
        global _system_module
        if SystemModule._singleton is None:
            SystemModule._singleton = cls()
        return SystemModule._singleton


class OverloadSet:
    """Collection of overloaded callables sharing the same name.

    Used when a name has multiple definitions (function overloads,
    or a shape + factory functions, etc.). Separates shape definitions
    from callable definitions to handle both ~Shape and Shape() contexts.
    """

    def __init__(self):
        self.shape = None       # Shape Value if one exists
        self.callables = []     # List of callable Values (Func, may include shape)

    def add_shape(self, shape_value):
        """Add a shape definition. Also adds to callables (shapes are callable)."""
        self.shape = shape_value
        if shape_value not in self.callables:
            self.callables.append(shape_value)

    def add_callable(self, func_value):
        """Add a callable (function) definition."""
        self.callables.append(func_value)

    def get_for_shape_context(self):
        """Get the value for ~name lookup."""
        if self.shape is None:
            raise TypeError("Name is not a shape")
        return self.shape

    def get_for_call_context(self):
        """Get candidates for name() call dispatch."""
        return self.callables

    def get_single(self):
        """Get single value if unambiguous, else return self for dispatch."""
        if len(self.callables) == 1:
            return self.callables[0]
        return self

    def __repr__(self):
        parts = []
        if self.shape:
            parts.append(f"shape={self.shape.data.qualified if hasattr(self.shape.data, 'qualified') else 'shape'}")
        parts.append(f"{len(self.callables)} callable(s)")
        return f"OverloadSet({', '.join(parts)})"


class Ambiguous:
    """Represents a name conflict in the namespace.

    Created when multiple non-overloadable definitions share the same
    unqualified name. This is an error condition that gets caught at
    build time when the name is referenced.
    """

    def __init__(self, qualified_names):
        self.qualified_names = list(qualified_names)

    def add_conflict(self, qualified_name):
        """Add another conflicting name."""
        if qualified_name not in self.qualified_names:
            self.qualified_names.append(qualified_name)

    def __repr__(self):
        return f"Ambiguous({', '.join(self.qualified_names)})"


def _strip_overload_suffix(qualified_name):
    """Strip .iXXX overload suffix from qualified name if present.

    Args:
        qualified_name: e.g., 'add.i001' or 'display.set_mode.i123'

    Returns:
        Base name without overload suffix, e.g., 'add' or 'display.set_mode'
    """
    if '.' not in qualified_name:
        return qualified_name

    parts = qualified_name.split('.')
    last_part = parts[-1]

    # Check if last part is .iXXX format
    if last_part.startswith('i') and len(last_part) > 1 and last_part[1:].isdigit():
        return '.'.join(parts[:-1])

    return qualified_name


def _generate_name_permutations(qualified_name, import_prefix=None):
    """Generate all valid lookup names for a qualified name.

    Args:
        qualified_name: e.g., 'display.set_mode.i001'
        import_prefix: e.g., 'pg' if imported, None if local

    Returns:
        List of lookup names to insert into namespace

    Examples:
        _generate_name_permutations('display.set_mode.i001')
        → ['display.set_mode', 'set_mode']

        _generate_name_permutations('display.set_mode', 'pg')
        → ['pg.display.set_mode', 'display.set_mode', 'set_mode']
    """
    # Strip .iXXX suffix (don't expose in namespace)
    base_name = _strip_overload_suffix(qualified_name)

    # Generate permutations from the base name
    permutations = []
    parts = base_name.split('.')

    # Add import-prefixed version if this is an imported definition
    if import_prefix:
        permutations.append(f"{import_prefix}.{base_name}")

    # Add all partial suffixes (e.g., 'display.set_mode', 'set_mode')
    for i in range(len(parts)):
        permutations.append('.'.join(parts[i:]))

    return permutations


def _insert_into_namespace(namespace, lookup_name, qualified_name, value, priority):
    """Insert a value into namespace with proper conflict/overload handling.

    Args:
        namespace: Dict to insert into (key → (priority, value/OverloadSet/Ambiguous))
        lookup_name: The exact name to insert at (e.g., 'set_mode', 'pg.display.set_mode')
        qualified_name: Full qualified name for error messages
        value: The Value to insert
        priority: 0=imported, 1=local (for shadowing)
    """
    existing = namespace.get(lookup_name)

    # Case 1: No existing entry - insert directly
    if existing is None:
        namespace[lookup_name] = (priority, value)
        return

    existing_priority, existing_value = existing

    # Case 2: Lower priority - don't insert (shadowed by local definition)
    if priority < existing_priority:
        return

    # Case 3: Higher priority - replace (local shadows import)
    if priority > existing_priority:
        namespace[lookup_name] = (priority, value)
        return

    # Case 4: Same priority - need to merge or create Ambiguous
    # Extract qualified name for error reporting
    def get_qualified_name(val):
        if isinstance(val, Ambiguous):
            return None  # Already ambiguous
        if isinstance(val, OverloadSet):
            # Get qualified name from first callable
            if val.callables:
                return val.callables[0].data.qualified if hasattr(val.callables[0].data, 'qualified') else None
        if hasattr(val, 'data') and hasattr(val.data, 'qualified'):
            return val.data.qualified
        return None

    # Handle Ambiguous existing value
    if isinstance(existing_value, Ambiguous):
        existing_value.add_conflict(qualified_name)
        return

    # Handle OverloadSet existing value
    if isinstance(existing_value, OverloadSet):
        if isinstance(value.data, comp.Shape):
            if existing_value.shape is not None:
                # Two shapes with same name = ambiguous
                namespace[lookup_name] = (priority, Ambiguous([
                    existing_value.shape.data.qualified,
                    qualified_name
                ]))
            else:
                existing_value.add_shape(value)
        elif isinstance(value.data, comp.Func):
            existing_value.add_callable(value)
        else:
            # Non-callable conflicts with OverloadSet
            existing_qualified = get_qualified_name(existing_value)
            if existing_qualified:
                namespace[lookup_name] = (priority, Ambiguous([existing_qualified, qualified_name]))
        return

    # Both are single Values - determine if we can create OverloadSet
    existing_is_callable = isinstance(existing_value.data, (comp.Func, comp.Shape))
    new_is_callable = isinstance(value.data, (comp.Func, comp.Shape))

    if existing_is_callable and new_is_callable:
        # Both callable - create OverloadSet
        overloads = OverloadSet()

        # Add existing
        if isinstance(existing_value.data, comp.Shape):
            overloads.add_shape(existing_value)
        else:
            overloads.add_callable(existing_value)

        # Add new
        if isinstance(value.data, comp.Shape):
            overloads.add_shape(value)
        else:
            overloads.add_callable(value)

        namespace[lookup_name] = (priority, overloads)
    else:
        # Incompatible types - create Ambiguous
        existing_qualified = get_qualified_name(existing_value) or lookup_name
        namespace[lookup_name] = (priority, Ambiguous([existing_qualified, qualified_name]))


def _add_definition_to_namespace(namespace, qualified_name, value, import_prefix=None, is_local=True):
    """Add a definition to namespace with all its permutations.

    Args:
        namespace: The namespace dict
        qualified_name: e.g., 'display.set_mode' or 'display.set_mode.i001'
        value: The Value
        import_prefix: e.g., 'pg' if imported, None if local
        is_local: True for module's own defs, False for imported
    """
    priority = 1 if is_local else 0
    permutations = _generate_name_permutations(qualified_name, import_prefix)

    for perm in permutations:
        _insert_into_namespace(namespace, perm, qualified_name, value, priority)


def _populate_tag_union_values(module):
    """Populate namespace with Tag values for tag union definitions.

    Tag unions are Shape definitions with qualified names starting with "tag.".
    For example, "tag.binary" with fields (zero one) creates:
    - binary (parent tag)
    - binary.zero and binary.one (leaf tags)

    For hierarchical tags like "tag.binary.quantum", creates:
    - binary (parent tag)
    - binary.quantum (hierarchical tag)

    Args:
        module: Module with namespace to populate
    """
    # Collect all tag union definitions
    # Tag unions must be Shape definitions: tag.binary = ~(zero one)
    # Use ~() for empty tag unions (not plain ())
    tag_unions = []
    for qualified_name, value in module.definitions.items():
        if not qualified_name.startswith('tag.'):
            continue

        # Only accept Shape definitions
        if isinstance(value.data, comp.Shape):
            tag_unions.append((qualified_name, value))

    # Track which tag names we've already created to avoid duplicates
    created_tags = set()

    for qualified_name, value in tag_unions:
        # Extract the tag union name (remove "tag." prefix)
        union_name = qualified_name[4:]  # Remove "tag." prefix

        # Get the shape
        shape = value.data
        private = shape.private

        # Create parent tag (e.g., "binary" for "tag.binary")
        # This allows using just the parent name as a tag
        if union_name and union_name not in created_tags:
            parent_tag = comp.Tag(union_name, private)
            parent_tag.module = module
            parent_tag_value = comp.Value.from_python(parent_tag)
            _add_definition_to_namespace(
                module.namespace,
                union_name,
                parent_tag_value,
                import_prefix=None,
                is_local=True
            )
            created_tags.add(union_name)

        # For each field in the shape, create a tag value
        for field_def in shape.fields:
            if not field_def.name:
                continue

            field_name = field_def.name
            tag_qualified = f"{union_name}.{field_name}"
            if tag_qualified not in created_tags:
                tag = comp.Tag(tag_qualified, private)
                tag.module = module
                tag_value = comp.Value.from_python(tag)

                # Add to namespace with all permutations
                _add_definition_to_namespace(
                    module.namespace,
                    tag_qualified,
                    tag_value,
                    import_prefix=None,
                    is_local=True
                )
                created_tags.add(tag_qualified)


def _get_identifier_name(id_cop):
    """Extract the qualified name from a value.identifier COP node.

    Args:
        id_cop: A value.identifier COP node

    Returns:
        String like "add" or "server.host" or None if not a valid identifier
    """
    try:
        tag = id_cop.positional(0).data.qualified
        if tag != "value.identifier":
            return None

        kids = id_cop.field("kids")
        parts = []
        for kid in kids.data.values():
            kid_token = kid.positional(0).data.qualified
            if kid_token in ("ident.token", "ident.text"):
                part = kid.field("value").data
                parts.append(part)
            else:
                # Complex identifier (expr, index, etc.) - can't resolve at finalize time
                return None
        return '.'.join(parts) if parts else None
    except (AttributeError, KeyError):
        return None


def _walk_and_resolve_cop(cop, namespace, param_names=None):
    """Walk a COP tree and resolve identifier references to namespace values.

    Replaces value.identifier nodes with value.constant nodes containing the
    resolved Value from the namespace.

    Args:
        cop: The COP node to walk
        namespace: Module namespace dict {name: (priority, value)}
        param_names: Set of parameter names to skip (handled by codegen)

    Returns:
        Potentially modified COP node
    """
    if cop is None:
        return cop

    param_names = param_names or set()

    try:
        tag = cop.positional(0).data.qualified
    except (AttributeError, KeyError):
        return cop

    # Handle value.identifier - try to resolve it
    if tag == "value.identifier":
        name = _get_identifier_name(cop)

        # Skip if we couldn't extract a name
        if name is None:
            return cop

        # Skip $ references (local scope, handled by codegen)
        if name == '$' or name.startswith('$.'):
            return cop

        # Skip parameter names (handled by codegen)
        if name in param_names:
            return cop

        # Try to resolve from namespace
        namespace_entry = namespace.get(name)
        if namespace_entry is not None:
            _, resolved_value = namespace_entry

            # Handle special namespace types
            if isinstance(resolved_value, (Ambiguous, OverloadSet)):
                # Can't resolve to constant - these will need special handling
                # For now, leave as identifier (will be handled at build/call time)
                return cop

            # If the resolved value has a finalized .cop that is a constant, use that COP directly
            # This ensures we get the folded constant value instead of the original COP structure
            if hasattr(resolved_value, 'cop') and resolved_value.cop is not None:
                try:
                    cop_tag = resolved_value.cop.positional(0).data.qualified
                    if cop_tag == "value.constant":
                        # The resolved value is already a finalized constant - use its COP directly
                        return resolved_value.cop
                except (AttributeError, KeyError):
                    pass

            # Create a value.constant node with the resolved value
            const_cop = comp.create_cop("value.constant", [], value=resolved_value)
            return const_cop

        # Unresolved - leave as-is for now (will error at build time)
        return cop

    # Handle value.block - extract parameter names from signature
    elif tag == "value.block":
        # Get signature to extract param names
        kids = cop.field("kids")
        kids_list = list(kids.data.values())
        if len(kids_list) >= 2:
            signature_cop = kids_list[0]
            body_cop = kids_list[1]

            # Extract parameter names from signature
            new_param_names = param_names.copy()
            # TODO: Parse signature to get actual param names
            # For now, assume 'input' and 'args' are standard
            new_param_names.add('input')
            new_param_names.add('args')

            # Recursively walk the body with updated param names
            new_body = _walk_and_resolve_cop(body_cop, namespace, new_param_names)

            # If body changed, create new block cop
            if new_body is not body_cop:
                new_kids_dict = kids.data.copy()
                keys = list(new_kids_dict.keys())
                if len(keys) >= 2:
                    new_kids_dict[keys[1]] = new_body

                    # Reconstruct the cop by copying all fields and updating kids
                    new_data = {}
                    for key, value in cop.data.items():
                        if isinstance(key, comp.Value) and key.data == "kids":
                            # Replace kids with the modified version
                            new_data[key] = comp.Value.from_python(new_kids_dict)
                        else:
                            # Keep other fields as-is
                            new_data[key] = value

                    return comp.Value.from_python(new_data)

        return cop

    # For all other nodes, recursively walk kids
    else:
        try:
            kids = cop.field("kids")
            if not isinstance(kids.data, dict):
                return cop

            # Walk each kid
            modified = False
            new_kids_dict = {}
            for key, kid in kids.data.items():
                new_kid = _walk_and_resolve_cop(kid, namespace, param_names)
                new_kids_dict[key] = new_kid
                if new_kid is not kid:
                    modified = True

            # If any kids changed, create new cop with updated kids
            if modified:
                # Reconstruct the cop by copying all fields and updating kids
                new_data = {}
                for key, value in cop.data.items():
                    if isinstance(key, comp.Value) and key.data == "kids":
                        # Replace kids with the modified version
                        new_data[key] = comp.Value.from_python(new_kids_dict)
                    else:
                        # Keep other fields as-is
                        new_data[key] = value

                new_cop = comp.Value.from_python(new_data)
                return new_cop

        except (KeyError, AttributeError):
            # No kids field, nothing to walk
            pass

    return cop


def _resolve_identifier_references(module):
    """Resolve all identifier references in module definitions to namespace values.

    Walks all COP trees in module.definitions and replaces value.identifier nodes
    with value.constant nodes containing the resolved Values. Then performs constant
    folding to evaluate constant expressions.

    Args:
        module: Module with populated namespace

    Side effects:
        Modifies the .cop attribute on Values in module.definitions
        For simple identifier-only values, replaces the entire Value with the resolved constant
        Updates namespace entries when definitions are replaced
    """
    # Track which definitions were replaced so we can update the namespace
    replaced_definitions = {}

    for qualified_name, value in list(module.definitions.items()):
        # Only process values that have COP trees
        if not hasattr(value, 'cop') or value.cop is None:
            continue

        # Step 1: Walk and resolve identifier references
        resolved_cop = _walk_and_resolve_cop(value.cop, module.namespace)

        # Step 2: Perform constant folding on the resolved tree
        # Create an empty namespace for resolve() since identifiers are already resolved
        empty_namespace = comp.Value.from_python({})
        folded_cop = comp.resolve(resolved_cop, empty_namespace, no_fold=False)

        # Update the cop if it changed
        if folded_cop is not value.cop:
            # Special case: if the original value was just an identifier (value.identifier)
            # and it resolved to a constant, replace the entire definition with the resolved value
            try:
                # Check the original cop (before we modify it)
                orig_tag = value.cop.positional(0).data.qualified
                folded_tag = folded_cop.positional(0).data.qualified
                if orig_tag == "value.identifier" and folded_tag == "value.constant":
                    # Extract the resolved value from the constant
                    resolved_value = folded_cop.field("value")
                    # Preserve the original cop for debugging
                    resolved_value.cop = folded_cop
                    # Replace in definitions
                    module.definitions[qualified_name] = resolved_value
                    replaced_definitions[qualified_name] = resolved_value
                    # Skip the cop update since we're replacing the entire value
                    continue
            except (AttributeError, KeyError):
                pass

            # Update the cop on the existing value
            value.cop = folded_cop

    # Update namespace entries for replaced definitions
    for qualified_name, new_value in replaced_definitions.items():
        # Regenerate namespace entries for this definition
        permutations = _generate_name_permutations(qualified_name, import_prefix=None)
        for perm in permutations:
            # Update the namespace entry if it exists
            if perm in module.namespace:
                priority, _ = module.namespace[perm]
                module.namespace[perm] = (priority, new_value)
