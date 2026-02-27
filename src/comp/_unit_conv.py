"""Lightweight unit conversion table for Comp numeric units.

Conversions are expressed as (factor, offset) pairs where:
    result = input * factor + offset

Each family has a designated base unit. For chains (A → C via A → base → C),
the convert() function composes two table lookups automatically.

This is intentionally hardcoded and non-extensible for the first implementation.
Custom unit families should be added here when needed.
"""

__all__ = ["convert"]

import decimal
import comp


# ---------------------------------------------------------------------------
# Conversion table: (from_qualified, to_qualified) -> (factor, offset)
# All factors and offsets are stored as Decimal for precision.
# ---------------------------------------------------------------------------

def _d(x):
    """Convert a numeric literal to Decimal."""
    return decimal.Decimal(str(x))


_TABLE = {
    # ---- Length (base: measure.length.meter) ----
    ("measure.length.meter",      "measure.length.centimeter"): (_d(100),       _d(0)),
    ("measure.length.centimeter", "measure.length.meter"):      (_d("0.01"),     _d(0)),
    ("measure.length.meter",      "measure.length.kilometer"):  (_d("0.001"),    _d(0)),
    ("measure.length.kilometer",  "measure.length.meter"):      (_d(1000),       _d(0)),
    ("measure.length.meter",      "measure.length.foot"):       (_d("3.28084"),  _d(0)),
    ("measure.length.foot",       "measure.length.meter"):      (_d("0.3048"),   _d(0)),
    ("measure.length.meter",      "measure.length.inch"):       (_d("39.3701"),  _d(0)),
    ("measure.length.inch",       "measure.length.meter"):      (_d("0.0254"),   _d(0)),
    ("measure.length.meter",      "measure.length.mile"):       (_d("0.000621371"), _d(0)),
    ("measure.length.mile",       "measure.length.meter"):      (_d("1609.344"), _d(0)),

    # ---- Time (base: measure.time.second) ----
    ("measure.time.second",      "measure.time.millisecond"): (_d(1000),    _d(0)),
    ("measure.time.millisecond", "measure.time.second"):      (_d("0.001"), _d(0)),
    ("measure.time.second",      "measure.time.minute"):      (_d("1") / _d(60),   _d(0)),
    ("measure.time.minute",      "measure.time.second"):      (_d(60),      _d(0)),
    ("measure.time.second",      "measure.time.hour"):        (_d("1") / _d(3600), _d(0)),
    ("measure.time.hour",        "measure.time.second"):      (_d(3600),    _d(0)),

    # ---- Temperature (base: measure.temperature.celsius) ----
    # These have non-zero offsets so chaining is handled specially below.
    # offset computed as factor * (-32) so that convert(32, F, C) == 0 exactly
    ("measure.temperature.celsius",    "measure.temperature.fahrenheit"): (_d("1.8"),        _d(32)),
    ("measure.temperature.fahrenheit", "measure.temperature.celsius"):    (_d("5") / _d(9),  (_d("5") / _d(9)) * _d(-32)),
    ("measure.temperature.celsius",    "measure.temperature.kelvin"):     (_d(1),            _d("273.15")),
    ("measure.temperature.kelvin",     "measure.temperature.celsius"):    (_d(1),            _d("-273.15")),

    # ---- Mass (base: measure.mass.gram) ----
    ("measure.mass.gram",     "measure.mass.kilogram"): (_d("0.001"),      _d(0)),
    ("measure.mass.kilogram", "measure.mass.gram"):     (_d(1000),         _d(0)),
    ("measure.mass.gram",     "measure.mass.pound"):    (_d("0.00220462"), _d(0)),
    ("measure.mass.pound",    "measure.mass.gram"):     (_d("453.59237"),  _d(0)),
    ("measure.mass.gram",     "measure.mass.ounce"):    (_d("0.035274"),   _d(0)),
    ("measure.mass.ounce",    "measure.mass.gram"):     (_d("28.349523"),  _d(0)),
}

# Base unit for each family (used for chained conversions)
_BASE = {
    "measure.length":      "measure.length.meter",
    "measure.time":        "measure.time.second",
    "measure.temperature": "measure.temperature.celsius",
    "measure.mass":        "measure.mass.gram",
}


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
