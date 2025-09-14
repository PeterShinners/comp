# Pipelines, Flow Control and Failures

*Design for Comp's error handling, control flow operators, pipeline composition, and failure propagation*

## Overview

Comp's approach to failures and flow control emphasizes explicit data flow through pipelines, automatic failure propagation, and composable error handling patterns. The system treats failures as structured data that flows through pipelines with special handling semantics.

## Pipeline Architecture

### Core Pipeline Operators

```comp
->      ; Invoke operator (function calls, structure construction)
=>      ; Iteration pipeline (collection processing)  
..>     ; Spread arrow (merge fields while maintaining flow)
!>      ; Failure handling pipeline  
|       ; Field fallback (not value-based conditionals)
```

### Invoke Pipeline (`->`)

Transforms structures through function calls or structure construction:

```comp
; Function invocation
data -> :validate -> :transform -> :save

; Structure construction
user -> {name=@.name, processed_at=:time:now}

; Module function calls
response -> http:parse -> json:extract -> db:save

; Pipeline starting with function call
:config:load -> :validate -> :apply_settings
```

### Iteration Pipeline (`=>`)

Processes collections by applying expressions to each element:

```comp
users => {name=@.name, active=@.status=="active"}
numbers => @ * 2  
files => :file:process

; With control flow
items => {
    @ -> :validate -> (
        @ ? @ | #skip    ; Skip invalid items
    )
}

; Nested iteration
groups => users => {user=@, group=@outer}
```

### Spread Arrow Pipeline (`..>`)

Merges additional fields while preserving pipeline flow:

```comp
; Add parameters without nesting
data ..> {timeout=30, retries=3} -> :network:request

; Equivalent to:
data -> {...@, timeout=30, retries=3} -> :network:request

; Works with function results
user ..> :load_preferences -> :render_profile

; Works with namespaces
request ..> @app.defaults -> :process_request
```

## Failure Propagation System

### Automatic Failure Propagation

When any pipeline operation encounters a failure structure, all subsequent operations are automatically skipped:

```comp
; If :step1 fails, :step2 and :step3 are skipped
data -> :step1 -> :step2 -> :step3

; Failure propagates through iteration
users => :validate -> :save  ; Invalid users skipped automatically

; Spread operations also propagate failures
data ..> :load_config -> :process  ; Config loading failure stops pipeline
```
### Failure Structures

Shape application failures return structured information:

```comp
{
    #failure
    #shape_application_failed
    message = "Type validation failed"
    partial = {x="hello", y=20}         ; Partial results
    mapping = {field pairing details}
    errors = {specific error list}
}
```

### Failure Structure Format

Failures are structured data with specific tags:

```comp
{
    #failure
    #error_type                    ; Specific error classification
    message = "Description of what went wrong"
    context = {original_input}     ; Context when error occurred
    stack_trace = [...]           ; Execution context
    recoverable = !true           ; Whether recovery is possible
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

The valve operator family uses **double characters** for visual consistency and clear control flow:

- **`-??`** Begin conditional (if)
- **`-&&`** Then action separator (and then) 
- **`-|?`** Else-if continuation (or if)
- **`-||`** Else fallback (or else)

#### How Valve Groups Work

A valve group is a sequence of conditional checks that work together as a single unit in the pipeline. The group receives an input value, evaluates conditions against it, and outputs the result of whichever branch executes.

**Input Flow**: The value entering the valve group (from the left side of `-??`) is available to all conditions within that group. Each condition can access and test this input value.

**Condition Evaluation**: Conditions are evaluated in order, top to bottom. The first condition that evaluates to true has its corresponding action executed. Once a condition matches, no further conditions in that valve group are checked.

**Output Flow**: The valve group outputs whatever value its executed action produces. This output then flows to the next operation in the pipeline. If no condition matches and there's no `-||` else clause, the valve group passes through the original input value unchanged.

#### Syntax Pattern

```comp
input_value -> 
    -?? condition -&& :action_if_true
    -|? another_condition -&& :action_if_this_true  
    -|| :action_if_all_false
-> receives_action_output
```

#### Data Flow Examples

**Simple conditional with value transformation:**
```comp
{score=85} -> -?? score > 90 -&& "A" -|| "B"  ; Outputs: "B"
```
The input struct flows in, the condition checks `score > 90` (false), so the else branch executes, outputting "B" to the pipeline.

**Chained conditions with different outputs:**
```comp
{age=25} ->
    -?? age < 18 -&& :restrict_access    ; Returns restricted view
    -|? age < 21 -&& :limit_features     ; Returns limited view  
    -|| :full_access                     ; Returns full view
-> :render_page
```
The age=25 input means both conditions fail, so `:full_access` executes. Whatever `:full_access` returns becomes the input to `:render_page`.

**Multiple independent valve groups:**
```comp
data 
-> :validate -?? is_valid -&& :log_success -|| :log_error  ; First group
-> :transform -?? needs_cache -&& :add_cache_headers       ; Second group
-> :send_response
```
Each valve group is independent. The first group's output (from either `:log_success` or `:log_error`) becomes the input to the second valve group. The second group tests this new input with its own condition.

#### Important Behaviors

**Pass-through on no match**: If no conditions match and no `-||` is provided, the original input passes through unchanged:
```comp
{value=10} -> -?? value > 100 -&& :process  ; No match, no else
-> :next_step  ; Receives {value=10} unchanged
```

**Early termination**: Once a condition matches, the valve group immediately executes that action and exits. Subsequent conditions are not evaluated:
```comp
{status="pending"} ->
    -?? status == "pending" -&& :queue_job     ; This matches and executes
    -|? status == "pending" -&& :different     ; Never evaluated
    -|| :default                               ; Never evaluated
```

**Condition access to input**: All conditions in a valve group can reference the input value:
```comp
user ->
    -?? user.age >= 18 and user.verified -&& :full_access
    -|? user.parent_consent -&& :limited_access
    -|| :deny
```

#### Key Benefits

1. **No ambiguity**: Each valve group is self-contained with clear boundaries
2. **No terminators needed**: The operators themselves define the structure  
3. **Consistent visual language**: Double-character operators form a clear family
4. **Readable flow**: `-??` asks a question, `-&&` provides the answer, `-|?` asks another, `-||` catches the rest
5. **Pipeline friendly**: Multiple valve groups can exist in sequence without interference
6. **Predictable data flow**: Input flows in, one action executes, output flows out

#### Complex Valve Examples

**Route request based on status code:**
```comp
response ->
    -?? :status == 401 -&& :redirect_to_login
    -|? :status == 403 -&& :show_forbidden_page
    -|? :status >= 500 -&& {:log_server_error -> :show_error_page}
    -|| :render_content  ; Final else
-> :send_to_client
```

**Apply discount based on customer tier:**
```comp
order ->
    -?? customer.tier == "premium" -&& :apply_premium_discount
    -|? customer.tier == "gold" -&& :apply_gold_discount
    -|? order.total > 100 -&& :apply_bulk_discount
    -|| order  ; No discount applied
-> :calculate_total
```

### Field Fallback (`|`)

Provides fallback values for **undefined fields only** (not falsy values):

```comp
; Field doesn't exist
user.nickname | "Anonymous"         ; Uses "Anonymous"
config.timeout | 30                 ; Uses 30

; Field exists but is falsy - fallback NOT used
user.enabled | !true               ; If enabled=!false, returns !false
user.score | 100                   ; If score=0, returns 0

; Common patterns
settings.url | "http:;localhost"   ; Default URL
user.preferences | {}               ; Empty preferences object
```

### Failure Handling Pipeline (`!>`)

Catches and handles failure conditions:

```comp
; Basic error handling
data -> :risky_operation !> "Operation failed"

; Preserve original data on failure
input -> :validate !> {@, error="Validation failed"}

; Chain error handlers
data -> :step1 !> :fallback1 -> :step2 !> :fallback2

; Error transformation
user -> :load_profile !> {
    error = "Profile not found"
    user_id = @.id
    suggested_action = "create_profile"
}
```

### Hierarchical Error Handling

```comp
; Handle specific error types
data -> :process 
    !> {error.#validation -> :handle_validation_error}
    !> {error.#network -> :handle_network_error}
    !> {error -> :handle_generic_error}  ; Catch-all

; Pattern matching in error handling
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
; Function-scoped labels
path -> :fs:open -> !label $fd -> :process_file
$fd -> :fs:close  ; Reuse labeled value

; Statement-scoped labels  
data -> :expensive_transform -> !label ^processed
^processed -> :validate
^processed -> :cache  
^processed -> :log
```

### Pipeline Composition

```comp
; Compose reusable pipeline segments  
$validation_pipeline = :check_format -> :check_constraints -> :check_business_rules
$processing_pipeline = :normalize -> :enrich -> :transform
$storage_pipeline = :serialize -> :compress -> :store

; Use composed pipelines
user_data -> $validation_pipeline -> $processing_pipeline -> $storage_pipeline
```

### Dynamic Pipeline Construction

```comp
; Build pipeline based on data characteristics
!func :create_pipeline ~{data_type ~str} = {
    data_type -> :match {
        "csv" -> (:csv:parse -> :validate -> :normalize)
        "json" -> (:json:parse -> :validate -> :transform)
        "xml" -> (:xml:parse -> :convert_to_json -> :validate)
        else -> (:binary:decode -> :detect_format -> :process)
    }
}

; Apply dynamic pipeline
input_file -> {
    type = extension -> :detect_file_type
    pipeline = type -> :create_pipeline
    data = !in -> pipeline
}
```

## Complex Flow Control Patterns

### Match-Style Dispatch

```comp
; Pattern matching with multiple conditions
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
; Collection processing with early termination
items => {
    @ -> :process -> {
        @.should_continue ? @ | #break    ; Break on condition
    }
}

; Collection processing with skip
users => {
    @.active ? (@ -> :process_user) | #skip
}

; Nested iteration with control
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
; State transitions through pipeline
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


### Lazy Pipeline Construction

```comp
; Pipeline steps computed lazily
processing_pipeline = [
    input_type -> :determine_parser -> :determine_validator -> :determine_processor
]

; Only construct pipeline when needed
data -> processing_pipeline -> :evaluate -> data
```

