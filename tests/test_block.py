"""Test block invoke, define, and morph."""

import comp
import comptest


def test_block_create_morph_run():
    """Test block invocation with structured input."""
    # Create a block that creates output
    block_ast = comp.ast.Block([
        comp.ast.FieldOp(
            key=comp.ast.String("output"),
            value=comp.ast.String("processed")
        )
    ])
    raw_block_value = comptest.run_ast(block_ast)

    # Verify it's a RawBlock
    assert isinstance(raw_block_value.data, comp.RawBlock)
    
    # Create a block shape that expects a struct with 'value' field
    block_shape_def = comp.BlockShapeDefinition([
        comp.ShapeField(name='value', shape='num')
    ])
    morph_result = comp.morph(raw_block_value, block_shape_def)
    assert morph_result.success

    # Verify original value was NOT modified (morph should not mutate)
    assert isinstance(raw_block_value.data, comp.RawBlock), "Original value should remain RawBlock"
    
    # Verify morph result contains a new Block wrapping the RawBlock
    assert isinstance(morph_result.value.data, comp.Block)
    assert morph_result.value.data.input_shape is not None
    assert morph_result.value.data.raw_block is raw_block_value.data

    # Create input struct
    input_struct = comp.ast.Structure([
        comp.ast.FieldOp(
            key=comp.ast.String('value'),
            value=comp.ast.Number(7)
        )
    ])
    
    # Create pipeline: [{value=7} |:@process]
    pipeline = comp.ast.Pipeline(
        seed=input_struct,
        operations=[
            comp.ast.PipeBlock(comp.ast.Identifier([
                comp.ast.ScopeField('@'),
                comp.ast.TokenField('process')
            ]))
        ]
    )
    
    result = comptest.run_ast(pipeline, local={'process': morph_result.value})
    assert comptest.assert_value(result, output="processed")


def test_pipe_block_requires_block_type():
    """Test that |: fails gracefully when not given a Block."""
    engine = comp.Engine()
    
    # Create a module
    module_ast = comp.ast.Module([])
    module = engine.run(module_ast)
    
    # Create a non-block value
    not_a_block = comp.Value(42)
    local_scope = comp.Value({'notblock': not_a_block})
    
    # Try to invoke it as a block
    pipeline = comp.ast.Pipeline(
        seed=comp.ast.Number(5),
        operations=[
            comp.ast.PipeBlock(comp.ast.Identifier([
                comp.ast.ScopeField('@'),
                comp.ast.TokenField('notblock')
            ]))
        ]
    )
    
    result = engine.run(pipeline, local=local_scope, module=module)
    comptest.assert_fail(result, message="requires Block")


def test_block_shape_evaluates_to_definition():
    """BlockShape.evaluate() should return a BlockShapeDefinition."""
    engine = comp.Engine()
    
    # Create a module (empty is fine for this test)
    module_ast = comp.ast.Module([])
    module = engine.run(module_ast)
    
    # Create a BlockShape with a field (no shape references)
    block_shape = comp.ast.BlockShape([
        comp.ast.ShapeFieldDef(
            name='input',  # Named field
            shape_ref=None,  # No specific shape
            is_spread=False
        )
    ])
    
    # Evaluate it with module context
    result = engine.run(block_shape, module=module)
    
    # Should be a BlockShapeDefinition (returned unwrapped, like ShapeRef does)
    assert isinstance(result, comp.BlockShapeDefinition)
    assert len(result.fields) == 1
    assert result.fields[0].name == 'input'
