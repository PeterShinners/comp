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

__all__ = ["Interp"]


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
        result = None

        for instr in instructions:
            result = instr.execute(frame)

        return result

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

    Attributes:
        registers: Dict mapping register names to Values
        env: Dict mapping variable names to Values
        interp: The interpreter instance (for nested calls)
    """

    def __init__(self, env=None, interp=None):
        self.registers = {}
        self.env = env if env is not None else {}
        self.interp = interp

    def get_value(self, source):
        """Get a value from either a register or directly.

        Args:
            source: Either a register name (str) or a Value

        Returns:
            The Value
        """
        if isinstance(source, str):
            if source not in self.registers:
                raise ValueError(f"Undefined register: {source}")
            return self.registers[source]
        return source

    def invoke_block(self, block, args):
        """Call a function with the given arguments.

        Args:
            block: Value containing a Block
            args: Value containing the argument struct

        Returns:
            Value result of the function call
        """
        # Get the function signature from the block
        signature_cop = block.data['signature_cop']
        
        # Parse signature to determine input parameters
        sig_kids = comp.cop_kids(signature_cop)
        param_names = []
        for field_cop in sig_kids:
            if hasattr(field_cop, 'to_python'):
                name = field_cop.to_python('name')
                if name:
                    param_names.append(name)
        
        # Create a new environment for the function
        # Start with the closure environment (captured at block definition)
        new_env = dict(block.data['closure_env'])
        
        # For now, treat the args as the argument input (not piped input)
        # TODO: Distinguish between piped input vs argument input
        if len(param_names) >= 2:
            # Two parameters: first is piped input, second is arguments
            # For dos(2), we don't have piped input, so use nil for first param
            new_env[param_names[0]] = comp.Value.from_python(None)  # piped input
            new_env[param_names[1]] = args  # argument input
        elif len(param_names) == 1:
            # One parameter: could be either piped or argument
            # For now, assume it's argument input
            new_env[param_names[0]] = args
            
        # Execute the pre-compiled body instructions
        new_frame = ExecutionFrame(env=new_env, interp=self.interp)
        result = None

        for instr in block.data['body_instructions']:
            result = instr.execute(new_frame)

        # Return the final result
        return result if result is not None else comp.Value.from_python(None)


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
    """Load a constant value into a register."""
    
    def __init__(self, cop, value, dest):
        super().__init__(cop)
        self.value = value
        self.dest = dest
    
    def execute(self, frame):
        frame.registers[self.dest] = self.value
        return self.value
    
    def __str__(self):
        return f"const {self.dest} = {self.value.format()}"


class LoadVar(Instruction):
    """Load a variable from the environment into a register."""
    
    def __init__(self, cop, name, dest):
        super().__init__(cop)
        self.name = name
        self.dest = dest
    
    def execute(self, frame):
        if self.name not in frame.env:
            raise NameError(f"Variable '{self.name}' not defined")
        value = frame.env[self.name]
        frame.registers[self.dest] = value
        return value
    
    def __str__(self):
        return f"load {self.dest} = {self.name}"


class StoreVar(Instruction):
    """Store a register value into the environment."""
    
    def __init__(self, cop, name, source):
        super().__init__(cop)
        self.name = name
        self.source = source
    
    def execute(self, frame):
        value = frame.get_value(self.source)
        frame.env[self.name] = value
        return value
    
    def __str__(self):
        return f"store {self.name} = {self.source}"


class BinOp(Instruction):
    """Binary arithmetic/logical operation."""
    
    def __init__(self, cop, op, left, right, dest):
        super().__init__(cop)
        self.op = op
        self.left = left
        self.right = right
        self.dest = dest
    
    def execute(self, frame):
        left_val = frame.get_value(self.left)
        right_val = frame.get_value(self.right)
        
        # Use the comp operations system
        result = comp._ops.binary_op(left_val, self.op, right_val)
        frame.registers[self.dest] = result
        return result
    
    def __str__(self):
        return f"binop {self.dest} = {self.left} {self.op} {self.right}"


class UnOp(Instruction):
    """Unary arithmetic/logical operation."""
    
    def __init__(self, cop, op, operand, dest):
        super().__init__(cop)
        self.op = op
        self.operand = operand
        self.dest = dest
    
    def execute(self, frame):
        operand_val = frame.get_value(self.operand)
        
        # Use the comp operations system
        result = comp._ops.unary_op(operand_val, self.op)
        frame.registers[self.dest] = result
        return result
    
    def __str__(self):
        return f"unop {self.dest} = {self.op}{self.operand}"


class BuildStruct(Instruction):
    """Build a struct from field values."""
    
    def __init__(self, cop, fields, dest):
        super().__init__(cop)
        self.fields = fields  # List of (key, value) tuples
        self.dest = dest
    
    def execute(self, frame):
        # Build the struct data dict
        struct_data = {}
        for key, source in self.fields:
            value = frame.get_value(source)
            struct_data[key] = value
        
        # Create the struct Value
        result = comp.Value.from_python(struct_data)
        frame.registers[self.dest] = result
        return result
    
    def __str__(self):
        field_strs = [f"{k}={v}" for k, v in self.fields]
        return f"struct {self.dest} = {{{', '.join(field_strs)}}}"


class BuildBlock(Instruction):
    """Build a block/function value."""
    
    def __init__(self, cop, signature_cop, body_instructions, dest):
        super().__init__(cop)
        self.signature_cop = signature_cop
        self.body_instructions = body_instructions
        self.dest = dest
    
    def execute(self, frame):
        # Create a Block Value containing the instructions and signature
        block_data = {
            'signature_cop': self.signature_cop,
            'body_instructions': self.body_instructions,
            'closure_env': dict(frame.env)  # Capture current environment
        }
        result = comp.Value(comp.shape_block, block_data)
        frame.registers[self.dest] = result
        return result
    
    def __str__(self):
        return f"block {self.dest} = <{len(self.body_instructions)} instructions>"


class Invoke(Instruction):
    """Invoke a function/block with arguments."""
    
    def __init__(self, cop, callable, args, dest):
        super().__init__(cop)
        self.callable = callable
        self.args = args
        self.dest = dest
    
    def execute(self, frame):
        callable_val = frame.get_value(self.callable)
        args_val = frame.get_value(self.args)
        
        # Use the frame's invoke_block method
        result = frame.invoke_block(callable_val, args_val)
        frame.registers[self.dest] = result
        return result
    
    def __str__(self):
        return f"invoke {self.dest} = {self.callable}({self.args})"

