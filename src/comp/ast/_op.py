"""Nodes for arithmetic, comparison, and boolean ops."""

__all__ = ["UnaryOp", "ArithmeticOp", "ComparisonOp", "BooleanOp", "FallbackOp"]

import comp
from . import _base


class UnaryOp(_base.ValueNode):
    """Unary operation: -x, !x, etc."""

    def __init__(self, op: str, operand: _base.ValueNode):
        if not isinstance(op, str):
            raise TypeError(f"UnaryOp op must be str, got {type(op)}")
        if not isinstance(operand, _base.ValueNode):
            raise TypeError(f"UnaryOp operand must be _base.ValueNode, got {type(operand)}")

        self.op = op
        self.operand = operand

    def evaluate(self, frame):
        operand_value = yield comp.Compute(self.operand)
        operand_value = operand_value.as_scalar()

        if self.op == "-":
            if operand_value.is_number:
                return comp.Value(-operand_value.data)
            else:
                return comp.fail(f"Cannot negate non-number: {operand_value.data}")

        elif self.op == "!!":
            if operand_value.tag == comp.TRUE:
                return comp.Value(False, tag=comp.FALSE)
            elif operand_value.tag == comp.FALSE:
                return comp.Value(True, tag=comp.TRUE)
            else:
                return comp.fail(f"Cannot apply !! to non-boolean: {operand_value}")

        else:
            return comp.fail(f"Unknown unary operator: {self.op}")

    def unparse(self) -> str:
        return f"{self.op}{self.operand.unparse()}"

    def __repr__(self):
        return f"UnaryOp({self.op!r}, {self.operand})"


class ArithmeticOp(_base.ValueNode):
    """Arithmetic operation: x + y, x - y, x * y, x / y.

    Both operands must be numbers.
    Always evaluates both operands (no short-circuiting).
    """

    def __init__(self, op: str, left: _base.ValueNode, right: _base.ValueNode):
        if op not in ("+", "-", "*", "/"):
            raise ValueError(f"ArithmeticOp requires +, -, *, or /, got {op!r}")
        if not isinstance(left, _base.ValueNode):
            raise TypeError(f"ArithmeticOp left must be _base.ValueNode, got {type(left)}")
        if not isinstance(right, _base.ValueNode):
            raise TypeError(f"ArithmeticOp right must be _base.ValueNode, got {type(right)}")

        self.op = op
        self.left = left
        self.right = right

    def evaluate(self, frame):
        left_value = yield comp.Compute(self.left)
        left_value = left_value.as_scalar()
        right_value = yield comp.Compute(self.right)
        right_value = right_value.as_scalar()

        if not (left_value.is_number and right_value.is_number):
            return comp.fail(
                f"Arithmetic requires numbers, got {left_value.data} {self.op} {right_value.data}"
            )

        left_num = left_value.data
        right_num = right_value.data

        if self.op == "+":
            return comp.Value(left_num + right_num)
        elif self.op == "-":
            return comp.Value(left_num - right_num)
        elif self.op == "*":
            return comp.Value(left_num * right_num)
        elif self.op == "/":
            if right_num == 0:
                return comp.fail("Division by zero")
            return comp.Value(left_num / right_num)

    def unparse(self) -> str:
        return f"({self.left.unparse()} {self.op} {self.right.unparse()})"

    def __repr__(self):
        return f"ArithmeticOp({self.op!r}, {self.left}, {self.right})"


class ComparisonOp(_base.ValueNode):
    """Comparison operation: x == y, x != y, x < y, x <= y, x > y, x >= y.

    == and != work on any values.
    <, <=, >, >= require numbers.
    Always evaluates both operands (no short-circuiting).
    Returns boolean (comp.TRUE/comp.FALSE tag).
    """

    def __init__(self, op: str, left: _base.ValueNode, right: _base.ValueNode):
        if op not in ("==", "!=", "<", "<=", ">", ">="):
            raise ValueError(f"ComparisonOp requires ==, !=, <, <=, >, or >=, got {op!r}")
        if not isinstance(left, _base.ValueNode):
            raise TypeError(f"ComparisonOp left must be _base.ValueNode, got {type(left)}")
        if not isinstance(right, _base.ValueNode):
            raise TypeError(f"ComparisonOp right must be _base.ValueNode, got {type(right)}")

        self.op = op
        self.left = left
        self.right = right

    def evaluate(self, frame):
        left_value = yield comp.Compute(self.left)
        left_value = left_value.as_scalar()
        right_value = yield comp.Compute(self.right)
        right_value = right_value.as_scalar()

        # Equality comparisons work on any values
        if self.op == "==":
            result = left_value.data == right_value.data
            return comp.Value(True if result else False, tag=comp.TRUE if result else comp.FALSE)
        elif self.op == "!=":
            result = left_value.data != right_value.data
            return comp.Value(True if result else False, tag=comp.TRUE if result else comp.FALSE)

        # Ordering comparisons require numbers
        if not (left_value.is_number and right_value.is_number):
            return comp.fail(
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

        return comp.Value(True if result else False, tag=comp.TRUE if result else comp.FALSE)

    def unparse(self) -> str:
        return f"({self.left.unparse()} {self.op} {self.right.unparse()})"

    def __repr__(self):
        return f"ComparisonOp({self.op!r}, {self.left}, {self.right})"


class BooleanOp(_base.ValueNode):
    """Boolean operation: x && y, x || y.

    Short-circuits evaluation:
    - && returns left if comp.FALSE, otherwise returns right
    - || returns left if comp.TRUE, otherwise returns right

    Operands should be boolean values (comp.TRUE/comp.FALSE tags), but any value
    can be used - the tag determines truthiness.
    """

    def __init__(self, op: str, left: _base.ValueNode, right: _base.ValueNode):
        if op not in ("&&", "||"):
            raise ValueError(f"BooleanOp requires && or ||, got {op!r}")
        if not isinstance(left, _base.ValueNode):
            raise TypeError(f"BooleanOp left must be _base.ValueNode, got {type(left)}")
        if not isinstance(right, _base.ValueNode):
            raise TypeError(f"BooleanOp right must be _base.ValueNode, got {type(right)}")

        self.op = op
        self.left = left
        self.right = right

    def evaluate(self, frame):
        """Evaluate left operand, short-circuit if possible, else evaluate right."""
        left_value = yield comp.Compute(self.left)
        left_value = left_value.as_scalar()

        if self.op == "&&":
            # Short-circuit: if left is comp.FALSE, return it without evaluating right
            if left_value.tag == comp.FALSE:
                return left_value
            # Otherwise evaluate and return right
            right_value = yield comp.Compute(self.right)
            right_value = right_value.as_scalar()
            return right_value

        else:  # "||"
            # Short-circuit: if left is comp.TRUE, return it without evaluating right
            if left_value.tag == comp.TRUE:
                return left_value
            # Otherwise evaluate and return right
            right_value = yield comp.Compute(self.right)
            right_value = right_value.as_scalar()
            return right_value

    def unparse(self) -> str:
        return f"({self.left.unparse()} {self.op} {self.right.unparse()})"

    def __repr__(self):
        return f"BooleanOp({self.op!r}, {self.left}, {self.right})"


class FallbackOp(_base.ValueNode):
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

    def __init__(self, left: _base.ValueNode, right: _base.ValueNode):
        if not isinstance(left, _base.ValueNode):
            raise TypeError(f"FallbackOp left must be _base.ValueNode, got {type(left)}")
        if not isinstance(right, _base.ValueNode):
            raise TypeError(f"FallbackOp right must be _base.ValueNode, got {type(right)}")

        self.left = left
        self.right = right

    def evaluate(self, frame):
        # allow_failures while evaluating left
        left_value = yield comp.Compute(self.left, allow_failures=True)

        # If left succeeded, return it
        if not frame.is_fail(left_value):
            return left_value

        # Left failed - evaluate right and return it
        # No allow_failures context here - if right fails, propagate normally
        right_value = yield comp.Compute(self.right)
        return right_value

    def unparse(self) -> str:
        return f"({self.left.unparse()} ?? {self.right.unparse()})"

    def __repr__(self):
        return f"FallbackOp({self.left}, {self.right})"
