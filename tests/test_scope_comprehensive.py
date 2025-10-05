"""
Comprehensive tests for all scope interactions
"""

import comp
from comp import run


def test_all_scopes_together():
    """Test interaction between $in, $out, unnamed, $ctx, $mod, $arg, ^, and @"""
    code = """
    !func |comprehensive ~_ = {
        @temp = 999
        first = $in.input_val
        second = first
        third = $ctx.context_val
        fourth = $mod.module_val
        fifth = $arg.argument_val
        sixth = ^combined
        seventh = @temp
        eighth = second
    }
    """

    ast_module = comp.parse_module(code)
    module = run.Module("test")
    module.process_ast(ast_module)
    module.resolve_all()

    func_def = module.funcs["comprehensive"]

    input_val = run.Value({"input_val": 100})
    ctx_val = run.Value({"context_val": 200})
    mod_val = run.Value({"module_val": 300})
    arg_val = run.Value({"argument_val": 400, "combined": 500})

    result = run.invoke(func_def, module, input_val, ctx_val, mod_val, arg_val)

    assert result.is_struct
    assert result.struct[run.Value("first")].to_python() == 100   # From $in
    assert result.struct[run.Value("second")].to_python() == 100  # From unnamed->$out (first)
    assert result.struct[run.Value("third")].to_python() == 200   # From $ctx
    assert result.struct[run.Value("fourth")].to_python() == 300  # From $mod
    assert result.struct[run.Value("fifth")].to_python() == 400   # From $arg
    assert result.struct[run.Value("sixth")].to_python() == 500   # From ^ ($arg overrides others)
    assert result.struct[run.Value("seventh")].to_python() == 999 # From @ (local)
    assert result.struct[run.Value("eighth")].to_python() == 100  # From unnamed->$out (second)


def test_chained_scope_priority_with_unnamed():
    """Test that ^ has proper priority and unnamed scope is independent"""
    code = """
    !func |priority ~_ = {
        value = 10
        from_unnamed = value
        from_chained = ^value
    }
    """

    ast_module = comp.parse_module(code)
    module = run.Module("test")
    module.process_ast(ast_module)
    module.resolve_all()

    func_def = module.funcs["priority"]

    # Set value in all scopes to see priority
    input_val = run.Value({"value": 1})
    ctx_val = run.Value({"value": 2})
    mod_val = run.Value({"value": 3})
    arg_val = run.Value({"value": 4})

    result = run.invoke(func_def, module, input_val, ctx_val, mod_val, arg_val)

    assert result.is_struct
    assert result.struct[run.Value("value")].to_python() == 10        # Set in $out
    assert result.struct[run.Value("from_unnamed")].to_python() == 10  # Gets from $out (priority)
    assert result.struct[run.Value("from_chained")].to_python() == 4   # Gets from $arg via ^


def test_out_scope_updates_incrementally():
    """Test that $out is updated as each field is added"""
    code = """
    !func |incremental ~_ = {
        a = 1
        b = $out.a
        c = $out.b
        d = $out.c
    }
    """

    ast_module = comp.parse_module(code)
    module = run.Module("test")
    module.process_ast(ast_module)
    module.resolve_all()

    func_def = module.funcs["incremental"]

    result = run.invoke(func_def, module, run.Value({}), run.Value({}), run.Value({}), run.Value({}))

    assert result.is_struct
    assert result.struct[run.Value("a")].to_python() == 1
    assert result.struct[run.Value("b")].to_python() == 1
    assert result.struct[run.Value("c")].to_python() == 1
    assert result.struct[run.Value("d")].to_python() == 1


def test_local_scope_not_in_output():
    """Test that @ (local) variables don't appear in output unless spread"""
    code = """
    !func |local-test ~_ = {
        @helper = 42
        result = @helper
    }
    """

    ast_module = comp.parse_module(code)
    module = run.Module("test")
    module.process_ast(ast_module)
    module.resolve_all()

    func_def = module.funcs["local-test"]

    result = run.invoke(func_def, module, run.Value({}), run.Value({}), run.Value({}), run.Value({}))

    assert result.is_struct
    # @helper should NOT be in the result
    assert run.Value("helper") not in result.struct
    # but result should have the value
    assert result.struct[run.Value("result")].to_python() == 42
