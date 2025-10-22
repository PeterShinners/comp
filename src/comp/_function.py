"""Function system for the engine."""

__all__ = ["Function", "PythonFunction", "FunctionDefinition",
            "RawBlock", "Block", "BlockShapeDefinition", "select_overload"]

import comp

from . import _entity


class Function:
    """Base class for callable functions in the engine.

    Functions in Comp are invoked through pipelines and receive:
    - input: The value flowing through the pipeline ($in)
    - args: Optional argument structure (^{...})

    Functions evaluate and return Value objects.
    """

    def __init__(self, name):
        """Create a function.

        Args:
            name (str): Function name (without | prefix)
        """
        self.name = name

    def __call__(self, frame, input_value, args=None):
        """Invoke the function.

        Args:
            frame (_Frame): The evaluation frame
            input_value (Value): Value from pipeline ($in)
            args (Value | None): Optional argument structure

        Returns:
            Value: Value result or fail value
        """
        raise NotImplementedError(f"Function {self.name} must implement __call__")

    def __repr__(self):
        """Return string representation of function.
        
        Returns:
            str: Function name with | prefix
        """
        return f"Function(|{self.name})"


class PythonFunction(Function):
    """Function implemented in Python.

    Wraps a Python callable to make it available in Comp pipelines.
    The callable receives (engine, input_value, args) and returns Value.

    PythonFunctions can optionally specify input_shape and arg_shape to:
    - Participate in overload selection
    - Automatically morph inputs and arguments before invocation
    - Properly type block arguments (converting RawBlock -> Block)
    """

    def __init__(self, name, python_func, input_shape=None, arg_shape=None):
        """Create a Python-implemented function.

        Args:
            name (str): Function name (without | prefix)
            python_func (callable): Callable(frame, input_value, args) -> Value (must be generator)
            input_shape: Optional shape for input morphing and overload selection
            arg_shape: Optional shape for argument morphing
        """
        super().__init__(name)
        self.python_func = python_func
        self.input_shape = input_shape
        self.arg_shape = arg_shape

    def evaluate(self, frame):
        """Evaluate as a function body (when used in stdlib functions).

        Extracts $in and ^arg from frame scopes and calls the Python function.
        Supports both regular functions and generators that yield Compute.
        
        Args:
            frame (_Frame): Evaluation frame with scopes
            
        Yields:
            Compute: Child evaluation requests (if function is a generator)
            
        Returns:
            Value: Result from the function
        """
        input_value = frame.scope('in')
        args = frame.scope('arg')

        # Call the Python function
        result = self(frame, input_value, args)
        
        # Check if result is a generator (function yielded Compute)
        if hasattr(result, '__next__'):
            # It's a generator - drive it to completion
            try:
                compute = next(result)
                while True:
                    # Yield the Compute to the engine
                    value = yield compute
                    # Send the result back to the generator
                    compute = result.send(value)
            except StopIteration as e:
                # Generator completed, return its value
                return e.value if e.value is not None else comp.Value(None)
        else:
            # Regular function - return result directly
            return result
        yield  # Make this a generator (though this line is never reached)

    def invoke(self, input_value, args_value=None, ctx_scope=None, frame=None):
        """Invoke this Python function with automatic morphing.

        If input_shape or arg_shape are defined, morphs the values before
        invoking the Python function. This allows PythonFunctions to:
        - Participate in overload selection
        - Automatically morph block arguments (RawBlock -> Block)
        - Validate input and argument shapes

        Args:
            input_value: Input value (may be morphed if input_shape is set)
            args_value: Arguments to pass (Value or None, may be morphed if arg_shape is set)
            ctx_scope: Context scope (unused for Python functions)
            frame: Evaluation frame (needed for generator-based builtins)

        Returns:
            generator: Always returns a generator (even for failures)
        """
        import comp

        # Morph input if input_shape is defined
        if self.input_shape is not None:
            morph_result = comp.morph(input_value, self.input_shape)
            if not morph_result.success:
                # Return a generator that yields the fail value
                shape_name = self.input_shape.full_name if hasattr(self.input_shape, 'full_name') else str(self.input_shape)
                def fail_gen():
                    return comp.fail(f"Function |{self.name} expects {shape_name}, got incompatible input")
                    yield  # Make it a generator (unreachable)
                return fail_gen()
            input_value = morph_result.value

        # Morph arguments if arg_shape is defined
        if self.arg_shape is not None and args_value is not None:
            arg_morph_result = comp.strong_morph(args_value, self.arg_shape)
            if not arg_morph_result.success:
                # Return a generator that yields the fail value
                def fail_gen():
                    return comp.fail(f"Function |{self.name}: arguments do not match argument shape")
                    yield  # Make it a generator (unreachable)
                return fail_gen()
            args_value = arg_morph_result.value
        elif args_value is None:
            args_value = comp.Value({})

        # Python functions execute immediately - no Compute object needed
        return self(frame, input_value, args_value)

    def __call__(self, frame, input_value, args=None):
        """Invoke the Python function.

        All Python functions must be generators. This ensures consistent handling
        and allows functions to yield Compute for child evaluations.

        Ensures all values are structs both on input and output, maintaining
        Comp's invariant that all Values are structs (scalars are wrapped in {_: value}).

        Args:
            frame (_Frame): Evaluation frame
            input_value (Value): Input from pipeline
            args (Value | None): Optional arguments

        Returns:
            generator: Generator that yields Compute and returns Value
        """
        try:
            # Ensure input and args are structs
            input_value = input_value.as_struct()
            if args is not None:
                args = args.as_struct()

            # Call the Python function (must be a generator)
            return self.python_func(frame, input_value, args)
        except Exception as e:
            # Return a fail value as a generator
            def fail_gen():
                return comp.fail(f"Error in function |{self.name}: {e}")
                yield  # Make it a generator (unreachable)
            return fail_gen()

    def __repr__(self):
        """Return string representation.

        Returns:
            str: Function name with | prefix and type indicator
        """
        return f"PythonFunction(|{self.name})"


class FunctionDefinition(_entity.Entity):
    """A function definition in the module.

    Functions transform input structures through pipelines and can accept arguments.
    They are lazy by default and support overloading through shape-based dispatch.

    Inherits from Entity so it can be returned from evaluate() and passed through scopes.

    Attributes:
        path (list[str]): Full path as list, e.g., ["math", "geometry", "area"]
        module (Module): The Module this function is defined in
        input_shape (ShapeDefinition | None): Shape defining expected input structure (or None for any)
        arg_shape (ShapeDefinition | None): Shape defining function arguments (or None for no args)
        body (AstNode): Structure definition AST node for the function body
        is_pure (bool): True if function has no side effects
        doc (str | None): Optional documentation string
        impl_doc (str | None): Optional documentation for this specific implementation (overloads)
    """
    def __init__(self, path, module, body, input_shape=None,
                 arg_shape=None, is_pure=False,
                 doc=None, impl_doc=None, _placeholder=False):
        """Initialize function definition.
        
        Args:
            path (list[str]): Full path as list
            module (Module): Module containing this function
            body (AstNode): Function body AST
            input_shape (ShapeDefinition | None): Expected input shape
            arg_shape (ShapeDefinition | None): Argument shape
            is_pure (bool): Whether function is pure (no side effects)
            doc (str | None): Documentation string
            impl_doc (str | None): Implementation-specific documentation
            _placeholder (bool): True if created during prepare(), not a real definition
        """
        self.path = path
        self.module = module
        self.input_shape = input_shape
        self.arg_shape = arg_shape
        self.body = body
        self.is_pure = is_pure
        self.doc = doc
        self.impl_doc = impl_doc
        self._placeholder = _placeholder  # True if created by prepare(), not real definition

    @property
    def name(self):
        """Get the function's leaf name (last element of path).
        
        Returns:
            str: Function name
        """
        return self.path[-1] if self.path else ""

    @property
    def full_name(self):
        """Get dot-separated full path.
        
        Returns:
            str: Full qualified name with dots
        """
        return ".".join(self.path)

    @property
    def parent_path(self):
        """Get the parent's path, or None for root functions.
        
        Returns:
            list[str] | None: Parent path or None
        """
        return self.path[:-1] if len(self.path) > 1 else None

    def matches_partial(self, partial):
        """Check if this function matches a partial path (prefix match).

        Args:
            partial (list[str]): Partial path in natural order, e.g., ["geometry", "area"]
                    for |geometry.area or just ["area"] for leaf-only reference

        Returns:
            bool: True if function's path ends with the partial path (prefix match on reversed path)
        """
        if len(partial) > len(self.path):
            return False
        # For prefix matching: partial matches if it equals the last N elements of our path
        return self.path[-len(partial):] == partial

    def invoke(self, input_value, args_value=None, ctx_scope=None):
        """Invoke this specific function definition.

        Handles:
        - Input morphing to this definition's input_shape
        - Argument morphing to arg_shape
        - Scope preparation (ctx, mod, var, arg)
        - Building Compute object

        Args:
            input_value: Input value (should already be morphed if from overload selection)
            args_value: Arguments to pass (Value or None)
            ctx_scope: Context scope for the function call

        Returns:
            Compute: Ready-to-execute compute object, or fail Value if error
        """
        import comp

        # Get function name for error messages
        func_name = self.full_name

        # Step 1: Morph arguments to arg shape with strong morph (~*)
        # This enables unnamed→named field pairing, tag matching, and strict validation
        arg_scope = args_value if args_value is not None else comp.Value({})
        if self.arg_shape is not None:
            arg_morph_result = comp.strong_morph(arg_scope, self.arg_shape)
            if not arg_morph_result.success:
                return comp.fail(f"Function |{func_name}: arguments do not match argument shape (missing required fields or type mismatch)")
            arg_scope = arg_morph_result.value

        # Step 2: Get mod scope from the function's module
        mod_shared = self.module.scope

        # Step 3: Apply weak morph to ctx and mod (~?)
        # Filter to only fields in arg shape (no defaults, no validation)
        ctx_scope_morphed = ctx_scope if ctx_scope is not None else comp.Value({})
        mod_scope = mod_shared
        if self.arg_shape is not None:
            # Weak morph for $ctx
            ctx_morph_result = comp.weak_morph(ctx_scope_morphed, self.arg_shape)
            if ctx_morph_result.success:
                ctx_scope_morphed = ctx_morph_result.value

            # Weak morph for $mod
            mod_morph_result = comp.weak_morph(mod_shared, self.arg_shape)
            if mod_morph_result.success:
                mod_scope = mod_morph_result.value

        var_scope = comp.Value({})  # Empty local scope

        # Build and return Compute object
        return comp.Compute(
            self.body,
            in_=input_value,
            arg=arg_scope,
            ctx=ctx_scope_morphed,
            mod=mod_scope,
            var=var_scope,
            module=self.module,
        )

    def __repr__(self):
        """Return string representation of function definition.

        Returns:
            str: Function signature with shapes
        """
        pure_str = "!pure " if self.is_pure else ""
        input_str = f" ~{self.input_shape}" if self.input_shape else ""
        arg_str = f" ^{self.arg_shape}" if self.arg_shape else ""
        return f"{pure_str}|{self.full_name}{input_str}{arg_str}"


class RawBlock:
    """An untyped block with captured definition context.

    Raw blocks are created with :{...} syntax and capture their definition context
    (the frame they were defined in) but have no input shape yet. They cannot be invoked
    until morphed with a BlockShape to create a Block.

    Blocks capture the frame they were defined in, giving them access to:
    - $var: Function-local variables (mutable, shared between invocations)
    - $arg: Function arguments
    - $ctx: Execution context
    - @local: Local scope
    - module: Module context
    - function: Function reference

    By capturing the frame, blocks can see mutations to $var between invocations,
    which is essential for stateful blocks like generators.

    Raw blocks do NOT capture:
    - $in: Set at invocation time
    - $out: Built during block execution

    Attributes:
        block_ast (Block): The Block AST node with operations
        frame (_Frame): The frame context where the block was defined
    """
    def __init__(self, block_ast, frame):
        """Initialize raw block with captured frame.
        
        Args:
            block_ast (Block): Block AST node with operations
            frame (_Frame): Frame context from block definition
        """
        self.block_ast = block_ast
        self.frame = frame

    def __repr__(self):
        """Return string representation.
        
        Returns:
            str: Summary showing operation count and frame depth
        """
        return f"RawBlock({len(self.block_ast.ops)} ops, frame={self.frame})"


class Block:
    """A typed block ready for invocation.

    Blocks are created by morphing a RawBlock with a BlockShape. They have:
    - An input shape that defines what structure they expect
    - All the captured context from the RawBlock
    - The ability to be invoked with the |: operator

    The Block holds a reference to the original RawBlock (for context and operations)
    plus the input shape that was applied through morphing.

    Attributes:
        raw_block (RawBlock): The RawBlock this was created from (contains ops and captured context)
        input_shape (ShapeDefinition): The shape defining expected input structure
    """
    def __init__(self, raw_block, input_shape):
        """Initialize typed block from raw block and shape.

        Args:
            raw_block (RawBlock): Untyped block with operations and context
            input_shape (ShapeDefinition): Expected input shape

        Raises:
            TypeError: If raw_block is not a RawBlock instance
        """
        if not isinstance(raw_block, RawBlock):
            raise TypeError("Block requires a RawBlock")
        self.raw_block = raw_block
        self.input_shape = input_shape

    def invoke(self, input_value):
        """Invoke this block with input.

        Extracts the block's captured context (frame) and builds a Compute
        object with the captured scopes plus the new input value.

        Args:
            input_value: Input value to pass as $in

        Returns:
            Compute: Ready-to-execute compute object
        """
        import comp

        # Ensure input is a struct
        input_value = input_value.as_struct()

        # Extract captured context from the raw block
        block_ast = self.raw_block.block_ast
        block_frame = self.raw_block.frame
        block_module = block_frame.scope('module')
        ctx_scope = block_frame.scope('ctx') or comp.Value({})
        var_scope = block_frame.scope('var') or comp.Value({})
        arg_scope = block_frame.scope('arg')

        # Build Compute object with captured context + new $in
        return comp.Compute(
            block_ast.body,
            in_=input_value,
            ctx=ctx_scope,
            var=var_scope,
            module=block_module,
            arg=arg_scope,
        )

    def __repr__(self):
        """Return string representation.

        Returns:
            str: Summary with operation count and shape
        """
        shape_str = f" ~:{self.input_shape}" if self.input_shape else ""
        return f"Block({len(self.raw_block.block_ast.ops)} ops{shape_str}, {self.raw_block.frame})"


class BlockShapeDefinition(_entity.Entity):
    """A block shape definition describing the input structure for blocks.

    BlockShapeDefinitions are created when BlockShape AST nodes are evaluated.
    They describe what input structure a block expects, similar to how
    ShapeDefinition describes struct layouts.

    Unlike regular shapes, BlockShapeDefinitions are specifically for block types
    and are used during morphing to convert RawBlock → Block.

    Attributes:
        fields (list[ShapeField]): List of ShapeField describing the expected input structure
    """
    def __init__(self, fields):
        """Initialize block shape definition.

        Args:
            fields (list[ShapeField]): Fields describing expected input structure

        Raises:
            TypeError: If fields is not a list
        """
        if not isinstance(fields, list):
            raise TypeError("Fields must be a list")
        # Note: We can't import ShapeField here due to circular dependency
        # The type check is relaxed to accept Any
        self.fields = fields

    def __repr__(self):
        """Return string representation.

        Returns:
            str: Summary with field count
        """
        return f"BlockShapeDefinition({len(self.fields)} fields)"


def select_overload(func_defs, input_value):
    """Select best matching overload via input morphing.

    Tries to morph the input value to each function's input shape and
    selects the overload with the best match score.

    Works with both regular FunctionDefinition (input_shape on func_def)
    and PythonFunction (input_shape on func_def.body).

    Args:
        func_defs: List of FunctionDefinition objects (overloads)
        input_value: Input value to morph to function shapes

    Returns:
        tuple: (best_func, morphed_input) where:
            - best_func: The selected FunctionDefinition
            - morphed_input: The input value morphed to the function's shape
        Or returns a fail Value if no overload matches
    """
    import comp

    # Get function name for error messages (from first definition)
    func_name = '.'.join(reversed(func_defs[0].path)) if func_defs else "unknown"

    # Try each overload and find the best match
    best_func = None
    best_morph = None
    best_score = None

    for func_def in func_defs:
        # Get input_shape - check both func_def and func_def.body (for PythonFunction)
        input_shape = func_def.input_shape
        if input_shape is None and isinstance(func_def.body, PythonFunction):
            input_shape = func_def.body.input_shape

        if input_shape is None:
            # No shape constraint - this is a wildcard match
            # Score it lower than any shaped match (use negative score)
            morph_result = comp.MorphResult(named_matches=0, tag_depth=0,
                                           assignment_weight=0, positional_matches=-1,
                                           value=input_value)
        else:
            # Try to morph input to this overload's shape
            morph_result = comp.morph(input_value, input_shape)
            if not morph_result.success:
                continue  # This overload doesn't match

        # Compare scores - higher is better (lexicographic tuple comparison)
        if best_score is None or morph_result > best_score:
            best_func = func_def
            best_morph = morph_result
            best_score = morph_result

    # Check if we found any matching overload
    if best_func is None or best_morph is None:
        return comp.fail(f"Function |{func_name}: no overload matches input shape")

    # Return the best match
    return (best_func, best_morph.value)
