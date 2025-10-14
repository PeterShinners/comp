"""Tests for function shape-based dispatch (overload selection)."""

import comp


def run_test_code(code: str):
    """Helper to run test code and return (engine, result) from |main."""
    engine = comp.Engine()
    module_ast = comp.parse_module(code)
    module = comp.Module()
    module.prepare(module_ast, engine)
    
    # Run module to process definitions
    module_result = engine.run(module_ast)
    assert isinstance(module_result, comp.Module)
    module = module_result
    
    # Get and call main function
    main_funcs = module.lookup_function(["main"])
    assert main_funcs is not None and len(main_funcs) > 0
    main_func = main_funcs[0]
    
    result = engine.run(
        main_func.body,
        in_=comp.Value(None),
        arg=comp.Value({}),
        ctx=comp.Value({}),
        mod=comp.Value({}),
        local=comp.Value({}),
        mod_funcs=module,
        mod_shapes=module,
        mod_tags=module,
    )
    
    return engine, result


def test_function_dispatch_by_shape():
    """Test that functions dispatch to most specific overload based on input shape."""
    code = """
!shape ~point = {x ~num y ~num}
!shape ~rect = {width ~num height ~num}

!func |area ~point = {
    result = "point"
}

!func |area ~rect = {
    result = width * height
}

!func |main ~{} = {
    point_result = [{x=5 y=10} |area]
    rect_result = [{width=5 height=10} |area]
}
"""
    
    engine, result = run_test_code(code)
    
    # Should succeed
    assert not engine.is_fail(result)
    assert result.is_struct
    
    # Check point result
    point_result = result.struct[comp.Value('point_result')]
    assert point_result.struct[comp.Value('result')].data == "point"
    
    # Check rect result
    rect_result = result.struct[comp.Value('rect_result')]
    assert rect_result.struct[comp.Value('result')].data == 50


def test_function_dispatch_with_wildcard():
    """Test that wildcard (no shape) functions work as fallback."""
    code = """
!shape ~special = {value ~num}

!func |process ~special = {
    result = value + 100
}

!func |process ~{} = {
    result = 999
}

!func |main ~{} = {
    special_result = [{value=5} |process]
    generic_result = [42 |process]
}
"""
    
    engine, result = run_test_code(code)
    
    # Should succeed
    assert not engine.is_fail(result)
    assert result.is_struct
    
    # Check special result - should use specific overload
    special_result = result.struct[comp.Value('special_result')]
    assert special_result.struct[comp.Value('result')].data == 105
    
    # Check generic results - should use wildcard overload
    generic_result = result.struct[comp.Value('generic_result')]
    assert generic_result.struct[comp.Value('result')].data == 999


def test_function_dispatch_most_specific():
    """Test that most specific shape wins in dispatch."""
    code = """
!shape ~animal = {name ~str}
!shape ~dog = {..~animal breed ~str}

!func |describe ~animal = {
    result = "animal " + name
}

!func |describe ~dog = {
    result = "dog " + breed + " " + name
}

!func |main ~{} = {
    animal_result = [{name="Generic"} |describe]
    dog_result = [{name="Buddy" breed="Golden"} |describe]
}
"""
    
    engine, result = run_test_code(code)
    
    # Should succeed
    assert not engine.is_fail(result)
    assert result.is_struct
    
    # Check animal result - should use base overload
    animal_result = result.struct[comp.Value('animal_result')]
    assert animal_result.struct[comp.Value('result')].data == "animal Generic"
    
    # Check dog result - should use more specific overload
    dog_result = result.struct[comp.Value('dog_result')]
    assert dog_result.struct[comp.Value('result')].data == "dog Golden Buddy"


def test_function_dispatch_no_match():
    """Test that dispatch fails when no overload matches."""
    code = """
!shape ~point = {x ~num y ~num}

!func |process ~point = {
    result = x + y
}

!func |main ~{} = {
    result = ["hello" |process]
}
"""
    
    engine, result = run_test_code(code)
    
    # Should fail - no overload matches string input
    assert engine.is_fail(result)
    assert "no overload matches input shape" in result.struct[comp.Value('message')].data


def test_function_dispatch_score_ordering():
    """Test that dispatch uses score ordering based on field counts."""
    code = """
!shape ~basic = {value ~num}
!shape ~extended = {value ~num extra ~num}

!func |check ~basic = {
    result = "basic"
}

!func |check ~extended = {
    result = "extended"
}

!func |main ~{} = {
    basic_result = [{value=42} |check]
    extended_result = [{value=42 extra=10} |check]
}
"""
    
    engine, result = run_test_code(code)
    
    # Should succeed and pick correct overload for each
    assert not engine.is_fail(result)
    assert result.is_struct
    
    # Basic should use basic overload
    basic_result = result.struct[comp.Value('basic_result')]
    assert basic_result.struct[comp.Value('result')].data == "basic"
    
    # Extended should use extended overload (more specific)
    extended_result = result.struct[comp.Value('extended_result')]
    assert extended_result.struct[comp.Value('result')].data == "extended"
