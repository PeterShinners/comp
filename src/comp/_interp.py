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
            resource="text",
            location="text",
            source_type="text",
            etag=hashlib.sha256(text.encode('utf-8')).hexdigest(),
            content=text,
            anchor="",
        )
        mod = comp.Module(src)
        self._new_module(mod)
        return mod


    def execute(self, instructions, env=None):
        """Execute a sequence of instructions.

        Args:
            instructions: List of Instruction objects
            env: Initial environment (variable bindings)

        Returns:
            Final result Value (from last instruction)
        """
        frame = ExecutionFrame(env, interp=self)
        return frame.run(instructions)

    def _new_module(self, module):
        """Internally scan and register module."""
        self.module_cache[module.token] = module
        scan = module.scan()
        imports = scan.to_python("imports") or []
        children = {}
        for imp in imports:
            name = imp.get("name")
            source = imp.get("source")
            if not (name and source):
                continue
            try:
                child = self.module(source, anchor=module.source.anchor)
                err = None
            except (comp.ModuleNotFoundError, comp.ModuleError) as e:
                child = None
                err = e
            children[name] = (child, err)
        module._register_imports(children, definitions=None, namespace=None)


class ExecutionFrame:
    """Runtime execution frame.

    Holds registers (temporaries) and environment (variables).
    This is the mutable state passed through instruction execution.

    Uses SSA-style implicit register numbering - instruction index IS the register.

    Attributes:
        registers: List of Values indexed by instruction number
        env: Dict mapping variable names to Values
        interp: The interpreter instance (for nested calls)
    """

    def __init__(self, env=None, interp=None):
        self.registers = []  # List indexed by instruction number
        self.env = env if env is not None else {}
        self.interp = interp

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

    def invoke_block(self, block_val, args, piped=None):
        """Call a function with the given arguments.

        Args:
            block_val: Value containing a Block or InternalCallable
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
        
        # Handle Block (Comp function)
        block = callable_obj
        
        # Create a new environment for the function
        # Start with the closure environment (captured at block definition)
        new_env = dict(block.closure_env)
        
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
            
        # Execute the pre-compiled body instructions
        new_frame = self._make_child_frame(new_env)
        result = new_frame.run(block.body_instructions)

        # Return the final result
        return result if result is not None else comp.Value.from_python(None)

    def _make_child_frame(self, env):
        """Create a child frame for nested execution.

        Override in subclass to propagate tracing behavior.

        Args:
            env: Environment dict for the new frame

        Returns:
            New ExecutionFrame (or subclass)
        """
        return ExecutionFrame(env=env, interp=self.interp)


# Instruction Classes
# ===================

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
    """Load a variable from the environment."""
    
    def __init__(self, cop, name):
        super().__init__(cop)
        self.name = name
    
    def execute(self, frame):
        # First check local environment
        if self.name in frame.env:
            value = frame.env[self.name]
            return frame.set_result(value)
        
        # Fall back to system module for builtins
        system = frame.interp.system
        if system and self.name in system._definitions:
            defn = system._definitions[self.name]
            if defn.value:
                return frame.set_result(defn.value)
        
        raise NameError(f"Variable '{self.name}' not defined")
    
    def format(self, idx):
        return f"%{idx}  LoadVar '{self.name}'"


class StoreVar(Instruction):
    """Store a value into the environment (no result register)."""
    
    def __init__(self, cop, name, source):
        super().__init__(cop)
        self.name = name
        self.source = source  # int index of source instruction
    
    def execute(self, frame):
        value = frame.get_value(self.source)
        frame.env[self.name] = value
        # StoreVar doesn't produce a result, but we still need to advance
        return frame.set_result(value)
    
    def format(self, idx):
        return f"%{idx}  StoreVar '{self.name}' = %{self.source}"


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

