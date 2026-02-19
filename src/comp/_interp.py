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

__all__ = ["Interp", "ExecutionFrame"]


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

        cached = self.module_cache.get(anchored)
        etag = cached.source.etag if cached else None
        src = comp._import.locate_resource(
            resource=anchored,
            etag=etag,
            search_paths=self.search_paths,
            search_fds=self.search_fds,
        )

        # If result is None, the etag matched - return cached version
        if src is None:
            return cached

        mod = comp.Module(src)
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

    def _new_module(self, module):
        """Internally scan and register module."""
        self.module_cache[module.token] = module

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
        parser = comp._parse.lark_parser("comp", start="start_import")
        try:
            tree = parser.parse(body)
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
        # Find the content token (middle one)
        source = ""
        for child in text_node.children:
            if isinstance(child, lark.Token) and "CONTENT" in child.type:
                source = child.value
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
    """

    def __init__(self, env=None, interp=None, module=None, parent_frame=None):
        self.registers = []  # List indexed by instruction number
        self.env = env if env is not None else {}
        self.interp = interp
        self.module = module
        self.parent_frame = parent_frame
        self.live_handles = None  # Set[HandleInstance] | None

    def run(self, instructions):
        """Execute a list of instructions, return final result.

        Args:
            instructions: List of instruction objects

        Returns:
            Value result of final instruction (or None)
        """
        result = None
        for idx, instr in enumerate(instructions):
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

    def invoke_block(self, block_val, args, piped=None):
        """Call a function with the given arguments.

        Args:
            block_val: Value containing a Block, DefinitionSet, Shape, or InternalCallable
            args: Value containing the argument struct
            piped: Value for piped input (or None if not piped)

        Returns:
            Value result of the function call
        """
        callable_obj = block_val.data
        
        # Handle InternalCallable (Python function)
        if isinstance(callable_obj, comp.InternalCallable):
            input_val = piped if piped is not None else args
            return callable_obj.func(input_val, args, self)
        
        # Handle Shape (morph input to shape)
        if isinstance(callable_obj, comp.Shape):
            input_val = piped if piped is not None else args
            morph_result = comp.morph(input_val, callable_obj, self)
            if morph_result.failure_reason:
                raise comp.CodeError(
                    f"Shape morph failed: {morph_result.failure_reason}",
                    block_val.cop if hasattr(block_val, "cop") else None
                )
            return morph_result.value
        
        # Handle DefinitionSet (dispatch to best-matching block, or shape as fallback)
        if isinstance(callable_obj, comp.DefinitionSet):
            result = self._dispatch_overload(callable_obj, args, piped)
            if result is None:
                raise comp.CodeError(
                    f"No matching overload found for input",
                    block_val.cop if hasattr(block_val, "cop") else None
                )
            # If dispatch returned a Value directly (from shape morph), return it
            if isinstance(result, comp.Value):
                return result
            # Otherwise it's a Block to invoke
            block = result
        else:
            # Handle Block (Comp function)
            block = callable_obj
        
        # Create a new environment for the function
        # Start with the closure environment (captured at block definition)
        new_env = dict(block.closure_env)
        
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
        input_val = piped if piped is not None else comp.Value.from_python({})
        args_val = args

        # Morph piped input to input shape
        if block.input_shape and isinstance(block.input_shape, comp.Shape):
            morph_result = comp.morph(input_val, block.input_shape, self)
            if morph_result.failure_reason:
                raise comp.CodeError(f"Input morph failed: {morph_result.failure_reason}", block_val.cop)
            input_val = morph_result.value

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
        result = new_frame.run(block.body_instructions)

        # Return the final result
        return result if result is not None else comp.Value.from_python(None)

    def _dispatch_overload(self, definition_set, args, piped):
        """Find the best-matching block from a DefinitionSet.

        Tries each definition's block input shape against the piped input 
        and returns the block with the best morph score. If no block matches,
        falls back to the shape definition (if any) and morphs to it.

        Args:
            definition_set: (DefinitionSet) Set of overloaded definitions
            args: (Value) Arguments struct
            piped: (Value | None) Piped input value

        Returns:
            (Block | Value | None) Best matching block, morphed Value from shape, or None
        """
        best_block = None
        best_score = None
        shape_defn = None
        
        # Iterate through definitions in the set
        for defn in definition_set.definitions:
            # Track shape definition for fallback
            if defn.shape is comp.shape_shape:
                shape_defn = defn
                continue
                
            # Skip if not a block definition or not folded yet
            if defn.shape is not comp.shape_block:
                continue
            if defn.value is None:
                continue
            
            block = defn.value.data
            
            # For single-parameter blocks, use args as input when not piped
            if block.input_name and not block.arg_name and piped is None:
                input_val = args
            else:
                input_val = piped if piped is not None else comp.Value.from_python({})
            
            # Try to morph input to this block's input shape
            if block.input_shape:
                morph_result = comp.morph(input_val, block.input_shape, self)
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
        if shape_defn is not None and shape_defn.value is not None:
            shape = shape_defn.value.data
            # For shape fallback, also use args as input when not piped
            input_val = piped if piped is not None else args
            morph_result = comp.morph(input_val, shape, self)
            if not morph_result.failure_reason:
                return morph_result.value
        
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
        return ExecutionFrame(env=env, interp=self.interp, module=module or self.module, parent_frame=self)


# Instruction Classes
# ===================


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

def _ensure_definition_value(defn, frame):
    """Lazily populate a definition's value if needed."""
    if defn.value is not None:
        return defn.value
    if defn.original_cop:
        cop_tag = comp.cop_tag(defn.original_cop)
        if cop_tag == "value.block":
            defn.value = comp.create_blockdef(defn.qualified, False, defn.original_cop)
            if defn.value and isinstance(defn.value.data, comp.Block):
                defn.value.data.module = frame.interp.module_cache.get(defn.module_id)
            return defn.value
        elif cop_tag == "shape.define":
            if frame.module:
                ns = frame.module.namespace()
                shape = comp.create_shape(defn.original_cop, ns)
                defn.value = comp.Value.from_python(shape)
                return defn.value
    return None


def _load_name(name, frame):
    """Resolve a name to a Value, checking env, module namespace, and system builtins."""
    if name in frame.env:
        return frame.env[name]

    if frame.module:
        ns = frame.module.namespace()
        if name in ns:
            item = ns[name]
            if isinstance(item, comp.DefinitionSet):
                if len(item.definitions) == 1:
                    defn = next(iter(item.definitions))
                    value = _ensure_definition_value(defn, frame)
                    if value:
                        return value
                for defn in item.definitions:
                    _ensure_definition_value(defn, frame)
                return comp.Value.from_python(item)
            elif hasattr(item, "value"):
                value = _ensure_definition_value(item, frame)
                if value:
                    return value

    system = frame.interp.system
    if system and name in system._definitions:
        defn = system._definitions[name]
        if defn.value:
            return defn.value

    raise NameError(f"Variable '{name}' not defined")

class Instruction:
    """Base class for all instructions."""
    
    def __init__(self, cop):
        self.cop = cop  # Source COP node for error reporting
    
    def execute(self, frame):
        """Execute this instruction in the given frame."""
        raise NotImplementedError()


class Const(Instruction):
    """Load a constant value."""
    
    def __init__(self, cop, value):
        super().__init__(cop)
        self.value = value
    
    def execute(self, frame):
        return frame.set_result(self.value)
    
    def format(self, idx):
        return f"%{idx}  Const {self.value.format()}"


class LoadVar(Instruction):
    """Load a variable from the environment or namespace.

    This is a pure load — no auto-invocation. The codegen emits an explicit
    TryInvoke instruction after LoadVar when the value is in a value position.
    For callable positions (Invoke/PipeInvoke), no TryInvoke is emitted.
    """

    def __init__(self, cop, name):
        super().__init__(cop)
        self.name = name

    def execute(self, frame):
        value = _load_name(self.name, frame)
        return frame.set_result(value)

    def format(self, idx):
        return f"%{idx}  LoadVar '{self.name}'"


class LoadLocal(Instruction):
    """Load a local variable from the frame environment.

    Used for let-bound locals and function parameters that are only known at
    runtime. Unlike LoadVar, this never consults the module namespace — the
    variable must already be present in frame.env (set by a StoreLocal).
    """

    def __init__(self, cop, name):
        super().__init__(cop)
        self.name = name

    def execute(self, frame):
        value = frame.env.get(self.name)
        if value is None:
            raise comp.CodeError(f"Undefined local variable: '{self.name}'")
        return frame.set_result(value)

    def format(self, idx):
        return f"%{idx}  LoadLocal '{self.name}'"


class TryInvoke(Instruction):
    """Invoke the value in a register with empty args if it is callable.

    If the value is a Block, InternalCallable, or DefinitionSet, it is called
    with no piped input and empty args. Otherwise the value passes through.

    The codegen emits this explicitly after value-position references and at
    the end of each definition's instruction sequence.
    """

    def __init__(self, cop, value):
        super().__init__(cop)
        self.value = value  # int register index

    def execute(self, frame):
        val = frame.get_value(self.value)
        if isinstance(val.data, (comp.Block, comp.InternalCallable, comp.DefinitionSet)):
            empty_args = comp.Value.from_python({})
            val = frame.invoke_block(val, empty_args, piped=None)
        return frame.set_result(val)

    def format(self, idx):
        return f"%{idx}  TryInvoke %{self.value}"


class LoadOverload(Instruction):
    """Load multiple overloaded definitions as a DefinitionSet."""
    
    def __init__(self, cop, names):
        super().__init__(cop)
        self.names = names  # list of qualified names
    
    def execute(self, frame):
        definition_set = comp.DefinitionSet()
        for name in self.names:
            # First check local environment for the definition
            if name in frame.env:
                value = frame.env[name]
                # If it's already a block value, we need to wrap it
                # This shouldn't normally happen - env usually has Values
                continue
            
            # Look up definition from module definitions
            defn = frame.lookup(name)
            if defn is not None:
                definition_set.definitions.add(defn)
        
        if not definition_set.definitions:
            raise NameError(f"No overloads found for '{self.names}'")
        
        result = comp.Value.from_python(definition_set)
        return frame.set_result(result)
    
    def format(self, idx):
        names_str = ", ".join(self.names)
        return f"%{idx}  LoadOverload [{names_str}]"


class StoreLocal(Instruction):
    """Store a value into the local frame environment.

    Used by op.let and struct.letassign to bind a name for subsequent
    LoadLocal references within the same function body.
    """

    def __init__(self, cop, name, source):
        super().__init__(cop)
        self.name = name
        self.source = source  # int index of source instruction

    def execute(self, frame):
        value = frame.get_value(self.source)
        frame.env[self.name] = value
        return frame.set_result(value)

    def format(self, idx):
        return f"%{idx}  StoreLocal '{self.name}' = %{self.source}"


class BinOp(Instruction):
    """Binary arithmetic/logical operation."""
    
    def __init__(self, cop, op, left, right):
        super().__init__(cop)
        self.op = op
        self.left = left    # int index
        self.right = right  # int index
    
    def execute(self, frame):
        left_val = frame.get_value(self.left)
        right_val = frame.get_value(self.right)
        result = comp._ops.math_binary(self.op, left_val, right_val)
        return frame.set_result(result)
    
    def format(self, idx):
        return f"%{idx}  BinOp '{self.op}' %{self.left} %{self.right}"


class UnOp(Instruction):
    """Unary arithmetic/logical operation."""

    def __init__(self, cop, op, operand):
        super().__init__(cop)
        self.op = op
        self.operand = operand  # int index

    def execute(self, frame):
        operand_val = frame.get_value(self.operand)
        result = comp._ops.math_unary(self.op, operand_val)
        return frame.set_result(result)

    def format(self, idx):
        return f"%{idx}  UnOp '{self.op}' %{self.operand}"


class CmpOp(Instruction):
    """Comparison operation (==, !=, <, <=, >, >=)."""

    def __init__(self, cop, op, left, right):
        super().__init__(cop)
        self.op = op
        self.left = left    # int index
        self.right = right  # int index

    def execute(self, frame):
        left_val = frame.get_value(self.left)
        right_val = frame.get_value(self.right)
        result = comp._ops.compare(self.op, left_val, right_val)
        return frame.set_result(result)

    def format(self, idx):
        return f"%{idx}  CmpOp '{self.op}' %{self.left} %{self.right}"


class GetField(Instruction):
    """Get a named field from a struct."""
    
    def __init__(self, cop, struct_reg, field):
        super().__init__(cop)
        self.struct_reg = struct_reg  # Register containing the struct
        self.field = field  # Field name to extract
    
    def execute(self, frame):
        struct_val = frame.get_value(self.struct_reg)
        # Look up the field by name
        field_key = comp.Value.from_python(self.field)
        result = struct_val.data.get(field_key)
        if result is None:
            raise comp.CodeError(f"Field '{self.field}' not found in struct", self.cop)
        return frame.set_result(result)
    
    def format(self, idx):
        return f"%{idx}  GetField %{self.struct_reg}.{self.field}"


class GetIndex(Instruction):
    """Get a field from a struct by position (0-based)."""
    
    def __init__(self, cop, struct_reg, index):
        super().__init__(cop)
        self.struct_reg = struct_reg  # Register containing the struct
        self.index = index  # 0-based position
    
    def execute(self, frame):
        struct_val = frame.get_value(self.struct_reg)
        # Get field by position
        items = list(struct_val.data.items())
        if self.index < 0 or self.index >= len(items):
            raise comp.CodeError(f"Index {self.index} out of range for struct with {len(items)} fields", self.cop)
        _, result = items[self.index]
        return frame.set_result(result)
    
    def format(self, idx):
        return f"%{idx}  GetIndex %{self.struct_reg}.#{self.index}"


class BuildStruct(Instruction):
    """Build a struct from field values."""
    
    def __init__(self, cop, fields):
        super().__init__(cop)
        self.fields = fields  # List of (key, source_idx) tuples
    
    def execute(self, frame):
        struct_data = {}
        for key, source in self.fields:
            value = frame.get_value(source)
            struct_data[key] = value
        result = comp.Value.from_python(struct_data)
        return frame.set_result(result)
    
    def format(self, idx):
        parts = []
        for key, src in self.fields:
            if isinstance(key, comp.Unnamed):
                parts.append(f"%{src}")
            else:
                parts.append(f"{key}=%{src}")
        return f"%{idx}  BuildStruct ({' '.join(parts)})"


class BuildBlock(Instruction):
    """Build a block/function value."""
    
    def __init__(self, cop, signature_cop, body_instructions):
        super().__init__(cop)
        self.signature_cop = signature_cop
        self.body_instructions = body_instructions
    
    def execute(self, frame):
        # Create a Block object and store the execution data
        block = comp.Block("anonymous", private=False)
        block.module = frame.module  # Capture the defining module
        block.body_instructions = self.body_instructions
        block.closure_env = dict(frame.env)
        block.signature_cop = self.signature_cop
        
        # Parse signature to extract parameter names and shapes
        # shape.define contains shape.field children with name="paramname" attribute
        sig_kids = comp.cop_kids(self.signature_cop)
        for i, field_cop in enumerate(sig_kids):
            # shape.field has name attribute directly
            try:
                param_name = field_cop.to_python("name")
            except (KeyError, AttributeError):
                param_name = None

            # Extract shape from field children
            param_shape = None
            field_kids = comp.cop_kids(field_cop)
            for fkid in field_kids:
                fkid_tag = comp.cop_tag(fkid)
                if fkid_tag == "shape.define":
                    # Build the shape from the nested shape.define
                    param_shape = self._build_shape_from_cop(fkid, frame)
                    break
                elif fkid_tag == "value.identifier":
                    # Direct reference like ~num - look it up
                    id_kids = comp.cop_kids(fkid)
                    if id_kids:
                        ref_name = id_kids[0].to_python("value")
                        defn = frame.lookup(ref_name) if hasattr(frame, "lookup") else None
                        if defn and defn.value:
                            param_shape = defn.value.data
                    break

            if param_name:
                if i == 0:
                    block.input_name = param_name
                    block.input_shape = param_shape
                elif i == 1:
                    block.arg_name = param_name
                    block.arg_shape = param_shape
        
        result = comp.Value(block)
        return frame.set_result(result)

    def _build_shape_from_cop(self, shape_cop, frame):
        """Build a Shape object from a shape.define COP node."""
        shape = comp.Shape("anonymous", private=False)

        for kid in comp.cop_kids(shape_cop):
            kid_tag = comp.cop_tag(kid)
            if kid_tag != "shape.field":
                continue

            # Get field name
            try:
                field_name = kid.to_python("name")
            except (KeyError, AttributeError):
                field_name = None

            # Get shape constraint and default from children
            field_shape = None
            field_default = None
            field_kids = comp.cop_kids(kid)

            for j, fkid in enumerate(field_kids):
                fkid_tag = comp.cop_tag(fkid)
                if fkid_tag.startswith("value."):
                    if field_shape is None:
                        # First value is shape reference
                        if fkid_tag == "value.identifier":
                            id_kids = comp.cop_kids(fkid)
                            if id_kids:
                                ref_name = id_kids[0].to_python("value")
                                defn = frame.lookup(ref_name) if hasattr(frame, "lookup") else None
                                if defn and defn.value:
                                    field_shape = defn.value.data
                        # Mark that we've seen the shape, even if lookup failed
                        if field_shape is None:
                            field_shape = comp.shape_any  # fallback
                    else:
                        # Second value is default - evaluate simple constants
                        field_default = self._eval_simple_value(fkid)

            field_obj = comp.ShapeField(name=field_name, shape=field_shape, default=field_default)
            shape.fields.append(field_obj)

        return shape

    def _eval_simple_value(self, cop):
        """Evaluate a simple constant COP to a Value."""
        import decimal
        tag = comp.cop_tag(cop)

        if tag == "value.number":
            literal = cop.to_python("value")
            return comp.Value.from_python(decimal.Decimal(literal))
        elif tag == "value.text":
            literal = cop.to_python("value")
            return comp.Value.from_python(literal)
        elif tag == "value.identifier":
            # Could be nil, true, false
            id_kids = comp.cop_kids(cop)
            if id_kids:
                name = id_kids[0].to_python("value")
                if name == "nil":
                    return comp.Value.from_python(comp.tag_nil)
                elif name == "true":
                    return comp.Value.from_python(comp.tag_true)
                elif name == "false":
                    return comp.Value.from_python(comp.tag_false)
        # For complex expressions, return None (no default)
        return None
    
    def format(self, idx):
        return f"%{idx}  BuildBlock ({len(self.body_instructions)} body)"


class BuildShape(Instruction):
    """Build a shape value from field definitions."""

    def __init__(self, cop, fields):
        super().__init__(cop)
        self.fields = fields  # List of (name, shape_idx, default_idx) tuples

    def execute(self, frame):
        shape = comp.Shape("anonymous", private=False)

        for name, shape_idx, default_idx in self.fields:
            # Get shape constraint if provided
            shape_constraint = None
            if shape_idx is not None:
                shape_val = frame.get_value(shape_idx)
                if shape_val and shape_val.data:
                    shape_constraint = shape_val.data

            # Get default if provided
            default_val = None
            if default_idx is not None:
                default_val = frame.get_value(default_idx)

            # Create ShapeField - store resolved values in shape/default
            # The morph code will check for both COP nodes and resolved values
            field = comp.ShapeField(name=name, shape=shape_constraint, default=default_val)
            shape.fields.append(field)

        result = comp.Value(shape)
        return frame.set_result(result)

    def format(self, idx):
        parts = [f"{n or '_'}" for n, s, d in self.fields]
        return f"%{idx}  BuildShape ({' '.join(parts)})"


class BuildShapeUnion(Instruction):
    """Build a shape union from member shapes."""

    def __init__(self, cop, member_indices):
        super().__init__(cop)
        self.member_indices = member_indices  # List of instruction indices

    def execute(self, frame):
        shapes = []
        for idx in self.member_indices:
            val = frame.get_value(idx)
            if val and val.data:
                shapes.append(val.data)

        union = comp.ShapeUnion(shapes)
        result = comp.Value(union)
        return frame.set_result(result)

    def format(self, idx):
        members = ' '.join(f'%{m}' for m in self.member_indices)
        return f"%{idx}  BuildShapeUnion ({members})"


class Invoke(Instruction):
    """Invoke a function/block with arguments (no piped input)."""
    
    def __init__(self, cop, callable, args):
        super().__init__(cop)
        self.callable = callable  # int index
        self.args = args          # int index
    
    def execute(self, frame):
        callable_val = frame.get_value(self.callable)
        args_val = frame.get_value(self.args)
        result = frame.invoke_block(callable_val, args_val, piped=None)
        return frame.set_result(result)
    
    def format(self, idx):
        return f"%{idx}  Invoke %{self.callable} (%{self.args})"


class PipeInvoke(Instruction):
    """Invoke a function/block with piped input and arguments."""
    
    def __init__(self, cop, callable, piped, args):
        super().__init__(cop)
        self.callable = callable  # int index
        self.piped = piped        # int index - the piped input value
        self.args = args          # int index
    
    def execute(self, frame):
        callable_val = frame.get_value(self.callable)
        piped_val = frame.get_value(self.piped)
        args_val = frame.get_value(self.args)
        result = frame.invoke_block(callable_val, args_val, piped=piped_val)
        return frame.set_result(result)
    
    def format(self, idx):
        return f"%{idx}  PipeInvoke %{self.callable} (%{self.piped} | %{self.args})"


class GrabHandle(Instruction):
    """Create a handle instance from a tag value (!grab)."""

    def __init__(self, cop, tag_reg):
        super().__init__(cop)
        self.tag_reg = tag_reg  # Register containing the Tag value

    def execute(self, frame):
        tag_val = frame.get_value(self.tag_reg)
        result = comp._tag.grab_handle(tag_val, frame)
        # Register handle with this frame so it can be auto-dropped on exit.
        handle = result.data
        if frame.live_handles is None:
            frame.live_handles = {handle}
        else:
            frame.live_handles.add(handle)
        return frame.set_result(result)

    def format(self, idx):
        return f"%{idx}  GrabHandle %{self.tag_reg}"


class DropHandle(Instruction):
    """Release a handle, marking it as dropped (!drop)."""

    def __init__(self, cop, handle_reg):
        super().__init__(cop)
        self.handle_reg = handle_reg  # Register containing the HandleInstance value

    def execute(self, frame):
        handle_val = frame.get_value(self.handle_reg)
        result = comp._tag.drop_handle(handle_val, frame)
        # Remove from live tracking so the frame exit doesn't double-drop it.
        if frame.live_handles and isinstance(handle_val.data, comp.HandleInstance):
            frame.live_handles.discard(handle_val.data)
        return frame.set_result(result)

    def format(self, idx):
        return f"%{idx}  DropHandle %{self.handle_reg}"


class PullHandle(Instruction):
    """Get private data from a handle (!pull)."""

    def __init__(self, cop, handle_reg):
        super().__init__(cop)
        self.handle_reg = handle_reg  # Register containing the HandleInstance value

    def execute(self, frame):
        handle_val = frame.get_value(self.handle_reg)
        result = comp._tag.pull_handle(handle_val, frame)
        return frame.set_result(result)

    def format(self, idx):
        return f"%{idx}  PullHandle %{self.handle_reg}"


class PushHandle(Instruction):
    """Store private data in a handle (!push)."""

    def __init__(self, cop, handle_reg, data_reg):
        super().__init__(cop)
        self.handle_reg = handle_reg  # Register containing the HandleInstance value
        self.data_reg = data_reg      # Register containing the data to store

    def execute(self, frame):
        handle_val = frame.get_value(self.handle_reg)
        data_val = frame.get_value(self.data_reg)
        result = comp._tag.push_handle(handle_val, data_val, frame)
        return frame.set_result(result)

    def format(self, idx):
        return f"%{idx}  PushHandle %{self.handle_reg} %{self.data_reg}"
