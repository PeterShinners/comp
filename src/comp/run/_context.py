"""Evaluation context for tracking runtime state during code execution.

The EvalContext manages the execution environment including:
- Stack trace for function calls
- Scope management ($in, $arg, locals)
- Failure/skip value tracking
- Source location tracking for errors
- Value creation tied to execution context
"""

__all__ = ["EvalContext", "StackFrame"]

from typing import Optional, Callable, Any
from . import _value, _mod, builtin


class StackFrame:
    """Represents a single frame in the execution stack.
    
    Tracks function calls, pipeline stages, and other execution contexts
    with their associated scopes and metadata.
    """
    
    def __init__(
        self,
        name: str,
        frame_type: str,  # "function", "pipeline", "module"
        in_value: Optional[_value.Value] = None,
        arg_value: Optional[_value.Value] = None,
        ast_node: Optional[Any] = None,
    ):
        """Initialize a stack frame.
        
        Args:
            name: Descriptive name (function name, "pipeline", etc.)
            frame_type: Type of frame ("function", "pipeline", "module")
            in_value: Value of $in scope for this frame
            arg_value: Value of $arg scope for this frame
            ast_node: Optional AST node being executed
        """
        self.name = name
        self.frame_type = frame_type
        self.in_value = in_value
        self.arg_value = arg_value
        self.ast_node = ast_node
        self.locals = {}  # @ local variables
        
    def __repr__(self):
        parts = [f"{self.frame_type}:{self.name}"]
        if self.in_value is not None:
            parts.append(f"$in={self.in_value}")
        if self.arg_value is not None:
            parts.append(f"$arg={self.arg_value}")
        if self.locals:
            parts.append(f"@locals={len(self.locals)}")
        return f"StackFrame({', '.join(parts)})"


class EvalContext:
    """Runtime evaluation context for Comp code execution.
    
    Manages execution state including:
    - Stack frames for tracing
    - Current module and scopes
    - Failure/skip value detection
    - Value creation with context tracking
    """
    
    def __init__(self, module: Optional[_mod.Module] = None):
        """Initialize evaluation context.
        
        Args:
            module: The module being executed
        """
        self.module = module
        self.stack = []  # Stack of StackFrame objects
        self._skip_predicate = None  # Optional: Callable[[Value], bool]
        
        # Current scope values (managed by stack frames, but cached for fast access)
        self._scopes = {
            'in': _value.Value({}),
            'out': _value.Value({}),
            'arg': _value.Value({}),
            'ctx': _value.Value({}),
            'mod': _value.Value({}),
            '_value': _value.Value({}),  # Current pipeline accumulator
        }
    
    def push_frame(
        self,
        name: str,
        frame_type: str,
        in_value: Optional[_value.Value] = None,
        arg_value: Optional[_value.Value] = None,
        ast_node: Optional[Any] = None,
    ) -> StackFrame:
        """Push a new stack frame for entering a function/pipeline/etc.
        
        Args:
            name: Frame identifier
            frame_type: "function", "pipeline", "module", etc.
            in_value: New $in value for this frame (if any)
            arg_value: New $arg value for this frame (if any)
            ast_node: AST node being executed
            
        Returns:
            The created StackFrame
        """
        frame = StackFrame(name, frame_type, in_value, arg_value, ast_node)
        self.stack.append(frame)
        
        # Update scope cache if values provided
        if in_value is not None:
            self._scopes['in'] = in_value
        if arg_value is not None:
            self._scopes['arg'] = arg_value
            
        return frame
    
    def pop_frame(self) -> Optional[StackFrame]:
        """Pop the top stack frame when exiting a function/pipeline/etc.
        
        Returns:
            The popped StackFrame, or None if stack was empty
        """
        if not self.stack:
            return None
        
        frame = self.stack.pop()
        
        # Restore previous scope values from parent frame
        if self.stack:
            parent = self.stack[-1]
            if parent.in_value is not None:
                self._scopes['in'] = parent.in_value
            if parent.arg_value is not None:
                self._scopes['arg'] = parent.arg_value
        else:
            # Back to empty scopes
            self._scopes['in'] = _value.Value({})
            self._scopes['arg'] = _value.Value({})
            
        return frame
    
    @property
    def current_frame(self) -> Optional[StackFrame]:
        """Get the current (top) stack frame."""
        return self.stack[-1] if self.stack else None
    
    @property
    def scopes(self) -> dict:
        """Get current scope values (for compatibility with existing code).
        
        Returns dict mapping scope names to Values.
        """
        return self._scopes
    
    def get_scope(self, name: str) -> _value.Value:
        """Get a scope value by name.
        
        Args:
            name: Scope name ('in', 'out', 'arg', 'ctx', 'mod', '_value')
            
        Returns:
            The scope Value
        """
        return self._scopes.get(name, _value.Value({}))
    
    def set_scope(self, name: str, value: _value.Value):
        """Set a scope value.
        
        Args:
            name: Scope name
            value: The Value to set
        """
        self._scopes[name] = value
    
    def set_local(self, name: str, value: _value.Value):
        """Set a @ local variable in the current frame.
        
        Args:
            name: Local variable name (without @)
            value: The value to store
        """
        if self.current_frame:
            self.current_frame.locals[name] = value
    
    def get_local(self, name: str) -> Optional[_value.Value]:
        """Get a @ local variable from the current frame.
        
        Args:
            name: Local variable name (without @)
            
        Returns:
            The value, or None if not found
        """
        if self.current_frame:
            return self.current_frame.locals.get(name)
        return None
    
    def value(self, data, ast_node: Optional[Any] = None) -> _value.Value:
        """Create a Value with context tracking.
        
        This is the preferred way to create values during evaluation,
        as it can attach context metadata (future: stack trace, source location).
        
        Args:
            data: The data to wrap (int, str, dict, TagValue, etc.)
            ast_node: Optional AST node that created this value
            
        Returns:
            New Value instance
        """
        # For now, just create a regular Value
        # Future: could attach .created_by_frame, .source_location, etc.
        return _value.Value(data)
    
    def should_skip(self, value: _value.Value) -> bool:
        """Check if a value should skip/bypass normal operations.
        
        This is the extensible replacement for is_failure(). Initially
        just checks for #fail tags, but can be customized via set_skip_predicate().
        
        Args:
            value: Value to check
            
        Returns:
            True if this value should skip operations
        """
        # Use custom predicate if set
        if self._skip_predicate:
            return self._skip_predicate(value)
        
        # Default: check if it's a failure value
        return _is_failure_value(value)
    
    def set_skip_predicate(self, predicate: Callable[[_value.Value], bool]):
        """Set a custom predicate for determining skippable values.
        
        Args:
            predicate: Function that takes a Value and returns bool
        """
        self._skip_predicate = predicate
    
    def fail(
        self,
        message: str,
        tag: Optional[Any] = None,
        ast_node: Optional[Any] = None,
        **extra_fields
    ) -> _value.Value:
        """Create a failure value with context information.
        
        This replaces raising exceptions. The failure value includes
        stack trace information and source location.
        
        Args:
            message: Error message
            tag: Specific failure tag (defaults to #fail.runtime)
            ast_node: AST node where failure occurred
            **extra_fields: Additional fields to include in failure struct
            
        Returns:
            Failure Value (struct with failure tag)
        """
        if tag is None:
            tag = builtin.fail_runtime
        
        # Build failure struct
        failure_struct = {
            _value.Unnamed(): tag,
            "message": message,
        }
        
        # Add stack trace information
        if self.stack:
            trace = self._format_stack_trace()
            if trace:
                failure_struct["trace"] = trace
        
        # Add source location if available
        if ast_node and hasattr(ast_node, 'meta'):
            # Future: extract line/column from ast_node.meta
            pass
        
        # Add any extra fields
        failure_struct.update(extra_fields)
        
        return self.value(failure_struct)
    
    def _format_stack_trace(self) -> str:
        """Format current stack trace as a string.
        
        Returns:
            Multi-line string with stack trace
        """
        lines = []
        for i, frame in enumerate(reversed(self.stack)):
            indent = "  " * i
            lines.append(f"{indent}{frame.frame_type} '{frame.name}'")
            if frame.in_value is not None:
                lines.append(f"{indent}  $in = {frame.in_value}")
        return "\n".join(lines)
    
    def evaluate(self, expr, ast_node: Optional[Any] = None):
        """Evaluate an expression using this context.
        
        This provides a natural way to recursively evaluate sub-expressions
        without passing evaluate_func around.
        
        Args:
            expr: AST node to evaluate
            ast_node: Optional override for current AST node
            
        Returns:
            Evaluated Value
        """
        from . import _eval
        # For now, delegate to the module-level evaluate
        # Future: this could be the primary evaluation entry point
        return _eval.evaluate(expr, self.module, self.scopes)
    
    def __repr__(self):
        parts = [f"module={self.module.name if self.module else 'None'}"]
        parts.append(f"stack_depth={len(self.stack)}")
        if self.current_frame:
            parts.append(f"current={self.current_frame.name}")
        return f"EvalContext({', '.join(parts)})"


def _is_failure_value(value: _value.Value) -> bool:
    """Check if a value is a failure (has #fail or #fail.* tag).
    
    This is the default skip predicate. Checks if value is a struct
    with a failure tag as its first unnamed field.
    
    Args:
        value: Value to check
        
    Returns:
        True if value is a failure
    """
    if not value.is_struct:
        return False
    
    # Check for unnamed field with failure tag
    for key, val in value.struct.items():
        if isinstance(key, _value.Unnamed):
            if val.is_tag and val.tag is not None:
                # Check if tag is #fail or starts with "fail."
                tag_name = val.tag.name if hasattr(val.tag, 'name') else None
                if tag_name == "fail" or (tag_name and tag_name.startswith("fail.")):
                    return True
            break  # Only check first unnamed field
    
    return False


def create_simple_context(module: Optional[_mod.Module] = None, **scope_values) -> EvalContext:
    """Create a simple evaluation context for testing/scripting.
    
    This provides an easy way to start evaluating Comp code from Python.
    
    Args:
        module: Optional module context
        **scope_values: Initial scope values (in_value=..., arg_value=..., etc.)
        
    Returns:
        Ready-to-use EvalContext
        
    Example:
        >>> ctx = create_simple_context(in_value=Value({"x": 10}))
        >>> result = ctx.evaluate(some_ast)
    """
    ctx = EvalContext(module)
    
    # Set up initial scopes from kwargs
    for scope_name, value in scope_values.items():
        if scope_name.endswith('_value'):
            scope_name = scope_name[:-6]  # Remove '_value' suffix
        ctx.set_scope(scope_name, value if isinstance(value, _value.Value) else _value.Value(value))
    
    return ctx
