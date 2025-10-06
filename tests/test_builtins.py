"""Test builtin functions from _builtin.py."""

import comp
from comp import run


def test_builtin_tags():
    """Test that builtin module is accessible via namespace."""
    module = run.Module("test")
    module.process_builtins()

    # Check that builtin module is registered
    assert "builtin" in module.mods
    builtin_mod = module.mods["builtin"]

    # Check that builtin tags exist in the builtin module
    assert "true" in builtin_mod.tags
    assert "false" in builtin_mod.tags
    assert "skip" in builtin_mod.tags
    assert "break" in builtin_mod.tags

    # Check that they have values
    assert builtin_mod.tags["true"].value is not None
    assert builtin_mod.tags["false"].value is not None
    assert builtin_mod.tags["skip"].value is not None
    assert builtin_mod.tags["break"].value is not None


def test_builtin_tags_are_singletons():
    """Test that builtin tags are singleton instances across modules."""
    from comp.run import _builtin

    # Create two separate modules
    module1 = run.Module("test1")
    module2 = run.Module("test2")

    module1.process_builtins()
    module2.process_builtins()

    # Both modules should reference the same builtin module
    assert module1.mods["builtin"] is module2.mods["builtin"]

    # Extract the Tag instances from the builtin module
    builtin_mod = module1.mods["builtin"]
    true_tag1 = builtin_mod.tags["true"].value.tag
    true_tag2 = module2.mods["builtin"].tags["true"].value.tag

    # They should be the SAME instance (identity equality)
    assert true_tag1 is true_tag2
    assert true_tag1 is _builtin.true

    # Same for false
    false_tag1 = builtin_mod.tags["false"].value.tag
    false_tag2 = module2.mods["builtin"].tags["false"].value.tag
    assert false_tag1 is false_tag2
    assert false_tag1 is _builtin.false


def test_builtin_print():
    """Test the builtin print function."""
    module = run.Module("test")
    module.process_builtins()

    # Create a Comp function that uses builtin print
    code = """
    !func |test ~_ = {
        value = [{x=5} |print |{result = x * 2}]
    }
    """

    ast_module = comp.parse_module(code)
    module.process_ast(ast_module)
    module.resolve_all()

    # Invoke the test function
    func_def = module.funcs["test"]
    result = run.invoke(func_def, module, run.Value({}), run.Value({}), run.Value({}), run.Value({}))

    assert result.is_struct
    assert result.struct[run.Value("value")].is_struct
    assert result.struct[run.Value("value")].struct[run.Value("result")].to_python() == 10


def test_builtin_double():
    """Test the builtin double function."""
    module = run.Module("test")
    module.process_builtins()

    # Test doubling a numeric field
    code = """
    !func |test ~_ = {
        value = [{x=7} |double]
    }
    """

    ast_module = comp.parse_module(code)
    module.process_ast(ast_module)
    module.resolve_all()

    # Invoke the test function
    func_def = module.funcs["test"]
    result = run.invoke(func_def, module, run.Value({}), run.Value({}), run.Value({}), run.Value({}))

    assert result.is_struct
    assert result.struct[run.Value("value")].is_struct
    assert result.struct[run.Value("value")].struct[run.Value("x")].to_python() == 14


def test_builtin_upper():
    """Test the builtin upper function."""
    module = run.Module("test")
    module.process_builtins()

    # Test uppercasing a string
    code = """
    !func |test ~_ = {
        value = ["hello" |upper]
    }
    """

    ast_module = comp.parse_module(code)
    module.process_ast(ast_module)
    module.resolve_all()

    # Invoke the test function
    func_def = module.funcs["test"]
    result = run.invoke(func_def, module, run.Value({}), run.Value({}), run.Value({}), run.Value({}))

    assert result.is_struct
    assert result.struct[run.Value("value")].to_python() == "HELLO"


def test_builtin_lower():
    """Test the builtin lower function."""
    module = run.Module("test")
    module.process_builtins()

    # Test lowercasing a string
    code = """
    !func |test ~_ = {
        value = ["WORLD" |lower]
    }
    """

    ast_module = comp.parse_module(code)
    module.process_ast(ast_module)
    module.resolve_all()

    # Invoke the test function
    func_def = module.funcs["test"]
    result = run.invoke(func_def, module, run.Value({}), run.Value({}), run.Value({}), run.Value({}))

    assert result.is_struct
    assert result.struct[run.Value("value")].to_python() == "world"


def test_builtin_pipeline_chain():
    """Test chaining multiple builtin functions."""
    module = run.Module("test")
    module.process_builtins()

    # Chain upper and lower
    code = """
    !func |test ~_ = {
        value = ["Hello" |upper |lower |upper]
    }
    """

    ast_module = comp.parse_module(code)
    module.process_ast(ast_module)
    module.resolve_all()

    # Invoke the test function
    func_def = module.funcs["test"]
    result = run.invoke(func_def, module, run.Value({}), run.Value({}), run.Value({}), run.Value({}))

    assert result.is_struct
    assert result.struct[run.Value("value")].to_python() == "HELLO"
