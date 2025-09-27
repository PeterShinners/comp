# Pipelines, Flow Control, and Failure Handling

*Design for Comp's pipeline operations, control flow patterns, and error management*

## Overview

Comp uses pipelines to eliminate the nested function call spaghetti. The `|` labeling and operators creates readable left-to-right data flow—like a recipe where each step transforms what came before. The syntax steers towards a flatter namespace to avoid excessive nesting and bracing.

Control flow and error handling work through functions that accept block arguments, providing a consistent approach that scales from simple transformations to complex workflows.

Pipeline modifiers using the wrench operator (`|<<`) enable meta-operations that can inspect, transform, and optimize pipeline structure before execution. These modifiers can add capabilities like progress tracking, query optimization, or performance profiling without modifying the original business logic.

Every statement gets fresh pipeline input through `$in`, which resets to the function's original input at each statement boundary. This enables natural parallel processing where multiple statements independently transform the same data—no variable juggling required.

These principles combine to present code that reads linearly, while still accomodating practical
and real world situations. Failures propagate predictably without hidden control flow, and all operations compose through the same fundamental mechanism. The functions that process pipeline data are detailed in [Functions and Blocks](function.md), while structure operations are covered in [Structures, Spreads, and Lazy Evaluation](structure.md).

## Pipeline Fundamentals

A pipeline starts with either a value or a function. Starting with a value feeds that data into the first function. Starting with a function (marked by leading `|`) means the function gets no initial input or uses ambient data—perfect for things like timestamps or configuration lookups.

```comp
!func |process ~{data} = {
    ; Pipelines with value input
    validated = $in |validate
    transformed = $in |transform
    
    ; Pipeline without initial value
    timestamp = (|now/time)
    
    ; Explicit pipeline with multiple steps
    result = $in |validate |transform |save
    
    ; All results combined
    {validated transformed timestamp result}
}
```

The `$in` reference provides access to pipeline data and resets at each
statement boundary. This enables natural parallel processing patterns where
multiple statements work on the same input data independently. Field references
use undecorated tokens that cascade through output being built to input.

## Statements and Temporaries

Each statement in Comp performs one of three actions based on its target. These
actions determine how the pipeline's result is used and whether it contributes
to the output structure being built.

**Variable Assignment** uses `@name` followed by `=` to create
function-local variables that can be referenced later in the function. These
variables exist only within the function's scope and are immutable once
assigned.

**Named Assignment** starts with a field name and `=`, assigning the pipeline
result to a named field in the output structure. Conflicting field names
override previous values, though this behavior can be modified with weak (`=?`)
or strong (`=*`) assignment operators.

**Unnamed Assignment** has no assignment target, adding the pipeline result as
an unnamed field to the output structure. These unnamed fields maintain their
order and can be accessed by position.

```comp
!func |process-data ~{data} = {
    ; Local variables store intermediate results
    @threshold = average * 1.5
    
    ; Use local variable in pipeline
    high-values = $in |filter {value > @threshold}
```

Function-local variables provide a crucial scope separate from field
lookups. They must always be explicitly referenced with the `@` prefix and
can only be used after definition.

## Control Flow Through Functions

Control flow in Comp uses functions with block arguments rather than special
syntax. This unification means all control flow follows the same patterns as
data transformation - it's just functions all the way down.

The core conditional functions - `if`, `when`, and `match` - cover the spectrum
from simple branches to complex pattern matching. The `if` function provides
classic if-then-else semantics. The `when` function handles single conditions
without an else clause. The `match` function enables pattern matching with
multiple conditions tested in order. All accept blocks that capture the current
scope and execute conditionally.

```comp
!func |process-request ~{request} = {
    ; Multiple conditional patterns
    response-type = $in |if {priority == urgent} 
                             immediate 
                             queued
    
    $in |when {response-type == immediate} {
        (%"Urgent: ${summary}" |alert-team)
    }
    
    status |match
        {$in == 200} {$in |handle-success}
        {$in >= 500} {$in |handle-server-error |alert-ops}
        {$in >= 400} {$in |handle-client-error}
        {#true} {$in |log-unknown |investigate}
}
```

Iteration follows the same function-with-blocks pattern. The `map` function
transforms each element and collects results, while `each` performs side effects
without collection. The `filter` function selects matching elements, and `fold`
reduces collections to single values using an accumulator. These functions
recognize special control tags - `#skip` continues to the next element, `#break`
stops iteration immediately, and any failure stops iteration and propagates the
error.

```comp
!func |analyze-records ~{records} = {
    ; Complete iteration pipeline
    processed = $in |filter {status != archived}
                   |map {
                       $in |if {priority < 0} 
                               {#skip} 
                               {$in |validate |enhance |{$in processed=(|now/time)}}
                   }
                   |fold {total=0 count=0} {
                       {total=(total + amount) count=(count + 1)}
                   }
    
    {records=processed.count average=processed.total/processed.count}
}
```

## Failure Management System

Failures in Comp are structures containing a `#fail` tag, providing a unified
error model that integrates naturally with the pipeline system. Rather than
exceptions that break control flow or error codes that require manual checking,
failures flow through pipelines with predictable propagation rules.

The language defines a hierarchical `#fail` tag system that categorizes errors
by type and origin. This hierarchy enables both specific and general error
handling - you can handle `#timeout.io.fail` specifically or work with all
`#io.fail` errors together. Functions generate failures for runtime errors like
missing fields, failed type conversions, or permission violations. User code
creates failures by simply including the appropriate `#fail` tag in a structure.

Modules can extend the failure hierarchy to define domain-specific error
categories. These extensions work like any tag extension - they create new leaf
nodes in the hierarchy while maintaining compatibility with parent handlers. For
detailed information about tag hierarchies and extension mechanisms, see [Tag
System](tag.md).

```comp
; Core hierarchy
#fail
  #io
    #missing
    #permission  
    #timeout
  #value
    #shape
    #constraint

; Module extension
!tag fail += {
    #database = Database operation failed {
        #connection = Unable to connect
        #constraint = Constraint violation  
        #deadlock = Transaction deadlock detected
    }
    #auth = Authentication failed {
        #expired = Credentials expired
        #invalid = Invalid credentials
    }
}

; Usage
{#connection.database.fail message="Connection pool exhausted" pool-id=5}
```

## Failure Recovery Patterns

Comp provides multiple mechanisms for handling failures, from simple fallbacks
to complex recovery procedures. The choice of mechanism depends on the
complexity of the recovery needed and whether you want to replace the failure or
perform cleanup.

The `??` fallback operator provides immediate recovery for single operations. It
receives the original input (not the failure) and provides an alternative value.
Multiple fallbacks can be chained, creating a cascade of alternatives tried in
order. This operator shines for providing defaults when optional fields are
missing or operations might fail.

```comp
; Cascading fallbacks for configuration
port = config.port ?? env.PORT ?? 8080
display-name = user.nickname ?? user.username ?? user.email ?? Anonymous

; Fallback with computation
timeout = settings.timeout ?? (settings.retry-count * 1000) ?? 5000
```

The `|?` operator handles failures with more complex recovery logic. It can be
configured with tag filters to handle specific failure types, with multiple `|?`
operators creating a chain of handlers tested in order.

```comp
!func |process-transaction ~{data} = {
    $in |validate
        |execute-steps
        |? {#io.fail} {$in |retry-with-backoff}
        |? {#deadlock.database.fail} {$in |wait-and-retry}
        |? {
            ; General failure - multiple operations for recovery
            @error = $in
            (%"Operation failed: ${@error.message}" |log)
            @error |cleanup-resources |{status=#failed original=$in}
        }
}

; Complex recovery in a single block
$in |risky-operation |? {
    @error = $in
    (%"Operation failed: ${@error.message}" |log)
    @error.code |match
        {$in >= 500} {$in |wait-and-retry}
        {$in == 429} {$in |backoff-exponentially}
        {#true} {$in |use-fallback-service}
}
```

## Pipeline Composition

Complex pipelines benefit from clear composition patterns. Parentheses clearly
delimit pipeline boundaries, making it obvious where transformations begin and
end. Within these boundaries, functions chain naturally through the `|`
operator.

The fresh `$in` at each statement boundary enables elegant parallel processing
patterns where multiple independent operations process the same input, then
combine their results. Each statement gets the same input, processes
independently, and contributes to the final structure.

```comp
!func |comprehensive-analysis ~{data} = {
    ; Three independent analyses on same input
    structure-valid = $in |validate-structure
    business-valid = $in |validate-business-rules  
    security-valid = $in |validate-security
    
    $in |if {structure-valid && business-valid && security-valid}
            {$in |process}
            {#validation.fail issues={structure-valid business-valid security-valid}}
}

!func |parallel-enrichment ~{record} = {
    ; Multiple enrichments of the same record
    with-score = $in |calculate-score
    with-category = $in |determine-category
    with-timestamp = $in |add-processing-time
    
    ; Merge all enrichments
    {$in ..with-score ..with-category ..with-timestamp}
}
```

## Pipeline Modifiers: The Wrench Operator

The wrench operator (`|<<`) enables pipeline meta-operations that inspect, transform, and optimize pipeline structure before execution. Unlike regular pipeline operations that transform data, wrench operations modify the pipeline itself, enabling powerful capabilities like progress tracking, query optimization, and performance instrumentation.

Pipeline modifiers identify operations using shape-based patterns, leveraging the consistent naming conventions in standard library functions. Operations with `~iterable` inputs are recognized as iteration points, enabling automatic progress tracking or parallelization without additional metadata.

```comp
; Automatic progress tracking
data |filter .{valid}
     |map .{expensive-transform}
     |<<progressbar    ; Analyzes pipeline, adds progress to all iterations

; Database query optimization  
db.users |filter .{active}
         |map .{name email}
         |<<push-to-sql    ; Converts to optimized SQL query

; Development and profiling
data |complex-pipeline
     |<<debug           ; Logs data at each stage
     |<<profile-time    ; Measures operation timing
```

The wrench operator transforms Comp from a pipeline language into a meta-pipeline language where the computation structure itself becomes malleable and optimizable. Multiple modifiers can be chained, creating sophisticated transformation and optimization chains.

For comprehensive details on pipeline modifier implementation, shape-based operation detection, and the full system design, see the [Pipeline Modifier System Design](../docs/early/28-wrench.md).

## Blocks and Pipeline Context

Blocks can contain pipelines without requiring additional parentheses, as the
block boundaries provide clear scope. This keeps the syntax clean for common
patterns like filtering and mapping.

```comp
; Block contains pipeline - no extra parens needed
items |map {$in |validate |enhance}

; Equivalent to (but cleaner than)
items |map {($in |validate |enhance)}

; At statement level, no parens needed
; Simple variable usage in pipeline
@result = $in |process |validate

; In expression position, parens required
total = (base |calculate) + (bonus |calculate)
```

## Placeholder Operator

The `???` operator serves as a placeholder for not-yet-implemented code. It can
appear anywhere an expression is expected and always evaluates to
`{#not-implemented.fail}` when reached at runtime. This enables sketching code
structure with compilable placeholders. For more information about failure types
and error handling patterns, see [Tag System](tag.md).

```comp
!func |incomplete ~{data} = {
    validated = $in |validate
    processed = ???  ; TODO: implement processing
    saved = processed |save
    {validated saved}
}

; Runtime behavior
??? ; Returns {#not-implemented.fail location="file.comp:42"}
```
