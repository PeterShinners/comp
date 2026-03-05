# Pipeline Modifier System Design

*Transforming and optimizing Comp pipelines through meta-operations*

## Overview

Pipeline modifiers are special operations that can inspect, transform, and optimize the pipeline itself before execution. Rather than just appending operations to a data flow, modifiers can reach back into the pipeline structure and reorganize it for efficiency, instrumentation, or enhanced functionality.

This system enables powerful capabilities like adding progress bars to any pipeline, optimizing database queries, or parallelizing operations—all without modifying the original business logic.

## Core Concepts

### Pipeline vs Lazy Structure

Functions in Comp return pipeline segments that compose into larger pipelines. Only when a pipeline is assigned or evaluated does it render into a lazy structure:

```comp
; Functions return pipeline segments
|filter .{x > 5}    ; Returns: Pipeline[Filter(x > 5)]

; Composition creates pipelines
data |filter .{x > 5} |map .{x * 2}
; Returns: Pipeline[Source(data), Filter(x > 5), Map(x * 2)]

; Assignment renders to lazy structure
result = data |filter .{x > 5} |map .{x * 2}
; NOW becomes lazy structure
```

### Pipeline Modifier Syntax

Pipeline modifiers use the `|<<` operator to visually distinguish them from normal operations. The double angle brackets signal "this operation modifies the upstream pipeline":

```comp
data |filter .{valid}
     |map .{transform}
     |<<optimize        ; Modifies pipeline structure
     |<<progressbar     ; Adds progress tracking
```

## Operation Identification

Pipeline modifiers identify operations to transform using shape-based patterns. Standard library functions use consistent naming conventions:

```comp
; Standard iterators use ~iterable shape
!func |map ~{source ~iterable} ^{transform ~block} = { ... }
!func |filter ~{source ~iterable} ^{predicate ~block} = { ... }
!func |fold ~{source ~iterable} ^{initial reducer ~block} = { ... }
```

This enables modifiers to recognize iteration points without additional metadata:

```comp
!func |<<progressbar ~{pipeline ~pipeline} = {
    ; Find operations with ~iterable inputs
    @iterations = pipeline |find-ops-with-shape ~iterable
    
    ; Inject progress tracking
    @wrapped = @iterations |wrap-blocks-with-progress
    pipeline |rebuild-with @wrapped
}
```

## Implementation Patterns

### Block Wrapping

Modifiers can wrap block arguments to inject behavior:

```comp
!func |wrap-with-progress ~{inner-block ~block} -> ~block = {
    .{
        $ctx.progress |increment
        $in |. inner-block  ; Execute original block
    }
}
```

### Pipeline Introspection

Pipelines expose their structure for examination:

```comp
@pipeline = data |complex-operations
@ops = @pipeline |get-operations
; Returns: [{type=#filter shape=~iterable block=...} ...]
```

### Pipeline Reconstruction

Modifiers return new pipelines with transformed operations:

```comp
!func |<<optimize ~{pipeline ~pipeline} = {
    @ops = pipeline |get-operations
    
    ; Merge consecutive filters
    @optimized = @ops |merge-consecutive #filter
    
    ; Return new pipeline
    pipeline |rebuild-with @optimized
}
```

## Use Cases

### Progress Tracking

Add progress bars to any pipeline without modifying code:

```comp
data |load
     |filter .{valid}
     |map .{expensive-transform}
     |<<progressbar    ; Automatically tracks all iterations
```

### Query Optimization

Push operations to the database:

```comp
db.users |filter .{active}
         |map .{name email}
         |<<push-to-sql    ; Converts to SELECT name, email WHERE active
```

### Performance Optimization

Combine and reorder operations:

```comp
data |filter .{x > 5}
     |filter .{x < 100}
     |map .{x * 2}
     |<<optimize    ; Merges filters, may reorder operations
```

### Development Tools

Add debugging and profiling:

```comp
data |complex-pipeline
     |<<debug           ; Logs data at each stage
     |<<profile-time    ; Measures operation timing
     |<<trace          ; Records execution path
```

## Fallback for Complex Cases

When automatic detection isn't sufficient, manual control is available:

```comp
data |begin-progress total=1000
     |custom-processor
     |each .{
         $in |increment-progress |process
     }
     |finish-progress
```

## Design Principles

1. **Visual Clarity** - The `|<<` syntax makes pipeline modification obvious
2. **Shape-Based Detection** - Uses existing shape system for operation identification
3. **Composable** - Multiple modifiers can be chained
4. **Non-Invasive** - Existing code works unchanged
5. **Fallback Control** - Manual options available for complex cases

## Benefits

- **Zero-Cost Enhancement** - Add features without touching business logic
- **Retroactive Improvement** - Enhance existing pipelines with new capabilities
- **Ecosystem Friendly** - Third-party modifiers can extend functionality
- **Performance Transparent** - Optimizations can be added/removed freely
- **Development Velocity** - Quick iteration with debugging modifiers

## Standard Modifiers

The standard library should provide common modifiers:

- `|<<progressbar` - Automatic progress tracking
- `|<<optimize` - Basic operation fusion and reordering
- `|<<cache` - Memoization of expensive operations
- `|<<parallelize` - Parallel execution where safe
- `|<<retry` - Automatic retry logic
- `|<<timeout` - Operation timeouts
- `|<<debug` - Development-time introspection

## Implementation Requirements

1. **Pipeline objects** must be introspectable before evaluation
2. **Operation metadata** needs consistent shape naming (e.g., `~iterable`)
3. **Lazy evaluation** must be preserved through transformation
4. **Fast paths** like `|length` enable efficient analysis without full evaluation

This system transforms Comp from a pipeline language into a meta-pipeline language where the computation itself becomes malleable and optimizable.