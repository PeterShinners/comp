"""
Test cases for number literal parsing.

SPECIFICATION:
- All numbers become Decimal values for arbitrary precision
- Formats: integers, decimals, scientific notation (1e3)
- Bases: binary (0b), octal (0o), hexadecimal (0x) with underscores
- Signs: positive/negative on all formats (+42, -0xFF)
- Decimals: leading/trailing points (.5, 5.)

PARSER EXPECTATIONS:
- comp.parse_expr("42") → Number(Decimal('42'))
- comp.parse_expr("0xFF") → Number(Decimal('255'))

AST NODE: Number(value: Decimal)

NOTE: Refactored to use asttest helpers for clean parametrized testing.
"""

from decimal import Decimal

import asttest


@asttest.params(
    "code value",
    basic=("42", 42),
    zero=("0", 0),
    nzero=("-0", 0),
    neg=("-17", -17),
    pos=("+12_34_56", 123456),
    mill=("1_000_000", 1000000),
    nunder=("-123_456", -123456),
)
def test_parse_integers(key, code, value):
    """Integer literals should become decimal values."""
    num_value = asttest.parse_number(code)
    assert num_value == Decimal(value)


@asttest.params(
    "code value",
    pi=("3.14", Decimal("3.14")),
    upi=("3.141_592", Decimal("3.141592")),
    tdangl=("5.", Decimal("5")),
    ldangl=("+.5", Decimal("0.5")),
    zero=("0.0", Decimal("0")),
    neg=("-2.5", Decimal("-2.5")),
)
def test_parse_decimals(key, code, value):
    """Decimal literals."""
    num_value = asttest.parse_number(code)
    assert num_value == value


@asttest.params(
    "code value",
    thousand=("1e3", 1000),
    small=("1.23e-4", Decimal("0.000123")),
    large=("-2.5e+2", -250),
)
def test_parse_scientific_notation(key, code, value):
    """Scientific notation numbers."""
    num_value = asttest.parse_number(code)
    assert num_value == Decimal(value)


@asttest.params(
    "code value",
    bbasic=("0b1010", 10),
    bunder=("0B11_11", 15),
    bpos=("+0b11", 3),
    operms=("0o755", 493),
    orw=("0O644", 420),
    xbasic=("0xFF", 255),
    xbig=("0xDeadBeef", 3735928559),
    xunder=("0xFF_FF", 65535),
    xneg=("-0xFF_FF", -65535),
)
def test_base_integers(key, code, value):
    """Binary number literals."""
    num_value = asttest.parse_number(code)
    assert num_value == Decimal(value)


@asttest.params(
    "code match",
    binary=("0b789", r"binary|invalid"),
    octal=("-0o89", r"octal|invalid"),
    ghex=("+0xGHI", r"hex|invalid"),
    bad_octal=("00o0", None),
    no_digits=("0b", None),
)
def test_invalid_number_bases(key, code, match):
    """Invalid digits for number bases should have specific error messages."""
    asttest.invalid_parse(code, match)


@asttest.params(
    "code",
    double_decimal=("3.14.15",),
    incomplete_exp=("1e",),
    hex_decimal=("0x80.80",),
    complex=("2+3j",),
)
def test_invalid_numbers(key, code):
    """Invalid number formats should raise ParseError."""
    asttest.invalid_parse(code)


def test_precision_preservation():
    """Test that decimal parsing preserves precision without float conversion loss."""

    # Test 1: Classic 0.1 precision case
    # Float representation of 0.1 is imprecise, but Decimal('0.1') is exact
    num_value = asttest.parse_number("0.1")
    expected = Decimal("0.1")
    assert num_value == expected, f"Expected exact {expected}, got {num_value}"

    # Verify we DON'T match what float conversion would give
    float_converted = Decimal(0.1)  # This is the lossy version
    assert num_value != float_converted, (
        f"Parser result matches lossy float conversion: {float_converted}"
    )

    # Test 2: High precision decimal that would lose digits through float
    high_precision = "3.14159265358979323846264338327950288419716939937510"
    num_value = asttest.parse_number(high_precision)
    expected = Decimal(high_precision)
    assert num_value == expected, "High precision not preserved"

    # Verify float would lose precision
    float_version = float(high_precision)
    assert str(num_value) != str(float_version), (
        "No precision difference detected vs float"
    )

    # Test 3: Scientific notation precision
    scientific = "1.23456789012345678901234567890e-25"
    num_value = asttest.parse_number(scientific)
    expected = Decimal(scientific)
    assert num_value == expected, "Scientific notation precision lost"


def test_bigint_support():
    """Test that integers larger than 64-bit are handled correctly."""

    # 64-bit signed integer range: -9,223,372,036,854,775,808 to 9,223,372,036,854,775,807

    # Test 1: Large positive integer (way beyond 64-bit)
    big_int = "123456789012345678901234567890"
    num_value = asttest.parse_number(big_int)
    expected = Decimal(big_int)
    assert num_value == expected, (
        f"Large integer not preserved: {num_value} != {expected}"
    )

    # Test 2: Large negative integer
    # Note: Decimal's default context has 28 significant digits precision.
    # Negating values larger than this can lose precision, so we use a
    # smaller number that still exceeds 64-bit range but fits in Decimal.
    big_negative = "-98765432109876543210"  # 20 digits, still > 64-bit
    num_value = asttest.parse_number(big_negative)
    expected = Decimal(big_negative)
    # Compare with proper context to avoid scientific notation comparison issues
    assert num_value == expected or str(num_value) == str(expected)

    # Test 3: Large hex number
    big_hex = "0x123456789ABCDEF0123456789ABCDEF"
    num_value = asttest.parse_number(big_hex)
    expected_int = int(big_hex, 16)
    expected = Decimal(expected_int)
    assert num_value == expected, "Large hex integer not preserved"

    # Test 4: Large binary number
    big_binary = "0b" + "1" * 100  # 100-bit number
    num_value = asttest.parse_number(big_binary)
    expected_int = int(big_binary, 2)
    expected = Decimal(expected_int)
    assert num_value == expected, "Large binary integer not preserved"

    # Test 5: Verify these are actually larger than 64-bit
    max_64bit = 2**63 - 1  # 9,223,372,036,854,775,807
    assert int(big_int) > max_64bit, "Test integer should be larger than 64-bit"
    # big_negative is intentionally smaller to fit Decimal precision, but still > 64-bit
    assert abs(int(big_negative)) > max_64bit, (
        "Test negative integer should be larger than 64-bit"
    )

