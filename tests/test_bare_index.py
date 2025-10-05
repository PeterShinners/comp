"""Test bare index field access (e.g., #0 instead of $in.#0)."""

import comp
from comp import run


def test_bare_index_field():
    """Test that bare #0 works to access positional field from unnamed scope."""
    code = """
    !func |test-func ~_ = {
        result = #0
    }
    """

    ast_module = comp.parse_module(code)
    module = run.Module("test")
    module.process_ast(ast_module)
    module.resolve_all()

    func_def = module.funcs["test-func"]

    # Create input with positional fields
    input_struct = run.Value(None)
    input_struct.struct = {
        run.Value("first"): run.Value(42),
        run.Value("second"): run.Value(100)
    }

    result = run.invoke(func_def, module, input_struct, run.Value({}), run.Value({}), run.Value({}))

    assert result.is_struct
    # #0 should get the first positional field (index 0)
    assert result.struct[run.Value("result")].to_python() == 42


def test_bare_index_field_multiple():
    """Test multiple bare index field accesses."""
    code = """
    !func |test-func ~_ = {
        first = #0
        second = #1
    }
    """

    ast_module = comp.parse_module(code)
    module = run.Module("test")
    module.process_ast(ast_module)
    module.resolve_all()

    func_def = module.funcs["test-func"]

    # Create input with positional fields
    input_struct = run.Value(None)
    input_struct.struct = {
        run.Value("a"): run.Value(10),
        run.Value("b"): run.Value(20),
        run.Value("c"): run.Value(30)
    }

    result = run.invoke(func_def, module, input_struct, run.Value({}), run.Value({}), run.Value({}))

    assert result.is_struct
    assert result.struct[run.Value("first")].to_python() == 10
    assert result.struct[run.Value("second")].to_python() == 20
