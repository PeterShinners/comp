# Comp Language Specification v2.0

## Overview

Comp is a programming language designed for data transformation, tool building, and computational workflows. The language emphasizes readability, immutability, and the natural flow of data through processing pipelines.

All data is treated as immutable structures that flow through transformation functions using left-to-right pipeline operators.

## Core Philosophy

Everything in Comp is data transformation through pipelines. Structures cannot be modified in place - instead, new structures are created using spread operators and field assignments. The language treats SQL results, JSON objects, function returns, and literals identically through a uniform data model.

## Syntax Principles

- Whitespace is optional everywhere in the language, only needed to separate statements
- Statements can span multiple lines and split on any token
- Multiple statements can be on a single line, separated by whitespace
- Mathematical operators are reserved for number types only
- Comments use `//` syntax only - no block comments to avoid nesting complexity
- Documentation uses angle brackets `< >`

## Sigil System

```comp
$local_var = 42           // Local variables (function scope)
^temp_var                 // Statement variables (pipeline scope)
@app.config              // Scoped namespaces (context stack)
:function_name           // Function references
~ShapeName              // Shape references  
#tag.variant            // Tag references
name&                   // Private suffix
"text"^html.safe        // Invoke attachment (rare)
!func, !shape, !tag     // Keywords
```

## Core Data Model

### Universal Struct Model

All data in Comp is represented as structs (key-value pairs). Scalars automatically promote to single-element structs when passed to functions expecting structs.

```comp
42                    // Scalar - becomes {42} when passed to functions
{x=1.0 y=2.0}         // Named field struct
{..data order=10}     // Spread existing struct with modifications
{"north" "south" "east" "west"}  // Unnamed field struct (array-like)
```

### Shape Definitions

Shapes define the expected structure and types of data:

```comp
!shape ~Point = {x ~number y ~number z ~number}
!shape ~User = {
    name ~string 
    age ~number 
    active ~bool = true  // Default value
}
```

### Shape-Based Compatibility

Functions accept any data containing the required structure. Extra fields are ignored, enabling flexible data transformation:

```comp
// Function expects {name ~string}
!func :process_user = {data -> "Hello ${data.name}"}

// All compatible:
{name="Alice"} -> :process_user                 // Exact match
{name="Bob" age=30} -> :process_user            // Extra fields ignored  
{name="Charlie" role="admin"} -> :process_user  // Shape compatible
```

### Type System with Tildes

Type annotations use tildes to connect fields with their types:

```comp
!shape ~Rectangle = {width ~number height ~number color ~string}
!func :area ~Rectangle = {width * height}

// Type validation in pipelines
user_data ~User -> :validate -> :save
value ~string -> :display
complex_shape ~module~ComplexType -> :process
```

## Pipeline Operators

Functions are invoked by applying pipeline operators to structures. Each operation creates new structures, forming chains of transformations.

### Invoke (`->`)

Transforms one structure into another through function calls or structure construction:

```comp
data -> :local_function        // Local function reference
data -> :module:function_name  // Imported function
data -> {result=@.status}      // Create new structure from incoming fields
```

### Iteration Pipeline (`=>`)

Iterates over unnamed fields in a structure, applying an expression to each value:

```comp
users => {user.name}           // Array of names from array of users
transactions => :commit        // Call method on individual values
```

The iteration block can return special control tokens like `#loop#skip` or `#loop#break`.

### Conditional Pipeline (`?|`)

Executes one of two code branches based on a boolean condition:

```comp
age >= 18 ?| #ticket#adult | #ticket#child
condition ?| {data -> :transform} | {}  // Empty block for no-op
```

### Failure Handling Pipeline (`!>`)

Handles error conditions and provides failure recovery:

```comp
data -> :risky_operation !> {error="Operation failed", original=@}
input -> :validate !> :default_value
```

### Field Fallback (`|`)

Provides fallback values for undefined fields (not value-based conditionals):

```comp
config.url | "http://default.com" -> :curl:fetch
user.name | "Anonymous" -> :display
settings.timeout | 30 -> :network:configure
```

Note: `|` only triggers when the field doesn't exist, not when the field has a falsy value.

## Failure Propagation

When any pipeline operation (`->`, `=>`) encounters a failure structure as input, all subsequent operations in that pipeline are automatically skipped. This creates consistent error handling across function calls, structure generation, and iteration.

## Privacy System

### Private Definitions

Functions, shapes, and tags can be marked private with `&` suffix, making them accessible only within the defining module:

```comp
!func :helper& = {data -> data.name}  // Private function
!shape ~Config& = {key ~string}      // Private shape
!tag #status& = {pending active}     // Private tag
```

### Private Data Attachment

Each module can attach private data to any structure using `&` syntax:

```comp
// Create structure with private data
$user = {login="pete" email="pete@example.com"}&{session="abc123" id=789}

// Access private data (only in same module)
$user.login          // "pete" - public field
$user&.session       // "abc123" - private field
$user&.id           // 789 - private field
```

### Private Data Inheritance

Private data automatically flows through pipeline operations and full spread operations:

```comp
$user& = {session="abc", token="xyz"}

// Automatic preservation in pipelines
$result = $user -> :transform -> :validate
// $result& = {session="abc", token="xyz"}

// Automatic preservation in full spread
$copy = {...$user extra="field"}
// $copy& = {session="abc", token="xyz"}

// Manual copying when needed
$selective = {name=$user.name}
$selective& = $user&  // Manual private data transfer
```

### Private Data Merging

When structures reference multiple sources, private data merges automatically using first-reference-wins for conflicts:

```comp
$source1& = {token="abc", shared="first"}
$source2& = {cache="xyz", shared="second"}

$merged = {field1=$source1.name, field2=$source2.email}
// $merged& = {token="abc", shared="first", cache="xyz"}
// First reference wins: $source1& merged before $source2&
```

## Variable Scopes and Labels

### Pipeline Labels

Create named variables mid-pipeline that can be referenced later:

```comp
// Function-scoped label (persists until function end)
path -> :fs:open -> !label $fd -> :process_file
// $fd can be used anywhere later in function

// Statement-scoped label (limited to current pipeline)  
data -> :validate -> !label ^clean -> :transform
// ^clean only available until this pipeline ends
```

### Scoped Namespaces

Access different levels of context using `@` prefix:

```comp
@app.config     // Application-level configuration
@mod.state      // Module-level state  
@in.data        // Input context
@out.result     // Output context
```

## Function Definitions

### Basic Function Syntax

```comp
!func :function_name ~InputShape = {
    // Function body - single expression that transforms input
    input -> :some_operation -> {result=@.value}
}

// With return type annotation
!func :calculate ~Point -> ~number = {
    input.x * input.y
}
```

### Higher-Order Functions

Functions can accept other functions as parameters through block syntax:

```comp
!func :process_list ~list blocks={handler} = {
    list => handler
}

// Usage with inline block
data -> :process_list handler={item -> item.name}
```

## Shape System

### Shape Definitions with Constraints

```comp
!shape ~User = {
    name ~string
    age ~number
    emails ~string[]     // Array of strings
    tags ~string[2-4]    // 2 to 4 string elements (syntax needs validation)
}
```

### Shape Inheritance through Tags

```comp
!tag #user = {
    basic = {name ~string}
    admin = {!super name ~string permissions ~string[]}
}
```

## Tag System

### Hierarchical Tags with Inheritance

```comp
!tag #vehicle = {
    car = {wheels=4 engine~string}
    truck = {!super wheels=6 cargo_capacity~number}  // Inherits from car
    motorcycle = {wheels=2 engine~string}
}

// Usage
$my_car = #vehicle.car
$delivery_truck = #vehicle.truck  // Has wheels, engine, and cargo_capacity
```

## Module System

### Module Loading Statements

Explicit module source declaration using keyword operators:

```comp
// Standard library modules
!stdmod math = math
!stdmod io = io/filesystem

// Git repository modules  
!gitmod color = @company/color-theory@1.4/color
!gitmod utils = @github/user/awesome-comp@latest/utils

// Filesystem paths
!diskmod neighbor = deps/thirdparty/suburbia
!diskmod config = ../shared/config

// Search paths
!pathmod plugin = user-extensions
!pathmod theme = custom-theme
```

### Conditional Module Loading

```comp
// Basic implementation with optional override
!stdmod crypto = crypto
!pathmod crypto ?= crypto-hardware   // Override if found

// Platform-specific overrides  
!diskmod jpeg = deps/basicjpeg
!pathmod jpeg ?= turbo-jpeg          // Use optimized version if available
```

### Module Usage

```comp
// Function calls with consistent colon prefixing
result = input 
    -> :math:sqrt 
    -> :color:to_hex 
    -> :io:write
```

## Introspection System

### Object Description

Use `!describe` to get metadata about language objects and runtime values:

```comp
// Language object metadata
!describe :function_name -> docstring -> :io:print
!describe #tag.variant -> children -> :io:print  
!describe ~Shape -> fields -> :debug:dump
!describe @app -> available_scopes -> :io:print

// Runtime value description
!describe 5 -> implementation           // #number.integer
!describe "text" -> encoding           // #string.utf8  
!describe $user -> shape              // ~User or inferred shape
!describe {a=1 b=2} -> field_count    // 2

// Module introspection
!describe module http -> {name=@.name, version=@.version, functions=@.functions}
```

## String System

### String Interpolation

```comp
"Hello ${name}"                    // Basic interpolation
"User: ${user.name} (${user.id})" // Nested field access
```

### Multiline Strings

```comp
"""
This is a multiline string
with ${interpolation} support
and "embedded quotes"
"""
```

### Template Processing

```comp
"Welcome ${user.name}"^html.safe   // Template with invoke handler
```

## Error Handling

### Automatic Failure Propagation

All pipeline operations (`->`, `=>`) automatically skip when input is a failure structure:

```comp
data -> :step1 -> :step2 -> :step3
// If step1 fails, step2 and step3 are automatically skipped
```

### Explicit Failure Handling

```comp
data -> :risky_operation !> {error="Failed", input=@}
result -> :validate !> :use_default_value
```

## Implementation Notes

### Core Language Features
- Basic pipeline operators and struct manipulation
- Structural typing and shape inference  
- Private data attachment system
- Failure propagation and error handling
- Standard library for common operations

### Advanced Features
- Tag system with hierarchical inheritance
- Context stack and dependency injection
- Module loading with conditional overrides
- Introspection and metadata access
- Template processing and string interpolation

### Future Considerations
- Binary buffer types for extension interoperability
- Performance optimizations for large data processing
- Development tooling and debugging support
- Package management and distribution

### Areas Requiring Further Design
- Module dependency sharing between applications and libraries  
- Shape size constraint syntax validation (`[2-4]` notation)
- Platform-specific module loading semantics
- Complex conditional module resolution patterns

---

*This specification defines the core language features and provides implementation guidance for the Comp programming language, emphasizing explicit data transformation through immutable pipeline operations.*