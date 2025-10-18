"""Number and mathematical operations"""

import decimal
import math

import comp


def absolute(frame, input_value: comp.Value, args: comp.Value | None = None):
    """Absolute positive value for number."""
    number, fail = _num(input_value, "|absolute input")
    if fail:
        return fail
    return comp.Value(number.copy_abs())


def floor(frame, input_value: comp.Value, args: comp.Value | None = None):
    """Largest integer less than or equal."""
    number, fail = _num(input_value, "|floor input")
    if fail:
        return fail
    number = number.to_integral_value(rounding=decimal.ROUND_FLOOR)
    return comp.Value(number)


def ceil(frame, input_value: comp.Value, args: comp.Value | None = None):
    """Smallest integer greater than or equal"""
    number, fail = _num(input_value, "|ceil input")
    if fail:
        return fail
    number = number.to_integral_value(rounding=decimal.ROUND_CEILING)
    return comp.Value(number)


def remainder(frame, input_value: comp.Value, args: comp.Value | None = None):
    """Remainder of division."""
    number, fail = _num(input_value, "|remainder input")
    if fail:
        return fail
    divisor, fail = _num(args, "|remainder divisor")
    if fail:
        return fail
    # Decimal % actually gets remainder correct for negatives (not a typical modulo)
    number = number % divisor
    return comp.Value(number)


def _num(value: comp.Value|None, name: str) -> tuple[decimal.Decimal, comp.Value | None]:
    """Convert to decimal or fail."""
    if value is None:
        return decimal.Decimal(0), comp.fail(f"{name} got no number")
    value = value.as_scalar()
    if not value.is_number:
        return decimal.Decimal(0), comp.fail(f"{name} expects number value")

    return value.data, None # type: ignore


def create_module() -> comp.Module:
    """Create the number library module."""
    module = comp.Module()

    # Define all number functions
    functions = (
        absolute,
        floor,
        ceil,
        remainder,
    )

    module.define_tag(["pi"], decimal.Decimal(math.pi))

    for py_func in functions:
        name = py_func.__name__
        if name.endswith("_"):
            name = name[:-1] + "?"
        py_function = comp.PythonFunction(name, py_func)
        module.define_function(
            path=[name],
            body=py_function,
            is_pure=True,  # Number functions are pure
            doc=py_func.__doc__,
        )

    return module
