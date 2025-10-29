# Lazy Structures

## Overview

Lazy structures are a variant of structures where field values are evaluated on-demand rather than immediately. They use the `^{}` syntax and provide:

- **On-demand evaluation**: Field values only compute when first accessed
- **Caching**: Each field evaluates exactly once and caches the result
- **Introspection**: Field names are known without triggering evaluation
- **Linear evaluation**: Fields evaluate in definition order for predictable side effects
- **Deterministic failure**: First error permanently fails the structure

## Syntax

```comp
; Regular structure - evaluates immediately
$eager = {
    x = [|expensive-computation]  ; Runs now
    y = [|another-computation]    ; Runs now
}

; Lazy structure - evaluates on access
$lazy = ^{
    x = [|expensive-computation]  ; Deferred
    y = [|another-computation]    ; Deferred
}

$lazy.x  ; Now x evaluates (and caches)
$lazy.y  ; Now y evaluates (and caches)
```

## Evaluation Semantics

### Linear Evaluation Order

Fields evaluate in definition order. To access field N, all fields 0..N-1 must evaluate successfully first.

```comp
$lazy = ^{
    a = [|print "computing a"] 1
    b = [|print "computing b"] 2
    c = [|print "computing c"] 3
}

$lazy.c  ; Prints: "computing a", "computing b", "computing c"
$lazy.a  ; No output - already cached
```

This ensures:
- Side effects happen in predictable order
- Later fields can depend on earlier fields
- Evaluation order is deterministic

### Caching

Each field evaluates exactly once. Subsequent accesses return the cached value.

```comp
$counter = 0

$lazy = ^{
    x = {
        $counter = [|+ $counter 1]
        $counter
    }
}

$lazy.x  ; Returns 1, increments counter
$lazy.x  ; Returns 1 (cached), counter unchanged
$lazy.x  ; Returns 1 (cached), counter unchanged
```

### Introspection Without Evaluation

Field names are known statically, allowing introspection without triggering evaluation.

```comp
$lazy = ^{
    expensive = [|compute-for-hours]
    moderate = [|compute-for-minutes]
    cheap = 5
}

[|keys $lazy]   ; Returns ["expensive" "moderate" "cheap"]
[|size $lazy]   ; Returns 3
[|has-key $lazy "expensive"]  ; Returns true

; None of the above trigger evaluation
```

## Failure Semantics

When a field evaluation fails, the entire lazy structure becomes permanently failed. All subsequent field accesses (including already-cached fields) immediately raise the cached error.

```comp
$lazy = ^{
    a = 1
    b = 2
    c = [|fail "explosion"]
    d = 4
    e = 5
}

$lazy.a  ; ✓ Returns 1, cached
$lazy.b  ; ✓ Returns 2, cached
$lazy.c  ; ✗ Fails with "explosion", error cached
$lazy.a  ; ✗ Immediately fails with cached "explosion"
$lazy.d  ; ✗ Immediately fails with cached "explosion"
$lazy.c  ; ✗ Immediately fails with cached "explosion"
```

### Why This Design?

1. **Predictable** - Same access pattern always produces same results
2. **Safe** - Can't accidentally skip failures and use later fields
3. **Clear state** - Structure is either healthy or failed, never partially failed
4. **Deterministic** - No retry logic, no hidden behavior

### Handling Failures Gracefully

**Inline fallbacks** - Handle potential failures at definition time:

```comp
$safe = ^{
    critical = [|must-succeed]
    optional = [|might-fail] ?? !nil
    more = [|continues-after-optional]
}

$safe.more  ; Works even if optional failed and returned !nil
```

**Try-catch** - Handle failures at access time:

```comp
$lazy = ^{
    a = 1
    b = [|might-fail]
    c = 3
}

$result = !try {
    $lazy.c
} !catch {
    ; Failure occurred - inspect what succeeded
    [|log "Partial results:" $lazy.evaluated]
    !nil
}
```

**Separate structures** - Isolate risky operations:

```comp
$safe_part = ^{a=1 b=2}
$risky_part = ^{c=[|might-fail] d=4}

$safe_part.b  ; Always works
$risky_part.d  ; Only fails if c fails
```

## Context Capture

Lazy structures capture their creation context (bindings and namespace), similar to blocks.

```comp
!let x=5 y=10 {
    $lazy = ^{
        sum = [|+ $x $y]      ; Captures x and y
        product = [|* $x $y]  ; Captures x and y
    }
}

$lazy.sum  ; Returns 15 (using captured values)
```

The captured context remains valid for the lifetime of the lazy structure.

## Resource Management

### Handle Cleanup

When a lazy structure goes out of scope, any handles in successfully-evaluated fields are automatically cleaned up via `|drop` dispatch.

```comp
!let {
    $lazy = ^{
        db = [|open-database "file.db"]
        result = [$db |query "SELECT * FROM users"]
    }
    
    $lazy.db  ; Opens database
    ; Use database...
}
; Block exits - database handle automatically closed
```

### Partial Evaluation Cleanup

If a lazy structure fails partway through evaluation:

```comp
!let {
    $lazy = ^{
        db = [|open-database "file.db"]
        result = [$db |query "BAD SQL"]  ; Fails
    }
    
    $lazy.result  ; Opens db, then fails on query
}
; Block exits - db handle still gets cleaned up
```

Only successfully-evaluated fields are cleaned up. Unevaluated fields never created resources, so they're safely ignored.

### Explicit Cleanup

```comp
$lazy = ^{
    db = [|open-database "file.db"]
    result = [$db |query "SELECT..."]
}

$lazy.db  ; Opens database
!drop $lazy  ; Explicitly forces cleanup of evaluated fields
```

## Comparison With Streams

Lazy structures and streams serve different purposes:

| Feature | Lazy Structure | Stream |
|---------|---------------|---------|
| Size | Finite, known field names | Potentially infinite |
| Access | Random access by field name | Sequential only |
| Evaluation | Each field once, cached | Generate on each call |
| Memory | All evaluated fields in memory | Constant or unbounded |
| Use case | Expensive computations, dependencies | Large/infinite sequences |

```comp
; Lazy structure - finite data, lazy evaluation
$lazy = ^{
    users = [$db |query "SELECT * FROM users"]
    count = [|length $users]
    summary = [|summarize $users]
}

; Stream - potentially infinite data
$stream = !stream {
    $i = 0
    !loop {
        !yield $i
        $i = [|+ $i 1]
    }
}
```

### Conversions

```comp
; Stream to lazy structure (collects N items)
$lazy = [|stream-to-struct $stream 100]
; Result: ^{0=0 1=1 2=2 ... 99=99}

; Lazy structure to stream (yields each field value)
$stream = [|struct-to-stream $lazy]
; Yields values in field definition order
```

## Use Cases

### Expensive Computations

```comp
$report = ^{
    data = [|fetch-large-dataset]
    analysis = [|analyze $data]
    visualization = [|create-viz $analysis]
    summary = [|summarize $analysis]
}

; Only fetch data and create summary (skip expensive viz)
[|print $report.summary]
```

### Dependency Pipelines

```comp
$pipeline = ^{
    raw = [|fetch-data $source]
    cleaned = [|clean $raw]
    validated = [|validate $cleaned]
    transformed = [|transform $validated]
    result = [|save $transformed]
}

; Each step only runs when needed, in order
$pipeline.result  ; Runs entire pipeline
```

### Conditional Computation

```comp
$config = ^{
    basic = [|load-config "basic.conf"]
    advanced = [|load-config "advanced.conf"]  ; Expensive
    experimental = [|load-config "experimental.conf"]  ; Very expensive
}

; Only load what's needed
$settings = if $mode == "basic" {
    $config.basic
} else if $mode == "advanced" {
    $config.advanced
} else {
    $config.experimental
}
```

### Partial Success Handling

```comp
$batch = ^{
    step1 = [|process-batch-1]
    step2 = [|process-batch-2]
    step3 = [|process-batch-3]  ; Might fail
    step4 = [|process-batch-4]
}

!try {
    $batch.step4  ; Try all steps
} !catch {
    [|log "Processed successfully:" [|keys $batch.evaluated]]
    ; Continue with partial results
}
```

## Implementation Notes

### AST Representation

```comp
{
    node = #lazy-structure
    fields = {
        x = {node=#function-call ...}
        y = {node=#literal value=5}
    }
    source = {line=10 col=5}
}
```

### Runtime Representation

```python
class LazyStructure:
    def __init__(self, ast_fields, context):
        self.fields = ast_fields          # {name: AST node}
        self.evaluated = {}               # {name: evaluated value}
        self.eval_order = list(ast_fields.keys())
        self.context = context            # Captured evaluation context
        self.failed_at = None             # Cached error (if failed)
        self.failed_field = None          # Which field failed
    
    def keys(self):
        """Return field names without evaluating"""
        return self.eval_order
    
    def get(self, key):
        """Get field value, evaluating if needed"""
        # If structure has failed, always raise cached error
        if self.failed_at is not None:
            raise self.failed_at
        
        # Return cached value if available
        if key in self.evaluated:
            return self.evaluated[key]
        
        # Evaluate linearly up to requested key
        for field_name in self.eval_order:
            if field_name in self.evaluated:
                continue
            
            try:
                value = evaluate(
                    self.fields[field_name], 
                    self.context
                )
                self.evaluated[field_name] = value
            except Exception as e:
                self.failed_at = e
                self.failed_field = field_name
                raise
            
            if field_name == key:
                break
        
        return self.evaluated[key]
    
    def cleanup(self):
        """Called when structure goes out of scope"""
        for value in self.evaluated.values():
            if is_handle(value):
                dispatch_drop(value)
```

### Standard Library Functions

```comp
; Force evaluation of all fields
[|force $lazy]  ; Returns fully-evaluated structure

; Check if structure is lazy
[|is-lazy $lazy]  ; Returns true

; Get evaluated fields (for debugging)
[|evaluated-keys $lazy]  ; Returns list of computed field names

; Convert between lazy and eager
[|to-lazy $eager]   ; Convert structure to lazy
[|to-eager $lazy]   ; Force all fields, return regular structure
```

## Edge Cases

### Empty Lazy Structure

```comp
$empty = ^{}

[|keys $empty]  ; Returns []
[|size $empty]  ; Returns 0
```

Valid but not particularly useful.

### Nested Lazy Structures

```comp
$outer = ^{
    inner = ^{
        x = [|expensive-1]
        y = [|expensive-2]
    }
    z = [|expensive-3]
}

$outer.inner.x  ; Evaluates: outer.inner, then inner.x
```

Lazy structures can be nested. Each level evaluates independently.

### Circular References

```comp
$lazy = ^{
    a = $lazy.b  ; Reference to later field
    b = 5
}

$lazy.a  ; Error: can't reference unevaluated field
```

Cannot reference later fields from earlier fields in the same structure. Linear evaluation prevents this.

### Spreading Lazy Structures

```comp
$lazy = ^{x=1 y=2}

$mixed = {
    ...$lazy  ; Forces evaluation of $lazy
    z = 3
}
```

Spreading a lazy structure forces immediate evaluation of all fields.

## Design Rationale

### Why Linear Evaluation?

1. **Predictable side effects** - Side effects happen in definition order
2. **Dependencies work naturally** - Later fields can rely on earlier fields
3. **Simpler mental model** - No need to track complex dependency graphs
4. **Efficient implementation** - No need for dependency resolution

### Why Cache Failures?

1. **Determinism** - Same access always produces same result
2. **Efficiency** - No wasted retries on hopeless operations
3. **Safety** - Forces proper error handling, can't accidentally skip failures
4. **Simplicity** - No retry logic, no special error states

### Why Not Recursive Evaluation?

Could allow lazy evaluation to continue past failures by only evaluating dependencies:

```comp
$lazy = ^{
    a = 1
    b = [|fail "error"]
    c = 3  ; Doesn't depend on b
}

$lazy.c  ; Could skip b and return 3
```

**Rejected because:**
- Requires dependency analysis (complex)
- Side effects become unpredictable
- Harder to reason about evaluation order
- Doesn't match the "linear evaluation" model

Users can achieve this with separate structures or inline fallbacks if needed.

