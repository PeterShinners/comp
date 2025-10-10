"""Test function system."""

from comp.engine.engine import Engine
from comp.engine.function import PythonFunction
from comp.engine.value import Value


def test_builtin_double():
    """Test |double function."""
    engine = Engine()

    result = engine.call_function("double", Value(5))
    assert result == Value(10)
    print("✓ |double works")


def test_builtin_print():
    """Test |print function (passes through)."""
    engine = Engine()

    result = engine.call_function("print", Value(42))
    assert result == Value(42)
    print("✓ |print works")


def test_builtin_identity():
    """Test |identity function."""
    engine = Engine()

    result = engine.call_function("identity", Value("hello"))
    assert result == Value("hello")
    print("✓ |identity works")


def test_builtin_add():
    """Test |add function with arguments."""
    engine = Engine()

    # |add requires ^{n=...} argument
    args = Value({Value("n"): Value(3)})
    result = engine.call_function("add", Value(5), args)
    assert result == Value(8)
    print("✓ |add works")


def test_builtin_wrap():
    """Test |wrap function."""
    engine = Engine()

    # |wrap requires ^{key=...} argument
    args = Value({Value("key"): Value("x")})
    result = engine.call_function("wrap", Value(5), args)

    assert result.is_struct
    assert result.struct[Value("x")] == Value(5)
    print("✓ |wrap works")


def test_function_not_found():
    """Test calling non-existent function."""
    engine = Engine()

    result = engine.call_function("nonexistent", Value(5))
    assert result.tag and result.tag.name == "fail"
    print("✓ Unknown function returns fail")


def test_custom_python_function():
    """Test registering custom Python function."""
    engine = Engine()

    def triple(engine, input_value, args):
        if not input_value.is_number:
            return engine.fail("triple expects number")
        return Value(input_value.data * 3)

    # Register custom function
    engine.register_function(PythonFunction("triple", triple))

    # Call it
    result = engine.call_function("triple", Value(4))
    assert result == Value(12)
    print("✓ Custom Python function works")


def test_function_with_wrong_input_type():
    """Test function with wrong input type."""
    engine = Engine()

    # |double expects number
    result = engine.call_function("double", Value("not a number"))
    assert result.tag and result.tag.name == "fail"
    print("✓ Function type checking works")


def test_function_missing_required_arg():
    """Test function with missing required argument."""
    engine = Engine()

    # |add requires ^{n=...}
    result = engine.call_function("add", Value(5), None)
    assert result.tag and result.tag.name == "fail"
    print("✓ Missing argument handling works")


if __name__ == "__main__":
    test_builtin_double()
    test_builtin_print()
    test_builtin_identity()
    test_builtin_add()
    test_builtin_wrap()
    test_function_not_found()
    test_custom_python_function()
    test_function_with_wrong_input_type()
    test_function_missing_required_arg()
    print("\n✅ All function tests passed!")
