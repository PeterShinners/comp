"""Main interpreter and instruction types.

Instructions are a higher-level bytecode representation that sits between
COP nodes and execution. Each instruction:
- Has a reference to its source COP node for error reporting
- Contains pre-resolved references (no runtime lookups)
- Holds literal Values when known at build time
- Uses a register-based model (named slots, not stack)

The instruction stream is linear and easy to march through.
Performance optimizations can happen later - clarity first.
"""

import hashlib
import os
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


class Interp:
    """Interpreter and state for Comp.

    An interpreter must be created to do most anything with comp objects
    or the language.
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

        # Module source cache: resource -> ModuleSource
        # Stores previously located module sources for etag validation and reuse
        self.module_cache = {}

        # Module cache: resource -> Module
        # Stores Module objects that have been created (may or may not be finalized)
        self.modules = {}

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
        src = comp._import.locate_resource(
            resource=anchored,
            etag=etag,
            search_paths=self.search_paths,
            search_fds=self.search_fds,
        )

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
                self.module_cache[anchored] = loc_cached  # prime resource key
                return loc_cached

        mod = comp.Module(src)
        if src.location:
            self.module_cache[src.location] = mod  # canonical key (abs path)
        self.module_cache[anchored] = mod           # resource string key
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
        self._new_module(mod)
        return mod


    def execute(self, instructions, env=None, module=None):
        """Execute a sequence of instructions.

        Args:
            instructions: List of Instruction objects
            env: Initial environment (variable bindings)
            module: The module being executed (for definition lookups)

        Returns:
            Final result Value (from last instruction)
        """
        frame = ExecutionFrame(env, interp=self, module=module)
        return frame.run(instructions)

    def build_namespace(self, module):
        """Build namespaces for a module and all its dependencies.

        Runs passes 1-4 (definitions, namespace, resolve aliases, apply aliases)
        on all modules in the dependency graph. This is sufficient for namespace
        inspection without doing the full build pipeline.

        Modules with parse errors in their definitions are skipped — the error
        is stored on the import record so downstream code can report it.

        Args:
            module: (Module) The root module
        """
        all_modules = self._collect_modules(module)
        failed = set()
        for mod in all_modules:
            try:
                mod.definitions()
            except (comp.ParseError, comp.CodeError):
                failed.add(id(mod))
        for mod in all_modules:
            if id(mod) not in failed:
                mod.namespace()
        for mod in all_modules:
            if id(mod) not in failed:
                mod.resolve_deferred()
        for mod in all_modules:
            if id(mod) not in failed:
                mod.apply_aliases()

    def build(self, module, fold=True, pure=False):
        """Build a module and all its dependencies through the full pipeline.

        This is the primary entry point for preparing a module for execution.
        It processes all discovered modules as a flat list (no recursive build),
        applying each pass independently.

        Build passes (each applied to ALL modules before the next begins):
        1. Definitions — lark parse statements into cop nodes
        2. Namespace — merge imports + local definitions
        3. Resolve aliases — resolve alias/export refs against namespace
        4. Apply aliases — inject resolved aliases into all namespaces
        5. Resolution — cop_resolve_names on every definition
        6. Fold/Optimize — coptimize for constant folding (optional)
        7. Codegen — generate instruction sequences
        8. Execute — run instructions to populate definition values

        Args:
            module: (Module) The root module to build
            fold: (bool) Whether to fold constants (default True)
            pure: (bool) Whether to evaluate pure functions at compile time

        Returns:
            (Module) The built module (same object, now fully prepared)
        """
        # Collect all modules in dependency order (imports before dependents)
        all_modules = self._collect_modules(module)

        # Pass 1: Definitions — parse all statements into cop nodes
        for mod in all_modules:
            mod.definitions()

        # Pass 2: Namespace — build namespace for each module
        for mod in all_modules:
            mod.namespace()

        # Pass 3: Resolve aliases — resolve alias/export refs against namespace
        for mod in all_modules:
            mod.resolve_deferred()

        # Pass 4: Apply aliases — inject resolved aliases into all namespaces
        for mod in all_modules:
            mod.apply_aliases()

        # Pass 5: Resolution — resolve all identifier cop nodes
        for mod in all_modules:
            mod_defs = mod.definitions()
            mod_ns = mod.namespace()
            for defn in mod_defs.values():
                if defn.resolved_cop is None:
                    defn.resolved_cop = comp.cop_resolve_names(
                        defn.original_cop, mod_ns
                    )

        # Pass 6: Fold/Optimize — constant folding
        if fold:
            for mod in all_modules:
                mod_defs = mod.definitions()
                mod_ns = mod.namespace()
                for defn in mod_defs.values():
                    defn.resolved_cop = comp.coptimize(
                        defn.resolved_cop, True, mod_ns
                    )

        # Pass 6b: Pure evaluation (optional)
        if pure:
            # Pre-execute pure definitions so their values are available
            # for folding. Modules are in dependency order, so imported
            # pure defs are ready before the modules that use them.
            for mod in all_modules:
                mod_defs = mod.definitions()
                mod_env = {}
                for name, defn in mod_defs.items():
                    if defn.pure and defn.resolved_cop is not None and defn.value is None:
                        try:
                            defn.instructions = comp.generate_code_for_definition(
                                defn.resolved_cop,
                                dispatch_own_name=defn.qualified,
                                dispatch_set_name=defn.qualified,
                                pure=True,
                            )
                            result = self.execute(defn.instructions, mod_env, module=mod)
                            defn.value = result
                            mod_env[name] = result
                        except Exception:
                            pass

            # Now fold definitions using namespace lookup (includes imports)
            for mod in all_modules:
                mod_defs = mod.definitions()
                mod_ns = mod.namespace()
                comp.evaluate_pure_definitions(mod_defs, mod_ns, self)
                if fold:
                    for defn in mod_defs.values():
                        defn.resolved_cop = comp.coptimize(
                            defn.resolved_cop, True, mod_ns
                        )

        # Pass 7: Codegen — generate instructions for all definitions
        for mod in all_modules:
            mod_defs = mod.definitions()
            for name, defn in mod_defs.items():
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
                    )
                except comp.CodeError as ce:
                    if not hasattr(ce, "module"):
                        ce.module = mod
                        ce.definition_name = name
                    raise
                except Exception as e:
                    raise comp.CodeError(
                        f"Code generation error for {mod.token}:{name}: {e}"
                    )

        # Pass 6: Execute — run instructions to populate definition values
        for mod in all_modules:
            mod_defs = mod.definitions()
            mod_env = {}
            # Shapes first (they don't depend on blocks)
            for name, defn in mod_defs.items():
                if defn.instructions and defn.value is None:
                    if defn.shape.qualified == "shape":
                        try:
                            result = self.execute(defn.instructions, mod_env, module=mod)
                        except comp.CodeError as ce:
                            if not hasattr(ce, "module") or ce.module is None:
                                ce.module = mod
                                ce.definition_name = name
                            raise
                        defn.value = result
                        mod_env[name] = result
            # Everything else
            for name, defn in mod_defs.items():
                if defn.instructions and defn.value is None:
                    try:
                        result = self.execute(defn.instructions, mod_env, module=mod)
                    except comp.CodeError as ce:
                        if not hasattr(ce, "module") or ce.module is None:
                            ce.module = mod
                            ce.definition_name = name
                        raise
                    defn.value = result
                    mod_env[name] = result

        return module

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

    def _new_module(self, module):
        """Internally scan and register module."""
        # module_cache entries (by resource string and abs path) are already
        # set by the module() method before this is called.

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

        module._register_imports(children, definitions=None, namespace=None)

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

    def __init__(self, env=None, interp=None, module=None, parent_frame=None, context=None):
        self.registers = []  # List indexed by instruction number
        self.env = env if env is not None else {}
        self._dollar_vars = {}  # "$", "$$", "$$$" — pipeline input context (per-invocation)
        self.interp = interp
        self.module = module
        self.parent_frame = parent_frame
        self.live_handles = None  # Set[HandleInstance] | None
        self.context = context if context is not None else {}
        self.failure = None  # comp.Value when a failure is propagating, else None

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

        Args:
            cop: (Value) COP node representing an expression

        Returns:
            (Value) The evaluated result
        """
        # Resolve identifiers against the module namespace so codegen
        # produces LoadVar instead of LoadLocal for namespace names.
        ns = self.module.namespace() if self.module else {}
        resolved = comp._resolve.cop_resolve_names(cop, ns)
        ctx = comp._codegen.CodeGenContext()
        ctx.build_expression(resolved)
        sub_frame = ExecutionFrame(
            env=dict(self.env),
            interp=self.interp,
            module=self.module,
            parent_frame=self,
            context=dict(self.context),
        )
        return sub_frame.run(ctx.instructions)

    def lookup(self, name):
        """Look up a name in environment, module namespace, and system definitions.

        Args:
            name: (str) Variable or definition name to look up

        Returns:
            (Definition | None) The definition if found, None otherwise
        """
        # Check local environment first
        if name in self.env:
            # Env contains Values, but we need to return a Definition-like object
            # For now, return None to fall through to namespace lookup
            pass

        # Check module namespace (includes imports and local definitions)
        if self.module:
            ns = self.module.namespace()
            if name in ns:
                item = ns[name]
                # Namespace contains DefinitionSet objects - extract single definition
                if isinstance(item, comp.DefinitionSet):
                    if len(item.definitions) == 1:
                        return next(iter(item.definitions))
                    # For multiple definitions, return the set itself
                    return item
                return item

        # Fall back to system module for builtins
        if self.interp and self.interp.system:
            system = self.interp.system
            if name in system._definitions:
                return system._definitions[name]

        return None

    def invoke_block(self, block_val, args, piped=None, source_cop=None):
        """Call a function with the given arguments.

        Args:
            block_val: Value containing a Block, DefinitionSet, Shape, or InternalCallable
            args: Value containing the argument struct
            piped: Value for piped input (or None if not piped)
            source_cop: (Value | None) COP node of the call site for error reporting

        Returns:
            Value result of the function call
        """
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

        # Handle DefinitionSet (legacy path — convert to Callable)
        if isinstance(callable_obj, comp.DefinitionSet):
            callable = comp.Callable("?")
            for defn in callable_obj.definitions:
                if defn.value is not None:
                    data = defn.value.data
                    if isinstance(data, comp.Callable):
                        for b in data.blocks:
                            callable.add_block(b)
                        if data.shape is not None and callable.shape is None:
                            callable.shape = data.shape
                    elif isinstance(data, comp.InternalCallable):
                        callable.add_block(data)
                    elif isinstance(data, (comp.Shape, comp.Tag, comp.ShapeUnion)):
                        callable.shape = data
            callable_obj = callable

        # Handle Callable (dispatch to best-matching block, shape, or single block)
        if isinstance(callable_obj, comp.Callable):
            if len(callable_obj.blocks) > 1 or (callable_obj.blocks and callable_obj.shape is not None):
                # Multiple blocks or blocks+shape: dispatch overload
                result = self._dispatch_overload(callable_obj, args, piped)
                if result is None:
                    names = [getattr(b, "qualified", "?") for b in callable_obj.blocks]
                    raise CompFail(_make_fail_value(
                        f"No matching overload found: {', '.join(names)}",
                        tag=comp.tag_fail_invoke,
                        cop_val=source_cop,
                    ))
                if isinstance(result, comp.Value):
                    return result
                block = result
            elif callable_obj.blocks:
                block = callable_obj.blocks[0]
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

        # If dispatch selected an InternalCallable (e.g. from a DefinitionSet
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

        # Share the closure environment directly — StoreLocal mutations
        # persist across invocations (e.g. a counter's !let count count+1).
        new_env = block.closure_env
        # Bind __self__ so !forward can locate the current Callable
        _self_callable = comp.Callable(block.qualified)
        _self_callable.add_block(block)
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
                cop_node = getattr(block_val, "cop", None) or source_cop
                err = comp.CodeError(
                    f"Input morph failed: {morph_result.failure_reason}"
                    f"\n  block: {block_name}, input_shape: {block.input_shape.qualified}"
                    f", input: {input_val.format()}"
                    f" ({input_val.shape.qualified if input_val.shape else '?'})",
                    cop_node)
                err.module = block.module
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

        # Spread :param names individually into the environment, TryInvoking each
        # value so that zero-arg callables are resolved to their result.
        # These come from :param declarations such as ":param timeout ~num=4".
        # After mask(), args_val is a named struct like {timeout: 4}.
        if block.param_names and isinstance(args_val.data, dict):
            param_set = set(block.param_names)
            _empty = comp.Value.from_python({})
            for k, v in args_val.data.items():
                fname = comp._morph._get_field_key(k)
                if fname is not None and fname in param_set:
                    # TryInvoke: if the bound value is callable, call it with no args
                    if isinstance(v.data, (comp.Callable, comp.InternalCallable)):
                        v = self.invoke_block(v, _empty, piped=None)
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
                block.body_instructions = comp.generate_code_for_definition(resolved_body)
            else:
                # No module - try to compile without namespace
                block.body_instructions = comp.generate_code_for_definition(block.body)
            
        # Execute the pre-compiled body instructions
        # Use the block's defining module for namespace lookups
        new_frame = self._make_child_frame(new_env, module=block.module)
        new_frame._dollar_vars = _dollar
        result = new_frame.run(block.body_instructions)

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
        for block in callable.blocks:
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
        return ExecutionFrame(env=env, interp=self.interp, module=module or self.module, parent_frame=self, context=dict(self.context))


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
