"""Exact rational number type for Comp values.

Numbers are stored as plain (n, d, dp) tuples in canonical reduced form.
Using bare tuples avoids class-allocation overhead while keeping isinstance
checks unambiguous — struct data lives in dicts, so tuple == number.

Tuple layout: (n, d, dp) where
  n:  numerator (int, any sign)
  d:  denominator (int, always > 0, always coprime with n after construction)
  dp: display hint (int)
        0    = no decimal origin  — integer literal or exact rational
        2    = 1 decimal place    — user wrote e.g. "1.9"
        3    = 2 decimal places   — user wrote e.g. "1.55"
        N≥2  = N-1 decimal places (dp=1 is reserved/unused in practice)
"""

__all__ = [
    "num_from_int",
    "num_from_decimal_str",
    "num_add",
    "num_sub",
    "num_mul",
    "num_div",
    "num_neg",
    "num_format",
    "num_to_float",
    "num_is_integer",
    "num_floor_int",
    "_make",
]

import math


def _make(n, d, dp):
    """Create a number tuple in canonical reduced form.

    Args:
        n:  (int) Numerator
        d:  (int) Denominator (must be non-zero; sign is normalised to d > 0)
        dp: (int) Display-places hint

    Returns:
        (tuple) Reduced canonical (n, d, dp)
    """
    if d < 0:
        n, d = -n, -d
    g = math.gcd(n if n >= 0 else -n, d)
    if g > 1:
        n, d = n // g, d // g
    return (n, d, dp)


def num_from_int(n):
    """Create a number tuple from a plain Python int.

    Args:
        n: (int) Integer value

    Returns:
        (tuple)
    """
    return (n, 1, 0)


def num_from_decimal_str(s):
    """Parse a decimal or integer literal string into a number tuple.

    Preserves the number of decimal digits as the dp display hint.

    Args:
        s: (str) Literal string, e.g. "1.55", "42", "0xff".

    Returns:
        (tuple)
    """
    if "." in s:
        dot = s.index(".")
        frac = s[dot + 1:]
        places = len(frac)
        n = int(s[:dot] + frac)
        d = 10 ** places
        g = math.gcd(n if n >= 0 else -n, d)
        return (n // g, d // g, places + 1)
    else:
        if len(s) > 2 and s[1:2].lower() in ("x", "b", "o"):
            n = int(s, 0)
        else:
            n = int(s)
        return (n, 1, 0)


# ---------------------------------------------------------------------------
# Arithmetic  (always produce a new reduced tuple)
# ---------------------------------------------------------------------------

def num_add(a, b):
    """Add two number tuples.

    Args:
        a: (tuple) (n, d, dp)
        b: (tuple) (n, d, dp)

    Returns:
        (tuple) a + b
    """
    an, ad, adp = a
    bn, bd, bdp = b
    n = an * bd + bn * ad
    d = ad * bd
    dp = adp if adp > bdp else bdp
    g = math.gcd(n if n >= 0 else -n, d)
    return (n // g, d // g, dp)


def num_sub(a, b):
    """Subtract two number tuples.

    Args:
        a: (tuple) (n, d, dp)
        b: (tuple) (n, d, dp)

    Returns:
        (tuple) a - b
    """
    an, ad, adp = a
    bn, bd, bdp = b
    n = an * bd - bn * ad
    d = ad * bd
    dp = adp if adp > bdp else bdp
    g = math.gcd(n if n >= 0 else -n, d)
    return (n // g, d // g, dp)


def num_mul(a, b):
    """Multiply two number tuples.

    Args:
        a: (tuple) (n, d, dp)
        b: (tuple) (n, d, dp)

    Returns:
        (tuple) a * b
    """
    an, ad, adp = a
    bn, bd, bdp = b
    n = an * bn
    d = ad * bd
    dp = adp if adp > bdp else bdp
    g = math.gcd(n if n >= 0 else -n, d)
    return (n // g, d // g, dp)


def num_div(a, b):
    """Divide two number tuples.

    Args:
        a: (tuple) (n, d, dp)
        b: (tuple) (n, d, dp)

    Returns:
        (tuple) a / b

    Raises:
        ZeroDivisionError: If b is zero
    """
    an, ad, adp = a
    bn, bd, bdp = b
    if bn == 0:
        raise ZeroDivisionError("division by zero")
    n = an * bd
    d = ad * bn
    if d < 0:
        n, d = -n, -d
    dp = adp if adp > bdp else bdp
    g = math.gcd(n if n >= 0 else -n, d)
    return (n // g, d // g, dp)


def num_neg(a):
    """Negate a number tuple.

    Args:
        a: (tuple) (n, d, dp)

    Returns:
        (tuple) -a
    """
    return (-a[0], a[1], a[2])


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def num_to_float(a):
    """Convert a number tuple to a Python float.

    Args:
        a: (tuple) (n, d, dp)

    Returns:
        (float)
    """
    return a[0] / a[1]


def num_is_integer(a):
    """Return True if the value is a whole number (d == 1).

    Args:
        a: (tuple) (n, d, dp)

    Returns:
        (bool)
    """
    return a[1] == 1


def num_floor_int(a):
    """Return floor(a) as a Python int.

    Args:
        a: (tuple) (n, d, dp)

    Returns:
        (int)
    """
    n, d, _ = a
    if d == 1:
        return n
    q, _ = divmod(n, d)
    return q


def num_format(a):
    """Format a number tuple for display.

    If dp == 0: display as integer (d==1) or fraction notation (d>1).
    If dp >= 2: display with (dp-1) decimal places using float formatting.

    Args:
        a: (tuple) (n, d, dp)

    Returns:
        (str)
    """
    n, d, dp = a
    if dp == 0:
        if d == 1:
            return str(n)
        if n < 0:
            return f"-{-n}/{d}"
        return f"{n}/{d}"
    places = dp - 1
    return f"{n / d:.{places}f}"

