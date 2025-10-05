"""
Test nested field access on scoped identifiers
"""

import comp
from comp import run


def test_nested_identifier_access():
    """Test that nested fields can be accessed from scopes"""
    code = """
    !func |test-func ~_ = {
        value = $mod.parent.child
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
    value = result.struct[run.Value("value")]
    assert value.to_python() == 11


def test_deeply_nested_identifier():
    """Test deeply nested field access"""
    code = """
    !func |test-func ~_ = {
        value = $ctx.level1.level2.level3.data
    }
    """

    ast_module = comp.parse_module(code)
    module = run.Module("test")
    module.process_ast(ast_module)
    module.resolve_all()

    func_def = module.funcs["test-func"]
    
    # Create deeply nested structure
    ctx_val = run.Value({
        "level1": run.Value({
            "level2": run.Value({
                "level3": run.Value({
                    "data": "found it!"
                })
            })
        })
    })

    result = run.invoke(func_def, module, run.Value({}), ctx_val, run.Value({}), run.Value({}))

    assert result.is_struct
    value = result.struct[run.Value("value")]
    assert value.to_python() == "found it!"


def test_nested_from_chained_scope():
    """Test nested field access from chained scope (^)"""
    code = """
    !func |test-func ~_ = {
        value = ^config.timeout
    }
    """

    ast_module = comp.parse_module(code)
    module = run.Module("test")
    module.process_ast(ast_module)
    module.resolve_all()

    func_def = module.funcs["test-func"]
    
    # Put config in $arg (highest priority in chained scope)
    arg_val = run.Value({"config": run.Value({"timeout": 30})})

    result = run.invoke(func_def, module, run.Value({}), run.Value({}), run.Value({}), arg_val)

    assert result.is_struct
    value = result.struct[run.Value("value")]
    assert value.to_python() == 30


def test_nested_from_local_scope():
    """Test nested field access from local scope (@)"""
    code = """
    !func |test-func ~_ = {
        @settings = {port = 8080}
        value = @settings.port
    }
    """

    ast_module = comp.parse_module(code)
    module = run.Module("test")
    module.process_ast(ast_module)
    module.resolve_all()

    func_def = module.funcs["test-func"]

    result = run.invoke(func_def, module, run.Value({}), run.Value({}), run.Value({}), run.Value({}))

    assert result.is_struct
    value = result.struct[run.Value("value")]
    assert value.to_python() == 8080


def test_spread_nested_field():
    """Test spread operator with nested field access"""
    code = """
    !func |test-func ~_ = {
        result = {..$ctx.server.defaults}
    }
    """

    ast_module = comp.parse_module(code)
    module = run.Module("test")
    module.process_ast(ast_module)
    module.resolve_all()

    func_def = module.funcs["test-func"]
    
    ctx_val = run.Value({
        "server": run.Value({
            "defaults": run.Value({
                "host": "localhost",
                "port": 3000
            })
        })
    })

    result = run.invoke(func_def, module, run.Value({}), ctx_val, run.Value({}), run.Value({}))

    assert result.is_struct
    result_val = result.struct[run.Value("result")]
    assert result_val.is_struct
    assert result_val.struct[run.Value("host")].to_python() == "localhost"
    assert result_val.struct[run.Value("port")].to_python() == 3000
