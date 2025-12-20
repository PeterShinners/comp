"""Perform builtin operations on Values.

These will raise Python exceptions for now.
(That may be the wrong design, fail values probably better longer term)

There is generally a function here for each of the cop operator nodes
"""

__all__ = [
    "math_binary",
    "math_unary",
    "compare",
    "logic_binary",
    "logic_unary",
]

import decimal
import fractions
import comp


def math_binary(op, left, right):
    """Math binary operation.

    This only works with numeric types.

    Args:
        op: (str) Operator like "+" "-" "/" "*" "**"
        left: (Value) Left value
        right: (Value) Right value

    Returns:
        (Value) Result of operation

    Raises:
        TypeError: If operands are not numeric
        ZeroDivisionError: If dividing by zero
    """
    if left.shape != comp.shape_num:
        raise TypeError(f"Left operand is not a number: {left.format()}")
    if right.shape != comp.shape_num:
        raise TypeError(f"Right operand is not a number: {right.format()}")

    # Try to leave this flexible between Fraction or Decimal as I'm unsure
    # which road is best.
    lval = left.data
    rval = right.data

    # In the future this must look at the unit attached to the number types
    # Doing possible conversions between them. For now a number is a number.

    if op == "+":
        result = lval + rval
    elif op == "-":
        result = lval - rval
    elif op == "*":
        result = lval * rval
    elif op == "/":
        result = lval / rval  # ZeroDivisionError may appear
    else:
        raise ValueError(f"Unknown math binary operator: {op}")

    return comp.Value(result)


def math_unary(op, right):
    """Math unary operation.

    This only works with numeric types.

    Args:
        op: (str) Operator like "+" "-"
        right: (Value) Right value

    Returns:
        (Value) Result of operation

    Raises:
        TypeError: If operand is not numeric
    """
    if right.shape != comp.shape_num:
        raise TypeError(f"Right operand is not a number: {right.format()}")

    # Try to leave this flexible between Fraction or Decimal as I'm unsure
    # which road is best.
    rval = right.data
    if op == "+":
        return right  # Unary + is a no-op
    if op == "-":
        if isinstance(rval, decimal.Decimal):
            # Decimal unary- munges based on precision, this is lossless
            nval = rval.copy_negate()
        else:
            nval = -rval
        return comp.Value(nval)
    else:
        raise ValueError(f"Unknown math unary operator: {op}")


def logic_binary(op, left, right):
    """Logic binary operation.

    This only works with boolean types.

    Args:
        op: (str) Operator like "&&" "||"
        left: (Value) Left value
        right: (Value) Right value

    Returns:
        (Value) Result of operation
    """
    if left.shape not in (comp.tag_true, comp.tag_false):
        raise TypeError(f"Left operand is not a boolean: {left.format()}")
    if right.shape not in (comp.tag_true, comp.tag_false):
        raise TypeError(f"Right operand is not a boolean: {right.format()}")

    # This may not be possible here as the code is intended to short
    # circuit. Which means the right value can't be evaluated as an arg.
    # but the logic for that is simple enough I suppose it won't need
    # this. Leave this helper in place for completeness. This also should be
    # doing type checking and other validations.
    lval = left.data is comp.tag_true
    rval = right.data is comp.tag_true

    if op == "&&":
        if rval and lval:
            return comp.Value(comp.tag_true)
        return comp.Value(comp.tag_false)
    elif op == "||":
        if rval or lval:
            return comp.Value(comp.tag_true)
        return comp.Value(comp.tag_false)
    else:
        raise ValueError(f"Unknown logic binary operator: {op}")


def logic_unary(op, right):
    """Logic unary operation.

    This only works with boolean types.

    Args:
        op: (str) Operator like "!!"
        right: (Value) Right value

    Returns:
        (Value) Result of operation
    """
    if right.shape not in (comp.tag_true, comp.tag_false):
        raise TypeError(f"Unary operand is not a boolean: {right.format()}")

    rval = right.data is comp.tag_true

    if op == "!!":
        if rval:
            return comp.Value(comp.tag_true)
        return comp.Value(comp.tag_false)
    else:
        raise ValueError(f"Unknown logic unary operator: {op}")


def compare(op, left, right):
    """Comparison operation.

    All types are comparable with any type.

    Args:
        op: (str) Operator like "==" "!=" "<" "<=" ">" ">="
        left: (Value) Left value
        right: (Value) Right value

    Returns:
        (Value) true or false tag
    """
    match op:
        case "==":
            if _equal(left, right):
                return comp.Value(comp.tag_true)
            return comp.Value(comp.tag_false)
        case "!=":
            if not _equal(left, right):
                return comp.Value(comp.tag_true)
            return comp.Value(comp.tag_false)
        case "<" | "<=" | ">" | ">=":
            if _equal(left, right):
                return op in ("<=", ">=")
            if op in ("<", "<="):
                return _lessthan(left, right)
            return _lessthan(right, left)

    raise ValueError(f"Unknown comparison operator: {op}")


def _equal(left, right):
    """Helper for equality comparison of two Values.

    Args:
        left: (Value) Left value
        right: (Value) Right value

    Returns:
        (bool) True if values are equal
    """
    lval = left.data
    rval = right.data
    if lval is rval:
        return True

    lshape = left.shape
    rshape = right.shape
    if lshape != rshape:
        return False

    if lshape is not comp.shape_struct:
        # For non-struct values, use standard Python equality
        return lval == rval

    # Recurse through structs
    if len(lval) != len(rval):
        return False

    lnamed = {}
    lunnamed = []
    for key, value in lval.items():
        if isinstance(key, comp.Unnamed):
            lunnamed.append(value)
        else:
            lnamed[key.data] = value
    rnamed = {}
    runnamed = []
    for key, value in rval.items():
        if isinstance(key, comp.Unnamed):
            runnamed.append(value)
        else:
            rnamed[key.data] = value

    if len(lnamed) != len(rnamed):
        return False

    for l, r in zip(lunnamed, runnamed):
        if not _equal(l, r):
            return False

    # This ain't great, there are field names that aren't python hashable
    for k, l in lnamed.items():
        r = rnamed.get(k)
        if r is None:
            return False
        if not _equal(l, r):
            return False

    return True


def _lessthan(left, right):
    """Helper for sorted comparison.

    Args:
        left: (Value) Left value
        right: (Value) Right value

    Returns:
        (bool) True if left is less than right
    """
    # Results on _equal values is undefined

    lval = left.data
    rval = right.data
    if lval is rval:
        return False

    lshape = left.shape
    rshape = right.shape
    if lshape != rshape:
        return _typeorder(left) < _typeorder(right)

    if lshape is comp.shape_tag:
        return lval.qualified < rval.qualified

    if lshape is not comp.shape_struct:
        return lval < rval

    # structs compare ordered field by field my field name first
    for (lkey, lvalue), (rkey, rvalue) in zip(lval.items(), rval.items()):
        if isinstance(lkey, comp.Unnamed) and not isinstance(rkey, comp.Unnamed):
            return True
        if isinstance(rkey, comp.Unnamed):
            return False
        if not _equal(lkey, rkey):
            return _lessthan(lkey, rkey)
        if not _equal(lvalue, rvalue):
            return _lessthan(lvalue, rvalue)

    # if let is subset of right (and everything else matched)
    return len(lval) < len(rval)


def _typeorder(value):
    """Return number describing sort order for mixed type comparisons.

    Args:
        value: (Value) Value to get type order for

    Returns:
        (int) Sort order number
    """
    shape = value.shape
    if shape is comp.shape_struct:
        # Struct order based on field count (empty or not)
        if len(value.data) == 0:
            return 0
        return 6
    if shape is comp.tag_false:
        return 1
    if shape is comp.tag_true:
        return 2
    if shape is comp.shape_tag:
        return 3
    if shape is comp.shape_num:
        return 4
    if shape is comp.shape_text:
        return 5

    return 7  # Unexpected or unknown type
