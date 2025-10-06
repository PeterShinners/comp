"""
Test spreading from local scope (@)
"""

import comp
from comp import run


def test_spread_local_basic():
    """Test spreading from local scope"""
    code = """
    !func |test-func ~_ = {
        @x = 10
        @y = 20
        result = {..@}
    }
    """

    ast_module = comp.parse_module(code)
    module = run.Module("test")
    module.process_ast(ast_module)
    module.resolve_all()

    func_def = module.funcs["test-func"]

    result = run.invoke(func_def, module, run.Value({}), run.Value({}), run.Value({}), run.Value({}))

    # Check what we got
    assert result.is_struct
    result_inner = result.struct[run.Value("result")]
    assert result_inner.is_struct

    # Should have x and y from local scope spread
    assert run.Value("x") in result_inner.struct
    assert run.Value("y") in result_inner.struct
    assert result_inner.struct[run.Value("x")].to_python() == 10
    assert result_inner.struct[run.Value("y")].to_python() == 20


def test_spread_empty_local():
    """Test spreading from empty local scope (at function start)"""
    code = """
    !func |test-func ~_ = {
        result = {..@}
    }
    """

    ast_module = comp.parse_module(code)
    module = run.Module("test")
    module.process_ast(ast_module)
    module.resolve_all()

    func_def = module.funcs["test-func"]

    result = run.invoke(func_def, module, run.Value({}), run.Value({}), run.Value({}), run.Value({}))

    # Check what we got
    assert result.is_struct
    result_inner = result.struct[run.Value("result")]
    assert result_inner.is_struct

    # Should be empty (@ is empty at function start)
    assert len(result_inner.struct) == 0


def test_spread_ctx():
    """Test spreading from $ctx"""
    code = """
    !func |test-func ~_ = {
        result = {..$ctx.server}
    }
    """

    ast_module = comp.parse_module(code)
    module = run.Module("test")
    module.process_ast(ast_module)
    module.resolve_all()

    func_def = module.funcs["test-func"]

    ctx_val = run.Value({"server": {"host": "localhost", "port": 8080}})

    result = run.invoke(func_def, module, run.Value({}), ctx_val, run.Value({}), run.Value({}))

    # Check what we got
    assert result.is_struct
    result_inner = result.struct[run.Value("result")]
    assert result_inner.is_struct

    # Should have fields from server
    assert run.Value("host") in result_inner.struct
    assert run.Value("port") in result_inner.struct
    assert result_inner.struct[run.Value("host")].to_python() == "localhost"
    assert result_inner.struct[run.Value("port")].to_python() == 8080
