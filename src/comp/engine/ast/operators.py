"""Operator nodes for arithmetic, comparison, and boolean operations."""

from .base import ValueNode
from ..value import TRUE, FALSE, Value


class UnaryOp(ValueNode):
    """Unary operation: -x, !x, etc."""
    
    def __init__(self, op: str, operand: ValueNode):
        if not isinstance(op, str):
            raise TypeError(f"UnaryOp op must be str, got {type(op)}")
        if not isinstance(operand, ValueNode):
            raise TypeError(f"UnaryOp operand must be ValueNode, got {type(operand)}")
        
        self.op = op
        self.operand = operand
    
    def evaluate(self, engine):
        """Evaluate operand, then apply unary operator."""
        operand_value = yield self.operand
        
        if self.op == "-":
            if operand_value.is_number:
                return Value(-operand_value.data)
            else:
                return engine.fail(f"Cannot negate non-number: {operand_value.data}")
        
        elif self.op == "!!":
            if operand_value.tag == TRUE:
                return Value(FALSE, tag=FALSE)
            elif operand_value.tag == FALSE:
                return Value(TRUE, tag=TRUE)
            else:
                return engine.fail(f"Cannot apply !! to non-boolean: {operand_value}")
        
        else:
            return engine.fail(f"Unknown unary operator: {self.op}")
    
    def unparse(self) -> str:
        """Convert back to source code."""
        return f"{self.op}{self.operand.unparse()}"
    
    def __repr__(self):
        return f"UnaryOp({self.op!r}, {self.operand})"


class ArithmeticOp(ValueNode):
    """Arithmetic operation: x + y, x - y, x * y, x / y.
    
    Both operands must be numbers.
    Always evaluates both operands (no short-circuiting).
    """
    
    def __init__(self, op: str, left: ValueNode, right: ValueNode):
        if op not in ("+", "-", "*", "/"):
            raise ValueError(f"ArithmeticOp requires +, -, *, or /, got {op!r}")
        if not isinstance(left, ValueNode):
            raise TypeError(f"ArithmeticOp left must be ValueNode, got {type(left)}")
        if not isinstance(right, ValueNode):
            raise TypeError(f"ArithmeticOp right must be ValueNode, got {type(right)}")
        
        self.op = op
        self.left = left
        self.right = right
    
    def evaluate(self, engine):
        """Evaluate both operands, then apply arithmetic operation."""
        left_value = yield self.left
        right_value = yield self.right
        
        if not (left_value.is_number and right_value.is_number):
            return engine.fail(
                f"Arithmetic requires numbers, got {left_value.data} {self.op} {right_value.data}"
            )
        
        left_num = left_value.data
        right_num = right_value.data
        
        if self.op == "+":
            return Value(left_num + right_num)
        elif self.op == "-":
            return Value(left_num - right_num)
        elif self.op == "*":
            return Value(left_num * right_num)
        elif self.op == "/":
            if right_num == 0:
                return engine.fail("Division by zero")
            return Value(left_num / right_num)
    
    def unparse(self) -> str:
        """Convert back to source code."""
        return f"({self.left.unparse()} {self.op} {self.right.unparse()})"
    
    def __repr__(self):
        return f"ArithmeticOp({self.left}, {self.op!r}, {self.right})"


class ComparisonOp(ValueNode):
    """Comparison operation: x == y, x != y, x < y, x <= y, x > y, x >= y.
    
    == and != work on any values.
    <, <=, >, >= require numbers.
    Always evaluates both operands (no short-circuiting).
    Returns boolean (TRUE/FALSE tag).
    """
    
    def __init__(self, op: str, left: ValueNode, right: ValueNode):
        if op not in ("==", "!=", "<", "<=", ">", ">="):
            raise ValueError(f"ComparisonOp requires ==, !=, <, <=, >, or >=, got {op!r}")
        if not isinstance(left, ValueNode):
            raise TypeError(f"ComparisonOp left must be ValueNode, got {type(left)}")
        if not isinstance(right, ValueNode):
            raise TypeError(f"ComparisonOp right must be ValueNode, got {type(right)}")
        
        self.op = op
        self.left = left
        self.right = right
    
    def evaluate(self, engine):
        """Evaluate both operands, then apply comparison."""
        left_value = yield self.left
        right_value = yield self.right
        
        # Equality comparisons work on any values
        if self.op == "==":
            result = left_value.data == right_value.data
            return Value(TRUE if result else FALSE, tag=TRUE if result else FALSE)
        elif self.op == "!=":
            result = left_value.data != right_value.data
            return Value(TRUE if result else FALSE, tag=TRUE if result else FALSE)
        
        # Ordering comparisons require numbers
        if not (left_value.is_number and right_value.is_number):
            return engine.fail(
                f"Comparison {self.op} requires numbers, got {left_value.data} vs {right_value.data}"
            )
        
        left_num = left_value.data
        right_num = right_value.data
        
        if self.op == "<":
            result = left_num < right_num
        elif self.op == "<=":
            result = left_num <= right_num
        elif self.op == ">":
            result = left_num > right_num
        elif self.op == ">=":
            result = left_num >= right_num
        
        return Value(TRUE if result else FALSE, tag=TRUE if result else FALSE)
    
    def unparse(self) -> str:
        """Convert back to source code."""
        return f"({self.left.unparse()} {self.op} {self.right.unparse()})"
    
    def __repr__(self):
        return f"ComparisonOp({self.left}, {self.op!r}, {self.right})"


class BooleanOp(ValueNode):
    """Boolean operation: x && y, x || y.
    
    Short-circuits evaluation:
    - && returns left if FALSE, otherwise returns right
    - || returns left if TRUE, otherwise returns right
    
    Operands should be boolean values (TRUE/FALSE tags), but any value
    can be used - the tag determines truthiness.
    """
    
    def __init__(self, op: str, left: ValueNode, right: ValueNode):
        if op not in ("&&", "||"):
            raise ValueError(f"BooleanOp requires && or ||, got {op!r}")
        if not isinstance(left, ValueNode):
            raise TypeError(f"BooleanOp left must be ValueNode, got {type(left)}")
        if not isinstance(right, ValueNode):
            raise TypeError(f"BooleanOp right must be ValueNode, got {type(right)}")
        
        self.op = op
        self.left = left
        self.right = right
    
    def evaluate(self, engine):
        """Evaluate left operand, short-circuit if possible, else evaluate right."""
        left_value = yield self.left
        
        if self.op == "&&":
            # Short-circuit: if left is FALSE, return it without evaluating right
            if left_value.tag == FALSE:
                return left_value
            # Otherwise evaluate and return right
            right_value = yield self.right
            return right_value
        
        else:  # "||"
            # Short-circuit: if left is TRUE, return it without evaluating right
            if left_value.tag == TRUE:
                return left_value
            # Otherwise evaluate and return right
            right_value = yield self.right
            return right_value
    
    def unparse(self) -> str:
        """Convert back to source code."""
        return f"({self.left.unparse()} {self.op} {self.right.unparse()})"
    
    def __repr__(self):
        return f"BooleanOp({self.op!r}, {self.left}, {self.right})"


class FallbackOp(ValueNode):
    """Fallback operation: x ?? y.
    
    Evaluates left operand normally (fails propagate):
    - If left succeeds (not a fail value), return it
    - If left fails, evaluate and return right operand
    
    The key: FallbackOp wraps ITSELF in allow_failures() so that when
    the left operand fails and propagates, FallbackOp still receives the
    fail value instead of being skipped.
    
    Examples:
        (1/0) ?? 42          # Returns 42 (left fails, fallback handles)
        (1/0) ?? (2/0)       # Propagates second fail (both fail)
        @x.undefined ?? 0    # Returns 0 if field undefined
    """
    
    def __init__(self, left: ValueNode, right: ValueNode):
        if not isinstance(left, ValueNode):
            raise TypeError(f"FallbackOp left must be ValueNode, got {type(left)}")
        if not isinstance(right, ValueNode):
            raise TypeError(f"FallbackOp right must be ValueNode, got {type(right)}")
        
        self.left = left
        self.right = right
    
    def evaluate(self, engine):
        """Evaluate left, handle fail by evaluating right."""
        # Hold allow_failures context while evaluating left
        # This means: if left fails, send the fail to us instead of propagating
        with engine.allow_failures():
            left_value = yield self.left
        # Context dropped - we've received the result (fail or not)
        
        # If left succeeded, return it
        if not engine.is_fail(left_value):
            return left_value
        
        # Left failed - evaluate right and return it
        # No allow_failures context here - if right fails, propagate normally
        right_value = yield self.right
        return right_value
    
    def unparse(self) -> str:
        """Convert back to source code."""
        return f"({self.left.unparse()} ?? {self.right.unparse()})"
    
    def __repr__(self):
        return f"FallbackOp({self.left}, {self.right})"
