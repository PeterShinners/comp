"""Test function system."""

import comp


def test_builtin_double():
    """Test |double function."""
    engine = comp.Engine()
    # Create minimal frame for function calling
    dummy_node = comp.ast.Number(0)
    frame = comp._engine._Frame(dummy_node, None, {}, False, engine)

    result = frame.call_function("double", comp.Value(5))
    assert result.data == 10


def test_builtin_print():
    """Test |print function (passes through)."""
    engine = comp.Engine()
    dummy_node = comp.ast.Number(0)
    frame = comp._engine._Frame(dummy_node, None, {}, False, engine)

    result = frame.call_function("print", comp.Value(42))
    assert result.data == 42


def test_builtin_identity():
    """Test |identity function."""
    engine = comp.Engine()
    dummy_node = comp.ast.Number(0)
    frame = comp._engine._Frame(dummy_node, None, {}, False, engine)

    result = frame.call_function("identity", comp.Value("hello"))
    assert result.data == "hello"


def test_builtin_add():
    """Test |add function with arguments."""
    engine = comp.Engine()
    dummy_node = comp.ast.Number(0)
    frame = comp._engine._Frame(dummy_node, None, {}, False, engine)

    # |add requires ^{n=...} argument
    args = comp.Value({"n": 3})
    result = frame.call_function("add", comp.Value(5), args)
    assert result.data == 8


def test_builtin_wrap():
    """Test |wrap function."""
    engine = comp.Engine()
    dummy_node = comp.ast.Number(0)
    frame = comp._engine._Frame(dummy_node, None, {}, False, engine)

    # |wrap requires ^{key=...} argument
    args = comp.Value({"key": "x"})
    result = frame.call_function("wrap", comp.Value(5), args)

    assert result.is_struct
    assert result.struct[comp.Value("x")] == comp.Value(5)


def test_function_not_found():
    """Test calling non-existent function."""
    engine = comp.Engine()
    dummy_node = comp.ast.Number(0)
    frame = comp._engine._Frame(dummy_node, None, {}, False, engine)

    result = frame.call_function("nonexistent", comp.Value(5))
    assert engine.is_fail(result)


def test_builtin_lookup():
    """Test engine.get_function() for builtins."""
    engine = comp.Engine()

    func = engine.get_function("double")
    assert func is not None
    assert func.name == "double"

    # Non-existent function
    assert engine.get_function("nonexistent") is None


def test_function_with_wrong_input_type():
    """Test function with wrong input type."""
    engine = comp.Engine()
    dummy_node = comp.ast.Number(0)
    frame = comp._engine._Frame(dummy_node, None, {}, False, engine)

    # |double expects number
    result = frame.call_function("double", comp.Value("not a number"))
    assert engine.is_fail(result)


def test_function_missing_required_arg():
    """Test function with missing required argument."""
    engine = comp.Engine()
    dummy_node = comp.ast.Number(0)
    frame = comp._engine._Frame(dummy_node, None, {}, False, engine)

    # |add requires ^{n=...}
    result = frame.call_function("add", comp.Value(5), None)
    assert engine.is_fail(result)


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
    func_def = comp.ast.FuncDef(
        path=["double"],
        body=comp.ast.Number(2)  # Simplified body
    )

    module = comp.Module()

    # Wrap in test node
    class TestWrapper(comp.ast.ValueNode):
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
    func_def = comp.ast.FuncDef(
        path=["process"],
        body=comp.ast.Number(1),
        input_shape=comp.ast.ShapeRef(["user"])
    )

    # Need a module with the shape defined
    module = comp.Module()
    module.define_shape(["user"], [comp.ShapeField(name="name")])

    class TestWrapper(comp.ast.ValueNode):
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
    func_def = comp.ast.FuncDef(
        path=["calculate"],
        body=comp.ast.Number(42),
        is_pure=True
    )

    module = comp.Module()

    class TestWrapper(comp.ast.ValueNode):
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
    func_ref = comp.ast.FuncRef(["double"])

    class TestNode(comp.ast.ValueNode):
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

    func_ref = comp.ast.FuncRef(["nonexistent"])

    class TestNode(comp.ast.ValueNode):
        def evaluate(self, frame):
            func = yield comp.Compute(func_ref)
            return func

        def unparse(self):
            return "test"

    engine = comp.Engine()
    result = engine.run(TestNode(), mod_funcs=module)

    # Should be a failure
    assert engine.is_fail(result)


def test_function_with_doc():
    """Test function with documentation."""
    func_def = comp.ast.FuncDef(
        path=["helper"],
        body=comp.ast.Number(1),
        doc="Main documentation",
        impl_doc="Implementation note"
    )

    module = comp.Module()

    class TestWrapper(comp.ast.ValueNode):
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
    func_def = comp.ast.FuncDef(
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
