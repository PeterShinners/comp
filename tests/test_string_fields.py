"""Test string field access and assignment (data."field name")."""

import comp
from comp import run


def test_string_field_access():
    """Test accessing fields with string keys."""
    code = """
    !func |test-func ~_ = {
        data = $in
        result = data."Hello, World!"
    }
    """

    ast_module = comp.parse_module(code)
    module = run.Module("test")
    module.process_ast(ast_module)
    module.resolve_all()

    func_def = module.funcs["test-func"]

    # Create input with a string key
    input_val = run.Value({"Hello, World!": 42, "normal": 100})

    result = run.invoke(func_def, module, input_val, run.Value({}), run.Value({}), run.Value({}))

    assert result.is_struct
    assert result.struct[run.Value("result")].to_python() == 42


def test_string_field_assignment():
    """Test assigning to fields with string keys."""
    code = """
    !func |test-func ~_ = {
        data = {normal=1}
        data."special-key" = 99
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
    assert data.struct[run.Value("normal")].to_python() == 1
    assert data.struct[run.Value("special-key")].to_python() == 99


def test_string_field_nested_access():
    """Test nested string field access."""
    code = """
    !func |test-func ~_ = {
        data = $in
        result = data.parent."child-key"
    }
    """

    ast_module = comp.parse_module(code)
    module = run.Module("test")
    module.process_ast(ast_module)
    module.resolve_all()

    func_def = module.funcs["test-func"]

    # Create nested input
    input_val = run.Value({
        "parent": run.Value({"child-key": 123, "other": 456})
    })

    result = run.invoke(func_def, module, input_val, run.Value({}), run.Value({}), run.Value({}))

    assert result.is_struct
    assert result.struct[run.Value("result")].to_python() == 123


def test_string_field_nested_assignment():
    """Test nested string field assignment."""
    code = """
    !func |test-func ~_ = {
        data = {parent={}}
        data.parent."new-field" = 77
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
    parent = data.struct[run.Value("parent")]
    assert parent.struct[run.Value("new-field")].to_python() == 77


def test_string_field_scoped():
    """Test string fields in scoped contexts."""
    code = """
    !func |test-func ~_ = {
        result = $in."special key"
    }
    """

    ast_module = comp.parse_module(code)
    module = run.Module("test")
    module.process_ast(ast_module)
    module.resolve_all()

    func_def = module.funcs["test-func"]

    input_val = run.Value({"special key": 999})

    result = run.invoke(func_def, module, input_val, run.Value({}), run.Value({}), run.Value({}))

    assert result.is_struct
    assert result.struct[run.Value("result")].to_python() == 999


def test_string_field_with_spaces():
    """Test string fields with spaces and special characters."""
    code = """
    !func |test-func ~_ = {
        data = $in
        a = data."first name"
        b = data."last-name"
        c = data."email@address"
    }
    """

    ast_module = comp.parse_module(code)
    module = run.Module("test")
    module.process_ast(ast_module)
    module.resolve_all()

    func_def = module.funcs["test-func"]

    input_val = run.Value({
        "first name": "John",
        "last-name": "Doe",
        "email@address": "john@example.com"
    })

    result = run.invoke(func_def, module, input_val, run.Value({}), run.Value({}), run.Value({}))

    assert result.is_struct
    assert result.struct[run.Value("a")].to_python() == "John"
    assert result.struct[run.Value("b")].to_python() == "Doe"
    assert result.struct[run.Value("c")].to_python() == "john@example.com"


def test_string_field_mixed_with_index():
    """Test combining string fields with index fields."""
    code = """
    !func |test-func ~_ = {
        data = $in
        result = data.#0."nested-key"
    }
    """

    ast_module = comp.parse_module(code)
    module = run.Module("test")
    module.process_ast(ast_module)
    module.resolve_all()

    func_def = module.funcs["test-func"]

    # Create input with first element having a string key
    input_val = run.Value({
        "first": run.Value({"nested-key": 888})
    })

    result = run.invoke(func_def, module, input_val, run.Value({}), run.Value({}), run.Value({}))

    assert result.is_struct
    assert result.struct[run.Value("result")].to_python() == 888
