"""
Test cases for scope reference and assignment parsing - Phase 01-08.

SPECIFICATION:
- Scope references: $ctx, $mod, $in, $out, $arg, ^, @ with field paths
- Special syntax: ^timeout (no dot), @local (no dot), $ctx.field (dot required)
- Assignment operators: =, =*, =? for scope assignments
- Deep field paths: $ctx.database.connection.pool-size (unlimited nesting)
- Mixed assignments: {$ctx.session = token, result.field = value, @temp = data}

PARSER EXPECTATIONS (Updated for flattened structure):
- comp.parse("$ctx") → ScopeReference(ScopeToken("$", "ctx"))
- comp.parse("$ctx.session") → ScopeReference(ScopeToken("$", "ctx"), Identifier("session"))
- comp.parse("^timeout") → ScopeReference(ScopeToken("^", None), Identifier("timeout"))
- comp.parse("@counter") → ScopeReference(ScopeToken("@", None), Identifier("counter"))
- comp.parse("$mod.two.three") → ScopeReference(ScopeToken("$", "mod"), Identifier("two"), Identifier("three"))
- comp.parse("{$ctx.session = token}") → StructureLiteral([ScopeAssignment(...)])

AST NODES: ScopeReference(scope_token, *field_identifiers),
           ScopeToken(scope_type, scope_name),
           ScopeTarget(scope_type, scope_name, field_path),
           ScopeAssignment(target, operator, value)

NOTE: This phase implements the foundation of Comp's explicit scoping system.
All scopes use explicit prefixes and have well-defined behavior for field lookup.
The flattened structure matches FieldAccessOperation for consistency.
"""

import pytest

import comp


@pytest.mark.parametrize("field,scope,field_count", [
    ("$ctx", "$ctx", 0),
    ("$mod", "$mod", 0),

    ("$in.child", "$in", 1),
    ("$out.#12", "$out", 1),
    ("$arg.'4+4'", "$arg", 1),

    ("@", "@", 0),
    ("@local-counter", "@", 1),
    ("^", "^", 0),
    ("^craft", "^", 1),
    ("^#4", "^", 1),
])
def test_valid_scopes(field, scope, field_count):
    """Test parsing of standalone scopes"""
    result = comp.parse(field)
    assert isinstance(result, comp.FieldAccessOperation)
    assert isinstance(result.object, comp.Scope)
    assert result.object.value == scope
    assert len(result.fields) == field_count


@pytest.mark.parametrize("field", [
    "$ctx.$mod",  # nested scope
    "one.$ctx",  # nested scope
    "$cat.dog",  # unknown scope
])
def test_invalid_scopes(field):
    """Test parsing of invalid standalong scopes"""
    with pytest.raises(comp.ParseError):
        comp.parse(field)


@pytest.mark.parametrize("field,left,right", [
    ("$ctx + ^two", "$ctx", "^"),
    ("$mod.#5 * @local", "$mod", "@"),
])
def test_binary_parsing(field, left, right):
    """Check operator precedence with simple expressions"""
    result = comp.parse(field)
    assert isinstance(result, comp.BinaryOperation)
    assert isinstance(result.left, comp.FieldAccessOperation)
    assert isinstance(result.right, comp.FieldAccessOperation)
    assert isinstance(result.left.object, comp.Scope)
    assert isinstance(result.right.object, comp.Scope)
    assert result.left.object.value == left
    assert result.right.object.value == right


@pytest.mark.parametrize("assignment,scope_type,scope_name,field_path,operator,value_type", [
    # Basic scope assignments
    ("$ctx=42", "$", "ctx", None, "=", comp.NumberLiteral),
    ("$mod={one=1}", "$", "mod", None, "=", comp.StructureLiteral),
    ("@local=value", "@", "local", None, "=", comp.Identifier),
    ("^timeout=30", "^", "timeout", None, "=", comp.NumberLiteral),

    # Scope field assignments
    ('$ctx.field=5', "$", "ctx", "field", "=", comp.NumberLiteral),
    ("$mod.config.port=8080", "$", "mod", "config.port", "=", comp.NumberLiteral),
    ("@temp.result=\"done\"", "@", "temp", "temp.result", "=", comp.StringLiteral),
    ("^user.name=\"alice\"", "^", "user", "user.name", "=", comp.StringLiteral),

    # Deep nested assignments
    ("$ctx.database.connection.pool=10", "$", "ctx", "database.connection.pool", "=", comp.NumberLiteral),
    ("@cache.user.profile.id=123", "@", "cache", "cache.user.profile.id", "=", comp.NumberLiteral),

    # Different assignment operators
    ("$ctx.setting=?default", "$", "ctx", "setting", "=?", comp.Identifier),
    ("$mod.global=*persistent", "$", "mod", "global", "=*", comp.Identifier),
    ("@temp=?fallback", "@", "temp", None, "=?", comp.Identifier),
    ("^args.timeout=*required", "^", "args", "args.timeout", "=*", comp.Identifier),
])
def test_scope_assignments(assignment, scope_type, scope_name, field_path, operator, value_type):
    """Test parsing of scope assignments at top level"""
    result = comp.parse(assignment)
    assert isinstance(result, comp.AssignmentOperation)

    # Check target - should be FieldAccessOperation
    assert isinstance(result.target, comp.FieldAccessOperation)

    # Check operator
    assert result.operator == operator

    # Check pipeline structure - assignments always have a pipeline
    assert hasattr(result, 'pipeline')
    assert isinstance(result.pipeline, comp.PipelineOperation)
    assert len(result.pipeline.stages) >= 1

    # Check value type - handle FieldAccessOperation wrapping
    actual_value = result.pipeline.stages[0]
    if value_type == comp.Identifier and isinstance(actual_value, comp.FieldAccessOperation):
        # Bare identifier becomes FieldAccessOperation(None, [Identifier])
        assert actual_value.object is None
        assert len(actual_value.fields) == 1
        assert isinstance(actual_value.fields[0], comp.Identifier)
    else:
        assert isinstance(actual_value, value_type)
    
    # Check scope structure
    if scope_type in ["$", "@", "^"]:
        # Should have a Scope as object
        assert isinstance(result.target.object, comp.Scope)
        expected_scope_value = f"{scope_type}{scope_name}" if scope_type == "$" else scope_type
        assert result.target.object.value == expected_scope_value
        
        # Check fields (for field paths like ctx.field)
        if field_path:
            assert len(result.target.fields) > 0
            # First field should be the actual field name
            assert isinstance(result.target.fields[0], comp.Identifier)
        else:
            # Direct scope assignment like $ctx=value should have scope name as field
            if scope_type == "$":
                # For $ctx=value, we expect no fields (the scope object contains the full $ctx)
                assert len(result.target.fields) == 0
            else:
                # For @local=value, ^timeout=value, we expect the name as a field
                assert len(result.target.fields) == 1
                assert isinstance(result.target.fields[0], comp.Identifier)
                assert result.target.fields[0].name == scope_name


@pytest.mark.parametrize("assignment,target_name,field_path,operator,value_type", [
    # Simple field assignments
    ("one=1", "one", [], "=", comp.NumberLiteral),
    ("field=\"text\"", "field", [], "=", comp.StringLiteral),

    # Nested field assignments
    ("one.two=2", "one", ["two"], "=", comp.NumberLiteral),
    ("field.nested.deep=value", "field", ["nested", ".", "deep"], "=", comp.Identifier),
    ("config.database.timeout=30", "config", ["database", ".", "timeout"], "=", comp.NumberLiteral),

    # Different assignment operators on fields
    ("setting=?default", "setting", [], "=?", comp.Identifier),
    ("config=*override", "config", [], "=*", comp.Identifier),
    ("field.nested=?fallback", "field", ["nested"], "=?", comp.Identifier),
])
def test_field_assignments(assignment, target_name, field_path, operator, value_type):
    """Test parsing of nested field assignments at top level"""
    result = comp.parse(assignment)
    assert isinstance(result, comp.AssignmentOperation)

    # Check target - should be FieldAccessOperation
    assert isinstance(result.target, comp.FieldAccessOperation)
    assert result.target.object is None  # Bare field access has no object
    
    # Check operator
    assert result.operator == operator

    # Check value type - handle FieldAccessOperation wrapping and pipeline structure
    # The value is now in result.pipeline.stages[0] for single-value assignments
    if len(result.pipeline.stages) == 1:
        value_node = result.pipeline.stages[0]
        if value_type == comp.Identifier and isinstance(value_node, comp.FieldAccessOperation):
            # Bare identifier becomes FieldAccessOperation(None, [Identifier])
            assert value_node.object is None
            assert len(value_node.fields) == 1
            assert isinstance(value_node.fields[0], comp.Identifier)
        else:
            assert isinstance(value_node, value_type)    # Check field structure
    assert len(result.target.fields) >= 1
    assert isinstance(result.target.fields[0], comp.Identifier)
    assert result.target.fields[0].name == target_name
    
    # Check nested field path
    if len(field_path) > 0:
        # For nested paths like one.two, we should have the base identifier plus additional fields
        # The flattened structure removes dots, so "config.database.timeout" becomes
        # [Identifier('config'), Identifier('database'), Identifier('timeout')] 
        expected_field_count = len([f for f in field_path if f != "."])  # Count non-dot fields
        assert len(result.target.fields) == expected_field_count + 1  # +1 for base identifier
        
        # Check the additional fields (skip the base identifier at index 0)
        field_index = 1
        for expected_field in field_path:
            if expected_field != ".":  # Skip dots in the path representation
                assert isinstance(result.target.fields[field_index], comp.Identifier)
                assert result.target.fields[field_index].name == expected_field
                field_index += 1


@pytest.mark.parametrize("assignment,description", [
    # Mixed scope and field assignments in structures (single assignments only - no commas)
    ("{$ctx.session = token}", "scope field assignment in structure"),
    
    # Complex nested structures with assignments
    ("{$ctx.database = {host=\"localhost\" port=5432}}", "nested structure assignment to scope"),
    ("{user.profile = {name=\"alice\" verified=#true}}", "nested structure assignment to field"),
])
def test_assignment_in_structures(assignment, description):
    """Test that assignments work correctly within structure literals"""
    result = comp.parse(assignment)
    assert isinstance(result, comp.StructureLiteral)
    assert len(result.operations) > 0

    # At least one operation should be an assignment operation
    has_assignment = any(isinstance(op, comp.StructureOperation) for op in result.operations)
    assert has_assignment, f"No assignment found in: {description}"


def test_scope_assignment_vs_reference():
    """Test that scope assignments and references are parsed differently"""
    # Reference - should be FieldAccessOperation
    ref_result = comp.parse("$ctx.session")
    assert isinstance(ref_result, comp.FieldAccessOperation)
    assert isinstance(ref_result.object, comp.Scope)
    
    # Assignment - should be AssignmentOperation
    assign_result = comp.parse("$ctx.session = token")
    assert isinstance(assign_result, comp.AssignmentOperation)
    assert isinstance(assign_result.target, comp.FieldAccessOperation)
    assert isinstance(assign_result.target.object, comp.Scope)
    assert assign_result.operator == "="

