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
    print(input_value.as_scalar().unparse())
    # Pass through unchanged
    return input_value


def builtin_identity(frame, input_value, args):
    """Identity function - returns input unchanged: [5 |identity] → 5"""
    return input_value


def builtin_length(frame, input_value, args):
    """Get the number of fields in a struct: [{a=1 b=2 c=3} |length] → 3"""
    if not input_value.is_struct:
        return comp.fail(f"|length expects struct, got {type(input_value.data).__name__}")
    
    # Count the fields in the struct
    return comp.Value(len(input_value.struct))


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
        compute = comp.prepare_block_call(cond_arg, input_value)
        if isinstance(compute, comp.Value):
            return compute  # Error during preparation
        
        # Execute each operation in the block
        result = yield compute
        if frame.bypass_value(result):
            return result
        result = result.as_scalar()
    else:
        result = cond_arg

    if result.is_tag:
        # Condition is already a boolean tag
        tag_ref = result.data
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
        compute = comp.prepare_block_call(branch_arg, input_value)
        if isinstance(compute, comp.Value):
            return compute  # Error during preparation
        result = yield compute
        if frame.bypass_value(result):
            return result
        return result.as_scalar()

    # Branch is a plain value - return it
    return branch_arg


def builtin_loop(frame, input_value, args):
    """Repeatedly invoke a block until it returns #break: [|loop :{...}]
    
    Takes a single block argument that is invoked repeatedly with an
    incrementing counter starting at 0.
    Returns a structure with accumulated unnamed fields from each iteration.
    
    Special tag values:
    - #break: Stops iteration, value is not added to result
    - #skip: Continues iteration, value is not added to result
    - Any other value: Added as unnamed field to result structure
    """
    if args is None or not args.is_struct:
        return comp.fail("|loop requires block argument")
    
    # Get the block arg by name or first positional
    block = args.data.get(comp.Value("op"))
    if block is None:
        unnamed = [v for k, v in args.data.items() if isinstance(k, comp.Unnamed)]
        if len(unnamed) != 1:
            return comp.fail("|loop requires exactly one block argument")
        block = unnamed[0]

    # Iterate until #break
    results = []
    counter = -1
    while True:
        counter += 1
        compute = comp.prepare_block_call(block, comp.Value(counter))
        if isinstance(compute, comp.Value):
            return compute  # Error during preparation
        
        result = yield compute
        if frame.bypass_value(result):
            return result
        result = result.as_scalar()
        if result.is_tag:
            if result.data.full_name == "break":
                break
            elif result.data.full_name == "skip":
                continue
        results.append(result)
    
    value = comp.Value(results)
    return value


def builtin_subscript(frame, input_value, args):
    """Get field value and name at given index position.
    
    Usage: [{a=1 b=2 c=3} |subscript index=1] → {value=2 field="b"}
           [{10 20 30} |subscript index=0] → {value=10 field="_"}
    
    Returns a struct with:
    - value: The field's value at that position
    - field: The field's name (string) or "_" for unnamed fields
    
    Supports negative indexing: -1 is last element, -2 is second-to-last, etc.
    """
    if not input_value.is_struct:
        return comp.fail(f"|subscript expects struct, got {type(input_value.data).__name__}")
    
    if args is None or not args.is_struct:
        return comp.fail("|subscript requires index argument")
    
    # Get the index argument
    index_key = comp.Value("index")
    if index_key not in args.struct:
        return comp.fail("|subscript requires index argument")
    
    index_value = args.struct[index_key].as_scalar()
    if not index_value.is_number:
        return comp.fail(f"|subscript index must be number, got {type(index_value.data).__name__}")
    
    index = int(index_value.data)
    
    # Convert struct to list to handle indexing
    fields = list(input_value.struct.items())
    
    # Handle negative indexing
    if index < 0:
        index = len(fields) + index
    
    # Check bounds
    if index < 0 or index >= len(fields):
        return comp.fail(f"subscript index {index} out of bounds (length {len(fields)})")
    
    # Get the field at this index
    field_key, field_value = fields[index]
    
    # Build result struct with value and field
    if isinstance(field_key, comp.Unnamed):
        field_name = comp.Value("_")
    else:
        # Field key is already a Value
        field_name = field_key
    
    return comp.Value({
        comp.Value('value'): field_value,
        comp.Value('field'): field_name,
    })


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
    # module.define_tag(["return"], value=None)

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
    
    # Block shape - defined as ~:{} (block with empty input shape)
    # This is a real shape definition with a BlockShapeDefinition
    # Used to type blocks: :{...}~any-block
    # Create the BlockShapeDefinition directly (not an AST node)
    from . import _function
    from . import _module as _module_runtime
    block_shape_def = _function.BlockShapeDefinition(fields=[])
    
    # Create a ShapeField (runtime entity) with the BlockShapeDefinition
    # This is a single positional field that is the block shape itself
    module.define_shape(["any-block"], fields=[_module_runtime.ShapeField(
        name=None,  # Positional field (no name)
        shape=block_shape_def,  # The ~:{} block shape (runtime entity)
        default=None
    )])

    # Register Python-backed functions
    funcs = {
        "double": builtin_double,
        "print": builtin_print,
        "identity": builtin_identity,
        "length": builtin_length,
        "add": builtin_add,
        "wrap": builtin_wrap,
        "if": builtin_if,
        "loop": builtin_loop,
        "subscript": builtin_subscript,
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

