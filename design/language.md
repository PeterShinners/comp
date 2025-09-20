# Language Overview

*Essential concepts and syntax for programming in Comp*

## Introduction

Comp is a functional language where every value is an immutable structure and every operation transforms data through pipelines. The language combines the accessibility of dynamic scripting with the safety of structural typing, making it ideal for data processing, API integration, and system glue code.

This overview introduces the essential concepts needed to understand Comp programs. For detailed specifications of any feature, see the corresponding design document in the `design/` directory.

## Getting Started

**Note: Comp is currently in design phase with no implementation. These examples show intended syntax and behavior.**

A minimal Comp file is a complete program. Every `.comp` file can serve three roles simultaneously: an executable program when it contains `!main`, an importable module through its exported definitions, and a complete package with embedded metadata.

```comp
!main = {
    (hello world |print)
}
```

Save this as `hello.comp` and (once implemented) run with `comp hello.comp`. The `!main` function serves as the entry point, receiving command-line arguments as its input structure and returning an exit code.

## Core Concepts

### Everything is a Structure

Comp unifies all data representation into structures - ordered collections that can contain both named and unnamed fields. This uniformity means the same operations work whether you're handling JSON from an API, rows from a database, or values computed in your program.

```comp
42                      
{x=10 y=20}            
{1 2 3}                
{name=Alice 30 active=#true}
```

When a scalar value like `42` enters a pipeline, it automatically promotes to a single-element structure `{42}`. This auto-wrapping means functions always receive structures, simplifying the programming model. Named fields can appear in any order and are accessed by name, while unnamed fields maintain their position and are accessed by index.

Structures are immutable - operations create new structures rather than modifying existing ones. This immutability ensures predictable behavior, enables safe parallelism, and eliminates entire classes of bugs related to shared mutable state.

### Pipeline Operations

Data transformation happens through pipelines that connect operations with the `|` operator. Each operation in a pipeline receives the output of the previous operation as its input, creating a clear left-to-right flow of data transformation.

```comp
(data |validate |transform |save)

(items |map |process-each |collect-results)

(risky |operation |? |handle-error)
```

Pipelines are enclosed in parentheses to clearly mark their boundaries. The `|` operator marks function application, with functions written as `|function-name`. The `|?` operator intercepts failures, allowing graceful error recovery without breaking the pipeline flow.

### Functions Transform Structures

Functions in Comp are pure transformations from one structure to another. Every function declares its expected pipeline input shape and argument structure. This dual-shape approach separates data flow from configuration.

```comp
!pipe {shape}
!args {}
!func |area = {
    $pipe.width * $pipe.height
}

!pipe {items}
!args {threshold ~num}
!func |filter-above = {
    $in |filter {$pipe.value > $arg.threshold}
}
```

Functions can be invoked by any structure containing the required fields. The separation between pipeline data (`$in`) and arguments (`$arg`) makes the distinction between data transformation and parameterization clear.

### Shapes Define Structure

Shapes act as schemas that describe the expected structure of data. They specify field names, types, default values, and constraints. Unlike rigid class definitions, shapes use structural matching - any data that contains the required fields satisfies the shape.

```comp
!shape user = {
    name ~str
    age ~num = 0
    email ~str
}
```

The `~` operator morphs structures to match shapes, performing validation and transformation in a single operation. When morphing, the system attempts to match fields by name first, then by position, applying defaults for missing optional fields.

### Tags for Enumeration

Tags provide hierarchical enumeration with optional values. They serve triple duty as enumerated constants, type markers, and polymorphic dispatch keys. Every tag is prefixed with `#` and uses reversed hierarchy notation.

```comp
!tag status = {
    #active = 1
    #inactive = 0  
    #pending
}

; Usage with shortened form when unique
state = #active
state = #pending
```

Tags can be referenced by their most specific part when unique, with additional parent components added only when disambiguation is needed.

## Module System

Modules organize related functionality into namespaces. Each module contains definitions of functions, shapes, and tags that work together. The import system brings modules into scope with namespace prefixes.

```comp
!import str = std "core/str"
!import math = std "core/math"

; Functions use reversed namespace notation
(text |upper/str)
(value |sqrt/math)

; Or create aliases for frequently used functions
!alias |sqrt = |sqrt/math
(value |sqrt)
```

## Control Flow

Control flow uses regular functions with block arguments. Blocks are evaluated within the function, receiving pipeline data as needed.

```comp
(value |if {$pipe.value > 5} large small)

($in |when {$pipe.error?} {
    ($pipe.error |log)
})

(value |match 
    {0} zero
    {1} one
    default other)
```

## Variables and Namespaces

Comp provides multiple namespaces for organizing data:

- `$in` - Pipeline input data
- `$pipe` - Output structure being built (cascades to `$in`)
- `$var.name` - Function-local variables
- `$arg.name` - Function arguments (cascades to `$ctx`, `$mod`)
- `$ctx.name` - Execution context
- `$mod.name` - Module-level data

```comp
!pipe {data}
!args {port ~num}
!func |example = {
    $var.sum = $in |sum
    
    server-port = $arg.port    ; Cascades through context/module
    total = $var.sum
    user = $pipe.user          ; Cascades through output/input
    config = $mod.config       ; Explicit module reference
}
```

## Basic Types

### Numbers

Comp numbers provide unlimited precision without overflow or rounding errors:

```comp
huge = 999999999999999999999
precise = 1/3              ; Exact fraction
5#meter + 10#foot          ; Units as tags
```

### Strings  

Strings are immutable UTF-8 text. Tokens without special prefixes are treated as string literals:

```comp
greeting = hello           ; String "hello"
name = Alice              ; String "Alice"
{name=Bob age=30}         ; name is field, Bob is string
```

### Booleans

Booleans are represented by two tags: `#true` and `#false`. Comparisons produce boolean values:

```comp
valid = $pipe.x > 0              
ready = #true
enabled = $pipe.name == Alice    ; Alice is string literal
```

## Operators Summary

**Pipeline and function operators:**
- `()` - Pipeline boundaries
- `|` - Function application
- `|?` - Failure handling

**Fallback operator:**
- `??` - Provide alternative value

**Assignment operators:**
- `=` - Normal assignment
- `*=` - Strong assignment (resists overwriting)
- `?=` - Weak assignment (only if undefined)

**Spread operators:**
- `..` - Normal spread
- `!..` - Strong spread
- `?..` - Weak spread

**Reference prefixes:**
- `$` - Variable/namespace access
- `|` - Function reference
- `#` - Tag reference  
- `~` - Shape reference

**Field access:**
- `data.field` - Named field
- `data#0` - Positional index (numeric literals only)
- `data.'expr'` - Computed field name
- `data."string"` - String literal field name

## Key Features

### Automatic Resource Management

Resources are tracked automatically and released when they go out of scope:

```comp
$var.file = (path/to/file |open/file)
content = $var.file |read
; File automatically closes when $var.file leaves scope
```

### Transactions

Transactions coordinate multiple operations that should succeed or fail atomically:

```comp
!transact $database {
    (user |insert)
    (profile |update)
}
```

### Store for Mutability

When controlled mutability is needed, Stores provide a safe container:

```comp
$var.store = (|new/store {count=0})
$var.store |update count {$pipe.count + 1}
current = $var.store |get count
```

## Complete Example

Here's a practical example showing the syntax in action:

```comp
!import gh = comp "github-api"
!import time = std "core/time"

!alias |now = |now/time

!main = {
    $var.after = (|now) - 1#week
    
    (|list-issues/gh repo=complang/comp) 
     |filter {$pipe.created-at >= $var.after}
     |map {
         thumbs-up = ($pipe.reactions |count-if {$pipe.content == #thumbs-up})
         {thumbs-up title=$pipe.title url=$pipe.url}
     }
     |sort-by reverse {$pipe.thumbs-up}
     |first 5)
}
```

## Style Guide

The standard style uses:
- Tabs for indentation
- lisp-case for names (lowercase with hyphens)
- `?` suffix for boolean functions and fields
- Operators at the start of continuation lines
- Lines under 100 characters when reasonable
- Function references always attached: `|function` not `| function`

## Next Steps

With these concepts, you're ready to explore Comp's design in depth. Each major feature has a dedicated design document in the `design/` directory:

- `structure.md` - Deep dive into structures and operations
- `function.md` - Function definition and dispatch
- `shape.md` - Shape system and morphing
- `pipeline.md` - Pipeline operations and failure handling
- `module.md` - Module system and imports

Remember that Comp is currently in design phase. These documents describe intended behavior that will guide implementation.