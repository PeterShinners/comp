# Pipelines, Flow Control, and Failure Handling

*Design for Comp's pipeline operations, control flow patterns, and error management*

## Overview

Comp uses pipelines to eliminate the nested function call spaghetti. Pipelines are enclosed in square brackets `[...]` with the `|` operator creating readable left-to-right data flow—like a recipe where each step transforms what came before. The syntax provides clear boundaries between data (structures) and computation (pipelines).

Control flow and error handling work through functions that accept block arguments, providing a consistent approach that scales from simple transformations to complex workflows.

Pipeline modifiers using the wrench operator (`|-|`) enable meta-operations that can inspect, transform, and optimize pipeline structure before execution. These modifiers can add capabilities like progress tracking, query optimization, or performance profiling without modifying the original business logic. The wrench operator requires a function reference, ensuring compile-time validation of pipeline modifiers.

Every statement gets fresh pipeline input through `$in`, which resets to the function's original input at each statement boundary. This enables natural parallel processing where multiple statements independently transform the same data—no variable juggling required.

Pipelines are deferred by default—they describe computation without executing it. Evaluation happens when the result is needed: field access, comparison operations, or explicit morphing to a shape. This enables powerful optimizations through pipeline modifiers and lazy evaluation of expensive operations.

These principles combine to present code that reads linearly, while still accomodating practical and real world situations. Failures propagate predictably without hidden control flow, and all operations compose through the same fundamental mechanism. The functions that process pipeline data are detailed in [Functions and Blocks](function.md), while structure operations are covered in [Structures, Spreads, and Lazy Evaluation](structure.md).

## Pipeline Fundamentals

Pipelines are enclosed in square brackets `[...]` and contain a sequence of operations connected by the pipe operator `|`. A pipeline can start with a seed value (the data being transformed) or begin directly with a function call (indicated by leading `|`).

```comp
!func |process ~{data} = {
    ; Pipeline with seed value
    validated = [data |validate]
    transformed = [data |transform]
    
    ; Pipeline without seed (unseeded)
    timestamp = [|now/time]
    
    ; Multi-step pipeline
    result = [data |validate |transform |save]
    
    ; All results combined
    {validated transformed timestamp result}
}
```

Functions always use the `|` prefix in pipeline contexts, creating a clear visual distinction between function calls and data references. The square brackets provide unambiguous boundaries, eliminating the parsing ambiguities that arise with inline pipeline syntax.

The `$in` reference provides access to pipeline data and resets at each statement boundary. This enables natural parallel processing patterns where multiple statements work on the same input data independently. Field references use undecorated tokens that cascade through output being built to input.

## Statements and Temporaries

Each statement in Comp performs one of three actions based on its target. These
actions determine how the pipeline's result is used and whether it contributes
to the output structure being built.

**Variable Assignment** uses `$var.name` followed by `=` to create
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
    $var.threshold = [$in.average |multiply 1.5]
    
    ; Use local variable in pipeline
    high-values = [$in.data |filter :{$in.value > $var.threshold}]
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
    response-type = [priority |if :{$in == urgent} 
                                   :immediate 
                                   :queued]
    
    [response-type |when :{$in == immediate} :{
        [%"Urgent: ${summary}" |alert-team]
    }]
    
    [status |match
        :{$in == 200} :{[status |handle-success]}
        :{$in >= 500} :{[status |handle-server-error |alert-ops]}
        :{$in >= 400} :{[status |handle-client-error]}
        :{#true} :{[status |log-unknown |investigate]}]
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
    processed = [records |filter :{status != archived}
                         |map :{
                             [priority |if :{$in < 0} 
                                           :{#skip} 
                                           :{[$in |validate |enhance |{$in processed=[|now/time]}]}]
                         }
                         |fold :{total=0 count=0} :{
                             {total=(total + amount) count=(count + 1)}
                         }]
    
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
    [$in.data |validate
          |execute-steps
          |? :{#io.fail} :{[$in.data |retry-with-backoff]}
          |? :{#deadlock.database.fail} :{[$in.data |wait-and-retry]}
          |? :{
              ; General failure - multiple operations for recovery
              $var.error = $in
              [%"Operation failed: ${$var.error.message}" |log]
              [$var.error |cleanup-resources |{status=#failed original=$var.error}]
          }]
}

; Complex recovery in a single block
[$in.data |risky-operation |? :{
    $var.error = $in
    [%"Operation failed: ${$var.error.message}" |log]
    [$var.error.code |match
        :{$in >= 500} :{[$var.error |wait-and-retry]}
        :{$in == 429} :{[$var.error |backoff-exponentially]}
        :{#true} :{[$var.error |use-fallback-service]}]
}]
```

## Pipeline Composition

Square brackets clearly delimit pipeline boundaries, making it obvious where transformations begin and end. Within these boundaries, functions chain naturally through the `|` operator. Adjacent pipelines at the same statement level automatically merge into a single chain.

The fresh `$in` at each statement boundary enables elegant parallel processing patterns where multiple independent operations process the same input, then combine their results. Each statement gets the same input, processes independently, and contributes to the final structure.

```comp
!func |comprehensive-analysis ~{data} = {
    ; Three independent analyses on same input
    structure-valid = [data |validate-structure]
    business-valid = [data |validate-business-rules]
    security-valid = [data |validate-security]
    
    [structure-valid && business-valid && security-valid
        |if :{$in} 
            :{[data |process]} 
            :{#validation.fail issues={structure-valid business-valid security-valid}}]
}

!func |parallel-enrichment ~{record} = {
    ; Multiple enrichments of the same record
    with-score = [record |calculate-score]
    with-category = [record |determine-category]
    with-timestamp = [record |add-processing-time]
    
    ; Merge all enrichments
    {record ..with-score ..with-category ..with-timestamp}
}
```

## Pipeline Modifiers: The Wrench Operator

The wrench operator (`|-|`) enables pipeline meta-operations that inspect, transform, and optimize pipeline structure before execution. Unlike regular pipeline operations that transform data, wrench operations modify the pipeline itself, enabling powerful capabilities like progress tracking, query optimization, and performance instrumentation.

The wrench operator requires a function reference (always prefixed with `|`), ensuring that pipeline modifiers are defined functions that can be validated at compile time. This prevents runtime errors and enables better tooling support for pipeline transformations.

Pipeline modifiers identify operations using shape-based patterns, leveraging the consistent naming conventions in standard library functions. Operations with `~iterable` inputs are recognized as iteration points, enabling automatic progress tracking or parallelization without additional metadata.

```comp
; Automatic progress tracking
[data |filter :{valid}
      |map :{expensive-transform}
      |-|progressbar]    ; Analyzes pipeline, adds progress to all iterations

; Database query optimization  
[db.users |filter :{active}
          |map :{name email}
          |-|push-to-sql]    ; Converts to optimized SQL query

; Development and profiling
[data |complex-pipeline
      |-|debug           ; Logs data at each stage
      |-|profile-time]   ; Measures operation timing
```

The wrench operator transforms Comp from a pipeline language into a meta-pipeline language where the computation structure itself becomes malleable and optimizable. Multiple modifiers can be chained, creating sophisticated transformation and optimization chains.

For comprehensive details on pipeline modifier implementation, shape-based operation detection, and the full system design, see the [Pipeline Modifier System Design](../docs/early/28-wrench.md).

## Blocks and Pipeline Context

Blocks can contain pipelines, with the square brackets providing clear boundaries for the pipeline operations. This keeps the syntax clean for common patterns like filtering and mapping.

```comp
; Block contains pipeline
items |map :{[$in |validate |enhance]}

; At statement level
$var.result = [$in.data |process |validate]

; Pipelines compose naturally
total = [$in.base |calculate] + [$in.bonus |calculate]

; Adjacent pipelines merge into single chain
result = [|fetch] [|validate] [|transform]  ; Equivalent to [|fetch |validate |transform]
```

## Pipeline Composition and Merging

Adjacent pipelines at the same statement level automatically merge into a single pipeline chain. This enables modular pipeline construction where operations can be built incrementally and composed together.

```comp
; These are equivalent
result = [|fetch |validate |transform]
result = [|fetch] [|validate] [|transform]

; Readable multi-line composition
result = [$in.data |validate]
         [|normalize]
         [|enrich]
         [|save]

; Building pipelines programmatically
$var.validators = [|check-format] [|check-rules]
$var.processors = [|transform] [|enrich]
full-pipeline = $var.validators $var.processors [|save]
```

Operators between pipelines prevent merging, creating separate pipeline evaluations:

```comp
; These are separate pipelines
combined = [x |double] + [y |triple]    ; Two pipelines, results added
condition = [a |check] && [b |validate]  ; Two pipelines, results compared
```

## Placeholder Operator

The `???` operator serves as a placeholder for not-yet-implemented code. It can
appear anywhere an expression is expected and always evaluates to
`{#not-implemented.fail}` when reached at runtime. This enables sketching code
structure with compilable placeholders. For more information about failure types
and error handling patterns, see [Tag System](tag.md).

```comp
!func |incomplete ~{data} = {
    validated = [data |validate]
    processed = ???  ; TODO: implement processing
    saved = [processed |save]
    {validated saved}
}

; Runtime behavior
??? ; Returns {#not-implemented.fail location="file.comp:42"}
```
