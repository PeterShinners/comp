"""Tests for standard library modules."""

import comp


def test_stdlib_string_module_exists():
    """Test that the string module can be loaded from stdlib."""
    from comp.stdlib import get_stdlib_module

    string_mod = get_stdlib_module("string")
    assert string_mod is not None
    assert isinstance(string_mod, comp.Module)


def test_string_upper():
    """Test string |upper function."""
    from comp.stdlib import get_stdlib_module

    string_mod = get_stdlib_module("string")

    # Get the upper function
    upper_funcs = string_mod.lookup_function(["upper"])
    assert upper_funcs is not None
    assert len(upper_funcs) > 0

    # Call the function through the engine
    engine = comp.Engine()
    dummy_node = comp.ast.Number(0)
    frame = comp._engine._Frame(dummy_node, None, {}, False, engine)

    # Get the Python function from the FunctionDefinition
    func_def = upper_funcs[0]
    py_func = func_def.body  # Should be a PythonFunction

    result = py_func(frame, comp.Value("hello"), None)
    # Python functions now return structs, so extract scalar
    assert result.as_scalar().data == "HELLO"


def test_string_lower():
    """Test string |lower function."""
    from comp.stdlib import get_stdlib_module

    string_mod = get_stdlib_module("string")
    lower_funcs = string_mod.lookup_function(["lower"])

    engine = comp.Engine()
    dummy_node = comp.ast.Number(0)
    frame = comp._engine._Frame(dummy_node, None, {}, False, engine)

    func_def = lower_funcs[0]
    py_func = func_def.body

    result = py_func(frame, comp.Value("HELLO"), None)
    # Python functions now return structs, so extract scalar
    assert result.as_scalar().data == "hello"


def test_string_split():
    """Test string |split function."""
    from comp.stdlib import get_stdlib_module

    string_mod = get_stdlib_module("string")
    split_funcs = string_mod.lookup_function(["split"])

    engine = comp.Engine()
    dummy_node = comp.ast.Number(0)
    frame = comp._engine._Frame(dummy_node, None, {}, False, engine)

    func_def = split_funcs[0]
    py_func = func_def.body

    # Test with separator argument
    args = comp.Value({
        comp.Value("sep"): comp.Value(",")
    })

    result = py_func(frame, comp.Value("a,b,c"), args)
    # Result is a struct with Unnamed keys (lists are represented as structs)
    assert result.is_struct
    assert len(result.data) == 3
    # Get values from the struct
    values = list(result.data.values())
    assert values[0].data == "a"
    assert values[1].data == "b"
    assert values[2].data == "c"


def test_string_import_stdlib():
    """Test importing string module via !import statement."""
    engine = comp.Engine()

    source = '''
!import /str = stdlib "string"
'''

    module_ast = comp.parse_module(source)
    module = engine.run(module_ast)

    # Check that the import was registered
    assert "str" in module.namespaces
    string_mod = module.namespaces["str"]
    assert isinstance(string_mod, comp.Module)

    # Verify functions are available
    upper_funcs = string_mod.lookup_function(["upper"])
    assert upper_funcs is not None


def test_string_length():
    """Test string |length function."""
    from comp.stdlib import get_stdlib_module
    from decimal import Decimal

    string_mod = get_stdlib_module("string")
    length_funcs = string_mod.lookup_function(["length"])

    engine = comp.Engine()
    dummy_node = comp.ast.Number(0)
    frame = comp._engine._Frame(dummy_node, None, {}, False, engine)

    func_def = length_funcs[0]
    py_func = func_def.body

    result = py_func(frame, comp.Value("hello"), None)
    # Python functions now return structs, so extract scalar
    assert result.as_scalar().data == Decimal("5")


def test_string_replace():
    """Test string |replace function."""
    from comp.stdlib import get_stdlib_module

    string_mod = get_stdlib_module("string")
    replace_funcs = string_mod.lookup_function(["replace"])

    engine = comp.Engine()
    dummy_node = comp.ast.Number(0)
    frame = comp._engine._Frame(dummy_node, None, {}, False, engine)

    func_def = replace_funcs[0]
    py_func = func_def.body

    args = comp.Value({
        comp.Value("old"): comp.Value("l"),
        comp.Value("new"): comp.Value("r")
    })

    result = py_func(frame, comp.Value("hello"), args)
    # Python functions now return structs, so extract scalar
    assert result.as_scalar().data == "herro"


def test_string_startswith():
    """Test string |startswith function."""
    from comp.stdlib import get_stdlib_module

    string_mod = get_stdlib_module("string")
    startswith_funcs = string_mod.lookup_function(["startswith"])

    engine = comp.Engine()
    dummy_node = comp.ast.Number(0)
    frame = comp._engine._Frame(dummy_node, None, {}, False, engine)

    func_def = startswith_funcs[0]
    py_func = func_def.body

    args = comp.Value({
        comp.Value("prefix"): comp.Value("he")
    })

    result = py_func(frame, comp.Value("hello"), args)
    # Python functions now return structs, so extract scalar
    assert result.as_scalar().data == comp.TRUE


def test_string_strip():
    """Test string |strip function."""
    from comp.stdlib import get_stdlib_module

    string_mod = get_stdlib_module("string")
    strip_funcs = string_mod.lookup_function(["strip"])

    engine = comp.Engine()
    dummy_node = comp.ast.Number(0)
    frame = comp._engine._Frame(dummy_node, None, {}, False, engine)

    func_def = strip_funcs[0]
    py_func = func_def.body

    result = py_func(frame, comp.Value("  hello  "), None)
    # Python functions now return structs, so extract scalar
    assert result.as_scalar().data == "hello"
