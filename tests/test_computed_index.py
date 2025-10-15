"""Tests for computed index field access."""
import comp


def test_literal_index_access():
    """Test data.#1 - literal positional index"""
    engine = comp.Engine()
    code = """
    !func |test ~{} = {
        data = {10 20 30}
        result = data.#1
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


def test_computed_index_from_variable():
    """Test data.#(@index) - computed index from variable"""
    engine = comp.Engine()
    code = """
    !func |test ~{} = {
        @index = 2
        data = {10 20 30 40}
        result = data.#(@index)
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
    assert result.struct[comp.Value('result')].data == 30


def test_computed_index_from_expression():
    """Test data.#(@index + 1) - computed index from expression"""
    engine = comp.Engine()
    code = """
    !func |test ~{} = {
        @index = 1
        data = {10 20 30 40 50}
        result = data.#(@index + 1)
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
    assert result.struct[comp.Value('result')].data == 30


def test_computed_index_equivalence():
    """Test that data.#(1) is equivalent to data.#1"""
    engine = comp.Engine()
    code = """
    !func |test ~{} = {
        data = {10 20 30}
        literal = data.#1
        computed = data.#(1)
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
    literal_val = result.struct[comp.Value('literal')].data
    computed_val = result.struct[comp.Value('computed')].data
    assert literal_val == computed_val == 20


def test_computed_index_out_of_bounds():
    """Test that out of bounds computed index fails gracefully"""
    engine = comp.Engine()
    code = """
    !func |test ~{} = {
        @index = 10
        data = {10 20 30}
        result = data.#(@index)
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

    assert engine.is_fail(result)
    assert "out of bounds" in str(result.struct[comp.Value('message')])


def test_computed_index_non_numeric():
    """Test that non-numeric computed index fails gracefully"""
    engine = comp.Engine()
    code = """
    !func |test ~{} = {
        @index = "not-a-number"
        data = {10 20 30}
        result = data.#(@index)
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

    assert engine.is_fail(result)
    assert "must evaluate to a number" in str(result.struct[comp.Value('message')])
