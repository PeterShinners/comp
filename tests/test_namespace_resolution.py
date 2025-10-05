"""Test namespace resolution for tags, functions, and shapes."""

import comp
from comp import run


def test_function_no_namespace():
    """Test that functions without namespace search current module then mods."""
    module = run.Module("test")
    module.process_builtins()
    
    # Builtin print should be found without namespace
    code = """
    !func |test ~_ = {
        value = ["hello" |print]
    }
    """
    
    ast_module = comp.parse_module(code)
    module.process_ast(ast_module)
    module.resolve_all()
    
    # Should find print from builtin module
    func_def = module.funcs["test"]
    result = run.invoke(func_def, module, run.Value({}), run.Value({}), run.Value({}), run.Value({}))
    
    assert result.is_struct
    assert result.struct[run.Value("value")].to_python() == "hello"


def test_function_explicit_namespace():
    """Test that functions with explicit namespace only search that namespace."""
    module = run.Module("test")
    module.process_builtins()
    
    # Explicitly reference builtin namespace
    code = """
    !func |test ~_ = {
        value = ["WORLD" |lower/builtin]
    }
    """
    
    ast_module = comp.parse_module(code)
    module.process_ast(ast_module)
    module.resolve_all()
    
    # Should find lower from builtin module
    func_def = module.funcs["test"]
    result = run.invoke(func_def, module, run.Value({}), run.Value({}), run.Value({}), run.Value({}))
    
    assert result.is_struct
    assert result.struct[run.Value("value")].to_python() == "world"


def test_tag_resolution_without_namespace():
    """Test tag resolution searches current module then mods."""
    module = run.Module("test")
    module.process_builtins()
    
    # Reference builtin tag without namespace
    code = """
    !func |test ~_ = {
        value = #true
    }
    """
    
    ast_module = comp.parse_module(code)
    module.process_ast(ast_module)
    module.resolve_all()
    
    func_def = module.funcs["test"]
    result = run.invoke(func_def, module, run.Value({}), run.Value({}), run.Value({}), run.Value({}))
    
    assert result.is_struct
    # Should resolve to the builtin true tag
    true_value = result.struct[run.Value("value")]
    assert true_value.is_tag
    assert true_value.tag.name == "#true"


def test_tag_resolution_with_namespace():
    """Test tag resolution with explicit namespace."""
    module = run.Module("test")
    module.process_builtins()
    
    # Reference builtin tag with explicit namespace
    code = """
    !func |test ~_ = {
        value = #false/builtin
    }
    """
    
    ast_module = comp.parse_module(code)
    module.process_ast(ast_module)
    module.resolve_all()
    
    func_def = module.funcs["test"]
    result = run.invoke(func_def, module, run.Value({}), run.Value({}), run.Value({}), run.Value({}))
    
    assert result.is_struct
    # Should resolve to the builtin false tag
    false_value = result.struct[run.Value("value")]
    assert false_value.is_tag
    assert false_value.tag.name == "#false"


def test_local_shadows_builtin():
    """Test that local definitions shadow builtin definitions."""
    module = run.Module("test")
    module.process_builtins()
    
    # Define a local print function
    code = """
    !func |print ~{x ~num} = {
        result = x * 100
    }
    
    !func |test ~_ = {
        value = [{x=5} |print]
    }
    """
    
    ast_module = comp.parse_module(code)
    module.process_ast(ast_module)
    module.resolve_all()
    
    func_def = module.funcs["test"]
    result = run.invoke(func_def, module, run.Value({}), run.Value({}), run.Value({}), run.Value({}))
    
    assert result.is_struct
    # Should use local print, not builtin
    assert result.struct[run.Value("value")].struct[run.Value("result")].to_python() == 500


def test_explicit_namespace_bypasses_local():
    """Test that explicit namespace bypasses local definition."""
    module = run.Module("test")
    module.process_builtins()
    
    # Define a local print function but explicitly call builtin
    code = """
    !func |print ~{x ~num} = {
        result = x * 100
    }
    
    !func |test ~_ = {
        value = ["test" |print/builtin]
    }
    """
    
    ast_module = comp.parse_module(code)
    module.process_ast(ast_module)
    module.resolve_all()
    
    func_def = module.funcs["test"]
    result = run.invoke(func_def, module, run.Value({}), run.Value({}), run.Value({}), run.Value({}))
    
    assert result.is_struct
    # Should use builtin print (passthrough), not local
    assert result.struct[run.Value("value")].to_python() == "test"
