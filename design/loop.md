# Iteration and Streams

*Design for Comp's iteration patterns and stream abstractions*

## Overview

Iteration in Comp works through functions that process sequences element by element. With all function returns being lazy structures by default, iteration naturally becomes efficient—transformations are deferred until values are actually needed. Streams extend this pattern by representing potentially infinite sequences as blocks that generate values on demand.

The design unifies finite and infinite sequences through two complementary mechanisms: lazy structures for finite data that stores computed values, and stream blocks for potentially infinite sequences. Both work seamlessly with the same iteration functions, providing consistency across the language.

Functions in Comp always return lazy structures, while literal structures in source code are always eager. This simple rule provides automatic optimization while maintaining Comp's "everything is a structure" philosophy. For details on function definition and lazy evaluation, see [Functions and Blocks](function.md). For structure operations and data manipulation, see [Structures, Spreads, and Lazy Evaluation](structure.md).

## Lazy Evaluation by Default

Function returns in Comp are always lazy structures. Values are computed on demand and stored for future access. Literal structures in source code are always eager. This distinction makes the evaluation strategy predictable and efficient.

```comp
; Literals evaluate immediately
config = {
    startup = (|initialize)    ; Runs now
    value = 42                 ; Immediate
}

; Function returns are lazy
!func |process = {
    expensive = (|compute-heavy)  ; Not executed yet
    cheap = value * 2             ; Not executed yet
}
result = |process                ; Returns lazy structure
result.expensive                  ; NOW it computes and stores

; Pipeline operations automatically optimize
data = source 
    |filter .{score > 100}       ; Returns lazy structure
    |map .{$in |transform}        ; Still lazy
    |sort-by .{name}              ; Still lazy
    
data#0                            ; Evaluates first element only
data |length                      ; Can use field introspection
```

### Deferred Computation Benefits

Comp's lazy structures store computed values, allowing multiple operations on the same data:

```comp
; Process once, use many times
results = items |filter .{valid} |map .{$in |expensive-transform}

results |length      ; Works
results#5            ; Works - might trigger computation
results |sum         ; Still works - uses stored values
results |average     ; Still works
```

### Field Introspection

Special functions allow examining structure shape without triggering evaluation:

```comp
!func |fields ~{structure} = {
    ; Returns field names without evaluating lazy values
}

!func |indices ~{structure} = {
    ; Returns count of unnamed fields without evaluating
}

; Efficient operations on lazy structures
lazy-data |fields                ; ["a", "b", "c"] - no evaluation
lazy-data |fields |contains "x"  ; Check field existence
lazy-data |indices                ; Count unnamed fields
```

## Iteration Fundamentals

Iteration functions transform or consume sequences by applying blocks to elements. The block receives each element as its pipeline input and can return values or control signals. Special tags control iteration flow: `#skip` continues without yielding, `#break` terminates iteration, and failures propagate immediately. For more details on pipeline flow control and failure handling, see [Pipelines, Flow Control, and Failure Handling](pipeline.md).

```comp
; Basic iteration over structures
{1 2 3} |map .{$in * 2}         ; Returns lazy {2 4 6}
{1 2 3} |filter .{$in > 1}      ; Returns lazy {2 3}
{1 2 3} |each .{$in |print}     ; Side effects, returns {}

; Control flow in iteration blocks
items |map .{
    $in < 0 |if .{#skip} .{$in * 2}  ; Skip negative values
    $in > 100 |if .{#break} .{$in}   ; Stop at values over 100
}
```

### Eager Resolution

When eager evaluation is needed, spread operations force computation:

```comp
lazy-result = data |complex-pipeline
eager-result = {..lazy-result}   ; Forces all evaluation

; Or use an explicit function
!func |eager ~{structure} = {..structure}
lazy-result |eager
```

## Streams as Blocks

Streams are blocks that maintain internal state and generate values when invoked. They capture their creation context through closure, allowing them to maintain state across invocations. The stream protocol is minimal: invoke the block to get the next value or `#break` to signal exhaustion.

```comp
; Stream generator returns a block
!func |counter ^{start ~num = 0} = &{
    @current = ^start - 1
    
    ; Return block that generates values
    $out = .{
        @current = @current + 1
        @current
    }
}

; Usage
@counts = (|counter start=10)
value1 = |.@counts    ; 10
value2 = |.@counts    ; 11
```

### Stream Protocol

Streams follow simple conventions:
- Return values when invoked with no arguments
- Return `#break` when exhausted
- Continue returning `#break` if invoked after exhaustion
- May return `#skip` to continue without yielding
- Failures propagate normally

### Block Input Morphing

Functions use loose morphing (extra fields ignored), while blocks use strict morphing when typed. This prevents accidental capture of unintended data through closure. For comprehensive coverage of morphing rules and block type signatures, see [Shapes, Units, and Type System](shape.md).

```comp
; Stream blocks typically expect no input
!shape ~generator = ~block{}    ; Strict - rejects any input

; Predicate blocks expect specific input
!shape ~predicate = ~block{value ~any}  ; Strict - must match exactly

; Two-way communication streams
!func |stateful-stream = &{
    @state = 0
    
    $out = .{value ~num?} {
        @state = value ?? @state + 1
        @state
    }
}

@stream = (|stateful-stream)
|.@stream           ; 1 (default increment)
10 |.@stream        ; 10 (explicit value)
```

## Core Iterator Functions

The standard library provides essential iteration functions that work uniformly on structures and streams:

### |map
Transforms each element through a block, returning a lazy structure.

```comp
!func |map ~{source} ^{transform ~block{}} = {
    ; Returns lazy structure with transformed values
}

; Usage
{1 2 3} |map .{$in * 2}        ; Lazy {2 4 6}
@stream |map .{$in |enhance}   ; Transformed stream
```

### |filter
Selects elements matching a predicate, returning a lazy structure.

```comp
!func |filter ~{source} ^{predicate ~block{}} = {
    ; Returns lazy structure with matching elements
}

; Usage
{1 2 3 4 5} |filter .{$in % 2 == 0}  ; Lazy {2 4}
@stream |filter .{score > threshold}  ; Filtered stream
```

### |take
Limits iteration to a specified number of elements.

```comp
!func |take ~{source} ^{count ~num} = {
    ; Returns lazy structure with first n elements
}

; Usage
{1 2 3 4 5} |take 3           ; Lazy {1 2 3}
(|counter) |take 10           ; Finite stream of 10 values
```

### |fold
Reduces a sequence to a single value using an accumulator.

```comp
!func |fold ~{source} ^{initial ~any reducer ~block{}} = {
    ; Block receives {accumulator element}
    ; Forces evaluation of source elements
}

; Usage
{1 2 3} |fold 0 .{accumulator + element}  ; 6
@stream |take 100 |fold {} .{..accumulator element}  ; Collect stream
```

### |each
Executes a block for each element, primarily for side effects.

```comp
!func |each ~{source} ^{action ~block{}} = {
    ; Forces evaluation, returns empty structure
}

; Usage
{1 2 3} |each .{$in |print}
@stream |take 10 |each .{$in |process}
```

### |range
Creates a sequence of numbers as a lazy structure.

```comp
!func |range ^{from ~num to ~num step ~num = 1} = {
    ; Returns lazy structure
}

; Usage
(1 |range 10)        ; Lazy {1 2 3 4 5 6 7 8 9}
(0 |range 100 step=2)  ; Lazy {0 2 4 6 8...98}
```

### |counter
Creates an infinite counting stream.

```comp
!func |counter ^{start ~num = 0 step ~num = 1} = &{
    @current = ^start - step
    
    $out = .{
        @current = @current + step
        @current
    }
}

; Usage
@ids = (|counter start=1000)
@evens = (|counter start=0 step=2)
```

### |zip
Combines multiple sequences element-wise into a lazy structure.

```comp
!func |zip ~{sources[]} = {
    ; Returns lazy structure of combined elements
    ; Stops at shortest sequence
}

; Usage
(|zip {1 2 3} {a b c})  ; Lazy {{1 a} {2 b} {3 c}}
```

### |has-any?
Checks if a sequence contains any elements without forcing evaluation.

```comp
!func |has-any? ~{source} = {
    ; Uses field introspection for lazy structures
    ; Checks first element for streams
}

; Usage
results |has-any? |if
    .{results |process}
    .{#no-results}
```

## Stream Patterns

### Lazy Initialization

Streams can defer expensive initialization until first use:

```comp
!func |file-lines ^{path ~str} = &{
    @file = #nil
    @done = #false
    
    $out = .{
        @file == #nil |when .{
            @file = ^path |open/file
        }
        
        @done |if .{#break} .{
            @line = @file |read-line
            @line == #eof |if .{
                @done = #true
                @file |close
                #break
            } .{@line}
        }
    }
}
```

### Integration with Context

Streams naturally integrate with Comp's context system:

```comp
; Set random generator in context
$ctx.random = (123 |seed/random)

; Functions use context stream
!func |create-values ^{count ~num} = {
    @rng = $ctx.random ?? (|default-random)
    
    (1 |range ^count) |map .{
        |.@rng |uniform {0 1}
    }
}
```

## Performance Characteristics

The lazy-by-default design provides automatic optimization for common patterns:

**Existence checks** are nearly instant:
```comp
results = data |complex-filter |expensive-transform
results |has-any?  ; No evaluation needed
```

**Partial evaluation** only computes what's needed:
```comp
data = items |map .{$in |expensive} |filter .{valid}
data#0  ; Only evaluates until first valid item found
```

**Chained operations** defer all computation:
```comp
result = source
    |filter .{test1}
    |map .{transform}
    |filter .{test2}
    |sort-by .{field}
; Nothing computed until result is accessed
```

**Deferred computation** prevents redundant computation:
```comp
expensive = data |map .{$in |complex-calculation}
expensive |sum      ; Computes all values
expensive |average  ; Uses stored values
```

The overhead of lazy structures (bookkeeping and value storage) is offset by avoided computation. For pure streaming needs where value storage is undesirable, explicit stream blocks provide an alternative with minimal memory footprint.