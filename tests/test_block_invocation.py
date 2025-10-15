"""Test block invocation with |: operator."""
import comp


def test_pipe_block_simple_invocation():
    """Test basic block invocation with |:."""
    engine = comp.Engine()
    
    # Create a module
    module_ast = comp.ast.Module([])
    module = engine.run(module_ast)
    
    # Create a raw block that returns a simple result
    block_ast = comp.ast.Block([
        comp.ast.FieldOp(
            key=comp.ast.String("result"),
            value=comp.ast.Number(42)
        )
    ])
    raw_block_value = engine.run(block_ast, module=module)
    
    # Morph it to a typed Block
    block_shape_def = comp.BlockShapeDefinition([
        comp.ShapeField(name=None, shape='num')  # Expects a number
    ])
    morph_result = comp.morph(raw_block_value, block_shape_def)
    assert morph_result.success
    
    # Store the block in @local scope
    block_struct = comp.Value({'processor': morph_result.value})
    
    # Create a pipeline that invokes the block: [5 |:@processor]
    pipeline = comp.ast.Pipeline(
        seed=comp.ast.Number(5),
        operations=[
            comp.ast.PipeBlock(comp.ast.Identifier([
                comp.ast.ScopeField('@'),
                comp.ast.TokenField('processor')
            ]))
        ]
    )
    
    # Run with the block in local scope
    result = engine.run(pipeline, local=block_struct, module=module)
    
    # Should have result: 42
    assert result.is_struct
    assert comp.Value('result') in result.struct
    assert result.struct[comp.Value('result')].data == 42


def test_pipe_block_with_struct_input():
    """Test block invocation with structured input."""
    engine = comp.Engine()
    
    # Create a module
    module_ast = comp.ast.Module([])
    module = engine.run(module_ast)
    
    # Create a block that creates output
    block_ast = comp.ast.Block([
        comp.ast.FieldOp(
            key=comp.ast.String("output"),
            value=comp.ast.String("processed")
        )
    ])
    raw_block_value = engine.run(block_ast, module=module)
    
    # Create a block shape that expects a struct with 'value' field
    block_shape_def = comp.BlockShapeDefinition([
        comp.ShapeField(name='value', shape='num')
    ])
    morph_result = comp.morph(raw_block_value, block_shape_def)
    assert morph_result.success
    
    # Store in local scope
    block_struct = comp.Value({'process': morph_result.value})
    
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
    
    result = engine.run(pipeline, local=block_struct, module=module)
    
    # Should have: {output: "processed"}
    assert result.is_struct
    assert comp.Value('output') in result.struct
    assert result.struct[comp.Value('output')].data == "processed"


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
    
    # Should fail with appropriate error
    # Check for fail structure
    assert result.is_struct
    assert comp.Value('message') in result.struct
    message = result.struct[comp.Value('message')].data
    # Message should mention Block
    assert 'Block' in message
