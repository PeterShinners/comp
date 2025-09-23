"""
Test cases for number literal parsing - Phase 02.

SPECIFICATION SUMMARY:
Number parsing with comprehensive format support including decimal, binary, octal,
hexadecimal, scientific notation, and signed numbers. All numbers become
decimal.Decimal values for arbitrary precision.

REQUIREMENTS FROM DESIGN DOCS:
- All numbers become decimal.Decimal values
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
- NumberLiteral: value (decimal.Decimal)
"""

from decimal import Decimal

import pytest

import comp


def test_parse_integers():
    """Integer literals should become decimal values."""
    result = comp.parse("42")
    assert isinstance(result, comp.NumberLiteral)
    assert result.value == 42

    result = comp.parse("-17")
    assert isinstance(result, comp.NumberLiteral)
    assert result.value == -17

    result = comp.parse("0")
    assert isinstance(result, comp.NumberLiteral)
    assert result.value == 0


def test_parse_decimals():
    """Decimal literals."""
    result = comp.parse("3.14")
    assert isinstance(result, comp.NumberLiteral)
    assert result.value == Decimal("3.14")

    result = comp.parse("-2.5")
    assert isinstance(result, comp.NumberLiteral)
    assert result.value == Decimal("-2.5")

    result = comp.parse("0.0")
    assert isinstance(result, comp.NumberLiteral)
    assert result.value == Decimal("0.0")


def test_parse_scientific_notation():
    """Scientific notation numbers."""
    result = comp.parse("1e3")
    assert isinstance(result, comp.NumberLiteral)
    assert result.value == Decimal("1000")

    result = comp.parse("1.23e-4")
    assert isinstance(result, comp.NumberLiteral)
    assert result.value == Decimal("0.000123")

    result = comp.parse("-2.5e2")
    assert isinstance(result, comp.NumberLiteral)
    assert result.value == Decimal("-250")


def test_parse_binary_numbers():
    """Binary number literals."""
    result = comp.parse("0b1010")
    assert isinstance(result, comp.NumberLiteral)
    assert result.value == 10

    result = comp.parse("0B11_11")
    assert isinstance(result, comp.NumberLiteral)
    assert result.value == 15


def test_parse_octal_numbers():
    """Octal number literals."""
    result = comp.parse("0o755")
    assert isinstance(result, comp.NumberLiteral)
    assert result.value == 493

    result = comp.parse("0O644")
    assert isinstance(result, comp.NumberLiteral)
    assert result.value == 420


def test_parse_hex_numbers():
    """Hexadecimal number literals."""
    result = comp.parse("0xFF")
    assert isinstance(result, comp.NumberLiteral)
    assert result.value == 255

    result = comp.parse("0xDeadBeef")
    assert isinstance(result, comp.NumberLiteral)
    assert result.value == 3735928559


def test_parse_numbers_with_underscores():
    """Numbers with underscore separators for readability."""
    result = comp.parse("1_000_000")
    assert isinstance(result, comp.NumberLiteral)
    assert result.value == Decimal("1000000")

    result = comp.parse("-0xFF_FF")
    assert isinstance(result, comp.NumberLiteral)
    assert result.value == Decimal("-65535")

    result = comp.parse("3.141_592")
    assert isinstance(result, comp.NumberLiteral)
    assert result.value == Decimal("3.141592")


def test_parse_leading_trailing_decimals():
    """Numbers with leading or trailing decimal points."""
    result = comp.parse("+.5")
    assert isinstance(result, comp.NumberLiteral)
    assert result.value == Decimal("0.5")

    result = comp.parse("5.")
    assert isinstance(result, comp.NumberLiteral)
    assert result.value == Decimal("5")


def test_parse_signed_numbers():
    """Positive and negative signs on all number formats."""
    # Positive integers
    result = comp.parse("+42")
    assert isinstance(result, comp.NumberLiteral)
    assert result.value == Decimal("42")

    # Negative binary
    result = comp.parse("-0b1010")
    assert isinstance(result, comp.NumberLiteral)
    assert result.value == Decimal("-10")

    # Positive hex
    result = comp.parse("+0xFF")
    assert isinstance(result, comp.NumberLiteral)
    assert result.value == Decimal("255")

    # Negative octal
    result = comp.parse("-0o644")
    assert isinstance(result, comp.NumberLiteral)
    assert result.value == Decimal("-420")


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


def test_precision_preservation():
    """Test that decimal parsing preserves precision without float conversion loss."""
    import decimal

    # Test 1: Classic 0.1 precision case
    # Float representation of 0.1 is imprecise, but Decimal('0.1') is exact
    result = comp.parse("0.1")
    expected = decimal.Decimal("0.1")
    assert result.value == expected, f"Expected exact {expected}, got {result.value}"

    # Verify we DON'T match what float conversion would give
    float_converted = decimal.Decimal(0.1)  # This is the lossy version
    assert result.value != float_converted, f"Parser result matches lossy float conversion: {float_converted}"

    # Test 2: High precision decimal that would lose digits through float
    high_precision = "3.14159265358979323846264338327950288419716939937510"
    result = comp.parse(high_precision)
    expected = decimal.Decimal(high_precision)
    assert result.value == expected, "High precision not preserved"

    # Verify float would lose precision
    float_version = float(high_precision)
    assert str(result.value) != str(float_version), "No precision difference detected vs float"

    # Test 3: Scientific notation precision
    scientific = "1.23456789012345678901234567890e-25"
    result = comp.parse(scientific)
    expected = decimal.Decimal(scientific)
    assert result.value == expected, "Scientific notation precision lost"

    # Test 4: Verify integers still work correctly (should use ast.literal_eval path)
    hex_result = comp.parse("0xFF")
    assert hex_result.value == decimal.Decimal(255), "Hex integer parsing broken"

    binary_result = comp.parse("-0b1010")
    assert binary_result.value == decimal.Decimal(-10), "Binary integer parsing broken"


def test_bigint_support():
    """Test that integers larger than 64-bit are handled correctly."""
    import decimal

    # 64-bit signed integer range: -9,223,372,036,854,775,808 to 9,223,372,036,854,775,807
    # Let's test numbers that are definitely larger than 64-bit

    # Test 1: Large positive integer (way beyond 64-bit)
    big_int = "123456789012345678901234567890"
    result = comp.parse(big_int)
    expected = decimal.Decimal(big_int)
    assert result.value == expected, f"Large integer not preserved: {result.value} != {expected}"

    # Test 2: Large negative integer
    big_negative = "-987654321098765432109876543210"
    result = comp.parse(big_negative)
    expected = decimal.Decimal(big_negative)
    assert result.value == expected, "Large negative integer not preserved"

    # Test 3: Large hex number (should go through ast.literal_eval -> int -> Decimal)
    big_hex = "0x123456789ABCDEF0123456789ABCDEF"
    result = comp.parse(big_hex)
    # Convert manually to check
    expected_int = int(big_hex, 16)
    expected = decimal.Decimal(expected_int)
    assert result.value == expected, "Large hex integer not preserved"

    # Test 4: Large binary number
    big_binary = "0b" + "1" * 100  # 100-bit number
    result = comp.parse(big_binary)
    expected_int = int(big_binary, 2)
    expected = decimal.Decimal(expected_int)
    assert result.value == expected, "Large binary integer not preserved"

    # Test 5: Verify these are actually larger than 64-bit
    max_64bit = 2**63 - 1  # 9,223,372,036,854,775,807
    assert int(big_int) > max_64bit, "Test integer should be larger than 64-bit"
    assert abs(int(big_negative)) > max_64bit, "Test negative integer should be larger than 64-bit"



def test_invalid_binary_numbers():
    """Binary numbers with invalid digits should give specific errors."""
    invalid_cases = [
        "0b123",  # Contains decimal digits
        "0b789",  # Contains non-binary digits
        "0bABC",  # Contains hex letters
        "0b12F",  # Mixed invalid digits
    ]

    for case in invalid_cases:
        with pytest.raises(comp.ParseError, match="Invalid binary number"):
            comp.parse(case)


def test_invalid_octal_numbers():
    """Octal numbers with invalid digits should give specific errors."""
    invalid_cases = [
        "0o789",  # Contains 8 and 9 (invalid for octal)
        "0o123ABC",  # Contains letters
        "0o99",  # All invalid digits
    ]

    for case in invalid_cases:
        with pytest.raises(comp.ParseError, match="Invalid octal number"):
            comp.parse(case)


def test_invalid_hex_numbers():
    """Hex numbers with invalid characters should give specific errors."""
    invalid_cases = [
        "0xGHIJ",  # Invalid hex letters
        "0x123G",  # Mixed valid/invalid
        "0xZZZ",  # All invalid letters
    ]

    for case in invalid_cases:
        with pytest.raises(comp.ParseError, match="Invalid hexadecimal number"):
            comp.parse(case)


def test_valid_base_numbers_still_work():
    """Ensure valid base numbers still parse correctly."""
    test_cases = [
        ("0b1010", 10),
        ("0o123", 83),
        ("0xFF", 255),
        ("-0b1010", -10),
        ("+0o123", 83),
    ]

    for input_str, expected in test_cases:
        result = comp.parse(input_str)
        assert isinstance(result, comp.NumberLiteral)
        assert result.value == expected


def test_error_messages_are_specific():
    """Verify error messages clearly identify the problem."""
    # Test that each base gives its own specific error message

    # Binary error
    with pytest.raises(comp.ParseError) as exc_info:
        comp.parse("0b789")
    assert "binary" in str(exc_info.value).lower()
    assert "non-binary digits" in str(exc_info.value)

    # Octal error
    with pytest.raises(comp.ParseError) as exc_info:
        comp.parse("0o89")
    assert "octal" in str(exc_info.value).lower()
    assert "non-octal digits" in str(exc_info.value)

    # Hex error
    with pytest.raises(comp.ParseError) as exc_info:
        comp.parse("0xGHI")
    assert "hexadecimal" in str(exc_info.value).lower()
    assert "invalid hex digits" in str(exc_info.value)


def test_signed_invalid_numbers():
    """Signed numbers with invalid base digits should also be caught."""
    invalid_cases = [
        "-0b789",  # Signed invalid binary
        "+0o89",  # Signed invalid octal
        "-0xGHI",  # Signed invalid hex
    ]

    for case in invalid_cases:
        with pytest.raises(comp.ParseError, match="Invalid"):
            comp.parse(case)

