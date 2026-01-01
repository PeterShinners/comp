"""Module represents a module's namespace at runtime"""

import os

import comp
from ._namespace import OverloadSet, Ambiguous


__all__ = ["Module", "OverloadSet", "Ambiguous"]


class Module:
    """A module in the Comp language.

    The module represents the data and code from source code. The module
    is not immediately parsed or loaded into this class. Methods like
    `scan` and `definitions` will incrementally build and prepare
    the module.

    Modules are created and managed by an Interp.
    
    Modules will import and reference other modules with import statements.
    Each import statement can use different compilers and resource locators
    but will always result in this same Module object.
        
    Modules are immutable once finalized. The finalize() method must be called
    before any code from the module can be compiled or executed.
    
    Args:
        source: ModuleSource containing the module's location and content

    """
    _token_counter = os.getpid() & 0xFFFF

    def __init__(self, source):
        if not hasattr(source, 'resource'):
            raise TypeError(f"Module requires a ModuleSource, got {type(source)}")

        self.source = source
        token = source.resource

        # Module token is not attempting to be a secure id,
        # Just to help distinguish conflicting tokens with a non repeating id
        count = hash(token) & 0xFFFF ^ Module._token_counter
        Module._token_counter += 1
        self.token = f"{token}#{count:04x}"

        # Intermediate cached parse passes
        self._scan = None
        self._definitions = None
        self._namespace = None
        self._finalized = False

    def __repr__(self):
        return f"Module<{self.token}>"

    def __hash__(self):
        return id(self.token)

    @property
    def is_finalized(self):
        """(bool) Whether the module has been finalized."""
        return self._finalized

    def scan(self):
        """Scan source for imports and metadata (fast, no full parse).

        This is a lightweight operation that extracts module metadata without
        doing a full parse. Useful for dependency resolution and tooling.

        This parse is fairly resilient to simple syntax errors, and 
        may be able to provide module information even when a full parse
        would fail.

        Results are cached.
        
        Returns:
            ScanResult: Object with .imports(), .package(), .docs() methods
        """

        if self._scan is None:
            self._scan = comp._scan.scan(self.source.content)
        return self._scan

    def definitions(self):
        """Parse source and extract definitions into module.definitions dict.
        
        This method lazily parses and extracts definitions on first call.
        Subsequent calls are no-ops if definitions already populated.

        Results are cached.

        Returns:
            dict: qualified names strings to Value objects
        """
        if self._definitions is not None:
            return self._definitions

        cop_tree = comp._parse.parse(self.source.content)
        self._definitions = comp.extract_definitions(cop_tree)
        return self._definitions

    def namespace(self, imports=None):
        """(dict) Resolved namespace dict for identifier lookups.

        Keys are qualified name strings, values are (priority, Value) tuples.
        Priority indicates the source of the definition:
        -1: system builtins
         0: imported module definitions
         1: local module definitions
        """
        if self._namespace is not None:
            return self._namespace

        if imports is None:
            imports = {}
        defs = self.definitions()

        from ._namespace import NamespaceBuilder
        nb = NamespaceBuilder()

        # Add system module builtins (priority -1)
        if not isinstance(self, SystemModule):
            system_module = SystemModule.get()
            nb.add_system_builtins(system_module.namespace())

        # Add imported module definitions (priority 0)
        for import_name, imported_module in imports.items():
            nb.add_module_definitions(
                imported_module.definitions,
                import_prefix=import_name,
                is_local=False
            )

        # Add local definitions (priority 1)
        nb.add_module_definitions(defs, is_local=True)

        # Create Tag values for tag union definitions
        _populate_tag_union_values(self, nb)

        # Export namespace from builder
        self._namespace = nb.to_dict()
        return self._namespace

    def finalize(self, imports=None):
        """Build namespace and resolve identifiers. Auto-calls definitions if needed.

        Args:
            imports: Dict {import_name: Module} of resolved imports

        Returns:
            self (for chaining)
        """
        namespace = self.namespace(imports=imports)

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
        self._definitions = {}
        self._definitions['nil'] = comp.Value.from_python(comp.tag_nil)
        self._definitions['bool'] = comp.Value.from_python(comp.tag_bool)
        self._definitions['bool.true'] = comp.Value.from_python(comp.tag_true)
        self._definitions['bool.false'] = comp.Value.from_python(comp.tag_false)
        self._definitions['true'] = comp.Value.from_python(comp.tag_true)
        self._definitions['false'] = comp.Value.from_python(comp.tag_false)
        self._definitions['fail'] = comp.Value.from_python(comp.tag_fail)

        # Builtin shapes - wrap in Value objects
        self._definitions['num'] = comp.Value.from_python(comp.shape_num)
        self._definitions['text'] = comp.Value.from_python(comp.shape_text)
        self._definitions['struct'] = comp.Value.from_python(comp.shape_struct)
        self._definitions['any'] = comp.Value.from_python(comp.shape_any)
        self._definitions['func'] = comp.Value.from_python(comp.shape_func)

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


def _populate_tag_union_values(module, namespace_builder):
    """Populate namespace with Tag values for tag union definitions.

    Tag unions are Shape definitions with qualified names starting with "tag.".
    For example, "tag.binary" with fields (zero one) creates:
    - binary (parent tag)
    - binary.zero and binary.one (leaf tags)

    For hierarchical tags like "tag.binary.quantum", creates:
    - binary (parent tag)
    - binary.quantum (hierarchical tag)

    Args:
        module: Module with definitions
        namespace_builder: NamespaceBuilder to add tag values to
    """
    # Collect all tag union definitions
    # Tag unions must be Shape definitions: tag.binary = ~(zero one)
    # Use ~() for empty tag unions (not plain ())
    tag_unions = []
    for qualified_name, value in module._definitions.items():
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
            namespace_builder.add_definition(
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
                namespace_builder.add_definition(
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
    if comp.cop_tag(id_cop) != "value.identifier":
        return None

    parts = []
    for kid in comp.cop_kids(id_cop):
        kid_tag = comp.cop_tag(kid)
        if kid_tag in ("ident.token", "ident.text"):
            parts.append(kid.field("value").data)
        else:
            return None  # Complex identifier
    return '.'.join(parts) if parts else None


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

    tag = comp.cop_tag(cop)

    # Handle value.identifier - try to resolve it
    if tag == "value.identifier":
        name = _get_identifier_name(cop)

        # Skip if we couldn't extract a name
        if name is None:
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
        kids_list = comp.cop_kids(cop)
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
                kids_field = cop.field("kids")
                new_kids_dict = kids_field.data.copy()
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
            # Walk each kid
            modified = False
            new_kids_dict = {}
            for key, kid in cop.field("kids").data.items():
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

    for qualified_name, value in list(module._definitions.items()):
        # Only process values that have COP trees
        if not hasattr(value, 'cop') or value.cop is None:
            continue

        # Step 1: Walk and resolve identifier references
        resolved_cop = _walk_and_resolve_cop(value.cop, module._namespace)

        # Step 2: Perform constant folding on the resolved tree
        folded_cop = comp._parse.cop_fold(resolved_cop)

        # Update the cop if it changed
        if folded_cop is not value.cop:
            # Special case: if the original value was just an identifier (value.identifier)
            # and it resolved to a constant, replace the entire definition with the resolved value
            try:
                # Check the original cop (before we modify it)
                orig_tag = comp.cop_tag(value)
                folded_tag = comp.cop_tag(folded_cop)
                if orig_tag == "value.identifier" and folded_tag == "value.constant":
                    # Extract the resolved value from the constant
                    resolved_value = folded_cop.field("value")
                    # Preserve the original cop for debugging
                    resolved_value.cop = folded_cop
                    # Replace in definitions
                    module._definitions[qualified_name] = resolved_value
                    replaced_definitions[qualified_name] = resolved_value
                    # Skip the cop update since we're replacing the entire value
                    continue
            except (AttributeError, KeyError):
                pass

            # Update the cop on the existing value
            value.cop = folded_cop

    # Update namespace entries for replaced definitions
    # We need to regenerate the permutations using the same logic as NamespaceBuilder
    for qualified_name, new_value in replaced_definitions.items():
        # Generate name permutations (same logic as NamespaceBuilder._generate_permutations)
        from ._namespace import NamespaceBuilder
        nb = NamespaceBuilder()
        permutations = nb._generate_permutations(qualified_name, import_prefix=None)

        for perm in permutations:
            # Update the namespace entry if it exists
            if perm in module.namespace:
                priority, _ = module.namespace[perm]
                module.namespace[perm] = (priority, new_value)
