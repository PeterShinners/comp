"""Module represents a module's namespace at runtime"""

import os

import comp


__all__ = ["Module"]


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
            dict: qualified names strings to Definition objects
        """
        if self._definitions is not None:
            return self._definitions

        parser = comp.lark_parser("comp")
        lark_tree = parser.parse(self.source.content)
        cop_tree = comp._parse.lark_to_cop(lark_tree)
        self._definitions = comp.extract_definitions(cop_tree, self.token)
        return self._definitions

    def namespace(self, imports=None):
        """(dict) Resolved namespace dict for identifier lookups.

        Each value is a DefinitionSet which will contain at least one definition
        and methods to help validate the various types of lookups (shape,
        call, value)
        """
        if imports is None:
            imports = {}
        if self._namespace is not None:
            return self._namespace

        # Don't try to get system module if we ARE the system module
        if isinstance(self, SystemModule):
            self._namespace = {}
        else:
            self._namespace = dict(SystemModule.get().namespace())
        for import_name, import_module in imports.items():
            import_definitions = import_module.definitions()
            import_namespace = comp._namespace.create_namespace(import_definitions, import_name)
            self._namespace = comp._namespace.merge_namespace(self._namespace, import_namespace, clobber=False)

        defs = self.definitions()
        namespace = comp._namespace.create_namespace(defs, None)
        self._namespace = comp._namespace.merge_namespace(self._namespace, namespace, clobber=True)

        return self._namespace

    def finalize(self, imports=None):
        """Build namespace and resolve identifiers. Auto-calls definitions if needed.

        Args:
            imports: Dict {import_name: Module} of resolved imports

        Returns:
            self (for chaining)
        """
        # Phase 3: Build namespace and resolve identifiers to references
        namespace = self.namespace(imports=imports)
        resolve_identifiers(self._definitions, namespace)

        # Phase 4: Constant folding - create Block/Shape values
        for definition in self._definitions.values():
            # Skip non-Definition objects (e.g., AST module Tags)
            if isinstance(definition, comp.Definition):
                fold_definition(definition)

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

        # Populate definitions dict with builtin tags and shapes as Definition objects
        # These are pre-folded since they're built-in objects

        self._definitions = {}

        # Helper to create Definition with pre-folded value
        def _create_builtin_def(name, obj, shape_type):
            value = comp.Value.from_python(obj)
            defn = comp.Definition(name, self.token, value, shape_type)
            defn.resolved_cop = value  # Already resolved
            defn.value = value  # Already folded
            return defn

        # Builtin tags - use shape_struct for tag values
        self._definitions['nil'] = _create_builtin_def('nil', comp.tag_nil, comp.shape_struct)
        self._definitions['bool'] = _create_builtin_def('bool', comp.tag_bool, comp.shape_struct)
        self._definitions['bool.true'] = _create_builtin_def('bool.true', comp.tag_true, comp.shape_struct)
        self._definitions['bool.false'] = _create_builtin_def('bool.false', comp.tag_false, comp.shape_struct)
        # Note: 'true' and 'false' shortcuts are created via namespace permutations from 'bool.true' and 'bool.false'
        self._definitions['fail'] = _create_builtin_def('fail', comp.tag_fail, comp.shape_struct)

        # Builtin shapes
        self._definitions['num'] = _create_builtin_def('num', comp.shape_num, comp.shape_shape)
        self._definitions['text'] = _create_builtin_def('text', comp.shape_text, comp.shape_shape)
        self._definitions['struct'] = _create_builtin_def('struct', comp.shape_struct, comp.shape_shape)
        self._definitions['any'] = _create_builtin_def('any', comp.shape_any, comp.shape_shape)
        self._definitions['func'] = _create_builtin_def('func', comp.shape_block, comp.shape_shape)

        # Set convenience attributes for direct access
        self.bool = comp.tag_bool
        self.true = comp.tag_true
        self.false = comp.tag_false
        self.fail = comp.tag_fail
        self.num = comp.shape_num
        self.text = comp.shape_text
        self.struct = comp.shape_struct
        self.any = comp.shape_any
        self.func = comp.shape_block

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
    for qualified_name, definition in module._definitions.items():
        if not qualified_name.startswith('tag.'):
            continue

        # Only accept Shape definitions
        if definition.shape == "shape" and definition.value and isinstance(definition.value.data, comp.Shape):
            tag_unions.append((qualified_name, definition))

    # Track which tag names we've already created to avoid duplicates
    created_tags = set()

    for qualified_name, definition in tag_unions:
        # Extract the tag union name (remove "tag." prefix)
        union_name = qualified_name[4:]  # Remove "tag." prefix

        # Get the shape from the folded definition value
        shape = definition.value.data
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


def fold_definition(definition):
    """Perform constant folding on a definition to create Shape/Block values.

    This function takes a Definition with resolved_cop and performs constant
    folding to create the final Value. For blocks, this creates Block objects.
    For shapes, this creates Shape objects.

    Args:
        definition: Definition with resolved_cop populated

    Side effects:
        Populates definition.value with the folded constant value
    """
    # Skip if already folded (e.g., SystemModule builtins)
    if definition.value is not None:
        return

    # Use resolved_cop if available, otherwise original_cop
    cop = definition.resolved_cop if definition.resolved_cop is not None else definition.original_cop

    if cop is None:
        return

    # Perform constant folding on the COP tree
    folded_cop = comp._parse.cop_fold(cop)

    # For blocks, create Block objects
    if definition.shape is comp.shape_block:
        try:
            # Extract qualified name and create Block
            private = False  # TODO: Extract from definition or cop
            func_value = comp.create_blockdef(definition.qualified, private, folded_cop)
            definition.value = func_value
            # Keep the folded COP for the function body
            definition.resolved_cop = folded_cop
        except comp.CodeError as e:
            # If can't create func, just keep folded cop
            definition.resolved_cop = folded_cop

    # For shapes, create Shape objects
    elif definition.shape is comp.shape_shape:
        try:
            # Extract qualified name and create Shape
            private = False  # TODO: Extract from definition or cop
            shape_value = comp.create_shapedef(definition.qualified, private, folded_cop)
            definition.value = shape_value
            # Shapes should have no COP after folding (fully resolved)
            definition.resolved_cop = None
        except comp.CodeError as e:
            # If can't create shape, just keep folded cop
            definition.resolved_cop = folded_cop

    # For other values, just perform constant folding
    else:
        # Try to extract constant value from folded cop
        try:
            tag = comp.cop_tag(folded_cop)
            if tag == "value.constant":
                # Extract the constant value
                definition.value = folded_cop.field("value")
                definition.resolved_cop = folded_cop
            elif tag == "value.reference":
                # Keep as reference - will be resolved at build time
                definition.resolved_cop = folded_cop
            else:
                # Keep the folded cop
                definition.resolved_cop = folded_cop
        except (AttributeError, KeyError):
            definition.resolved_cop = folded_cop


def resolve_identifiers(definitions, namespace):
    """Resolve identifiers in definitions to value.reference nodes.

    This function walks all definition COP trees and replaces value.identifier
    nodes with value.reference nodes pointing to Definition objects.

    Args:
        definitions: Dict {qualified_name: Definition} to resolve
        namespace: Namespace dict {name: (priority, value_or_definition)}

    Returns:
        dict: The namespace dictionary (for chaining)

    Side effects:
        Populates definition.resolved_cop for each definition in definitions
    """
    # Resolve identifiers in each definition
    for qualified_name, definition in definitions.items():
        # Skip non-Definition objects (e.g., AST module Tags)
        if not isinstance(definition, comp.Definition):
            continue

        if definition.original_cop is None:
            continue

        # Skip if already resolved (e.g., SystemModule builtins)
        if definition.resolved_cop is not None:
            continue

        # Walk the COP tree and replace identifiers with references
        definition.resolved_cop = _resolve_to_references(
            definition.original_cop,
            namespace
        )

    return namespace


def _resolve_to_references(cop, namespace, param_names=None):
    """Walk a COP tree and replace value.identifier with value.reference nodes.

    Args:
        cop: The COP node to walk
        namespace: Module namespace dict {name: (priority, value_or_definition)}
        param_names: Set of parameter names to skip (handled by codegen)

    Returns:
        Potentially modified COP node
    """
    if cop is None:
        return cop

    param_names = param_names or set()
    tag = comp.cop_tag(cop)

    # Handle value.identifier - replace with value.reference
    if tag == "value.identifier":
        name = _get_identifier_name(cop)

        # Skip if we couldn't extract a name
        if name is None:
            return cop

        # Skip parameter names (handled by codegen)
        if name in param_names:
            return cop

        # Try to resolve from namespace
        definition_set = namespace.get(name)
        if definition_set is not None:
            # Extract Definition from DefinitionSet
            definition = None
            import_namespace = None

            # Try to get a scalar (unambiguous) definition
            scalar_def = definition_set.scalar()
            if scalar_def is not None:
                # Single unambiguous definition
                definition = scalar_def
                # Check if this came from an import
                if hasattr(definition, '_import_namespace'):
                    import_namespace = definition._import_namespace
            else:
                # Multiple definitions (overloaded) - leave as identifier for build-time resolution
                return cop

            # Create value.reference node
            if definition is not None:
                return comp.create_reference_cop(
                    definition,
                    identifier_cop=cop,
                    import_namespace=import_namespace
                )

        # Unresolved - leave as-is (will error at build time)
        return cop

    # Handle value.block - extract parameter names from signature
    elif tag == "value.block":
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
            new_body = _resolve_to_references(body_cop, namespace, new_param_names)

            # If body changed, create new block cop
            if new_body is not body_cop:
                kids_field = cop.field("kids")
                new_kids_dict = kids_field.data.copy()
                keys = list(new_kids_dict.keys())
                if len(keys) >= 2:
                    new_kids_dict[keys[1]] = new_body

                    # Reconstruct the cop
                    new_data = {}
                    for key, value in cop.data.items():
                        if isinstance(key, comp.Value) and key.data == "kids":
                            new_data[key] = comp.Value.from_python(new_kids_dict)
                        else:
                            new_data[key] = value

                    return comp.Value.from_python(new_data)

        return cop

    # Handle mod.namefield - only resolve the value child, not the name
    elif tag == "mod.namefield":
        try:
            modified = False
            new_kids_dict = {}
            for key, kid in cop.field("kids").data.items():
                # Check if this is the name field (n=) or value field (v=)
                # The name field should NOT be resolved
                if key.data == "n":
                    new_kids_dict[key] = kid
                else:
                    new_kid = _resolve_to_references(kid, namespace, param_names)
                    new_kids_dict[key] = new_kid
                    if new_kid is not kid:
                        modified = True

            # If any kids changed, create new cop
            if modified:
                new_data = {}
                for key, value in cop.data.items():
                    if isinstance(key, comp.Value) and key.data == "kids":
                        new_data[key] = comp.Value.from_python(new_kids_dict)
                    else:
                        new_data[key] = value

                return comp.Value.from_python(new_data)
        except (KeyError, AttributeError):
            pass

        return cop

    # For all other nodes, recursively walk kids
    else:
        try:
            modified = False
            new_kids_dict = {}
            for key, kid in cop.field("kids").data.items():
                new_kid = _resolve_to_references(kid, namespace, param_names)
                new_kids_dict[key] = new_kid
                if new_kid is not kid:
                    modified = True

            # If any kids changed, create new cop
            if modified:
                new_data = {}
                for key, value in cop.data.items():
                    if isinstance(key, comp.Value) and key.data == "kids":
                        new_data[key] = comp.Value.from_python(new_kids_dict)
                    else:
                        new_data[key] = value

                return comp.Value.from_python(new_data)
        except (KeyError, AttributeError):
            pass

    return cop


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
            if isinstance(resolved_value, (Ambiguous, Overload)):
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

