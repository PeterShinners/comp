# Shapes, Blocks, and Higher-Order Functions

*Design for Comp's shape system, block parameters, and higher-order function capabilities*

## Overview

This document covers Comp's shape system for structural typing, block-based higher-order functions, and their integration patterns. Shapes provide flexible data validation and transformation, while blocks enable powerful functional programming patterns with controlled execution environments.

## Shape System

### Shape Definition Syntax

```comp
!shape ~Point2d = {
    x ~num = 0
    y ~num = 0
}

!shape ~User = {
    name ~str
    age ~num
    email ~str
    active ~bool = !true
    preferences? // Optional field
    tags #user_tag[]  // Array of user tags
}
```

### Shape Inheritance with Spreading

```comp
!shape ~Point3d = {
    ...~Point2d    // Inherit x, y fields
    z ~num = 0  // Add z coordinate
}

!shape ~ColoredPoint = {
    ...~Point2d
    color ~str = "black"
}

// Function parameter spreading
!func :analyze ~{...~RawData, complexity ~num = 0} = {
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
    host ~str = "localhost"
    port ~num = 8080
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
!func :create_user ~{name ~str, age ~num, active ~bool = !true} = {
    // Automatically morphs input using ?~@
    @in -> :validate -> :save
}

// All of these work:
{name="Alice", age=30} -> :create_user                    // Uses default active=!true
{name="Bob", age=25, active=!false} -> :create_user       // Explicit active
{name="Carol", age=40, extra="data"} -> :create_user      // Extra fields ignored (weak morph)
```

## Block Parameters and Higher-Order Functions

### Block-Based Function Parameters

```comp
!func :process_list ~{items, blocks={handler}} = {
    items => handler
}

// Usage with inline blocks
data -> :process_list 
    handler={item -> item.name -> :str:uppercase}
```

### Named Block Parameters

```comp
!func :http_request ~{url ~str} blocks={
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

## Shape Pattern Matching

### Shape-Based Pattern Matching

Shapes can be used for pattern matching and conditional processing:

```comp
!shape ~HttpResponse = {
    status #http_status
    data
    headers = {}
}

// Pattern matching on shapes
response ~ HttpResponse -> match {
    {status=#http_status#success} -> data -> :process_success
    {status=#http_status#error, data} -> data -> :handle_error  
    {status=#http_status#redirect, headers} -> headers.location -> :redirect
}
```

### Guard Conditions in Shapes

```comp
!shape ~ValidUser = {
    name ~str|len>0      // Non-empty string
    age ~num|min=0|max=150  // Reasonable age range
    email ~str|matches=/^[^@]+@[^@]+$/  // Email pattern
}

!func :create_user ~ValidUser = {
    // Input guaranteed to match validation rules
    @in -> :save_to_database
}
```

## Performance and Optimization

### Shape Compilation and Caching

```comp
// Shapes can be compiled for faster repeated application
!shape ~ValidatedUser = {
    name ~str|len>0
    email ~str|matches=/^[^@]+@[^@]+$/
    age ~num|min=0|max=150
}

// First application compiles shape rules
user_data ~ ValidatedUser  // Compiles validation rules
similar_data ~ ValidatedUser  // Uses cached compiled shape
```

## Integration Examples

### API Handler with Shape Validation

```comp
!shape ~UserCreateRequest = {
    name ~str|len>0
    email ~str|matches=/^[^@]+@[^@]+$/
    age ~num|min=13|max=120
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
!func :etl_pipeline ~{source ~str, target ~str} blocks={
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

## Unit System

### Unit Definition Syntax

```comp
!unit @distance ~num = {
    m = !nil                    // Base unit
    km = {mult=0.001}          // Conversion factor
    inch = {mult=39.3701}      // Inches per meter
    lightyear = {mult=1.057e-16}
}

!unit @temperature ~num = {
    celsius = !nil
    fahrenheit = {offset=32, mult=1.8}    // Custom conversion
    kelvin = {offset=-273.15}
}
```

### Unit Usage and Conversion

```comp
distance = 5@distance@km
converted = distance -> :units:to @distance@m    // 5000@distance@m

// Automatic validation
speed = 60@distance@km / 1@time@hour    // Type-safe unit arithmetic
```

### Unit-Aware Security

Units can apply domain-specific escaping for security:

```comp
$query = "SELECT * FROM users WHERE id=${user_id}"@sql
// @sql unit automatically applies SQL escaping

$html = "<div>${content}</div>"@html
// @html unit applies HTML escaping

$shell = "ls ${directory}"@shell  
// @shell unit applies shell escaping
```

### Custom Unit Formatters

Unit formatters must be `!pure` functions for compile-time evaluation:

```comp
!pure :format_currency ~{value @currency} = {
    "$${value -> :num:format {decimals=2}}"
}

@currency = {formatter=:format_currency}
```


## Implementation Priorities

1. **Shape Morphing**: Three-phase matching algorithm implementation
2. **Block Parameters**: Higher-order functions with block syntax  
3. **Shape Compilation**: Optimization and caching for repeated shape applications
4. **Guard Conditions**: Runtime validation of shape constraints
5. **Pattern Matching**: Shape-based conditional processing

## Open Design Questions

1. **Shape Constraints**: How should complex shape constraints be validated efficiently at runtime vs compile-time?

2. **Block Execution**: Should block parameters have configurable execution environments (pure vs effectful)?

3. **Shape Inheritance**: Should there be explicit inheritance relationships between shapes beyond spreading?

4. **Shape Validation**: What level of shape constraint checking should happen at compile-time vs runtime?

5. **Block Scope**: How should variable capture work in block parameters passed to functions?

This design provides a comprehensive shape and block system that enables flexible data validation, powerful functional programming patterns, and sophisticated higher-order function capabilities while maintaining clear execution semantics.
