"""
Tests for chained scope (^) that chains through $arg -> $ctx -> $mod
"""

import comp
from comp import run


def test_chained_scope_priority_arg_first():
    """Test that ^ looks up $arg first"""
    # Parse a simple function that returns ^x
    code = """
    !func |test-func ~_ = {
        result = ^x
    }
    """

    ast_module = comp.parse_module(code)
    module = run.Module("test")
    module.process_ast(ast_module)
    module.resolve_all()

    func_def = module.funcs["test-func"]

    # Create values for different scopes
    arg_val = run.Value({"x": 10})    # $arg.x = 10
    ctx_val = run.Value({"x": 20})    # $ctx.x = 20
    mod_val = run.Value({"x": 30})    # $mod.x = 30

    result = run.invoke(func_def, module, run.Value({}), ctx_val, mod_val, arg_val)

    # ^x should resolve to $arg.x (highest priority)
    assert result.is_struct
    assert result.struct[run.Value("result")].to_python() == 10


def test_chained_scope_fallthrough_to_ctx():
    """Test that ^ falls through to $ctx when not in $arg"""
    code = """
    !func |test-func ~_ = {
        result = ^y
    }
    """

    ast_module = comp.parse_module(code)
    module = run.Module("test")
    module.process_ast(ast_module)
    module.resolve_all()

    func_def = module.funcs["test-func"]

    # Only $ctx and $mod have 'y'
    arg_val = run.Value({"x": 10})    # $arg has no 'y'
    ctx_val = run.Value({"y": 20})    # $ctx.y = 20
    mod_val = run.Value({"y": 30})    # $mod.y = 30

    result = run.invoke(func_def, module, run.Value({}), ctx_val, mod_val, arg_val)

    # ^y should resolve to $ctx.y (second priority)
    assert result.is_struct
    assert result.struct[run.Value("result")].to_python() == 20


def test_chained_scope_fallthrough_to_mod():
    """Test that ^ falls through to $mod when not in $arg or $ctx"""
    code = """
    !func |test-func ~_ = {
        result = ^z
    }
    """

    ast_module = comp.parse_module(code)
    module = run.Module("test")
    module.process_ast(ast_module)
    module.resolve_all()

    func_def = module.funcs["test-func"]

    # Only $mod has 'z'
    arg_val = run.Value({"x": 10})    # $arg has no 'z'
    ctx_val = run.Value({"y": 20})    # $ctx has no 'z'
    mod_val = run.Value({"z": 30})    # $mod.z = 30

    result = run.invoke(func_def, module, run.Value({}), ctx_val, mod_val, arg_val)

    # ^z should resolve to $mod.z (lowest priority)
    assert result.is_struct
    assert result.struct[run.Value("result")].to_python() == 30


def test_chained_scope_spread():
    """Test that ..^ spreads all chained scopes with proper priority"""
    code = """
    !func |test-func ~_ = {
        ..^
    }
    """

    ast_module = comp.parse_module(code)
    module = run.Module("test")
    module.process_ast(ast_module)
    module.resolve_all()

    func_def = module.funcs["test-func"]

    # Each scope has overlapping fields
    arg_val = run.Value({"a": 1, "b": 2})        # $arg
    ctx_val = run.Value({"b": 20, "c": 30})      # $ctx (b should be overridden)
    mod_val = run.Value({"c": 300, "d": 400})    # $mod (c should be overridden)

    result = run.invoke(func_def, module, run.Value({}), ctx_val, mod_val, arg_val)

    # Result should have all fields with proper priority:
    # a=1 (from $arg), b=2 (from $arg, overrides $ctx), c=30 (from $ctx, overrides $mod), d=400 (from $mod)
    assert result.is_struct
    result_dict = {k.to_python(): v.to_python() for k, v in result.struct.items()}

    assert result_dict == {
        "a": 1,    # from $arg
        "b": 2,    # from $arg (overrides $ctx.b=20)
        "c": 30,   # from $ctx (overrides $mod.c=300)
        "d": 400   # from $mod
    }


def test_chained_scope_nested_field():
    """Test that ^ can access nested fields like ^user.name"""
    code = """
    !func |test-func ~_ = {
        result = ^user.name
    }
    """

    ast_module = comp.parse_module(code)
    module = run.Module("test")
    module.process_ast(ast_module)
    module.resolve_all()

    func_def = module.funcs["test-func"]

    # $arg has nested structure
    arg_val = run.Value({"user": {"name": "Alice", "age": 30}})
    ctx_val = run.Value({})
    mod_val = run.Value({})

    result = run.invoke(func_def, module, run.Value({}), ctx_val, mod_val, arg_val)

    # ^user.name should resolve to $arg.user.name
    assert result.is_struct
    assert result.struct[run.Value("result")].to_python() == "Alice"
