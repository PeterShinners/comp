"""Test token to string literal conversion in atom contexts.

This feature enables cleaner syntax by automatically converting simple tokens
to string literals when they appear as atom values, while preserving identifiers
in other contexts like assignments and references.

SPECIFICATION:
- Simple tokens in atom context (structure values) → strings
- Tokens in field names (assignments) → stay as identifiers
- Dotted identifiers → stay as identifiers
- Scoped identifiers ($var) → stay as identifiers

EXAMPLES:
- {USERNAME USER} → {"USERNAME" "USER"}
- {name = value} → name stays identifier, value becomes "value"
- {foo.bar} → stays as identifier
- {$var.name} → stays as scoped identifier
"""

import comp
import pytest


def test_tokens_in_structure_become_strings():
    """Simple tokens as structure values are converted to strings."""
    result = comp.parse_expr("{USERNAME USER LOGNAME}")
    
    assert isinstance(result, comp.ast.Structure)
    assert len(result.ops) == 3
    
    for i, op in enumerate(result.ops):
        assert isinstance(op, comp.ast.FieldOp)
        assert isinstance(op.value, comp.ast.String), f"Field {i} should be String"
    
    # Verify the actual string values
    assert result.ops[0].value.value == "USERNAME"
    assert result.ops[1].value.value == "USER"
    assert result.ops[2].value.value == "LOGNAME"


def test_assignment_value_tokens_become_strings():
    """Tokens on right side of assignments become strings."""
    result = comp.parse_expr("{name = value}")
    
    assert isinstance(result, comp.ast.Structure)
    assert len(result.ops) == 1
    
    op = result.ops[0]
    assert isinstance(op, comp.ast.FieldOp)
    
    # Key should be String (field name)
    assert isinstance(op.key, comp.ast.String)
    assert op.key.value == "name"
    
    # Value should be String (converted from token)
    assert isinstance(op.value, comp.ast.String)
    assert op.value.value == "value"


def test_dotted_identifiers_not_converted():
    """Dotted identifiers remain as identifiers, not strings."""
    result = comp.parse_expr("{foo.bar}")
    
    assert isinstance(result, comp.ast.Structure)
    op = result.ops[0]
    
    # Should be an Identifier with multiple fields
    assert isinstance(op.value, comp.ast.Identifier)
    assert len(op.value.fields) == 2


def test_scoped_identifiers_not_converted():
    """Scoped identifiers ($var.name) remain as identifiers."""
    result = comp.parse_expr("{$var.name}")
    
    assert isinstance(result, comp.ast.Structure)
    op = result.ops[0]
    
    # Should be an Identifier with scope
    assert isinstance(op.value, comp.ast.Identifier)
    assert isinstance(op.value.fields[0], comp.ast.ScopeField)


def test_mixed_values_in_structure():
    """Structure with mixed token, string, number, and identifier values."""
    result = comp.parse_expr('{USERNAME "literal" 42 $var.name}')
    
    assert isinstance(result, comp.ast.Structure)
    assert len(result.ops) == 4
    
    # USERNAME (token → string)
    assert isinstance(result.ops[0].value, comp.ast.String)
    assert result.ops[0].value.value == "USERNAME"
    
    # "literal" (already string)
    assert isinstance(result.ops[1].value, comp.ast.String)
    assert result.ops[1].value.value == "literal"
    
    # 42 (number)
    assert isinstance(result.ops[2].value, comp.ast.Number)
    
    # $var.name (scoped identifier)
    assert isinstance(result.ops[3].value, comp.ast.Identifier)


def test_tokens_in_pipeline_seed():
    """Tokens in pipeline seed structures are converted to strings."""
    result = comp.parse_expr("[{USERNAME USER LOGNAME} |map]")
    
    assert isinstance(result, comp.ast.Pipeline)
    
    # Seed should be a Structure
    seed = result.seed
    assert isinstance(seed, comp.ast.Structure)
    assert len(seed.ops) == 3
    
    # All should be strings
    for i, op in enumerate(seed.ops):
        assert isinstance(op.value, comp.ast.String), f"Seed field {i} should be String"


def test_readme_example():
    """Test the README example pattern works correctly."""
    # Simplified version without the fallback operator
    result = comp.parse_expr("[{USERNAME USER LOGNAME} |map]")
    
    assert isinstance(result, comp.ast.Pipeline)
    seed = result.seed
    
    # All environment variable names should be strings
    assert all(isinstance(op.value, comp.ast.String) for op in seed.ops)


def test_multiple_assignments():
    """Multiple assignments with token values."""
    result = comp.parse_expr("{name = alice age = young}")
    
    assert isinstance(result, comp.ast.Structure)
    assert len(result.ops) == 2
    
    # Both values should be strings
    assert isinstance(result.ops[0].value, comp.ast.String)
    assert result.ops[0].value.value == "alice"
    assert isinstance(result.ops[1].value, comp.ast.String)
    assert result.ops[1].value.value == "young"


def test_nested_structures():
    """Nested structures with token values."""
    result = comp.parse_expr("{outer = {inner = token}}")
    
    assert isinstance(result, comp.ast.Structure)
    
    # Outer value is a structure
    outer_op = result.ops[0]
    assert isinstance(outer_op.value, comp.ast.Structure)
    
    # Inner value should be a string
    inner_op = outer_op.value.ops[0]
    assert isinstance(inner_op.value, comp.ast.String)
    assert inner_op.value.value == "token"


def test_tokens_with_hyphens():
    """Tokens with hyphens should be converted to strings."""
    result = comp.parse_expr("{user-name api-key}")
    
    assert isinstance(result, comp.ast.Structure)
    assert len(result.ops) == 2
    
    assert isinstance(result.ops[0].value, comp.ast.String)
    assert result.ops[0].value.value == "user-name"
    assert isinstance(result.ops[1].value, comp.ast.String)
    assert result.ops[1].value.value == "api-key"


def test_tokens_with_question_mark():
    """Tokens with trailing question mark should be converted to strings."""
    result = comp.parse_expr("{valid? optional?}")
    
    assert isinstance(result, comp.ast.Structure)
    assert len(result.ops) == 2
    
    assert isinstance(result.ops[0].value, comp.ast.String)
    assert result.ops[0].value.value == "valid?"
    assert isinstance(result.ops[1].value, comp.ast.String)
    assert result.ops[1].value.value == "optional?"
