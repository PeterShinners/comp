# Comp Language Specification

## Overview

Comp is a data transformation language built around immutable structures flowing through pipelines. Every operation creates new data rather than modifying existing values, ensuring predictable behavior and enabling powerful composition patterns.

## Core Concepts

### 1. Data Model

Everything in Comp is a structure (struct) - an ordered collection of fields that may be named, unnamed, or tagged.

```comp
// Structures can mix named and unnamed fields
{10, name="Alice", age=30}          // Mixed structure
{x=5, y=10}                          // Named fields only
{100, 200, 300}                      // Unnamed fields only
```

### 2. Pipeline Operators

Data flows left-to-right through transformation functions:

```comp
data -> transform -> filter -> output    // Single item pipeline
data => transform => filter => output    // Collection pipeline
```

### 3. Immutability

All data is immutable. Operations create new structures:

```comp
original = {x=10, y=20}
modified = {...original, x=15}    // Creates new struct {x=15, y=20}
// original remains {x=10, y=20}
```

### 4. Shape System

Shapes define expected structure and enable type checking:

```comp
!shape Point2d = {x(number), y(number)}
data ~ Point2d    // Morphs data to match shape
```

## Language Elements

### Boolean Operators

```comp
!true     // Boolean true
!false    // Boolean false
```

### Structure Creation

```comp
// Regular (eager) structures
{field=value, field2=value2}

// Lazy structures (evaluated on access)
[expensive_field = computation]
```

### Field Access

```comp
// Named field access
data.fieldname
data."field name with spaces"

// Computed field access
data.'$variable_name'
data.'(expression)'

// Positional access
data#0    // First element
data#1    // Second element
```

### Variables and Scopes

```comp
$var = value           // Local variable
@in.field             // Input scope
@mod.setting          // Module scope
@env.config           // Environment scope
```

### Functions

```comp
!func name(parameters) = expression

// Anonymous functions
{x, y -> x + y}
```

### Control Flow

```comp
// Conditional (ternary)
condition ? true_value | false_value

// Pattern matching
value -> match {
    pattern1 = result1
    pattern2 = result2
    else = default
}
```

### Assignment Operators

```comp
=     // Normal assignment
*=    // Strong assignment (force/persist)
?=    // Weak assignment (conditional)
^=    // Protected assignment
~=    // Override assignment
```

### Spread Operators

```comp
...data           // Normal spread
..*data          // Protected spread
..?data          // Conditional spread
```

## Type System

### Basic Types
- Numbers (integer and floating point)
- Strings (UTF-8 text)
- Booleans (`!true`, `!false`)
- Structures (ordered field collections)
- Tags (hierarchical type markers)

### Tag System

Tags provide semantic typing and hierarchical categorization:

```comp
#status.ok
#http.response.success
#validation.error.missing_field
```

### Shape Definitions

```comp
!shape TypeName = {
    field1(type)
    field2(type) = default_value
    field3?                    // Optional field
    #tag_field                // Tag-typed field
    ...rest                   // Rest fields
}
```

## Shape Application and Morphing

### Basic Shape Application

```comp
data ~ Shape           // Normal morph
data *~ Shape          // Strong morph (strict)
data ?~ Shape          // Weak morph (lenient)
data ~@ Shape          // Morph with namespace inheritance
```

### Field Matching Algorithm

When applying shapes, fields are matched in this order:
1. **Named matches** - Exact field name matches
2. **Tag matches** - Fields with matching tags
3. **Positional matches** - Remaining fields by position

### Function Dispatch

Functions with the same name but different shapes use lexicographic scoring:
1. Number of named field matches
2. Number of tag field matches  
3. Assignment strength (strong > normal > weak)
4. Number of positional matches

## Standard Library Structure

```comp
:string:*         // String operations
:number:*         // Numeric operations
:struct:*         // Structure operations
:array:*          // Collection operations
:tag:*            // Tag operations
:io:*             // Input/output
:json:*           // JSON handling
:sql:*            // Database operations
```

## Data Transformation Concepts

### Promotion
Converting external data into Comp types:
```comp
json_data -> :json:promote    // Strings → dates, numbers, tags
cli_args -> :cli:promote      // "yes" → !true, "3" → 3
```

### Morphing
Applying shapes to restructure data:
```comp
{10, 20} ~ Point2d    // Morphs to {x=10, y=20}
```

### Casting
Type conversions between Comp types:
```comp
"123" -> :number:cast       // String to number
#status.ok -> :string:cast  // Tag to string
```

---

## Implementation Details

### Pipeline Operations

#### Spread Arrow Operator (`..>`)

The spread arrow merges additional fields into the flowing data:

```comp
// Equivalent expressions
data ..> {min=0 max=10} -> :clamp
data -> {..$in min=0 max=10} -> :clamp

// Works with functions returning structures
data ..> :get_defaults -> :process

// Can spread from namespaces
data ..> @func -> :process
```

This operator is particularly useful for adding parameters to a value flowing through a pipeline without wrapping it in a nested structure.

### Namespace Scoping

#### Scope Hierarchy
1. `@in` - Function input parameters
2. `@func` - Function-local scope (automatically cleared on exit)
3. `@mod` - Module-level constants and configuration
4. `@env` - Environment-wide settings

#### Function Scope Behavior
The `@func` namespace provides function-local storage that is automatically cleaned up:

```comp
!func process(data) = {
    @func.retries = 3        // Set function-scoped value
    @func.timeout = 30       // Available throughout function
    
    data -> :fetch -> :parse  // Can access @func values
}  // @func namespace cleared here
```

Unlike `@mod` and `@env`, the `@func` namespace is isolated to each function invocation and cannot persist beyond the function's scope.

### Structure Access Patterns

#### Named Field Access
- Direct: `data.field`
- Quoted: `data."field name"`
- Computed: `data.'$var'` or `data.'(expr)'`

#### Positional Access
- Zero-indexed: `data#0`, `data#1`
- Forward-only (no negative indexing)
- Out of bounds returns failure

#### Assignment Behaviors

##### With Named Fields
- `=` overwrites existing
- `?=` only assigns if undefined
- `*=` forces assignment

##### With Positions
- `=` assigns if position exists (fails otherwise)
- `?=` assigns if position valid (silent skip otherwise)
- `*=` extends structure if needed

### Shape Application Details

#### Matching Process
1. **Pass 1**: Match all named fields explicitly
2. **Pass 2**: Match tagged fields by tag type
3. **Pass 3**: Fill remaining with positional matching
4. **Pass 4**: Apply defaults for unmatched optional fields

#### Compound Operators
- `~` - Normal morph with defaults
- `*~` - Strong morph (strict, no extras)
- `?~` - Weak morph (lenient, allow missing)
- `~@` - Include namespace lookups
- `*~@` - Strong with namespace
- `?~@` - Weak with namespace

#### Function Invocation
Functions automatically apply `?~@` to incoming arguments:
- Weak: Extra fields ignored
- Namespace-aware: Can pull defaults from scope chain

### Failure Handling

Shape application failures return structured data:
```comp
{
    #failure
    #shape_application_failed
    message = "Description"
    partial = {partial results}
    mapping = {field mappings}
    errors = {specific errors}
}
```

### Domain-Specific Promotion

Different data sources use different promotion rules:

```comp
:cli:promote     // "yes"→!true, "0"→!false, "3"→3
:json:promote    // ISO dates→datetime, true/false→boolean
:sql:promote     // 1/0→boolean, SQL dates→datetime
:env:promote     // All strings, selective promotion
```

### Lazy Evaluation

Lazy structures `[...]` evaluate fields on access:
- Fields computed only when needed
- Can use flow control (`break`)
- Captures context at creation time

### Contextual Behaviors

Assignment operators and shape applications adapt to context:
- In named fields: `?=` checks existence
- In positions: `?=` checks validity
- In functions: Persistence vs temporary

---

## Design Principles

1. **Immutability First** - No in-place modification
2. **Explicit Over Magic** - Clear, predictable behavior
3. **Composition Friendly** - All operations compose naturally
4. **Data Flow Oriented** - Left-to-right pipeline model
5. **Structural Freedom** - Mix named, unnamed, and tagged fields
6. **Progressive Enhancement** - From simple values to complex shapes

---

## Future Considerations

- Module system and imports
- Async operations and promises
- Custom operators
- Macro system
- Performance optimizations
- Tooling integration

---

*Version: 0.3.0 - Last updated: September 2025*