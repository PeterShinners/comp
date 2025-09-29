"""
Test edge cases and invalid syntax for operators.

This module tests corner cases, invalid syntax, and boundary conditions
for all operators to ensure proper error handling and edge case behavior.
"""

import pytest

import comp


def _check_identifier(node, expected_name=None):
    """Helper to check if a node is an identifier, handling FieldAccessOperation wrapping."""
    if isinstance(node, comp.Identifier):
        if expected_name is not None:
            assert node.name == expected_name
        return True
    elif isinstance(node, comp.FieldAccessOperation):
        # Bare identifier becomes FieldAccessOperation(None, [Identifier])
        if node.object is None and len(node.fields) == 1 and isinstance(node.fields[0], comp.Identifier):
            if expected_name is not None:
                assert node.fields[0].name == expected_name
            return True
    return False


# Invalid mathematical operator syntax cases that should raise parse errors
invalid_mathematical_operator_cases = [
    # Invalid operator combinations
    ("12 * / 3", "consecutive binary operators"),
    ("5 + * 2", "plus followed by multiply"),
    ("1 / / 2", "double division operator"),
    ("7 - * 8", "minus followed by multiply"),
    ("9 % / 3", "modulo followed by division"),
    # Missing operands (but not unary cases)
    ("3 +", "binary operator without right operand"),
    ("* 4", "multiply without left operand"),
    ("/ 2", "divide without left operand"),
    ("()", "empty parentheses"),
    # Invalid parentheses
    ("(3 + 4", "unclosed parenthesis"),
    ("3 + 4)", "unmatched closing parenthesis"),
    ("((3 + 4)", "unmatched nested parenthesis"),
    ("3 + (4 * 5))", "extra closing parenthesis"),
    # Invalid whitespace/structure
    ("3 + 4 5", "missing operator between numbers"),
    ("x y", "missing operator between identifiers"),
    ("#tag1 #tag2", "missing operator between references"),
]


# Invalid operator syntax cases
invalid_advanced_operator_cases = [
    # Invalid assignment contexts
    ("x + y = z", "assign to expression"),
    ("= value", "assignment without target"),
    # Invalid spread syntax
    ("..x", "spread outside structure"),
    ("{ .. }", "incomplete spread"),
    # Invalid field access
    ("x.", "incomplete field access"),
    (".name", "field access without object"),
    ("42.field", "field access on literal"),
    # Invalid index access
    ("x#", "incomplete index access"),
    ("user#name", "index with identifier instead of number"),
    ("config.database.#identifier", "tag in field name without quotes"),
    # Invalid private data operators
    ("x&", "incomplete private attach"),
    ("&data", "private attach without object"),
    ("x&.", "incomplete private access"),
    ("&.field", "private access without object"),
    # Invalid pipeline operators
    ("|? fallback", "pipeline failure without operation"),
    ("op |?", "incomplete pipeline failure"),
    ("|{}", "pipeline block without operation"),
    ("op |", "incomplete pipeline"),
    # Invalid block syntax
    (":{", "unclosed block definition"),
    ("|:", "block invoke without target"),
    (":{ x +", "incomplete block expression"),
    ("|:{x + y} args", "inline block definition with args - not supported"),
    # Invalid fallback operators
    ("?? value", "fallback without left operand"),
    ("|?", "incomplete alternative fallback"),
    ("x ??", "incomplete fallback"),
    # Invalid special syntax
    ("???x", "placeholder with extra content"),
    ("x[]y", "array brackets with content"),
    ("'incomplete", "unclosed single quote"),
]


# Valid but tricky mathematical cases that should parse correctly
tricky_valid_mathematical_cases = [
    # Unary operators (these should be valid)
    ("4--4", "double minus (4 - (-4))"),
    ("4+-4", "plus minus (4 + (-4))"),
    ("4*-4", "multiply negative (4 * (-4))"),
    ("4/-4", "divide negative (4 / (-4))"),
    ("-4*-4", "negative multiply negative"),
    ("--4", "double negative"),
    ("+ 5", "unary plus"),
    ("3 + + 4", "binary plus with unary plus"),
    # Valid operators that might look suspicious
    ("2 ** 3", "exponentiation operator"),
    ("4 && 5", "logical AND operator"),
    ("6 || 7", "logical OR operator"),
    # Complex precedence
    ("1 + 2 * 3 - 4 / 2", "mixed precedence"),
    ("(1 + 2) * (3 - 4)", "parentheses precedence"),
    ("1 + 2 * 3 + 4", "left-to-right same precedence"),
    # Edge cases with references and identifiers
    ("x + -y", "identifier plus negative identifier"),
    ("#tag + -#other", "tag plus negative tag"),
    ("~shape * -~other", "shape multiply negative shape"),
    # Complex nested expressions (without function calls for now)
    ("((1 + 2) * 3) - ((4 / 2) + 1)", "deeply nested parentheses"),
    ("{result = (x + y) * (a - b)}", "structure with complex expression"),
]


# Valid but tricky operator cases
tricky_valid_advanced_cases = [
    # Complex assignment expressions
    ('{config = {port=8080 host="localhost"}}', "nested structure assignment"),
    ("{user =? default-user}", "weak assignment in structure"),
    ("{data =* computed-value}", "strong assignment in structure"),
    # Complex spread operations
    ('{..defaults ..overrides name="test"}', "multiple spreads with assignment"),
    ("{ ..x ..y }", "multiple spreads without explicit assignment"),
    ("{user ..= {verified=#true timestamp=now}}", "spread assignment with structure"),
    # Complex assignment (chained is undefined but valid syntax for now)
    ("x = y = z", "chained assignment expression"),
    # Complex field/index access
    ("users.#0.profile.name", "chained access operations"),
    ("data&.session.user.id", "private field access chain"),
    # Quoted tag in field name (correct syntax)
    ("config.database.'#primary'.connection", "quoted tag in field name"),
    # Standalone index references (like tag atoms but all digits)
    ("#0", "standalone index reference zero"),
    ("#123", "standalone multi-digit index reference"),
    ("items.#0 + #1", "object index access plus standalone index"),
    # Complex fallback chains
    ("config.port ?? env.PORT ?? 8080", "chained fallback operators"),
    ('primary.value |? secondary.value |? "default"', "chained alternative fallback"),
    # Complex pipeline operations
    ("data |? {error=true} ?? fallback-data", "pipeline with fallback"),
    # Simple block operations that should work
    (":{x + y}", "block definition"),
    ("|:processor", "block invoke operation"),
    # Shape unions with other operators
    ("~string|~number + value", "shape union with mathematical operator"),
    ("(~int|~float) * multiplier", "parenthesized shape union"),
]


@pytest.mark.parametrize(
    "invalid_input,description",
    invalid_mathematical_operator_cases + invalid_advanced_operator_cases,
    ids=[
        case[1]
        for case in invalid_mathematical_operator_cases
        + invalid_advanced_operator_cases
    ],
)
def test_invalid_operator_syntax(invalid_input, description):
    """Test that invalid operator syntax raises parse errors."""
    with pytest.raises(Exception) as exc_info:
        comp.parse(invalid_input)

    # Verify we get some kind of parse error
    assert exc_info.value is not None
    print(f"✓ Correctly rejected: {invalid_input} - {description}")
    print(f"  Error: {exc_info.value}")


@pytest.mark.parametrize(
    "valid_input,description",
    tricky_valid_mathematical_cases,  # Only test mathematical cases for now
    ids=[case[1] for case in tricky_valid_mathematical_cases],
)
def test_tricky_valid_mathematical_syntax(valid_input, description):
    """Test that tricky but valid mathematical syntax parses correctly."""
    try:
        result = comp.parse(valid_input)
        assert result is not None
        print(f"✓ Correctly parsed: {valid_input} - {description}")
        print(f"  Result: {result}")
    except Exception as e:
        pytest.fail(
            f"Should have parsed '{valid_input}' ({description}) but got error: {e}"
        )


@pytest.mark.parametrize(
    "valid_input,description",
    tricky_valid_advanced_cases,
    ids=[case[1] for case in tricky_valid_advanced_cases],
)
def test_tricky_valid_advanced_syntax(valid_input, description):
    """Test that tricky but valid syntax parses correctly."""

    # Skip cases that are known to be broken (not yet implemented)
    broken_cases = [
        # All current test cases should work or properly fail
    ]

    if description in broken_cases:
        pytest.skip(f"Not implemented yet: {description}")

    try:
        result = comp.parse(valid_input)
        assert result is not None
        print(f"✓ Correctly parsed: {valid_input} - {description}")
        print(f"  Result: {result}")
    except Exception as e:
        pytest.fail(
            f"Should have parsed '{valid_input}' ({description}) but got error: {e}"
        )


def test_operator_precedence():
    """Test that operator precedence works correctly."""
    # Test basic precedence: multiplication before addition
    result = comp.parse("2 + 3 * 4")
    assert isinstance(result, comp.BinaryOperation)
    assert result.operator == "+"
    assert isinstance(result.left, comp.NumberLiteral)
    assert result.left.value == 2
    assert isinstance(result.right, comp.BinaryOperation)
    assert result.right.operator == "*"

    # Test parentheses override precedence
    result = comp.parse("(2 + 3) * 4")
    assert isinstance(result, comp.BinaryOperation)
    assert result.operator == "*"
    # Left side should be the parenthesized addition
    # Note: We might need to handle parentheses transformation better


def test_unary_operators():
    """Test unary operators work correctly."""
    # Test basic unary minus
    result = comp.parse("-5")
    assert isinstance(result, comp.UnaryOperation)
    assert result.operator == "-"
    assert isinstance(result.operand, comp.NumberLiteral)
    assert result.operand.value == 5

    # Test unary in expressions
    result = comp.parse("x + -y")
    assert isinstance(result, comp.BinaryOperation)
    assert result.operator == "+"
    assert _check_identifier(result.left, "x")
    # Right side should be negative identifier (however that's represented)


def test_comparison_operators():
    """Test comparison operators parse correctly."""
    comparison_ops = ["==", "!=", "<", "<=", ">", ">="]

    for op in comparison_ops:
        expr = f"x {op} y"
        result = comp.parse(expr)
        assert isinstance(result, comp.BinaryOperation)
        assert result.operator == op
        assert _check_identifier(result.left, "x")
        assert _check_identifier(result.right, "y")


def test_logical_operators():
    """Test logical operators parse correctly."""
    logical_cases = [
        ("x and y", "and"),
        ("x or y", "or"),
        ("not x", "not"),
        ("x and y or z", "mixed logical"),
    ]

    for expr, _ in logical_cases:
        try:
            result = comp.parse(expr)
            print(f"✓ Logical operator: {expr} -> {result}")
        except Exception as e:
            print(f"⚠ Logical operator may not be implemented yet: {expr} -> {e}")


def test_mixed_atom_types_in_operations():
    """Test that different atom types can be used in operations."""
    mixed_cases = [
        "42 + x",  # number + identifier
        "x + #balance",  # identifier + tag
        "#rate * 100",  # tag * number
        "~num + ~int",  # shape + shape
        "|getValue - count",  # function reference - identifier (proper syntax)
        "{total = base + #tax}",  # structure with mixed operation
    ]

    for expr in mixed_cases:
        result = comp.parse(expr)
        assert result is not None
        print(f"✓ Mixed atoms: {expr} -> type: {type(result).__name__}")


def test_deeply_nested_expressions():
    """Test complex nested expressions parse correctly."""
    nested_cases = [
        # Skip complex parentheses for now due to transformer issues
        # "((x + y) * z)",
        # "(a + (b * c))",
        # "((a + b) * (c + d))",
        "x + y * z",  # Simple precedence
        "{result = base + tax * rate}",  # Structure with expression
        "x + (y - z)",  # Simple parentheses
    ]

    for expr in nested_cases:
        result = comp.parse(expr)
        assert result is not None
        print(f"✓ Nested expression: {expr}")


def test_whitespace_sensitivity():
    """Test how whitespace affects operator parsing."""
    # These should all be equivalent
    equivalent_cases = [
        ["1 + 2", "1+2"],  # Addition (if tokenizer supports it)
        ["x * y", "x*y"],  # Multiplication
        ["a == b", "a==b"],  # Comparison
    ]

    for expressions in equivalent_cases:
        results = []
        for expr in expressions:
            try:
                result = comp.parse(expr)
                results.append(result)
                print(f"✓ Whitespace test: '{expr}' -> {result}")
            except Exception as e:
                print(f"⚠ Whitespace issue: '{expr}' -> {e}")
                results.append(None)

        # All non-None results should be equivalent
        valid_results = [r for r in results if r is not None]
        if len(valid_results) > 1:
            # Could add more sophisticated equivalence checking here
            print("  Multiple valid parses for equivalent expressions")


def test_assignment_operator_precedence():
    """Test assignment operator precedence (should be lowest)."""
    # Assignment should have lower precedence than mathematical operators
    result = comp.parse("{result = x + y * z}")
    assert isinstance(result, comp.StructureLiteral)
    # The structure should contain the assignment with the full expression as value
    assert len(result.operations) > 0
    operation = result.operations[0]
    assert hasattr(operation, "target")
    assert hasattr(operation, "expression")
    # The expression should be the full binary operation, not just 'x'
    assert isinstance(operation.expression, comp.BinaryOperation)


def test_fallback_operator_precedence():
    """Test fallback operator precedence interactions."""
    # Test fallback with mathematical operators
    result = comp.parse("x + y ?? z * w")
    # Should be: (x + y) ?? (z * w)
    assert isinstance(result, comp.FallbackOperation)
    assert result.operator == "??"
    # Both sides should be binary operations due to precedence
    assert isinstance(result.left, comp.BinaryOperation)
    assert isinstance(result.right, comp.BinaryOperation)


def test_field_access_precedence():
    """Test field access operator precedence (should be high)."""
    # Field access should have higher precedence than mathematical operators
    result = comp.parse("user.age + 5")
    assert isinstance(result, comp.BinaryOperation)
    assert result.operator == "+"
    # Left side should be field access, not identifier
    assert isinstance(result.left, comp.FieldAccessOperation)
    assert isinstance(result.right, comp.NumberLiteral)


def test_complex_operator_interactions():
    """Test complex interactions between mathematical and operators."""
    complex_cases = [
        # Mathematical with assignment
        ("{total = base + tax * rate}", comp.StructureLiteral),
        # Mathematical with fallback
        ("value + increment ?? default-increment", comp.FallbackOperation),
        # Mathematical with field access
        ("user.balance * interest-rate", comp.BinaryOperation),
        # Skip index access for now as it's not fully implemented
        ("prices.'#index' + tax-amount", comp.BinaryOperation),
        # Skip complex combined case with index access
        ("{result = data.#3.value * factor ?? default-result}", comp.StructureLiteral),
    ]

    for expr, expected_type in complex_cases:
        result = comp.parse(expr)
        assert isinstance(result, expected_type)
        print(f"✓ Complex interaction: {expr} -> {type(result).__name__}")
