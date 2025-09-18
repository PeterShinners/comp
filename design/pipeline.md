# Pipelines, Flow Control, and Failure Handling

*Design for Comp's pipeline operations, control flow patterns, and error management*

## Overview

Comp uses a single pipeline operator `->` to connect operations into data transformation chains. Control flow and error handling are achieved through functions that accept block arguments, providing a consistent and composable approach to program flow.

Every statement in Comp benefits from "statement seeding" - an implicit `.. ->` prefix that provides the context's input data. This eliminates verbose data threading while maintaining explicit control when needed.

## Pipeline Fundamentals and Statement Seeding

The `->` operator is Comp's fundamental composition mechanism, passing data from one operation to the next in readable left-to-right flows. A pipeline consists of one or more operations connected by `->`. Each operation can be a function reference, structure constructor, literal value, string template, or special operator like `!label`. The pipeline naturally composes these different operation types into complex transformations.

Statement seeding revolutionizes how data flows through functions. Every statement in a function or block automatically begins with the input data through an implicit `.. ->` prefix. This seed value flows into the statement's pipeline unless explicitly overridden. The seed resets at each statement boundary, so each statement starts fresh with the context input rather than the previous statement's result. Within a pipeline, `..` refers to the previous operation's output, creating a clear distinction between the statement seed and pipeline flow.

```comp
!func :process ~{data} = {
    validated = :validate       ; Implicit: .. -> :validate
    transformed = :transform    ; Implicit: .. -> :transform
    combined = {validated transformed}
    
    ; Explicit pipeline overrides the seed
    other_data -> :different_process -> :save
}
```

This design enables natural parallel processing patterns where multiple statements work on the same input data independently, then combine their results. The implicit seeding eliminates the verbose threading common in functional languages while maintaining explicitness when needed.

## Statements and Temporaries

Each statement in Comp performs one of three actions based on its target. These actions determine how the pipeline's result is used and whether it contributes to the output structure being built.

**Temporary Assignment** starts with a `$` prefixed token followed by `=`. This creates a function-local temporary that can be referenced later in the function but doesn't contribute to the output structure. These temporaries exist only within the function's scope and are immutable once assigned. Nested field assignment creates a new temporary structure with the specified modification.

**Named Assignment** starts with a field name and `=`, assigning the pipeline result to a named field in the output structure. Conflicting field names override previous values, though this behavior can be modified with weak (`?=`) or strong (`*=`) assignment operators.

**Unnamed Assignment** has no assignment target, adding the pipeline result as an unnamed field to the output structure. These unnamed fields maintain their order and can be accessed by position.

```comp
!func :analyze ~{data} = {
    ; Temporary - available in function, not in output
    $threshold = data.average * 1.5
    
    ; Named field - part of output structure
    high_values = data -> :filter .{value > $threshold}
    
    ; Unnamed field - added to output positionally
    data -> :calculate_median
    
    ; Nested temporary assignment
    $config = {timeout=30 retries=3}
    $config.timeout = 60  ; Creates new structure, doesn't modify original
}
```

Function-local temporaries prefixed with `$` provide a crucial namespace separate from the field lookups. They must always be explicitly referenced with their prefix and can only be used after definition. This separation prevents naming conflicts and makes data flow explicit.

## Control Flow Through Functions

Control flow in Comp abandons special operators in favor of functions with block arguments. This unification means all control flow follows the same patterns as data transformation - it's just functions all the way down.

The core conditional functions - `:if`, `:when`, and `:match` - cover the spectrum from simple branches to complex pattern matching. The `:if` function provides classic if-then-else semantics with two branches. The `:when` function handles single conditions without an else clause, perfect for optional actions. The `:match` function enables pattern matching with multiple conditions tested in order. All three accept blocks that capture the current scope and execute conditionally based on their test conditions.

```comp
!func :process_request ~{request} = {
    ; Multiple conditional patterns in action
    response_type = :if .{request.priority == "urgent"} 
        .{"immediate"} 
        .{"queued"}
    
    :when .{response_type == "immediate"} .{
        "Urgent: ${request.summary}" -> :alert_team
    }
    
    request.status -> :match
        .{.. == 200} .{:handle_success}
        .{.. >= 500} .{:handle_server_error -> :alert_ops}
        .{.. >= 400} .{:handle_client_error}
        .{#true} .{:log_unknown -> :investigate}
}
```

Iteration follows the same function-with-blocks pattern. The `:map` function transforms each element and collects results, while `:each` performs side effects without collection. The `:filter` function selects matching elements, and `:fold` reduces collections to single values using an accumulator. These functions recognize special control tags - `#skip` continues to the next element without including the current result, `#break` stops iteration immediately, and any failure stops iteration and propagates the error.

```comp
!func :analyze_records ~{records} = {
    ; Complete iteration pipeline
    processed = records 
        -> :filter .{status != "archived"}
        -> :map .{
            :if .{priority < 0} .{#skip} .{
                :validate -> :enhance -> {.. processed=:time/now}
            }
        }
        -> :fold {total=0 count=0} .{
            {total=(total + amount) count=(count + 1)}
        }
    
    {records=processed.count average=processed.total/processed.count}
}
```

## Failure Management System

Failures in Comp are structures containing a `#fail` tag, providing a unified error model that integrates naturally with the pipeline system. Rather than exceptions that break control flow or error codes that require manual checking, failures flow through pipelines with predictable propagation rules.

The language defines a hierarchical `#fail` tag system that categorizes errors by type and origin. This hierarchy enables both specific and general error handling - you can handle `#fail#io#timeout` specifically or work with all `#fail#io` errors together. Functions generate failures for runtime errors like missing fields, failed type conversions, or permission violations. User code creates failures by simply including the appropriate `#fail` tag in a structure, often with additional context fields.

Modules can extend the failure hierarchy to define domain-specific error categories. These extensions work like any tag extension - they create new leaf nodes in the hierarchy while maintaining compatibility with parent handlers. The extended tags should include descriptive values and follow consistent naming patterns.

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
!tag #fail += {
    #database = "Database operation failed" {
        #connection = "Unable to connect"
        #constraint = "Constraint violation"  
        #deadlock = "Transaction deadlock detected"
    }
    #auth = "Authentication failed" {
        #expired = "Credentials expired"
        #invalid = "Invalid credentials"
    }
}

; Usage
{#fail#database#connection message="Connection pool exhausted" pool_id=5}
```

Failure messages should follow consistent formatting guidelines to provide clear, actionable information. The initial string field should contain a one-sentence description of what failed. Messages should identify specific values causing problems rather than generic statements. Use "Index ${index} must be positive" instead of "Invalid index". Additional fields should suggest remediation when possible, using descriptive field names that display clearly in error reports.

## Failure Recovery Patterns

Comp provides multiple mechanisms for handling failures, from simple fallbacks to complex recovery procedures. The choice of mechanism depends on the complexity of the recovery needed and whether you want to replace the failure or just perform cleanup.

The `|` fallback operator provides immediate recovery for single operations. It receives the original input (not the failure) and provides an alternative value. Multiple fallbacks can be chained, creating a cascade of alternatives tried in order. This operator shines for providing defaults when optional fields are missing or operations might fail.

```comp
; Cascading fallbacks for configuration
port = config.port | env.PORT | 8080
display_name = user.nickname | user.username | user.email | "Anonymous"

; Fallback with computation
timeout = settings.timeout | (settings.retry_count * 1000) | 5000
```

The `!>` operator handles failures with more complex recovery logic. Since it only accepts a single operation, multi-step recovery requires a block. The operator can be configured with tag filters to handle specific failure types, with multiple `!>` operators creating a chain of handlers tested in order.

```comp
!func :process_transaction ~{data} = {
    data -> :validate
         -> :execute_steps
         !> (#fail#io) {:retry_with_backoff}
         !> (#fail#database#deadlock) {:wait_and_retry}
         !> {
             ; General failure - need block for multiple operations
             :log_error
             -> :cleanup_resources
             -> {status="failed" original=..}
         }
}

; Complex recovery in a single block
risky_operation !> {
    $error = ..
    "Operation failed: ${error.message}" % .. -> :log
    $error.code -> :match
        .{.. >= 500} .{:wait_and_retry}
        .{.. == 429} .{:backoff_exponentially}
        .{#true} .{:use_fallback_service}
}
```

When using tag filters, parentheses group multiple tags with `|` for alternatives. The filter matches any failure in the specified hierarchies. Without a filter, the handler matches any failure based on the current module's `#fail` definition.

## Pipeline Composition and Labels

Complex pipelines often need to reference intermediate values or compose multiple transformation chains. The `!label` operator captures values at any point in a pipeline, making them available for later reference. This eliminates the need for breaking pipelines into separate statements just to capture intermediate results.

Statement seeding enables elegant parallel processing patterns where multiple independent operations process the same input, then combine their results. Each statement gets the same seed, processes independently, and contributes to the final structure. This pattern is particularly powerful for analysis or validation operations that need multiple perspectives on the same data.

```comp
!func :comprehensive_analysis ~{data} = {
    ; Capture original for comparison
    data -> :normalize 
         -> !label $normalized
         -> :validate
         -> !label $validated
         -> :enhance
         -> {
             original = $normalized
             validated = $validated  
             enhanced = ..
             delta = :calculate_changes $normalized ..
         }
}

!func :parallel_validation ~{input} = {
    ; Three independent validations on same input
    structure_valid = :validate_structure
    business_valid = :validate_business_rules  
    security_valid = :validate_security
    
    :if .{structure_valid && business_valid && security_valid}
        .{input -> :process}
        .{{#fail#validation issues={structure_valid business_valid security_valid}}}
}
```

## Design Principles

The pipeline and failure system embodies several core principles that guide its design and usage. The single pipeline operator creates consistency - there's no special syntax to learn for different scenarios. Automatic failure propagation eliminates defensive programming while ensuring errors can't be silently ignored. Explicit recovery makes error handling visible in the code structure. Statement seeding provides implicit data flow while maintaining explicit control. The uniform function-and-block pattern means control flow follows the same rules as data transformation.

These principles combine to create a system where complex data transformations, control flow, and error handling integrate naturally. The result is code that reads linearly while handling the full complexity of real-world data processing. Failures propagate predictably without hidden control flow, temporaries provide clear scoping without namespace pollution, and all operations compose through the same fundamental pipeline mechanism.