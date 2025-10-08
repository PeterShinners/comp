"""Test advanced field access: nested, string fields, computed fields."""

import runtest


@runtest.params(
    "code, ctx_val, expected",
    # Nested access
    two_level=("result = $ctx.parent.child", {"parent": {"child": 42}}, 42),
    three_level=("result = $ctx.a.b.c", {"a": {"b": {"c": 99}}}, 99),
    # From different scopes
    from_mod=("result = $mod.config.port", None, 8080),  # Will set mod_val separately
    from_arg=("result = $arg.user.name", None, "Alice"),
    # Chained scope nested
    chained=("result = ^settings.host", None, "localhost"),
)
def test_nested_field_access(key, code, ctx_val, expected):
    """Test nested field access from various scopes."""
    full_code = f"!func |test ~_ = {{ {code} }}"
    
    # Set up scope values based on which is needed
    mod_val = {"config": {"port": 8080}} if "$mod" in code else {}
    arg_val = {"user": {"name": "Alice"}} if "$arg" in code else {}
    
    # For chained scope, set in $ctx
    if "^" in code:
        ctx_val = {"settings": {"host": "localhost"}}
    
    result = runtest.run_function(full_code, "test", {}, ctx_val or {}, mod_val, arg_val)
    assert runtest.get_field_python(result, "result") == expected


@runtest.params(
    "code, in_data, expected",
    # String field access from $in
    simple_string=('result = $in."Hello World"', {"Hello World": 42}, 42),
    special_chars=('result = $in."special-key"', {"special-key": 99}, 99),
    # String field assignment
    assign=('data."my key" = 100', {}, 100),
    # Nested with string
    nested=('result = $in.parent."child-key"', {"parent": {"child-key": 77}}, 77),
)
def test_string_fields(key, code, in_data, expected):
    """Test string field access and assignment."""
    if "data." in code:
        # Assignment test
        full_code = f"!func |test ~_ = {{\ndata = {{}}\n{code}\n}}"
        result = runtest.run_function(full_code, "test", in_data)  # Pass to $in (first param)
        data = runtest.get_field_python(result, "data")
        assert data["my key"] == expected
    else:
        # Access test - read from $in
        full_code = f"!func |test ~_ = {{\n{code}\n}}"
        result = runtest.run_function(full_code, "test", in_data)  # Pass to $in (first param)
        assert runtest.get_field_python(result, "result") == expected


@runtest.params(
    "code, expected",
    # Computed field with number expression
    number_expr=("result = data.'4+4'", "eight"),
    # Computed field with string expression
    string_expr=('result = data.\'"computed"\'', "value"),
)
def test_computed_fields(key, code, expected):
    """Test computed field access using 'expr' syntax."""
    if "4+4" in code:
        # Number expression
        setup = 'data = {\'4+4\' = "eight"}'
    else:
        # String expression
        setup = 'data = {\'"computed"\' = "value"}'
    
    full_code = f"!func |test ~_ = {{\n{setup}\n{code}\n}}"
    result = runtest.run_function(full_code, "test", {})
    assert runtest.get_field_python(result, "result") == expected


def test_deeply_nested_access():
    """Test very deep nesting."""
    code = """
    !func |test ~_ = {
        result = $ctx.a.b.c.d.e
    }
    """
    ctx_val = {
        "a": {
            "b": {
                "c": {
                    "d": {
                        "e": "deep value"
                    }
                }
            }
        }
    }
    result = runtest.run_function(code, "test", {}, ctx_val)
    assert runtest.get_field_python(result, "result") == "deep value"


def test_mixed_field_types():
    """Test mixing normal, string, and computed fields in one path."""
    code = """
    !func |test ~_ = {
        obj = {
            normal = {
                '5+5' = "mixed"
            }
        }
        result = obj.normal.'5+5'
    }
    """
    result = runtest.run_function(code, "test", {})
    assert runtest.get_field_python(result, "result") == "mixed"
