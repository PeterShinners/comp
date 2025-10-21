"""Engine for evaluating AST nodes with scope stack architecture.

The Engine provides scope management for AST node coordination.
Scopes are used for both variable bindings and parent→child coordination.

The engine doesn't know about language semantics - it just provides primitives.
AST nodes orchestrate everything using these tools.
"""

__all__ = ["Engine", "Compute", "prepare_function_call", "prepare_block_call"]

import comp


class Engine:
    """Evaluation engine with scope stack.

    The engine is a generic processor for nodes that contain `evaluate`
    generators. The generators return `Value` objects and yield child nodes for
    further evaluation.

    The engine comes with a generic system for evaluation to define a stack of
    scopes, which allows evaluation to provide context and coordination for
    evaluating child nodes.

    The engine has a simple concept of value that should be skip or bypass
    processing. These are usually associated with failure types, but could be
    expanded to anything the user want to the engine to handle specially.
    """

    def __init__(self):
        """Initialize the engine with an empty context scope.
        
        The context scope is persistent across function calls and stored
        as an empty struct (Value(None)).
        """
        # Context scope storage - persistent across function calls
        # Value(None) creates an empty struct
        self.ctx_scope = comp.Value(None)

    def run(self, node, **scopes):
        """Run a node and return its result (frame-based evaluation).

        This is the main entry point for evaluation. It handles the generator
        protocol: yielding children, sending results back, getting final result.

        The op generator builds a list of Frame objects describing the
        execution path while processing.

        Fail values immediately stop processing UNLESS the parent frame
        has allow_failures set, in which case the fail is sent to it via send().

        Args:
            node (AstNode): AST node to evaluate
            **scopes: Keyword arguments to define initial scopes (in_ becomes in)

        Returns:
            Value: Final Value result from node evaluation
        """
        result = comp.Value({})  # Set by first StopIteration before use
        result_bypass = False  # Track if result contains a failure

        # Handle Python keyword workarounds: in_ -> in
        if 'in_' in scopes:
            scopes['in'] = scopes.pop('in_')

        # Create initial frame
        newest = _Frame(node, None, scopes, False, self)
        current = newest

        while current:
            try:
                # If current is allowed to receive failures and we have one
                if result_bypass and current.allowed:
                    # Parent consumed the failure - clear both flags
                    current.allowed = False
                    result_bypass = False

                # Failures bypass frames that don't allow them
                elif result_bypass:
                    current.gen.close()
                    current = current.previous
                    continue

                # Advance generator - yields a Compute request
                if current is newest:
                    request = next(current.gen)
                else:
                    request = current.gen.send(result)

                # Mark the parent (current) as allowed to receive failures from the child (request)
                if request.allow_failures:
                    current.allowed = True

                # Create child frame - generator created automatically in __init__
                newest = _Frame(
                    request.node,
                    current,
                    request.scopes,
                    request.allow_failures,
                    self
                )
                current = newest

            except StopIteration as e:
                # Handle returned value and step out to parent
                result = e.value
                if result is None:
                    print("NONERESULT:", current, current.node)
                result.ast = current.node  # Minimal temporary tracking of source
                result_bypass = self.bypass_value(result)
                current = current.previous

        return result

    def run_function(self, func, in_=None, args=None, ctx=None):
        """Run a defined function with proper scope setup.
        
        This is a Pythonic entry point for invoking Comp functions directly.
        This is not used by the runtime language.

        It uses the same logic as PipeFunc for selecting overloads, morphing
        arguments, and preparing scopes.
        
        Args:
            func: FuncDef or function name (if name, looks up in func.module)
            in_: Input value (will be wrapped in Value if needed, defaults to empty struct)
            args: Arguments dict or Value (optional)
            ctx: Context dict or Value (optional, uses engine.ctx_scope if None)
            
        Returns:
            Value: Result of function execution
        """
        # Wrap inputs in Value if needed, default to empty struct for in_
        if in_ is None:
            in_ = comp.Value({})
        elif not isinstance(in_, comp.Value):
            in_ = comp.Value(in_)
        if args is not None and not isinstance(args, comp.Value):
            args = comp.Value(args)
        if ctx is not None and not isinstance(ctx, comp.Value):
            ctx = comp.Value(ctx)
        
        # Get ctx scope (use provided or engine's default)
        ctx_scope = ctx if ctx is not None else self.ctx_scope
        
        # Prepare the function call (handles overload selection, morphing, scope setup)
        result = comp.prepare_function_call(
            func_defs=[func], input_value=in_, args_value=args, ctx_scope=ctx_scope)
        
        # Check if preparation returned a failure Value
        if isinstance(result, comp.Value):
            return result
        
        # result is a Compute object - execute it using the engine
        return self.run(result.node, **result.scopes)

    def bypass_value(self, value):
        """Check if a value is a type that should be bypassed.

        Usually this means any fail value, but in the future this could be
        expanded so the engine can bypass and handle custom types.
        
        Args:
            value (Value): Value to check for failure
            
        Returns:
            bool: True if value contains a #fail tag
        """
        return isinstance(value, comp.Value) and value.is_fail


class Compute:
    """Request to evaluate a child AST node.

    This is yielded from `AstNode.evaluate` when further processing is requested.
    The engine receives this request and creates an internal _Frame to track execution.

    Args:
        node (AstNode): AST node to evaluate (required)
        allow_failures (bool): Whether this evaluation can receive fail values (default: False)
        **scopes: Scope bindings for this evaluation (keyword arguments)
    """

    __slots__ = ('node', 'allow_failures', 'scopes')

    def __init__(self, node, allow_failures=False, **scopes):
        self.node = node
        self.scopes = {k.rstrip('_'): v for k, v in scopes.items()}
        self.allow_failures = allow_failures

    def __repr__(self):
        """Return string representation of Compute request.
        
        Returns:
            str: Formatted string showing node, scopes, and allow_failures
        """
        parts = [f"node={self.node!r}"]
        if self.scopes:
            parts.append(f"scopes={list(self.scopes.keys())}")
        if self.allow_failures:
            parts.append("allow_failures=True")
        return f"Compute({', '.join(parts)})"


class _Frame:
    """Evaluation frame - represents one step in the call stack.

    This is a self-contained execution context that forms a linked list.
    Each frame knows its parent, eliminating the need for a separate stack.

    The frame provides all services needed by AST node generators:
    - Scope lookup (flattened dict with parent fallback)
    - Failure checking
    - Function calls

    The generator is created automatically during initialization.

    Args:
        node (AstNode): AST node being evaluated
        previous (_Frame | None): Parent frame (None for root)
        scopes (dict): Scope bindings for this frame (merged with parent)
        allow_failures (bool): Whether this frame can receive failures
        engine (Engine): Engine reference for function registry and fail_tag
    """
    __slots__ = ('node', 'gen', 'previous', 'scopes', 'allowed', 'engine')

    def __init__(self, node, previous, scopes, allow_failures, engine):
        self.node = node
        self.previous = previous
        self.allowed = allow_failures  # Can frame receive failure values? (modified as engine loops)
        self.engine = engine  # Temporary for function registry

        if not previous:
            self.scopes = scopes
        elif not scopes:
            self.scopes = previous.scopes  # No copy needed
        else:
            self.scopes = {**previous.scopes, **scopes}  # Flatten scope over previous

        # Create the generator now that the frame is fully initialized
        self.gen = node.evaluate(self)

    def scope(self, key):
        """Look up a scope value.
        
        Args:
            key (str): Scope name to look up
            
        Returns:
            Value | None: Scope value or None if not found
        """
        return self.scopes.get(key)

    def bypass_value(self, value):
        """Check if a value is a fail value.
        
        Args:
            value (Value): Value to check
            
        Returns:
            bool: True if value is a fail value
        """
        return self.engine.bypass_value(value)

    def __repr__(self):
        """Return string representation showing frame depth.
        
        Returns:
            str: Formatted string with depth and node
        """
        depth = 0
        frame = self
        while frame.previous:
            depth += 1
            frame = frame.previous
        return f"_Frame(depth={depth}, node={self.node!r})"



def prepare_function_call(func_defs, input_value, args_value, ctx_scope):
    """Prepare a function call by selecting overload and building Compute.
    
    This function encapsulates the logic for:
    1. Selecting the best matching overload via input morphing
    2. Morphing arguments to the function's arg shape
    3. Preparing ctx and mod scopes with weak morphing
    4. Building a Compute object ready to execute
    
    Args:
        func_defs: List of FunctionDef objects (overloads)
        input_value: Input value to morph to function's input shape
        args_value: Arguments to pass (Value or None)
        ctx_scope: Context scope for the function call
        
    Returns:
        Compute: Ready-to-execute compute object, or fail Value if error
    """
    # Get function name for error messages (from first definition)
    func_name = '.'.join(reversed(func_defs[0].path)) if func_defs else "unknown"

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
        return comp.fail(f"Function |{func_name}: no overload matches input shape")
    
    # Use the morphed input value from the best match
    func_def = best_func
    input_value = best_morph.value

    # Step 2: Morph arguments to arg shape with strong morph (~*)
    # This enables unnamed→named field pairing, tag matching, and strict validation
    arg_scope = args_value if args_value is not None else comp.Value({})
    if func_def.arg_shape is not None:
        arg_morph_result = comp.strong_morph(arg_scope, func_def.arg_shape)
        if not arg_morph_result.success:
            return comp.fail(f"Function |{func_name}: arguments do not match argument shape (missing required fields or type mismatch)")
        arg_scope = arg_morph_result.value

    # Step 3: Get mod scope from the function's module
    mod_shared = func_def.module.scope

    # Step 4: Apply weak morph to ctx and mod (~?)
    # Filter to only fields in arg shape (no defaults, no validation)
    ctx_scope_morphed = ctx_scope
    mod_scope = mod_shared
    if func_def.arg_shape is not None:
        # Weak morph for $ctx
        ctx_morph_result = comp.weak_morph(ctx_scope, func_def.arg_shape)
        if ctx_morph_result.success:
            ctx_scope_morphed = ctx_morph_result.value

        # Weak morph for $mod
        mod_morph_result = comp.weak_morph(mod_shared, func_def.arg_shape)
        if mod_morph_result.success:
            mod_scope = mod_morph_result.value

    var_scope = comp.Value({})  # Empty local scope

    # Build and return Compute object
    return comp.Compute(
        func_def.body,
        in_=input_value,
        arg=arg_scope,
        ctx=ctx_scope_morphed,
        mod=mod_scope,
        var=var_scope,
        module=func_def.module,
    )


def prepare_block_call(block, input):
    """Prepare a block invocation by extracting context and building Compute list.
    
    Blocks capture their definition context (frame) and can be invoked with
    different input values. This function handles:
    1. Extracting the block AST and captured frame
    2. Getting scopes from the captured frame (ctx, var, arg, module)
    3. Creating an accumulator for the block's struct building
    4. Building a list of Compute objects for each operation in the block
    
    Args:
        block (Value): Block or RawBlock value to invoke
        input (Value): Input value to pass as $in
        
    Returns:
        tuple: (compute_list, accumulator) where:
            - compute_list: List of Compute objects to execute sequentially
            - accumulator: The struct accumulator to collect results
            Or returns a fail Value if error
    """
    block = block.as_scalar()
    input = input.as_struct()
    if not block.is_block:
        return comp.fail("Expected block value")

    # Likely a raw block for now, as builtin funcs do not morph
    # arguments like a comp function should
    if isinstance(block.data, comp.RawBlock):
        block = comp.Value(comp.Block(block.data, comp.ast.BlockShape([])))

    # # RawBlocks must be morphed with a shape before they can be invoked
    # if isinstance(block, comp.RawBlock):
    #     return comp.fail(
    #         "PipeBlock |: cannot invoke Raw block directly. "
    #         "Raw block must be morphed with a block shape (e.g., ~:{}) before invocation."
    #     )

    block_ast = block.data.raw_block.block_ast
    block_frame = block.data.raw_block.frame
    block_module = block_frame.scope('module')
    ctx_scope = block_frame.scope('ctx') or comp.Value({})
    var_scope = block_frame.scope('var') or comp.Value({})
    arg_scope = block_frame.scope('arg')
    
    compute = comp.Compute(
        block_ast.body,
        in_=input,
        ctx=ctx_scope,
        var=var_scope,
        module=block_module,
        arg=arg_scope,
    )
    return compute

