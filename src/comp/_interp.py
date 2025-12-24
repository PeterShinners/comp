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

import comp

__all__ = ["Interp", "Instruction", "Const", "BinOp", "UnOp", "LoadVar", "StoreVar", "Invoke", "BuildStruct", "BuildBlock"]


class Instruction:
    """Base class for all instructions.

    All instruction subclasses should have:
    - cop: Reference to the COP node that generated this instruction
    - dest: Name of register to store result (None for no result)
    """

    def execute(self, frame):
        """Execute this instruction in the given frame.

        Args:
            frame: ExecutionFrame with registers and environment

        Returns:
            Value result (or None)
        """
        raise NotImplementedError(f"{self.__class__.__name__}.execute")


class Const(Instruction):
    """Load a constant value.

    Attributes:
        cop: COP node that generated this instruction
        value: The constant Value to load
        dest: (str or None) Optional destination register
    """

    def __init__(self, cop, value, dest=None):
        self.cop = cop
        self.value = value
        self.dest = dest

    def execute(self, frame):
        if self.dest:
            frame.registers[self.dest] = self.value
        return self.value

    def __repr__(self):
        return f"Const(value={self.value.format()}, dest={self.dest!r})"


class BinOp(Instruction):
    """Binary operation (add, subtract, multiply, etc).

    Attributes:
        cop: COP node that generated this instruction
        op: (str) Operator string ("+", "-", "*", "/", etc)
        left: (str or Value) Register name or Value
        right: (str or Value) Register name or Value
        dest: (str or None) Optional destination register
    """

    def __init__(self, cop, op, left, right, dest=None):
        self.cop = cop
        self.op = op
        self.left = left
        self.right = right
        self.dest = dest

    def execute(self, frame):
        left_val = frame.get_value(self.left)
        right_val = frame.get_value(self.right)
        result = comp.math_binary(self.op, left_val, right_val)
        if self.dest:
            frame.registers[self.dest] = result
        return result

    def __repr__(self):
        left_str = self.left.format() if hasattr(self.left, "format") else self.left
        right_str = self.right.format() if hasattr(self.right, "format") else self.right
        return f"BinOp(op={self.op!r}, left={left_str}, right={right_str}, dest={self.dest!r})"


class UnOp(Instruction):
    """Unary operation (negate, not, etc).

    Attributes:
        cop: COP node that generated this instruction
        op: (str) Operator string ("-", "not", etc)
        operand: (str or Value) Register name or Value
        dest: (str or None) Optional destination register
    """

    def __init__(self, cop, op, operand, dest=None):
        self.cop = cop
        self.op = op
        self.operand = operand
        self.dest = dest

    def execute(self, frame):
        operand_val = frame.get_value(self.operand)
        result = comp.math_unary(self.op, operand_val)
        if self.dest:
            frame.registers[self.dest] = result
        return result

    def __repr__(self):
        operand_str = self.operand.format() if hasattr(self.operand, "format") else self.operand
        return f"UnOp(op={self.op!r}, operand={operand_str}, dest={self.dest!r})"


class LoadVar(Instruction):
    """Load a variable from the environment.

    Attributes:
        cop: COP node that generated this instruction
        name: (str) Variable name to load
        dest: (str or None) Optional destination register
    """

    def __init__(self, cop, name, dest=None):
        self.cop = cop
        self.name = name
        self.dest = dest

    def execute(self, frame):
        result = frame.env.get(self.name)
        if result is None:
            raise NameError(f"Undefined variable: {self.name}")
        if self.dest:
            frame.registers[self.dest] = result
        return result

    def __repr__(self):
        return f"LoadVar(name={self.name!r}, dest={self.dest!r})"


class StoreVar(Instruction):
    """Store a value to a variable in the environment.

    Attributes:
        cop: COP node that generated this instruction
        name: (str) Variable name to store to
        source: (str or Value) Register name or Value to store
        dest: (str or None) Optional destination register (usually None)
    """

    def __init__(self, cop, name, source, dest=None):
        self.cop = cop
        self.name = name
        self.source = source
        self.dest = dest

    def execute(self, frame):
        value = frame.get_value(self.source)
        frame.env[self.name] = value
        return value

    def __repr__(self):
        source_str = self.source.format() if hasattr(self.source, "format") else self.source
        return f"StoreVar(name={self.name!r}, source={source_str}, dest={self.dest!r})"


class Invoke(Instruction):
    """Invoke a function (block value) with arguments.

    Attributes:
        cop: COP node that generated this instruction
        callable: (str or Value) Register name or Value containing the function
        args: (str or Value) Register name or Value containing the argument struct
        dest: (str or None) Optional destination register
    """

    def __init__(self, cop, callable, args, dest=None):
        self.cop = cop
        self.callable = callable
        self.args = args
        self.dest = dest

    def execute(self, frame):
        func = frame.get_value(self.callable)
        args = frame.get_value(self.args)
        result = frame.call_function(func, args)
        if self.dest:
            frame.registers[self.dest] = result
        return result

    def __repr__(self):
        callable_str = self.callable.format() if hasattr(self.callable, "format") else self.callable
        args_str = self.args.format() if hasattr(self.args, "format") else self.args
        return f"Call(callable={callable_str}, args={args_str}, dest={self.dest!r})"


class BuildStruct(Instruction):
    """Build a struct value from fields.

    Attributes:
        cop: COP node that generated this instruction
        fields: List of (key, value) pairs where:
            - key is either comp.Unnamed() for positional or a string/Value for named
            - value is either a register name (str) or a Value
        dest: (str or None) Destination register
    """

    def __init__(self, cop, fields, dest=None):
        self.cop = cop
        self.fields = fields  # [(key, value_or_register), ...]
        self.dest = dest

    def execute(self, frame):
        # Build the struct dictionary
        struct_dict = {}
        for key, value_source in self.fields:
            value = frame.get_value(value_source)
            # Ensure keys are proper types (Unnamed or Value, not plain strings)
            if isinstance(key, str):
                key = comp.Value(key)
            struct_dict[key] = value

        result = comp.Value(struct_dict)
        if self.dest:
            frame.registers[self.dest] = result
        return result

    def __repr__(self):
        fields_str = []
        for key, val in self.fields:
            key_str = "#" if isinstance(key, comp.Unnamed) else repr(key)
            val_str = val.format() if hasattr(val, "format") else val
            fields_str.append(f"{key_str}={val_str}")
        return f"BuildStruct([{', '.join(fields_str)}], dest={self.dest!r})"


class BuildBlock(Instruction):
    """Create a block (function/closure) value.

    Attributes:
        cop: COP node that generated this instruction
        signature_cop: COP node for the signature (shape.define)
        body_instructions: List of pre-compiled instructions for the body
        dest: (str or None) Destination register
    """

    def __init__(self, cop, signature_cop, body_instructions, dest=None):
        self.cop = cop
        self.signature_cop = signature_cop
        self.body_instructions = body_instructions
        self.dest = dest

    def execute(self, frame):
        # Create a block value that contains the compiled instructions
        # Store as a special block type (we'll need a Block class)
        block = Block(self.signature_cop, self.body_instructions, frame.env.copy())
        result = comp.Value(block)
        result.cop = self.cop
        if self.dest:
            frame.registers[self.dest] = result
        return result

    def __repr__(self):
        return f"BuildBlock(sig=..., body={len(self.body_instructions)} instrs, dest={self.dest!r})"


class Block:
    """Runtime block value (compiled function/closure).

    Attributes:
        signature_cop: COP node for the signature
        body_instructions: Pre-compiled instructions
        closure_env: Captured environment (for closures)
    """

    def __init__(self, signature_cop, body_instructions, closure_env):
        self.signature_cop = signature_cop
        self.body_instructions = body_instructions
        self.closure_env = closure_env

    def __repr__(self):
        return f"Block({len(self.body_instructions)} instrs)"


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

    def call_function(self, func, args):
        """Call a function with the given arguments.

        Args:
            func: Value containing a Block
            args: Value containing the argument struct

        Returns:
            Value result of the function call
        """
        # Check if func contains a Block
        if not isinstance(func.data, Block):
            raise TypeError(f"Cannot call non-block value (got {type(func.data).__name__})")

        block = func.data

        # Create a new environment for the function
        # Start with the closure environment (captured at block definition)
        # TODO: Handle signature/parameters properly - bind args to param names
        new_env = dict(block.closure_env)

        # Execute the pre-compiled body instructions
        new_frame = ExecutionFrame(env=new_env, interp=self.interp)
        result = None

        for instr in block.body_instructions:
            result = instr.execute(new_frame)

        # Return the final result
        return result if result is not None else comp.Value.from_python(None)


class Interp:
    """Interpreter and state for Comp.

    An interpreter must be created to do most anything with comp objects
    or the language.
    """

    def __init__(self):
        self.system = comp._module.SystemModule.get()

    def __repr__(self):
        return "Interp<>"

    def __hash__(self):
        return id(self)

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
