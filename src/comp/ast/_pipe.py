"""Pipeline AST nodes."""

__all__ = ["Pipeline", "PipelineOp", "PipeFunc", "PipeStruct", "PipeFallback"]

import comp
from . import _base
from . import _struct


class PipelineOp(_base.ValueNode):
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


class Pipeline(_base.ValueNode):
    """Pipeline expression: [seed |op1 |op2 ...]

    Evaluates seed (or uses $in if no seed) then evaluates each operation
    with the value from the preceding statement. Handles failure flow control
    manually, through the fallback operations as needed.

    Args:
        seed: Initial value (None for unseeded pipeline)
        operations: List of PipelineOp nodes
    """

    def __init__(self, seed: _base.ValueNode | None, operations: list[PipelineOp]):
        if seed is not None and not isinstance(seed, _base.ValueNode):
            raise TypeError("Pipeline seed must be _base.ValueNode or None")
        if not isinstance(operations, list):
            raise TypeError("Pipeline operations must be a list")

        self.seed = seed
        self.operations = operations

    def evaluate(self, frame):
        # Get initial value
        if self.seed is not None:
            current = yield comp.Compute(self.seed)
            # Function call morph auto promote seed to a struct
            # But in case there are no calls in this pipeline do it here
            current = current.as_struct()
        else:
            current = frame.scope('in')
            if current is None:
                return comp.fail("Unseeded pipeline requires $in scope")

        current_is_fail = frame.is_fail(current)

        # Thread through each operation
        for op in self.operations:
            if isinstance(op, PipeFallback):
                if not current_is_fail:
                    continue  # Valid values skip fallback
            elif current_is_fail:
                continue  # Failures skip everything else

            current = yield comp.Compute(op, allow_failures=True, in_=current)
            current_is_fail = frame.is_fail(current)

        return current

    def unparse(self) -> str:
        statements = []
        if self.seed is not None:
            statements.append(self.seed.unparse())
        statements.extend(op.unparse() for op in self.operations)
        return f"[{' '.join(statements)}]"

    def __repr__(self):
        seed_info = "seeded" if self.seed else "unseeded"
        return f"Pipeline({seed_info}, {len(self.operations)} ops)"


class PipeFunc(PipelineOp):
    """Pipeline function call: |funcname or |funcname ^{args}

    Args:
        func_name: Function name (without | prefix)
        args: Optional argument struct value
    """

    def __init__(self, func_name: str, args: _base.ValueNode | None = None):
        if not isinstance(func_name, str):
            raise TypeError("PipeFunc func_name must be string")
        if args is not None and not isinstance(args, _base.ValueNode):
            raise TypeError("PipeFunc args must be _base.ValueNode or None")

        self.func_name = func_name
        self.args = args

    def evaluate(self, frame):
        # Get current pipeline value from $in scope
        input_value = frame.scope('in')
        if input_value is None:
            return comp.fail(f"PipeFunc |{self.func_name} requires $in scope")

        # Evaluate args if present
        args_value = None
        if self.args is not None:
            args_value = yield comp.Compute(self.args)
            if frame.is_fail(args_value):
                return args_value

        # Try to call as builtin function first
        builtin_func = frame.engine.get_function(self.func_name)
        if builtin_func is not None:
            result = builtin_func(frame, input_value, args_value)
            return result

        # Not a builtin - look up Comp-defined function
        mod_funcs = frame.scope('mod_funcs')
        if mod_funcs is None:
            return comp.fail(f"Function |{self.func_name} not found (no mod_funcs scope)")

        # Parse the function path (support dotted names)
        func_path = self.func_name.split('.')
        func_path_reversed = list(reversed(func_path))

        # Look up function in module
        func_defs = mod_funcs.lookup_function(func_path_reversed)
        if func_defs is None or len(func_defs) == 0:
            return comp.fail(f"Function |{self.func_name} not found")

        # For now, use the first overload (TODO: implement shape matching)
        func_def = func_defs[0]

        # Prepare function scopes
        # $in = input_value (already promoted to struct by pipeline)
        # $arg = args_value (or empty struct if no args)
        # $ctx = inherited from current frame
        # $mod = module scope
        # @local = empty struct for function temporaries

        arg_scope = args_value if args_value is not None else comp.Value({})
        ctx_scope = frame.scope('ctx')
        if ctx_scope is None:
            ctx_scope = frame.engine.ctx_scope
        mod_scope = frame.scope('mod')
        if mod_scope is None:
            mod_scope = mod_funcs.scope

        local_scope = comp.Value({})  # Empty local scope

        # Evaluate function body with these scopes
        result = yield comp.Compute(
            func_def.body,
            in_=input_value,
            arg=arg_scope,
            ctx=ctx_scope,
            mod=mod_scope,
            local=local_scope,
            # Pass through module scopes for nested function calls
            mod_funcs=mod_funcs,
            mod_shapes=frame.scope('mod_shapes'),
            mod_tags=frame.scope('mod_tags'),
        )

        return result

    def unparse(self) -> str:
        if self.args:
            return f"|{self.func_name} {self.args.unparse()}"
        return f"|{self.func_name}"

    def __repr__(self):
        if self.args:
            return f"PipeFunc({self.func_name}, with args)"
        return f"PipeFunc({self.func_name})"


class PipeStruct(PipelineOp):
    """Pipeline structure literal : |{field=value ...}

    Replace the current pipeline value with the given structure.

    Args:
        struct: _structures.Structure expression to merge (typically a _structures.Structure node)

    """

    def __init__(self, struct: _struct.Structure):
        if not isinstance(struct, _struct.Structure):
            raise TypeError("PipeStruct struct must be _structures.Structure")
        self.struct = struct

    def evaluate(self, frame):
        input_value = frame.scope('in')

        # Wrap scalars into structure
        input_value = input_value.as_struct()
        if not isinstance(input_value.data, dict):
            return comp.fail(f"PipeStruct requires struct input, got {type(input_value.data).__name__}")

        # Evaluate the structure to merge
        struct = yield comp.Compute(self.struct)
        return struct

    def unparse(self) -> str:
        return f"|{self.struct.unparse()}"

    def __repr__(self):
        return f"PipeStruct({self.struct!r})"


class PipeFallback(PipelineOp):
    """Pipeline fallback operation: |? fallback_expr

    Only called when $in is a failure. Return new structure to take
    its place. Results should be structure, or will be promoted into
    a structure.

    Args:
        fallback: Expression to evaluate when handling a fail
    """

    def __init__(self, fallback: _base.ValueNode):
        if not isinstance(fallback, _base.ValueNode):
            raise TypeError("PipeFallback fallback must be _base.ValueNode")
        self.fallback = fallback

    def evaluate(self, frame):
        value = (yield comp.Compute(self.fallback))
        value = value.as_struct()
        return value

    def unparse(self) -> str:
        return f"|? {self.fallback.unparse()}"

    def __repr__(self):
        return f"PipeFallback({self.fallback!r})"

