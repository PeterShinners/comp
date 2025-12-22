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

__all__ = ["Interp", "Instruction", "Const", "BinOp", "UnOp", "LoadVar", "StoreVar"]


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


class ExecutionFrame:
    """Runtime execution frame.

    Holds registers (temporaries) and environment (variables).
    This is the mutable state passed through instruction execution.

    Attributes:
        registers: Dict mapping register names to Values
        env: Dict mapping variable names to Values
    """

    def __init__(self, env=None):
        self.registers = {}
        self.env = env if env is not None else {}

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
        frame = ExecutionFrame(env)
        result = None

        for instr in instructions:
            result = instr.execute(frame)

        return result
