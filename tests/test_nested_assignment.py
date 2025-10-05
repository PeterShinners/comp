"""
FUTURE: Test nested field assignment to SCOPED variables ($ctx, $mod, @, etc.)

These tests are NOT YET IMPLEMENTED. They test assignment to nested paths
within scopes like $mod.parent.child = 12 or @data.x = 10.

Currently only unscoped nested assignment works (e.g., parent.child = 12).
See test_output_nested_assignment.py for working tests.
"""

import comp
from comp import run


def _test_nested_assignment():
    """FUTURE: Test that nested fields can be assigned to $mod"""
    code = """
    !func |test-func ~_ = {
        $mod.parent.child = 12
        result = $mod
    }
    """

    ast_module = comp.parse_module(code)
    module = run.Module("test")
    module.process_ast(ast_module)
    module.resolve_all()

    func_def = module.funcs["test-func"]
    
    # Create nested structure in $mod
    mod_val = run.Value({"parent": run.Value({"child": 11})})

    result = run.invoke(func_def, module, run.Value({}), run.Value({}), mod_val, run.Value({}))

    assert result.is_struct
    result_val = result.struct[run.Value("result")]
    assert result_val.is_struct
    
    # Check if the nested value was modified
    parent = result_val.struct[run.Value("parent")]
    assert parent.is_struct
    child = parent.struct[run.Value("child")]
    assert child.to_python() == 12  # Should be updated from 11 to 12


def _test_nested_assignment_creates_intermediate():
    """FUTURE: Test that nested assignment to $ctx creates intermediate structures"""
    code = """
    !func |test-func ~_ = {
        $ctx.new.nested.value = 42
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
    
    # Check if intermediate structures were created
    new = result_val.struct[run.Value("new")]
    assert new.is_struct
    nested = new.struct[run.Value("nested")]
    assert nested.is_struct
    value = nested.struct[run.Value("value")]
    assert value.to_python() == 42


def _test_multiple_nested_assignments():
    """FUTURE: Test multiple nested assignments to $ctx"""
    code = """
    !func |test-func ~_ = {
        $ctx.config.timeout = 30
        $ctx.config.retries = 3
        $ctx.config.host = "localhost"
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


def _test_nested_assignment_to_local():
    """FUTURE: Test nested assignment to @local scope"""
    code = """
    !func |test-func ~_ = {
        @data.x = 10
        @data.y = 20
        result = @data
    }
    """

    ast_module = comp.parse_module(code)
    module = run.Module("test")
    module.process_ast(ast_module)
    module.resolve_all()

    func_def = module.funcs["test-func"]

    result = run.invoke(func_def, module, run.Value({}), run.Value({}), run.Value({}), run.Value({}))

    assert result.is_struct
    data = result.struct[run.Value("result")]
    assert data.is_struct
    assert data.struct[run.Value("x")].to_python() == 10
    assert data.struct[run.Value("y")].to_python() == 20
