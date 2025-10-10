"""Pipeline AST nodes for the engine.

Pipelines are the core execution model in Comp. They thread a value through
a sequence of operations, with each operation receiving the previous result
as input.

Syntax: [seed |op1 |op2 |op3]
- seed: Initial value (optional - if missing, uses $in scope)
- operations: List of pipeline operations that transform the value
"""

from .base import ValueNode
from ..value import Value


class Pipeline(ValueNode):
    """Pipeline expression: [seed |op1 |op2 ...]

    Evaluates seed (or uses $in if no seed), then threads the value through
    each operation in sequence. Each operation sees the previous result as $in.

    The pipeline creates a new scope frame for each operation with:
    - in: Current value flowing through pipeline
    - out: (Future) Output scope for side effects

    Correct by Construction:
    - seed is ValueNode or None
    - operations is list of PipelineOp nodes
    """

    def __init__(self, seed: ValueNode | None, operations: list):
        """Create pipeline.

        Args:
            seed: Initial value (None for unseeded pipeline)
            operations: List of PipelineOp nodes

        Raises:
            TypeError: If seed is not ValueNode or None, or operations not a list
        """
        if seed is not None and not isinstance(seed, ValueNode):
            raise TypeError("Pipeline seed must be ValueNode or None")
        if not isinstance(operations, list):
            raise TypeError("Pipeline operations must be a list")

        self.seed = seed
        self.operations = operations

    def evaluate(self, engine):
        """Evaluate pipeline by threading value through operations.

        1. Get initial value (seed or $in scope)
        2. For each operation:
           - Set up scope frame with current value as $in
           - Evaluate operation (which will use $in)
           - Result becomes next $in
        3. Return final result
        """
        # Get initial value
        if self.seed is not None:
            current = yield self.seed
            if engine.is_fail(current):
                return current
        else:
            # Unseeded pipeline uses existing $in scope
            current = engine.get_scope('in')
            if current is None:
                return engine.fail("Unseeded pipeline requires $in scope")

        # Thread through each operation
        for i, op in enumerate(self.operations):
            # Create scope frame with current value as $in
            # Use **dict to avoid 'in' keyword syntax error
            with engine.scope_frame(**{'in': current}):
                # Check if next operation can handle fails
                # If yes, evaluate this op with allow_failures
                next_can_handle = (
                    i + 1 < len(self.operations) and
                    getattr(self.operations[i + 1], 'can_handle_fail', False)
                )

                if next_can_handle:
                    # Next op handles fails - allow this op to fail
                    with engine.allow_failures():
                        current = yield op
                else:
                    # No fail handler - fail normally
                    current = yield op
                    if engine.is_fail(current):
                        return current

        return current

    def unparse(self) -> str:
        """Convert back to source code."""
        seed_str = self.seed.unparse() if self.seed else ""
        ops_str = " ".join(op.unparse() for op in self.operations)

        if seed_str:
            return f"[{seed_str} {ops_str}]"
        else:
            return f"[{ops_str}]"

    def __repr__(self):
        seed_info = "seeded" if self.seed else "unseeded"
        return f"Pipeline({seed_info}, {len(self.operations)} ops)"


class PipelineOp(ValueNode):
    """Base class for pipeline operations.

    Pipeline operations transform the value flowing through a pipeline.
    They receive the current value via $in scope and return the next value.

    This is a base class - specific operations inherit from it:
    - PipeFunc: Call a function
    - PipeStruct: Merge a structure
    - PipeBlock: Execute a block
    - PipeFallback: Fallback operation
    """
    pass


class PipeFunc(PipelineOp):
    """Pipeline function call: |funcname or |funcname ^{args}

    Calls a function with:
    - input: Current pipeline value ($in)
    - args: Optional argument structure

    The function receives the pipeline value and returns the next value.

    Correct by Construction:
    - func_name is a string
    - args is ValueNode or None
    """

    def __init__(self, func_name: str, args: ValueNode | None = None):
        """Create pipeline function call.

        Args:
            func_name: Function name (without | prefix)
            args: Optional argument expression (evaluates to struct)

        Raises:
            TypeError: If func_name not string or args not ValueNode/None
        """
        if not isinstance(func_name, str):
            raise TypeError("PipeFunc func_name must be string")
        if args is not None and not isinstance(args, ValueNode):
            raise TypeError("PipeFunc args must be ValueNode or None")

        self.func_name = func_name
        self.args = args

    def evaluate(self, engine):
        """Evaluate function call with pipeline input.

        1. Get $in scope (current pipeline value)
        2. Evaluate args if present
        3. Call function with input and args
        4. Return result
        """
        # Get current pipeline value from $in scope
        input_value = engine.get_scope('in')
        if input_value is None:
            return engine.fail(f"PipeFunc |{self.func_name} requires $in scope")

        # Evaluate args if present
        args_value = None
        if self.args is not None:
            args_value = yield self.args
            if engine.is_fail(args_value):
                return args_value

        # Call the function
        result = engine.call_function(self.func_name, input_value, args_value)
        return result

    def unparse(self) -> str:
        """Convert back to source code."""
        if self.args:
            return f"|{self.func_name} {self.args.unparse()}"
        return f"|{self.func_name}"

    def __repr__(self):
        if self.args:
            return f"PipeFunc({self.func_name}, with args)"
        return f"PipeFunc({self.func_name})"


class PipeStruct(PipelineOp):
    """Pipeline structure merge operation: |{field=value ...}

    Merges a structure into the pipeline value:
    - $in must be a struct
    - Evaluates structure expression
    - Merges new fields into $in (new fields override)
    - Returns merged struct

    This enables building up structures incrementally:
    - [{x=1} |{y=2}] → {x=1 y=2}
    - [{a=1 b=2} |{b=3}] → {a=1 b=3}

    Correct by Construction:
    - struct is a ValueNode (typically Structure)
    """

    def __init__(self, struct: ValueNode):
        """Create structure merge operation.

        Args:
            struct: Structure expression to merge (typically a Structure node)

        Raises:
            TypeError: If struct is not a ValueNode
        """
        if not isinstance(struct, ValueNode):
            raise TypeError("PipeStruct struct must be ValueNode")
        self.struct = struct

    def evaluate(self, engine):
        """Merge structure into pipeline input.

        1. Get $in scope (current pipeline value - must be struct)
        2. Evaluate structure expression
        3. Merge structure into $in (new fields override)
        4. Return merged result
        """
        input_value = engine.get_scope('in')
        if input_value is None:
            return engine.fail("PipeStruct requires $in scope")

        # Input must be a struct (dict)
        if not isinstance(input_value.data, dict):
            return engine.fail(f"PipeStruct requires struct input, got {type(input_value.data).__name__}")

        # Evaluate the structure to merge
        merge_value = yield self.struct
        if engine.is_fail(merge_value):
            return merge_value

        # Merge result must also be a struct
        if not isinstance(merge_value.data, dict):
            return engine.fail(f"PipeStruct merge value must be struct, got {type(merge_value.data).__name__}")

        # Create merged dict (input first, then overlay merge)
        merged_dict = {**input_value.data, **merge_value.data}

        return Value(merged_dict)

    def unparse(self) -> str:
        """Convert back to source code."""
        return f"|{self.struct.unparse()}"

    def __repr__(self):
        return f"PipeStruct({self.struct!r})"


class PipeFallback(PipelineOp):
    """Pipeline fallback operation: |? recovery_expr

    Handles failures in the pipeline:
    - If $in is a fail: Evaluate and return recovery expression
    - If $in is success: Pass through unchanged

    This allows pipelines to recover from errors gracefully.

    Correct by Construction:
    - recovery is a ValueNode
    - can_handle_fail is True (signals to Pipeline)
    """

    can_handle_fail = True  # Tell Pipeline we handle fails

    def __init__(self, recovery: ValueNode):
        """Create fallback operation.

        Args:
            recovery: Expression to evaluate when handling a fail

        Raises:
            TypeError: If recovery is not a ValueNode
        """
        if not isinstance(recovery, ValueNode):
            raise TypeError("PipeFallback recovery must be ValueNode")
        self.recovery = recovery

    def evaluate(self, engine):
        """Handle fail or pass through success.

        1. Get $in scope (current pipeline value)
        2. If fail: Evaluate and return recovery expression
        3. If success: Return $in unchanged
        """
        input_value = engine.get_scope('in')
        if input_value is None:
            return engine.fail("PipeFallback |? requires $in scope")

        if engine.is_fail(input_value):
            # Input is a fail - evaluate recovery
            return (yield self.recovery)
        else:
            # Input is success - pass through
            return input_value

    def unparse(self) -> str:
        """Convert back to source code."""
        return f"|? {self.recovery.unparse()}"

    def __repr__(self):
        return f"PipeFallback({self.recovery!r})"

