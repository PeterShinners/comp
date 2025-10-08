"""Unit testing quality of life and readability helpers for runtime tests."""

import re

import pytest

import comp


def params(names, **cases):
    """Simplified parametrize decorator for test cases.

    Args:
        names: Space or comma-separated string of parameter names
        **cases: Named test cases where key is the test ID and value is
                either a single argument or tuple of arguments

    Returns:
        pytest.mark.parametrize decorator with 'key' as first parameter

    Example:
        @params("left op right expected", add=(5, "+", 3, 8))
        def test_arithmetic(key, left, op, right, expected):
            result = eval_binary_op(left, op, right)
            assert result == expected
    """
    keys = list(cases)
    params = []
    for k, v in cases.items():
        # If value is a tuple, unpack it; otherwise keep as single value
        if isinstance(v, tuple):
            params.append((k, *v))
        else:
            params.append((k, v))

    columns = names.replace(",", " ").split()
    columns.insert(0, "key")
    return pytest.mark.parametrize(columns, params, ids=keys)


def eval_binary_op(left, op, right):
    """Evaluate a binary operation directly using internal functions.
    
    Args:
        left: Left operand (Python value or comp.run.Value)
        op: Operator string ("+", "-", "*", etc.)
        right: Right operand (Python value or comp.run.Value)
    
    Returns:
        Result as comp.run.Value
        
    Example:
        result = eval_binary_op(5, "+", 3)
        assert result.to_python() == 8
    """
    # Convert Python values to comp.run.Value if needed
    if not isinstance(left, comp.run.Value):
        left = comp.run.Value(left)
    if not isinstance(right, comp.run.Value):
        right = comp.run.Value(right)
    
    # Create a simple expression node
    expr = type('BinaryOp', (), {'op': op, 'kids': [None, None]})()
    
    # Use the internal operator evaluation
    # We need to pass a dummy evaluate function since we have values already
    def dummy_eval(node, scopes):
        if node is expr.kids[0]:
            return left
        if node is expr.kids[1]:
            return right
        raise ValueError(f"Unexpected node in eval_binary_op: {node}")
    
    # Create minimal module and scopes
    module = comp.run.Module("test")
    scopes = comp.run._eval.ChainedScope()
    
    return comp.run._ops.evaluate_binary_op(expr, module, scopes, dummy_eval)


def eval_unary_op(op, operand):
    """Evaluate a unary operation directly using internal functions.
    
    Args:
        op: Operator string ("-", "+", "!!")
        operand: Operand (Python value or comp.run.Value)
    
    Returns:
        Result as comp.run.Value
        
    Example:
        result = eval_unary_op("-", 42)
        assert result.to_python() == -42
    """
    # Convert Python value to comp.run.Value if needed
    if not isinstance(operand, comp.run.Value):
        operand = comp.run.Value(operand)
    
    # Create a simple expression node
    expr = type('UnaryOp', (), {'op': op, 'kids': [None]})()
    
    # Use the internal operator evaluation
    def dummy_eval(node, scopes):
        if node is expr.kids[0]:
            return operand
        raise ValueError(f"Unexpected node in eval_unary_op: {node}")
    
    # Create minimal module and scopes
    module = comp.run.Module("test")
    scopes = comp.run._eval.ChainedScope()
    
    return comp.run._ops.evaluate_unary_op(expr, module, scopes, dummy_eval)


def run_function(code, func_name, *scope_args):
    """Parse and run a function with minimal setup.
    
    Args:
        code: Source code containing function definition
        func_name: Name of function to invoke
        *scope_args: Arguments for $in, $ctx, $mod, $arg scopes (as Python values or comp.run.Value)
    
    Returns:
        Result as comp.run.Value
        
    Example:
        code = '''
        !func |double ~_ = {
            result = $in * 2
        }
        '''
        result = run_function(code, "double", 21)
        assert result.struct[comp.run.Value("result")].to_python() == 42
    """
    module = module_from_code(code)
    func_def = module.funcs[func_name]
    
    # Convert Python values to comp.run.Value if needed
    value_args = []
    for arg in scope_args:
        if not isinstance(arg, comp.run.Value):
            value_args.append(comp.run.Value(arg))
        else:
            value_args.append(arg)
    
    # Pad with empty structs if needed (for $in, $ctx, $mod, $arg)
    while len(value_args) < 4:
        value_args.append(comp.run.Value({}))
    
    return comp.run.invoke(func_def, module, *value_args[:4])


def eval_expression(code, **bindings):
    """Evaluate a simple expression with variable bindings.
    
    Args:
        code: Expression source code
        **bindings: Variable name to value mappings
    
    Returns:
        Result as run.Value
        
    Example:
        result = eval_expression("x + y", x=10, y=32)
        assert result.to_python() == 42
    """
    # Wrap in a function that assigns bindings and evaluates expression
    func_code = "!func |__eval__ ~_ = {\n"
    for name, value in bindings.items():
        if isinstance(value, str):
            func_code += f'    {name} = "{value}"\n'
        elif isinstance(value, bool):
            func_code += f'    {name} = #{str(value).lower()}\n'
        else:
            func_code += f'    {name} = {value}\n'
    func_code += f"    __result__ = {code}\n"
    func_code += "}\n"
    
    result = run_function(func_code, "__eval__")
    return result.struct[comp.run.Value("__result__")]


def should_raise(code, func_name, *scope_args, match=None):
    """Assert that running a function raises an exception.
    
    Args:
        code: Source code containing function definition
        func_name: Name of function to invoke
        *scope_args: Arguments for $in, $out, $ctx, $env scopes
        match: Optional regex pattern to match against error message
    
    Returns:
        The exception that was raised
        
    Raises:
        pytest.fail: If function succeeds or regex doesn't match
        
    Example:
        should_raise(code, "test-func", match="out of bounds")
    """
    try:
        run_function(code, func_name, *scope_args)
    except Exception as err:
        if match:
            msg = str(err)
            if not re.search(match, msg, re.IGNORECASE):
                pytest.fail(
                    f"Error message doesn't match pattern '{match}':\n"
                    f"  Message: {msg}",
                    pytrace=False
                )
        return err
    pytest.fail(f"Expected exception for function '{func_name}'", pytrace=False)


def get_field(struct_value, field_name):
    """Get a field value from a struct by name.
    
    Args:
        struct_value: A comp.run.Value that is a struct
        field_name: Name of field to retrieve (string)
    
    Returns:
        Field value as comp.run.Value
        
    Example:
        result = run_function(code, "test-func")
        value = get_field(result, "count")
        assert value.to_python() == 42
    """
    assert struct_value.is_struct, f"Expected struct, got {struct_value}"
    return struct_value.struct[comp.run.Value(field_name)]


def get_field_python(struct_value, field_name):
    """Get a field value from a struct and convert to Python.
    
    Args:
        struct_value: A run.Value that is a struct
        field_name: Name of field to retrieve (string)
    
    Returns:
        Field value as Python type
        
    Example:
        result = run_function(code, "test-func")
        assert get_field_python(result, "count") == 42
    """
    return get_field(struct_value, field_name).to_python()


def module_from_code(code, name="test"):
    """Parse code and return a comp.run.Module with definitions.
    
    Args:
        code: Source code containing definitions
        name: Name for the module (default "test")
    
    Returns:
        A comp.run.Module with parsed definitions
        
    Example:
        module = module_from_code('!func |double ~{x ~num} = {x * 2}')
        assert "double" in module.funcs
    """
    ast_module = comp.parse_module(code)
    module = comp.run.Module(name)
    module.process_ast(ast_module)
    module.resolve_all()
    return module
