"""Test index field access (#0, #1, #2, etc.)."""

import comp
from comp import run


def test_index_access_unnamed_fields():
    """Test accessing unnamed fields by index."""
    code = """
    !func |test-func ~_ = {
        data = {10 20 30}
        first = data.#0
        second = data.#1
        third = data.#2
    }
    """

    ast_module = comp.parse_module(code)
    module = run.Module("test")
    module.process_ast(ast_module)
    module.resolve_all()

    func_def = module.funcs["test-func"]
    result = run.invoke(func_def, module, run.Value({}), run.Value({}), run.Value({}), run.Value({}))

    assert result.is_struct
    assert result.struct[run.Value("first")].to_python() == 10
    assert result.struct[run.Value("second")].to_python() == 20
    assert result.struct[run.Value("third")].to_python() == 30


def test_index_access_named_fields():
    """Test accessing named fields by index."""
    code = """
    !func |test-func ~_ = {
        data = {one=1 two=2 three=3}
        first = data.#0
        second = data.#1
        third = data.#2
    }
    """

    ast_module = comp.parse_module(code)
    module = run.Module("test")
    module.process_ast(ast_module)
    module.resolve_all()

    func_def = module.funcs["test-func"]
    result = run.invoke(func_def, module, run.Value({}), run.Value({}), run.Value({}), run.Value({}))

    assert result.is_struct
    assert result.struct[run.Value("first")].to_python() == 1
    assert result.struct[run.Value("second")].to_python() == 2
    assert result.struct[run.Value("third")].to_python() == 3


def test_index_access_mixed_fields():
    """Test accessing mixed named/unnamed fields by index."""
    code = """
    !func |test-func ~_ = {
        data = {one=1 2 three=3}
        first = data.#0
        second = data.#1
        third = data.#2
    }
    """

    ast_module = comp.parse_module(code)
    module = run.Module("test")
    module.process_ast(ast_module)
    module.resolve_all()

    func_def = module.funcs["test-func"]
    result = run.invoke(func_def, module, run.Value({}), run.Value({}), run.Value({}), run.Value({}))

    assert result.is_struct
    assert result.struct[run.Value("first")].to_python() == 1
    assert result.struct[run.Value("second")].to_python() == 2
    assert result.struct[run.Value("third")].to_python() == 3


def test_index_access_scoped():
    """Test accessing scoped struct fields by index."""
    code = """
    !func |test-func ~_ = {
        result = $in.#0
    }
    """

    ast_module = comp.parse_module(code)
    module = run.Module("test")
    module.process_ast(ast_module)
    module.resolve_all()

    func_def = module.funcs["test-func"]
    
    # Create input with fields
    input_val = run.Value({"first": 100, "second": 200})
    
    result = run.invoke(func_def, module, input_val, run.Value({}), run.Value({}), run.Value({}))

    assert result.is_struct
    # Should get the first field value (100)
    assert result.struct[run.Value("result")].to_python() == 100


def test_index_access_chained():
    """Test chained index access like data.#0.#1."""
    code = """
    !func |test-func ~_ = {
        data = {{10 20} {30 40}}
        result = data.#0.#1
    }
    """

    ast_module = comp.parse_module(code)
    module = run.Module("test")
    module.process_ast(ast_module)
    module.resolve_all()

    func_def = module.funcs["test-func"]
    result = run.invoke(func_def, module, run.Value({}), run.Value({}), run.Value({}), run.Value({}))

    assert result.is_struct
    # data#0 is {10 20}, then #1 is 20
    assert result.struct[run.Value("result")].to_python() == 20


def test_index_out_of_bounds():
    """Test that accessing out of bounds index raises an error."""
    code = """
    !func |test-func ~_ = {
        data = {10 20}
        result = data.#5
    }
    """

    ast_module = comp.parse_module(code)
    module = run.Module("test")
    module.process_ast(ast_module)
    module.resolve_all()

    func_def = module.funcs["test-func"]
    
    try:
        run.invoke(func_def, module, run.Value({}), run.Value({}), run.Value({}), run.Value({}))
        assert False, "Should have raised an error for out of bounds index"
    except (ValueError, IndexError):
        pass  # Expected
