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
        frame_depth = 0  # Track recursion depth to prevent infinite loops

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
                    frame_depth -= 1  # Decrement when bypassing frames
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

                # Check frame depth to prevent infinite loops (circular references)
                frame_depth += 1
                if frame_depth > 50:
                    raise RuntimeError(
                        f"Frame depth exceeded 50 - possible infinite loop or circular reference. "
                        f"Current node: {request.node.__class__.__name__}"
                    )

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
                # Set ast node for source tracking (only for Value objects)
                # Don't overwrite if already set to something more specific than a Pipeline/Block
                if isinstance(result, comp.Value):
                    if result.ast is None:
                        result.ast = current.node
                    elif result.is_fail:
                        # For failures, prefer more specific nodes (PipeFunc) over containers (Pipeline)
                        # Only overwrite if current node is more specific
                        existing_ast = result.ast
                        # Pipeline and Block are "container" nodes - prefer child nodes over these
                        if isinstance(existing_ast, (comp.ast.Pipeline, comp.ast.Block)):
                            result.ast = current.node
                result_bypass = self.bypass_value(result)
                frame_depth -= 1  # Decrement when stepping back to parent
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
    - Handle tracking (for automatic cleanup)

    The generator is created automatically during initialization.

    Args:
        node (AstNode): AST node being evaluated
        previous (_Frame | None): Parent frame (None for root)
        scopes (dict): Scope bindings for this frame (merged with parent)
        allow_failures (bool): Whether this frame can receive failures
        engine (Engine): Engine reference for function registry and fail_tag
    """
    __slots__ = ('node', 'gen', 'previous', 'scopes', 'allowed', 'engine', 'handles')

    def __init__(self, node, previous, scopes, allow_failures, engine):
        self.node = node
        self.previous = previous
        self.allowed = allow_failures  # Can frame receive failure values? (modified as engine loops)
        self.engine = engine  # Temporary for function registry
        self.handles = set()  # HandleInstances reachable from this frame

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
    
    def register_handles(self, value):
        """Register all handles in a value with this frame (bidirectional).
        
        Establishes bidirectional tracking between handles and frame:
        - frame.handles tracks all HandleInstances reachable from frame
        - handle.frames tracks all frames that can reach the handle
        
        This enables automatic cleanup: when frame exits and unregisters,
        if handle.frames becomes empty, the handle can be automatically dropped.
        
        Args:
            value: comp.Value to register (registers all contained handles)
        """
        if not isinstance(value, comp.Value):
            return
        
        # Leverage Value.handles (computed at creation, O(1) iteration)
        for handle in value.handles:
            # Bidirectional registration
            self.handles.add(handle)
            handle.frames.add(self)

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

    This function delegates to:
    1. select_overload() - Select best matching overload via input morphing
    2. FunctionDefinition.invoke() - Prepare the function call

    Args:
        func_defs: List of FunctionDef objects (overloads)
        input_value: Input value to morph to function's input shape
        args_value: Arguments to pass (Value or None)
        ctx_scope: Context scope for the function call

    Returns:
        Compute: Ready-to-execute compute object, or fail Value if error
    """
    # Step 1: Select best overload
    result = comp.select_overload(func_defs, input_value)
    if isinstance(result, comp.Value):  # It's a fail Value
        return result

    best_func, morphed_input = result

    # Step 2: Delegate to the function definition's invoke method
    return best_func.invoke(morphed_input, args_value, ctx_scope)


def prepare_block_call(block, input):
    """Prepare a block invocation by delegating to Block.invoke().

    RawBlocks must be morphed to Blocks before invocation (via arg_shape morphing).
    This function no longer provides a fallback conversion.

    Args:
        block (Value): Block value to invoke (must be typed Block, not RawBlock)
        input (Value): Input value to pass as $in

    Returns:
        Compute: Ready-to-execute compute object, or fail Value if error
    """
    block = block.as_scalar()
    input = input.as_struct()

    # Check for RawBlock and fail - these must be morphed first
    if block.is_raw_block:
        return comp.fail(
            "Cannot invoke RawBlock directly. "
            "RawBlock must be morphed with a block shape (e.g., ~any-block) before invocation."
        )

    if not block.is_block:
        return comp.fail("Expected Block value")

    # Delegate to the Block's invoke method
    block_obj = block.data
    if not isinstance(block_obj, comp.Block):
        return comp.fail(f"Expected Block, got {type(block_obj).__name__}")

    return block_obj.invoke(input)

