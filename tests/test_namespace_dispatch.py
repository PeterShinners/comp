"""Test namespace dispatch - dynamic dispatch based on tag/handle defining module.

This tests the new syntax: |func-name/$var.ref
Where $var.ref is a tag or handle, and the function is looked up in the
module that defined that tag or handle.
"""

import pytest
import comp


def test_tag_namespace_dispatch():
    """Test dispatching to a function in a tag's defining namespace."""
    
    # Create module A with a tag and a function
    module_a_source = """
!tag #mode = {
    #readonly = 1
    #readwrite = 2
}

!func |validate ~{val #mode} = {
    "validated in module A"
}
"""
    module_a_ast = comp.parse_module(module_a_source)
    module_a = comp.Module(module_id="module_a")
    engine = comp.Engine()
    module_a.prepare(module_a_ast, engine)
    module_a = engine.run(module_a_ast, module=module_a)
    
    # Create module B with a tag and function using namespace dispatch
    module_b_source = """
!tag #color = {
    #red
    #green
}

!func |process ~{} = {
    $var.tag = #readonly
    [$var.tag |validate/($var.tag) val=$var.tag]
}
"""
    module_b_ast = comp.parse_module(module_b_source)
    module_b = comp.Module(module_id="module_b")
    # Add module_a as a namespace
    module_b.add_namespace("module_a", module_a)
    module_b.prepare(module_b_ast, engine)
    module_b = engine.run(module_b_ast, module=module_b)
    
    # Call the process function which should dispatch to module_a's validate
    result = engine.run_function(
        module_b.functions['process'][0],
        in_=comp.Value({}),
        args=None,
        ctx=None
    )
    
    # Result should be a struct with the pipeline result
    assert result.is_struct
    # Get the unnamed field key - it's an Unnamed instance
    unnamed_key = list(result.struct.keys())[0]
    inner_result = result.struct[unnamed_key]
    assert inner_result.is_string
    assert inner_result.data == "validated in module A"


def test_handle_namespace_dispatch():
    """Test dispatching to a function in a handle's defining namespace."""
    
    # Create module with a handle and functions for it
    # For this test, let's use a simpler approach where we define the function
    # to accept the handle implicitly via $in 
    module_source = """
!handle @db

!func |exec ~{@db} = {
    {result="executed successfully"}
}

!func |testdispatch ~{} = {
    $var.handle = !grab @db
    [$var.handle |exec/($var.handle)]
}
"""
    module_ast = comp.parse_module(module_source)
    module = comp.Module(module_id="test_module")
    engine = comp.Engine()
    module.prepare(module_ast, engine)
    module = engine.run(module_ast, module=module)
    
    # Call testdispatch which uses handle namespace dispatch
    result = engine.run_function(
        module.functions['testdispatch'][0],
        in_=comp.Value({}),
        args=None,
        ctx=None
    )
    
    assert result.is_struct
    data = result.as_scalar()
    assert data.data == "executed successfully"


def test_namespace_dispatch_with_private_function():
    """Test that namespace dispatch can access private functions in the defining module."""
    
    # Create module A with a private function
    module_a_source = """
!tag #state = {
    #active
    #inactive
}

!func |internal-validate& ~{val #state} = {
    "private validation"
}
"""
    module_a_ast = comp.parse_module(module_a_source)
    module_a = comp.Module(module_id="module_a")
    engine = comp.Engine()
    module_a.prepare(module_a_ast, engine)
    module_a = engine.run(module_a_ast, module=module_a)
    
    # Create module B that uses namespace dispatch to access the private function
    module_b_source = """
!func |test ~{} = {
    $var.tag = #active
    [$var.tag |internal-validate/($var.tag) val=$var.tag]
}
"""
    module_b_ast = comp.parse_module(module_b_source)
    module_b = comp.Module(module_id="module_b")
    module_b.add_namespace("module_a", module_a)
    module_b.prepare(module_b_ast, engine)
    module_b = engine.run(module_b_ast, module=module_b)
    
    # Call the test function - should be able to access the private function
    # via namespace dispatch
    result = engine.run_function(
        module_b.functions['test'][0],
        in_=comp.Value({}),
        args=None,
        ctx=None
    )
    
    # Result should be a struct with the pipeline result
    assert result.is_struct
    unnamed_key = list(result.struct.keys())[0]
    inner_result = result.struct[unnamed_key]
    assert inner_result.is_string
    assert inner_result.data == "private validation"


def test_namespace_dispatch_not_found():
    """Test that namespace dispatch fails gracefully when function not found."""
    
    # Create module with a tag but no corresponding function
    module_source = """
!tag #readonly = 1

!func |test ~{} = {
    $var.tag = #readonly
    [$var.tag |nonexistent/($var.tag)]
}
"""
    module_ast = comp.parse_module(module_source)
    module = comp.Module(module_id="test_module")
    engine = comp.Engine()
    module.prepare(module_ast, engine)
    module = engine.run(module_ast, module=module)
    
    # Call test - should fail with appropriate error
    result = engine.run_function(
        module.functions['test'][0],
        in_=comp.Value({}),
        args=None,
        ctx=None
    )
    
    assert result.is_fail


def test_namespace_dispatch_wrong_type():
    """Test that namespace dispatch fails when given a non-tag/handle value."""
    
    module_source = """
!func |test ~{} = {
    $var.num = 42
    [$var.num |some-func/($var.num)]
}
"""
    module_ast = comp.parse_module(module_source)
    module = comp.Module(module_id="test_module")
    engine = comp.Engine()
    module.prepare(module_ast, engine)
    module = engine.run(module_ast, module=module)
    
    # Call test - should fail because numbers don't have namespaces
    result = engine.run_function(
        module.functions['test'][0],
        in_=comp.Value({}),
        args=None,
        ctx=None
    )
    
    assert result.is_fail


def test_static_namespace():
    """Test static namespace references in function calls."""
    
    # Create module A with a function
    module_a_source = """
!func |greet ~{name ~str} = {
    $in % "Hello, %{name}!"
}
"""
    module_a_ast = comp.parse_module(module_a_source)
    module_a = comp.Module(module_id="module_a")
    engine = comp.Engine()
    module_a.prepare(module_a_ast, engine)
    module_a = engine.run(module_a_ast, module=module_a)
    
    # Create module B that uses static namespace reference
    module_b_source = """
!func |test ~{} = {
    [{name="World"} |greet/module_a]
}
"""
    module_b_ast = comp.parse_module(module_b_source)
    module_b = comp.Module(module_id="module_b")
    module_b.add_namespace("module_a", module_a)
    module_b.prepare(module_b_ast, engine)
    module_b = engine.run(module_b_ast, module=module_b)
    
    # Call test - should use static namespace reference
    result = engine.run_function(
        module_b.functions['test'][0],
        in_=comp.Value({}),
        args=None,
        ctx=None
    )
    
    # Result should be a struct with the pipeline result
    assert result.is_struct
    unnamed_key = list(result.struct.keys())[0]
    inner_result = result.struct[unnamed_key]
    assert inner_result.is_string
    assert inner_result.data == "Hello, World!"
