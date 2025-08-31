# Comp Language Specification

*Detailed technical specification for the Comp programming language*

## Overview

Comp is a programming language based on **shape-based data flow through chained pipelines**. All data is treated as immutable structures that flow through transformation functions using left-to-right pipeline operators.

## Core Data Model

### Universal Struct Model
- All data in Comp is represented as structs (key-value pairs)
- Scalars automatically promote to single-element structs when needed
- Collections are structs containing indexed or named elements

```comp
# These are equivalent when passed to functions expecting structs
42                    # Scalar
{42}                  # Single-element struct
{value=42}            # Named field struct
```

### Shape-Based Compatibility
Functions accept any data that contains the required structure, regardless of additional fields:

```comp
# Function expects {name: string}
process_user = {data -> "Hello ${data.name}"}

# All of these work:
{name="Alice"} -> process_user                    # Exact match
{name="Bob" age=30} -> process_user               # Extra fields ignored  
{name="Charlie" role="admin" active=true} -> process_user  # Shape matches
```

## Pipeline Operators

### Basic Pipeline (`->`)
Passes data from left side to right side function:

```comp
data -> function_name
data -> {item -> transformation}
```

### Iteration Pipeline (`->each`)
Applies transformation to each element in a collection:

```comp
users ->each {user -> user.name}
numbers ->each {n -> n * 2}
```

### Conditional Pipeline (`->if`)
Executes pipeline branch based on condition:

```comp
data -> {item -> item.age >= 18} ->if {
    item -> adult.process
} else {
    item -> minor.process  
}
```

### Error Handling Pipeline (`->failed`)
Catches and handles errors in pipeline:

```comp
risky_operation 
-> process.data
->failed {error -> 
    error.log("Failed: ${error.message}")
    -> fallback.value
}
```

## Type System

### Structural Typing
Types are defined by required structure rather than explicit declarations:

```comp
# Type annotation (optional)
user_data : {name: string age: int email: string}

# Function with structural requirement
greet = {person : {name: string} -> "Hello ${person.name}"}
```

### Hierarchical Tags
Tags provide polymorphism and type organization:

```comp
# Fixed enumeration tag
!tag animal = {dog cat bird fish}

# Open set tag (extensible)
!tag status = {pending processing completed error ...}

# Shape with tag inheritance
!shape Dog = {...Animal type=animal.dog breed: string}
!shape Cat = {...Animal type=animal.cat indoor: bool}
```

### Collection Constraints
Specify size and type constraints for collections:

```comp
# Function requiring exactly 3 strings
process_names = {names : {string[3]} -> names ->each string.capitalize}

# Function requiring 1 or more users
notify_users = {users : {User[1-]} -> users ->each send.notification}

# Optional items (0 or more)
process_tags = {tags : {string[0-]} -> tags ->each tag.normalize}
```

## Advanced Features

### Context Stack
Dependency injection through hierarchical context:

```comp
# Context injection
$ctx.database -> {db -> db.query("SELECT * FROM users")}
$ctx.logger -> {log -> log.info("Processing started")}

# Context flows through pipelines automatically
```

### Global State
Explicit global mutable variables:

```comp
# Declaration
!global app_state : {current_user: User session_id: string}

# Usage
app_state.current_user = new_user
app_state.session_id -> session.validate
```

### Lazy Evaluation
Deferred computation with context capture:

```comp
!lazy expensive_computation = {
    large_dataset -> complex.analysis -> ml.predict
}

# Computed only when accessed
expensive_computation -> use.results
```

### Documentation Integration
Built-in documentation syntax:

```comp
@ProcessUser Transforms user data for display
@param user User object with name and profile  
@returns Formatted user string
process_user = {user : {name: string} ->
    @ Convert user name to display format @
    "User: ${user.name}" 
}
```

## Standard Library Integration

### File Operations
```comp
# Read and process files
"/path/file.json" -> file.read -> json.parse -> process.data

# Write results  
processed_data -> json.stringify -> file.write("/output/result.json")
```

### Database Operations
```comp
# Query and transform
"SELECT * FROM users WHERE active = true" 
-> db.query 
->each {user -> {id=user.id display_name="${user.first} ${user.last}"}}
-> results.collect
```

### String Processing
```comp
# Text manipulation pipeline
"Hello World" 
-> string.lower 
-> {text -> text@string.split(" ")} 
->each string.capitalize 
-> {words -> words@string.join("-")}
# Result: "Hello-World"
```

## Syntax Grammar

### Basic Structure
```
program := statement*
statement := assignment | expression | declaration
assignment := identifier '=' expression
expression := pipeline | literal | struct | function
pipeline := expression '->' operator
operator := 'each' | 'if' | 'failed' | identifier | lambda
```

### Struct Literals
```
struct := '{' field_list? '}'
field_list := field (',' field)*
field := identifier '=' expression | expression | '...' identifier
```

### Function Definitions
```
function := '{' parameter_list? '->' expression '}'
parameter_list := parameter (',' parameter)*
parameter := identifier | identifier ':' type_spec
```

### Type Specifications
```
type_spec := identifier | struct_type | collection_type
struct_type := '{' field_type_list '}'
collection_type := '{' type_spec '[' range_spec ']' '}'
range_spec := number | number '-' | number '-' number
```

## Implementation Notes

### Phase 1: Core Language
- Basic pipeline operators and struct manipulation
- Structural typing and shape inference
- Standard library for common operations

### Phase 2: Advanced Features  
- Tag system and hierarchical polymorphism
- Context stack and dependency injection
- Lazy evaluation and optimization

### Phase 3: Tooling Ecosystem
- Syntax highlighting and language server
- Package management and module system
- Development tools and debugging support

---

*This specification defines the core language features and provides implementation guidance for the Comp programming language.*