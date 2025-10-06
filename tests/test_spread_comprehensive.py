"""
Comprehensive tests for the spread operator (..)
"""

import comp
from comp import run


def test_spread_from_ctx():
    """Spread operator pulls fields from $ctx scopes"""
    code = """
    !func |test-func ~_ = {
        defaults = {..$ctx.config}
    }
    """

    ast_module = comp.parse_module(code)
    module = run.Module("test")
    module.process_ast(ast_module)
    module.resolve_all()

    func_def = module.funcs["test-func"]

    ctx_val = run.Value({"config": {"timeout": 30, "retries": 3}})

    result = run.invoke(func_def, module, run.Value({}), ctx_val, run.Value({}), run.Value({}))

    assert result.is_struct
    defaults = result.struct[run.Value("defaults")]
    assert defaults.is_struct
    assert defaults.struct[run.Value("timeout")].to_python() == 30
    assert defaults.struct[run.Value("retries")].to_python() == 3


def test_spread_from_local_scope():
    """Spread operator works with @ local scope"""
    code = """
    !func |test-func ~_ = {
        @common = "value"
        @another = 42
        output = {..@}
    }
    """

    ast_module = comp.parse_module(code)
    module = run.Module("test")
    module.process_ast(ast_module)
    module.resolve_all()

    func_def = module.funcs["test-func"]

    result = run.invoke(func_def, module, run.Value({}), run.Value({}), run.Value({}), run.Value({}))

    assert result.is_struct
    output = result.struct[run.Value("output")]
    assert output.is_struct
    # Local scope fields are spread into output
    assert output.struct[run.Value("common")].to_python() == "value"
    assert output.struct[run.Value("another")].to_python() == 42


def test_spread_empty_struct():
    """Spreading an empty struct produces empty result"""
    code = """
    !func |test-func ~_ = {
        empty = {}
        result = {..empty}
    }
    """

    ast_module = comp.parse_module(code)
    module = run.Module("test")
    module.process_ast(ast_module)
    module.resolve_all()

    func_def = module.funcs["test-func"]

    result = run.invoke(func_def, module, run.Value({}), run.Value({}), run.Value({}), run.Value({}))

    assert result.is_struct
    result_val = result.struct[run.Value("result")]
    assert result_val.is_struct
    assert len(result_val.struct) == 0


def test_spread_nested_field():
    """Spread operator can access nested fields"""
    code = """
    !func |test-func ~_ = {
        copy = {..$ctx.database.settings}
    }
    """

    ast_module = comp.parse_module(code)
    module = run.Module("test")
    module.process_ast(ast_module)
    module.resolve_all()

    func_def = module.funcs["test-func"]

    ctx_val = run.Value({
        "database": {
            "settings": {
                "pool_size": 10,
                "timeout": 5000
            }
        }
    })

    result = run.invoke(func_def, module, run.Value({}), ctx_val, run.Value({}), run.Value({}))

    assert result.is_struct
    copy = result.struct[run.Value("copy")]
    assert copy.is_struct
    assert copy.struct[run.Value("pool_size")].to_python() == 10
    assert copy.struct[run.Value("timeout")].to_python() == 5000


def test_multiple_spreads():
    """Multiple spread operators can be used sequentially"""
    code = """
    !func |test-func ~_ = {
        first = {a=1}
        second = {b=2}
        combined = {..first ..second}
    }
    """

    ast_module = comp.parse_module(code)
    module = run.Module("test")
    module.process_ast(ast_module)
    module.resolve_all()

    func_def = module.funcs["test-func"]

    result = run.invoke(func_def, module, run.Value({}), run.Value({}), run.Value({}), run.Value({}))

    assert result.is_struct
    combined = result.struct[run.Value("combined")]
    assert combined.is_struct
    # Should have fields from both spreads
    assert combined.struct[run.Value("a")].to_python() == 1
    assert combined.struct[run.Value("b")].to_python() == 2


def test_spread_from_chained_scope():
    """Spread operator works with chained scope (^)"""
    code = """
    !func |test-func ~_ = {
        result = {..^}
    }
    """

    ast_module = comp.parse_module(code)
    module = run.Module("test")
    module.process_ast(ast_module)
    module.resolve_all()

    func_def = module.funcs["test-func"]

    arg_val = run.Value({"from_arg": "arg_value"})
    ctx_val = run.Value({"from_ctx": "ctx_value"})
    mod_val = run.Value({"from_mod": "mod_value"})

    result = run.invoke(func_def, module, run.Value({}), ctx_val, mod_val, arg_val)

    assert result.is_struct
    result_val = result.struct[run.Value("result")]
    assert result_val.is_struct

    # Chained scope prioritizes arg, then ctx, then mod
    # All should be present in the spread
    assert result_val.struct[run.Value("from_arg")].to_python() == "arg_value"
    assert result_val.struct[run.Value("from_ctx")].to_python() == "ctx_value"
    assert result_val.struct[run.Value("from_mod")].to_python() == "mod_value"
