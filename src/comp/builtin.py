"""Builtin module providing core tags, shapes, and functions."""

import comp

# Builtin tag constants (somewhat placeholder until the real module arrives)
TRUE = comp.TagRef(None)
FALSE = comp.TagRef(None)
FAIL = comp.TagRef(None)
FAIL_TYPE = comp.TagRef(None)
FAIL_DIV_ZERO = comp.TagRef(None)
# TagDefinition(path=path, module=self, value=value)


# Basic builtin functions (some placeholder temporaries)

def builtin_double(frame, input_value, args):
    """Double a number: [5 |double] → 10"""
    input_value = input_value.as_scalar()
    if not input_value.is_number:
        return comp.fail(f"|double expects number, got {input_value.data}")
    return comp.Value(input_value.data * 2)


def builtin_print(frame, input_value, args):
    """Print a value and pass it through: [5 |print] → 5 (with side effect)"""
    # Print the value using unparse() for clean output
    print(f"[PRINT] {input_value.as_scalar().unparse()}")
    # Pass through unchanged
    return input_value


def builtin_identity(frame, input_value, args):
    """Identity function - returns input unchanged: [5 |identity] → 5"""
    return input_value


def builtin_add(frame, input_value, args):
    """Add argument to input: [5 |add ^{n=3}] → 8"""
    input_value = input_value.as_scalar()
    if not input_value.is_number:
        return comp.fail(f"|add expects number input, got {input_value.data}")

    if args is None or not args.is_struct:
        return comp.fail("|add requires argument ^{n=...}")

    n_key = comp.Value("n")
    if n_key not in args.struct:
        return comp.fail("|add requires argument ^{n=...}")

    n_value = args.struct[n_key]
    if not n_value.is_number:
        return comp.fail(f"|add argument n must be number, got {n_value.data}")

    return comp.Value(input_value.data + n_value.data)


def builtin_wrap(frame, input_value, args):
    """Wrap input in a struct with given key: [5 |wrap ^{key="x"}] → {x: 5}"""
    if args is None or not args.is_struct:
        return comp.fail("|wrap requires argument ^{key=...}")

    key_key = comp.Value("key")
    if key_key not in args.struct:
        return comp.fail("|wrap requires argument ^{key=...}")

    key_value = args.struct[key_key]
    return comp.Value({key_value: input_value})


def builtin_if(frame, input_value, args):
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
            var_scope = block_data.var_scope if block_data.var_scope is not None else comp.Value({})
            block_function = block_data.function
        elif isinstance(block_data, comp.Block):
            block_ast = block_data.raw_block.block_ast
            block_module = block_data.raw_block.function.module if block_data.raw_block.function else frame.scope('module')
            ctx_scope = block_data.raw_block.ctx_scope if block_data.raw_block.ctx_scope is not None else comp.Value({})
            var_scope = block_data.raw_block.var_scope if block_data.raw_block.var_scope is not None else comp.Value({})
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
                var=var_scope,
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
            var_scope = block_data.var_scope if block_data.var_scope is not None else comp.Value({})
            block_function = block_data.function
        elif isinstance(block_data, comp.Block):
            block_ast = block_data.raw_block.block_ast
            block_module = block_data.raw_block.function.module if block_data.raw_block.function else frame.scope('module')
            ctx_scope = block_data.raw_block.ctx_scope if block_data.raw_block.ctx_scope is not None else comp.Value({})
            var_scope = block_data.raw_block.var_scope if block_data.raw_block.var_scope is not None else comp.Value({})
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
                var=var_scope,
                module=block_module,
                arg=frame.scope('arg') if block_function is not None else None,
            )
        
        # Return the accumulated result
        return accumulator
    else:
        # Branch is a plain value - return it
        return branch_arg


def builtin_while(frame, input_value, args):
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
        var_scope = block_data.var_scope if block_data.var_scope is not None else comp.Value({})
        block_function = block_data.function
    elif isinstance(block_data, comp.Block):
        block_ast = block_data.raw_block.block_ast
        block_module = block_data.raw_block.function.module if block_data.raw_block.function else frame.scope('module')
        ctx_scope = block_data.raw_block.ctx_scope if block_data.raw_block.ctx_scope is not None else comp.Value({})
        var_scope = block_data.raw_block.var_scope if block_data.raw_block.var_scope is not None else comp.Value({})
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
                                      in_=input_value, ctx=ctx_scope, var=var_scope,
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


def get_builtin_module():
    """Get the shared builtin module instance.

    Lazily creates the builtin module on first call, then returns
    the same instance for all subsequent calls.
    
    Returns:
        Module: The shared builtin module instance
    """
    global _builtin_module
    if _builtin_module is not None:
        return _builtin_module


    # Import Module here to avoid circular import at module load time
    from . import _module as _module_runtime
    module = _module_runtime.Module(is_builtin=True)

    # Boolean tags
    true_def = module.define_tag(["true"], value=None)
    false_def = module.define_tag(["false"], value=None)

    # Control flow tags
    module.define_tag(["break"], value=None)
    module.define_tag(["skip"], value=None)

    # Failure tags
    fail_def = module.define_tag(["fail"], value=None)
    module.define_tag(["fail", "runtime"], value=None)
    fail_type_def = module.define_tag(["fail", "type"], value=None)
    fail_zero_def = module.define_tag(["fail", "div_zero"], value=None)
    module.define_tag(["fail", "not_found"], value=None)
    module.define_tag(["fail", "ambiguous"], value=None)

    TRUE.tag_def = true_def
    FALSE.tag_def = false_def
    FAIL.tag_def = fail_def
    FAIL_TYPE.tag_def = fail_type_def
    FAIL_DIV_ZERO.tag_def = fail_zero_def

    # Register Shapes
    # Note: These are placeholder definitions. The actual type checking
    # will be done in the morph system based on runtime values.
    # We define them here so they can be referenced in user code.
    module.define_shape(["num"], fields=[])
    module.define_shape(["str"], fields=[])
    module.define_shape(["bool"], fields=[])
    module.define_shape(["any"], fields=[])
    module.define_shape(["struct"], fields=[])
    module.define_shape(["nil"], fields=[])

    # Register Python-backed functions
    funcs = {
        "double": builtin_double,
        "print": builtin_print,
        "identity": builtin_identity,
        "add": builtin_add,
        "wrap": builtin_wrap,
        "if": builtin_if,
        "while": builtin_while,
    }
    for name, func in funcs.items():
        # Create a FunctionDefinition with the Python function as body
        module.define_function(
            path=[name],
            body=comp.PythonFunction(name, func),
            is_pure=False,  # I/O functions aren't pure
            doc=getattr(func, "__doc__", None),
        )

    _builtin_module = module
    return _builtin_module


# Singleton instance (Module | None)
_builtin_module = None

