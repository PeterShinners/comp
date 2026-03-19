"""Module represents unit of code, usually from a file"""

import os

import comp


__all__ = ["Module", "Definition", "Ambiguous"]


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
        self.callouts = []  # Module-level callouts (scan errors, import failures, non-definition statements)

        # Module-level values (from !mod statements)
        self._mod_values = None

        # Deferred definitions: list of (kind, name, ref_string, is_private)
        # kind is "alias" or "export"
        # Populated during definitions(), resolved during resolve_deferred()
        self._deferred_defs = []

        # Resolved alias/export definitions for cross-module visibility.
        # Dict of {alias_name: Definition} — same shape as definitions() returns.
        # Only public aliases/exports are stored here. Populated by resolve_deferred().
        self._exported_aliases = {}

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
        return scan_result.to_python("statements") or []

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
            elif operator == "export":
                self._process_export_statement(stmt)
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
        shape = comp.shape_block
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

        if name in self._definitions:
            raise comp.CodeError(
                f"Duplicate definition '{name}' in module '{self.token}'",
                cop_value,
            )

        self._definitions[name] = definition

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

        Aliases are resolved during namespace() against the namespace.
        Syntax: !alias NAME REFERENCE  (NAME may carry & for private)
        """
        raw_name = stmt.get("name")
        is_private = raw_name.endswith("&")
        alias_name = raw_name[:-1] if is_private else raw_name
        alias_ref = stmt.get("body", "").strip()
        if alias_ref:
            self._deferred_defs.append(("alias", alias_name, alias_ref, is_private))

    def _process_export_statement(self, stmt):
        """Process a !export statement, queuing for namespace-time resolution.

        Exports are resolved during namespace() against the imports.

        Two forms:
          !export NAME IMPORT_ALIAS  — re-export all public defs from IMPORT_ALIAS,
                                       each exported as NAME.def_qualified_name.
          !export NAME IMPORT_ALIAS.SUB.PATH  — re-export only defs whose qualified
                                                name starts with SUB.PATH from
                                                IMPORT_ALIAS; each exported name is
                                                NAME + suffix after SUB.PATH.
        NAME may carry & suffix for private.
        """
        raw_name = stmt.get("name")
        is_private = raw_name.endswith("&")
        export_name = raw_name[:-1] if is_private else raw_name
        export_ref = stmt.get("body", "").strip()
        if export_ref:
            self._deferred_defs.append(("export", export_name, export_ref, is_private))

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

        - Callable for invokable references (single or overloaded)
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
            import_definitions = import_module.definitions()
            import_namespace = create_namespace(import_definitions, import_name)
            self._namespace = merge_namespace(self._namespace, import_namespace, clobber=False)

        defs = self.definitions()
        namespace = create_namespace(defs, None)
        self._namespace = merge_namespace(self._namespace, namespace, clobber=True)

        return self._namespace

    def resolve_deferred(self):
        """Resolve queued alias and export refs against the namespace.

        Pass 3: Called by the interpreter after all module namespaces are
        built. Resolves alias/export references to concrete Definitions
        and stores public results in _exported_aliases for cross-module
        propagation. Does NOT modify any namespace.

        Aliases resolve against the namespace (local defs + imports).
        Exports resolve against the imports only.
        """
        if not self._deferred_defs:
            return

        # Build lookup of alias names to their refs for recursive resolution.
        # Multiple aliases can share a name (overload dispatch), so group them.
        alias_lookup = {}
        for kind, name, ref, is_private in self._deferred_defs:
            if kind == "alias":
                alias_lookup.setdefault(name, []).append((ref, is_private))

        # Cache of already-resolved alias names -> list of Definition
        resolved_cache = {}
        # Set of alias names currently being resolved (cycle detection)
        resolving = set()

        def resolve_alias_ref(ref):
            """Resolve an alias reference against the namespace.

            Follows alias chains recursively.  Returns a list of Definition
            objects from the end of the chain, or an empty list if unresolvable.
            """
            entry = self._namespace.get(ref)
            if entry is not None:
                if isinstance(entry, comp.Callable):
                    return list(entry.entries)
                elif isinstance(entry, Definition):
                    return [entry]
                elif isinstance(entry, Ambiguous):
                    return list(entry.definitions)

            # Check if ref is a pending alias in this module
            if ref in alias_lookup:
                return resolve_alias_name(ref)

            return []

        def resolve_alias_name(name):
            """Resolve all refs for a given alias name, with cycle detection."""
            if name in resolved_cache:
                return resolved_cache[name]

            if name in resolving:
                raise comp.CodeError(f"Circular alias: {name}")

            resolving.add(name)
            result = []
            for ref, _is_private in alias_lookup[name]:
                result.extend(resolve_alias_ref(ref))
            resolving.discard(name)

            resolved_cache[name] = result
            return result

        def resolve_export_pairs(def_name, def_ref):
            """Resolve an export statement to (exported_name, Definition) pairs.

            When def_ref is a simple import alias, re-exports every public def
            from that module as def_name.def_qualified.

            When def_ref is dotted (import_alias.sub.path), re-exports only defs
            whose qualified name starts with sub_path; each exported name is
            def_name + the suffix after sub_path, so the sub_path is replaced by
            def_name.

            Examples:
              !export util  mymod     -> util.split, util.join ...
              !export measure.time unit.measure.time
                -> unit defs 'measure.time.second' -> 'measure.time.second',
                               'measure.time.day'    -> 'measure.time.day', ...
            """
            if "." in def_ref:
                # Sub-path form: def_ref is "import_alias.sub.path"
                dot = def_ref.index(".")
                import_key = def_ref[:dot]
                sub_path = def_ref[dot + 1:]
            else:
                import_key = def_ref
                sub_path = None

            if import_key not in self._imports:
                return []
            import_module, import_err = self._imports[import_key]
            if import_module is None or import_err:
                return []

            result = []
            for qualified, tdef in import_module.definitions().items():
                if tdef.private:
                    continue
                if sub_path is not None:
                    if qualified == sub_path:
                        exported_name = def_name
                    elif qualified.startswith(sub_path + "."):
                        suffix = qualified[len(sub_path):]  # starts with "."
                        exported_name = def_name + suffix
                    else:
                        continue
                else:
                    exported_name = f"{def_name}.{qualified}"
                result.append((exported_name, tdef))
            return result

        # Resolve each deferred def and store results.
        # _resolved_deferred: list of (kind, name, defs, is_private)
        # _exported_aliases: {alias_name: set of Definition} for public aliases
        #   visible to importers. Keyed by the alias name, not the definition's
        #   qualified name.
        self._resolved_deferred = []
        self._exported_aliases = {}

        # Two-pass: resolve exports first so aliases can reference exported names.
        # Pass A: exports — resolve and inject into namespace immediately
        for kind, def_name, def_ref, is_private in self._deferred_defs:
            if kind != "export":
                continue
            target_pairs = resolve_export_pairs(def_name, def_ref)
            for exported_name, tdef in target_pairs:
                self._resolved_deferred.append((kind, exported_name, {tdef}, is_private))
                if not is_private:
                    self._exported_aliases.setdefault(exported_name, set()).add(tdef)
                # Inject into namespace so aliases in pass B can find these
                _inject_ns(self._namespace, exported_name, {tdef})

        # Pass B: aliases — can now reference exported names
        for kind, def_name, def_ref, is_private in self._deferred_defs:
            if kind != "alias":
                continue
            target_defs = resolve_alias_ref(def_ref)
            if not target_defs:
                continue
            self._resolved_deferred.append((kind, def_name, set(target_defs), is_private))
            if not is_private:
                self._exported_aliases.setdefault(def_name, set()).update(target_defs)

    def apply_aliases(self):
        """Inject resolved aliases into namespaces.

        Pass 4: Called by the interpreter after all modules have run
        resolve_deferred(). Injects resolved aliases into this module's
        own namespace, then merges imported modules' exported aliases
        under their import prefixes.
        """
        # Inject own resolved aliases (public + private) into own namespace
        if hasattr(self, "_resolved_deferred"):
            for kind, name, defs, is_private in self._resolved_deferred:
                _inject_ns(self._namespace, name, defs)

        # Merge imported modules' exported aliases with import prefix
        if self._imports:
            for import_name, (import_module, import_err) in self._imports.items():
                if import_module is None or import_err:
                    continue
                if not import_module._exported_aliases:
                    continue
                for alias_name, alias_defs in import_module._exported_aliases.items():
                    # Generate prefixed + unprefixed permutations from the alias name
                    parts = alias_name.split(".")
                    parts_prefixed = [import_name] + parts
                    for part_list in (parts_prefixed, parts):
                        for i in range(len(part_list)):
                            perm = ".".join(part_list[i:])
                            _inject_ns(self._namespace, perm, alias_defs)

    def finalize(self):
        """Build namespace and resolve identifiers. Auto-calls definitions if needed."""
        definitions = self.definitions()
        namespace = self.namespace()
        self.resolve_deferred()
        self.apply_aliases()
        for definition in definitions.values():
            if definition.resolved_cop is not None:
                continue
            definition.resolved_cop = comp.cop_resolve_names(
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
        qualified: (str) Fully qualified name (e.g., "cart", "add")
        module_id: (str) Module token string (not reference)
        original_cop: (Value) The original COP node
        shape: (Shape) Shape constant (comp.shape_block, comp.shape_shape, etc.)
        private: (bool) Whether this definition is private to the module
    Attributes:
        qualified: (str) Fully qualified name
        module_id: (str) Module token that owns this definition (avoids circular refs)
        original_cop: (Value) The original COP node from parsing
        resolved_cop: (Value | None) The resolved+folded+optimized COP node
        shape: (Shape) Shape constant indicating definition type
        value: (Value | None) The constant-folded value (Shape/Block/etc) if applicable
        instructions: (list | None) Bytecode instructions for this definition
        private: (bool) Whether this definition is private to the module

    """
    __slots__ = ("qualified", "module_id", "original_cop", "resolved_cop", "shape", "value", "instructions", "private", "pure", "callouts")

    def __init__(self, qualified, module_id, original_cop, shape, private=False):
        self.qualified = qualified
        self.module_id = module_id
        self.original_cop = original_cop
        self.shape = shape
        self.private = private
        self.pure = False  # Whether this is a !pure definition (evaluate at compile time)
        self.resolved_cop = None  # Filled during identifier resolution
        self.value = None  # Filled during constant folding
        self.instructions = None  # Filled during code generation
        self.callouts = []  # Callouts discovered during any build phase for this definition

    def __repr__(self):
        shape_name = self.shape.qualified
        return f"Definition<{self.qualified}:{shape_name}>"


def _inject_ns(namespace, name, defs):
    """Add definitions to a namespace under the given name."""
    existing = namespace.get(name)
    if existing is not None and isinstance(existing, comp.Callable):
        existing.entries.extend(defs)
    else:
        new_callable = comp.Callable(name)
        new_callable.entries.extend(defs)
        namespace[name] = new_callable


def create_namespace(definitions, prefix):
    """Create namespace from definitions dict.

    Create a lookup namespace from definitions.
    If no namespace is given then this will include private definitions.

    Args:
        definitions: (dict) Mapping of qualified names to Definition objects
        prefix: (str | None) Optional namespace to prefix to definitions
    Returns:
        dict: Mapping of names to Callable or Ambiguous
    """
    namespace = {}
    for qualified, definition in definitions.items():
        for name in _identifier_permutations(definition, prefix):
            if prefix and definition.private:
                continue
            defs = namespace.get(name)
            if defs is None:
                defs = namespace[name] = comp.Callable(name)
            defs.entries.append(definition)
    return namespace


def merge_namespace(base, overrides, clobber):
    """Merge two namespaces into a new resulting namespace.

    Args:
        base: (dict) Base namespace
        overrides: (dict) Namespace with overriding definitions
        clobber: (bool) New definitions replace previous ones
    Returns:
        dict: Mapping of names to Callable or Ambiguous

    """
    result = dict(base)
    if clobber:
        result.update(overrides)

    else:
        for name, value in overrides.items():
            existing = result.get(name)
            # Always create a new Callable to avoid mutating shared objects.
            # Shared objects arise because dict(sys.namespace()) is a shallow copy —
            # mutating them would corrupt sys's namespace.
            new_callable = comp.Callable(name)
            if existing is not None:
                new_callable.entries.extend(existing.entries)
            new_callable.entries.extend(value.entries)
            result[name] = new_callable

    return result


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

    For a definition with qualified name "split" and prefix "t":
    - Generates "t.split", "split"
    - The alias "t" alone is never generated (no definition has qualified="")
    - So import aliases never shadow builtins or local names

    Args:
        definition: (Definition) Definition object with qualified name
        prefix: (str | None) Optional namespace prefix to add

    Returns:
        (list) List of permutation strings to add to namespace
    """
    permutations = []
    qualified = definition.qualified
    parts = qualified.split('.')
    if prefix:
        parts.insert(0, prefix)

    # Generate all suffix permutations
    for i in range(len(parts)):
        name = '.'.join(parts[i:])
        permutations.append(name)

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
