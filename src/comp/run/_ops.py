"""Operator evaluation for runtime values."""

__all__ = ["evaluate_binary_op", "evaluate_unary_op"]

from . import _value, builtin


def evaluate_binary_op(expr, module, scopes, evaluate_func):
    """Evaluate a binary operation expression.
    
    Handles:
    - Mathematical operations (+, -, *, /, %, **)
    - String concatenation (+)
    - Comparison operators (==, !=, <, <=, >, >=)
    - Boolean operators (&&, ||)
    
    Args:
        expr: BinaryOp AST node
        module: Module context
        scopes: Scope values dict
        evaluate_func: The evaluate function to use for sub-expressions
    
    Returns:
        Result Value from applying the operator
        
    Raises:
        ValueError: If the operator cannot be applied to the operand types
    """
    # Boolean operators - short-circuit evaluation
    if expr.op == "&&":
        left = evaluate_func(expr.left, module, scopes)
        if not _is_boolean_tag(left):
            raise ValueError(f"Boolean operator && requires boolean operands, got {left}")
        # Short-circuit: if left is false, return false without evaluating right
        if left.tag is builtin.false:
            return left
        right = evaluate_func(expr.right, module, scopes)
        if not _is_boolean_tag(right):
            raise ValueError(f"Boolean operator && requires boolean operands, got {right}")
        return right
    
    elif expr.op == "||":
        left = evaluate_func(expr.left, module, scopes)
        if not _is_boolean_tag(left):
            raise ValueError(f"Boolean operator || requires boolean operands, got {left}")
        # Short-circuit: if left is true, return true without evaluating right
        if left.tag is builtin.true:
            return left
        right = evaluate_func(expr.right, module, scopes)
        if not _is_boolean_tag(right):
            raise ValueError(f"Boolean operator || requires boolean operands, got {right}")
        return right
    
    # For all other operators, evaluate both operands
    left = evaluate_func(expr.left, module, scopes)
    right = evaluate_func(expr.right, module, scopes)
    
    # Comparison operators
    if expr.op in ("==", "!=", "<", "<=", ">", ">="):
        return _compare_values(left, right, expr.op)

    # Mathematical operations on numbers
    if left.is_num and right.is_num:
        if expr.op == "+":
            return _value.Value(left.num + right.num)
        elif expr.op == "-":
            return _value.Value(left.num - right.num)
        elif expr.op == "*":
            return _value.Value(left.num * right.num)
        elif expr.op == "/":
            return _value.Value(left.num / right.num)
        elif expr.op == "//":
            return _value.Value(left.num // right.num)
        elif expr.op == "%":
            return _value.Value(left.num % right.num)
        elif expr.op == "**":
            return _value.Value(left.num ** right.num)

    # String concatenation
    if expr.op == "+" and left.is_str and right.is_str:
        return _value.Value(left.str + right.str)

    raise ValueError(f"Cannot apply operator {expr.op} to {left} and {right}")


def evaluate_unary_op(expr, module, scopes, evaluate_func):
    """Evaluate a unary operation expression.
    
    Handles:
    - Unary plus and minus on numbers
    - Logical NOT (!!) on booleans
    
    Args:
        expr: UnaryOp AST node
        module: Module context
        scopes: Scope values dict
        evaluate_func: The evaluate function to use for sub-expressions
    
    Returns:
        Result Value from applying the operator
        
    Raises:
        ValueError: If the operator cannot be applied to the operand type
    """
    operand = evaluate_func(expr.right, module, scopes)

    if expr.op == "!!":
        # Logical NOT on booleans
        if not _is_boolean_tag(operand):
            raise ValueError(f"Logical NOT (!!) requires boolean operand, got {operand}")
        if operand.tag is builtin.true:
            return _value.Value(builtin.false)
        else:
            return _value.Value(builtin.true)
    
    if operand.is_num:
        if expr.op == "-":
            return _value.Value(-operand.num)
        elif expr.op == "+":
            return _value.Value(+operand.num)

    raise ValueError(f"Cannot apply unary operator {expr.op} to {operand}")


def _is_boolean_tag(value):
    """Check if a value is a boolean tag (#true or #false)."""
    return value.is_tag and (value.tag is builtin.true or value.tag is builtin.false)


def _compare_values(left, right, op):
    """Compare two values according to Comp's total ordering rules.
    
    Equality operators (==, !=) require same type.
    Ordering operators (<, <=, >, >=) use deterministic total ordering.
    
    Type ordering: {} < #false < #true < numbers < strings < non-empty structs < other tags
    
    Args:
        left: Left Value operand
        right: Right Value operand
        op: Comparison operator (==, !=, <, <=, >, >=)
        
    Returns:
        Value containing #true or #false tag
    """
    # Equality operators
    if op == "==":
        result = _values_equal(left, right)
        return _value.Value(builtin.true if result else builtin.false)
    
    elif op == "!=":
        result = _values_equal(left, right)
        return _value.Value(builtin.false if result else builtin.true)
    
    # Ordering operators - use total ordering
    # Type ordering: {} < #false < #true < numbers < strings < non-empty structs < other tags
    cmp_result = _compare_total_order(left, right)
    
    if op == "<":
        return _value.Value(builtin.true if cmp_result < 0 else builtin.false)
    elif op == "<=":
        return _value.Value(builtin.true if cmp_result <= 0 else builtin.false)
    elif op == ">":
        return _value.Value(builtin.true if cmp_result > 0 else builtin.false)
    elif op == ">=":
        return _value.Value(builtin.true if cmp_result >= 0 else builtin.false)
    
    raise ValueError(f"Unknown comparison operator: {op}")


def _values_equal(left, right):
    """Test if two values are equal (structural equality).
    
    Equality requires same type and same content.
    Tags are compared by identity - aliases compare as equal.
    Note: For now, we only support basic types (not full struct comparison).
    """
    # Different types cannot be compared - raise error
    if left.is_num != right.is_num:
        raise ValueError(f"Cannot compare equality between different types: {left} and {right}")
    if left.is_str != right.is_str:
        raise ValueError(f"Cannot compare equality between different types: {left} and {right}")
    if left.is_tag != right.is_tag:
        raise ValueError(f"Cannot compare equality between different types: {left} and {right}")
    if left.is_struct != right.is_struct:
        raise ValueError(f"Cannot compare equality between different types: {left} and {right}")
    
    # Same type comparisons
    if left.is_num:
        return left.num == right.num
    elif left.is_str:
        return left.str == right.str
    elif left.is_tag:
        # Tag equality is by identity (same TagValue instance)
        # This means aliases (different names, same tag) compare as equal
        return left.tag is right.tag
    elif left.is_struct:
        # TODO: Implement full struct comparison
        # For now, just do basic comparison
        if len(left.struct) != len(right.struct):
            return False
        # Simple key-value comparison (not handling all edge cases yet)
        for key, val in left.struct.items():
            if key not in right.struct:
                return False
            if not _values_equal(val, right.struct[key]):
                return False
        return True
    
    return False


def _compare_total_order(left, right):
    """Compare two values using total ordering.
    
    Returns:
        -1 if left < right
        0 if left == right
        1 if left > right
    
    Type ordering: {} < #false < #true < numbers < strings < non-empty structs < other tags
    Within same type, use natural ordering.
    """
    # Get type priorities (lower number = comes first)
    # Special handling for boolean tags which come before numbers
    def type_priority(val):
        if val.is_struct:
            # Empty struct comes first
            if not val.struct or len(val.struct) == 0:
                return 0
            # Non-empty structs come after strings
            return 5
        elif val.is_tag:
            # Boolean tags have special priority before numbers
            if val.tag is builtin.false:
                return 1
            elif val.tag is builtin.true:
                return 2
            # Other tags come last
            return 6
        elif val.is_num:
            return 3
        elif val.is_str:
            return 4
        return 7  # Unknown type
    
    left_priority = type_priority(left)
    right_priority = type_priority(right)
    
    # Different types: compare by type priority
    if left_priority != right_priority:
        return -1 if left_priority < right_priority else 1
    
    # Same type: compare within type
    if left.is_num:
        if left.num < right.num:
            return -1
        elif left.num > right.num:
            return 1
        else:
            return 0
    
    elif left.is_str:
        if left.str < right.str:
            return -1
        elif left.str > right.str:
            return 1
        else:
            return 0
    
    elif left.is_tag:
        # Tag ordering: identity-equal tags are equal (handles aliases)
        if left.tag is right.tag:
            return 0
        
        # Special case for boolean tags
        if left.tag is builtin.false and right.tag is builtin.true:
            return -1
        if left.tag is builtin.true and right.tag is builtin.false:
            return 1
        
        # Lexicographical comparison: compare leaf names, then walk up hierarchy
        # Tag identifiers are stored left-to-right (root first)
        # e.g., ["status", "error", "timeout"] for #timeout.error.status
        left_id = left.tag.identifier
        right_id = right.tag.identifier
        
        # Compare from leaf (rightmost) to root (leftmost)
        max_depth = max(len(left_id), len(right_id))
        for i in range(1, max_depth + 1):
            # Get component from the right (leaf first)
            left_component = left_id[-i] if i <= len(left_id) else None
            right_component = right_id[-i] if i <= len(right_id) else None
            
            # If one ran out of components, shorter is less
            if left_component is None:
                return -1  # left is shorter (parent)
            if right_component is None:
                return 1   # right is shorter (parent)
            
            # Compare components lexicographically
            if left_component < right_component:
                return -1
            elif left_component > right_component:
                return 1
            # If equal, continue to next level up
        
        # All components equal (shouldn't happen if not identity-equal)
        return 0
    
    elif left.is_struct:
        # TODO: Implement full struct ordering
        # For now, compare by size
        if len(left.struct) < len(right.struct):
            return -1
        elif len(left.struct) > len(right.struct):
            return 1
        else:
            return 0
    
    return 0
