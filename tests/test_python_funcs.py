"""Test Python-implemented functions."""

import comp
from comp import run


def test_simple_python_function():
    """Test a simple Python function that can be called from Comp."""

    # Create a Python function
    def double_value(in_value: run.Value, arg_value: run.Value) -> run.Value:
        """Double a numeric value."""
        # Get x from in_value (pipeline input)
        if in_value.is_struct and in_value.struct:
            x_val = in_value.struct.get(run.Value("x"))
            if x_val and x_val.is_num:
                # Return a struct with the result
                return run.Value({"result": x_val.num * 2})

        # Fallback
        return run.Value({})

    # Create a module and register the Python function
    module = run.Module("test")
    func_def = run.FuncDef(identifier=["double"])
    func_def.implementations.append(run.PythonFuncImpl(double_value, "double"))
    module.funcs["double"] = func_def

    # Create a Comp function that calls the Python function
    code = """
    !func |test ~_ = {
        value = [{x=5} |double]
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


def test_python_print_function():
    """Test a Python print function (useful for debugging)."""

    printed_values = []

    def print_func(in_value: run.Value, arg_value: run.Value) -> run.Value:
        """Print the input value and pass it through."""
        # Convert to Python and print
        printed_values.append(in_value.to_python())
        # Pass through the input unchanged
        return in_value

    # Create a module and register the print function
    module = run.Module("test")
    print_def = run.FuncDef(identifier=["print"])
    print_def.implementations.append(run.PythonFuncImpl(print_func, "print"))
    module.funcs["print"] = print_def

    # Create a Comp function that uses print
    code = """
    !func |add-one ~{x ~num} = {
        result = x + 1
    }

    !func |test ~_ = {
        value = [{x=5} |add-one |print |{final = result * 2}]
    }
    """

    ast_module = comp.parse_module(code)
    module.process_ast(ast_module)
    module.resolve_all()

    # Invoke the test function
    func_def = module.funcs["test"]
    result = run.invoke(func_def, module, run.Value({}), run.Value({}), run.Value({}), run.Value({}))

    # Check that print was called with the intermediate value
    assert len(printed_values) == 1
    assert printed_values[0] == {"result": 6}

    # Check final result
    assert result.is_struct
    assert result.struct[run.Value("value")].struct[run.Value("final")].to_python() == 12


def test_python_function_in_pipeline():
    """Test Python function in multi-stage pipeline."""

    def add_ten(in_value: run.Value, arg_value: run.Value) -> run.Value:
        """Add 10 to the 'value' field."""
        if in_value.is_struct and in_value.struct:
            val = in_value.struct.get(run.Value("value"))
            if val and val.is_num:
                result = run.Value(None)
                result.struct = {run.Value("value"): run.Value(val.num + 10)}
                return result
        return in_value

    # Create module with Python function
    module = run.Module("test")
    add_ten_def = run.FuncDef(identifier=["add-ten"])
    add_ten_def.implementations.append(run.PythonFuncImpl(add_ten, "add-ten"))
    module.funcs["add-ten"] = add_ten_def

    # Comp function using Python function in pipeline
    code = """
    !func |test ~_ = {
        result = [{value=5} |add-ten |{final = value * 2}]
    }
    """

    ast_module = comp.parse_module(code)
    module.process_ast(ast_module)
    module.resolve_all()

    # Invoke and check result
    func_def = module.funcs["test"]
    result = run.invoke(func_def, module, run.Value({}), run.Value({}), run.Value({}), run.Value({}))

    # {value=5} -> add-ten -> {value=15} -> {final=30}
    assert result.is_struct
    assert result.struct[run.Value("result")].struct[run.Value("final")].to_python() == 30


if __name__ == "__main__":
    print("Running Python function tests...")
    test_simple_python_function()
    print("✓ Simple Python function")
    test_python_print_function()
    print("✓ Python print function")
    test_python_function_in_pipeline()
    print("✓ Python function in pipeline")
    print("All tests passed!")
