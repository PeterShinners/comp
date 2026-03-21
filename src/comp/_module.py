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
        self._interp_phase = 0          # Set by Interp during build phases
        self._scan_error = None         # Cached exception from failed scan()
        self._definitions_error = None  # Cached exception from failed definitions()

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

    def scan(self):
        """Scan source for imports and metadata (fast, no full parse).

        This is a lightweight operation that extracts module metadata without
        doing a full parse. Useful for dependency resolution and tooling.

        This parse is fairly resilient to simple syntax errors, and
        may be able to provide module information even when a full parse
        would fail.

        Results are cached.  On failure the exception is cached and
        re-raised on future calls.

        Returns:
            ScanResult: Object with .imports(), .package(), .docs() methods

        Raises:
            Exception: If scanning fails (cached for future calls)
        """
        if self._scan is not None:
            return self._scan
        if self._scan_error is not None:
            raise self._scan_error
        try:
            self._scan = comp._scan.scan(self.source.content)
        except Exception as e:
            self._scan_error = e
            raise
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

    def _register_imports(self, imports):
        """Register imports and reset module to phase 0.

        Called by the interpreter after scanning import statements.
        Resets all cached build state so the module can be rebuilt
        through the phase pipeline.
        """
        self._imports = imports
        self._definitions = None
        self._namespace = None
        self._interp_phase = 0
        self._scan_error = None
        self._definitions_error = None
        self._mod_values = None
        self._deferred_defs = []
        self._exported_aliases = {}

    def definitions(self):
        """Parse source and extract definitions into module.definitions dict.

        This is a cached dictionary of qualified name strings to Definitions.
        Initially the Definitions will contain only raw cop (ast) node
        hierarchies. These definitions will be progressively refined and
        populated through the various build passes.

        Results are cached.  On failure the exception is cached and
        re-raised on future calls.  No partial state is stored on the
        module after a failure.

        Returns:
            dict: qualified names strings to Definition objects

        Raises:
            ParseError: If a statement body fails to parse
            CodeError: If definition extraction fails
        """
        if self._definitions is not None:
            return self._definitions
        if self._definitions_error is not None:
            raise self._definitions_error

        try:
            defs, mod_values, deferred = self._build_definitions()
        except Exception as e:
            self._definitions_error = e
            raise

        self._definitions = defs
        self._mod_values = mod_values
        self._deferred_defs = deferred
        return self._definitions

    def _build_definitions(self):
        """Build definitions from module statements.

        Delegates each statement to _compiler functions, then adopts the
        resulting Definitions into this module.  Tag definitions get their
        Tag.module bound here.

        Returns:
            (tuple) (defs, mod_values, deferred_defs)

        Raises:
            ParseError: On parse failure
            CodeError: On structural or duplicate-name errors
        """
        statements = self.statements()
        defs = {}
        mod_values = {}
        deferred = []

        for stmt in statements:
            operator = stmt.get("operator")

            if operator in ("func", "pure", "tag", "shape", "startup"):
                pairs = comp._compiler.compile_definition(stmt, self.token)
                for name, defn in pairs:
                    # Tag parent entries (no cop) skip if name already claimed
                    if defn.original_cop is None and defn.shape is comp.shape_tag:
                        if name not in defs:
                            defs[name] = defn
                    else:
                        defs[name] = defn
                    # Adopt tag definitions — bind Tag.module to this module
                    if defn.shape is comp.shape_tag and defn.value is not None:
                        tag_obj = defn.value.data
                        if isinstance(tag_obj, comp.Tag):
                            tag_obj.module = self

            elif operator == "mod":
                name, cop_value = comp._compiler.compile_mod_value(stmt)
                mod_values[name] = cop_value

            elif operator in ("alias", "export"):
                entry = comp._compiler.compile_deferred(stmt)
                if entry is not None:
                    deferred.append(entry)

        return defs, mod_values, deferred

    def startup(self, name):
        """Get the Definition for a !startup entry point by name.

        Args:
            name: (str) The startup name (e.g., "main")

        Returns:
            (Definition | None) The startup definition, or None if not found
        """
        return self.definitions().get(f"!startup.{name}")

    def startup_names(self):
        """Return names of all !startup entry points in this module.

        Returns:
            (list) Names of all startup entry points, in source order
        """
        prefix = "!startup."
        return [
            qualified[len(prefix):]
            for qualified, defn in self.definitions().items()
            if defn.startup
        ]

    def prepare_startup(self, name):
        """Prepare a named !startup for execution.

        Returns the startup Definition and an initial argument struct that
        will be passed to the startup block.

        Args:
            name: (str) Name of the startup entry point (e.g. "main")

        Returns:
            (tuple) ``(definition, initial_struct)`` or ``(None, None)``

            definition: (Definition) The startup definition
            initial_struct: (Value) Starting struct for the startup invocation
        """
        defn = self.startup(name)
        if defn is None:
            return None, None

        # Build the initial struct that is handed to the startup block.
        # Eventually each contributing module will add fields here.  For now
        # we include one placeholder field so the struct is non-empty.
        initial_value = comp.Value.from_python({"timeout": 10})
        return defn, initial_value

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

        if self._interp_phase < 1:
            raise comp.ModuleError(
                "Interpreter must call build_namespaces() before accessing namespace."
            )

        if self._imports is None:
            raise comp.ModuleError("Cannot build namespace until interpreter registers imports.")

        if isinstance(self, comp._internal.SystemModule):
            self._namespace = {}
        else:
            sys = comp.get_internal_module("system")
            self._namespace = dict(sys.namespace())

        for import_name, (import_module, import_err) in self._imports.items():
            if import_err or import_module is None:
                continue
            try:
                import_definitions = import_module.definitions()
            except (comp.ParseError, comp.CodeError):
                continue
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
        startup: (bool) Whether this is a !startup entry point

    """
    __slots__ = ("qualified", "module_id", "original_cop", "resolved_cop", "shape", "value", "instructions", "private", "pure", "startup")

    def __init__(self, qualified, module_id, original_cop, shape, private=False):
        self.qualified = qualified
        self.module_id = module_id
        self.original_cop = original_cop
        self.shape = shape
        self.private = private
        self.pure = False  # Whether this is a !pure definition (evaluate at compile time)
        self.startup = False  # Whether this is a !startup entry point
        self.resolved_cop = None  # Filled during identifier resolution
        self.value = None  # Filled during constant folding
        self.instructions = None  # Filled during code generation

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
        if definition.startup:
            continue
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
