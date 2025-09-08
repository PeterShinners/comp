# Functions, Shapes, Blocks, and Pure Functions

*Design for Comp's function system, shape morphing, block parameters, and pure function guarantees*

## Overview

Comp's function system centers around structural parameter matching, compile-time pure functions, block-based higher-order functions, and sophisticated shape morphing. The design emphasizes static analyzability while enabling flexible runtime dispatch.

## Function Definition and Dispatch

### Basic Function Syntax

```comp
!func :function_name ~InputShape -> ~OutputShape = {
    // Single expression that transforms input
    @in -> :some_operation -> {result=@.value}
}

// Simple function without explicit types
!func :calculate = {
    @in.x * @in.y + @in.z
}

// Function with default parameters
!func :process ~{data, timeout=30, retries=3} = {
    data -> :transform {timeout=@in.timeout, retries=@in.retries}
}
```

### Function Dispatch Algorithm

Functions with the same name use **lexicographic scoring** for dispatch:

**Score Tuple**: `{named_matches, tag_matches, assignment_weight, position_matches}`

```comp
!func :render ~{x, y} = "2D rendering"           // Score: {2, 0, 0, 0}
!func :render ~{x, y} *= "priority 2D"          // Score: {2, 0, 1, 0}
!func :render ~{x, y, z} = "3D rendering"       // Score: {3, 0, 0, 0}

// Dispatch examples
{x=5, y=10} -> :render           // "priority 2D" wins: {2,0,1,0} > {2,0,0,0}
{x=5, y=10, z=15} -> :render     // "3D rendering" wins: {3,0,0,0} > others
{x=5, y=10, extra="data"} -> :render  // "priority 2D": extra fields ignored
```

### Polymorphic Dispatch with Tags

```comp
!func :process ~{item #status#pending} = "Processing pending item"
!func :process ~{item #status#active} = "Processing active item"
!func :process ~{item #priority#high} = "High priority processing"

// Most specific match wins
{item={}, status=#status#pending, priority=#priority#high} -> :process
// "Processing pending item" (status match is more specific)
```

### Function Reference Syntax

```comp
:function_name              // Local function reference
module:function_name        // Imported function reference

// Function as first-class values
$processor = :validate_data
$handler = http:handle_request

// Pipeline can start with function calls
:gfx:init -> :gfx:setup -> :gfx:shutdown
```

## Shape System

### Shape Definition Syntax

```comp
!shape ~Point2d = {
    x ~number = 0
    y ~number = 0
}

!shape ~User = {
    name ~string
    age ~number
    email ~string
    active ~bool = !true
    preferences? // Optional field
    tags #user_tag[]  // Array of user tags
}
```

### Shape Inheritance with Spreading

```comp
!shape ~Point3d = {
    ...~Point2d    // Inherit x, y fields
    z ~number = 0  // Add z coordinate
}

!shape ~ColoredPoint = {
    ...~Point2d
    color ~string = "black"
}

// Function parameter spreading
!func :analyze ~{...~RawData, complexity ~number = 0} = {
    // Has all RawData fields plus complexity parameter
    @in -> :process_with_complexity
}
```

### Shape Application Operators

```comp
data ~ Shape           // Normal morph with defaults
data *~ Shape          // Strong morph (strict, no extras allowed)
data ?~ Shape          // Weak morph (lenient, missing fields OK)
data ~@ Shape          // Include namespace lookups for defaults
```

### Shape Morphing Algorithm

**Three-Phase Field Matching Process**:

1. **Named Matches** - Exact field name matches
2. **Tag Matches** - Fields with matching tag types
3. **Positional Matches** - Remaining fields matched by position
4. **Default Application** - Unmatched optional fields get defaults

```comp
!shape ~Config = {
    host ~string = "localhost"
    port ~number = 8080
    debug ~bool = !false
}

// Morphing example
{"192.168.1.1", debug=!true, extra="ignored"} ~ Config
// Phase 1: debug=!true matches by name
// Phase 2: (no tag matches)
// Phase 3: "192.168.1.1" -> host by position
// Phase 4: port=8080 from default
// Result: {host="192.168.1.1", port=8080, debug=!true}
```

### Shape Application in Function Calls

Functions automatically apply `?~@` (weak morph with namespace) to incoming arguments:

```comp
!func :create_user ~{name ~string, age ~number, active ~bool = !true} = {
    // Automatically morphs input using ?~@
    @in -> :validate -> :save
}

// All of these work:
{name="Alice", age=30} -> :create_user                    // Uses default active=!true
{name="Bob", age=25, active=!false} -> :create_user       // Explicit active
{name="Carol", age=40, extra="data"} -> :create_user      // Extra fields ignored (weak morph)
```

## Pure Functions

### Pure Function Definition

```comp
!pure :validate_email ~{email ~string} -> ~bool = {
    // Receives completely empty @ctx - no security tokens, no permissions
    email -> :string:match /^[^@]+@[^@]+$/
}

!pure :calculate_tax ~{amount ~number, rate ~number} -> ~number = {
    amount * (rate / 100)
}
```

### Pure Function Guarantees

**Security Isolation**:
- Receive empty `@ctx` regardless of caller permissions
- Cannot access files, network, or other resources
- Enable compile-time evaluation and caching
- Safe for parallel execution without locks

**Use Cases**:
- Mathematical computations
- Data validation and parsing
- Unit conversion and formatting
- Compile-time constant evaluation

```comp
// Compile-time evaluation example
!pure :fibonacci ~{n ~number} -> ~number = {
    n <= 1 ? n | (:fibonacci {n=(n-1)} + :fibonacci {n=(n-2)})
}

// Can be evaluated at compile time for constant inputs
$fib_10 = 10 -> :fibonacci    // Computed at compile time: 55
```

### Pure vs Regular Functions

```comp
// Regular function - can access resources
!func :load_config ~{path ~string} = {
    // Has caller's permissions and context
    path -> :file:read -> :json:parse
}

// Pure function - isolated execution
!pure :parse_config ~{json_text ~string} = {
    // No permissions, no file access possible
    json_text -> :json:parse -> :validate_structure
}

// Combined usage
config_path -> :load_config -> :parse_config -> :apply_defaults
```

## Block Parameters and Higher-Order Functions

### Block-Based Function Parameters

```comp
!func :process_list ~{items, blocks={handler}} = {
    items => handler
}

// Usage with inline blocks
data -> :process_list 
    handler={item -> item.name -> :string:uppercase}
```

### Named Block Parameters

```comp
!func :http_request ~{url ~string} blocks={
    on_success = {response -> response}      // Default handler
    on_error = {error -> :log_error error}   // Default error handler
    on_timeout?                              // Optional timeout handler
} = {
    url -> :http:get 
        -> on_success
        !> on_error
        timeout> on_timeout
}

// Usage with dotted block syntax
api_url -> :http_request
    .on_success{response -> response.data -> :process}
    .on_error{error -> error -> :escalate}
    .on_timeout{-> :retry_request}
```

### Variadic Block Parameters

```comp
!func :match_cases ~{value} blocks={cases={..(input)}} = {
    // Accepts any number of blocks with same signature
    value -> :find_matching_case cases
}

// Usage
user_status -> :match_cases
    .pending{status -> :send_reminder}
    .active{status -> :log_activity}
    .expired{status -> :archive_user}
    .default{status -> :handle_unknown}
```

### Block Execution Environment

**Key Principle**: Blocks execute with caller's full permissions, not restricted permissions.

```comp
!func :url_dispatch ~{parsed_url} blocks={...routes} = {
    // Blocks run with whatever permissions caller has
    parsed_url.path -> :match_routes routes
}

// Usage - blocks have full access
url -> :url_dispatch
    ."/api/*" {request -> :database:query}     // Can access database
    ."/upload" {request -> :file:write}        // Can write files
    .else {request -> :error:not_found}        // Full error handling
```

## Advanced Function Features

### Function Argument Blocks as Pure Functions

**Current Design Decision**: All argument blocks passed to functions are treated as `!pure` functions by default.

```comp
!func :transform_data ~{data} blocks={transformer} = {
    // transformer block receives empty @ctx (pure environment)
    data => transformer    // Block cannot access files, network, etc.
}

// Usage
dataset -> :transform_data
    transformer={item -> item.value * 2}    // Pure computation only
```

**Rationale**: Start conservative - gather empirical evidence for when resource access in blocks is actually needed.

### Function Metadata and Documentation

```comp
!func :api_endpoint ~{request ~HttpRequest} -> ~HttpResponse = {
    request -> :validate -> :process -> :format_response
}

// Documentation integration
!describe :api_endpoint -> {
    params = @.shape_info
    returns = @.return_type
    description = @.docstring
}
```

### Function Composition Patterns

```comp
// Function composition through pipeline
$pipeline = :validate -> :transform -> :save
data -> $pipeline

// Conditional function application
$processor = use_advanced ? :advanced_process | :simple_process
data -> $processor

// Function with context injection
!func :process_with_context ~{data} = {
    @func.start_time = :time:now
    @func.correlation_id = :uuid:generate
    
    data -> :validate -> :transform -> :audit_log
}
```

## Shape Pattern Matching

### Pattern-Based Function Dispatch

```comp
!func :handle_response ~{status #http_status#success, data} = {
    data -> :process_success_data
}

!func :handle_response ~{status #http_status#error, message} = {
    message -> :log_error -> :send_alert
}

!func :handle_response ~{status #http_status#redirect, location} = {
    location -> :follow_redirect
}

// Automatic dispatch based on structure
response -> :handle_response    // Calls appropriate overload
```

### Guard Conditions in Shapes

```comp
!shape ~ValidUser = {
    name ~string|len>0      // Non-empty string
    age ~number|min=0|max=150  // Reasonable age range
    email ~string|matches=/^[^@]+@[^@]+$/  // Email pattern
}

!func :create_user ~ValidUser = {
    // Input guaranteed to match validation rules
    @in -> :save_to_database
}
```

## Function Scope and Lifecycle

### Function-Scoped Namespace

```comp
!func :batch_process ~{items} = {
    @func.processed_count = 0
    @func.error_count = 0
    @func.start_time = :time:now
    
    items => {
        item -> :process_item 
        -> {@ ? (@func.processed_count += 1) | (@func.error_count += 1)}
    }
    
    // Generate summary report
    {
        processed = @func.processed_count
        errors = @func.error_count
        duration = :time:now - @func.start_time
    }
}  // @func namespace automatically cleared here
```

### Function Entry and Exit Hooks

```comp
!func :database_transaction ~{operations} = {
    // Setup
    $transaction = :db:begin_transaction
    @func.transaction = $transaction
    
    // Main processing with automatic cleanup
    operations -> {
        @ -> :execute_in_transaction @func.transaction
    } -> {
        // Success: commit
        @func.transaction -> :db:commit
        @
    } !> {
        // Error: rollback
        @func.transaction -> :db:rollback
        @ // Re-raise error
    }
}
```

## Performance and Optimization

### Compile-Time Function Evaluation

```comp
// Pure functions with constant inputs evaluated at compile-time
!pure :power ~{base ~number, exponent ~number} = {
    base ** exponent
}

$constant_result = {base=2, exponent=10} -> :power  // Compile-time: 1024
$runtime_result = user_input -> :power              // Runtime evaluation
```

### Function Memoization

```comp
!pure :expensive_computation ~{input ~ComplexData} = {
    // Pure functions automatically eligible for memoization
    input -> :complex_algorithm -> :more_processing
}

// Automatic memoization based on input structure hash
$result1 = data -> :expensive_computation  // Computed
$result2 = data -> :expensive_computation  // Cached result
```

### Lazy Function Parameters

```comp
!func :conditional_process ~{data, expensive_backup=[{-> :expensive_operation}]} = {
    data -> :primary_process -> (
        @ ? @ | expensive_backup -> :evaluate  // Only evaluate if needed
    )
}

// Usage
input -> :conditional_process expensive_backup=[{-> :fallback_computation}]
```

## Integration Examples

### API Handler with Shape Validation

```comp
!shape ~UserCreateRequest = {
    name ~string|len>0
    email ~string|matches=/^[^@]+@[^@]+$/
    age ~number|min=13|max=120
    notifications ~bool = !true
}

!func :create_user_endpoint ~UserCreateRequest -> ~HttpResponse = {
    @in -> :validate_unique_email -> :create_user -> :send_welcome_email -> {
        status = 201
        body = {message="User created successfully", user=@}
        headers = {"Content-Type": "application/json"}
    }
}
```

### Data Processing Pipeline with Blocks

```comp
!func :etl_pipeline ~{source ~string, target ~string} blocks={
    extract = {source -> :load_data}
    transform = {data -> data}  // Default identity transform
    load = {data, target -> :save_data {data=data, destination=target}}
} = {
    source -> extract -> transform -> {data=@, target=@in.target} -> load
}

// Usage with custom processing blocks
"input.csv" -> :etl_pipeline "output.json"
    .extract{path -> :csv:parse}
    .transform{rows => {name=@.customer, total=@.amount * 1.1}}
    .load{data, target -> data -> :json:stringify -> :file:write target}
```

### Pattern Matching Function

```comp
!func :process_event ~{type #event_type, payload} = {
    // Dispatches based on event type tag
    {type=type, payload=payload} -> :log_event
    payload
}

!func :process_event ~{type #event_type#user_login, payload} = {
    payload -> :update_last_login -> :send_login_notification
}

!func :process_event ~{type #event_type#purchase, payload} = {
    payload -> :update_inventory -> :process_payment -> :send_receipt
}

!func :process_event ~{type #event_type#error, payload} = {
    payload -> :escalate_error -> :notify_administrators
}
```

## Implementation Priorities

1. **Basic Function Dispatch**: Shape-based parameter matching and scoring
2. **Pure Function System**: Security isolation and compile-time evaluation
3. **Shape Morphing**: Three-phase matching algorithm implementation
4. **Block Parameters**: Higher-order functions with block syntax
5. **Function Scoping**: `@func` namespace management and lifecycle
6. **Pattern Matching**: Tag-based polymorphic dispatch
7. **Performance**: Memoization and compile-time optimization

## Open Design Questions

1. **Block Purity**: Should all function argument blocks be restricted to pure execution, or should there be syntax for blocks that can access resources?

2. **Shape Constraints**: How should complex shape constraints be validated efficiently at runtime vs compile-time?

3. **Function Overloading**: What happens when shape patterns are ambiguous? Should there be explicit disambiguation syntax?

4. **Tail Call Optimization**: Should the language guarantee tail call optimization for recursive functions?

5. **Async Functions**: How should asynchronous operations integrate with the pipeline model?

6. **Function Metadata**: What introspection capabilities should be available for functions at runtime?

This design provides a comprehensive function system that balances expressiveness with safety, enables powerful abstraction patterns while maintaining static analyzability, and supports both pure computational functions and effectful operations through clear distinctions.
