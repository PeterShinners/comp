# Functions

*Design for Comp's function system, dispatch algorithms, and execution model*

## Overview

Comp's function system centers around structural parameter matching with sophisticated dispatch algorithms. Functions use lexicographic scoring for polymorphic dispatch, support both pure and effectful execution, and integrate seamlessly with the pipeline-oriented architecture.

struct in, struct out behavior
output type unspecified


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

## Function shape matching

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


## Function Metadata and Advanced Features

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

## Pattern-Based Function Dispatch


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

## Implementation Priorities

1. **Basic Function Dispatch**: Shape-based parameter matching and scoring
2. **Pure Function System**: Security isolation and compile-time evaluation
3. **Function Scoping**: `@func` namespace management and lifecycle
4. **Pattern Matching**: Tag-based polymorphic dispatch
5. **Performance**: Memoization and compile-time optimization

## Open Design Questions

1. **Block Purity**: Should all function argument blocks be restricted to pure execution, or should there be syntax for blocks that can access resources?

2. **Function Overloading**: What happens when shape patterns are ambiguous? Should there be explicit disambiguation syntax?

3. **Tail Call Optimization**: Should the language guarantee tail call optimization for recursive functions?

4. **Async Functions**: How should asynchronous operations integrate with the pipeline model?

5. **Function Metadata**: What introspection capabilities should be available for functions at runtime?

This design provides a comprehensive function system that balances expressiveness with safety, enables powerful abstraction patterns while maintaining static analyzability, and supports both pure computational functions and effectful operations through clear distinctions.
