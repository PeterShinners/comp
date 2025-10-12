"""Tests for function invocation with scope masking and morphing.

These tests validate the new function invocation system at the runtime level.
Parser integration is not yet complete, so we test the runtime primitives directly.
"""

import comp


def test_module_has_scope_attribute():
    """Test that modules have a scope attribute for $mod storage."""
    module = comp.run.Module("<test>")

    # Module should have a scope attribute
    assert hasattr(module, 'scope')
    assert module.scope is not None
    assert module.scope.is_struct
    # Initially empty
    assert module.scope.struct == {}


def test_engine_has_ctx_scope_attribute():
    """Test that engines have a ctx_scope attribute for $ctx storage."""
    from comp.engine import Engine
    engine = Engine()

    # Engine should have a ctx_scope attribute
    assert hasattr(engine, 'ctx_scope')
    assert engine.ctx_scope is not None
    assert engine.ctx_scope.is_struct


def test_function_has_shape_attributes():
    """Test that FuncImpl has input_shape and arg_shape attributes."""
    import decimal
    # Create a simple function with empty body
    body = comp.ast.Number(decimal.Decimal(1))
    func = comp.run.FuncImpl(body)

    # Function should have shape attributes
    assert hasattr(func, 'input_shape')
    assert hasattr(func, 'arg_shape')
    assert func.input_shape is None  # Initially None
    assert func.arg_shape is None  # Initially None


def test_invoke_signature_accepts_engine():
    """Test that invoke() accepts an engine parameter."""
    import decimal
    from comp.engine import Engine

    # Create a mock AST node with body attribute
    class MockASTNode:
        def __init__(self, body_node):
            self.body = body_node

    # Create a simple function that returns a number
    body = comp.ast.Number(decimal.Decimal(42))
    mock_ast = MockASTNode(body)
    impl = comp.run.FuncImpl(mock_ast)

    # Create a function definition and add the implementation
    func_def = comp.run.FuncDef(["test"])
    func_def.implementations.append(impl)

    module = comp.run.Module("<test>")
    engine = Engine()

    # Should not raise - engine parameter is accepted
    result = comp.run.invoke(func_def, module, engine=engine)

    # Should return a value
    assert result is not None


def test_morphing_functions_exist():
    """Test that strong_morph and weak_morph are available."""
    # These should be importable from comp.run
    assert hasattr(comp.run, 'strong_morph')
    assert hasattr(comp.run, 'weak_morph')
    assert callable(comp.run.strong_morph)
    assert callable(comp.run.weak_morph)


def test_mask_functions_exist():
    """Test that mask and strict_mask are available."""
    # These should be importable from comp.run
    assert hasattr(comp.run, 'mask')
    assert hasattr(comp.run, 'strict_mask')
    assert callable(comp.run.mask)
    assert callable(comp.run.strict_mask)
