# Pipelines, Flow Control, and Failure Handling

*Design for Comp's pipeline operations, control flow patterns, and error
management*

## Overview

Comp uses pipelines to connect operations into data # Module extension
!tag #fail += {
    #database = Database operation failed {
        #connection = Unable to connect
        #constraint = Constraint violationformation chains. The
`|` operator marks function application, creating readable left-to-right data
flow. Control flow and error handling are achieved through functions that accept
block arguments (dotted structures `.{}`), providing a consistent and composable
approach to program flow.

Every statement in Comp benefits from fresh pipeline input - `$in` resets to the
function's original input at each statement boundary. This enables parallel
processing patterns where multiple statements independently transform the same
input data. The functions that process pipeline data are detailed in [Functions
and Blocks](function.md), while the structure operations within pipelines are
covered in [Structures, Spreads, and Lazy Evaluation](structure.md).

The pipeline and failure system embodies several core principles that guide its
design and usage. The single pipeline pattern with `|` creates consistency -
there's no special syntax for different scenarios. Automatic failure propagation
eliminates defensive programming while ensuring errors can't be silently
ignored. Explicit recovery makes error handling visible in the code structure.
Fresh `$in` at statement boundaries provides clean parallel processing. The
uniform function-and-block pattern means control flow follows the same rules as
data transformation.

These principles combine to create a system where complex data transformations,
control flow, and error handling integrate naturally. The result is code that
reads linearly while handling the full complexity of real-world data processing.
Failures propagate predictably without hidden control flow, variables provide
clear scoping without namespace pollution, and all operations compose through
the same fundamental pipeline mechanism.

## Pipeline Fundamentals

The `|` operator is Comp's fundamental composition mechanism, marking function
application within pipeline boundaries. Pipelines are enclosed in parentheses to
clearly delimit their scope. Each function in a pipeline receives the output of
the previous function as its input, creating natural data flow.

A pipeline consists of one or more functions connected by `|`. The first element
can be either a value or a function. When starting with a value, it becomes the
input to the first function. When starting with a function (marked by leading
`|`), the function receives no initial input or uses ambient data depending on
its definition.

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
override previous values, though this behavior can be modified with weak (`?=`)
or strong (`*=`) assignment operators.

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
