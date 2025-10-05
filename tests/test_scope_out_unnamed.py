"""
Tests for $out scope and unnamed scope (chains $out -> $in)
"""

import comp
from comp import run


def test_out_scope_self_reference():
    """Test that $out allows referencing previously set fields"""
    code = """
    !func |test-func ~_ = {
        first = 10
        second = $out.first
        third = $out.second
    }
    """

    ast_module = comp.parse_module(code)
    module = run.Module("test")
    module.process_ast(ast_module)
    module.resolve_all()

    func_def = module.funcs["test-func"]

    result = run.invoke(func_def, module, run.Value({}), run.Value({}), run.Value({}), run.Value({}))

    # All fields should reference the first value
    assert result.is_struct
    assert result.struct[run.Value("first")].to_python() == 10
    assert result.struct[run.Value("second")].to_python() == 10
    assert result.struct[run.Value("third")].to_python() == 10


def test_unnamed_scope_from_out():
    """Test that unscoped identifiers read from $out first"""
    code = """
    !func |test-func ~_ = {
        cat = 100
        dog = cat
        pig = dog
    }
    """

    ast_module = comp.parse_module(code)
    module = run.Module("test")
    module.process_ast(ast_module)
    module.resolve_all()

    func_def = module.funcs["test-func"]

    result = run.invoke(func_def, module, run.Value({}), run.Value({}), run.Value({}), run.Value({}))

    # dog and pig should reference values from $out (previously set fields)
    assert result.is_struct
    assert result.struct[run.Value("cat")].to_python() == 100
    assert result.struct[run.Value("dog")].to_python() == 100
    assert result.struct[run.Value("pig")].to_python() == 100


def test_unnamed_scope_from_in():
    """Test that unscoped identifiers fall back to $in when not in $out"""
    code = """
    !func |test-func ~_ = {
        dog = cat
        pig = dog
    }
    """

    ast_module = comp.parse_module(code)
    module = run.Module("test")
    module.process_ast(ast_module)
    module.resolve_all()

    func_def = module.funcs["test-func"]

    # Pass cat in the input
    input_val = run.Value({"cat": "meow"})

    result = run.invoke(func_def, module, input_val, run.Value({}), run.Value({}), run.Value({}))

    # dog should get cat from $in, pig should get dog from $out
    assert result.is_struct
    assert result.struct[run.Value("dog")].to_python() == "meow"
    assert result.struct[run.Value("pig")].to_python() == "meow"


def test_unnamed_scope_out_overrides_in():
    """Test that $out values override $in values in unnamed scope"""
    code = """
    !func |test-func ~_ = {
        animal = "dog"
        result = animal
    }
    """

    ast_module = comp.parse_module(code)
    module = run.Module("test")
    module.process_ast(ast_module)
    module.resolve_all()

    func_def = module.funcs["test-func"]

    # Pass animal in input, but it should be overridden by $out
    input_val = run.Value({"animal": "cat"})

    result = run.invoke(func_def, module, input_val, run.Value({}), run.Value({}), run.Value({}))

    # result should get "dog" from $out, not "cat" from $in
    assert result.is_struct
    assert result.struct[run.Value("animal")].to_python() == "dog"
    assert result.struct[run.Value("result")].to_python() == "dog"


def test_demo_example():
    """Test the demo example from the spec"""
    code = """
    !func |demo ~_ = {
        dog = cat
        pig = dog
    }
    """

    ast_module = comp.parse_module(code)
    module = run.Module("test")
    module.process_ast(ast_module)
    module.resolve_all()

    func_def = module.funcs["demo"]

    # Pass cat="hello" in the input
    input_val = run.Value({"cat": "hello"})

    result = run.invoke(func_def, module, input_val, run.Value({}), run.Value({}), run.Value({}))

    # Both dog and pig should contain "hello"
    assert result.is_struct
    assert result.struct[run.Value("dog")].to_python() == "hello"
    assert result.struct[run.Value("pig")].to_python() == "hello"
