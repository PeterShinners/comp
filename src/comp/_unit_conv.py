"""Lightweight unit conversion table for Comp numeric units.

Conversions are expressed as (factor, offset) pairs where:
    result = input * factor + offset

Each family has a designated base unit. For chains (A → C via A → base → C),
the convert_rational() function composes two table lookups automatically.

All factors and offsets are stored as (n, d) reduced-integer rational pairs so
that unit conversion is exact pure-integer arithmetic with no floating-point or
string intermediaries.  Irrational conversions (degree ↔ radian) are stored as
high-precision rational approximations — these are inherently inexact.

This is intentionally hardcoded and non-extensible for the first implementation.
Custom unit families should be added here when needed.
"""

__all__ = ["convert_rational"]

import fractions
import math
import comp


# ---------------------------------------------------------------------------
# Conversion table: (from_qualified, to_qualified) -> (fn, fd, on, od)
#   factor = fn/fd,  offset = on/od
#   result = value * (fn/fd) + (on/od)
#
# All values are exact rationals derived from SI definitions.
# Approximations (π-based angle conversions) are noted inline.
# ---------------------------------------------------------------------------

def _entry(factor_str, offset_n=0, offset_d=1):
    """Build a table entry (fn, fd, on, od) from a fraction string and optional offset."""
    f = fractions.Fraction(factor_str)
    return (f.numerator, f.denominator, offset_n, offset_d)


_TABLE = {
    # ---- Length (base: measure.length.meter) ----
    # 1 inch = 2.54 cm = 0.0254 m  (exact by SI definition)
    # 1 foot = 12 inches = 0.3048 m  (exact by SI definition)
    # 1 mile = 1609.344 m  (exact by SI definition)
    ("measure.length.meter",      "measure.length.centimeter"): (100, 1,    0, 1),
    ("measure.length.centimeter", "measure.length.meter"):      (1,   100,  0, 1),
    ("measure.length.meter",      "measure.length.kilometer"):  (1,   1000, 0, 1),
    ("measure.length.kilometer",  "measure.length.meter"):      (1000, 1,   0, 1),
    ("measure.length.meter",      "measure.length.foot"):       _entry("10000/3048"),   # = 1250/381
    ("measure.length.foot",       "measure.length.meter"):      _entry("3048/10000"),   # = 381/1250
    ("measure.length.meter",      "measure.length.inch"):       _entry("10000/254"),    # = 5000/127
    ("measure.length.inch",       "measure.length.meter"):      _entry("254/10000"),    # = 127/5000
    ("measure.length.meter",      "measure.length.mile"):       _entry("1000/1609344"), # = 125/201168
    ("measure.length.mile",       "measure.length.meter"):      _entry("1609344/1000"), # = 201168/125

    # ---- Time (base: measure.time.second) ----
    ("measure.time.second",      "measure.time.millisecond"): (1000, 1,    0, 1),
    ("measure.time.millisecond", "measure.time.second"):      (1,    1000, 0, 1),
    ("measure.time.second",      "measure.time.minute"):      (1,    60,   0, 1),
    ("measure.time.minute",      "measure.time.second"):      (60,   1,    0, 1),
    ("measure.time.second",      "measure.time.hour"):        (1,    3600, 0, 1),
    ("measure.time.hour",        "measure.time.second"):      (3600, 1,    0, 1),

    # ---- Temperature (base: measure.temperature.celsius) ----
    # 1°C → °F: result = value * 9/5 + 32
    # 1°F → °C: result = value * 5/9 - 160/9
    # 1°C → K:  result = value + 27315/100
    ("measure.temperature.celsius",    "measure.temperature.fahrenheit"): (9,  5, 32,    1),
    ("measure.temperature.fahrenheit", "measure.temperature.celsius"):    (5,  9, -160,  9),
    ("measure.temperature.celsius",    "measure.temperature.kelvin"):     (1,  1, 27315, 100),
    ("measure.temperature.kelvin",     "measure.temperature.celsius"):    (1,  1, -27315, 100),

    # ---- Mass (base: measure.mass.gram) ----
    # 1 lb = 453.59237 g exactly (SI definition: 45359237/100000)
    # 1 oz = 1/16 lb = 45359237/1600000 g
    ("measure.mass.gram",     "measure.mass.kilogram"): (1,        1000,      0, 1),
    ("measure.mass.kilogram", "measure.mass.gram"):     (1000,     1,         0, 1),
    ("measure.mass.gram",     "measure.mass.pound"):    _entry("100000/45359237"),
    ("measure.mass.pound",    "measure.mass.gram"):     (45359237, 100000,    0, 1),
    ("measure.mass.gram",     "measure.mass.ounce"):    _entry("1600000/45359237"),
    ("measure.mass.ounce",    "measure.mass.gram"):     (45359237, 1600000,   0, 1),

    # ---- Angle (base: measure.angle.degrees) ----
    # π is irrational — these are high-precision rational approximations.
    # π/180 ≈ 0.01745329251994329576923...  (20 sig figs)
    # 180/π ≈ 57.2957795130823208767...
    ("measure.angle.degrees", "measure.angle.radians"): _entry("17453292519943295769/1000000000000000000000"),
    ("measure.angle.radians", "measure.angle.degrees"): _entry("5729577951308232522/100000000000000000"),
}

# Base unit for each family (used for chained conversions)
_BASE = {
    "measure.length":      "measure.length.meter",
    "measure.time":        "measure.time.second",
    "measure.temperature": "measure.temperature.celsius",
    "measure.mass":        "measure.mass.gram",
    "measure.angle":       "measure.angle.degrees",
}


def _family(qualified):
    """Return the family prefix for a unit qualified name (all but last segment)."""
    parts = qualified.split(".")
    if len(parts) < 2:
        return None
    return ".".join(parts[:-1])


def _apply_rational(vn, vd, fn, fd, on, od):
    """Apply (factor, offset) to a rational value, returning a reduced rational.

    result = (vn/vd) * (fn/fd) + (on/od)
           = (vn*fn*od + on*vd*fd) / (vd*fd*od)
    """
    n = vn * fn * od + on * vd * fd
    d = vd * fd * od
    if d < 0:
        n, d = -n, -d
    g = math.gcd(n if n >= 0 else -n, d)
    return (n // g, d // g)


def convert_rational(vn, vd, from_unit, to_unit):
    """Convert a rational value from one unit to another.

    Args:
        vn: (int) Numerator of the value
        vd: (int) Denominator of the value
        from_unit: (Tag) Source unit tag
        to_unit:   (Tag) Target unit tag

    Returns:
        (tuple) Reduced (n, d) rational result

    Raises:
        comp.EvalError: If conversion is not possible
    """
    from_q = from_unit.qualified
    to_q = to_unit.qualified

    if from_q == to_q:
        g = math.gcd(vn if vn >= 0 else -vn, vd)
        return (vn // g, vd // g)

    from_family = _family(from_q)
    to_family = _family(to_q)

    if from_family != to_family:
        raise comp.EvalError(
            f"Cannot convert between different unit families: "
            f"[{from_q}] (family: {from_family}) and [{to_q}] (family: {to_family})"
        )

    key = (from_q, to_q)
    if key in _TABLE:
        fn, fd, on, od = _TABLE[key]
        return _apply_rational(vn, vd, fn, fd, on, od)

    # Chain through base unit
    base = _BASE.get(from_family)
    if base is None:
        raise comp.EvalError(
            f"No conversion path for [{from_q}] to [{to_q}]: "
            f"family '{from_family}' has no registered base unit"
        )

    key_to_base = (from_q, base)
    key_from_base = (base, to_q)

    if key_to_base not in _TABLE or key_from_base not in _TABLE:
        raise comp.EvalError(
            f"No conversion path for [{from_q}] to [{to_q}] "
            f"(tried chaining through [{base}])"
        )

    fn1, fd1, on1, od1 = _TABLE[key_to_base]
    fn2, fd2, on2, od2 = _TABLE[key_from_base]

    # Compose: intermediate = v * f1 + o1,  result = intermediate * f2 + o2
    # composed factor = f1 * f2,  composed offset = o1 * f2 + o2
    cfn = fn1 * fn2
    cfd = fd1 * fd2
    con = on1 * fn2 * od2 + on2 * od1 * fd2
    cod = od1 * fd2 * od2
    return _apply_rational(vn, vd, cfn, cfd, con, cod)


def _family(qualified):
    """Return the family prefix for a unit qualified name (all but last segment)."""
    parts = qualified.split(".")
    if len(parts) < 2:
        return None
    return ".".join(parts[:-1])


def _apply(value, factor, offset):
    """Apply a (factor, offset) conversion: result = value * factor + offset."""
    # Ensure value is Decimal for consistent arithmetic
    if not isinstance(value, decimal.Decimal):
        value = decimal.Decimal(str(value))
    return value * factor + offset


def convert(value, from_unit, to_unit):
    """Convert a numeric value from one unit to another.

    Tries a direct table lookup first. If not found, attempts to chain
    through the family's base unit (from → base → to).

    Args:
        value: (Decimal | Fraction | int | float) Numeric value to convert
        from_unit: (Tag) Source unit tag
        to_unit: (Tag) Target unit tag

    Returns:
        (Decimal) Converted value

    Raises:
        comp.EvalError: If conversion is not possible (different families or unknown units)
    """
    from_q = from_unit.qualified
    to_q = to_unit.qualified

    if from_q == to_q:
        # Same unit — no conversion needed
        if not isinstance(value, decimal.Decimal):
            value = decimal.Decimal(str(value))
        return value

    # Check unit families
    from_family = _family(from_q)
    to_family = _family(to_q)

    if from_family != to_family:
        raise comp.EvalError(
            f"Cannot convert between different unit families: "
            f"[{from_q}] (family: {from_family}) and [{to_q}] (family: {to_family})"
        )

    # Direct lookup
    key = (from_q, to_q)
    if key in _TABLE:
        factor, offset = _TABLE[key]
        return _apply(value, factor, offset)

    # Chain through base unit
    base = _BASE.get(from_family)
    if base is None:
        raise comp.EvalError(
            f"No conversion path for [{from_q}] to [{to_q}]: "
            f"family '{from_family}' has no registered base unit"
        )

    key_to_base = (from_q, base)
    key_from_base = (base, to_q)

    if key_to_base not in _TABLE or key_from_base not in _TABLE:
        raise comp.EvalError(
            f"No conversion path for [{from_q}] to [{to_q}] "
            f"(tried chaining through [{base}])"
        )

    factor1, offset1 = _TABLE[key_to_base]
    factor2, offset2 = _TABLE[key_from_base]

    # Chain: value → base → target
    intermediate = _apply(value, factor1, offset1)
    return _apply(intermediate, factor2, offset2)
