import pytest
import comp


def run_ast(ast: comp.ast.AstNode, **scopes) -> comp.Value:
    """Run ast nodes inside an engine."""
    engine = comp.Engine()

    value_scopes = {}
    for key, val in scopes.items():
        if not isinstance(val, comp.Entity):
            val = comp.Value(val)
        value_scopes[key] = val

    if 'module' not in scopes:
        module_ast = comp.ast.Module([])
        module = engine.run(module_ast)
        value_scopes['module'] = module

    for scope in ['in_', 'arg', 'ctx', 'mod', 'local']:
        if scope not in value_scopes:
            value_scopes[scope] = comp.Value({})

    return engine.run(ast, **value_scopes)


def run_func(code: str, **scopes) -> comp.Value:
    """Define a function named test and run its body directly."""
    module_ast = comp.parse_module(code)

    engine = comp.Engine()
    module = comp.Module()
    module.prepare(module_ast, engine)
    engine.run(module_ast, module=module)

    value_scopes = {}
    for key, val in scopes.items():
        if not isinstance(val, comp.Entity):
            val = comp.Value(val)
        value_scopes[key] = val

    for scope in ['in_', 'arg', 'ctx', 'mod', 'local']:
        if scope not in value_scopes:
            value_scopes[scope] = comp.Value({})
    value_scopes['module'] = module

    test_funcs = module.lookup_function(["test"])
    if not test_funcs:
        raise ValueError("No |test function defined")
    test_func = test_funcs[0]
    return engine.run(test_func.body, **value_scopes)


def run_frame(name: str, input, args) -> comp.Value:
    """Invoke defined function directly by name."""
    engine = comp.Engine()
    dummy_node = comp.ast.Number(0)
    frame = comp._engine._Frame(dummy_node, None, {}, False, engine)
    input = comp.Value(input)
    args = comp.Value(args) if args is not None else None
    result = frame.call_function(name, input, args)
    return result


def run_pipe(seed, *operations, func=None, **scopes) -> comp.Value:
    """Create and execute a pipeline from seed and operations."""

    if isinstance(seed, int):
        seed = comp.ast.Number(seed)
    elif isinstance(seed, str):
        seed = comp.ast.String(seed)

    pipeline = comp.ast.Pipeline(seed=seed, operations=list(operations))

    value_scopes = {}
    for key, val in scopes.items():
        if not isinstance(val, comp.Entity):
            val = comp.Value(val)
        value_scopes[key] = val

    engine = comp.Engine()
    if func is not None:
        name = func.__name__
        engine.functions[name] = comp.PythonFunction(name, func)

    result = engine.run(pipeline, **value_scopes)
    return result


def make_shape(shape_name, *fields):
    """Generate shape with given fields (name, builtinshape, default) or ShapeField"""
    builtin = comp.get_builtin_module()

    shape_fields = []
    for field in fields:
        if isinstance(field, tuple):
            shape = builtin.shapes[field[1]]
            default = comp.Value(field[2]) if field[2] is not None else None
            shape_fields.append(comp.ShapeField(name=field[0], shape=shape, default=default))
        else:
            shape_fields.append(field)

    module = comp.Module()
    module.define_shape([shape_name], shape_fields)
    shape = module.shapes[shape_name]
    return shape


def assert_value(value: comp.Value, *args, **kwargs):
    """Assert value is not failure and convert to python."""
    engine = comp.Engine()
    assert not engine.is_fail(value), f"Value failed, {value[comp.Value('message')]}"

    if args:
        python = value.as_scalar().to_python()
        assert python == args[0], f"Expected {args[0]!r}, got {python!r}"
    for key, val in kwargs.items():
        python = value.data[comp.Value(key)].as_scalar().to_python()
        assert python == val, f"Expected {key} {val!r}, got {python!r}"
    return value.to_python()


def assert_fail(value, message=None):
    """Assert that a value is a fail value."""
    assert isinstance(value, comp.Value)
    engine = comp.Engine()
    assert engine.is_fail(value)
    if message:
        data = value.to_python()
        fail_message = data["message"]
        assert message in fail_message, f"Failure message {fail_message!r} does not contain expected '{message!r}'"


def parse_module(code: str) -> comp.Module:
    """Parse comp code and return the prepared module."""
    module_ast = comp.parse_module(code)
    engine = comp.Engine()
    module = comp.Module()
    module.prepare(module_ast, engine)
    engine.run(module_ast, module=module)
    return module
