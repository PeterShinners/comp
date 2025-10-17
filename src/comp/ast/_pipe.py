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
        namespace: Optional namespace for the function reference
        args: Optional argument struct value
    """

    def __init__(self, func_name: str, args: _base.ValueNode | None = None, namespace: str | None = None):
        if not isinstance(func_name, str):
            raise TypeError("PipeFunc func_name must be string")
        if args is not None and not isinstance(args, _base.ValueNode):
            raise TypeError("PipeFunc args must be _base.ValueNode or None")
        if namespace is not None and not isinstance(namespace, str):
            raise TypeError("PipeFunc namespace must be string or None")

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
            if frame.is_fail(args_value):
                return args_value

        # Try to call as builtin function first
        builtin_func = frame.engine.get_function(self.func_name)
        if builtin_func is not None:
            result = builtin_func(frame, input_value, args_value)
            # Check if result is a generator (function yields Compute)
            if hasattr(result, '__next__'):
                # Drive the generator to completion
                try:
                    compute = next(result)
                    while True:
                        value = yield compute
                        compute = result.send(value)
                except StopIteration as e:
                    return e.value if e.value is not None else comp.Value(None)
            return result

        # Use pre-resolved function definitions if available (fast path)
        if self._resolved is not None:
            func_defs = self._resolved
        else:
            # Slow path: runtime lookup for modules not prepared
            module = frame.scope('module')
            if module is None:
                return comp.fail(f"Function |{self.func_name} not found (no module scope)")

            # Parse the function path (support dotted names)
            func_path = self.func_name.split('.')
            func_path_reversed = list(reversed(func_path))

            # Look up function in module (with optional namespace)
            try:
                func_defs = module.lookup_function(func_path_reversed, self.namespace)
            except ValueError as e:
                # Not found or ambiguous
                return comp.fail(str(e))

        # Step 1: Select best overload by trying to morph input to each shape
        best_func = None
        best_morph = None
        best_score = None
        
        for func_def in func_defs:
            if func_def.input_shape is None:
                # No shape constraint - this is a wildcard match
                # Score it lower than any shaped match (use negative score)
                morph_result = comp.MorphResult(named_matches=0, tag_depth=0,
                                               assignment_weight=0, positional_matches=-1,
                                               value=input_value)
            else:
                # Try to morph input to this overload's shape
                morph_result = comp.morph(input_value, func_def.input_shape)
                if not morph_result.success:
                    continue  # This overload doesn't match
            
            # Compare scores - higher is better (lexicographic tuple comparison)
            if best_score is None or morph_result > best_score:
                best_func = func_def
                best_morph = morph_result
                best_score = morph_result
        
        # Check if we found any matching overload
        if best_func is None:
            return comp.fail(f"Function |{self.func_name}: no overload matches input shape")
        
        # Use the morphed input value from the best match
        func_def = best_func
        input_value = best_morph.value

        # Step 2: Morph arguments to arg shape with strong morph (~*)
        # This enables unnamed→named field pairing, tag matching, and strict validation
        arg_scope = args_value if args_value is not None else comp.Value({})
        if func_def.arg_shape is not None:
            arg_morph_result = comp.strong_morph(arg_scope, func_def.arg_shape)
            if not arg_morph_result.success:
                return comp.fail(f"Function |{self.func_name}: arguments do not match argument shape (missing required fields or type mismatch)")
            arg_scope = arg_morph_result.value

        # Step 3: Get shared ctx and mod scopes
        ctx_shared = frame.scope('ctx')
        if ctx_shared is None:
            ctx_shared = frame.engine.ctx_scope
        
        # Get mod scope from the function's module (not from frame)
        mod_shared = func_def.module.scope

        # Step 4: Apply weak morph to ctx and mod (~?)
        # Filter to only fields in arg shape (no defaults, no validation)
        ctx_scope = ctx_shared
        mod_scope = mod_shared
        if func_def.arg_shape is not None:
            # Weak morph for $ctx
            ctx_morph_result = comp.weak_morph(ctx_shared, func_def.arg_shape)
            if ctx_morph_result.success:
                ctx_scope = ctx_morph_result.value

            # Weak morph for $mod
            mod_morph_result = comp.weak_morph(mod_shared, func_def.arg_shape)
            if mod_morph_result.success:
                mod_scope = mod_morph_result.value

        local_scope = comp.Value({})  # Empty local scope

        # Evaluate function body with these scopes
        # Note: module scope comes from func_def.module
        result = yield comp.Compute(
            func_def.body,
            in_=input_value,
            arg=arg_scope,
            ctx=ctx_scope,
            mod=mod_scope,
            local=local_scope,
            # Use the function's module for all lookups
            module=func_def.module,
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
        if frame.is_fail(block_value):
            return block_value

        # If the value is a structure with a single unnamed Block, unwrap it
        # This handles the common case where a function returns a structure containing a block
        if block_value.is_struct and len(block_value.data) == 1:
            # Get the first (and only) value from the dict
            first_value = next(iter(block_value.data.values()))
            if first_value.is_block and isinstance(first_value.data, comp.Block):
                block_value = first_value

        # Check if it's a Block (wrapped in Value)
        if not block_value.is_block or not isinstance(block_value.data, comp.Block):
            return comp.fail(f"PipeBlock |: requires Block, got {type(block_value.data).__name__}")

        block = block_value.data

        # Note: We don't morph the input here - that's the responsibility of the
        # code that stores/retrieves blocks. If a block has an input shape, it should
        # only be stored in contexts where morphing will happen (e.g., struct fields
        # with block type shapes). For now, we trust that the Block is being invoked
        # with appropriate input.

        # Execute block operations like Structure does, but with captured context
        # Create an accumulator dict for the block output
        struct_dict = {}
        accumulator = comp.Value.__new__(comp.Value)
        accumulator.data = struct_dict
        accumulator.tag = None

        # Create chained scope: $out (accumulator) chains to $in
        chained = comp.ChainedScope(accumulator, input_value)

        # Get module reference - either from block's function or from frame
        # Blocks defined in functions have function.module, module-scope blocks need frame's module
        block_module = block.raw_block.function.module if block.raw_block.function else None
        if block_module is None:
            # Module-scope block - get module from frame
            block_module = frame.scope('module')
            if block_module is None:
                return comp.fail("Block invocation requires module context")

        # Execute each operation from the block with captured context
        for op in block.raw_block.block_ast.ops:
            yield comp.Compute(
                op,
                struct_accumulator=accumulator,
                unnamed=chained,
                in_=input_value,
                ctx=block.raw_block.ctx_scope if block.raw_block.ctx_scope is not None else comp.Value({}),
                local=block.raw_block.local_scope if block.raw_block.local_scope is not None else comp.Value({}),
                module=block_module,
                # If block was defined in a function, pass arg scope
                arg=frame.scope('arg') if block.raw_block.function is not None else None,
            )

        # Return the accumulated result
        return accumulator

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

