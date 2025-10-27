"""Pipeline AST nodes."""

__all__ = ["Pipeline", "PipelineOp", "PipeFunc", "PipeStruct", "PipeBlock", "PipeFallback"]

import comp

from . import _base, _struct


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

        current_bypass_value = frame.bypass_value(current)

        # Thread through each operation
        for op in self.operations:
            if isinstance(op, PipeFallback):
                if not current_bypass_value:
                    continue  # Valid values skip fallback
            elif current_bypass_value:
                continue  # Failures skip everything else

            current = yield comp.Compute(op, allow_failures=True, in_=current)
            current_bypass_value = frame.bypass_value(current)

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
        namespace: Optional namespace for the function reference
                  Can be a string (static namespace) or ValueNode (dynamic dispatch via $var.ref)
        args: Optional argument struct value
    """

    def __init__(self, func_name: str, args: _base.ValueNode | None = None, namespace: str | _base.ValueNode | None = None):
        if not isinstance(func_name, str):
            raise TypeError("PipeFunc func_name must be string")
        if args is not None and not isinstance(args, _base.ValueNode):
            raise TypeError("PipeFunc args must be _base.ValueNode or None")
        if namespace is not None and not isinstance(namespace, (str, _base.ValueNode)):
            raise TypeError("PipeFunc namespace must be string, ValueNode, or None")

        self.func_name = func_name
        self.namespace = namespace
        self.args = args
        self._resolved = None  # Pre-resolved function definitions (set by Module.prepare())

    def evaluate(self, frame):
        # Get current pipeline value from $in scope
        input_value = frame.scope('in')
        if input_value is None:
            return comp.fail(f"PipeFunc |{self.func_name} requires $in scope")

        # Evaluate args if present
        args_value = None
        if self.args is not None:
            args_value = yield comp.Compute(self.args)
            if frame.bypass_value(args_value):
                return args_value

        # Resolve namespace if it's a ValueNode (dynamic dispatch)
        resolved_namespace = None
        if self.namespace is not None:
            if isinstance(self.namespace, str):
                # Static namespace reference
                resolved_namespace = self.namespace
            else:
                # Dynamic namespace dispatch - evaluate the node to get a tag or handle
                namespace_value = yield comp.Compute(self.namespace)
                if frame.bypass_value(namespace_value):
                    return namespace_value
                
                # Extract the defining module from the tag or handle
                namespace_value = namespace_value.as_scalar()
                if namespace_value.is_tag:
                    # Get the tag's defining module
                    tag_ref = namespace_value.data
                    defining_module = tag_ref.tag_def.module
                    resolved_namespace = defining_module
                elif namespace_value.is_handle:
                    # Get the handle's defining module
                    handle_inst = namespace_value.data
                    defining_module = handle_inst.handle_def.module
                    resolved_namespace = defining_module
                else:
                    return comp.fail(f"Namespace dispatch requires tag or handle, got {type(namespace_value.data).__name__}")

        # Get function definitions (pre-resolved or lookup at runtime)
        if self._resolved is not None:
            func_defs = self._resolved
        else:
            # Runtime lookup for modules not prepared
            module = frame.scope('module')
            if module is None:
                return comp.fail(f"Function |{self.func_name} not found (no module scope)")

            # Parse the function path (support dotted names)
            func_path = self.func_name.split('.')

            # Look up function in module (with optional namespace)
            # If resolved_namespace is a Module, need to look up directly in that module
            if isinstance(resolved_namespace, comp.Module):
                # Direct dispatch to a specific module
                try:
                    func_defs = resolved_namespace.lookup_function(func_path, namespace=None, local_only=False)
                except ValueError as e:
                    # Not found or ambiguous
                    return comp.fail(str(e))
            else:
                # String namespace or None - use normal lookup
                try:
                    func_defs = module.lookup_function(func_path, resolved_namespace)
                except ValueError as e:
                    # Not found or ambiguous
                    return comp.fail(str(e))

        # Check if this is a PythonFunction (needs special handling)
        # PythonFunctions return generators that must be driven to completion
        if len(func_defs) == 1 and isinstance(func_defs[0].body, comp.PythonFunction):
            python_func = func_defs[0].body
            gen = python_func.invoke(input_value, args_value, frame)

            # All PythonFunctions are generators - drive to completion
            try:
                compute = next(gen)  # type: ignore
                while True:
                    value = yield compute
                    compute = gen.send(value)  # type: ignore
            except StopIteration as e:
                return e.value if e.value is not None else comp.Value(None)

        # Regular Comp function - use prepare_function_call
        # Get ctx scope for function call
        ctx_scope = frame.scope('ctx')
        if ctx_scope is None:
            ctx_scope = frame.engine.ctx_scope

        # Use prepare_function_call to build the Compute object
        compute = comp.prepare_function_call(
            func_defs, input_value, args_value, ctx_scope)
        if isinstance(compute, comp.Value) and compute.is_fail:
            return compute  # Preparation failed

        # Execute the prepared function call
        result = yield compute
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


class PipeBlock(PipelineOp):
    """Pipeline block invocation: |:block_ref

    Invokes a Block (typed block created through morphing) with the current
    pipeline value as $in. The block executes with its captured context
    (module, function, $ctx, @local from definition time) plus the new $in.

    Args:
        block_ref: Identifier reference to the Block value
    """

    def __init__(self, block_ref: _base.ValueNode):
        if not isinstance(block_ref, _base.ValueNode):
            raise TypeError("PipeBlock block_ref must be _base.ValueNode")
        self.block_ref = block_ref

    def evaluate(self, frame):
        # Get current pipeline value from $in scope
        input_value = frame.scope('in')
        if input_value is None:
            return comp.fail("PipeBlock |: requires $in scope")

        # Evaluate the block reference to get the Block value
        block_value = yield comp.Compute(self.block_ref)
        if frame.bypass_value(block_value):
            return block_value

        # Check if it's a Block (not RawBlock) wrapped in Value
        block_value = block_value.as_scalar()
        if not block_value.is_block:
            return comp.fail(f"PipeBlock |: requires Block, got {type(block_value.data).__name__}")

        # Note: We don't morph the input here - that's the responsibility of the
        # code that stores/retrieves blocks. If a block has an input shape, it should
        # only be stored in contexts where morphing will happen (e.g., struct fields
        # with block type shapes). For now, we trust that the Block is being invoked
        # with appropriate input.

        compute = comp.prepare_block_call(block_value, input_value)
        if isinstance(compute, comp.Value):
            return compute  # Error during preparation
        result = yield compute
        return result

    def unparse(self) -> str:
        return f"|:{self.block_ref.unparse()}"

    def __repr__(self):
        return f"PipeBlock({self.block_ref!r})"


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

