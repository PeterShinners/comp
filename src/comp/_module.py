"""Module represents unit of code, usually from a file"""

import os

import comp


__all__ = ["Module", "Definition", "DefinitionSet", "Ambiguous"]


class Module:
    """A module in the Comp language.

    The module represents the data and code from source code. The module
    is not immediately parsed or loaded into this class. Methods like
    `scan` and `definitions` will incrementally build and prepare
    the module.

    Modules are created and managed by an Interp, not created directly.
    
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
        self.source = source
        self.token = _unique_token(source.resource)

        # Intermediate cached parse passes
        self._scan = None
        self._imports = None
        self._definitions = None
        self._namespace = None
        self._finalized = False

        # Module-level values (from !mod statements)
        self._mod_values = None

        # Alias statements: list of (alias_name, ref_string, is_private)
        # Populated during definitions(), resolved during namespace()
        self._alias_stmts = []

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

    def statements(self):
        """Get list of module-level statements from scan.

        Each statement is a dict with:
            - operator: str (e.g., "import", "func", "shape")
            - name: str (the definition name)
            - pos: tuple (line, col, end_line, end_col)
            - body: str (the raw text after the name)
            - hash: str (blake2s digest of body for change detection)

        Returns:
            list: List of statement dicts
        """
        scan_result = self.scan()
        definitions = scan_result.to_python("definitions") or []
        return definitions

    def comment(self, context=None):
        """Get comment for a given context.

        Args:
            context: Currently only None is supported (module-level comment)

        Returns:
            str: The comment text, or empty string if no comment found

        For context=None, returns the first comment in the file (module-level documentation).
        This is typically a doc comment (///) or block comment (/* */) at the top of the file.
        """
        if context is not None:
            # Future: support getting comments for specific statements
            return ""

        # Get module-level comment (first comment in the file)
        scan_result = self.scan()
        docs = scan_result.to_python("docs") or []
        if not docs:
            return ""

        # Return the first comment's content
        first_comment = docs[0]
        return first_comment.get("content", "")

    def package(self):
        """Get package metadata from !package statements.

        Returns:
            dict: {key: Value} package metadata key-value pairs
        """
        statements = self.statements()
        metadata = {}

        for stmt in statements:
            if stmt.get("operator") != "package":
                continue

            key = stmt.get("name")
            body = stmt.get("body", "")
            line_offset = stmt.get("pos", [1])[0]
            col_offset = stmt.get("body_col", 0)

            tree = comp.lark_parse(body, "comp", "start_package", line_offset=line_offset, col_offset=col_offset)
            cop = comp.lark_to_cop(tree)
            sys_ns = comp.get_internal_module("system").namespace()
            folded = comp.coptimize(cop, fold=True, namespace=sys_ns)

            if comp.cop_tag(folded) == "value.constant":
                value = folded.field("value")
            else:
                value = comp.Value.from_python(body.strip())

            metadata[key] = value

        return metadata

    def imports(self):
        """Dictionary of imported modules with metadata.

        Each key is the name the module is imported as. The value is a dictionary
        containing the module object, possible import error, source location,
        documentation, and other known data.

        This requires the module belongs to an Interpreter that has already
        scanned and resolved its imports.

        Returns:
            dict: {name: {"module": Module|None, "error": Exception|None,
                          "source": str, "location": str, "docs": str, ...}}
        """
        if self._imports is None:
            raise comp.ModuleError("Module must belong to an interpreter.")

        imports = {}
        for name, (mod, err) in self._imports.items():
            import_info = {
                "module": mod,
                "error": err,
                "source": None,
                "location": None,
                "docs": None,
            }

            # Extract metadata from module if available
            if mod is not None:
                import_info["source"] = mod.source.resource
                import_info["location"] = mod.source.location
                try:
                    scan = mod.scan()
                    docs = scan.to_python("docs") or []
                    if docs:
                        import_info["docs"] = docs[0].get("content", "")
                except:
                    pass

            imports[name] = import_info
        return imports

    def _register_imports(self, imports, definitions, namespace):
        """Interpreter call to store registered imports and precached data.
        
        These modules are likely not parsed or finalized yet, but the
        interpreter must do this before the complete namespace can be generated.

        if the interpeter has precached information about the module definitions
        or namespace it can be passed now.

        """
        if self._imports is not None:
            raise comp.ModuleError("Module imports already registered.")
        self._definitions = definitions
        self._namespace = namespace
        self._imports = imports

    def definitions(self):
        """Parse source and extract definitions into module.definitions dict.

        This is a cached dictionary of qualified name strings to Definitions.
        Initially the Definitions will contain only raw cop (ast) node
        hierarchies. These definitions will be progressively refined and
        populated through the various build passes.

        Returns:
            dict: qualified names strings to Definition objects
        """
        if self._definitions is not None:
            return self._definitions

        self._definitions = {}
        self._mod_values = {}
        statements = self.statements()

        # Process each statement by dispatching to operator-specific handlers
        for stmt in statements:
            operator = stmt.get("operator")

            # Dispatch to operator-specific handler
            # Each handler updates module state directly
            if operator in ("func", "pure"):
                self._process_func_statement(stmt)
            elif operator == "tag":
                self._process_tag_statement(stmt)
            elif operator == "shape":
                self._process_shape_statement(stmt)
            elif operator == "mod":
                self._process_mod_statement(stmt)
            elif operator == "alias":
                self._process_alias_statement(stmt)
            else:
                pass  # Handle import, package, startup separately

        return self._definitions

    def _process_func_statement(self, stmt):
        """Process a !func or !pure statement, adding definitions to self._definitions."""
        raw_name = stmt.get("name")
        is_private = raw_name.endswith("&")
        name = raw_name[:-1] if is_private else raw_name
        body = stmt.get("body", "")
        line_offset = stmt.get("pos", [1])[0]
        col_offset = stmt.get("body_col", 0)

        tree = comp.lark_parse(body, "comp", "start_func", line_offset=line_offset, col_offset=col_offset)
        cop_value = comp.lark_to_cop(tree)

        # Determine shape - check if it's wrapped
        shape = comp.shape_func
        value_tag = comp.cop_tag(cop_value)
        if value_tag == "value.wrapper":
            # Check the wrapped inner value (first kid)
            try:
                inner_kids = comp.cop_kids(cop_value)
                if inner_kids:
                    inner_tag = comp.cop_tag(inner_kids[0])
                    if inner_tag not in ("function.define", "value.block"):
                        shape = comp.shape_struct
            except (KeyError, AttributeError):
                shape = comp.shape_struct

        # Create base definition
        definition = Definition(name, self.token, cop_value, shape, private=is_private)
        if stmt.get("operator") == "pure":
            definition.pure = True

        # Handle overloading with auto-suffix
        if not hasattr(self, '_overload_counters'):
            self._overload_counters = {}

        counter = self._overload_counters.get(name, 0) + 1
        self._overload_counters[name] = counter
        qualified_name = f"{name}.i{counter:03d}"
        definition.qualified = qualified_name
        definition.auto_suffix = True

        self._definitions[qualified_name] = definition

    def _process_tag_statement(self, stmt):
        """Process a !tag statement, adding tag hierarchy to self._definitions."""
        raw_name = stmt.get("name")
        is_private = raw_name.endswith("&")
        name = raw_name[:-1] if is_private else raw_name
        body = stmt.get("body", "")
        line_offset = stmt.get("pos", [1])[0]
        col_offset = stmt.get("body_col", 0)

        tree = comp.lark_parse(body, "comp", "start_tag", line_offset=line_offset, col_offset=col_offset)
        cop_value = comp.lark_to_cop(tree)

        # Create main tag definition
        tag = comp.Tag(name, private=False)
        tag.module = self
        main_def = Definition(name, self.token, original_cop=cop_value, shape=comp.shape_tag, private=is_private)
        main_def.value = comp.Value.from_python(tag)
        self._definitions[name] = main_def

        # todo not sure full parent hierarchy is right, perhaps just immediate
        # parent? this depends on how name hierarchy combines with functions
        # or other statement identifiers

        # Expand hierarchical parents
        # For "does.exist", create "does"
        parts = name.split('.')
        for i in range(1, len(parts)):
            parent_name = '.'.join(parts[:i])
            if parent_name not in self._definitions:
                parent_tag = comp.Tag(parent_name, private=False)
                parent_tag.module = self
                parent_def = Definition(parent_name, self.token, original_cop=None, shape=comp.shape_tag)
                parent_def.value = comp.Value.from_python(parent_tag)
                self._definitions[parent_name] = parent_def

        # Expand children from cop_value
        # For each child identifier in struct.define, create name.child
        for child_cop in comp.cop_kids(cop_value):
            child_tag = comp.cop_tag(child_cop)
            child_private = is_private  # children inherit parent privacy
            if child_tag == "value.private_tag":
                # Explicit & marker on this child
                child_private = True
                inner = comp.cop_kids(child_cop)
                if inner:
                    child_cop = inner[0]
                    child_tag = comp.cop_tag(child_cop)
            if child_tag == "value.identifier":
                # Extract child name
                child_name = self._statement_identifier(child_cop)
                child_qualified = f"{name}.{child_name}"

                child_tag_obj = comp.Tag(child_qualified, private=False)
                child_tag_obj.module = self
                child_def = Definition(child_qualified, self.token, original_cop=None, shape=comp.shape_tag, private=child_private)
                child_def.value = comp.Value.from_python(child_tag_obj)
                self._definitions[child_qualified] = child_def

    def _process_shape_statement(self, stmt):
        """Process a !shape statement, adding shape definition to self._definitions."""
        raw_name = stmt.get("name")
        is_private = raw_name.endswith("&")
        name = raw_name[:-1] if is_private else raw_name
        body = stmt.get("body", "")
        line_offset = stmt.get("pos", [1])[0]
        col_offset = stmt.get("body_col", 0)

        tree = comp.lark_parse(body, "comp", "start_shape", line_offset=line_offset, col_offset=col_offset)
        cop_value = comp.lark_to_cop(tree)

        # Create shape definition
        definition = Definition(name, self.token, cop_value, comp.shape_shape, private=is_private)
        self._definitions[name] = definition

    def _process_mod_statement(self, stmt):
        """Process a !mod statement, storing value in self._mod_values."""
        name = stmt.get("name")
        body = stmt.get("body", "").strip()
        # Parse the mod body
        lark_tree = comp.lark_parse(body, "comp", rule="start_mod")
        cop_value = comp._parse.lark_to_cop(lark_tree)

        # Store mod value separately (not as a definition)
        # These are module-level configuration values, accessible via module.mod_values()
        self._mod_values[name] = cop_value

    def _process_alias_statement(self, stmt):
        """Process a !alias statement, queuing for namespace-time resolution.

        Aliases are resolved during namespace() once imports are available.
        Syntax: !alias NAME REFERENCE  (NAME may carry & for private)
        """
        raw_name = stmt.get("name")
        is_private = raw_name.endswith("&")
        alias_name = raw_name[:-1] if is_private else raw_name
        alias_ref = stmt.get("body", "").strip()
        if alias_ref:
            self._alias_stmts.append((alias_name, alias_ref, is_private))

    def _statement_identifier(self, identifier_cop):
        """Extract name from value.identifier COP node.

        Args:
            identifier_cop: value.identifier COP node

        Returns:
            str: Identifier name (e.g., "add" or "server.host")
        """
        # todo this needs to fail on non token/text types (like #2 or $ or expr)
        # also this should be called on every statement type, not just tags
        parts = []
        for kid in comp.cop_kids(identifier_cop):
            kid_tag = comp.cop_tag(kid)
            if kid_tag in ("ident.token", "ident.text"):
                parts.append(kid.field("value").data)
        return '.'.join(parts) if parts else ""

    def startup(self, name):
        """Find and parse a !startup statement by name.

        Args:
            name: The startup function name (e.g., "main")

        Returns:
            Value: The parsed COP node for the startup body, or None if not found
        """
        for stmt in self.statements():
            if stmt.get("operator") == "startup" and stmt.get("name") == name:
                body = stmt.get("body", "")
                line_offset = stmt.get("pos", [1])[0]
                col_offset = stmt.get("body_col", 0)
                tree = comp.lark_parse(body, "comp", "start_startup", line_offset=line_offset, col_offset=col_offset)
                return comp.lark_to_cop(tree)
        return None

    def startup_names(self):
        """Return names of all !startup statements in this module.

        Returns:
            (list) Names of all startup entry points, in source order
        """
        return [
            stmt["name"]
            for stmt in self.statements()
            if stmt.get("operator") == "startup" and stmt.get("name")
        ]

    def prepare_startup(self, name):
        """Prepare a named !startup for execution.

        Parses the startup body into COP nodes (not yet optimized) and builds
        an initial argument struct that will be passed to the startup block.

        The initial struct is assembled from top-level contributions across all
        modules.  For now it contains a single hardcoded placeholder field so
        the mechanism has something concrete to evolve from.

        Args:
            name: (str) Name of the startup entry point (e.g. "main")

        Returns:
            (tuple) ``(cop, initial_struct)`` or ``(None, None)`` if not found.

            cop: (Value) Parsed COP node for the startup body (un-optimized)
            initial_struct: (Value) Starting struct for the startup invocation
        """
        cop = self.startup(name)
        if cop is None:
            return None, None

        # Build the initial struct that is handed to the startup block.
        # Eventually each contributing module will add fields here.  For now
        # we include one placeholder field so the struct is non-empty.
        initial_value = comp.Value.from_python({"timeout": 10})
        return cop, initial_value

    def namespace(self):
        """(dict) Resolved namespace dict for identifier lookups.

        This cached dictionary is derived from the module definitions().
        The namespace combines definitions from this module and its imports.
        
        The namespace dictionary contains qualified names as keys and
        each value is either

        - Definition for single direct references
        - DefinitionSet for overloaded references
        - Ambiguous for conflicting references from imports

        Most definitions will have multiple references from the namespace
        dictionary. Any value is referencable by shortened fragments of
        the fully qualified name.
        
        At this point any failed import statements will result in an exception.

        This requires the module belongs to an Interpreter that has already
        scanned and resolved its imports.

        """
        if self._namespace is not None:
            return self._namespace

        for import_module, import_err in self._imports.values():
            if import_err:
                raise import_err

        if self._imports is None:
            raise comp.ModuleError("Cannot build namespace until interpreter registers imports.")

        if isinstance(self, comp._internal.SystemModule):
            self._namespace = {}
        else:
            sys = comp.get_internal_module("system")
            self._namespace = dict(sys.namespace())

        for import_name, (import_module, import_err) in self._imports.items():
            # Trigger the import module's namespace build if it hasn't started yet.
            # This ensures _apply_aliases() has run so alias definitions appear in
            # import_module._definitions before we pull them into our own namespace.
            # Skip if already mid-build (_namespace not None) to avoid circular issues.
            if import_module is not None and import_module._namespace is None:
                try:
                    import_module.namespace()
                except Exception:
                    pass  # errors surface via import_err or the check above
            import_definitions = import_module.definitions()
            import_namespace = create_namespace(import_definitions, import_name)
            self._namespace = merge_namespace(self._namespace, import_namespace, clobber=False)

        defs = self.definitions()
        namespace = create_namespace(defs, None)
        self._namespace = merge_namespace(self._namespace, namespace, clobber=True)

        self._apply_aliases()

        return self._namespace

    def _apply_aliases(self):
        """Resolve queued !alias statements against the current namespace.

        Called once at the end of namespace() after all imports and local
        definitions have been merged.  For each alias:
        - Creates new Definitions that share the target's COP / value / instructions
        - Injects all name permutations into self._namespace
        - Adds non-private alias Definitions to self._definitions so they
          are visible to modules that import this one
        """
        alias_counters = {}
        for alias_name, alias_ref, is_private in self._alias_stmts:
            target_entry = self._namespace.get(alias_ref)
            if target_entry is None:
                continue  # unresolved reference — silently skip for now

            if isinstance(target_entry, DefinitionSet):
                target_defs = list(target_entry.definitions)
            elif isinstance(target_entry, Definition):
                target_defs = [target_entry]
            elif isinstance(target_entry, Ambiguous):
                target_defs = list(target_entry.definitions)
            else:
                continue

            alias_defs = []
            for tdef in sorted(target_defs, key=lambda d: d.qualified):
                if tdef.auto_suffix:
                    # Overloaded: allocate an alias.i001 / alias.i002 … qualified name
                    count = alias_counters.get(alias_name, 0) + 1
                    alias_counters[alias_name] = count
                    alias_qualified = f"{alias_name}.i{count:03d}"
                    alias_auto_suffix = True
                else:
                    alias_qualified = alias_name
                    alias_auto_suffix = False

                alias_def = Definition(
                    alias_qualified, self.token, tdef.original_cop, tdef.shape,
                    private=is_private, auto_suffix=alias_auto_suffix
                )
                alias_def.pure = tdef.pure
                alias_def.resolved_cop = tdef.resolved_cop
                alias_def.value = tdef.value
                alias_def.instructions = tdef.instructions
                alias_defs.append(alias_def)

                if not is_private:
                    self._definitions[alias_qualified] = alias_def

            # Build a single DefinitionSet for all overloads of this alias
            alias_def_set = DefinitionSet()
            for alias_def in alias_defs:
                alias_def_set.definitions.add(alias_def)

            # Collect every permutation name for this alias
            all_perms = set()
            for alias_def in alias_defs:
                for perm_name in _identifier_permutations(alias_def, None):
                    all_perms.add(perm_name)

            # Non-private aliases REPLACE existing entries (disambiguation).
            # Private aliases only add (local name shorthand only).
            for perm_name in all_perms:
                if not is_private:
                    self._namespace[perm_name] = alias_def_set
                else:
                    existing = self._namespace.get(perm_name)
                    if existing is None:
                        self._namespace[perm_name] = DefinitionSet()
                        existing = self._namespace[perm_name]
                    if isinstance(existing, DefinitionSet):
                        existing.definitions.update(alias_def_set.definitions)

    def finalize(self):
        """Build namespace and resolve identifiers. Auto-calls definitions if needed.

        Args:
            imports: Dict {import_name: Module} of resolved imports
        """
        definitions = self.definitions()
        namespace = self.namespace()
        for definition in definitions.values():
            if definition.resolved_cop is not None:
                continue
            definition.resolved_cop = comp.cop_resolve(
                definition.original_cop,
                namespace
            )

        self._finalized = True


class Definition:
    """A module-level definition that can be referenced.

    Definitions are created during the extraction phase and progressively
    enhanced through the compilation pipeline:
    1. Extract: Create with original_cop and shape
    2. Resolve: Populate resolved_cop with identifier references resolved
    3. Fold: Populate value with constant-folded Shape/Block/etc
    4. Codegen: Populate instructions with bytecode

    Args:
        qualified: Fully qualified name (e.g., "cart", "add.i001")
        module_id: Module token string (not reference)
        original_cop: The original COP node
        shape: Shape constant (comp.shape_block, comp.shape_shape, etc.)
        private: Whether this definition is private to the module
        auto_suffix: Whether this definition has an auto-generated suffix
    Attributes:
        qualified: (str) Fully qualified name (e.g., "cart", "add.i001")
        module_id: (str) Module token that owns this definition (avoids circular refs)
        original_cop: (Value) The original COP node from parsing
        resolved_cop: (Value | None) The resolved+folded+optimized COP node
        shape: (Shape) Shape constant indicating definition type
        value: (Value | None) The constant-folded value (Shape/Block/etc) if applicable
        instructions: (list | None) Bytecode instructions for this definition
        private: (bool) Whether this definition is private to the module
        auto_suffix: (bool) Whether the qualified name has an auto-generated suffix

    """
    __slots__ = ("qualified", "module_id", "original_cop", "resolved_cop", "shape", "value", "instructions", "private", "auto_suffix", "pure")

    def __init__(self, qualified, module_id, original_cop, shape, private=False, auto_suffix=False):
        self.qualified = qualified
        self.module_id = module_id
        self.original_cop = original_cop
        self.shape = shape
        self.private = private  # Whether this definition is private to the module
        self.auto_suffix = auto_suffix  # Whether qualified name has auto-generated suffix
        self.pure = False  # Whether this is a !pure definition (evaluate at compile time)
        self.resolved_cop = None  # Filled during identifier resolution
        self.value = None  # Filled during constant folding
        self.instructions = None  # Filled during code generation

    def __repr__(self):
        shape_name = self.shape.qualified
        return f"Definition<{self.qualified}:{shape_name}>"


def create_namespace(definitions, prefix):
    """Create namespace from definitions dict.

    Create a lookup namespace from definitions.
    If no namespace is given then this will include private definitions.

    Args:
        definitions: (dict) Mapping of qualified names to Definition objects
        prefix: (str | None) Optional namespace to prefix to definitions
    Returns:
        dict: Mapping of names to Definition, DefinitionSet, or Ambiguous
    """
    namespace = {}
    for qualified, definition in definitions.items():
        for name in _identifier_permutations(definition, prefix):
            if prefix and definition.private:
                continue
            defs = namespace.get(name)
            if defs is None:
                defs = namespace[name] = DefinitionSet()
            defs.definitions.add(definition)
    return namespace


def merge_namespace(base, overrides, clobber):
    """Merge two namespaces into a new resulting namespace.

    Args:
        base: (dict) Base namespace
        overrides: (dict) Namespace with overriding definitions
        clobber: (bool) New definitions replace previous ones
    Returns:
        dict: Mapping of names to Definition, DefinitionSet, or Ambiguous

    """
    result = dict(base)
    if clobber:
        result.update(overrides)

    else:
        for name, value in overrides.items():
            existing = result.get(name)
            # Always create a new DefinitionSet to avoid mutating shared objects.
            # Shared sets arise because dict(sys.namespace()) is a shallow copy —
            # mutating the DefinitionSet objects would corrupt sys's namespace.
            new_set = DefinitionSet()
            if existing is not None:
                new_set.definitions.update(existing.definitions)
            new_set.definitions.update(value.definitions)
            result[name] = new_set

    return result


class DefinitionSet:
    """Collection of definitions for a given qualified name.
    Attrs:
        definitions: (set) of at least one definition
    """
    def __init__(self):
        self.definitions = set()

    def __repr__(self):
        return f"<DefinitionSet x{len(self.definitions)}>"

    def format(self):
        """Format for display."""
        names = [d.qualified for d in self.definitions]
        return f"DefinitionSet({', '.join(names)})"

    def scalar(self):
        """Get single definition if unambiguous or None."""
        if len(self.definitions) != 1:
            return None
        return next(iter(self.definitions))

    def shape(self):
        """Get single shape definition or None"""
        shapes = [d for d in self.definitions if d.shape is comp.shape_shape]
        if len(shapes) != 1:
            return None
        return shapes[0]

    def invokables(self):
        """Get all invokeable (blocks, funcs, and/or a single shape) or empty list"""
        shapes = [d for d in self.definitions if d.shape is comp.shape_shape]
        blocks = [
            d for d in self.definitions
            if d.shape is comp.shape_block or d.shape is comp.shape_func
        ]
        if len(shapes) > 1:
            return None
        if len(blocks) + len(shapes) != len(self.definitions):
            return None
        return shapes + blocks


class Ambiguous:
    """Represents an ambiguous namespace entry that cannot be resolved.

    This occurs when multiple non-invokable definitions share the same name
    and cannot be disambiguated through overload dispatch.

    Attributes:
        definitions: (set) The conflicting definitions
        reason: (str) Description of why this is ambiguous
    """

    def __init__(self, definitions, reason="Multiple conflicting definitions"):
        self.definitions = set(definitions)
        self.reason = reason

    def __repr__(self):
        names = [d.qualified for d in self.definitions]
        return f"<Ambiguous: {', '.join(names)}>"


def _identifier_permutations(definition, prefix):
    """Generate lookup name permutations from a Definition.

    For auto-suffixed identifiers like "tree-contains.i001":
    - Generates "tree-contains.i001" (full qualified name)
    - Generates "tree-contains" (base name without suffix)
    - Skips the bare suffix "i001"

    This allows both "tree-contains" and "tree-contains.i001" to resolve.

    For imports with a prefix (e.g. prefix="t", qualified="split.i001"):
    - Generates "t.split.i001", "t.split", "split.i001", "split"
    - The alias "t" alone is never generated (no definition has qualified="")
    - So import aliases never shadow builtins or local names

    Args:
        definition: Definition object with qualified name and auto_suffix flag
        prefix: Optional namespace prefix to add

    Returns:
        list: List of permutation strings to add to namespace
    """
    permutations = []
    qualified = definition.qualified
    parts = qualified.split('.')
    if prefix:
        parts.insert(0, prefix)

    last = len(parts) - 1

    # Generate all suffix permutations
    for i in range(len(parts)):
        name = '.'.join(parts[i:])
        # Skip if this is just the bare auto-generated suffix
        if definition.auto_suffix and i == last:
            continue
        permutations.append(name)

    # If we have an auto-generated suffix, also add the base name without it
    # e.g., "tree-contains.i001" also generates "tree-contains"
    if definition.auto_suffix and len(parts) > 1:
        base_parts = parts[:-1]
        for i in range(len(base_parts)):
            base_name = '.'.join(base_parts[i:])
            if base_name not in permutations:
                permutations.append(base_name)

    return permutations


_token_counter = os.getpid() & 0xFFFF

def _unique_token(token):
    "Generate a unique token for internal use."
    # ot attempting to be a secure id, just distinguish conflicting tokens 
    # with a non repeating id
    global _token_counter
    count = hash(token) & 0xFFFF ^ Module._token_counter
    _token_counter += 1
    return f"{token}#{count:04x}"
