"""Test computed field access and assignment.

ComputeField uses single quotes to evaluate an expression as the field name.
Example: data.'4+4' uses the number 8 as the field name.
"""

import comp
from comp import run


def test_compute_field_number():
    """Test computed field with numeric result."""
    code = """
    !func |test-func ~_ = {
        data = {
            '4+4' = "eight"
        }
        result = data.'4+4'
    }
    """

    ast_module = comp.parse_module(code)
    module = run.Module("test")
    module.process_ast(ast_module)
    module.resolve_all()

    func_def = module.funcs["test-func"]

    result = run.invoke(func_def, module, run.Value({}), run.Value({}), run.Value({}), run.Value({}))

    assert result.is_struct
    assert result.struct[run.Value("result")].to_python() == "eight"


def test_compute_field_string():
    """Test computed field with string result."""
    code = """
    !func |test-func ~_ = {
        data = {
            '"computed"' = "value"
        }
        result = data.'"computed"'
    }
    """

    ast_module = comp.parse_module(code)
    module = run.Module("test")
    module.process_ast(ast_module)
    module.resolve_all()

    func_def = module.funcs["test-func"]

    result = run.invoke(func_def, module, run.Value({}), run.Value({}), run.Value({}), run.Value({}))

    assert result.is_struct
    assert result.struct[run.Value("result")].to_python() == "value"


def test_compute_field_nested():
    """Test nested computed fields."""
    code = """
    !func |test-func ~_ = {
        outer = {
            '"inner"' = {
                '42' = "answer"
            }
        }
        result = outer.'"inner"'.'42'
    }
    """

    ast_module = comp.parse_module(code)
    module = run.Module("test")
    module.process_ast(ast_module)
    module.resolve_all()

    func_def = module.funcs["test-func"]

    result = run.invoke(func_def, module, run.Value({}), run.Value({}), run.Value({}), run.Value({}))

    assert result.is_struct
    assert result.struct[run.Value("result")].to_python() == "answer"


def test_compute_field_assignment():
    """Test assigning to computed field."""
    code = """
    !func |test-func ~_ = {
        data = {}
        data.'2*3' = "six"
        result = data.'6'
    }
    """

    ast_module = comp.parse_module(code)
    module = run.Module("test")
    module.process_ast(ast_module)
    module.resolve_all()

    func_def = module.funcs["test-func"]

    result = run.invoke(func_def, module, run.Value({}), run.Value({}), run.Value({}), run.Value({}))

    assert result.is_struct
    assert result.struct[run.Value("result")].to_python() == "six"


def test_compute_field_nested_assignment():
    """Test nested assignment with computed fields."""
    code = """
    !func |test-func ~_ = {
        outer.'10+10'.inner = "nested"
        result = outer.'20'.inner
    }
    """

    ast_module = comp.parse_module(code)
    module = run.Module("test")
    module.process_ast(ast_module)
    module.resolve_all()

    func_def = module.funcs["test-func"]

    result = run.invoke(func_def, module, run.Value({}), run.Value({}), run.Value({}), run.Value({}))

    assert result.is_struct
    assert result.struct[run.Value("result")].to_python() == "nested"


def test_compute_field_mixed_types():
    """Test computed fields mixed with other field types."""
    code = """
    !func |test-func ~_ = {
        data = {
            first = {
                '"Hello, World!"' = {
                    '0' = "zero"
                    '1' = "one"
                }
            }
        }
        result = data.first.'"Hello, World!"'.'0'
    }
    """

    ast_module = comp.parse_module(code)
    module = run.Module("test")
    module.process_ast(ast_module)
    module.resolve_all()

    func_def = module.funcs["test-func"]

    result = run.invoke(func_def, module, run.Value({}), run.Value({}), run.Value({}), run.Value({}))

    assert result.is_struct
    assert result.struct[run.Value("result")].to_python() == "zero"


def test_compute_field_in_expression():
    """Test computed field in structure expression."""
    code = """
    !func |test-func ~_ = {
        result = {
            person.'100+1' = "Alice"
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
    result_struct = result.struct[run.Value("result")]
    person_struct = result_struct.struct[run.Value("person")]
    assert person_struct.struct[run.Value(101)].to_python() == "Alice"

