"""
Test scoped nested assignment via spread pattern
"""

import comp
from comp import run


def test_scoped_assignment_via_spread():
    """Test $mod.parent.child=14 pattern using $mod = {..$mod parent.child=14}"""
    code = """
    !func |test-func ~_ = {
        $mod = {..$mod parent.child = 14}
        result = $mod
    }
    """

    ast_module = comp.parse_module(code)
    module = run.Module("test")
    module.process_ast(ast_module)
    module.resolve_all()

    func_def = module.funcs["test-func"]

    # Start with nested structure in $mod
    mod_val = run.Value({"parent": run.Value({"child": 11})})

    result = run.invoke(func_def, module, run.Value({}), run.Value({}), mod_val, run.Value({}))

    assert result.is_struct
    result_val = result.struct[run.Value("result")]
    assert result_val.is_struct

    # Check if the nested value was modified
    parent = result_val.struct[run.Value("parent")]
    assert parent.is_struct
    child = parent.struct[run.Value("child")]
    assert child.to_python() == 14  # Should be updated from 11 to 14


def test_scoped_assignment_creates_path():
    """Test creating new nested path in scope via spread"""
    code = """
    !func |test-func ~_ = {
        $ctx = {..$ctx config.timeout = 30}
        result = $ctx
    }
    """

    ast_module = comp.parse_module(code)
    module = run.Module("test")
    module.process_ast(ast_module)
    module.resolve_all()

    func_def = module.funcs["test-func"]

    # Start with empty $ctx
    ctx_val = run.Value({})

    result = run.invoke(func_def, module, run.Value({}), ctx_val, run.Value({}), run.Value({}))

    assert result.is_struct
    result_val = result.struct[run.Value("result")]
    assert result_val.is_struct

    # Check if the nested structure was created
    config = result_val.struct[run.Value("config")]
    assert config.is_struct
    timeout = config.struct[run.Value("timeout")]
    assert timeout.to_python() == 30


def test_multiple_scoped_assignments():
    """Test multiple nested assignments to same scope"""
    code = """
    !func |test-func ~_ = {
        $ctx = {..$ctx config.timeout = 30}
        $ctx = {..$ctx config.retries = 3}
        $ctx = {..$ctx config.host = "localhost"}
        result = $ctx.config
    }
    """

    ast_module = comp.parse_module(code)
    module = run.Module("test")
    module.process_ast(ast_module)
    module.resolve_all()

    func_def = module.funcs["test-func"]

    ctx_val = run.Value({})

    result = run.invoke(func_def, module, run.Value({}), ctx_val, run.Value({}), run.Value({}))

    assert result.is_struct
    config = result.struct[run.Value("result")]
    assert config.is_struct

    # All three fields should be present
    assert config.struct[run.Value("timeout")].to_python() == 30
    assert config.struct[run.Value("retries")].to_python() == 3
    assert config.struct[run.Value("host")].to_python() == "localhost"


def test_local_scope_nested_via_spread():
    """Test nested assignment with spread in local scope"""
    code = """
    !func |test-func ~_ = {
        temp = {data.x = 10}
        temp2 = {..temp data.y = 20}
        result = temp2.data
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

    # Check nested structure
    x = result_val.struct[run.Value("x")]
    assert x.to_python() == 10
    y = result_val.struct[run.Value("y")]
    assert y.to_python() == 20
