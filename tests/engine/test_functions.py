"""Test function system."""

import comp.engine as comp
from comp.engine.ast._base import ValueNode
from comp.engine.ast._function import FuncDef, FuncRef
from comp.engine.ast._shape import ShapeRef


def test_builtin_double():
    """Test |double function."""
    engine = comp.Engine()

    result = engine.call_function("double", comp.Value(5))
    assert result.data == 10


def test_builtin_print():
    """Test |print function (passes through)."""
    engine = comp.Engine()

    result = engine.call_function("print", comp.Value(42))
    assert result.data == 42


def test_builtin_identity():
    """Test |identity function."""
    engine = comp.Engine()

    result = engine.call_function("identity", comp.Value("hello"))
    assert result.data == "hello"


def test_builtin_add():
    """Test |add function with arguments."""
    engine = comp.Engine()

    # |add requires ^{n=...} argument
    args = comp.Value({"n": 3})
    result = engine.call_function("add", comp.Value(5), args)
    assert result.data == 8


def test_builtin_wrap():
    """Test |wrap function."""
    engine = comp.Engine()

    # |wrap requires ^{key=...} argument
    args = comp.Value({"key": "x"})
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
    assert result.to_python() == 12


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


# New AST-based function system tests


def test_module_function_storage():
    """Verify Module can store and retrieve functions."""
    module = comp.Module()

    # Define a simple function
    module.define_function(["double"], body=None)

    # Look up function
    funcs = module.lookup_function(["double"])
    assert funcs is not None
    assert len(funcs) == 1
    assert funcs[0].name == "double"

    # Non-existent function
    assert module.lookup_function(["nonexistent"]) is None


def test_function_overloads():
    """Verify functions can have multiple overloads."""
    module = comp.Module()

    # Define two overloads
    module.define_function(["process"], body=None, impl_doc="first impl")
    module.define_function(["process"], body=None, impl_doc="second impl")

    # Look up should return both
    funcs = module.lookup_function(["process"])
    assert funcs is not None
    assert len(funcs) == 2
    assert funcs[0].impl_doc == "first impl"
    assert funcs[1].impl_doc == "second impl"


def test_simple_function_definition():
    """Test defining a function."""
    # Create function definition: !func |double = {2}
    func_def = FuncDef(
        path=["double"],
        body=comp.ast.Number(2)  # Simplified body
    )

    module = comp.Module()

    # Wrap in test node
    class TestWrapper(ValueNode):
        def evaluate(self, frame):
            result = yield comp.Compute(func_def, mod_funcs=module)
            return result

        def unparse(self):
            return "test"

    engine = comp.Engine()
    result = engine.run(TestWrapper(), mod_funcs=module)

    # Should succeed
    assert result.to_python() == comp.TRUE

    # Function should be in module
    funcs = module.lookup_function(["double"])
    assert funcs is not None
    assert len(funcs) == 1


def test_function_with_input_shape():
    """Test function with input shape constraint."""
    func_def = FuncDef(
        path=["process"],
        body=comp.ast.Number(1),
        input_shape=ShapeRef(["user"])
    )

    # Need a module with the shape defined
    module = comp.Module()
    from comp.engine._module import ShapeField
    module.define_shape(["user"], [ShapeField(name="name")])

    class TestWrapper(ValueNode):
        def evaluate(self, frame):
            result = yield comp.Compute(func_def, mod_funcs=module, mod_shapes=module)
            return result

        def unparse(self):
            return "test"

    engine = comp.Engine()
    result = engine.run(TestWrapper(), mod_funcs=module, mod_shapes=module)

    assert result.to_python() == comp.TRUE

    # Check function was stored with input shape
    funcs = module.lookup_function(["process"])
    assert funcs is not None
    assert funcs[0].input_shape is not None


def test_pure_function():
    """Test pure function flag."""
    func_def = FuncDef(
        path=["calculate"],
        body=comp.ast.Number(42),
        is_pure=True
    )

    module = comp.Module()

    class TestWrapper(ValueNode):
        def evaluate(self, frame):
            result = yield comp.Compute(func_def, mod_funcs=module)
            return result

        def unparse(self):
            return "test"

    engine = comp.Engine()
    result = engine.run(TestWrapper(), mod_funcs=module)

    assert result.to_python() == comp.TRUE

    funcs = module.lookup_function(["calculate"])
    assert funcs[0].is_pure is True


def test_function_reference():
    """Test referencing a defined function."""
    # Manually set up module with a function
    module = comp.Module()
    module.define_function(["double"], body=None, doc="Doubles a number")

    # Create reference: |double
    func_ref = FuncRef(["double"])

    class TestNode(ValueNode):
        def evaluate(self, frame):
            func = yield comp.Compute(func_ref)
            return func

        def unparse(self):
            return "test"

    engine = comp.Engine()
    result = engine.run(TestNode(), mod_funcs=module)

    # Should return structure with function metadata
    assert isinstance(result.data, dict)
    # Check name field exists
    found_name = False
    for key in result.data.keys():
        if hasattr(key, 'to_python') and key.to_python() == 'name':
            assert result.data[key].to_python() == "double"
            found_name = True
            break
    assert found_name


def test_function_reference_not_found():
    """Test that missing functions are handled."""
    module = comp.Module()

    func_ref = FuncRef(["nonexistent"])

    class TestNode(ValueNode):
        def evaluate(self, frame):
            func = yield comp.Compute(func_ref)
            return func

        def unparse(self):
            return "test"

    engine = comp.Engine()
    result = engine.run(TestNode(), mod_funcs=module)

    # Should be a failure
    assert result.tag == comp.FAIL


def test_function_with_doc():
    """Test function with documentation."""
    func_def = FuncDef(
        path=["helper"],
        body=comp.ast.Number(1),
        doc="Main documentation",
        impl_doc="Implementation note"
    )

    module = comp.Module()

    class TestWrapper(ValueNode):
        def evaluate(self, frame):
            result = yield comp.Compute(func_def, mod_funcs=module)
            return result

        def unparse(self):
            return "test"

    engine = comp.Engine()
    result = engine.run(TestWrapper(), mod_funcs=module)

    assert result.to_python() == comp.TRUE

    funcs = module.lookup_function(["helper"])
    assert funcs[0].doc == "Main documentation"
    assert funcs[0].impl_doc == "Implementation note"


def test_function_unparse():
    """Test unparsing function definition."""
    func_def = FuncDef(
        path=["test"],
        body=comp.ast.Number(1),
        is_pure=True
    )

    unparsed = func_def.unparse()
    assert "!pure" in unparsed
    assert "|test" in unparsed


def test_list_all_functions():
    """Test listing all functions in module."""
    module = comp.Module()

    module.define_function(["func1"], body=None)
    module.define_function(["func2"], body=None)
    module.define_function(["func1"], body=None)  # Overload

    all_funcs = module.list_functions()
    assert len(all_funcs) == 3  # Two unique names, one overload
