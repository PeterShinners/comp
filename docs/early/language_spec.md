# Comp Language Specification

*Detailed technical specification for the Comp programming language*

## Overview

Comp is a programming language based on **shape-based data flow through chained pipelines**. All data is treated as immutable structures that flow through transformation functions using left-to-right pipeline operators.

### Core Philosophy

Everything in Comp is data transformation through pipelines. Structures cannot be modified in place - instead, new structures are created using spread operators and field assignments. The language treats SQL results, JSON objects, function returns, and literals identically through a uniform data model.

### Syntax Principles

- Whitespace separates fields and function calls, no commas or semicolons required
- Statements can span multiple lines and multiple statements can appear on single lines
- Each expression ends when it reaches the end of pipeline operators
- Whitespace is optional inside expressions, only needed to separate tokens
- Mathematical operators are reserved for number types only
- Comments use `//` and `/* */` syntax

### Key Concepts

- All data flows left-to-right through transformation pipelines
- Functions accept one input structure and generate one output structure
- Defining structures uses the same syntax as defining function blocks
- The language provides minimal flow control - prefer higher-level functions
- Multiple scopes provide different visibility for storing values

## Core Data Model

### Universal Struct Model

All data in Comp is represented as structs (key-value pairs). Scalars automatically promote to single-element structs when passed to functions expecting structs.

```comp
42                    # Scalar - becomes {42} when passed to functions
{x=1.0 y=2.0}         # Named field struct
{..data order=10}     # Spread existing struct with modifications
{"north" "south" "east" "west"}  # Unnamed field struct (array-like)
```

### Shape Definitions

Shapes define the expected structure and types of data:

```comp
!shape Point = {x(number) y(number) z(number)}
!shape User = {
    name(string) 
    age(number) 
    active(bool) = true  # Default value
}
```

### Shape-Based Compatibility

Functions accept any data containing the required structure. Extra fields are ignored, enabling flexible data transformation:

```comp
# Function expects {name(string)}
process_user = {data -> "Hello ${data.name}"}

# All compatible:
{name="Alice"} -> process_user                    # Exact match
{name="Bob" age=30} -> process_user               # Extra fields ignored  
{name="Charlie" role="admin"} -> process_user     # Shape compatible
```

### Type System with Parentheses

Type annotations use parentheses for clarity and familiarity:

```comp
!shape Rectangle = {width(number) height(number) color(string)}
!func area(rect(Rectangle)) = {rect.width * rect.height}

# Type validation in pipelines
user_data(User) -> validate -> save
value(string) -> display
```

## Pipeline Operators

### Basic Pipeline (`->`)

Passes data from left side to right side function:

```comp
data -> function_name
data -> {item -> transformation}
data -> module:function_name    # Imported function
data -> :local_function         # Local function reference
```

### Iteration Pipeline (`=>`)

Applies transformation to each unnamed field in a structure:

```comp
users => {user -> user.name}           # Transform each user
numbers => {n -> n * 2}                # Double each number
data => {item -> item.active ? item}   # Filter active items
```

The iteration block can return special control tokens like `skip` or `break`. The standard library provides higher-level iteration with indexing and accumulation.

### Conditional Pipeline (`?|`)

Ternary operator for conditional execution - exactly one branch executes:

```comp
age >= 18 ? {-> adult_processing} | {-> minor_processing}
condition ? {data -> transform} | {}  # Empty block for no-op
```

### Failure Handling Pipeline (`!>`)

Handles error conditions in pipelines. Operations are skipped when structure contains error tags:

```comp
risky_operation 
-> process_data 
!> {error -> 
    error.log("Failed: ${error.message}")
    -> fallback_value
}
```

## Built-in Types

### Number Type

Unified number type prioritizing mathematical correctness:

```comp
10 / 3        # Always 3.333..., never truncates
1000000000000000000 + 1  # Always exact, no overflow
price * quantity  # No type juggling needed
```

Context controls numeric behavior:

```comp
$ctx.number.epsilon = 1e-9        # Equality comparison tolerance
$ctx.number.precision = 28        # Decimal precision
$ctx.number.rounding = math.half_up  # Rounding method
$ctx.number.int = math.round       # Fractional to integer conversion
```

### String Type

Unicode character sequences with template interpolation and multiline support:

```comp
"Hello ${name}"                    # Template interpolation
"Hello ${name}"@html.escape        # Template with handler
message(string) -> display         # Type annotation

# Triple quotes for multiline and embedded quotes
sql_query = """
    SELECT users.name, profiles.bio
    FROM users 
    WHERE users.active = true
"""

html_template = """
    <div class="user">
        <h2>${user.name}</h2>
        <p>"${user.bio}"</p>
    </div>
"""
```

### Boolean Type

Binary true/false values:

```comp
active = true
condition = user.age >= 18
verified(bool) -> process
```

### Buffer Type

Binary data blocks for system interaction and FFI:

```comp
image_data(buffer) -> compress
file_content -> buffer.decode("utf8")
```

## Functions and Shapes

### Function Definitions

Functions are defined with explicit input shapes:

```comp
!func greet(person({name(string)})) = {
    "Hello ${person.name}!"
}

!func calculate_area(rect({width(number) height(number)})) = {
    rect.width * rect.height
}
```

### Function Calls and Module References

Functions use `:` prefix for local references and module qualification for imports:

```comp
# Local function calls
data -> :validate_input -> :process_data

# Imported function calls  
data -> io:print
config -> json:stringify -> file:write("/config.json")

# Functions can start pipeline chains
:initialize_system -> :load_config -> :start_services
```

### Shape Definitions

Shapes define data structure contracts:

```comp
!shape User = {
    name(string)
    email(string) 
    age(number)
    preferences({theme(string) = "light"})
}

# Usage
user_data(User) -> validate_user -> save_to_database
```

## Tags and Polymorphism

### Tag Definitions

Tags provide hierarchical type organization and polymorphic dispatch:

```comp
# Simple tag enumeration
!tag status = {pending, completed, failed}

# Hierarchical tags
!tag emotions = {
    anger = {fury, irritation, righteous}
    joy = {happiness, excitement, contentment}
    fear = {worry, terror, respect}
}

# Cross-module tag importing
!tag local_status = {
    ..external#workflow#status    # Import all values
    custom_pending                # Local extension  
    urgent = external#workflow#status#high  # Alias
}
```

### Tag-Based Polymorphism

Functions dispatch based on tag-typed struct fields:

```comp
!shape Pet = {name(string) breed(#animal) age(number)}

# Polymorphic function implementations
!func speak(breed(#animal#dog)) = {pet -> "${pet.name} barks loudly"}
!func speak(breed(#animal#cat)) = {pet -> "${pet.name} meows softly"}
!func speak(breed(#animal#bird)) = {pet -> "${pet.name} chirps sweetly"}

# Usage - dispatch based on breed field value
my_dog = {name="Rex" breed=#animal#dog age=3}
my_dog -> :speak    # Calls dog implementation
```

### Inheritance with !super

Call parent implementations in tag hierarchies:

```comp
!func process(emotion(#emotions#anger)) = {
    "Processing anger: ${data.intensity}"
}

!func process(emotion(#emotions#anger#fury)) = {
    intensity_check -> !super(emotion)  # Call anger implementation
    -> add_fury_specific_handling
}

# Specific parent targeting
result -> !super(emotion=#emotions#anger)  # Skip intermediate levels
```

### Cross-Branch Calling

Jump between tag branches using explicit casting:

```comp
# Transform data to different branch, then call
{...dog_data breed=#animal#cat}(Cat) -> :feed
```

## Assignment and Variables

### Basic Assignment

Assignment passes the assigned value forward in pipelines:

```comp
$name = "Alice"          # Assign and pass "Alice" forward
$count = data.length     # Assign length and pass length forward
```

### Pipeline Value Capture

Capture current pipeline value while preserving flow:

```comp
config_path -> $path = $in -> io:read_data -> process -> $path -> fs:delete
```

### Nested Blocks for Side Effects

Execute side effects without disrupting main pipeline flow:

```comp
user_data -> nest.{
    $email = data.contact.email
    $timestamp = @now
    debug.log("Processing user: ${data.name}")
} -> validate_and_save
```

### Spread Assignment

Shorthand for struct updates:

```comp
# Standard spread assignment
user ..= {verified=true last_login=@now}

# Weak assignment - only add new fields
user ..?= {preferences={theme="dark"}}

# Strong assignment - replace entirely
user ..*= {name="Updated Name"}
```

## Field Access and Quoting

### Field Access Rules

```comp
# String identifiers - no quotes
user.profile.name

# Tags - no quotes (visually distinct)
config.#priority#high.handler

# Other types - quotes required
matrix.'0'.'1'.value        # Numbers
settings.'true'.enabled     # Booleans
data.'"complex key"'.value  # Strings with special characters
```

## Context and Scoping

### Context Stack

Hierarchical dependency injection through `$ctx`:

```comp
$ctx.database.connection = "prod://server"
$ctx.logger.level = "DEBUG"

# Context flows through pipelines
data -> process_with_logging -> save_to_database
```

### Application State

Global mutable state through `$app`:

```comp
$app.current_user = authenticated_user
$app.session_id = session.generate()

# Application state accessible throughout program
current_permissions = $app.current_user.permissions
```

### Thread Safety

Contexts are cloned at thread creation for isolation:

```comp
# Main thread context
$ctx.processing.mode = "batch"

worker_thread = spawn.{
    # Thread gets copy of parent context
    $ctx.processing.mode = "realtime"  # Only affects this thread
    heavy_computation -> results
}

# Main thread context unchanged
```

## Block-Based Functions

### Functions with Block Parameters

Functions can accept blocks as structured parameters:

```comp
!func match(input(single))
    cases={
        #status#pending(input)
        #status#completed(input)
        else = {input -> :error("Unhandled case")}  # Default block
    }
) = {
    input == #status#pending ? {input -> cases.#status#pending}
    | input == #status#completed ? {input -> cases.#status#completed}  
    | {input -> cases.else}
}
```

### Usage with Dotted Block Syntax

```comp
status -> :match
    .#status#pending {data -> "Still processing"}
    .#status#completed {data -> "All finished"}
    .else {data -> "Unknown status"}

# Custom match functions for different patterns
user_input -> :match_values
    .'0' {-> "Zero selected"}
    .'"quit"' {-> "Exiting program"}
    .else {-> "Unknown option"}
```

### Variadic Block Parameters

Functions accepting any number of blocks:

```comp
!func event_dispatcher(event(single))
    handlers={..(event)}  # Any number of event handler blocks
) = {
    # Dispatch to appropriate handler based on event type
    handlers => {handler_name, handler_func ->
        event_matches(event, handler_name) ? {event -> handler_func}
    }
}
```

## Error Handling

Error handling is integrated into pipeline flow rather than exceptions. Errors are special tagged structures that skip normal processing and flow to error handlers.

```comp
# Errors flow through pipelines
file_path -> io:read !> {error -> "Could not read file: ${error.path}"}
-> json:parse !> {error -> "Invalid JSON format"}  
-> validate_data !> {error -> "Data validation failed: ${error.details}"}
-> process_successfully
```

## Standard Library Integration

### File Operations

```comp
"/path/to/file.json" -> io:read -> json:parse -> process_data
processed_data -> json:stringify -> io:write("/output/result.json")
```

### Database Operations

```comp
"SELECT * FROM users WHERE active = true" 
-> db:query 
=> {user -> {id=user.id display_name="${user.first} ${user.last}"}}
-> results:collect
```

### String Processing

```comp
"Hello World" 
-> string:lower 
-> {text -> text@string.split(" ")} 
=> string:capitalize 
-> {words -> words@string.join("-")}
# Result: "hello-world"
```

## Key Standard Library Functions

The Comp standard library provides essential functions that complement the language's pipeline philosophy:

**Flow Control:**
- `:nest` - Execute block with side effects while preserving main pipeline flow
- `:match` - Pattern matching with multiple condition blocks  
- `:if` - Conditional execution with then/else blocks
- `:retry` - Retry operations with configurable attempts and backoff

**Data Transformation:**
- `:filter` - Remove elements that don't match conditions
- `:reduce` - Fold collection into single value with accumulator

**I/O Operations:**
- `:io:read` - Read data from files, URLs, or streams
- `:io:write` - Write data to files or outputs
- `:io:print` - Display data to console with formatting

**Concurrency:**
- `:spawn` - Create concurrent execution threads
- `:join` - Wait for thread completion and merge results
- `:parallel` - Execute multiple operations concurrently

These functions are designed to work seamlessly with Comp's pipeline operators and maintain the language's emphasis on immutable data transformation.

## Implementation Notes

### Compilation Phases

1. **Lexical Analysis**: Tokenize source with support for `#tag#value`, `:function`, field access
2. **Parsing**: Build AST with pipeline expressions, block parameters, tag hierarchies  
3. **Type Inference**: Shape-based compatibility checking, tag dispatch resolution
4. **Code Generation**: Target bytecode or native code with numeric optimizations

### Optimization Opportunities

- **Pipeline Fusion**: Combine adjacent transformations into single operations
- **Lazy Evaluation**: Defer expensive computations until results needed
- **Tag Dispatch**: Compile-time resolution of polymorphic function calls
- **Numeric Specialization**: Optimize common numeric operations despite unified type

---

*This specification defines the core Comp language features for implementation. The language prioritizes mathematical correctness, pipeline clarity, and shape-based flexibility while maintaining strong static analysis capabilities.*