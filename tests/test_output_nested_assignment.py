"""
Test nested field assignment in function output scope
"""

import comp
from comp import run


def test_simple_nested_field():
    """Test that nested fields create intermediate structures"""
    code = """
    !func |test-func ~_ = {
        parent.child = 12
    }
    """

    ast_module = comp.parse_module(code)
    module = run.Module("test")
    module.process_ast(ast_module)
    module.resolve_all()

    func_def = module.funcs["test-func"]

    result = run.invoke(func_def, module, run.Value({}), run.Value({}), run.Value({}), run.Value({}))

    assert result.is_struct
    # Should have created parent structure
    parent = result.struct[run.Value("parent")]
    assert parent.is_struct
    # parent should have child field
    child = parent.struct[run.Value("child")]
    assert child.to_python() == 12


def test_deeply_nested_field():
    """Test deeply nested field assignment"""
    code = """
    !func |test-func ~_ = {
        level1.level2.level3.value = 42
    }
    """

    ast_module = comp.parse_module(code)
    module = run.Module("test")
    module.process_ast(ast_module)
    module.resolve_all()

    func_def = module.funcs["test-func"]

    result = run.invoke(func_def, module, run.Value({}), run.Value({}), run.Value({}), run.Value({}))

    assert result.is_struct
    level1 = result.struct[run.Value("level1")]
    assert level1.is_struct
    level2 = level1.struct[run.Value("level2")]
    assert level2.is_struct
    level3 = level2.struct[run.Value("level3")]
    assert level3.is_struct
    value = level3.struct[run.Value("value")]
    assert value.to_python() == 42


def test_multiple_nested_fields():
    """Test multiple assignments to same nested structure"""
    code = """
    !func |test-func ~_ = {
        config.timeout = 30
        config.retries = 3
        config.host = "localhost"
    }
    """

    ast_module = comp.parse_module(code)
    module = run.Module("test")
    module.process_ast(ast_module)
    module.resolve_all()

    func_def = module.funcs["test-func"]

    result = run.invoke(func_def, module, run.Value({}), run.Value({}), run.Value({}), run.Value({}))

    assert result.is_struct
    config = result.struct[run.Value("config")]
    assert config.is_struct
    # All three fields should be present
    assert config.struct[run.Value("timeout")].to_python() == 30
    assert config.struct[run.Value("retries")].to_python() == 3
    assert config.struct[run.Value("host")].to_python() == "localhost"


def test_nested_and_flat_fields_mixed():
    """Test mixing nested and flat field assignments"""
    code = """
    !func |test-func ~_ = {
        simple = 1
        nested.value = 2
        another = 3
    }
    """

    ast_module = comp.parse_module(code)
    module = run.Module("test")
    module.process_ast(ast_module)
    module.resolve_all()

    func_def = module.funcs["test-func"]

    result = run.invoke(func_def, module, run.Value({}), run.Value({}), run.Value({}), run.Value({}))

    assert result.is_struct
    # Should have both flat and nested fields
    assert result.struct[run.Value("simple")].to_python() == 1
    assert result.struct[run.Value("another")].to_python() == 3
    nested = result.struct[run.Value("nested")]
    assert nested.is_struct
    assert nested.struct[run.Value("value")].to_python() == 2


def test_overwrite_nested_path():
    """Test that later assignments to same path override earlier ones"""
    code = """
    !func |test-func ~_ = {
        data.x = 10
        data.x = 20
    }
    """

    ast_module = comp.parse_module(code)
    module = run.Module("test")
    module.process_ast(ast_module)
    module.resolve_all()

    func_def = module.funcs["test-func"]

    result = run.invoke(func_def, module, run.Value({}), run.Value({}), run.Value({}), run.Value({}))

    assert result.is_struct
    data = result.struct[run.Value("data")]
    assert data.is_struct
    # Should have the last assigned value
    assert data.struct[run.Value("x")].to_python() == 20
