# Phase 01-09: Pipeline Operations

**Status**: ❌ IN PROGRESS
**Target start**: After scopes and assignments are complete

## Overview

Transform pipeline parsing from the current binary tree expression model to a flat list of simple operations. Currently, `StructureOperation` has a single "expression" field containing a tree of `BinaryOperation` nodes. This phase restructures pipelines to store a flat sequence of pipeline operations, making them easier to reason about during implementation and optimization.

This change aligns the AST with how pipelines will actually be executed - as a linear sequence of transformations rather than nested expressions. It also enables better pipeline analysis for features like the wrench operator (`|<<`) and pipeline optimization.

## Planned Features

### Pipeline Operation Types
- **Function calls**: `|validate`, `|process`, `|transform`
- **Structure operations**: `|{field=value}`, `|{..spread extra=data}`
- **Conditional pipelines**: `|if condition block else-block`  
- **Iteration operations**: `|map block`, `|filter block`, `|each block`
- **Failure handling**: `|? fallback-expression`
- **Pipeline modifiers**: `|<< modifier` (wrench operator)

### Flat Pipeline Representation
Instead of nested binary operations, store pipelines as flat lists:
```python
# Before (current): Single complex expression tree
StructureOperation(target, operator, BinaryOperation(left, "|", right))

# After: Flat list of simple operations  
PipelineExpression([
    PipelineStep("function", "|validate"),
    PipelineStep("function", "|process"), 
    PipelineStep("failure", "|?", fallback_expr),
    PipelineStep("modifier", "|<<", modifier_expr)
])
```

### Statement vs Expression Pipelines  
- **Statement pipelines**: Start with value, flow through operations
- **Expression pipelines**: Embedded in larger expressions, parenthesized
- **Block pipelines**: Within `.{pipeline}` blocks, no additional parens needed

## Success Criteria

### Pipeline Parsing
- [ ] Parse linear pipeline sequences: `data |validate |process |save`
- [ ] Parse function calls: `|transform`, `|database.query`, `|math/sqrt` 
- [ ] Parse structure operations: `|{result=value}`, `|{..base extra=field}`
- [ ] Parse failure handling: `|? fallback-value`, `|? {default-structure}`
- [ ] Parse pipeline modifiers: `|<< progressbar`, `|<< debug`

### AST Structure Changes
- [ ] Replace expression trees with flat `PipelineStep` lists
- [ ] `PipelineExpression` contains ordered sequence of operations
- [ ] Each `PipelineStep` has operation type and arguments
- [ ] Maintain compatibility with existing structure operations

### Expression Integration
- [ ] Support pipelines in expression contexts with proper precedence
- [ ] Handle parenthesized pipeline expressions
- [ ] Support pipeline results in binary operations
- [ ] Integrate with existing field access and structure operations

### Special Pipeline Forms  
- [ ] Leading function calls: `(|now/time)`, `(|generate-token)`
- [ ] Complex failure chains: `|? {type="fallback"} |? final-default`
- [ ] Nested structure pipelines: `{result=($in |process |validate)}`

## Implementation Plan

### Step 1: Define New AST Nodes
```python
class PipelineExpression(ASTNode):
    def __init__(self, steps: list[PipelineStep]):
        self.steps = steps

class PipelineStep(ASTNode):
    def __init__(self, step_type: str, operator: str, argument: ASTNode = None):
        self.step_type = step_type    # "function", "failure", "modifier", "structure"
        self.operator = operator      # "|", "|?", "|<<", etc.
        self.argument = argument      # Function reference, fallback expression, etc.
```

### Step 2: Update Grammar
```lark
// Pipeline as sequence of operations, not binary tree
pipeline: pipeline_start pipeline_step*

pipeline_start: expression
              | function_reference  // Leading function call

pipeline_step: PIPE function_reference                  -> pipeline_function
             | PIPE_FAILURE expression                  -> pipeline_failure  
             | PIPE_MODIFIER expression                 -> pipeline_modifier
             | PIPE structure_literal                   -> pipeline_structure

// Update existing structure operation parsing
structure_operation: (scope_target | field_target) assignment_op pipeline
                  | pipeline  // Positional pipeline
```

### Step 3: Update Parser Logic
- Modify `_CompTransformer` to build `PipelineExpression` nodes
- Convert existing binary operation parsing to flat step sequences
- Handle special cases for leading function calls and complex expressions

### Step 4: Test Integration
- Update existing tests that expect binary operation trees
- Add new tests for flat pipeline representation
- Ensure compatibility with structure operations and expressions

## Key Design Decisions

### Flat vs Nested Representation
- **Flat list** enables easier pipeline analysis and transformation
- **Sequential operations** match actual execution model
- **Better optimization** potential for pipeline fusion and wrench operations
- **Clearer semantics** for pipeline composition and failure propagation

### Operation Type Classification
- **Function calls** - Most common pipeline operation
- **Structure operations** - Creating/modifying structures in pipeline
- **Failure handling** - Explicit error recovery
- **Modifiers** - Meta-operations using wrench operator

### Precedence and Grouping
- Pipelines have lower precedence than most operators
- Parentheses required for pipeline expressions in arithmetic contexts
- Block boundaries provide implicit grouping for pipelines
- Statement-level pipelines need no additional grouping

### Backward Compatibility
- Keep existing `StructureOperation` structure 
- Replace expression trees with `PipelineExpression` where appropriate
- Maintain support for single expressions (non-pipeline operations)
- Gradual migration of complex expressions to pipeline form

## Examples to Support

```comp
// Basic pipeline sequences
data |validate |process |save
user |fetch-profile |check-permissions |format-response

// Leading function calls (no input)
timestamp = (|now/time)
token = (|generate-uuid)  
config = (|load-defaults)

// Structure operations in pipelines
user |{verified=#true created=(|now/time)} |save
input |validate |{result=value error=nil} |return

// Failure handling
risky-data |parse |? "invalid-data"
user |authenticate |? {error="auth-failed"} |? guest-user

// Pipeline modifiers (wrench operator)  
large-dataset |process |<<progressbar
database-query |optimize |<<push-to-sql |<<debug

// Complex nested pipelines
result = {
    processed = $in |validate |transform
    backup = $in |? fallback-processing
    timestamp = (|now/time)
}

// Mixed with other expressions
total = (items |map {value * 2} |sum) + base-amount
valid = (input |validate) && (permissions |check)

// Statement pipelines (no parens needed)
validated = $in |check-schema |verify-business-rules
result = validated |process |enrich |{status=#complete}
```

## AST Node Specifications

### PipelineExpression
```python
class PipelineExpression(ASTNode):
    """AST node representing a complete pipeline sequence."""
    def __init__(self, initial_value: ASTNode | None, steps: list[PipelineStep]):
        self.initial_value = initial_value  # Starting value, or None for leading function
        self.steps = steps                 # Ordered list of pipeline operations
```

### PipelineStep
```python
class PipelineStep(ASTNode):  
    """AST node representing a single pipeline operation."""
    def __init__(self, step_type: str, operator: str, argument: ASTNode):
        self.step_type = step_type  # "function", "structure", "failure", "modifier"
        self.operator = operator    # "|", "|?", "|<<", etc.
        self.argument = argument    # FunctionReference, expression, etc.
```

### Updated StructureOperation
```python
class StructureOperation(ASTNode):
    """Updated to support pipeline expressions."""
    def __init__(self, target: ASTNode | None, operator: str, expression: ASTNode):
        self.target = target        # ScopeTarget, FieldTarget, or None
        self.operator = operator    # "=", "=*", "=?"
        self.expression = expression # Now can be PipelineExpression
```

## Test Structure

Tests organized by pipeline operation type and complexity:
- `tests/test_pipeline_basic.py` - Simple pipeline sequences  
- `tests/test_pipeline_functions.py` - Function call operations
- `tests/test_pipeline_structures.py` - Structure operations in pipelines
- `tests/test_pipeline_failures.py` - Failure handling operations
- `tests/test_pipeline_modifiers.py` - Wrench operator and modifiers
- `tests/test_pipeline_expressions.py` - Pipelines in expression contexts
- `tests/test_pipeline_complex.py` - Nested and complex pipeline patterns

## Grammar Changes Preview

```lark  
// Current (binary tree approach)
?pipe_expr: or_expr
         | pipe_expr PIPE or_expr -> shape_union_operation

// New (flat pipeline approach)  
?pipeline_expr: or_expr
              | pipeline

pipeline: pipeline_start pipeline_step+

pipeline_start: or_expr
              | function_reference

pipeline_step: PIPE function_reference      -> pipeline_function_step
             | PIPE_FAILURE or_expr         -> pipeline_failure_step  
             | PIPE_MODIFIER or_expr        -> pipeline_modifier_step
             | PIPE structure_literal       -> pipeline_structure_step
```

## What We're NOT Building (Yet)

- Pipeline execution and runtime behavior
- Pipeline optimization and fusion
- Wrench operator implementation details
- Advanced pipeline analysis for query optimization
- Pipeline debugging and introspection tools

## Future Phases

- **Phase 02-08**: "Pipeline evaluation and failure propagation" - Runtime pipeline execution
- **Phase 03-XX**: "Wrench operator implementation" - Pipeline modifier system
- **Phase CC-XX**: "Pipeline optimization" - Query optimization and pipeline fusion