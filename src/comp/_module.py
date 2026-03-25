"""Module represents unit of code, usually from a file"""

import os

import comp


__all__ = ["Module", "Definition", "Ambiguous"]


class Module:
    """A module of Comp source code, usually from a single file.

    Modules are created and managed by an ``Interp`` — never instantiated
    directly.  The module is lazily parsed; data becomes available as the
    interpreter advances through its build phases:

        **Phase 0** — ``scan()``, ``statements()``, ``definitions()``
        **Phase 1** (after ``build_namespaces()``) — ``namespace()``
        **Phase 2** (after ``build_instructions()``) — definition values populated

    Validation is accessed through ``Interp.callouts(module=m)``.

    Args:
        source: (ModuleSource) Location, content, and etag for this module
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

        # Set to True when the module declares !no-default, opting out of the
        # automatic default-namespace injection.  Detected lazily on first call
        # to no_default property.
        self._no_default = None

        # Per-module tag hierarchy for ancestry checks (built after namespace)
        self._tag_hierarchy = None

    @property
    def tag_hierarchy(self):
        """Tag ancestor map for morph dispatch.

        Lazily built from imported + local tag definitions after
        namespace() has been populated.  Returns _EMPTY_HIERARCHY if
        this module has no tags or hasn't been built yet.
        """
        if self._tag_hierarchy is not None:
            return self._tag_hierarchy
        if self._namespace is None:
            return comp._tag._EMPTY_HIERARCHY
        self._tag_hierarchy = _build_tag_hierarchy(self)
        return self._tag_hierarchy

    def __repr__(self):
        return f"Module<{self.token}>"

    def __hash__(self):
        return id(self.token)

    @property
    def no_default(self):
        """True when this module has declared !no-default.

        Lazily scanned from the module's statements so it is available
        before the full definitions() pass.
        """
        if self._no_default is None:
            try:
                stmts = self.statements()
                self._no_default = any(
                    s.get("operator") == "no-default" for s in stmts
                )
            except Exception:
                self._no_default = False
        return self._no_default

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
        """Get module-level documentation comment.

        Args:
            context: Reserved for future use (must be None)

        Returns:
            (str) The comment text, or empty string
        """
        if context is not None:
            return ""
        scan_result = self.scan()
        docs = scan_result.to_python("docs") or []
        if not docs:
            return ""
        return docs[0].get("content", "")

    def package(self):
        """Get package metadata from !package statements.

        Returns:
            (dict) {key: Value} package metadata
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

        Requires the module to belong to an interpreter that has scanned
        and resolved its imports.

        Returns:
            (dict) {name: {"module": Module|None, "error": Exception|None, ...}}
        """
        if self._imports is None:
            raise comp.ModuleError("Module must belong to an interpreter.")
        result = {}
        for name, (mod, err) in self._imports.items():
            info = {"module": mod, "error": err, "source": None, "location": None, "docs": None}
            if mod is not None:
                info["source"] = mod.source.resource
                info["location"] = mod.source.location
                try:
                    scan = mod.scan()
                    docs = scan.to_python("docs") or []
                    if docs:
                        info["docs"] = docs[0].get("content", "")
                except Exception:
                    pass
            result[name] = info
        return result

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
        self._no_default = None

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

            if operator in ("func", "pure", "tag", "shape", "startup", "main"):
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
        """Get the Definition for a !startup context preparation by name.

        Args:
            name: (str) The startup context name (e.g., "default", "web")

        Returns:
            (Definition | None) The startup definition, or None if not found
        """
        return self.definitions().get(f"!startup.{name}")

    def startups(self):
        """Get all !startup context preparation definitions.

        Returns:
            (dict) Mapping of context name to Definition
        """
        result = {}
        for name, defn in self.definitions().items():
            if defn.startup:
                ctx_name = name.split(".", 1)[1] if "." in name else name
                result[ctx_name] = defn
        return result

    def main_entry(self, name):
        """Get the Definition for a !main entry point by name.

        Args:
            name: (str) The entry point name (e.g., "console", "serve")

        Returns:
            (Definition | None) The main definition, or None if not found
        """
        return self.definitions().get(f"!main.{name}")

    def main_entries(self):
        """Get all !main entry point definitions.

        Returns:
            (dict) Mapping of entry point name to Definition
        """
        result = {}
        for name, defn in self.definitions().items():
            if defn.main:
                entry_name = name.split(".", 1)[1] if "." in name else name
                result[entry_name] = defn
        return result

    def prepare_main(self, name):
        """Prepare a named !main entry point for execution.

        Returns the main Definition and an initial context struct built
        by executing the startup context DAG.

        Args:
            name: (str) Name of the entry point (e.g. "console", "serve")

        Returns:
            (tuple) ``(definition, initial_context)`` or ``(None, None)``

            definition: (Definition) The main entry point definition
            initial_context: (Value) Starting context struct
        """
        defn = self.main_entry(name)
        if defn is None:
            return None, None

        # For now, return an empty context struct.
        # The full DAG execution will be wired up in the interpreter.
        initial_context = comp.Value.from_python({})
        return defn, initial_context

    def namespace(self):
        """Resolved namespace for identifier lookups.

        Available after ``Interp.build_namespaces()`` (phase 1+).  Combines
        definitions from this module, its imports, and the system module.
        Keys are qualified name strings; values are ``Callable`` (single or
        overloaded) or ``Ambiguous`` entries.

        Results are cached.  Raises ``ModuleError`` if called before the
        interpreter has reached phase 1.

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

    def _resolve_deferred(self):
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

            # Check if ref is a pending alias in this module (but not if
            # already being resolved — that would be a true cycle).
            if ref in alias_lookup and ref not in resolving:
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

            # Also include child definitions matching the reference prefix.
            # e.g., aliasing "entry-type" from "fsn.entry-type" also captures
            # "entry-type.dir" from "fsn.entry-type.dir", etc.
            child_prefix = def_ref + "."
            for ns_key, ns_entry in list(self._namespace.items()):
                if not ns_key.startswith(child_prefix):
                    continue
                child_suffix = ns_key[len(def_ref):]
                child_alias = def_name + child_suffix
                if isinstance(ns_entry, comp.Callable):
                    child_defs = set(ns_entry.entries)
                elif isinstance(ns_entry, Ambiguous):
                    child_defs = set(ns_entry.definitions)
                else:
                    continue
                self._resolved_deferred.append((kind, child_alias, child_defs, is_private))
                if not is_private:
                    self._exported_aliases.setdefault(child_alias, set()).update(child_defs)

    def _apply_aliases(self, default_mod=None):
        """Inject resolved aliases into namespaces.

        Pass 4: Called by the interpreter after all modules have run
        resolve_deferred(). Injects resolved aliases into this module's
        own namespace, then merges imported modules' exported aliases
        under their import prefixes.

        Finally, injects the default module's exported aliases (unprefixed)
        into every module that has not declared !no-default.

        Args:
            default_mod: (Module | None) The pre-located default module, or None
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
                    # Generate all suffix permutations from the prefixed alias name.
                    # e.g. import_name="b", alias_name="if" → "b.if", "if"
                    parts = [import_name] + alias_name.split(".")
                    for i in range(len(parts)):
                        perm = ".".join(parts[i:])
                        _inject_ns(self._namespace, perm, alias_defs)

        # Inject the default module's exported aliases unprefixed into every
        # module that has not opted out with !no-default.
        # Skip if the module already explicitly imports default (the import
        # loop above already injected the unprefixed aliases).
        if not self.no_default:
            if default_mod is None:
                default_mod = _find_default_module(self)
            already_imported_default = (
                default_mod is not None
                and self._imports is not None
                and any(m is default_mod for m, _e in self._imports.values())
            )
            if default_mod is not None and default_mod._exported_aliases and not already_imported_default:
                default_ns = {}
                for alias_name, alias_defs in default_mod._exported_aliases.items():
                    # Only inject unprefixed — no "default." prefix
                    parts = alias_name.split(".")
                    for i in range(len(parts)):
                        perm = ".".join(parts[i:])
                        _inject_ns(default_ns, perm, alias_defs)
                # clobber=False: local defs and explicit-import symbols win
                self._namespace = merge_namespace(default_ns, self._namespace, clobber=True)


class Definition:
    """A single module-level definition (function, shape, tag, etc.).

    Definitions are data objects created during ``build_namespaces()``
    and progressively populated through ``build_instructions()``:

        1. **Extract** — ``original_cop`` and ``shape`` set
        2. **Resolve** — ``resolved_cop`` filled with resolved identifiers
        3. **Fold** — ``resolved_cop`` updated with folded constants
        4. **Codegen** — ``instructions`` generated, ``value`` populated

    Definitions are accessed via ``Module.definitions()`` and are
    validated through ``Interp.callouts()``.

    Attributes:
        qualified:    (str) Fully qualified name (e.g. "cart", "add")
        module_id:    (str) Owning module's token (avoids circular refs)
        original_cop: (Value) Raw COP node from parsing
        resolved_cop: (Value | None) Resolved + folded COP node
        shape:        (Shape) Definition type (shape_block, shape_shape, etc.)
        value:        (Value | None) Evaluated definition value
        instructions: (list | None) Bytecode for this definition
        private:      (bool) Private to the module
        pure:         (bool) Compile-time evaluable (!pure)
        startup:      (bool) Context preparation (!startup)
        startup_deps: (list) Dependency names for !startup context
        main:         (bool) Entry point (!main)
        main_deps:    (list) Dependency names for !main entry point
    """
    __slots__ = ("qualified", "module_id", "original_cop", "resolved_cop", "shape", "value", "instructions", "private", "pure", "startup", "startup_deps", "main", "main_deps")

    def __init__(self, qualified, module_id, original_cop, shape, private=False):
        self.qualified = qualified
        self.module_id = module_id
        self.original_cop = original_cop
        self.shape = shape
        self.private = private
        self.pure = False  # Whether this is a !pure definition (evaluate at compile time)
        self.startup = False  # Whether this is a !startup context preparation
        self.startup_deps = []  # Dependency names for context preparation
        self.main = False  # Whether this is a !main entry point
        self.main_deps = []  # Dependency names for entry point
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
        if definition.startup or definition.main:
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


def _find_default_module(module):
    """Find the default module from any module's import graph.

    Walks the import graph to locate a module whose source resource is
    "default" (or ends with "/default.comp" / "default.comp").  Returns
    None if not found.

    Args:
        module: (Module) Any module to start the search from

    Returns:
        (Module | None) The default module, or None
    """
    visited = set()

    def _walk(mod):
        mid = id(mod)
        if mid in visited:
            return None
        visited.add(mid)
        resource = getattr(mod.source, "resource", "") or ""
        if (resource in ("default", "default.comp")
                or resource.endswith("/default.comp")
                or resource.endswith("\\default.comp")):
            return mod
        imports = getattr(mod, "_imports", None) or {}
        for _name, (child, _err) in imports.items():
            if child is not None:
                result = _walk(child)
                if result is not None:
                    return result
        return None

    return _walk(module)


def _build_tag_hierarchy(module):
    """Build a TagHierarchy from a module's visible tag definitions.

    Collects tag definitions from the system module, all imports, and
    local definitions — without clobbering.  Tags that share any
    namespace-key permutation are placed in the same equivalence slot
    via union-find.  Parent slots are then determined by namespace-key
    prefix matching.

    Args:
        module: (Module) The module to build a hierarchy for

    Returns:
        (TagHierarchy) Assembled tag hierarchy
    """
    # Phase 1: Collect all (namespace_key, Tag) pairs
    # key_tags: {key: set of tag_id}
    # tag_keys: {tag_id: set of keys}
    # all_tags: {tag_id: Tag}
    key_tags = {}
    tag_keys = {}
    all_tags = {}

    def _add_tag(tag, prefix):
        tid = id(tag)
        all_tags[tid] = tag
        qualified = tag.qualified
        parts = qualified.split(".")
        if prefix:
            parts = [prefix] + parts
        for i in range(len(parts)):
            key = ".".join(parts[i:])
            key_tags.setdefault(key, set()).add(tid)
            tag_keys.setdefault(tid, set()).add(key)

    def _collect_defs(defs, prefix):
        for defn in defs.values():
            if (defn.shape is comp.shape_tag and defn.value is not None
                    and isinstance(defn.value.data, comp.Tag)
                    and not (prefix and defn.private)):
                _add_tag(defn.value.data, prefix)

    # System module tags (no prefix)
    if not isinstance(module, comp._internal.SystemModule):
        sys = comp.get_internal_module("system")
        if sys is not None:
            sys_defs = sys.definitions()
            _collect_defs(sys_defs, None)

    # Import tag definitions
    imports = getattr(module, "_imports", None) or {}
    for import_name, (import_mod, import_err) in imports.items():
        if import_err or import_mod is None:
            continue
        try:
            _collect_defs(import_mod.definitions(), import_name)
        except (comp.ParseError, comp.CodeError):
            continue

    # Local tag definitions (no prefix)
    try:
        _collect_defs(module.definitions(), None)
    except (comp.ParseError, comp.CodeError):
        pass

    if not all_tags:
        return comp._tag._EMPTY_HIERARCHY

    # Phase 2: Union-Find to group tags sharing namespace keys
    uf = {}

    def _find(x):
        path = []
        while uf.get(x, x) != x:
            path.append(x)
            x = uf[x]
        for p in path:
            uf[p] = x
        return x

    def _union(a, b):
        ra, rb = _find(a), _find(b)
        if ra != rb:
            uf[ra] = rb

    for tids in key_tags.values():
        tids_list = list(tids)
        for i in range(1, len(tids_list)):
            _union(tids_list[0], tids_list[i])

    # Phase 3: Assign slot ids and collect per-slot keys
    slot_of = {}
    slot_keys = {}

    for tid in all_tags:
        rep = _find(tid)
        slot_of[tid] = rep
        slot_keys.setdefault(rep, set()).update(tag_keys.get(tid, set()))

    # Phase 4: Map every namespace key to its slot
    key_to_slot = {}
    for rep, keys in slot_keys.items():
        for key in keys:
            key_to_slot[key] = rep

    # Phase 5: Determine parent slot for each slot
    # Use longest key, walk down its prefixes to find the first different slot
    slot_parent = {}
    for rep, keys in slot_keys.items():
        longest = max(keys, key=len)
        parts = longest.split(".")
        for i in range(len(parts) - 1, 0, -1):
            prefix = ".".join(parts[:i])
            parent_rep = key_to_slot.get(prefix)
            if parent_rep is not None and parent_rep != rep:
                slot_parent[rep] = parent_rep
                break

    # Phase 6: Assemble TagHierarchy
    hierarchy = comp.TagHierarchy()
    for tid, tag in all_tags.items():
        hierarchy._slot[tag] = slot_of[tid]
    hierarchy._parent_slot = slot_parent
    return hierarchy
