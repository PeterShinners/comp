"""Test index field assignment (data.#0 = value)."""

import comp
from comp import run


def test_index_assignment_unnamed_fields():
    """Test assigning to unnamed fields by index."""
    code = """
    !func |test-func ~_ = {
        data = {10 20 30}
        data.#1 = 99
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

    # Check that order is preserved and value is updated
    values = list(data.struct.values())
    assert len(values) == 3
    assert values[0].to_python() == 10
    assert values[1].to_python() == 99  # Updated
    assert values[2].to_python() == 30


def test_index_assignment_named_fields():
    """Test assigning to named fields by index."""
    code = """
    !func |test-func ~_ = {
        data = {one=1 two=2 three=3}
        data.#1 = 99
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

    # Check that order is preserved, value is updated, and keys are unchanged
    items = list(data.struct.items())
    assert len(items) == 3
    assert items[0][0].to_python() == "one"
    assert items[0][1].to_python() == 1
    assert items[1][0].to_python() == "two"
    assert items[1][1].to_python() == 99  # Updated value
    assert items[2][0].to_python() == "three"
    assert items[2][1].to_python() == 3


def test_index_assignment_mixed_fields():
    """Test assigning to mixed named/unnamed fields by index."""
    code = """
    !func |test-func ~_ = {
        data = {one=1 2 three=3}
        data.#1 = 99
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

    # Check order preserved
    items = list(data.struct.items())
    assert len(items) == 3
    assert items[0][0].to_python() == "one"
    assert items[0][1].to_python() == 1
    # Second item is unnamed, value should be updated
    assert items[1][1].to_python() == 99
    assert items[2][0].to_python() == "three"
    assert items[2][1].to_python() == 3


def test_index_assignment_scoped():
    """Test indexed assignment in scoped contexts."""
    code = """
    !func |test-func ~_ = {
        $mod = {..$mod}
        $mod.#0 = 42
        result = $mod
    }
    """

    ast_module = comp.parse_module(code)
    module = run.Module("test")
    module.process_ast(ast_module)
    module.resolve_all()

    func_def = module.funcs["test-func"]

    # Start with a struct in $mod
    mod_val = run.Value({"first": 100, "second": 200})

    result = run.invoke(func_def, module, run.Value({}), run.Value({}), mod_val, run.Value({}))

    assert result.is_struct
    result_val = result.struct[run.Value("result")]
    assert result_val.is_struct

    # First field should be updated to 42
    items = list(result_val.struct.items())
    assert items[0][1].to_python() == 42


def test_index_assignment_nested():
    """Test nested indexed assignment like parent.#0.child = value."""
    code = """
    !func |test-func ~_ = {
        data = {{x=1} {y=2}}
        data.#0.x = 99
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

    # Get first element
    first = list(data.struct.values())[0]
    assert first.is_struct
    assert first.struct[run.Value("x")].to_python() == 99


def test_index_assignment_out_of_bounds():
    """Test that assigning to out of bounds index raises an error."""
    code = """
    !func |test-func ~_ = {
        data = {10 20}
        data.#5 = 99
    }
    """

    ast_module = comp.parse_module(code)
    module = run.Module("test")
    module.process_ast(ast_module)
    module.resolve_all()

    func_def = module.funcs["test-func"]

    try:
        run.invoke(func_def, module, run.Value({}), run.Value({}), run.Value({}), run.Value({}))
        raise AssertionError("Should have raised an error for out of bounds index")
    except (ValueError, IndexError):
        pass  # Expected
