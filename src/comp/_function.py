"""Function system for the engine."""

__all__ = ["Function", "PythonFunction", "FunctionDefinition",
            "RawBlock", "Block", "BlockShapeDefinition"]

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
    """

    def __init__(self, name, python_func):
        """Create a Python-implemented function.

        Args:
            name (str): Function name (without | prefix)
            python_func (callable): Callable(frame, input_value, args) -> Value
        """
        super().__init__(name)
        self.python_func = python_func

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

    def __call__(self, frame, input_value, args=None):
        """Invoke the Python function.

        Ensures all values are structs both on input and output, maintaining
        Comp's invariant that all Values are structs (scalars are wrapped in {_: value}).
        
        Supports both regular functions and generators (that yield Compute).
        
        Args:
            frame (_Frame): Evaluation frame
            input_value (Value): Input from pipeline
            args (Value | None): Optional arguments
            
        Returns:
            Value | generator: Result value or generator for async functions
        """
        try:
            # Ensure input and args are structs
            input_value = input_value.as_struct()
            if args is not None:
                args = args.as_struct()

            # Call the Python function
            result = self.python_func(frame, input_value, args)
            
            # Check if result is a generator (function yielded Compute)
            if hasattr(result, '__next__'):
                # It's a generator - we need to drive it through the engine
                # We'll make evaluate() handle this
                # For now, just propagate the generator
                return result
            
            # Regular function - ensure result is a struct
            # BUT: Don't wrap blocks - they need to stay as Block/RawBlock objects
            if result.is_block or result.is_raw_block:
                return result
            return result.as_struct()
        except Exception as e:
            return comp.fail(f"Error in function |{self.name}: {e}")

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
        """Check if this function matches a partial path (suffix match).

        Args:
            partial (list[str]): Reversed partial path, e.g., ["area", "geometry"]
                    for |area.geometry (leaf first)

        Returns:
            bool: True if function's path ends with the partial path
        """
        if len(partial) > len(self.path):
            return False
        # Match from the end of our path (which is already in definition order)
        # partial is in reference order (reversed), so we need to reverse it
        partial_def_order = list(reversed(partial))
        return self.path[-len(partial):] == partial_def_order

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
