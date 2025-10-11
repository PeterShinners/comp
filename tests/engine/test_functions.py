"""Test function system."""

import comp.engine as comp


def test_builtin_double():
    """Test |double function."""
    engine = comp.Engine()

    result = engine.call_function("double", comp.Value(5))
    assert result == comp.Value(10)


def test_builtin_print():
    """Test |print function (passes through)."""
    engine = comp.Engine()

    result = engine.call_function("print", comp.Value(42))
    assert result == comp.Value(42)


def test_builtin_identity():
    """Test |identity function."""
    engine = comp.Engine()

    result = engine.call_function("identity", comp.Value("hello"))
    assert result == comp.Value("hello")


def test_builtin_add():
    """Test |add function with arguments."""
    engine = comp.Engine()

    # |add requires ^{n=...} argument
    args = comp.Value({comp.Value("n"): comp.Value(3)})
    result = engine.call_function("add", comp.Value(5), args)
    assert result == comp.Value(8)


def test_builtin_wrap():
    """Test |wrap function."""
    engine = comp.Engine()

    # |wrap requires ^{key=...} argument
    args = comp.Value({comp.Value("key"): comp.Value("x")})
    result = engine.call_function("wrap", comp.Value(5), args)

    assert result.is_struct
    assert result.struct[comp.Value("x")] == comp.Value(5)


def test_function_not_found():
    """Test calling non-existent function."""
    engine = comp.Engine()

    result = engine.call_function("nonexistent", comp.Value(5))
    assert result.tag and result.tag.name == "fail"


def test_custom_python_function():
    """Test registering custom Python function."""
    engine = comp.Engine()

    def triple(engine, input_value, args):
        if not input_value.is_number:
            return engine.fail("triple expects number")
        return comp.Value(input_value.data * 3)

    # Register custom function
    engine.register_function(comp.PythonFunction("triple", triple))

    # Call it
    result = engine.call_function("triple", comp.Value(4))
    assert result == comp.Value(12)


def test_function_with_wrong_input_type():
    """Test function with wrong input type."""
    engine = comp.Engine()

    # |double expects number
    result = engine.call_function("double", comp.Value("not a number"))
    assert result.tag and result.tag.name == "fail"


def test_function_missing_required_arg():
    """Test function with missing required argument."""
    engine = comp.Engine()

    # |add requires ^{n=...}
    result = engine.call_function("add", comp.Value(5), None)
    assert result.tag and result.tag.name == "fail"
    print("✓ Missing argument handling works")

