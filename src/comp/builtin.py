"""Builtin module providing core tags, shapes, and functions."""

import comp

# Builtin tag constants (somewhat placeholder until the real module arrives)
TRUE = comp.TagRef(None)
FALSE = comp.TagRef(None)
FAIL = comp.TagRef(None)
FAIL_TYPE = comp.TagRef(None)
FAIL_DIV_ZERO = comp.TagRef(None)
# TagDefinition(path=path, module=self, value=value)


def format_failure(fail_value, indent=0):
    """Format a failure value for display with source location and cause chain.
    
    This function produces human-readable error messages from Comp failure values,
    including:
    - Error tag or message
    - Source file location (filename:line)
    - Source code context with caret pointer
    - Cause chain for nested errors
    
    Args:
        fail_value: The failure Value to format
        indent: Current indentation level for nested errors
        
    Returns:
        Formatted error message string
    """
    if not fail_value.is_fail:
        return str(fail_value)
    
    lines = []
    prefix = "  " * indent
    
    # Handle simple string failures (not structured)
    if not fail_value.is_struct:
        # Extract the message from the string data
        message = str(fail_value.data) if fail_value.data else "Unknown error"
        
        # Get source position from AST node
        pos = None
        if fail_value.ast is not None and hasattr(fail_value.ast, 'position'):
            pos = fail_value.ast.position
        
        # Format error line with source location
        error_line = f"{prefix}fail"
        if pos:
            if pos.filename and pos.start_line:
                error_line += f" at {pos.filename}:{pos.start_line}"
            elif pos.start_line:
                error_line += f" on line {pos.start_line}"
        
        lines.append(error_line)
        lines.append(f"{prefix}  {message}")
        
        # Add source line if available
        if pos and pos.filename and pos.start_line:
            try:
                with open(pos.filename, 'r', encoding='utf-8') as f:
                    source_lines = f.readlines()
                    line_idx = pos.start_line - 1
                    if 0 <= line_idx < len(source_lines):
                        source_line = source_lines[line_idx].rstrip()
                        lines.append(f"{prefix}  | {source_line}")
                        
                        # Add caret line pointing to the error column
                        if pos.start_column:
                            caret_line = f"{prefix}  | " + " " * (pos.start_column - 1) + "^"
                            lines.append(caret_line)
            except (OSError, IOError):
                pass
        
        return "\n".join(lines)
    
    # Handle structured failures
    
    # Extract common fields
    message = None
    tag_names = []  # Collect all unnamed tags
    cause = None
    exception_type = None
    fail_field = None  # Track the 'fail' field specifically
    
    # We know data is a dict because is_struct is True
    assert isinstance(fail_value.data, dict)
    
    for key, val in fail_value.data.items():
        if isinstance(key, comp.Value) and key.is_string:
            field_name = key.data
            if field_name == "message" and val.is_string:
                message = val.data
            elif field_name == "exception_type" and val.is_string:
                exception_type = val.data
            elif field_name == "cause" and val.is_fail:
                cause = val
            elif field_name == "fail" and val.is_tag:
                # This is the mapped tag from |map-sqlite-error
                assert isinstance(val.data, comp.TagRef)
                fail_field = val.data.full_name
        elif isinstance(key, comp.Unnamed) and val.is_tag:
            # We know val.data is a TagRef because is_tag is True
            assert isinstance(val.data, comp.TagRef)
            tag_names.append(val.data.full_name)
    
    # Prefer the 'fail' field if it exists (from mapping), otherwise use unnamed tags
    tag_name = fail_field if fail_field else (tag_names[0] if tag_names else None)
    
    # Format the main error line with source location
    error_line = f"{prefix}"
    if tag_name:
        if exception_type:
            error_line += f"[{exception_type}] {tag_name}"
        else:
            error_line += f"{tag_name}"
    else:
        error_line += "Failure"
    
    # Get source position from AST node
    pos = None
    if fail_value.ast is not None and hasattr(fail_value.ast, 'position'):
        pos = fail_value.ast.position
    
    # Add source location if available
    if pos:
        if pos.filename and pos.start_line:
            error_line += f" at {pos.filename}:{pos.start_line}"
        elif pos.start_line:
            error_line += f" on line {pos.start_line}"
    
    lines.append(error_line)
    
    # Add message
    if message:
        lines.append(f"{prefix}  {message}")
    
    # Add source line if available
    if pos and pos.filename and pos.start_line:
        try:
            with open(pos.filename, 'r', encoding='utf-8') as f:
                source_lines = f.readlines()
                line_idx = pos.start_line - 1
                if 0 <= line_idx < len(source_lines):
                    source_line = source_lines[line_idx].rstrip()
                    lines.append(f"{prefix}  | {source_line}")
                    
                    # Add caret line pointing to the error column
                    if pos.start_column:
                        # Calculate spaces needed (accounting for the "  | " prefix)
                        # Column is 1-indexed
                        spaces = " " * (pos.start_column - 1)
                        lines.append(f"{prefix}  | {spaces}^")
        except (OSError, IOError):
            # Couldn't read source file, skip it
            pass
    
    # Add cause chain
    if cause:
        lines.append(f"{prefix}  Caused by:")
        lines.append(format_failure(cause, indent + 2))
    
    return "\n".join(lines)


# Basic builtin functions (some placeholder temporaries)

def builtin_double(frame, input_value, args):
    """Double a number: [5 |double] → 10"""
    # Input shape ~num ensures input_value is a number
    input_value = input_value.as_scalar()
    return comp.Value(input_value.data * 2)
    yield  # Make it a generator (unreachable)


def builtin_print(frame, input_value, args):
    """Print a value and pass it through: [5 |print] → 5 (with side effect)"""
    # Print the value using unparse() for clean output
    print(input_value.as_scalar().unparse())
    # Pass through unchanged
    return input_value
    yield  # Make it a generator (unreachable)


def builtin_identity(frame, input_value, args):
    """Identity function - returns input unchanged: [5 |identity] → 5"""
    return input_value
    yield  # Make it a generator (unreachable)


def builtin_length(frame, input_value, args):
    """Get the number of fields in a struct: [{a=1 b=2 c=3} |length] → 3"""
    # Input shape ~struct ensures input_value is a struct
    return comp.Value(len(input_value.struct))
    yield  # Make it a generator (unreachable)


def builtin_add(frame, input_value, args):
    """Add argument to input: [5 |add ^{n=3}] → 8"""
    # Input shape ~num ensures input_value is a number
    # Arg shape ~{n~num} ensures args has field 'n' with a number value
    input_value = input_value.as_scalar()
    n_value = args.struct[comp.Value("n")]
    return comp.Value(input_value.data + n_value.data)
    yield  # Make it a generator (unreachable)


def builtin_wrap(frame, input_value, args):
    """Wrap input in a struct with given key: [5 |wrap ^{key="x"}] → {x: 5}"""
    # Arg shape ~{key~str} ensures args has field 'key' with a string value
    key_value = args.struct[comp.Value("key")]
    return comp.Value({key_value: input_value})
    yield  # Make it a generator (unreachable)


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

    # Check if else_arg is the default empty struct {} (meaning no else was provided)
    if else_arg is not None:
        if else_arg.is_struct and len(else_arg.data) == 0:
            # Default value {} means no else argument was provided
            else_arg = None
    
    # Evaluate condition
    if cond_arg.is_block or cond_arg.is_raw_block:
        # Condition is a block - evaluate it with input_value
        block_value = cond_arg
        if cond_arg.is_raw_block:
            # Convert RawBlock to typed Block with empty input shape (any-block)
            block_value = comp.Value(comp.Block(cond_arg.data, input_shape=[]))
        compute = comp.prepare_block_call(block_value, input_value)
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
    if branch_arg.is_block or branch_arg.is_raw_block:
        block_value = branch_arg
        if branch_arg.is_raw_block:
            block_value = comp.Value(comp.Block(branch_arg.data, input_shape=[]))
        compute = comp.prepare_block_call(block_value, input_value)
        if isinstance(compute, comp.Value):
            return compute  # Error during preparation
        result = yield compute
        if frame.bypass_value(result):
            return result
        return result

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
    # Input shape ~any accepts any value (no restriction)
    # Arg shape ~{index~num} ensures args has field 'index' with a number value

    # Get the index argument
    index_value = args.struct[comp.Value("index")].as_scalar()
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
    yield  # Make it a generator (unreachable)


def builtin_format_failure(frame, input_value, args):
    """Format a failure value as a human-readable string.
    
    Usage: [$var.error |format-failure] → "fail at file.comp:10\n  Error message\n..."
    
    Takes a failure value and returns a formatted string with:
    - Error tag or message
    - Source file location (filename:line)
    - Source code context with caret pointer
    - Cause chain for nested errors
    
    Returns the formatted string, or if input is not a failure, returns
    the string representation of the input.
    """
    # Input shape ~any accepts any value
    result_str = format_failure(input_value)
    return comp.Value(result_str)
    yield  # Make it a generator (unreachable)


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

    module = comp.Module(is_builtin=True)

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
    block_shape_def = comp.BlockShapeDefinition(fields=[])
    
    # Create a ShapeField (runtime entity) with the BlockShapeDefinition
    # This is a single positional field that is the block shape itself
    module.define_shape(["any-block"], fields=[comp.ShapeField(
        name=None,  # Positional field (no name)
        shape=block_shape_def,  # The ~:{} block shape (runtime entity)
        default=None
    )])

    # Register Python-backed functions with their arg shapes
    # Format: name: (func, arg_shape_text or None)
    # Use parse_shape() to create shapes from text
    funcs_with_shapes = [
        ("double", builtin_double, "~num", None),
        ("print", builtin_print, "~any", None),
        ("identity", builtin_identity, "~any", None),
        ("length", builtin_length, "~struct", None),
        ("add", builtin_add, "~num", "~{n~num}"),
        ("wrap", builtin_wrap, "~any", "~{key~str}"),
        ("subscript", builtin_subscript, "~any", "~{index~num}"),
        ("format-failure", builtin_format_failure, "~any", None),
        # if accepts blocks OR values for all arguments (checked at runtime)
        ("if", builtin_if, "~any", "~{~any ~any ~any={}}"),  # cond, then, else (optional, default empty struct)
        # loop requires a block
        ("loop", builtin_loop, "~any", "~{op~any-block}"),
    ]

    for name, func, input_shape, arg_shape in funcs_with_shapes:
        module.define_py_function(
            path=[name],
            python_func=func,
            input_shape=input_shape,
            arg_shape=arg_shape,
            is_pure=True,
        )

    _builtin_module = module
    return _builtin_module


# Singleton instance (Module | None)
_builtin_module = None

