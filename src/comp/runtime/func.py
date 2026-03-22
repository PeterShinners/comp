"""Effectful Python functions callable via py.call from Comp.

These functions take plain Python objects and may produce side effects
(I/O, mutation, etc.).  They are callable via py.call from Comp code.

Unlike comp.runtime.pure, this module is NOT in the pure-call allowlist
and functions here cannot be used inside !pure definitions.

Note on output formatting
-------------------------
Functions here receive values already converted from Comp to Python by the
py.call mechanism, so they print Python's representation rather than Comp's
literal format (e.g. a struct prints as a Python dict, not ``{a=1 b=2}``).
For Comp-formatted output use the built-in ``output`` internal callable.
"""

import sys


def output(value):
    """Print a Python value to stdout and return it.

    Args:
        value: The Python object to print.

    Returns:
        The input value, unchanged.
    """
    print(value)
    return value


def output_err(value):
    """Print a Python value to stderr and return it.

    Args:
        value: The Python object to print.

    Returns:
        The input value, unchanged.
    """
    print(value, file=sys.stderr)
    return value
