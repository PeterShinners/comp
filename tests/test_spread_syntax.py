"""
Test spread operator syntax variations
"""

import comp
from comp import run


def test_spread_only():
    """Test spread without assignment"""
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

    assert result.is_struct
    result_inner = result.struct[run.Value("result")]
    assert result_inner.is_struct
    assert result_inner.struct[run.Value("host")].to_python() == "localhost"
    assert result_inner.struct[run.Value("port")].to_python() == 8080


def test_assignment_only():
    """Test assignment without spread"""
    code = """
    !func |test-func ~_ = {
        result = {port=100}
    }
    """

    ast_module = comp.parse_module(code)
    module = run.Module("test")
    module.process_ast(ast_module)
    module.resolve_all()

    func_def = module.funcs["test-func"]

    result = run.invoke(func_def, module, run.Value({}), run.Value({}), run.Value({}), run.Value({}))

    assert result.is_struct
    result_inner = result.struct[run.Value("result")]
    assert result_inner.is_struct
    assert result_inner.struct[run.Value("port")].to_python() == 100
