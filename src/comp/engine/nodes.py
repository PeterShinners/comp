"""AST nodes with generator-based evaluation.

Each node has an evaluate(ctx) method that returns a generator.
The generator yields child expressions to evaluate and receives
their values, then returns the final result.
"""

from typing import Generator, Any
from .value import Value, TRUE, FALSE


class ASTNode:
    """Base class for AST nodes."""
    
    def evaluate(self, ctx) -> Generator[Any, Value, Value]:
        """Evaluate this node using generator protocol.
        
        Yields: Child AST nodes to evaluate
        Receives: Values from evaluated children
        Returns: Final computed Value
        
        Args:
            ctx: EvalContext managing execution
            
        Returns:
            Generator that yields children and returns result
        """
        raise NotImplementedError(f"{self.__class__.__name__}.evaluate() not implemented")


class Number(ASTNode):
    """Numeric literal - evaluates to itself."""
    
    def __init__(self, value: int | float):
        self.value = value
    
    def evaluate(self, ctx):
        """Number literals don't yield - they just return their value."""
        # This is a degenerate generator - doesn't yield anything
        return Value(self.value)
        yield  # Make this a generator (unreachable, but required by Python)
    
    def __repr__(self):
        return f"Number({self.value})"


class String(ASTNode):
    """String literal - evaluates to itself."""
    
    def __init__(self, value: str):
        self.value = value
    
    def evaluate(self, ctx):
        """String literals don't yield - they just return their value."""
        return Value(self.value)
        yield  # Make this a generator
    
    def __repr__(self):
        return f"String({self.value!r})"


class UnaryOp(ASTNode):
    """Unary operation: -x, !x, etc."""
    
    def __init__(self, op: str, operand: ASTNode):
        self.op = op
        self.operand = operand
    
    def evaluate(self, ctx):
        """Evaluate operand, then apply unary operator."""
        # Yield child expression, receive evaluated value
        operand_value = yield self.operand
        
        # Apply operator
        if self.op == "-":
            # Negation
            if operand_value.is_number:
                return Value(-operand_value.data)
            else:
                return ctx.fail_value(
                    f"Cannot negate non-number: {operand_value.data}",
                    ctx.fail_type
                )
        
        elif self.op == "!":
            # Logical NOT
            if operand_value.tag == TRUE:
                return Value(FALSE, tag=FALSE)
            elif operand_value.tag == FALSE:
                return Value(TRUE, tag=TRUE)
            else:
                return ctx.fail_value(
                    f"Cannot apply ! to non-boolean: {operand_value}",
                    ctx.fail_type
                )
        
        else:
            return ctx.fail_value(f"Unknown unary operator: {self.op}")
    
    def __repr__(self):
        return f"UnaryOp({self.op!r}, {self.operand})"


class BinaryOp(ASTNode):
    """Binary operation: x + y, x == y, etc."""
    
    def __init__(self, op: str, left: ASTNode, right: ASTNode):
        self.op = op
        self.left = left
        self.right = right
    
    def evaluate(self, ctx):
        """Evaluate operands, then apply binary operator.
        
        Note: No manual skip checking! If either operand yields a skip value
        (like a failure), the context will short-circuit and this generator
        will be abandoned.
        """
        # Special case: short-circuit boolean operators
        if self.op in ("&&", "||"):
            left_value = yield self.left
            
            if self.op == "&&":
                # AND: if left is false, return left (don't evaluate right)
                if left_value.tag == FALSE:
                    return left_value
                # Left is true, return right
                right_value = yield self.right
                return right_value
            
            else:  # "||"
                # OR: if left is true, return left (don't evaluate right)
                if left_value.tag == TRUE:
                    return left_value
                # Left is false, return right
                right_value = yield self.right
                return right_value
        
        # All other operators need both operands
        left_value = yield self.left
        right_value = yield self.right
        
        # Arithmetic operators
        if self.op in ("+", "-", "*", "/"):
            if not (left_value.is_number and right_value.is_number):
                return ctx.fail_value(
                    f"Arithmetic requires numbers, got {left_value.data} {self.op} {right_value.data}",
                    ctx.fail_type
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
                    return ctx.fail_value("Division by zero", ctx.fail_type)
                return Value(left_num / right_num)
        
        # Comparison operators
        elif self.op in ("==", "!=", "<", "<=", ">", ">="):
            if self.op == "==":
                result = left_value.data == right_value.data
                return Value(TRUE if result else FALSE, tag=TRUE if result else FALSE)
            elif self.op == "!=":
                result = left_value.data != right_value.data
                return Value(TRUE if result else FALSE, tag=TRUE if result else FALSE)
            
            # Ordering operators - require same type and comparable
            if not (left_value.is_number and right_value.is_number):
                return ctx.fail_value(
                    f"Comparison requires numbers, got {left_value.data} vs {right_value.data}",
                    ctx.fail_type
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
        
        else:
            return ctx.fail_value(f"Unknown binary operator: {self.op}")
    
    def __repr__(self):
        return f"BinaryOp({self.left}, {self.op!r}, {self.right})"
