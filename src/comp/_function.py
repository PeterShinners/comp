"""Function system for the engine.

Simple function infrastructure to support pipeline operations.
Starts with Python-implemented functions, will add Comp-defined functions later.
"""

__all__ = ["Function", "PythonFunction"]

import comp

from . import _value


class Function:
    """Base class for callable functions in the engine.

    Functions in Comp are invoked through pipelines and receive:
    - input: The value flowing through the pipeline ($in)
    - args: Optional argument structure (^{...})

    Functions evaluate and return Value objects.
    """

    def __init__(self, name: str):
        """Create a function.

        Args:
            name: Function name (without | prefix)
        """
        self.name = name

    def __call__(self, frame, input_value: _value.Value, args: _value.Value | None = None):
        """Invoke the function.

        Args:
            frame: The evaluation frame
            input_value: Value from pipeline ($in)
            args: Optional argument structure

        Returns:
            Value result or fail value
        """
        raise NotImplementedError(f"Function {self.name} must implement __call__")

    def __repr__(self):
        return f"Function(|{self.name})"


class PythonFunction(Function):
    """Function implemented in Python.

    Wraps a Python callable to make it available in Comp pipelines.
    The callable receives (engine, input_value, args) and returns Value.
    """

    def __init__(self, name: str, python_func):
        """Create a Python-implemented function.

        Args:
            name: Function name (without | prefix)
            python_func: Callable(frame, input_value, args) -> Value
        """
        super().__init__(name)
        self.python_func = python_func

    def evaluate(self, frame):
        """Evaluate as a function body (when used in stdlib functions).

        Extracts $in and ^arg from frame scopes and calls the Python function.
        Supports both regular functions and generators that yield Compute.
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

    def __call__(self, frame, input_value: _value.Value, args: _value.Value | None = None):
        """Invoke the Python function.

        Ensures all values are structs both on input and output, maintaining
        Comp's invariant that all Values are structs (scalars are wrapped in {_: value}).
        
        Supports both regular functions and generators (that yield Compute).
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
            return result.as_struct()
        except Exception as e:
            return comp.fail(f"Error in function |{self.name}: {e}")

    def __repr__(self):
        return f"PythonFunction(|{self.name})"


# ============================================================================
# Built-in Functions
# ============================================================================

def builtin_double(frame, input_value: _value.Value, args: _value.Value | None = None):
    """Double a number: [5 |double] → 10"""
    input_value = input_value.as_scalar()
    if not input_value.is_number:
        return comp.fail(f"|double expects number, got {input_value.data}")
    return _value.Value(input_value.data * 2)


def builtin_print(frame, input_value: _value.Value, args: _value.Value | None = None):
    """Print a value and pass it through: [5 |print] → 5 (with side effect)"""
    # Print the value using unparse() for clean output
    print(f"[PRINT] {input_value.as_scalar().unparse()}")
    # Pass through unchanged
    return input_value


def builtin_identity(frame, input_value: _value.Value, args: _value.Value | None = None):
    """Identity function - returns input unchanged: [5 |identity] → 5"""
    return input_value


def builtin_add(frame, input_value: _value.Value, args: _value.Value | None = None):
    """Add argument to input: [5 |add ^{n=3}] → 8"""
    input_value = input_value.as_scalar()
    if not input_value.is_number:
        return comp.fail(f"|add expects number input, got {input_value.data}")

    if args is None or not args.is_struct:
        return comp.fail("|add requires argument ^{n=...}")

    n_key = _value.Value("n")
    if n_key not in args.struct:
        return comp.fail("|add requires argument ^{n=...}")

    n_value = args.struct[n_key]
    if not n_value.is_number:
        return comp.fail(f"|add argument n must be number, got {n_value.data}")

    return _value.Value(input_value.data + n_value.data)


def builtin_wrap(frame, input_value: _value.Value, args: _value.Value | None = None):
    """Wrap input in a struct with given key: [5 |wrap ^{key="x"}] → {x: 5}"""
    if args is None or not args.is_struct:
        return comp.fail("|wrap requires argument ^{key=...}")

    key_key = _value.Value("key")
    if key_key not in args.struct:
        return comp.fail("|wrap requires argument ^{key=...}")

    key_value = args.struct[key_key]
    return _value.Value({key_value: input_value})


def builtin_if(frame, input_value: _value.Value, args: _value.Value | None = None):
    """Conditional evaluation: [x |if ^{:{cond} :{then} :{else}}]
    
    Takes 2 or 3 positional arguments:
    - First arg (condition): Block or boolean value
    - Second arg (then): Block or value to return if condition is true
    - Third arg (else, optional): Block or value to return if condition is false
    
    Each block receives the input value as $in.
    If condition is false and no else block provided, returns input unchanged.
    """
    if args is None or not args.is_struct:
        return comp.fail("|if requires arguments (cond then [else])")
    
    # Get positional arguments (unnamed fields)
    argvalues = [v for k, v in args.struct.items() if isinstance(k, comp.Unnamed)]
    
    if len(argvalues) < 2:
        return comp.fail("|if requires at least 2 arguments (condition and then-branch)")
    if len(argvalues) > 3:
        return comp.fail("|if accepts at most 3 arguments (condition, then, else)")
    
    cond_arg = argvalues[0]
    then_arg = argvalues[1]
    else_arg = argvalues[2] if len(argvalues) == 3 else None
    
    # Evaluate condition
    if cond_arg.is_block:
        # Condition is a block - evaluate it with input_value
        block_data = cond_arg.data  # This is Block or RawBlock
        
        # Get block AST and module
        if isinstance(block_data, comp.RawBlock):
            block_ast = block_data.block_ast
            block_module = block_data.function.module if block_data.function else frame.scope('module')
            ctx_scope = block_data.ctx_scope if block_data.ctx_scope is not None else comp.Value({})
            local_scope = block_data.local_scope if block_data.local_scope is not None else comp.Value({})
            block_function = block_data.function
        elif isinstance(block_data, comp.Block):
            block_ast = block_data.raw_block.block_ast
            block_module = block_data.raw_block.function.module if block_data.raw_block.function else frame.scope('module')
            ctx_scope = block_data.raw_block.ctx_scope if block_data.raw_block.ctx_scope is not None else comp.Value({})
            local_scope = block_data.raw_block.local_scope if block_data.raw_block.local_scope is not None else comp.Value({})
            block_function = block_data.raw_block.function
        else:
            return comp.fail(f"|if condition block has unexpected type: {type(block_data)}")
        
        # Execute block like PipeBlock does
        struct_dict = {}
        accumulator = comp.Value.__new__(comp.Value)
        accumulator.data = struct_dict
        chained = comp.ChainedScope(accumulator, input_value)
        
        # Execute each operation from the block
        for op in block_ast.ops:
            yield comp.Compute(
                op,
                struct_accumulator=accumulator,
                unnamed=chained,
                in_=input_value,
                ctx=ctx_scope,
                local=local_scope,
                module=block_module,
                arg=frame.scope('arg') if block_function is not None else None,
            )
        
        # Get the result
        cond_result = accumulator
        
        if frame.is_fail(cond_result):
            return cond_result
        
        # Check if result is a boolean tag
        cond_result = cond_result.as_scalar()
        if cond_result.is_tag:
            tag_ref = cond_result.data
            if tag_ref.full_name == "true":
                condition = True
            elif tag_ref.full_name == "false":
                condition = False
            else:
                return comp.fail(f"|if condition block must return #true or #false, got #{tag_ref.full_name}")
        else:
            return comp.fail(f"|if condition block must return boolean tag, got {cond_result}")
    
    elif cond_arg.is_tag:
        # Condition is already a boolean tag
        tag_ref = cond_arg.data
        if tag_ref.full_name == "true":
            condition = True
        elif tag_ref.full_name == "false":
            condition = False
        else:
            return comp.fail(f"|if condition must be #true or #false, got #{tag_ref.full_name}")
    else:
        return comp.fail("|if condition must be a block or boolean tag")
    
    # Execute appropriate branch
    if condition:
        branch_arg = then_arg
    elif else_arg is not None:
        branch_arg = else_arg
    else:
        # No else branch and condition is false - return input unchanged
        return input_value
    
    # Evaluate the selected branch
    if branch_arg.is_block:
        # Branch is a block - evaluate it with input_value
        block_data = branch_arg.data
        
        # Get block AST and module
        if isinstance(block_data, comp.RawBlock):
            block_ast = block_data.block_ast
            block_module = block_data.function.module if block_data.function else frame.scope('module')
            ctx_scope = block_data.ctx_scope if block_data.ctx_scope is not None else comp.Value({})
            local_scope = block_data.local_scope if block_data.local_scope is not None else comp.Value({})
            block_function = block_data.function
        elif isinstance(block_data, comp.Block):
            block_ast = block_data.raw_block.block_ast
            block_module = block_data.raw_block.function.module if block_data.raw_block.function else frame.scope('module')
            ctx_scope = block_data.raw_block.ctx_scope if block_data.raw_block.ctx_scope is not None else comp.Value({})
            local_scope = block_data.raw_block.local_scope if block_data.raw_block.local_scope is not None else comp.Value({})
            block_function = block_data.raw_block.function
        else:
            return comp.fail(f"|if branch block has unexpected type: {type(block_data)}")
        
        # Execute block like PipeBlock does
        struct_dict = {}
        accumulator = comp.Value.__new__(comp.Value)
        accumulator.data = struct_dict
        chained = comp.ChainedScope(accumulator, input_value)
        
        # Execute each operation from the block
        for op in block_ast.ops:
            yield comp.Compute(
                op,
                struct_accumulator=accumulator,
                unnamed=chained,
                in_=input_value,
                ctx=ctx_scope,
                local=local_scope,
                module=block_module,
                arg=frame.scope('arg') if block_function is not None else None,
            )
        
        # Return the accumulated result
        return accumulator
    else:
        # Branch is a plain value - return it
        return branch_arg


def builtin_while(frame, input_value: _value.Value, args: _value.Value | None = None):
    """Repeatedly invoke a block until it returns #break: [|while :{...}]
    
    Takes a single block argument that is invoked repeatedly.
    Returns a structure with accumulated unnamed fields from each iteration.
    
    Special tag values:
    - #break: Stops iteration, value is not added to result
    - #skip: Continues iteration, value is not added to result
    - Any other value: Added as unnamed field to result structure
    """
    if args is None or not args.is_struct:
        return comp.fail("|while requires argument ^{:{...}}")
    
    # Get the block (should be first positional arg)
    argvalues = [v for k, v in args.struct.items() if isinstance(k, comp.Unnamed)]
    
    if len(argvalues) != 1:
        return comp.fail("|while requires exactly one block argument")
    
    block_arg = argvalues[0]
    
    if not block_arg.is_block:
        return comp.fail("|while block must be a block")
    
    # Get block components
    block_data = block_arg.data
    
    if isinstance(block_data, comp.RawBlock):
        block_ast = block_data.block_ast
        block_module = block_data.function.module if block_data.function else frame.scope('module')
        ctx_scope = block_data.ctx_scope if block_data.ctx_scope is not None else comp.Value({})
        local_scope = block_data.local_scope if block_data.local_scope is not None else comp.Value({})
        block_function = block_data.function
    elif isinstance(block_data, comp.Block):
        block_ast = block_data.raw_block.block_ast
        block_module = block_data.raw_block.function.module if block_data.raw_block.function else frame.scope('module')
        ctx_scope = block_data.raw_block.ctx_scope if block_data.raw_block.ctx_scope is not None else comp.Value({})
        local_scope = block_data.raw_block.local_scope if block_data.raw_block.local_scope is not None else comp.Value({})
        block_function = block_data.raw_block.function
    else:
        return comp.fail(f"|while block has unexpected type: {type(block_data)}")
    
    # Get #break and #skip tags for comparison
    break_tag = frame.engine.builtin_tags.get('break')
    skip_tag = frame.engine.builtin_tags.get('skip')
    
    # Accumulate results
    result_list = []
    
    # Iterate until #break
    while True:
        # Execute block with input_value as $in
        struct_dict = {}
        accumulator = comp.Value.__new__(comp.Value)
        accumulator.data = struct_dict
        chained = comp.ChainedScope(accumulator, input_value)
        
        # Execute each operation
        last_result = input_value  # Default to input if no ops
        for op in block_ast.ops:
            last_result = yield comp.Compute(op, struct_accumulator=accumulator, unnamed=chained,
                                      in_=input_value, ctx=ctx_scope, local=local_scope,
                                      module=block_module, func_ctx=block_function)
            if frame.is_fail(last_result):
                return last_result
        
        # Get the block's result
        if struct_dict:
            # Block built a structure
            block_result = accumulator
        else:
            # Block returned a single value
            block_result = last_result
        
        # Check for #break tag
        if block_result.is_tag and block_result.data == break_tag:
            break
        
        # Check for #skip tag
        if block_result.is_tag and block_result.data == skip_tag:
            continue
        
        # Add result to accumulator
        result_list.append(block_result)
    
    # Convert list to structure with unnamed fields
    result_dict = {comp.Unnamed(): value for value in result_list}
    return comp.Value(result_dict)


# ============================================================================
# Function Registry
# ============================================================================

def create_builtin_functions():
    """Create all built-in Python functions.

    Returns:
        Dict mapping function names to Function objects
    """
    return {
        "double": PythonFunction("double", builtin_double),
        "print": PythonFunction("print", builtin_print),
        "identity": PythonFunction("identity", builtin_identity),
        "add": PythonFunction("add", builtin_add),
        "wrap": PythonFunction("wrap", builtin_wrap),
        "if": PythonFunction("if", builtin_if),
        "while": PythonFunction("while", builtin_while),
    }
