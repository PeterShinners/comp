"""
Test nested field assignment inside nested structures
"""

import comp
from comp import run


def test_nested_in_nested():
    """Test that nested assignments work inside structure values"""
    code = """
    !func |test-func ~_ = {
        grandparent = {parent.child = 13}
    }
    """

    ast_module = comp.parse_module(code)
    module = run.Module("test")
    module.process_ast(ast_module)
    module.resolve_all()

    func_def = module.funcs["test-func"]

    result = run.invoke(func_def, module, run.Value({}), run.Value({}), run.Value({}), run.Value({}))

    assert result.is_struct
    grandparent = result.struct[run.Value("grandparent")]
    assert grandparent.is_struct
    # Should have parent structure
    parent = grandparent.struct[run.Value("parent")]
    assert parent.is_struct
    # parent should have child
    child = parent.struct[run.Value("child")]
    assert child.to_python() == 13


def test_multiple_nested_in_nested():
    """Test multiple nested assignments in nested structure"""
    code = """
    !func |test-func ~_ = {
        root = {
            config.timeout = 30
            config.retries = 3
        }
    }
    """

    ast_module = comp.parse_module(code)
    module = run.Module("test")
    module.process_ast(ast_module)
    module.resolve_all()

    func_def = module.funcs["test-func"]

    result = run.invoke(func_def, module, run.Value({}), run.Value({}), run.Value({}), run.Value({}))

    assert result.is_struct
    root = result.struct[run.Value("root")]
    assert root.is_struct
    config = root.struct[run.Value("config")]
    assert config.is_struct
    assert config.struct[run.Value("timeout")].to_python() == 30
    assert config.struct[run.Value("retries")].to_python() == 3


def test_deeply_nested_in_nested():
    """Test deeply nested paths inside nested structures"""
    code = """
    !func |test-func ~_ = {
        outer = {
            inner.deep.value = 42
        }
    }
    """

    ast_module = comp.parse_module(code)
    module = run.Module("test")
    module.process_ast(ast_module)
    module.resolve_all()

    func_def = module.funcs["test-func"]

    result = run.invoke(func_def, module, run.Value({}), run.Value({}), run.Value({}), run.Value({}))

    assert result.is_struct
    outer = result.struct[run.Value("outer")]
    assert outer.is_struct
    inner = outer.struct[run.Value("inner")]
    assert inner.is_struct
    deep = inner.struct[run.Value("deep")]
    assert deep.is_struct
    value = deep.struct[run.Value("value")]
    assert value.to_python() == 42
