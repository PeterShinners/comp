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
    # Unwrap single-field structs (e.g., from parenthesized expressions)
    left = left.as_scalar()
    right = right.as_scalar()

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
    # Unwrap single-field structs (e.g., from parenthesized expressions)
    right = right.as_scalar()

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

    All types are comparable with any type using total ordering.

    Args:
        op: (str) Operator like "==" "!=" "<" "<=" ">" ">="
        left: (Value) Left value
        right: (Value) Right value

    Returns:
        (Value) true or false tag
    """
    cmp = _compare(left, right)
    result = False
    match op:
        case "==":
            result = cmp == 0
        case "!=":
            result = cmp != 0
        case "<":
            result = cmp < 0
        case "<=":
            result = cmp <= 0
        case ">":
            result = cmp > 0
        case ">=":
            result = cmp >= 0
        case _:
            raise ValueError(f"Unknown comparison operator: {op}")

    if result:
        return comp.Value(comp.tag_true)
    return comp.Value(comp.tag_false)


def _compare(left, right):
    """Compare two Values using total ordering.

    Type ordering: {} < false < true < other tags < numbers < text < non-empty structs

    Args:
        left: (Value) Left value
        right: (Value) Right value

    Returns:
        (int) -1 if left < right, 0 if equal, 1 if left > right
    """
    lval = left.data
    rval = right.data

    # Identity check
    if lval is rval:
        return 0

    lshape = left.shape
    rshape = right.shape

    # Different type priorities
    lpri = _type_priority(left)
    rpri = _type_priority(right)
    if lpri != rpri:
        return -1 if lpri < rpri else 1

    # Same type - compare within type
    if lshape is comp.shape_num:
        if lval < rval:
            return -1
        if lval > rval:
            return 1
        return 0

    if lshape is comp.shape_text:
        if lval < rval:
            return -1
        if lval > rval:
            return 1
        return 0

    if lshape is comp.shape_tag:
        # Tags compare by qualified name
        if lval.qualified < rval.qualified:
            return -1
        if lval.qualified > rval.qualified:
            return 1
        return 0

    if lshape is comp.shape_struct:
        return _compare_struct(left, right)

    # Fallback for unknown types
    return 0


def _type_priority(value):
    """Return type priority for total ordering.

    Order: empty struct < false < true < other tags < numbers < text < non-empty structs

    Args:
        value: (Value) Value to get priority for

    Returns:
        (int) Priority number (lower = comes first)
    """
    shape = value.shape

    if shape is comp.shape_struct:
        if len(value.data) == 0:
            return 0  # Empty struct first
        return 6  # Non-empty structs last

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

    return 7  # Unknown


def _compare_struct(left, right):
    """Compare two structs field by field.

    Comparison rules:
    - Compare fields in iteration order
    - Unnamed fields sort before named fields
    - For named fields, compare by field name first, then value
    - Shorter struct is less if all compared fields are equal

    Args:
        left: (Value) Left struct
        right: (Value) Right struct

    Returns:
        (int) -1 if left < right, 0 if equal, 1 if left > right
    """
    ldata = left.data
    rdata = right.data

    litems = list(ldata.items())
    ritems = list(rdata.items())

    for i in range(max(len(litems), len(ritems))):
        # If one ran out, shorter is less
        if i >= len(litems):
            return -1
        if i >= len(ritems):
            return 1

        lkey, lval = litems[i]
        rkey, rval = ritems[i]

        # Compare key types: unnamed < named
        l_unnamed = isinstance(lkey, comp.Unnamed)
        r_unnamed = isinstance(rkey, comp.Unnamed)

        if l_unnamed and not r_unnamed:
            return -1  # Unnamed comes before named
        if not l_unnamed and r_unnamed:
            return 1   # Named comes after unnamed

        # Both named: compare field names
        if not l_unnamed:
            # Keys are Values containing field names
            key_cmp = _compare(lkey, rkey)
            if key_cmp != 0:
                return key_cmp

        # Compare values
        val_cmp = _compare(lval, rval)
        if val_cmp != 0:
            return val_cmp

    # All fields equal and same length
    return 0


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
