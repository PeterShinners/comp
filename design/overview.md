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
    "Hello, World!" -> :print
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
{name="Alice" 30 active=#true}
```

When a scalar value like `42` enters a pipeline, it automatically promotes to a single-element structure `{42}`. This auto-wrapping means functions always receive structures, simplifying the programming model. Named fields can appear in any order and are accessed by name, while unnamed fields maintain their position and are accessed by index.

Structures are immutable - operations create new structures rather than modifying existing ones. This immutability ensures predictable behavior, enables safe parallelism, and eliminates entire classes of bugs related to shared mutable state.

### Pipeline Operations

Data transformation happens through pipelines that connect operations with the `->` operator. Each operation in a pipeline receives the output of the previous operation as its input, creating a clear left-to-right flow of data transformation.

```comp
data -> :validate -> :transform -> :save

items => :process_each => :collect_results

risky -> :operation !> :handle_error
```

The pipeline model extends beyond simple function chaining. The `=>` operator maps operations over collections, applying transformations to each element. The `!>` operator intercepts failures, allowing graceful error recovery without breaking the pipeline flow. These operators work together to create expressive data transformation chains that handle both success and failure paths elegantly.

### Functions Transform Structures

Functions in Comp are pure transformations from one structure to another. Every function declares its expected input shape - a structural pattern that describes what fields and types it requires. This shape-based approach means any data source can invoke any function as long as it provides the required fields.

```comp
!func :area ~{width ~num height ~num} = {
    width * height
}
```

This area function can be invoked by any structure containing numeric width and height fields. Position-based structures like `{10 20}` work through positional matching, while named structures like `{width=5 height=8}` match by field names. The function doesn't care about the source of the data - it could come from JSON, a database, or internal computation.

Statement seeding eliminates repetitive data threading. Each statement in a function body implicitly receives the function's input structure, as if prefixed with `.. ->`. This means common patterns like validation and transformation can be written concisely:

```comp
!func :analyze ~{data} = {
    cleaned = :clean_data
    validated = :validate  
    {cleaned validated}
}
```

Here, both `cleaned` and `validated` independently process the input data without explicit threading, then combine their results into the output structure.

### Shapes Define Structure

Shapes act as schemas that describe the expected structure of data. They specify field names, types, default values, and constraints. Unlike rigid class definitions, shapes use structural matching - any data that contains the required fields satisfies the shape.

```comp
!shape ~User = {
    name ~str
    age ~num = 0
    email ~str
}
```

The `~` operator morphs structures to match shapes, performing validation and transformation in a single operation. When morphing, the system attempts to match fields by name first, then by position, applying defaults for missing optional fields. If required fields cannot be matched or constraints are violated, the morphing fails with a descriptive error.

Shapes compose through spreading and union types, enabling complex schemas built from simpler pieces. They integrate with the module system for reusable type definitions and with the function system for parameter validation.

### Tags for Enumeration

Tags provide hierarchical enumeration with optional values. They serve triple duty as enumerated constants, type markers, and polymorphic dispatch keys. Every tag is prefixed with `#` and can exist in hierarchies where child tags inherit meaning from their parents.

```comp
!tag #status = {
    #active = 1
    #inactive = 0  
    #pending
}
```

Tags with values support bidirectional conversion - a numeric `1` can morph to `#status#active`, and the tag can convert back to its numeric value. This makes tags ideal for working with external systems that use numeric codes or string identifiers while maintaining type safety within Comp.

The hierarchical nature enables sophisticated pattern matching and polymorphic dispatch. Functions can handle specific tags while providing fallback behavior for parent categories, creating extensible systems without modification of existing code.

## Module System

Modules organize related functionality into namespaces. Each module contains definitions of functions, shapes, and tags that work together. The import system brings modules into scope with namespace prefixes, preventing naming conflicts while keeping references clear.

```comp
!import str/ = std "core/str"
!import math/ = std "core/math"
```

After importing, definitions are referenced through their namespace with type-specific prefixes. Functions use `:` (colon), shapes use `~` (tilde), and tags use `#` (hash). This visual distinction makes the type of each reference immediately apparent:

```comp
:math/sqrt              
~str/pattern           
#io/mode#read          
```

Modules can be single files or directories, imported from the standard library, local paths, git repositories, or package registries. Every module is self-contained with no forward declarations or header files required. Dependencies are explicit through imports, and circular dependencies are prevented by design.

## Control Flow

Control flow in Comp uses functions with block arguments rather than special syntax. Blocks are deferred structure definitions passed to functions, evaluated when the function calls them. This uniform approach means control flow follows the same patterns as data transformation.

Conditional execution uses three primary functions. The `:if` function provides traditional if-then-else branching with two blocks. The `:when` function executes a block only when a condition is true, with no else clause. The `:match` function enables pattern matching against multiple conditions:

```comp
:if .{x > 5} .{"large"} .{"small"}

:when .{error} .{
    error -> :log
}

value -> :match
    .{0} .{"zero"}
    .{1} .{"one"}
    .{..} .{"other"}
```

Iteration uses a similar pattern with functions that accept blocks for processing each element. The `:map` function transforms elements and collects results. The `:filter` function selects matching elements. The `:each` function performs side effects without collecting results. The `:fold` function reduces collections to single values using an accumulator pattern.

## Namespaces

Field references in Comp resolve through a stack of namespaces, each providing a different scope of data. When you write an undecorated token like `port` in your code, the language searches through these namespaces in order until finding a match.

The namespace stack consists of four layers. The `!out` namespace contains the structure currently being built by the function. The `..` namespace (accessed through double dots) contains the input structure to the current context. The `!ctx` namespace carries context that flows through function calls. The `!mod` namespace provides module-level shared data.

```comp
!func :example ~{port} = {
    !ctx.debug = #true       
    !mod.default = 8080      
    
    server_port = port       
    fallback = default       
}
```

This layered approach eliminates verbose parameter passing while keeping data flow explicit. Context naturally flows through call chains, module constants are available everywhere, and the separation between input and output prevents accidental mutations.

## Basic Types

### Numbers

Comp numbers provide unlimited precision without the overflow or rounding errors that plague fixed-size numeric types. Whether working with huge integers, precise decimals, or exact fractions, numbers maintain their precision through all operations.

```comp
huge = 999999999999999999999
precise = 1/3              
5#meter + 10#foot          
```

Division produces exact rational results - `1/3` remains a precise fraction rather than a truncated decimal. Units attach semantic meaning to numbers, enabling automatic conversion within unit families while preventing nonsensical operations like adding meters to seconds.

### Strings  

Strings are immutable UTF-8 text that cannot be modified after creation. Instead of concatenation operators, Comp uses template formatting through the `%` operator, providing a unified approach to string building.

```comp
"Hello, ${name}!" % {name="World"}
"${} + ${} = ${}" % {2 3 5}
```

Templates support positional placeholders that match unnamed fields, named placeholders that reference specific fields, and indexed placeholders for explicit positioning. String units can attach to provide semantic meaning and control template escaping behavior.

### Booleans

Booleans are represented by two tags: `#true` and `#false`. There's no automatic conversion from other types to booleans - comparisons must be explicit. This prevents ambiguity about truthiness and makes boolean logic clear.

```comp
valid = x > 0              
ready = #true
enabled = name == "Alice"
```

Boolean operators `&&`, `||`, and `!!` work exclusively with boolean values and short-circuit their evaluation. Control flow functions interpret `#false` and empty structures `{}` as false, all other values as true.

## Operators Summary

Pipeline operators control data flow: `->` transforms data through single operations, `=>` maps operations over collections, and `!>` handles failures in pipelines.

Assignment operators have three variants: `=` for normal assignment, `*=` for strong assignment that resists overwriting, and `?=` for weak assignment that only sets undefined fields.

Comparison operators work across all types with deterministic results: `==` and `!=` test equality, while `<`, `>`, `<=`, and `>=` provide total ordering even across different types.

Mathematical operators apply only to numbers: `+` addition, `-` subtraction, `*` multiplication, `/` division, `%` modulo, and `**` exponentiation.

Boolean operators apply only to booleans: `&&` logical AND, `||` logical OR, and `!!` logical NOT, all with short-circuit evaluation.

Utility operators handle special cases: `|` provides fallback values for failed operations, `%` applies template formatting to strings, and `...` acts as a placeholder for unimplemented code.

## Language Syntax

### Tokens and Naming

Valid identifiers in Comp follow Unicode UAX-31 with ASCII hyphens allowed. The preferred style uses lowercase words separated by hyphens (lisp-case), though other styles are permitted when interfacing with external systems.

```comp
valid-name
html5
_internal
用户名
```

### Comments

Line comments use `;` semicolon and continue to the end of the line. There are no block comments. The semicolon style distinguishes comments from other operators and follows Lisp traditions.

```comp
; Main entry point
!main = {
    data -> :process  ; Transform input
}
```

### Whitespace

Whitespace is completely flexible except between statements, where it's required. The language uses no commas, semicolons, or other separators between field definitions or list elements.

```comp
{x=1 y=2 z=3}
{x=1
 y=2
 z=3}
```

Both structures are identical. Indentation uses tabs by convention, but any consistent indentation works.

### Statement Structure

Every statement consists of an optional assignment target followed by a pipeline. Statements are separated by whitespace and execute independently with fresh seeding from the input.

```comp
target = pipeline
pipeline_only
$temp = value -> :transform
```

## Key Features

### Automatic Resource Management

Resources like files and network connections are tracked automatically and released when they go out of scope. Explicit early release is also supported for fine-grained control.

```comp
$file = "/data.txt" -> :file/open
content = $file -> :read
```

The file automatically closes when `$file` leaves scope, eliminating resource leaks without manual bookkeeping.

### Transactions

Transactions coordinate multiple operations that should succeed or fail atomically. Whether updating databases, modifying files, or managing distributed state, transactions ensure consistency.

```comp
!transact $database {
    user -> :insert
    profile -> :update
}
```

If any operation fails, all changes rollback automatically.

### Trail Navigation

Trails provide dynamic path-based navigation through structures. The `/path/` syntax creates trail values that can be stored, passed, and applied to navigate or modify nested data.

```comp
data//users.0.email/              
config//database.host/ = "localhost"
```

Trails are just structures with special syntax support, not a distinct type.

### Store for Mutability

When controlled mutability is needed, Stores provide a safe container for mutable state. All mutations go through explicit operations, maintaining clear boundaries between functional and stateful code.

```comp
$store = :store/new {count=0}
$store -> :update /count/ <- {.. + 1}
current = $store -> :get /count/
```

Data retrieved from stores is immutable, preserving functional programming benefits.

## Next Steps

With these concepts, you're ready to explore Comp's design in depth. Each major feature has a dedicated design document in the `design/` directory:

- `structure.md` - Deep dive into structures and operations
- `function.md` - Function definition and dispatch
- `shape.md` - Shape system and morphing
- `pipeline.md` - Pipeline operations and failure handling
- `module.md` - Module system and imports

Remember that Comp is currently in design phase. These documents describe intended behavior that will guide implementation.