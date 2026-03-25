"""Comp interpreter: phased build pipeline and runtime execution.

The Interp class orchestrates module loading, compilation, and execution
through a three-phase pipeline.  ExecutionFrame provides the runtime
stack for instruction execution.
"""

import hashlib
import os
import sys
from pathlib import Path

import comp

__all__ = ["Interp", "ExecutionFrame", "CompFail"]


class CompFail(Exception):
    """Raised by Python (InternalCallable) functions to signal a comp failure.

    The value is a comp.Value that will be set as frame.failure, causing the
    interpreter to fast-forward through remaining instructions until caught
    by a Fallback or PipeFallback instruction.

    Args:
        value: (comp.Value) The failure value to propagate
    """

    def __init__(self, value):
        self.value = value


def _exception_to_tag(exc):
    """Map a Python exception to the appropriate comp fail tag.

    Args:
        exc: Python exception instance

    Returns:
        (comp.Tag) The most specific matching fail tag
    """
    if isinstance(exc, (ZeroDivisionError, OverflowError, ArithmeticError)):
        return comp.tag_fail_math
    if isinstance(exc, (TypeError, ValueError)):
        return comp.tag_fail_value
    if isinstance(exc, (KeyError, IndexError, AttributeError)):
        return comp.tag_fail_field
    return comp.tag_fail


def _make_fail_value(message, tag=None, cause=None, cop_val=None):
    """Create a structured failure Value conforming to shape_failure.

    Args:
        message: (str | Exception) Human-readable error description
        tag: (comp.Tag | None) Specific fail tag; defaults to tag_fail
        cause: (comp.Value | None) Chained failure cause, or None for nil
        cop_val: (comp.Value | None) COP struct for source location, or None for nil

    Returns:
        (comp.Value) Struct with fail/message/cause/cop fields
    """
    if tag is None:
        tag = comp.tag_fail
    if isinstance(message, BaseException):
        # Use first string arg if available, otherwise fall back to type name
        msg = next((a for a in message.args if isinstance(a, str)), None)
        if not msg:
            msg = type(message).__name__
    else:
        msg = str(message) if message else ""
    nil = comp.tag_nil
    return comp.Value.from_python({
        "fail": tag,
        "message": msg,
        "cause": cause if cause is not None else nil,
        "cop": cop_val if cop_val is not None else nil,
    })


def _build_delivery_struct(delivery_map):
    """Convert a Python name->Value map into a Comp struct Value."""
    fields = {}
    for name, value in (delivery_map or {}).items():
        fields[comp.Value.from_python(name)] = value
    return comp.Value(fields)


class Interp:
    """Comp language interpreter.

    The interpreter orchestrates a phased build pipeline for modules:

        **Phase 0 — Modules loaded**
        Modules are added via ``module()`` or ``module_from_text()``.
        Imports are crawled and resolved.  ``Module.statements()`` and
        ``Module.definitions()`` are available.

        **build_namespaces() — Phase 1**
        All module definitions are parsed, namespaces built, and aliases
        resolved.  ``Module.namespace()`` is now available.

        **build_instructions() — Phase 2**
        Identifiers are resolved, constants folded, validators run,
        bytecode generated, and definition values populated.
        ``invoke()`` is now available.

    Each phase is idempotent: re-calling is a no-op.  Adding a new module
    resets back to phase 0 so subsequent build calls pick it up.

    Build methods are best-effort — they return ``[(Module, Exception)]``
    error lists and never raise.  Only ``invoke()`` raises on errors.

    Validation diagnostics (callouts) are collected via ``callouts()``.
    """

    def __init__(self):
        self.system = comp.get_internal_module("system")
        # Import-related state (was ImportContext)
        comp_root = str(Path(__file__).parent)
        working_dir = str(Path.cwd())
        self.comp_root = comp_root
        self.working_dir = working_dir
        self.search_paths = [
            os.path.join(self.comp_root, "stdlib"),  # Built-in stdlib
            os.path.join(self.working_dir, "stdlib"),  # Project stdlib
            os.path.join(self.working_dir, "lib"),  # Project lib
            self.working_dir,  # Project root
        ]
        # Open directory file descriptors for efficient searching
        # On Windows, directory fds work differently, so we test if it's supported
        self.search_fds = []
        for path in self.search_paths:
            if not os.path.isdir(path):
                self.search_fds.append(-1)
                continue
            try:
                # Try to open directory - works on Unix, may fail on Windows
                fd = os.open(path, os.O_RDONLY)
                self.search_fds.append(fd)
            except (FileNotFoundError, OSError, PermissionError):
                # Directory exists but can't be opened as fd (Windows)
                # Use -1 to indicate fallback to path-based search
                self.search_fds.append(-1)

        self.module_cache = {}
        self._phase = 0  # 0=modules added, 1=namespaces built, 2=instructions built
        # Guard to avoid recursive callout validation while building callout stdlib.
        self._disable_build_validations = 0
        # Populated by build_namespaces/build_instructions when timing is needed.
        self.timings = {}
        # Set to True to print a line to stderr for every module load/cache-hit.
        self.trace_imports = False

    def __del__(self):
        for fd in getattr(self, 'search_fds', []):
            if fd >= 0:
                try:
                    os.close(fd)
                except OSError:
                    pass

    def __repr__(self):
        return "Interp<>"

    def __hash__(self):
        return id(self)

    # module methods should have compiler arg? probably.
    def module(self, resource, anchor=None):
        """Get new or existing Module for a given resource.

        Modules are cached and act as singletons within an interpreter.
        Module objects are lazily parsed and compiled. The Module may be
        invalid but still get a Module object.

        Args:
            resource: Module resource identifier to locate
            anchor: Directory of the module doing the import (for relative imports)
            compiler: Compiler to use for the module (default: "comp")

        Returns:
            (comp.Module) Module with location, content, and etag

        Raises:
            ModuleNotFoundError: Module not found in search paths
            NotImplementedError: For git://, http://, etc. URLs
        """
        anchored = comp._import.anchor_resource(resource, anchor)

        internal_mod = comp.get_internal_module(anchored)
        if internal_mod is not None:
            return internal_mod

        # Fast path: already loaded under this exact resource string
        cached = self.module_cache.get(anchored)
        etag = cached.source.etag if cached else None
        import time as _time
        _t0 = _time.perf_counter()
        src = comp._import.locate_resource(
            resource=anchored,
            etag=etag,
            search_paths=self.search_paths,
            search_fds=self.search_fds,
        )
        _t1 = _time.perf_counter()

        # etag matched - return cached version
        if src is None:
            return cached

        # Canonical dedup: same absolute path → reuse existing Module.
        # Different resource strings (e.g. "limit" vs "stdlib/limit") can resolve
        # to the same file; using src.location as the canonical key prevents
        # creating duplicate Module instances that break the circular-import guard.
        if src.location:
            loc_cached = self.module_cache.get(src.location)
            if loc_cached is not None:
                # Record the resource alias so future requests for this string are fast.
                self.module_cache[anchored] = loc_cached
                return loc_cached

        mod = comp.Module(src)
        # Store ONLY under the canonical absolute path as the primary key.
        # The resource string alias is also stored so fast-path hits work next time,
        # but both point at the same object — no duplicate Module instances.
        if src.location:
            self.module_cache[src.location] = mod
        self.module_cache[anchored] = mod
        self._new_module(mod)
        return mod

    def module_from_text(self, text):
        """Create a Module from existing text."""
        src = comp._import.ModuleSource(
            resource="txt",
            location="txt",
            etag=hashlib.sha256(text.encode('utf-8')).hexdigest(),
            content=text,
            anchor="",
        )
        mod = comp.Module(src)
        self.module_cache["txt"] = mod
        self._new_module(mod)
        return mod

    def invoke(self, module, name, piped=None, args=None):
        """Invoke a named function in a module.

        Auto-promotes through ``build_instructions()`` (phase 2) before
        executing.  Raises immediately if any module has build errors.

        Args:
            module: (Module | str) Module object or import path string
            name: (str) Function name to invoke
            piped: (Value | None) Piped input value
            args: (Value | dict | None) Arguments; dicts are auto-converted

        Returns:
            (Value) Result of the function call
        """
        if isinstance(module, str):
            module = self.module(module)

        errors = self.build_instructions()
        if errors:
            # Check if any error affects this module's dependency chain
            for mod, exc in errors:
                raise exc

        defs = module.definitions()
        defn = defs.get(name)
        if defn is None:
            raise comp.CodeError(f"Function {name!r} not found in module")

        if defn.value is None:
            raise comp.CodeError(f"Function {name!r} has no value (not yet built?)")

        if args is None:
            args = comp.Value.from_python({})
        elif isinstance(args, dict):
            args = comp.Value.from_python(args)

        env = {n: d.value for n, d in defs.items() if d.value is not None}
        frame = ExecutionFrame(env, interp=self, module=module)
        return frame.invoke_block(defn.value, args, piped=piped)

    def _execute(self, instructions, env=None, module=None):
        """Execute a sequence of instructions (internal).

        Used by ``build_instructions()`` to run definition bytecode.
        External callers should use ``invoke()`` instead.

        Args:
            instructions: List of Instruction objects
            env: Initial environment (variable bindings)
            module: The module being executed (for definition lookups)

        Returns:
            Final result Value (from last instruction)
        """
        frame = ExecutionFrame(env, interp=self, module=module)
        return frame.run(instructions)

    def resolve_startup_dag(self, main_defn):
        """Resolve the startup dependency DAG for a !main entry point.

        Builds a topologically sorted list of startup context names that
        need to be executed before the entry point runs. The implicit
        "default" layer is always included as the base.

        Args:
            main_defn: (Definition) The !main entry point definition

        Returns:
            (list) Topologically sorted list of startup context names,
                   starting with "default"

        Raises:
            comp.CodeError: On circular dependencies
        """
        deps = main_defn.main_deps if main_defn.main_deps else []

        # Collect all startup definitions across all modules
        all_startups = {}
        for mod in self._unique_modules():
            for ctx_name, defn in mod.startups().items():
                if ctx_name not in all_startups:
                    all_startups[ctx_name] = []
                all_startups[ctx_name].append(defn)

        # Build dependency graph from startup definitions
        dep_graph = {}
        for ctx_name, defns in all_startups.items():
            dep_graph[ctx_name] = set()
            for defn in defns:
                for dep in defn.startup_deps:
                    dep_graph[ctx_name].add(dep)

        # Add the main's direct dependencies
        needed = set(deps)
        needed.add("default")

        # Expand transitive dependencies
        visited = set()
        order = []

        def visit(name, path):
            if name in path:
                cycle = " -> ".join(list(path) + [name])
                raise comp.CodeError(
                    f"Circular startup dependency: {cycle}"
                )
            if name in visited:
                return
            visited.add(name)
            path_set = path | {name}
            for dep in dep_graph.get(name, set()):
                visit(dep, path_set)
            order.append(name)

        for dep in sorted(needed):
            visit(dep, set())

        # Ensure default is always first
        if "default" in order:
            order.remove("default")
        order.insert(0, "default")

        return order

    def collect_startup_providers(self, context_name):
        """Collect all !startup providers for a given context name.

        Walks all modules in the import tree and collects definitions
        that match the given context name.

        Args:
            context_name: (str) The startup context name (e.g., "default", "web")

        Returns:
            (list) List of (module, definition) tuples
        """
        providers = []
        for mod in self._unique_modules():
            defn = mod.startup(context_name)
            if defn is not None:
                providers.append((mod, defn))
        return providers

    def execute_startup_context(self, module, main_name):
        """Execute the full startup context DAG for a !main entry point.

        Resolves the dependency DAG, executes each layer of context
        providers in order, and returns the merged context.

        Args:
            module: (Module) The root module containing the !main
            main_name: (str) Name of the !main entry point

        Returns:
            (Value) Merged context struct with hierarchical keys

        Raises:
            comp.CodeError: On circular deps or context key conflicts
        """
        main_defn = module.main_entry(main_name)
        if main_defn is None:
            return comp.Value.from_python({})

        dag_order = self.resolve_startup_dag(main_defn)
        merged_context = {}

        for layer_name in dag_order:
            providers = self.collect_startup_providers(layer_name)
            if not providers:
                continue

            # Execute each provider independently
            layer_results = {}
            for provider_mod, provider_defn in providers:
                if provider_defn.value is None:
                    continue
                block_val = provider_defn.value
                if not isinstance(block_val.data, comp.Callable):
                    continue

                # Build $ input from dependency contexts
                dep_input = {}
                for dep_name in provider_defn.startup_deps:
                    if dep_name in merged_context:
                        dep_input[dep_name] = merged_context[dep_name]
                dollar_val = comp.Value.from_python(dep_input)

                # Execute the provider block
                env = {n: d.value for n, d in provider_mod.definitions().items()
                       if d.value is not None}
                frame = ExecutionFrame(env, interp=self, module=provider_mod)
                result = frame.invoke_block(block_val, dollar_val, piped=None)

                # Collect results — each field becomes layer_name.field in context
                if result is not None and result.shape == comp.shape_struct:
                    for key, val in result.data.items():
                        if isinstance(key, comp.Unnamed):
                            continue
                        field_name = key.data if hasattr(key, "data") else str(key)
                        qualified_key = f"{layer_name}.{field_name}"
                        if qualified_key in layer_results:
                            raise comp.CodeError(
                                f"Context conflict in '{layer_name}': "
                                f"multiple providers define '{field_name}'"
                            )
                        layer_results[qualified_key] = val

            # Merge layer results into the accumulated context
            merged_context.update(layer_results)
            # Also store a sub-struct for $ access in dependent layers
            layer_struct = {}
            for qkey, val in layer_results.items():
                field = qkey.split(".", 1)[1] if "." in qkey else qkey
                layer_struct[field] = val
            merged_context[layer_name] = comp.Value.from_python(layer_struct)

        return comp.Value.from_python(merged_context)

    def _unique_modules(self):
        """Get deduplicated list of modules from the cache."""
        seen = set()
        modules = []
        for mod in self.module_cache.values():
            if id(mod) not in seen:
                seen.add(id(mod))
                modules.append(mod)
        return modules

    def build_namespaces(self):
        """Build namespaces for all modules (phase 0 → 1).

        Parses all module definitions, stamps phase 1 on every module
        (unlocking ``Module.namespace()``), builds each namespace from
        local definitions and imports, then resolves and applies aliases.

        Best-effort: builds as many namespaces as possible, skipping
        modules that failed to parse.  Idempotent if already at phase 1+.

        Returns:
            (list) List of (Module, Exception) pairs for modules that had errors
        """
        if self._phase >= 1:
            return []

        import time as _time
        all_modules = self._all_modules()
        errors = []

        # Pass 1: Definitions — parse all statements into cop nodes
        _t0 = _time.perf_counter()
        for mod in all_modules:
            try:
                mod.definitions()
            except (comp.ParseError, comp.CodeError) as e:
                errors.append((mod, e))

        # Stamp phase 1 on all modules so namespace() gate is unlocked
        for mod in all_modules:
            mod._interp_phase = 1
        _t1 = _time.perf_counter()

        # Pass 2: Namespace — build namespace for each module
        for mod in all_modules:
            if mod._definitions_error is not None:
                continue
            mod.namespace()

        # Pass 2b: Tag hierarchies — build per-module tag ancestry maps
        for mod in all_modules:
            if mod._definitions_error is not None:
                continue
            _ = mod.tag_hierarchy

        _t2 = _time.perf_counter()

        # Pass 3: Resolve aliases — resolve alias/export refs against namespace
        for mod in all_modules:
            if mod._definitions_error is not None:
                continue
            mod._resolve_deferred()
        _t3 = _time.perf_counter()

        # Pass 4: Apply aliases — inject resolved aliases into all namespaces
        # Locate the default module once so _apply_aliases doesn't have to
        # walk each module's import graph (user modules don't import default).
        default_mod = None
        for _mod in all_modules:
            _resource = getattr(_mod.source, "resource", "") or ""
            if (_resource in ("default", "default.comp")
                    or _resource.endswith("/default.comp")
                    or _resource.endswith("\\default.comp")):
                default_mod = _mod
                break

        for mod in all_modules:
            if mod._definitions_error is not None:
                continue
            mod._apply_aliases(default_mod=default_mod)
        _t4 = _time.perf_counter()

        self.timings["ns.definitions"] = self.timings.get("ns.definitions", 0.0) + (_t1 - _t0)
        self.timings["ns.namespace"]   = self.timings.get("ns.namespace",   0.0) + (_t2 - _t1)
        self.timings["ns.resolve"]     = self.timings.get("ns.resolve",     0.0) + (_t3 - _t2)
        self.timings["ns.aliases"]     = self.timings.get("ns.aliases",     0.0) + (_t4 - _t3)

        self._phase = 1
        return errors

    def build_instructions(self):
        """Build all modules through the full pipeline (phase 1 → 2).

        Auto-calls ``build_namespaces()`` if not yet at phase 1.  Then
        for every definition: resolves identifiers, folds constants,
        runs comp-side validators, generates bytecode, and executes
        definitions to populate their values.

        Best-effort: accumulates errors and continues.  Definitions
        that fail validation are skipped during codegen.

        Idempotent if already at phase 2+.

        Returns:
            (list) List of (Module, Exception) pairs for all errors
        """
        if self._phase >= 2:
            return []

        import time as _time
        _tb0 = _time.perf_counter()
        errors = list(self.build_namespaces())
        _tb1 = _time.perf_counter()
        self.timings["build.build_namespaces"] = self.timings.get("build.build_namespaces", 0.0) + (_tb1 - _tb0)
        all_modules = self._all_modules()

        # Resolve + fold + validate each definition via Definition.callouts()
        # Definitions with error callouts are marked to skip codegen.
        # Skip validation when building internal dependencies (e.g. callout stdlib)
        # to avoid recursion.
        failed_defs = set()
        skip_validation = self._disable_build_validations > 0
        _t0 = _time.perf_counter()
        _callout_bootstrap_before = self.timings.get("callout.bootstrap", 0.0)
        for mod in all_modules:
            if mod._definitions_error is not None:
                continue
            mod_defs = mod.definitions()
            mod_ns = mod.namespace()
            for defn in mod_defs.values():
                # Resolve and fold even when skipping validation
                if defn.original_cop is None:
                    continue
                if defn.resolved_cop is None:
                    defn.resolved_cop = comp.cop_resolve_names(
                        defn.original_cop, mod_ns
                    )
                defn.resolved_cop = comp.coptimize(defn.resolved_cop, True, mod_ns)

                if not skip_validation:
                    defn_callouts = comp._callout.cop_callouts(defn, interp=self, namespace=mod_ns)
                    for c in defn_callouts:
                        if c.severity == comp.ERROR:
                            failed_defs.add(id(defn))
                            err = comp.CodeError(c.message)
                            if c.primary and c.primary.span:
                                s = c.primary.span
                                err.row = s.line
                                err.col = s.col
                                err.end_col = s.col + s.length
                            err.module = mod
                            errors.append((mod, err))
                            break
        _t1 = _time.perf_counter()
        _callout_bootstrap_after = self.timings.get("callout.bootstrap", 0.0)
        self.timings["build.resolve_fold_validate"] = (
            self.timings.get("build.resolve_fold_validate", 0.0)
            + (_t1 - _t0) - (_callout_bootstrap_after - _callout_bootstrap_before)
        )

        # Pure evaluation (optional — always enabled for build_instructions)
        for mod in all_modules:
            if mod._definitions_error is not None:
                continue
            mod_defs = mod.definitions()
            mod_env = {}
            for name, defn in mod_defs.items():
                if id(defn) in failed_defs:
                    continue
                if defn.pure and defn.resolved_cop is not None and defn.value is None:
                    try:
                        defn.instructions = comp.generate_code_for_definition(
                            defn.resolved_cop,
                            dispatch_own_name=defn.qualified,
                            dispatch_set_name=defn.qualified,
                            pure=True,
                            namespace=mod.namespace(),
                        )
                        result = self._execute(defn.instructions, mod_env, module=mod)
                        defn.value = result
                        mod_env[name] = result
                    except Exception:
                        pass
        _t2 = _time.perf_counter()

        # Codegen — generate instructions for all non-failed definitions
        for mod in all_modules:
            if mod._definitions_error is not None:
                continue
            mod_defs = mod.definitions()
            for name, defn in mod_defs.items():
                if id(defn) in failed_defs:
                    continue
                if defn.instructions is not None:
                    continue
                if defn.resolved_cop is None:
                    continue
                try:
                    defn.instructions = comp.generate_code_for_definition(
                        defn.resolved_cop,
                        dispatch_own_name=defn.qualified,
                        dispatch_set_name=defn.qualified,
                        pure=defn.pure,
                        namespace=mod.namespace(),
                    )
                except (comp.CodeError, Exception) as e:
                    if isinstance(e, comp.CodeError):
                        errors.append((mod, e))
                    else:
                        errors.append((mod, comp.CodeError(
                            f"Code generation error for {mod.token}:{name}: {e}"
                        )))
        _t3 = _time.perf_counter()

        # Execute — run instructions to populate definition values
        for mod in all_modules:
            if mod._definitions_error is not None:
                continue
            mod_defs = mod.definitions()
            mod_env = {}
            # Shapes first (they don't depend on blocks)
            for name, defn in mod_defs.items():
                if defn.instructions and defn.value is None:
                    if defn.shape.qualified == "shape":
                        try:
                            result = self._execute(defn.instructions, mod_env, module=mod)
                        except comp.CodeError as ce:
                            errors.append((mod, ce))
                            continue
                        defn.value = result
                        mod_env[name] = result
            # Everything else
            for name, defn in mod_defs.items():
                if defn.instructions and defn.value is None:
                    try:
                        result = self._execute(defn.instructions, mod_env, module=mod)
                    except comp.CodeError as ce:
                        errors.append((mod, ce))
                        continue
                    defn.value = result
                    mod_env[name] = result

        # Stamp phase 2 on all modules
        for mod in all_modules:
            mod._interp_phase = 2
        self._phase = 2
        _t4 = _time.perf_counter()

        self.timings["build.build_namespaces"] = self.timings.get("build.build_namespaces", 0.0)
        self.timings["build.pure_eval"]  = self.timings.get("build.pure_eval",  0.0) + (_t2 - _t1)
        self.timings["build.codegen"]    = self.timings.get("build.codegen",    0.0) + (_t3 - _t2)
        self.timings["build.execute"]    = self.timings.get("build.execute",    0.0) + (_t4 - _t3)

        return errors

    def callouts(self, module=None, definition=None, min_severity="warning"):
        """Collect validation callouts.

        Single entry point for all validation diagnostics.  Ensures
        namespaces are built (phase 1), then runs comp-side validators
        on the requested scope.

        Scoping:
            - ``callouts()`` — all modules in the interpreter
            - ``callouts(module=m)`` — one module and its imports
            - ``callouts(module=m, definition=d)`` — one definition only

        When *definition* is given, *module* must also be given and the
        definition must belong to that module.

        Args:
            module:       (Module | None) Scope to a single module tree
            definition:   (Definition | None) Scope to a single definition
            min_severity: (str) Minimum severity threshold

        Returns:
            (list) Flat list of Callout objects
        """
        if definition is not None and module is None:
            raise ValueError("definition requires module")
        if module is not None:
            if id(module) not in {id(m) for m in self.module_cache.values()}:
                raise ValueError("module does not belong to this interpreter")
        if definition is not None:
            defs = module.definitions()
            if definition not in defs.values():
                raise ValueError("definition does not belong to the given module")

        self.build_namespaces()

        if definition is not None:
            ns = module.namespace() if module._namespace is not None else {}
            source_file = getattr(module.source, "resource", None)
            return self._definition_callouts(definition, ns, min_severity, source_file=source_file)

        all_callouts = []
        modules = self._collect_modules(module) if module else self._all_modules()
        for mod in modules:
            all_callouts.extend(self._module_callouts(mod, min_severity))
        return all_callouts

    def _module_callouts(self, mod, min_severity="error"):
        """Collect callouts for a single module.

        Combines import errors, parse/definition errors, and per-definition
        validation callouts.

        Args:
            mod: (Module) The module to validate

        Returns:
            (list) Callout objects
        """
        result = []

        # Import errors
        if mod._imports:
            for import_name, (import_module, import_err) in mod._imports.items():
                if import_err:
                    result.append(Callout(
                        severity=ERROR,
                        code="import-error",
                        message=str(import_err),
                        phase=PHASE_PARSE,
                    ))

        # Parse/definition errors
        if mod._definitions_error is not None:
            result.append(comp._callout.exception_to_callout(mod._definitions_error))
            return result

        # Per-definition validation (requires phase 1)
        if mod._interp_phase >= 1 and mod._definitions is not None:
            ns = mod._namespace or {}
            source_file = getattr(mod.source, "resource", None)
            for defn in mod._definitions.values():
                result.extend(self._definition_callouts(defn, ns, min_severity, source_file=source_file))

        return result

    def _definition_callouts(self, defn, namespace, min_severity="error", source_file=None):
        """Resolve, fold, and validate a single definition.

        Brings the definition through resolution and folding if not already
        done, then runs the unified validation pass.

        Args:
            defn: (Definition) The definition to validate
            namespace: (dict) Module namespace for identifier resolution
            source_file: (str | None) Source file path for location context

        Returns:
            (list) Callout objects from validation
        """
        if defn.original_cop is None:
            return []
        if defn.resolved_cop is None:
            defn.resolved_cop = comp.cop_resolve_names(
                defn.original_cop, namespace
            )
            defn.resolved_cop = comp.coptimize(defn.resolved_cop, True, namespace)
        callouts = comp._callout.cop_callouts(defn, min_severity=min_severity, interp=self, namespace=namespace)
        for c in callouts:
            c.definition_name = defn.qualified
            if c.primary and c.primary.span and not c.primary.span.file:
                c.primary.span.file = source_file
        return callouts

    def _collect_modules(self, root_module):
        """Collect all modules reachable from root in dependency order.

        Returns a flat list where imports appear before the modules that
        import them.  Internal/system modules are excluded.

        Args:
            root_module: (Module) The root module

        Returns:
            (list) Modules in dependency order (imports first)
        """
        visited = set()
        result = []

        def walk(mod):
            mod_id = id(mod)
            if mod_id in visited:
                return
            if isinstance(mod, comp._internal.InternalModule):
                return
            if isinstance(mod, comp._internal.SystemModule):
                return
            visited.add(mod_id)

            # Visit imports first (they were already discovered by _new_module)
            if mod._imports is not None:
                for import_name, (child_mod, child_err) in mod._imports.items():
                    if child_mod is not None:
                        walk(child_mod)

            result.append(mod)

        walk(root_module)
        return result

    def _all_modules(self):
        """Get all non-internal modules in the interpreter in dependency order."""
        visited = set()
        result = []

        def walk(mod):
            mod_id = id(mod)
            if mod_id in visited:
                return
            if isinstance(mod, (comp._internal.InternalModule, comp._internal.SystemModule)):
                return
            visited.add(mod_id)
            if mod._imports is not None:
                for import_name, (child_mod, child_err) in mod._imports.items():
                    if child_mod is not None:
                        walk(child_mod)
            result.append(mod)

        for mod in self.module_cache.values():
            walk(mod)
        return result

    def _new_module(self, module):
        """Internally scan and register module."""
        # module_cache entries (by resource string and abs path) are already
        # set by the module() method before this is called.

        # Adding a module invalidates completed phases — force rebuild
        self._phase = 0

        # Eagerly pull in the callout module so it's part of _all_modules() from
        # the very first build pass, rather than being bootstrapped mid-validation.
        # Guard: don't recurse when we're registering callout itself.
        if (module.source.resource != "callout"
                and self.module_cache.get("callout") is None):
            try:
                self.module("callout")
            except Exception:
                pass  # callout unavailable; validation degrades gracefully

        # Eagerly pull in the default module so its aliases are available to
        # every module that doesn't declare !no-default.
        # Guards: don't recurse when registering default or any of its stdlib
        # imports, and only attempt once (when default is not yet cached).
        _default_bootstrap_guard = getattr(self, "_bootstrapping_default", False)
        if (not _default_bootstrap_guard
                and not module.no_default
                and self.module_cache.get("default") is None):
            self._bootstrapping_default = True
            try:
                self.module("default")
            except Exception:
                pass  # default unavailable; degrades gracefully
            finally:
                self._bootstrapping_default = False

        # Get statements from the module scan
        statements = module.statements()
        import_stmts = [s for s in statements if s.get("operator") == "import"]

        children = {}
        for stmt in import_stmts:
            name = stmt.get("name")
            body = stmt.get("body", "").strip()

            # Parse the import body: <compiler> "<source>"
            # For now, we'll do simple parsing - later this should use the full parser
            try:
                import_info = self._parse_import_body(body)
                compiler = import_info.get("compiler")
                source = import_info.get("source")

                if not (name and source):
                    continue

                if compiler != "comp":
                    err = comp.ModuleError(f"Unknown compiler '{compiler}' for {name} import.'")
                    child = None
                    continue

                # Load the imported module
                child = self.module(source, anchor=module.source.anchor)
                err = None
            except (comp.ModuleNotFoundError, comp.ModuleError) as e:
                child = None
                err = e
            except Exception as e:
                # Catch parsing errors too
                child = None
                err = comp.ModuleError(f"Failed to parse import: {e}")

            children[name] = (child, err)

        module._register_imports(children)

    def _parse_import_body(self, body):
        """Parse import statement body: <compiler> "<source>"

        Returns dict with 'compiler' and 'source' keys.
        """
        import lark

        # Parse using start_import entry point
        try:
            tree = comp._parse.lark_parse(body, "comp", rule="start_import")
        except Exception as e:
            raise ValueError(f"Failed to parse import body: {e}")

        # Extract compiler (identifier) and source (text)
        # Tree structure: start_import -> [identifier, text]
        identifier_node = tree.children[0]  # identifier Tree
        text_node = tree.children[1]        # text Tree

        # Get compiler name: identifier -> tokenfield -> TOKENFIELD token
        tokenfield_node = identifier_node.children[0]  # tokenfield Tree
        compiler_token = tokenfield_node.children[0]   # TOKENFIELD Token
        compiler = compiler_token.value

        # Get source: text -> [DUBQUOTE, SHORT_TEXT_CONTENT, DUBQUOTE] or [SIXQUOTE, LONG_TEXT_CONTENT, SIXQUOTE]
        # Or text -> [STRING] where STRING includes quotes
        # Find the content token (middle one)
        source = ""
        for child in text_node.children:
            if isinstance(child, lark.Token):
                if "CONTENT" in child.type:
                    source = child.value
                    break
                if child.type == "STRING":
                    # STRING token includes quotes, strip them
                    source = child.value[1:-1]
                    break

        return {"compiler": compiler, "source": source}


class ExecutionFrame:
    """Runtime execution frame.

    Holds registers (temporaries) and environment (variables).
    This is the mutable state passed through instruction execution.

    Uses SSA-style implicit register numbering - instruction index IS the register.

    Attributes:
        registers: List of Values indexed by instruction number
        env: Dict mapping variable names to Values
        interp: The interpreter instance (for nested calls)
        module: The module being executed (for definition lookups)
        parent_frame: The frame that spawned this one (None for top-level)
        live_handles: Set of HandleInstance objects grabbed by this frame
            (None until the first !grab, to avoid allocating a set for every frame)
        context: Dict of name->Value pairs that flow down into called functions
            as implicit named argument defaults (!ctx bindings)
    """

    def __init__(self, env=None, interp=None, module=None, parent_frame=None, context=None, definition_name=None):
        self.registers = []  # List indexed by instruction number
        self.env = env if env is not None else {}
        self._dollar_vars = {}  # "$", "$$", "$$$" — pipeline input context (per-invocation)
        self._pipeline_delivery = {}
        self._last_delivery = {}
        self._delivered_coupling = {}
        self.interp = interp
        self.module = module
        self.parent_frame = parent_frame
        self.live_handles = None  # Set[HandleInstance] | None
        self.context = context if context is not None else {}
        self.failure = None  # comp.Value when a failure is propagating, else None
        self.definition_name = definition_name

    def run(self, instructions):
        """Execute a list of instructions, return final result.

        When frame.failure is set, non-catching instructions are skipped but
        their register slot is filled with the failure value to keep the
        register index model consistent.  Fallback / PipeFallback instructions
        have can_catch_failure=True and always execute so they may clear the
        failure and resume normal execution.

        Args:
            instructions: List of instruction objects

        Returns:
            Value result of final instruction (or None)
        """
        result = None
        for idx, instr in enumerate(instructions):
            if self.failure is not None and not instr.can_catch_failure:
                # Fast-forward: skip but keep register alignment
                self.registers.append(self.failure)
                result = self.failure
            else:
                result = instr.execute(self)
            self.on_step(idx, instr, result)
        _frame_exit_cleanup(self, result)
        return result

    def on_step(self, idx, instr, result):
        """Hook called after each instruction executes.

        Override in subclass to add tracing.

        Args:
            idx: Instruction index
            instr: The instruction that executed
            result: The result value
        """
        pass

    def get_value(self, source):
        """Get a value from either a register index or directly.

        Args:
            source: Either a register index (int) or a Value

        Returns:
            The Value
        """
        if isinstance(source, int):
            if source >= len(self.registers):
                raise ValueError(f"Undefined register: %{source}")
            return self.registers[source]
        return source

    def set_result(self, value):
        """Set the result of the current instruction.

        The instruction index is implicitly len(registers).
        """
        self.registers.append(value)
        return value

    def eval(self, cop):
        """Compile and evaluate a COP expression in this frame's context.

        Used internally by instructions that need to evaluate default
        parameter values at runtime (e.g. ``!param x = <expr>``).

        Args:
            cop: (Value) COP node representing an expression

        Returns:
            (Value) The evaluated result
        """
        ns = self.module.namespace() if self.module else {}
        resolved = comp._resolve.cop_resolve_names(cop, ns)
        ctx = comp._codegen.CodeGenContext()
        ctx.build_expression(resolved)
        sub_frame = self._make_child_frame(dict(self.env), module=self.module)
        return sub_frame.run(ctx.instructions)

    def invoke_block(self, block_val, args, piped=None, delivery=None, source_cop=None):
        """Call a function with the given arguments.

        Args:
            block_val: Value containing a Block, Callable, Shape, or InternalCallable
            args: Value containing the argument struct
            piped: Value for piped input (or None if not piped)
            source_cop: (Value | None) COP node of the call site for error reporting

        Returns:
            Value result of the function call
        """
        self._last_delivery = {}
        callable_obj = block_val.data
        
        # Handle InternalCallable (Python function)
        if isinstance(callable_obj, comp.InternalCallable):
            input_val = piped if piped is not None else args
            # Pre-morph input to declared shape when one is provided.
            # A morph failure produces CompFail so the call site fails-through,
            # exactly like a regular Comp function with a non-matching input type.
            if callable_obj.input_shape is not None:
                morph_result = comp.morph(input_val, callable_obj.input_shape, self)
                if morph_result.failure_reason:
                    if morph_result.failure_value is not None:
                        raise CompFail(morph_result.failure_value)
                    raise CompFail(_make_fail_value(
                        morph_result.failure_reason,
                        tag=comp.tag_fail_value,
                        cop_val=source_cop,
                    ))
                input_val = morph_result.value
            try:
                return callable_obj.func(input_val, args, self)
            except CompFail:
                raise  # Let the caller decide how to handle the failure
        
        # Handle Shape, ShapeUnion, ShapeCollection, or Tag (morph input to shape, return result only)
        if isinstance(callable_obj, (comp.Shape, comp.ShapeUnion, comp.ShapeCollection, comp.Tag)):
            input_val = piped if piped is not None else args
            morph_result = comp.morph(input_val, callable_obj, self)
            if morph_result.failure_reason:
                # Fall back to the union's default value if one was defined
                if isinstance(callable_obj, comp.ShapeUnion) and callable_obj.default is not None:
                    return callable_obj.default
                # For union shapes, all members failed — use a generic failure.
                # Never surface a specific limit failure from one member since the
                # value might have been valid for another member.
                if not isinstance(callable_obj, comp.ShapeUnion) and morph_result.failure_value is not None:
                    raise CompFail(morph_result.failure_value)
                raise CompFail(_make_fail_value(morph_result.failure_reason, tag=comp.tag_fail_value, cop_val=source_cop))
            return morph_result.value

        # Handle Callable (dispatch to best-matching block, shape, or single block)
        if isinstance(callable_obj, comp.Callable):
            if len(callable_obj.entries) > 1 or (callable_obj.entries and callable_obj.shape is not None):
                # Multiple entries or entries+shape: dispatch overload
                result = self._dispatch_overload(callable_obj, args, piped)
                if result is None:
                    names = [getattr(b, "qualified", "?") for b in callable_obj.entries]
                    raise CompFail(_make_fail_value(
                        f"No matching overload found: {', '.join(names)}",
                        tag=comp.tag_fail_invoke,
                        cop_val=source_cop,
                    ))
                if isinstance(result, comp.Value):
                    return result
                block = result
            elif callable_obj.entries:
                block = callable_obj.entries[0]
            elif callable_obj.shape is not None:
                # Shape-only callable — morph input
                input_val = piped if piped is not None else args
                morph_result = comp.morph(input_val, callable_obj.shape, self)
                if morph_result.failure_reason:
                    if isinstance(callable_obj.shape, comp.ShapeUnion) and callable_obj.shape.default is not None:
                        return callable_obj.shape.default
                    if morph_result.failure_value is not None:
                        raise CompFail(morph_result.failure_value)
                    raise CompFail(_make_fail_value(morph_result.failure_reason, tag=comp.tag_fail_value, cop_val=source_cop))
                return morph_result.value
            else:
                raise CompFail(_make_fail_value(
                    f"Empty callable: {callable_obj.qualified}",
                    tag=comp.tag_fail_invoke,
                    cop_val=source_cop,
                ))
        else:
            raise CompFail(_make_fail_value(
                f"Not callable: {type(callable_obj).__name__}",
                tag=comp.tag_fail_invoke,
                cop_val=source_cop,
            ))

        # If dispatch selected an InternalCallable (e.g. from a Callable
        # that mixed Python builtins into a Callable), handle it now.
        if isinstance(block, comp.InternalCallable):
            input_val = piped if piped is not None else args
            if block.input_shape is not None:
                morph_result = comp.morph(input_val, block.input_shape, self)
                if morph_result.failure_reason:
                    if morph_result.failure_value is not None:
                        raise CompFail(morph_result.failure_value)
                    raise CompFail(_make_fail_value(
                        morph_result.failure_reason,
                        tag=comp.tag_fail_value,
                        cop_val=source_cop,
                    ))
                input_val = morph_result.value
            return block.func(input_val, args, self)

        # If the block has a runtime wrapper, build invoke-data on the fly and
        # call the wrapper instead of executing the block directly.
        if block.wrapper is not None:
            import copy as _copy
            wrapper_val = block.wrapper
            _key = comp.Value.from_python
            _nil = comp.Value.from_python(comp.tag_nil)
            input_for_data = piped if piped is not None else _nil
            # Create statement: a Callable containing a wrapper-free copy of the
            # block so the wrapper can call `invoke` without triggering recursion.
            stmt_block = _copy.copy(block)
            stmt_block.wrapper = None
            stmt_callable = comp.Callable(block.qualified)
            stmt_callable.add(stmt_block)
            stmt_val = comp.Value(stmt_callable)
            local_data = {_key(k): v for k, v in self.env.items() if "." not in k}
            locals_val = comp.Value(local_data)
            ctx_data = {_key(k): v for k, v in self.context.items()}
            context_val = comp.Value(ctx_data)
            invoke_data = comp.Value({
                _key("statement"): stmt_val,
                _key("input"):     input_for_data,
                _key("locals"):    locals_val,
                _key("context"):   context_val,
            })
            return self.invoke_block(
                wrapper_val,
                comp.Value.from_python({}),
                piped=invoke_data,
                source_cop=source_cop,
            )

        # Share the closure environment directly — StoreLocal mutations
        # persist across invocations (e.g. a counter's !let count count+1).
        new_env = block.closure_env
        # Bind __self__ so !forward can locate the current Callable
        _self_callable = comp.Callable(block.qualified)
        _self_callable.add(block)
        new_env["__self__"] = comp.Value(_self_callable)
        
        # For single-parameter blocks (input only, no arg), treat args as piped input
        # This allows `up(5)` to work the same as `5|up()` for `:n(n+1)`
        if block.input_name and not block.arg_name and piped is None:
            # Extract the first positional value from the args struct
            # So `transpose(p)` passes `p` as input, not `(p)`
            args_data = args.data if hasattr(args, "data") else args
            if isinstance(args_data, dict):
                # Check for single positional argument (key is Unnamed)
                positional_items = []
                for k, v in args_data.items():
                    if isinstance(k, comp.Unnamed):
                        positional_items.append(v)
                
                if len(positional_items) == 1 and len(args_data) == 1:
                    # Single positional arg - extract it as the input
                    piped = positional_items[0]
                else:
                    # Multiple args or named args - use the whole struct as input
                    piped = args
            else:
                piped = args
            args = comp.Value.from_python({})
        
        # Apply morph/mask to parameters based on shapes
        _nil = comp.Value.from_python(comp.tag_nil)
        input_val = piped if piped is not None else _nil
        args_val = args

        # Morph piped input to input shape
        if block.input_shape and isinstance(block.input_shape, comp.Shape):
            morph_result = comp.morph(input_val, block.input_shape, self)
            if morph_result.failure_reason:
                block_name = block.qualified or "?"
                cop_node = source_cop or getattr(block_val, "cop", None)
                err = comp.CodeError(
                    f"Input morph failed: {morph_result.failure_reason}"
                    f"\n  block: {block_name}, input_shape: {block.input_shape.qualified}"
                    f", input: {input_val.format()}"
                    f" ({input_val.shape.qualified if input_val.shape else '?'})",
                    cop_node)
                err.module = self.module or block.module
                err.definition_name = self.definition_name
                raise err

        # Inject context values as implicit defaults for named arg-shape fields
        # not explicitly provided by the caller.  The mask step that follows will
        # validate types and apply real shape defaults when needed.
        if block.arg_shape and isinstance(block.arg_shape, comp.Shape) and self.context:
            args_val = _inject_context(args_val, block.arg_shape, self)

        # Mask arguments to arg shape
        if block.arg_shape and isinstance(block.arg_shape, comp.Shape):
            masked_val, error = comp.mask(args_val, block.arg_shape, self)
            if error:
                raise comp.CodeError(f"Argument mask failed: {error}", block_val.cop)
            args_val = masked_val

        # Bind parameters based on the block's signature
        if block.input_name and block.arg_name:
            # Two parameters: input_name=morphed input, arg_name=masked args
            new_env[block.input_name] = input_val
            new_env[block.arg_name] = args_val
        elif block.input_name:
            # One parameter: gets input if piped, otherwise args
            if piped is not None:
                new_env[block.input_name] = input_val
            else:
                new_env[block.input_name] = args_val

        # Spread !param names individually into the environment, TryInvoking each
        # value so that zero-arg callables are resolved to their result.
        # These come from !param declarations such as "!param timeout ~num=4".
        # After mask(), args_val is a named struct like {timeout: 4}.
        if block.param_names and isinstance(args_val.data, dict):
            param_set = set(block.param_names)
            for k, v in args_val.data.items():
                fname = comp._morph._get_field_key(k)
                if fname is not None and fname in param_set:
                    new_env[fname] = v

        if block.dependency_shape and isinstance(block.dependency_shape, comp.Shape):
            delivery_val = _build_delivery_struct(delivery)
            masked_delivery, error = comp.mask(delivery_val, block.dependency_shape, self)
            if error:
                raise comp.CodeError(f"Dependency mask failed: {error}", source_cop or block.signature_cop)
            if isinstance(masked_delivery.data, dict):
                dependency_set = set(block.dependency_names)
                for k, v in masked_delivery.data.items():
                    fname = comp._morph._get_field_key(k)
                    if fname is not None and fname in dependency_set:
                        new_env[fname] = v

        # Pipeline input context: $ / $$ / $$$ live on the frame, not in env,
        # so they don't pollute the shared closure dict.  Shift from the
        # captured dollar vars that were snapshotted when the block was created.
        _captured = block.captured_dollar_vars or {}
        _dollar = {}
        _dollar["$$$"] = _captured.get("$$", _nil)
        _dollar["$$"] = _captured.get("$", _nil)
        _dollar["$"] = input_val
        
        # Lazily compile body instructions if needed
        if block.body_instructions is None and block.body:
            # Need to resolve and compile the body COP
            # Get namespace from the block's module for name resolution
            if block.module:
                ns = block.module.namespace()
                resolved_body = comp.coptimize(block.body, True, ns)
                block.body_instructions = comp.generate_code_for_definition(resolved_body, namespace=ns)
            else:
                # No module - try to compile without namespace
                block.body_instructions = comp.generate_code_for_definition(block.body)
            
        # Execute the pre-compiled body instructions
        # Use the block's defining module for namespace lookups
        new_frame = self._make_child_frame(new_env, module=block.module)
        new_frame.definition_name = block.qualified
        new_frame._dollar_vars = _dollar

        result = new_frame.run(block.body_instructions)

        outgoing_coupling = dict(getattr(new_frame, "_delivered_coupling", {}) or {})

        # Skip delivery validation when the frame already holds a failure — the
        # !fail propagation (below) takes priority and the coupling state may be
        # incomplete or mismatched by design (e.g. ~any !fail branch).
        if new_frame.failure is None and outgoing_coupling and not block.deliver_specs:
            name = next(iter(outgoing_coupling.keys()))
            raise comp.CodeError(
                f"Delivered dependency `{name}` is not declared in signature",
                source_cop or block.signature_cop,
            )
        if new_frame.failure is None and block.deliver_specs:
            declared_shapes = {}
            for spec in block.deliver_specs:
                name = spec.get("name")
                if name:
                    declared_shapes[name] = spec.get("shape")

            for name, delivered_value in list(outgoing_coupling.items()):
                if name not in declared_shapes:
                    raise comp.CodeError(
                        f"Delivered dependency `{name}` is not declared in signature",
                        source_cop or block.signature_cop,
                    )
                deliver_shape = declared_shapes.get(name)
                if deliver_shape is None:
                    continue
                morph_result = comp.morph(delivered_value, deliver_shape, self)
                if morph_result.failure_reason:
                    if morph_result.failure_value is not None:
                        raise CompFail(morph_result.failure_value)
                    raise comp.CodeError(
                        f"Delivered dependency `{name}` does not match declared shape",
                        source_cop or block.signature_cop,
                    )
                outgoing_coupling[name] = morph_result.value

        # If the called block finished with an unhandled failure, raise it so
        # callers can distinguish a failure from a normally-computed value.
        if new_frame.failure is not None:
            fail = new_frame.failure
            if isinstance(fail.data, dict):
                frame_key = comp.Value.from_python("frame")
                block_name = block.dispatch_set_name or block.qualified
                if frame_key not in fail.data and block_name:
                    operator = "pure" if block.pure else "func"
                    fail.data[frame_key] = comp.Value.from_python(
                        f"!{operator} `{block_name}`"
                    )
            raise CompFail(fail)

        self._last_delivery = outgoing_coupling

        # Return the final result
        return result if result is not None else comp.Value.from_python(None)

    def _dispatch_overload(self, callable, args, piped, skip_name=None):
        """Find the best-matching block from a Callable.

        Tries each block's input shape against the piped input and returns
        the block with the best morph score. If no block matches, falls back
        to the Callable's shape and morphs to it.

        Args:
            callable: (Callable) Callable with blocks and optional shape
            args: (Value) Arguments struct
            piped: (Value | None) Piped input value
            skip_name: (str | None) Qualified name of the block to skip (for !forward)

        Returns:
            (Block | Value | None) Best matching block, morphed Value from shape, or None
        """
        best_block = None
        best_score = None

        # Iterate through blocks in the callable
        for block in callable.entries:
            qualified = getattr(block, "qualified", None)
            # Skip the currently-executing overload (used by !forward)
            if skip_name and qualified == skip_name:
                continue

            # For single-parameter blocks, use args as input when not piped
            input_name = getattr(block, "input_name", None)
            arg_name = getattr(block, "arg_name", None)
            if input_name and not arg_name and piped is None:
                input_val = args
            else:
                input_val = piped if piped is not None else comp.Value.from_python({})

            # Try to morph input to this block's input shape
            input_shape = getattr(block, "input_shape", None)
            if input_shape:
                morph_result = comp.morph(input_val, input_shape, self)
                if morph_result.failure_reason:
                    # This overload doesn't match
                    continue
                score = morph_result.score
            else:
                # No input shape constraint - matches anything with lowest priority
                score = (0, 0, 0)

            # Compare scores (higher is better)
            if best_score is None or score > best_score:
                best_score = score
                best_block = block

        # If a block matched, return it
        if best_block is not None:
            return best_block

        # Fall back to shape morph if no block matched
        if callable.shape is not None:
            shape = callable.shape
            # For shape fallback, also use args as input when not piped
            input_val = piped if piped is not None else args
            morph_result = comp.morph(input_val, shape, self)
            if not morph_result.failure_reason:
                return morph_result.value
            # If morph failed but shape is a union with a default, use it
            if isinstance(shape, comp.ShapeUnion) and shape.default is not None:
                return shape.default

        return None
    def _make_child_frame(self, env, module=None):
        """Create a child frame for nested execution.

        Override in subclass to propagate tracing behavior.

        Args:
            env: Environment dict for the new frame
            module: Module for namespace lookups (defaults to self.module)

        Returns:
            New ExecutionFrame (or subclass)
        """
        child = ExecutionFrame(env=env, interp=self.interp, module=module or self.module, parent_frame=self, context=dict(self.context))
        child._pipeline_delivery = dict(self._pipeline_delivery)
        return child


# Instruction Classes
# ===================


def _inject_context(args_val, arg_shape, frame):
    """Augment args_val with context values for named shape fields not yet provided.

    For each named field declared in arg_shape that is absent from the explicit
    args struct, check whether the frame context carries a value under that name.
    If so, and the value passes the shape field's type constraint, inject it as an
    additional named field.  The mask step that follows will pick it up in phase-1
    (named matching) exactly like an explicitly-passed argument.

    Args:
        args_val: (Value) The caller-supplied argument struct
        arg_shape: (Shape) The function's argument shape
        frame: (ExecutionFrame) The calling frame whose context is consulted

    Returns:
        (Value) Possibly-augmented args struct (original if nothing was injected)
    """
    # Collect the names already present in explicit args, and count positionals
    explicit_names = set()
    positional_count = 0
    if isinstance(args_val.data, dict):
        for k in args_val.data:
            field_name = comp._morph._get_field_key(k)
            if field_name is not None:
                explicit_names.add(field_name)
            else:
                positional_count += 1

    # Count how many shape fields could still be satisfied by positional matching
    # (those not already provided by name).  If positionals could cover all of them,
    # context injection would just override what the caller intended.  Skip injection
    # for those fields so the mask positional-matching pass handles them instead.
    unnamed_fillable = [
        sf for sf in arg_shape.fields
        if sf.name not in explicit_names
    ]
    positionals_will_fill = min(positional_count, len(unnamed_fillable))

    injections = {}
    unfilled_by_positional = 0  # track fields context may still fill
    for shape_field in arg_shape.fields:
        name = shape_field.name
        if name is None or name in explicit_names:
            continue
        # If this field would be covered by a positional arg, skip context injection
        if unfilled_by_positional < positionals_will_fill:
            unfilled_by_positional += 1
            continue
        unfilled_by_positional += 1
        ctx_val = frame.context.get(name)
        if ctx_val is None:
            continue
        # Only inject if the value satisfies the field's type constraint
        constraint = comp._morph._resolve_shape_field(shape_field, frame)
        if constraint is None or comp._morph._check_type(ctx_val, constraint, frame):
            injections[comp.Value.from_python(name)] = ctx_val

    if not injections:
        return args_val

    new_data = dict(args_val.data) if isinstance(args_val.data, dict) else {}
    new_data.update(injections)
    return comp.Value(new_data)


def _frame_exit_cleanup(frame, result):
    """Auto-drop handles that didn't escape, transfer those that did to parent.

    Called at the end of every ExecutionFrame.run(). Does nothing unless the
    frame actually grabbed at least one handle.

    Args:
        frame: (ExecutionFrame) The frame that is exiting
        result: (Value | None) The return value of the frame
    """
    if not frame.live_handles:
        return

    # Materialise the set of handles that escaped through the return value.
    if result is not None and result.handles:
        escaped_set = comp.materialize_handles(result)
    else:
        escaped_set = frozenset()

    escaped = frame.live_handles & escaped_set
    leaked  = frame.live_handles - escaped_set

    # Auto-drop handles that didn't escape (still owned, not returned).
    for handle in leaked:
        if not handle.released:
            handle.released = True

    # Transfer handles that escaped to the parent frame's ownership.
    if escaped and frame.parent_frame is not None:
        parent = frame.parent_frame
        if parent.live_handles is None:
            parent.live_handles = set(escaped)
        else:
            parent.live_handles.update(escaped)
