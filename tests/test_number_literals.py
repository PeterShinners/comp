"""
Test cases for number literal parsing - Phase 02.

SPECIFICATION SUMMARY:
Number parsing with comprehensive format support including decimal, binary, octal,
hexadecimal, scientific notation, and signed numbers. All numbers become
Decimal values for arbitrary precision.

REQUIREMENTS FROM DESIGN DOCS:
- All numbers become Decimal values
- Support integers, decimals, scientific notation
- Support binary (0b), octal (0o), hexadecimal (0x) with underscores
- Support positive/negative signs on all formats
- Leading/trailing decimal points (.5, 5.)
- Special values (inf, nan) are NOT numbers - they become tags in Phase 03

PARSER EXPECTATIONS:
- comp.parse("42") → NumberLiteral(Decimal('42'))
- comp.parse("0xFF") → NumberLiteral(Decimal('255'))
- comp.parse("+.5") → NumberLiteral(Decimal('0.5'))
- comp.parse("-0b1010") → NumberLiteral(Decimal('-10'))

ERROR CASES TO HANDLE:
- Invalid numbers: "3.14.15", "1e" (incomplete)
- Special values: "inf" (becomes tag in Phase 03)
- Mixed formats: "0x80.80" (decimals not allowed in alternate bases)

AST NODE STRUCTURE:
- NumberLiteral: value (Decimal)
"""

from decimal import Decimal

import pytest

import comp


def test_parse_integers():
    """Integer literals should become decimal values."""
    result = comp.parse("42")
    _assertNum(result, "42")

    result = comp.parse("-17")
    _assertNum(result, -17)
    assert isinstance(result, comp.NumberLiteral)
    assert result.value == -17

    result = comp.parse("0")
    _assertNum(result, 0)


def test_parse_decimals():
    """Decimal literals."""
    result = comp.parse("3.14")
    _assertNum(result, "3.14")

    result = comp.parse("-2.5")
    _assertNum(result, "-2.5")

    result = comp.parse("0.0")
    _assertNum(result, "0.0")


def test_parse_scientific_notation():
    """Scientific notation numbers."""
    result = comp.parse("1e3")
    _assertNum(result, "1000")

    result = comp.parse("1.23e-4")
    _assertNum(result, "0.000123")

    result = comp.parse("-2.5e+2")
    _assertNum(result, "-250")


def test_parse_binary_numbers():
    """Binary number literals."""
    result = comp.parse("0b1010")
    _assertNum(result, 10)

    result = comp.parse("0B11_11")
    _assertNum(result, 15)

    with pytest.raises(comp.ParseError, match="binary"):
        comp.parse("0b789")


def test_parse_octal_numbers():
    """Octal number literals."""
    result = comp.parse("0o755")
    _assertNum(result, 493)

    result = comp.parse("0O644")
    _assertNum(result, 420)

    with pytest.raises(comp.ParseError, match="octal"):
        comp.parse("-0o89")


def test_parse_hex_numbers():
    """Hexadecimal number literals."""
    result = comp.parse("0xFF")
    _assertNum(result, 255)

    result = comp.parse("0xDeadBeef")
    _assertNum(result, 3735928559)

    with pytest.raises(comp.ParseError, match="hexadecimal"):
        comp.parse("+0xGHI")


def test_underscores():
    """Numbers with underscore separators for readability."""
    result = comp.parse("1_000_000")
    _assertNum(result, 1000000)

    result = comp.parse("-0xFF_FF")
    _assertNum(result, -65535)

    result = comp.parse("3.141_592")
    _assertNum(result, "3.141592")

    result = comp.parse("-_2_")
    _assertNum(result, -2)

    result = comp.parse("+_2_._2_")
    _assertNum(result, "2.2")


def test_dangling_decimals():
    """Numbers with leading or trailing decimal points."""
    result = comp.parse("+.5")
    _assertNum(result, "0.5")

    result = comp.parse("5.")
    _assertNum(result, "5")

    with pytest.raises(comp.ParseError):
        # should one day have a better error message then "No terminal matches"
        comp.parse("-.")


def test_invalid_numbers():
    """Invalid number formats should raise ParseError."""
    with pytest.raises(comp.ParseError):
        comp.parse("3.14.15")  # Double decimal

    with pytest.raises(comp.ParseError):
        comp.parse("1e")  # Incomplete scientific notation

    with pytest.raises(comp.ParseError):
        comp.parse("inf")  # Special values are tags, not numbers (Phase 03)

    with pytest.raises(comp.ParseError):
        comp.parse("0x80.80")  # Decimals not allowed in alternate bases

    with pytest.raises(comp.ParseError):
        comp.parse("00o0")  # Too many leading zeros

    with pytest.raises(comp.ParseError):
        comp.parse("0b")  # No actual digits

    with pytest.raises(comp.ParseError):
        comp.parse("2+3j")  # No Python complex values


def test_precision_preservation():
    """Test that decimal parsing preserves precision without float conversion loss."""

    # Test 1: Classic 0.1 precision case
    # Float representation of 0.1 is imprecise, but Decimal('0.1') is exact
    result = comp.parse("0.1")
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
    expected = Decimal(scientific)
    assert result.value == expected, "Scientific notation precision lost"


def test_bigint_support():
    """Test that integers larger than 64-bit are handled correctly."""

    # 64-bit signed integer range: -9,223,372,036,854,775,808 to 9,223,372,036,854,775,807

    # Test 1: Large positive integer (way beyond 64-bit)
    big_int = "123456789012345678901234567890"
    result = comp.parse(big_int)
    expected = Decimal(big_int)
    assert result.value == expected, (
        f"Large integer not preserved: {result.value} != {expected}"
    )

    # Test 2: Large negative integer
    big_negative = "-987654321098765432109876543210"
    result = comp.parse(big_negative)
    expected = Decimal(big_negative)
    assert result.value == expected, "Large negative integer not preserved"

    # Test 3: Large hex number (should go through ast.literal_eval -> int -> Decimal)
    big_hex = "0x123456789ABCDEF0123456789ABCDEF"
    result = comp.parse(big_hex)
    # Convert manually to check
    expected_int = int(big_hex, 16)
    expected = Decimal(expected_int)
    assert result.value == expected, "Large hex integer not preserved"

    # Test 4: Large binary number
    big_binary = "0b" + "1" * 100  # 100-bit number
    result = comp.parse(big_binary)
    expected_int = int(big_binary, 2)
    expected = Decimal(expected_int)
    assert result.value == expected, "Large binary integer not preserved"

    # Test 5: Verify these are actually larger than 64-bit
    max_64bit = 2**63 - 1  # 9,223,372,036,854,775,807
    assert int(big_int) > max_64bit, "Test integer should be larger than 64-bit"
    assert abs(int(big_negative)) > max_64bit, (
        "Test negative integer should be larger than 64-bit"
    )


def _assertNum(value, match):
    """Helper to assert a parsed number matches expected Decimal value."""
    assert isinstance(value, comp.NumberLiteral)
    if isinstance(match, str):
        match = Decimal(match)
    assert value.value == match
