"""Test spread operations: ..$scope, ..@local, spread+assign, spread priority."""

import runtest


@runtest.params(
    "code, ctx_val, expected_fields",
    # Basic spread from scope
    spread_ctx=("{..$ctx}", {"x": 10, "y": 20}, {"x": 10, "y": 20}),
    spread_arg=("{..$arg}", {}, {"a": 1, "b": 2}),  # Will pass arg in test
    # Empty spread
    empty_spread=("{..$ctx}", {}, {}),
)
def test_spread_operations(key, code, ctx_val, expected_fields):
    """Test various spread patterns."""
    full_code = f"!func |test ~_ = {{ result = {code} }}"
    
    # Handle arg_val case
    arg_val = {"a": 1, "b": 2} if "$arg" in code else {}
    
    result = runtest.run_function(full_code, "test", {}, ctx_val, {}, arg_val)
    result_field = runtest.get_field(result, "result")
    
    for field_name, expected_value in expected_fields.items():
        actual = runtest.get_field_python(result_field, field_name)
        assert actual == expected_value


def test_spread_local_scope():
    """Test spreading from local (@) scope."""
    code = """
    !func |test ~_ = {
        @x = 10
        @y = 20
        result = {..@}
    }
    """
    result = runtest.run_function(code, "test", {})
    result_field = runtest.get_field(result, "result")
    
    assert runtest.get_field_python(result_field, "x") == 10
    assert runtest.get_field_python(result_field, "y") == 20


def test_spread_with_assignments():
    """Test spread combined with field assignments."""
    code = """
    !func |test ~_ = {
        result = {..$ctx}
        result.z = 30
    }
    """
    result = runtest.run_function(code, "test", {}, {"x": 10})
    result_field = runtest.get_field(result, "result")
    
    assert runtest.get_field_python(result_field, "x") == 10
    assert runtest.get_field_python(result_field, "z") == 30


def test_spread_nested_field():
    """Test spreading a nested field."""
    code = """
    !func |test ~_ = {
        result = {..$ctx.config}
    }
    """
    result = runtest.run_function(
        code, "test",
        {},                                                    # $in
        {"config": {"host": "localhost", "port": 8080}},      # $ctx
    )
    result_field = runtest.get_field(result, "result")
    
    assert runtest.get_field_python(result_field, "host") == "localhost"
    assert runtest.get_field_python(result_field, "port") == 8080


def test_spread_chained_scope():
    """Test spreading from chained scope (^)."""
    code = """
    !func |test ~_ = {
        result = {..^}
    }
    """
    # Chained scope: $arg -> $ctx -> $mod
    result = runtest.run_function(
        code, "test",
        {},                           # $in
        {"b": 20, "c": 30},          # $ctx
        {"c": 300, "d": 400},        # $mod
        {"a": 1, "b": 2}             # $arg (highest priority)
    )
    result_field = runtest.get_field(result, "result")
    
    # Priority: $arg > $ctx > $mod
    assert runtest.get_field_python(result_field, "a") == 1    # from $arg
    assert runtest.get_field_python(result_field, "b") == 2    # from $arg (overrides $ctx)
    assert runtest.get_field_python(result_field, "c") == 30   # from $ctx (overrides $mod)
    assert runtest.get_field_python(result_field, "d") == 400  # from $mod


@runtest.params(
    "code, expected",
    # Spread literal with additional fields
    extend=("{x=1 ..$ctx y=3}", {"x": 1, "a": 10, "b": 20, "y": 3}),
    # Multiple spreads
    multi=("{..$ctx ..$arg}", {"a": 10, "b": 2, "c": 30}),  # $arg.b overrides $ctx.b
    # Spread with field override
    override=("{a=99 ..$ctx}", {"a": 99, "b": 20}),  # a=99 comes first, but spread doesn't override
)
def test_spread_literals(key, code, expected):
    """Test spread literals in structure construction."""
    full_code = f"!func |test ~_ = {{ result = {code} }}"
    
    # Set up context values
    ctx_val = {"a": 10, "b": 20}
    arg_val = {"b": 2, "c": 30}
    
    result = runtest.run_function(full_code, "test", {}, ctx_val, {}, arg_val)
    result_field = runtest.get_field(result, "result")
    
    for field_name, expected_value in expected.items():
        actual = runtest.get_field_python(result_field, field_name)
        assert actual == expected_value


@runtest.params(
    "code, input_val, expected",
    # Spread assign into existing struct
    basic=("""
        result = {x=1 y=2}
        result..= $in
    """, {"z": 3, "w": 4}, {"x": 1, "y": 2, "z": 3, "w": 4}),
    # Spread assign with override
    override=("""
        result = {a=10 b=20}
        result..= $in
    """, {"b": 99, "c": 30}, {"a": 10, "b": 99, "c": 30}),
    # Spread assign from empty
    empty=("""
        result = {}
        result..= $in
    """, {"x": 100}, {"x": 100}),
)
def test_spread_assign(key, code, input_val, expected):
    """Test spread assign operator (..=) merging fields into existing struct."""
    full_code = f"!func |test ~_ = {{ {code} }}"
    
    result = runtest.run_function(full_code, "test", input_val)
    result_field = runtest.get_field(result, "result")
    
    # Verify all expected fields
    for field_name, expected_value in expected.items():
        actual = runtest.get_field_python(result_field, field_name)
        assert actual == expected_value
    
    # Verify no extra fields
    assert result_field.is_struct and result_field.struct is not None
    assert len(result_field.struct) == len(expected)
