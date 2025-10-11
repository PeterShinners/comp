"""Example showing how EvalContext would be used in the runtime.

This demonstrates the migration path from the current scopes-based
approach to the context-based approach.
"""

from . import _context, _value, builtin


# BEFORE (current approach):
def old_style_binary_op(expr, module, scopes, evaluate_func):
    """Old style with scopes dict and evaluate_func parameter."""
    left = evaluate_func(expr.left, module, scopes)
    # Check if failure...
    right = evaluate_func(expr.right, module, scopes)
    # More logic...
    
    # Create failure value manually
    if left.is_num and right.is_str:
        return _value.Value({
            _value.Unnamed(): builtin.fail_runtime,
            "message": "Cannot add number and string"
        })
    
    return _value.Value(left.num + right.num)


# AFTER (with EvalContext):
def new_style_binary_op(expr, ctx):
    """New style with EvalContext."""
    # Evaluate sub-expressions using context
    left = ctx.evaluate(expr.left)
    
    # Check if we should skip (extensible for future pipeline bypass)
    if ctx.should_skip(left):
        return left
    
    right = ctx.evaluate(expr.right)
    if ctx.should_skip(right):
        return right
    
    # Create failure using context (includes stack trace automatically)
    if left.is_num and right.is_str:
        return ctx.fail(
            "Cannot add number and string",
            tag=builtin.fail_type,
            left_type="num",
            right_type="str"
        )
    
    # Create values using context (future: tracks creation location)
    return ctx.value(left.num + right.num, ast_node=expr)


# Function call example:
def call_function_with_context(func_def, input_value, arg_value, ctx):
    """Example of calling a function with context tracking."""
    # Push a stack frame for this function call
    frame = ctx.push_frame(
        name=func_def.name,
        frame_type="function",
        in_value=input_value,
        arg_value=arg_value,
        # ast_node=func_def.ast_node  # Future
    )
    
    try:
        # Evaluate function body with updated context
        result = ctx.evaluate(func_def.body)
        return result
    finally:
        # Always pop the frame
        ctx.pop_frame()


# Pipeline example:
def evaluate_pipeline_with_context(pipeline_ast, seed_value, ctx):
    """Example of pipeline evaluation with context."""
    # Push pipeline frame
    ctx.push_frame(
        name="pipeline",
        frame_type="pipeline",
        in_value=seed_value
    )
    
    try:
        current = seed_value
        
        for stage in pipeline_ast.stages:
            # Check if current value should skip
            if ctx.should_skip(current):
                return current
            
            # Update $in for this stage
            ctx.set_scope('in', current)
            
            # Evaluate stage
            current = ctx.evaluate(stage)
        
        return current
    finally:
        ctx.pop_frame()


# Simple usage from Python:
def example_usage():
    """Show how to use EvalContext from Python."""
    import comp
    
    # Parse some code
    module = comp.parse_module("!func |test ~{x ~num} = {x * 2}")
    
    # Create a simple context
    ctx = _context.create_simple_context(
        module=module,
        in_value=_value.Value({"x": 10})
    )
    
    # Evaluate something
    # result = ctx.evaluate(some_ast)
    
    # Custom skip predicate example:
    def my_skip_predicate(value):
        # Skip both failures AND empty structs
        if ctx.should_skip(value):  # Check default (failures)
            return True
        return value.is_struct and len(value.struct) == 0
    
    ctx.set_skip_predicate(my_skip_predicate)
    
    # Now empty structs will also be skipped in pipelines
    # This demonstrates the extensibility for custom "bypass" types


# Migration path - wrap old functions:
def evaluate_with_context_wrapper(expr, module, scopes):
    """Temporary wrapper to use context with old-style code.
    
    This allows gradual migration.
    """
    # Create context from old-style scopes
    ctx = _context.EvalContext(module)
    ctx._scopes = scopes.copy()  # Use existing scopes
    
    # Could push an initial frame
    ctx.push_frame("evaluation", "module")
    
    try:
        return ctx.evaluate(expr)
    finally:
        ctx.pop_frame()
