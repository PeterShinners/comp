"""
Test cases for number literal parsing.

SPECIFICATION:
- All numbers become Decimal values for arbitrary precision
- Formats: integers, decimals, scientific notation (1e3)
- Bases: binary (0b), octal (0o), hexadecimal (0x) with underscores
- Signs: positive/negative on all formats (+42, -0xFF)
- Decimals: leading/trailing points (.5, 5.)

PARSER EXPECTATIONS:
- comp.parse("42") → NumberLiteral(Decimal('42'))
- comp.parse("0xFF") → NumberLiteral(Decimal('255'))

AST NODE: NumberLiteral(value: Decimal)
"""

from decimal import Decimal

import pytest

import comp


@pytest.mark.parametrize("input_text,expected_value", [
    ("42", "42"),
    ("-17", "-17"),
    ("0", "0"),
])
def test_parse_integers(input_text, expected_value):
    """Integer literals should become decimal values."""
    result = comp.parse(input_text)
    _assertNum(result, expected_value)


@pytest.mark.parametrize("input_text,expected_value", [
    ("3.14", "3.14"),
    ("-2.5", "-2.5"),
    ("0.0", "0.0"),
])
def test_parse_decimals(input_text, expected_value):
    """Decimal literals."""
    result = comp.parse(input_text)
    _assertNum(result, expected_value)


@pytest.mark.parametrize("input_text,expected_value", [
    ("1e3", "1000"),
    ("1.23e-4", "0.000123"),
    ("-2.5e+2", "-250"),
])
def test_parse_scientific_notation(input_text, expected_value):
    """Scientific notation numbers."""
    result = comp.parse(input_text)
    _assertNum(result, expected_value)


@pytest.mark.parametrize("input_text,expected_value", [
    ("0b1010", 10),
    ("0B11_11", 15),
])
def test_parse_binary_numbers(input_text, expected_value):
    """Binary number literals."""
    result = comp.parse(input_text)
    _assertNum(result, expected_value)


@pytest.mark.parametrize("input_text,expected_value", [
    ("0o755", 493),
    ("0O644", 420),
])
def test_parse_octal_numbers(input_text, expected_value):
    """Octal number literals."""
    result = comp.parse(input_text)
    _assertNum(result, expected_value)


def test_error_message():
    """Specific information in parse error"""
    with pytest.raises(comp.ParseError, match="invalid.*binary"):
        comp.parse("0b789")
    with pytest.raises(comp.ParseError, match="invalid.*octal"):
        comp.parse("-0o89")
    with pytest.raises(comp.ParseError, match="invalid.*hex"):
        comp.parse("+0xGHI")


@pytest.mark.parametrize("input_text,expected_value", [
    ("0xFF", 255),
    ("0xDeadBeef", 3735928559),
])
def test_parse_hex_numbers(input_text, expected_value):
    """Hexadecimal number literals."""
    result = comp.parse(input_text)
    _assertNum(result, expected_value)


@pytest.mark.parametrize("input_text,expected_value", [
    ("1_000_000", "1000000"),
    ("-0xFF_FF", -65535),
    ("3.141_592", "3.141592"),
    ("-123_456", "-123456"),
    ("+12_34_56", "123456"),
])
def test_underscores(input_text, expected_value):
    """Numbers with underscore separators for readability."""
    result = comp.parse(input_text)
    _assertNum(result, expected_value)


@pytest.mark.parametrize("input_text,expected_value", [
    ("+.5", "0.5"),
    ("5.", "5"),
])
def test_dangling_decimals(input_text, expected_value):
    """Numbers with leading or trailing decimal points."""
    result = comp.parse(input_text)
    _assertNum(result, expected_value)


# @pytest.xfail(reason="TODO: proper error handling for malformed numbers")
# def test_ugly_failure():
#     """should one day have a better error message then "No terminal matches" """
#     with pytest.raises(comp.ParseError):
#         comp.parse("-.")

@pytest.mark.parametrize("input_text", [
    "3.14.15",  # Double decimal
    "1e",  # Incomplete scientific notation
    "0x80.80",  # Decimals not allowed in alternate bases
    "00o0",  # Too many leading zeros
    "0b",  # No actual digits
    "2+3j",  # No Python complex values
])
def test_invalid_numbers(input_text):
    """Invalid number formats should raise ParseError."""
    with pytest.raises(comp.ParseError):
        comp.parse(input_text)


def test_precision_preservation():
    """Test that decimal parsing preserves precision without float conversion loss."""

    # Test 1: Classic 0.1 precision case
    # Float representation of 0.1 is imprecise, but Decimal('0.1') is exact
    result = comp.parse("0.1")
    assert isinstance(result, comp.NumberLiteral)
    expected = Decimal("0.1")
    assert result.value == expected, f"Expected exact {expected}, got {result.value}"

    # Verify we DON'T match what float conversion would give
    float_converted = Decimal(0.1)  # This is the lossy version
    assert result.value != float_converted, (
        f"Parser result matches lossy float conversion: {float_converted}"
    )

    # Test 2: High precision decimal that would lose digits through float
    high_precision = "3.14159265358979323846264338327950288419716939937510"
    result = comp.parse(high_precision)
    assert isinstance(result, comp.NumberLiteral)
    expected = Decimal(high_precision)
    assert result.value == expected, "High precision not preserved"

    # Verify float would lose precision
    float_version = float(high_precision)
    assert str(result.value) != str(float_version), (
        "No precision difference detected vs float"
    )

    # Test 3: Scientific notation precision
    scientific = "1.23456789012345678901234567890e-25"
    result = comp.parse(scientific)
    assert isinstance(result, comp.NumberLiteral)
    expected = Decimal(scientific)
    assert result.value == expected, "Scientific notation precision lost"


def test_bigint_support():
    """Test that integers larger than 64-bit are handled correctly."""

    # 64-bit signed integer range: -9,223,372,036,854,775,808 to 9,223,372,036,854,775,807

    # Test 1: Large positive integer (way beyond 64-bit)
    big_int = "123456789012345678901234567890"
    result = comp.parse(big_int)
    assert isinstance(result, comp.NumberLiteral)
    expected = Decimal(big_int)
    assert result.value == expected, (
        f"Large integer not preserved: {result.value} != {expected}"
    )

    # Test 2: Large negative integer
    big_negative = "-987654321098765432109876543210"
    result = comp.parse(big_negative)
    assert isinstance(result, comp.NumberLiteral)
    expected = Decimal(big_negative)
    assert result.value == expected, "Large negative integer not preserved"

    # Test 3: Large hex number (should go through ast.literal_eval -> int -> Decimal)
    big_hex = "0x123456789ABCDEF0123456789ABCDEF"
    result = comp.parse(big_hex)
    assert isinstance(result, comp.NumberLiteral)
    # Convert manually to check
    expected_int = int(big_hex, 16)
    expected = Decimal(expected_int)
    assert result.value == expected, "Large hex integer not preserved"

    # Test 4: Large binary number
    big_binary = "0b" + "1" * 100  # 100-bit number
    result = comp.parse(big_binary)
    assert isinstance(result, comp.NumberLiteral)
    expected_int = int(big_binary, 2)
    expected = Decimal(expected_int)
    assert result.value == expected, "Large binary integer not preserved"

    # Test 5: Verify these are actually larger than 64-bit
    max_64bit = 2**63 - 1  # 9,223,372,036,854,775,807
    assert int(big_int) > max_64bit, "Test integer should be larger than 64-bit"
    assert abs(int(big_negative)) > max_64bit, (
        "Test negative integer should be larger than 64-bit"
    )


@pytest.mark.parametrize("input_text,expected_value", [
    ("42", 42),
    ("-17", -17),
    ("3.14", "3.14"),
    ("0xFF", 255),
    ("0b1010", 10),
    ("0o755", 493),
    ("1e3", "1000"),
    ("-0xFF", -255),
    ("+0b11", 3),
    ("1_000_000", 1000000),
    ("0xFF_FF", 65535),
    ("3.141_592", "3.141592"),
])
def test_comprehensive_number_formats(input_text, expected_value):
    """Comprehensive test of all supported number formats."""
    result = comp.parse(input_text)
    _assertNum(result, expected_value)


def _assertNum(value, match):
    """Helper to assert a parsed number matches expected Decimal value."""
    assert isinstance(value, comp.NumberLiteral)
    if isinstance(match, str):
        match = Decimal(match)
    assert value.value == match
