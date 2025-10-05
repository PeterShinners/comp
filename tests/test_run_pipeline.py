"""Test runtime pipeline execution."""

import comp
from comp import run


def test_simple_pipeline_with_func():
    """Test basic pipeline with a simple function."""
    code = """
    !func |double ~{x ~num} = {
        result = x * 2
    }
    
    !func |test ~_ = {
        value = [{x=5} |double]
    }
    """

    ast_module = comp.parse_module(code)
    module = run.Module("test")
    module.process_ast(ast_module)
    module.resolve_all()

    func_def = module.funcs["test"]
    result = run.invoke(func_def, module, run.Value({}), run.Value({}), run.Value({}), run.Value({}))

    assert result.is_struct
    assert result.struct[run.Value("value")].is_struct
    # The double function should return {result = 10}
    assert result.struct[run.Value("value")].struct[run.Value("result")].to_python() == 10


def test_unseeded_pipeline():
    """Test pipeline without explicit seed (uses $in)."""
    code = """
    !func |process ~{x ~num} = {
        result = x + 1
    }
    
    !func |test ~_ = {
        value = [{x=10} |process]
    }
    """

    ast_module = comp.parse_module(code)
    module = run.Module("test")
    module.process_ast(ast_module)
    module.resolve_all()

    func_def = module.funcs["test"]
    input_value = run.Value(None)
    input_value.struct = {run.Value("data"): run.Value(5)}
    
    result = run.invoke(func_def, module, input_value, run.Value({}), run.Value({}), run.Value({}))

    assert result.is_struct
    assert result.struct[run.Value("value")].is_struct
    # Should return {result = 11}
    assert result.struct[run.Value("value")].struct[run.Value("result")].to_python() == 11


def test_multi_stage_pipeline():
    """Test pipeline with multiple stages."""
    code = """
    !func |add-one ~{x ~num} = {
        result = x + 1
    }
    
    !func |double ~{x ~num} = {
        result = x * 2
    }
    
    !func |test ~_ = {
        value = [{x=5} |add-one |double x=result]
    }
    """

    ast_module = comp.parse_module(code)
    module = run.Module("test")
    module.process_ast(ast_module)
    module.resolve_all()

    func_def = module.funcs["test"]
    result = run.invoke(func_def, module, run.Value({}), run.Value({}), run.Value({}), run.Value({}))

    assert result.is_struct
    # {x=5} -> add-one -> {result=6} -> double (with x=#0 which is 6) -> {result=12}
    final_value = result.struct[run.Value("value")]
    assert final_value.is_struct
    # Need to access through result field
    assert final_value.struct[run.Value("result")].to_python() == 12


def test_pipe_struct_transformation():
    """Test inline struct transformation with |{...}"""
    code = """
    !func |test ~_ = {
        value = [{x=5 y=10} |{doubled = x * 2 sum = x + y}]
    }
    """

    ast_module = comp.parse_module(code)
    module = run.Module("test")
    module.process_ast(ast_module)
    module.resolve_all()

    func_def = module.funcs["test"]
    result = run.invoke(func_def, module, run.Value({}), run.Value({}), run.Value({}), run.Value({}))

    assert result.is_struct
    final_value = result.struct[run.Value("value")]
    assert final_value.is_struct
    # Should have doubled=10 and sum=15
    assert final_value.struct[run.Value("doubled")].to_python() == 10
    assert final_value.struct[run.Value("sum")].to_python() == 15


def test_pipe_struct_with_function():
    """Test PipeStruct combined with function calls."""
    code = """
    !func |double ~{x ~num} = {
        result = x * 2
    }
    
    !func |test ~_ = {
        value = [{x=5} |double |{final = result * 3}]
    }
    """

    ast_module = comp.parse_module(code)
    module = run.Module("test")
    module.process_ast(ast_module)
    module.resolve_all()

    func_def = module.funcs["test"]
    result = run.invoke(func_def, module, run.Value({}), run.Value({}), run.Value({}), run.Value({}))

    assert result.is_struct
    final_value = result.struct[run.Value("value")]
    assert final_value.is_struct
    # {x=5} -> double -> {result=10} -> |{final = result * 3} -> {final=30}
    assert final_value.struct[run.Value("final")].to_python() == 30


if __name__ == "__main__":
    print("Running pipeline tests...")
    test_simple_pipeline_with_func()
    print("✓ Simple pipeline")
    test_unseeded_pipeline()
    print("✓ Unseeded pipeline")
    test_multi_stage_pipeline()
    print("✓ Multi-stage pipeline")
    test_pipe_struct_transformation()
    print("✓ PipeStruct transformation")
    test_pipe_struct_with_function()
    print("✓ PipeStruct with function")
    print("All tests passed!")
