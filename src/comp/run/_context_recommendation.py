"""Recommended approach for using EvalContext in runtime functions.

This demonstrates the clearest pattern: expressions passed explicitly,
context replaces (module, scopes, evaluate_func).

Functions still use return values for clarity and testability.
Context provides the "where/how" while expression provides the "what".
"""

from . import _context, _value, builtin


# ============================================================================
# RECOMMENDED PATTERN
# ============================================================================

def evaluate_binary_op(expr, ctx: _context.EvalContext) -> _value.Value:
    """Recommended signature: expression + context, returns Value.
    
    - expr: What to evaluate (the intent)
    - ctx: Where we are and how to evaluate (the state)
    - Returns: Result value (functional style)
    
    This is clean, testable, and Pythonic.
    """
    # Boolean operators - short-circuit evaluation
    if expr.op == "&&":
        left = ctx.evaluate(expr.left)
        if ctx.should_skip(left):
            return left
        if not _is_boolean_tag(left):
            return ctx.fail(f"Boolean operator && requires boolean operands, got {left}")
        
        # Short-circuit: if left is false, don't evaluate right
        if left.tag is builtin.false:
            return left
        
        right = ctx.evaluate(expr.right)
        if ctx.should_skip(right):
            return right
        if not _is_boolean_tag(right):
            return ctx.fail(f"Boolean operator && requires boolean operands, got {right}")
        return right
    
    # For all other operators, evaluate both operands
    left = ctx.evaluate(expr.left)
    if ctx.should_skip(left):
        return left
    
    right = ctx.evaluate(expr.right)
    if ctx.should_skip(right):
        return right
    
    # Comparison operators
    if expr.op in ("==", "!=", "<", "<=", ">", ">="):
        return _compare_values(left, right, expr.op, ctx)
    
    # Math operators
    if left.is_num and right.is_num:
        if expr.op == "+":
            return ctx.value(left.num + right.num)
        elif expr.op == "-":
            return ctx.value(left.num - right.num)
        elif expr.op == "*":
            return ctx.value(left.num * right.num)
        elif expr.op == "/":
            if right.num == 0:
                return ctx.fail("Division by zero", tag=builtin.fail_runtime)
            return ctx.value(left.num / right.num)
    
    # String concatenation
    if expr.op == "+" and left.is_str and right.is_str:
        return ctx.value(left.str + right.str)
    
    return ctx.fail(f"Cannot apply operator {expr.op} to {left} and {right}")


def _is_boolean_tag(value):
    """Helper - same as before."""
    return value.is_tag and (value.tag is builtin.true or value.tag is builtin.false)


def _compare_values(left, right, op, ctx):
    """Helper - takes context for fail() calls."""
    # ... comparison logic ...
    if left.is_num != right.is_num:
        return ctx.fail(f"Cannot compare different types: {left} and {right}")
    
    # ... rest of logic
    return ctx.value(builtin.true)


# ============================================================================
# CALL SITES - How functions call each other
# ============================================================================

def evaluate_structure(expr, ctx: _context.EvalContext) -> _value.Value:
    """Example showing how evaluation functions call each other.
    
    The pattern:
    1. Take expression + context
    2. Call ctx.evaluate() for sub-expressions
    3. Return the result
    
    Context flows through naturally, expressions are explicit.
    """
    fields = {}
    
    for assignment in expr.assignments:
        # Evaluate the value expression
        value = ctx.evaluate(assignment.value_expr)
        
        # Check if we got a failure
        if ctx.should_skip(value):
            # For structures, we might want to propagate the failure
            return value
        
        # Store in fields dict
        fields[assignment.name] = value
    
    # Create the struct value
    return ctx.value(fields)


def evaluate_pipeline(expr, ctx: _context.EvalContext) -> _value.Value:
    """Example showing stack frame management in context.
    
    For pipeline, we want to track it in the stack and manage $in scope.
    """
    # Evaluate seed if present
    if expr.seed:
        current = ctx.evaluate(expr.seed)
        if ctx.should_skip(current):
            return current
    else:
        # Use $in from enclosing scope
        current = ctx.get_scope('in')
    
    # Push a pipeline frame to track execution
    ctx.push_frame(
        name="pipeline",
        frame_type="pipeline",
        in_value=current,
        ast_node=expr
    )
    
    try:
        # Process each stage
        for stage in expr.stages:
            # Check if we should skip
            if ctx.should_skip(current):
                return current
            
            # Update $in for this stage
            ctx.set_scope('in', current)
            
            # Evaluate the stage
            current = ctx.evaluate(stage)
        
        return current
    
    finally:
        # Always pop the frame
        ctx.pop_frame()


def call_function(func_def, input_value, arg_value, ctx: _context.EvalContext) -> _value.Value:
    """Example showing function calls with context.
    
    Function calls push a frame with new $in/$arg scopes.
    """
    # Push function call frame
    ctx.push_frame(
        name=func_def.name,
        frame_type="function",
        in_value=input_value,
        arg_value=arg_value,
        ast_node=func_def.ast_node if hasattr(func_def, 'ast_node') else None
    )
    
    try:
        # Evaluate function body with new scopes
        result = ctx.evaluate(func_def.body)
        return result
    
    finally:
        # Pop frame restores previous scopes
        ctx.pop_frame()


# ============================================================================
# WHY RETURN VALUES INSTEAD OF ctx.set_result()?
# ============================================================================

def why_return_values():
    """
    You asked: "I guess this means functions put their result onto 
    the context instead of dealing with return values?"
    
    My recommendation: Keep using return values. Here's why:
    
    1. TESTABILITY
       result = evaluate_binary_op(expr, ctx)
       assert result.is_num
       
       vs
       
       evaluate_binary_op(expr, ctx)
       assert ctx.result.is_num  # Less clear where result came from
    
    2. CALL STACK CLARITY
       The Python call stack shows what's being evaluated:
       
       evaluate_pipeline() at line 100
         evaluate_structure() at line 50
           evaluate_binary_op() at line 30
       
       vs context-based would all be "ctx.step()" - harder to debug
    
    3. FUNCTIONAL REASONING
       result = a(b(c(x)))  # Clear data flow
       
       vs
       
       ctx.eval(x)
       ctx.step_c()
       ctx.step_b()
       ctx.step_a()
       result = ctx.result  # Less clear
    
    4. PYTHON IDIOMS
       Python developers expect functions to return values.
       It's easier to understand and maintain.
    
    5. EXCEPTION COMPATIBILITY
       With returns, exceptions can still propagate if needed.
       With ctx.result, you'd need to check ctx.has_error everywhere.
    
    WHEN to use ctx.set_result():
    - If you need true continuation-passing style
    - If you want to build an interpreter loop with explicit eval stack
    - If you need very fine-grained control of evaluation order
    
    But for Comp, I recommend keeping return values.
    Context provides environment/state, functions return results.
    """
    pass


# ============================================================================
# STACK AS LINKED LIST
# ============================================================================

def about_linked_list_stack():
    """
    You mentioned: "Python keeps the stack as a linked list (with 'back' 
    references). But maybe that is just an efficiency thing?"
    
    Python's frame.f_back is both an efficiency and debugging feature:
    
    1. EFFICIENCY
       - No copying needed when pushing/popping
       - O(1) frame access
       - Natural for recursion
    
    2. DEBUGGING
       - Can walk the stack from any frame
       - Inspect variables in parent frames
       - Build tracebacks
    
    For Comp's EvalContext, our list-based approach is fine because:
    
    1. We control when frames are pushed/popped (no async weirdness)
    2. We rarely need to inspect parent frames during evaluation
    3. Python's list operations are very fast
    4. Code is simpler and more Pythonic
    
    If we needed it, we could add:
    
    class StackFrame:
        def __init__(self, ...):
            self.parent = None  # Set when pushed
            
    ctx.push_frame(...):
        frame.parent = self.current_frame
        self.stack.append(frame)
    
    But I'd wait until there's a clear need. YAGNI principle applies.
    """
    pass


# ============================================================================
# ALTERNATIVE: "CONTEXT KNOWS WHAT TO DO NEXT"
# ============================================================================

def context_driven_evaluation_example():
    """
    You mentioned interest in "context knows what should be done next".
    
    This is an interesting idea! It could look like:
    
    class EvalContext:
        def __init__(self):
            self.eval_stack = []  # Stack of expressions to evaluate
            self.value_stack = []  # Stack of completed values
            
        def push_eval(self, expr):
            '''Schedule an expression for evaluation.'''
            self.eval_stack.append(expr)
        
        def step(self):
            '''Evaluate one step of the top expression.'''
            if not self.eval_stack:
                return None
            
            expr = self.eval_stack[-1]
            
            # Dispatch based on expression type
            if isinstance(expr, BinaryOp):
                return self._step_binary_op()
            elif isinstance(expr, Identifier):
                return self._step_identifier()
            # ...
        
        def run_to_completion(self):
            '''Run until eval_stack is empty.'''
            while self.eval_stack:
                self.step()
            return self.value_stack[-1] if self.value_stack else None
    
    This enables:
    - Stepping through evaluation (debugger)
    - Pausing/resuming execution
    - Limiting evaluation steps (timeouts)
    - Async evaluation (await in the step loop)
    - Recording full execution trace
    
    But it comes with costs:
    - Much more complex state management
    - Harder to reason about control flow
    - Need to reify all local state into the context
    - Less Pythonic, harder for contributors to understand
    
    My take: Start simple (expression + context + return values).
    If you need stepper/async later, you can add it as a layer on top:
    
    class SteppableContext(EvalContext):
        def evaluate_stepped(self, expr):
            # Break evaluation into steps
            # Yield at each step
            # Still use the simple evaluate() underneath
    
    Don't prematurely commit to the complex architecture unless you
    know you'll need it. The simple approach can evolve into it.
    """
    pass


# ============================================================================
# FINAL RECOMMENDATION
# ============================================================================

"""
RECOMMENDED PATTERN FOR COMP:

Signature:  def evaluate_xxx(expr, ctx: EvalContext) -> Value
            
            - expr: AST node (what to evaluate)
            - ctx: Runtime context (where/how to evaluate)
            - Returns: Result value
            
Evaluation: result = ctx.evaluate(sub_expr)
            - Context handles recursive evaluation
            - No more passing evaluate_func around
            
Failures:   return ctx.fail("error message", tag=builtin.fail_type)
            - Context automatically includes stack trace
            - Replaces manual failure struct creation
            
Skipping:   if ctx.should_skip(value):
                return value
            - Generic skip check (extensible beyond failures)
            - Clean pipeline bypass semantics
            
Frames:     ctx.push_frame("function_name", "function", in_value=..., arg_value=...)
            try:
                result = ctx.evaluate(body)
                return result
            finally:
                ctx.pop_frame()
            - Track execution for stack traces
            - Manage scope transitions
            
Values:     return ctx.value(data, ast_node=expr)
            - Future: tracks creation location
            - Consistent value creation

This is:
- Simple and Pythonic
- Easy to test and debug  
- Functional in style (clear data flow)
- Extensible (can add stepping/async later)
- Natural for Comp's evaluation model

The context provides infrastructure (where/how), functions provide logic (what),
and return values provide results. Clean separation of concerns.
"""
