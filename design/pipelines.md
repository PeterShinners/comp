# Pipelines, Flow Control and Failures

*Design for Comp's error handling, control flow operators, pipeline composition, and failure propagation*

## Overview

Comp's approach to failures and flow control emphasizes explicit data flow through pipelines, automatic failure propagation, and composable error handling patterns. The system treats failures as structured data that flows through pipelines with special handling semantics.

## Pipeline Architecture

### Core Pipeline Operators

```comp
->      // Invoke operator (function calls, structure construction)
=>      // Iteration pipeline (collection processing)  
..>     // Spread arrow (merge fields while maintaining flow)
!>      // Failure handling pipeline  
|       // Field fallback (not value-based conditionals)
```

### Invoke Pipeline (`->`)

Transforms structures through function calls or structure construction:

```comp
// Function invocation
data -> :validate -> :transform -> :save

// Structure construction
user -> {name=@.name, processed_at=:time:now}

// Module function calls
response -> http:parse -> json:extract -> db:save

// Pipeline starting with function call
:config:load -> :validate -> :apply_settings
```

### Iteration Pipeline (`=>`)

Processes collections by applying expressions to each element:

```comp
users => {name=@.name, active=@.status=="active"}
numbers => @ * 2  
files => :file:process

// With control flow
items => {
    @ -> :validate -> (
        @ ? @ | #skip    // Skip invalid items
    )
}

// Nested iteration
groups => users => {user=@, group=@outer}
```

### Spread Arrow Pipeline (`..>`)

Merges additional fields while preserving pipeline flow:

```comp
// Add parameters without nesting
data ..> {timeout=30, retries=3} -> :network:request

// Equivalent to:
data -> {...@, timeout=30, retries=3} -> :network:request

// Works with function results
user ..> :load_preferences -> :render_profile

// Works with namespaces
request ..> @app.defaults -> :process_request
```

## Failure Propagation System

### Automatic Failure Propagation

When any pipeline operation encounters a failure structure, all subsequent operations are automatically skipped:

```comp
// If :step1 fails, :step2 and :step3 are skipped
data -> :step1 -> :step2 -> :step3

// Failure propagates through iteration
users => :validate -> :save  // Invalid users skipped automatically

// Spread operations also propagate failures
data ..> :load_config -> :process  // Config loading failure stops pipeline
```
### Failure Structures

Shape application failures return structured information:

```comp
{
    #failure
    #shape_application_failed
    message = "Type validation failed"
    partial = {x="hello", y=20}         // Partial results
    mapping = {field pairing details}
    errors = {specific error list}
}
```

### Failure Structure Format

Failures are structured data with specific tags:

```comp
{
    #failure
    #error_type                    // Specific error classification
    message = "Description of what went wrong"
    context = {original_input}     // Context when error occurred
    stack_trace = [...]           // Execution context
    recoverable = !true           // Whether recovery is possible
}
```

### Failure Types Hierarchy

```comp
!tag #failure = {
    validation = {
        type_mismatch = !nil
        missing_field = !nil
        constraint_violation = !nil
        shape_application_failed = !nil
    }
    runtime = {
        resource_unavailable = !nil
        permission_denied = !nil
        timeout = !nil
        network_error = {retryable=!true}
        io_error = !nil
    }
    system = {
        memory_exhausted = !nil
        stack_overflow = !nil
        internal_error = !nil
    }
    user = {
        invalid_input = !nil
        unauthorized = !nil
        not_found = !nil
    }
}
```

## Flow Control Operators


### Valve Operators

The valve operators (`-?`, `-&`, `-|`) conditionally direct data through 
transformations in a pipeline. Like mechanical valves, they control whether data
flows through a processing branch or bypasses it.

- **`-?`** Tests a condition (check valve)
- **`-&`** Executes when condition is true (open channel)
- **`-|`** Executes when condition is false (bypass channel, optional)

Groups of these valve operators can appear together as a special pairing of
operations. 

The grouping must begin with the `-?` operator to start with a conditional
statement. The `-?` conditional operator can appear after each `-&` operation to
provide a followup conditional check, similar to an "else if" in other
languages.

The `-&` then operator must appear once, immediately following each `-?`
condition.

The final `-|` else operator is optional and can only be used at the end of the
grouping. 

In the grouping of operators, only a single `-&` or `-|` operator will be
invoked. If the optional `-|` condition is not provided, then perhaps none 
of the blocks will be invoked.

Every block in the grouping of valve conditionals is invoked with the
same value passed into the start of the grouping. The final result of these
grouped operators will be the result of whichever branch was selected.

When multiple `-?` condition blocks are used, they will be executed up until the
point where a single condition true. The values generated by these condition
blocks only influcence the conditional logic, they are not propogated beyond
their execution.

When any of the blocks contain more than one statement, the parser requires
them be wrapped in `{}` braces so that it becomes a single statement.

#### Basic Example

```comp
// Apply discount if user is premium member
order
  -? user.premium?
  -& :apply-premium-discount
  -> :calculate-total

// With explicit else branch
customer -? age >= 18 -& $adult-price -| $child-price -> :checkout
```

#### Else-If Chains

Multiple conditions can be chained by placing `-?` after previous conditions:

```comp
// Route request based on status code
response
  -? :status == 401
  -& :redirect-to-login
  -? :status == 403  
  -& :show-forbidden-page
  -? :status >= 500
  -& {:log-server-error -> :show-error-page}
  -| :render-content  // Final else
  -> :send-to-client
```

### Field Fallback (`|`)

Provides fallback values for **undefined fields only** (not falsy values):

```comp
// Field doesn't exist
user.nickname | "Anonymous"         // Uses "Anonymous"
config.timeout | 30                 // Uses 30

// Field exists but is falsy - fallback NOT used
user.enabled | !true               // If enabled=!false, returns !false
user.score | 100                   // If score=0, returns 0

// Common patterns
settings.url | "http://localhost"   // Default URL
user.preferences | {}               // Empty preferences object
```

### Failure Handling Pipeline (`!>`)

Catches and handles failure conditions:

```comp
// Basic error handling
data -> :risky_operation !> "Operation failed"

// Preserve original data on failure
input -> :validate !> {@, error="Validation failed"}

// Chain error handlers
data -> :step1 !> :fallback1 -> :step2 !> :fallback2

// Error transformation
user -> :load_profile !> {
    error = "Profile not found"
    user_id = @.id
    suggested_action = "create_profile"
}
```

### Hierarchical Error Handling

```comp
// Handle specific error types
data -> :process 
    !> {error.#validation -> :handle_validation_error}
    !> {error.#network -> :handle_network_error}
    !> {error -> :handle_generic_error}  // Catch-all

// Pattern matching in error handling
response -> :http:request !> {
    @.status_code -> match {
        404 -> {error="Not found", action="check_url"}
        500 -> {error="Server error", action="retry_later"}  
        timeout -> {error="Timeout", action="retry_immediately"}
        else -> {error="Unknown error", code=@.status_code}
    }
}
```

## Advanced Pipeline Patterns

### Pipeline Labels and Reuse

```comp
// Function-scoped labels
path -> :fs:open -> !label $fd -> :process_file
$fd -> :fs:close  // Reuse labeled value

// Statement-scoped labels  
data -> :expensive_transform -> !label ^processed
^processed -> :validate
^processed -> :cache  
^processed -> :log
```

### Pipeline Composition

```comp
// Compose reusable pipeline segments  
$validation_pipeline = :check_format -> :check_constraints -> :check_business_rules
$processing_pipeline = :normalize -> :enrich -> :transform
$storage_pipeline = :serialize -> :compress -> :store

// Use composed pipelines
user_data -> $validation_pipeline -> $processing_pipeline -> $storage_pipeline
```

### Dynamic Pipeline Construction

```comp
// Build pipeline based on data characteristics
!func :create_pipeline ~{data_type ~str} = {
    data_type -> :match {
        "csv" -> (:csv:parse -> :validate -> :normalize)
        "json" -> (:json:parse -> :validate -> :transform)
        "xml" -> (:xml:parse -> :convert_to_json -> :validate)
        else -> (:binary:decode -> :detect_format -> :process)
    }
}

// Apply dynamic pipeline
input_file -> {
    type = extension -> :detect_file_type
    pipeline = type -> :create_pipeline
    data = !in -> pipeline
}
```

## Complex Flow Control Patterns

### Match-Style Dispatch

```comp
// Pattern matching with multiple conditions
user_request -> match {
    {method="GET", path="/api/*"} -> :handle_api_get
    {method="POST", authenticated=!true} -> :handle_authenticated_post
    {method="POST", authenticated=!false} -> :require_authentication
    {method="PUT", role="admin"} -> :handle_admin_put
    {status=#error} -> :handle_error_request
    else -> :handle_default
}
```

### Loop-Style Iteration with Control

```comp
// Collection processing with early termination
items => {
    @ -> :process -> {
        @.should_continue ? @ | #break    // Break on condition
    }
}

// Collection processing with skip
users => {
    @.active ? (@ -> :process_user) | #skip
}

// Nested iteration with control
groups => {
    group -> {
        items => {
            item -> :validate -> {
                @ ? (@ -> :process_item) | #skip
            }
        }
    }
}
```

### State Machine Patterns

```comp
// State transitions through pipeline
!func :process_order ~{order, state=#order_state#pending} = {
    {order=order, state=state} -> match {
        {state=#order_state#pending} -> :validate_order -> {
            @ ? {@.order, state=#order_state#validated} | #failure
        }
        {state=#order_state#validated} -> :process_payment -> {
            @ ? {@.order, state=#order_state#paid} | #failure  
        }
        {state=#order_state#paid} -> :fulfill_order -> {
            @ ? {@.order, state=#order_state#shipped} | #failure
        }
        {state=#order_state#shipped} -> :track_delivery -> {
            @ ? {@.order, state=#order_state#delivered} | #failure
        }
        else -> #failure
    }
}
```

## Error Recovery Patterns

### Retry Logic

```comp
// Simple retry with exponential backoff
!func :retry_operation ~{operation, max_attempts=3} = {
    attempt = 1
    {operation=operation, attempt=attempt, max_attempts=max_attempts} -> {
        @.operation -> :execute !> {
            @outer.attempt < @outer.max_attempts ? {
                delay = 2 ** @outer.attempt  // Exponential backoff
                delay -> :time:sleep
                @outer -> {...@outer, attempt=@outer.attempt+1} -> :retry_operation
            } | {
                error = "Max retry attempts exceeded"
                last_error = @
                #failure
            }
        }
    }
}
```

### Graceful Degradation

```comp
// Fallback chain with degraded functionality
user_data -> :load_full_profile 
    !> :load_basic_profile      // Fallback to basic
    !> :load_cached_profile     // Fallback to cache
    !> :create_default_profile  // Final fallback
```

### Circuit Breaker Pattern

```comp
!func :circuit_breaker ~{operation, threshold=5, timeout=60} = {
    @mod.circuit_state | "closed" -> match {
        "closed" -> {
            @mod.failure_count | 0 < threshold ? 
                operation -> :execute !> :handle_circuit_failure |
                :open_circuit
        }
        "open" -> {
            (@mod.last_failure_time + timeout) < :time:now ?
                :attempt_half_open |
                {error="Circuit breaker open", #failure}
        }
        "half_open" -> {
            operation -> :execute -> :close_circuit !> :open_circuit
        }
    }
}
```

## Integration with Other Systems

### Pipeline-Based API Handlers

```comp
!func :api_endpoint ~{request} = {
    request
    -> :parse_request
    -> :authenticate  !> {status=401, error="Unauthorized"}
    -> :validate      !> {status=400, error="Invalid input"}  
    -> :authorize     !> {status=403, error="Forbidden"}
    -> :process       !> {status=500, error="Processing failed"}
    -> :format_response
    -> {status=200, data=@}
}
```

### Stream Processing Pipeline

```comp
// Process data streams with error handling
event_stream 
    => :deserialize     !> :log_deserialization_error
    => :enrich_event    !> :handle_enrichment_failure
    => :validate_schema !> :quarantine_invalid_event
    => :route_event     !> :send_to_dead_letter_queue
```

### Database Transaction Pipeline

```comp
!func :user_registration ~{user_data} = {
    !transaction using $db_connection {
        user_data
        -> :validate_user_data    !> :rollback_with_error
        -> :check_email_unique    !> :rollback_with_error
        -> :hash_password
        -> :create_user_record    !> :rollback_with_error  
        -> :send_welcome_email    !> :log_email_failure  // Don't fail transaction
        -> :audit_user_creation   !> :log_audit_failure  // Don't fail transaction
    }
}
```

## Performance and Optimization

### Short-Circuit Evaluation

```comp
// Expensive operations only run if needed
expensive_check = [compute_expensive_condition]
cheap_check = compute_cheap_condition

// Short-circuit: expensive_check only evaluated if cheap_check passes
cheap_check && expensive_check ?| :proceed | :skip
```

### Lazy Pipeline Construction

```comp
// Pipeline steps computed lazily
processing_pipeline = [
    input_type -> :determine_parser -> :determine_validator -> :determine_processor
]

// Only construct pipeline when needed
data -> processing_pipeline -> :evaluate -> data
```

### Parallel Pipeline Execution

```comp
// Fork pipeline into parallel branches
user_data -> {
    profile = [@ -> :load_profile]           // Parallel branch 1
    permissions = [@ -> :load_permissions]   // Parallel branch 2  
    settings = [@ -> :load_settings]         // Parallel branch 3
} -> {
    // Wait for all branches to complete
    user = {
        ...@.profile -> :await
        permissions = @.permissions -> :await
        settings = @.settings -> :await
    }
}
```

## Implementation Priorities

1. **Basic Pipeline Operators**: `->`, `=>`, `..>` with failure propagation
2. **Conditional Flow**: `?|` operator with proper branching
3. **Error Handling**: `!>` operator with structured failure data
4. **Field Fallback**: `|` operator for undefined field handling
5. **Pipeline Labels**: Function and statement-scoped value reuse
6. **Complex Patterns**: Match expressions, retry logic, circuit breakers
7. **Performance**: Short-circuit evaluation, lazy construction, parallelization

## Open Design Questions

1. **Exception Semantics**: Should there be a way to "throw" exceptions that skip multiple pipeline levels, or should all error handling be explicit through `!>` operators?

2. **Async Pipeline Integration**: How should asynchronous operations integrate with the pipeline model? Should there be special async pipeline operators?

3. **Pipeline Debugging**: What introspection and debugging capabilities should be available for complex pipeline chains?

4. **Resource Cleanup**: How should pipelines handle resource cleanup when failures occur partway through processing?

5. **Pipeline Composition**: Should there be syntax for creating reusable pipeline templates or macros?

6. **Partial Failure Handling**: How should pipelines handle cases where some items in a collection succeed and others fail?

This design provides a comprehensive system for handling failures and controlling program flow through explicit pipeline operations, emphasizing predictable data flow and composable error handling patterns while maintaining the language's focus on immutable data transformation.
