"""Test block morphing from RawBlock to Block."""
import comp


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


def test_raw_block_morphs_to_block():
    """RawBlock should morph to Block when matched with BlockShapeDefinition."""
    engine = comp.Engine()
    
    # Create a module
    module_ast = comp.ast.Module([])
    module = engine.run(module_ast)
    
    # Create a simple raw block
    block_ast = comp.ast.Block([
        comp.ast.FieldOp(
            key=comp.ast.String("result"),
            value=comp.ast.Number(42)
        )
    ])
    raw_block_value = engine.run(block_ast, module=module)
    
    # Verify it's a RawBlock
    assert isinstance(raw_block_value.data, comp.RawBlock)
    
    # Create a BlockShapeDefinition
    block_shape_def = comp.BlockShapeDefinition([
        comp.ShapeField(name=None, shape='num')  # Unnamed num field
    ])
    
    # Morph the raw block to match the block shape
    morph_result = comp.morph(raw_block_value, block_shape_def)
    
    # Verify it's now a Block
    assert morph_result.success
    block_value = morph_result.value
    assert isinstance(block_value.data, comp.Block)
    assert block_value.data.input_shape is not None


def test_block_preserves_captured_context():
    """Block should preserve the context captured by RawBlock."""
    engine = comp.Engine()
    
    # Create a module
    module_ast = comp.ast.Module([])
    module = engine.run(module_ast)
    
    # Create a simple raw block
    block_ast = comp.ast.Block([
        comp.ast.FieldOp(
            key=comp.ast.String("result"),
            value=comp.ast.Number(42)
        )
    ])
    raw_block_value = engine.run(block_ast, module=module)
    
    # Verify it's a RawBlock with captured context
    assert isinstance(raw_block_value.data, comp.RawBlock)
    raw_block = raw_block_value.data
    # Note: module is None because block is created at module scope, not inside a function
    # The module would be accessed via function.module if defined inside a function
    assert raw_block.block_ast is not None
    
    # Create a BlockShapeDefinition and morph
    block_shape_def = comp.BlockShapeDefinition([
        comp.ShapeField(name=None, shape='num')
    ])
    morph_result = comp.morph(raw_block_value, block_shape_def)
    
    # Verify it's now a Block that delegates to the same RawBlock
    assert morph_result.success
    block = morph_result.value.data
    assert isinstance(block, comp.Block)
    assert block.raw_block is raw_block
    # Module comes from raw_block.module (which is None for module-scope blocks)
    assert block.module is raw_block.module  # Both are None in this case
    assert block.block_ast is raw_block.block_ast
