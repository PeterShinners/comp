"""Tests for the |if builtin function."""
import comp


def test_if_with_true_tag():
    """Test [5 |if #true 10 20] → 10"""
    engine = comp.Engine()
    code = """
    !func |test ~{} = {
        result = [5 |if #true 10 20]
    }
    """
    module_ast = comp.parse_module(code)
    module = comp.Module()
    module.prepare(module_ast, engine)
    module_result = engine.run(module_ast, module=module)
    module = module_result

    test_funcs = module.lookup_function(["test"])
    test_func = test_funcs[0]

    result = engine.run(
        test_func.body,
        in_=comp.Value(None),
        arg=comp.Value({}),
        ctx=comp.Value({}),
        mod=comp.Value({}),
        local=comp.Value({}),
        module=module,
    )

    assert not engine.is_fail(result)
    assert result.struct[comp.Value('result')].data == 10


def test_if_with_false_tag():
    """Test [5 |if #false 10 20] → 20"""
    engine = comp.Engine()
    code = """
    !func |test ~{} = {
        result = [5 |if #false 10 20]
    }
    """
    module_ast = comp.parse_module(code)
    module = comp.Module()
    module.prepare(module_ast, engine)
    module_result = engine.run(module_ast, module=module)
    module = module_result

    test_funcs = module.lookup_function(["test"])
    test_func = test_funcs[0]

    result = engine.run(
        test_func.body,
        in_=comp.Value(None),
        arg=comp.Value({}),
        ctx=comp.Value({}),
        mod=comp.Value({}),
        local=comp.Value({}),
        module=module,
    )

    assert not engine.is_fail(result)
    assert result.struct[comp.Value('result')].data == 20


def test_if_without_else():
    """Test [5 |if #false 10] → 5 (returns input when no else branch)"""
    engine = comp.Engine()
    code = """
    !func |test ~{} = {
        result = [5 |if #false 10]
    }
    """
    module_ast = comp.parse_module(code)
    module = comp.Module()
    module.prepare(module_ast, engine)
    module_result = engine.run(module_ast, module=module)
    module = module_result

    test_funcs = module.lookup_function(["test"])
    test_func = test_funcs[0]

    result = engine.run(
        test_func.body,
        in_=comp.Value(None),
        arg=comp.Value({}),
        ctx=comp.Value({}),
        mod=comp.Value({}),
        local=comp.Value({}),
        module=module,
    )

    assert not engine.is_fail(result)
    result_value = result.struct[comp.Value('result')]
    # When condition is false and no else, should return input unchanged
    # Pipeline seeds create structures with unnamed fields, so [5 ...] creates {_: 5}
    assert result_value.is_struct
    unnamed_values = [v for k, v in result_value.struct.items() if isinstance(k, comp.Unnamed)]
    assert len(unnamed_values) == 1
    assert unnamed_values[0].data == 5


def test_if_passes_input_to_branches():
    """Test that branches receive $in from pipeline"""
    engine = comp.Engine()
    code = """
    !func |test ~{} = {
        result = [5 |if #true {double = $in * 2} {half = $in / 2}]
    }
    """
    module_ast = comp.parse_module(code)
    module = comp.Module()
    module.prepare(module_ast, engine)
    module_result = engine.run(module_ast, module=module)
    module = module_result

    test_funcs = module.lookup_function(["test"])
    test_func = test_funcs[0]

    result = engine.run(
        test_func.body,
        in_=comp.Value(None),
        arg=comp.Value({}),
        ctx=comp.Value({}),
        mod=comp.Value({}),
        local=comp.Value({}),
        module=module,
    )

    assert not engine.is_fail(result)
    result_val = result.struct[comp.Value('result')]
    assert result_val.struct[comp.Value('double')].data == 10  # 5 * 2
