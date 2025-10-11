# Generator-Based Evaluation Engine

This is a **proof-of-concept** implementation of a generator-based evaluation engine for Comp. It's separate from the existing `comp.run` runtime to explore the architecture without disrupting working code.

## Key Concepts

### AST Nodes as Generators

Each AST node has an `evaluate(ctx)` method that returns a generator:

```python
class BinaryOp:
    def evaluate(self, ctx):
        # Yield child expressions to evaluate
        left = yield self.left
        right = yield self.right
        
        # Return final computed value
        return apply_op(left, right)
```

The generator:
- **Yields**: Child AST nodes that need evaluation
- **Receives**: `Value` objects (results from evaluating children)
- **Returns**: Final `Value` result

### Evaluation Context

The `EvalContext` manages execution. It supports two modes:

#### Recursive Mode (Default)
```python
ctx = EvalContext(use_stackless=False)
result = ctx.evaluate(expr)
```

- Uses Python's call stack
- Simple and fast
- Limited by Python's recursion depth (~1000)

#### Stackless Mode
```python
ctx = EvalContext(use_stackless=True)
result = ctx.evaluate(expr)
```

- Maintains explicit operation stack
- No recursion depth limit
- Can handle deeply nested expressions

### Automatic Short-Circuiting

**No manual skip checking required in AST nodes!**

```python
class BinaryOp:
    def evaluate(self, ctx):
        left = yield self.left   # If this fails...
        right = yield self.right # ...this never executes!
        return apply_op(left, right)
```

The context detects "skip values" (failures, etc.) and automatically:
1. Stops the generator
2. Propagates the skip value up
3. Never resumes the abandoned generator

This is **true short-circuiting** - the generator execution literally stops.

## Files

- **`value.py`**: Runtime values (`Value`, `Tag`, builtin tags)
- **`nodes.py`**: AST nodes with generator-based evaluation
- **`context.py`**: Evaluation context (recursive & stackless)
- **`test_engine.py`**: Comprehensive test suite
- **`demo.py`**: Interactive demonstration

## Running

### Run the demo:
```bash
python -m comp.engine.demo
```

### Run the tests:
```bash
pytest src/comp/engine/test_engine.py -v
```

## Architecture Highlights

### 1. Clean Separation
AST nodes only contain evaluation logic - no manual state tracking, no skip checking boilerplate.

### 2. Generator Protocol
```
Yield:   ASTNode    (what to evaluate)
Receive: Value      (evaluation result)
Return:  Value      (final result)
```

### 3. Execution Flexibility
Same AST nodes work with both recursive and stackless execution - the context chooses.

### 4. Python 3.3+ Features
Uses generator return values (`return` in generators becomes `StopIteration.value`). This is the same mechanism that powers Python's `async`/`await`.

## Examples

### Simple arithmetic:
```python
from comp.engine import *

ctx = EvalContext()

# 2 + 3
expr = BinaryOp("+", Number(2), Number(3))
result = ctx.evaluate(expr)
print(result.data)  # 5
```

### Nested operations:
```python
# (2 + 3) * 4
expr = BinaryOp("*",
    BinaryOp("+", Number(2), Number(3)),
    Number(4)
)
result = ctx.evaluate(expr)
print(result.data)  # 20
```

### Failure propagation:
```python
# 5 + (1 / 0)  -> failure propagates
expr = BinaryOp("+",
    Number(5),
    BinaryOp("/", Number(1), Number(0))
)
result = ctx.evaluate(expr)
print(result.tag)  # #fail.type
print(result.data["message"])  # "Division by zero"
```

### Stackless for deep recursion:
```python
ctx = EvalContext(use_stackless=True)

# Build: 1 + 1 + 1 + ... (1000 times)
expr = Number(1)
for _ in range(999):
    expr = BinaryOp("+", expr, Number(1))

result = ctx.evaluate(expr)
print(result.data)  # 1000
```

## Comparison with Existing Runtime

| Feature | Current (`comp.run`) | This Engine |
|---------|---------------------|-------------|
| Evaluation | Functions with explicit recursion | Generators with implicit state |
| Skip checking | Manual `if is_failure(x): return x` | Automatic via context |
| State tracking | Function call stack | Generator state |
| Deep recursion | Limited (~1000 depth) | Unlimited (stackless mode) |
| Short-circuit | Manual checks everywhere | True short-circuit (generator stops) |
| Code clarity | Explicit but verbose | Clean and concise |

## Next Steps

This is a **proof-of-concept**. To integrate into the main runtime:

1. **Add more AST node types** (Structure, Pipeline, FunctionCall, etc.)
2. **Add scope management** (variables, function calls, imports)
3. **Port existing tests** to validate equivalence
4. **Performance testing** to compare with current runtime
5. **Migration strategy** to move from `comp.run` to generator-based

## Philosophy

This approach treats evaluation as **coroutine-style computation**:
- AST nodes are "tasks" that cooperatively yield control
- Context is the "scheduler" that manages execution
- Skip values are like "exceptions" that propagate automatically

It's the same pattern Python uses for `async`/`await` - battle-tested and proven.
