# Comp Language Specification

*Detailed technical specification for the Comp programming language*

## Overview

Comp is a programming language based on **shape-based data flow through chained pipelines**. All data is treated as immutable structures that flow through transformation functions using left-to-right pipeline operators.

### Core Philosophy

Everything in Comp is data transformation through pipelines. Structures cannot be modified in place - instead, new structures are created using spread operators and field assignments. The language treats SQL results, JSON objects, function returns, and literals identically through a uniform data model.

### Syntax Principles

- Whitespace is optional everywhere in the language, only needed to sparate statements
- Statements can span multiple lines and split on any token
- Multiple statements can be on a single line, separated by whitespace
- Mathematical operators are reserved for number types only
- Comments use `//` syntax only and docstrings are quoted in angle brackets `< >`

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
42                    // Scalar - becomes {42} when passed to functions
{x=1.0 y=2.0}         // Named field struct
{..data order=10}     // Spread existing struct with modifications
{"north" "south" "east" "west"}  // Unnamed field struct (array-like)
```

### Shape Definitions

Shapes define the expected structure and types of data:

```comp
!shape Point = {x ~number y ~number z ~number}
!shape User = {
    name ~string 
    age ~number 
    active ~bool = true  // Default value
}
```

### Shape-Based Compatibility

Functions accept any data containing the required structure. Extra fields are ignored, enabling flexible data transformation:

```comp
# Function expects {name ~string}
process_user = {data -> "Hello ${data.name}"}

# All compatible:
{name="Alice"} -> process_user                 // Exact match
{name="Bob" age=30} -> process_user            // Extra fields ignored  
{name="Charlie" role="admin"} -> process_user  // Shape compatible
```

### Type System with Tildes

Type annotations use tildes to connect fields with their types:

```comp
!shape Rectangle = {width ~number height ~number color ~string}
!func area ~Rectangle = {width * height}

# Type validation in pipelines
user_data ~User -> validate -> save
value ~string -> display
complex_shape ~module~ComplexType -> process
```

## Pipeline Operators

Functions are invoked by invoking a function on a structure. Following functions
and structure operations modify the input structure to create new ones. This
constructs a linear chain of operations into a pipeline.

### Invoke (`->`)

This fundamental operator is used to transform one structure into another, either
through invoking a function or applying a structure construction statement.

```comp
data -> :local_function        // Local function reference
data -> :module:function_name  // Imported function
data -> {result=status}        // Create new structure from incoming fields
```

### Iteration Pipeline (`=>`)

The unnamed fields of a structure can be iterated with the low level `=>`
operator. This invokes the expression for each value in the structure.
When complete the results of each iteration are combined back into an
array structure with no named fields.

When the iteration operator is invoked, it is given a simple structure
that that contains the value.

This is instended to be a low level operator. The language library provides 
more convenient and high level iterations that build on this. Those can do 
filtering, accumulation and track progress.

```comp
users => {user.name}           // Array of names from array of users
transactions => commit         // Call method on individual values
```

The iteration block can return special control tokens like 
`#loop#skip` or `#loop#break`. The standard library provides higher-level 
iteration with indexing and accumulation.

### Conditional Pipeline (`?|`)

This operator is provided three statements. The first is a condition that is
evaluated as either true or false. This is followed by a true statement
and a false statement. This will invoke one those blocks depending on the
condition. All three blocks are always required.

The condition statement goes before the question mark and the pipe character separates
the two 

Executes exactly one of two code branches based on a boolean condition. 
Both branches must be provided, though one can be empty for no-op behavior.

This is instended to be a low level operator. The language library provides 
more convenient and high level conditionals that build on this. Those can do 
do matching on more than two cases, provide other fallbacks, and allow
structuring the code into more readable blocks.

```comp
age >= 18 ? #ticket#adult | #ticket#child
condition ? {data -> transform} | {}  // Empty block for no-op
```

### Failure Handling Pipeline (`!>`)

When an incoming structure represents a failure, all other pipeline operators
are skipped, and the failure value is propogated past them. Using this
error invokation allows getting the error condition. This statement can
provide a fallback value for error recovery, generate a new failure that is
with better explenations, or pass through the incoming failure structure
to continue propogating the failure.

```comp
risky_operation -> process_data 
!> {error -> error.log("Failed: ${message}") -> $fallback_value}
```

## Built-in Types

Comp provides a minimal set of built-in types that form the foundation for 
all data manipulation. Complex types are built using shapes and structures 
rather than additional primitives. 

### Number Type

A unified type that eliminates the common problems of integer overflow, 
division truncation, and floating-point precision errors. Mathematical 
operations always produce mathematically correct results.

```comp
10 / 3        # Always 3.333..., never truncates
1000000000000000000 + 1  # Always exact, no overflow
price * quantity  # No type juggling needed
```

### String Type

Strings are sequences of unicode characters. This both single character and
empty sequences.

String literals are defined using double quotes. Triple quotes can be used
to define multiline strings, and simplify escaping of internal quote characters.

Strings can also be invoked to perform template expansion. See the 
Invoked Values section on how this can be customized for strings, or any
type of value.

Numeric operators do not work on strings. Use the library `string` to
manipulate and query string data.

```comp
name = "Peter"
template = "Hello ${name}"
greet = $name -> $template  
loud = $greet -> :string:uppercase
// Results in "HELLO PETER"

# Triple quotes for multiline and embedded quotes
sql_query = """
    SELECT users.name, profiles.bio
    FROM users 
    WHERE users.active = true
"""

```

### Boolean Type

Standard true/false values for logical operations and conditional flow control.

```comp
active = true
condition = user.age >= 18
verified ~bool -> process
```

### Buffer Type

Raw binary data for system interaction, file I/O, and interfacing with 
external libraries that expect byte arrays.

This concept is still mostly undefined, but likely represents the only
mutable data type in the language.

```comp
image_data ~buffer -> compress
file_content -> buffer.decode("utf8")
```

### Resources

Resources represent an object that is outside the control of the language
itself. This can be things like system file handles, network sockets, or
random number generators.

Operating on resources is always non-determistic. Any call could fail at
any time.

Resources also require cleanup. References to resources are carefully tracked
and automatically released when no longer needed. There are operators to
explcitly release and uninitialize resources even while they are still accessible.

## Functions and Shapes

Functions in Comp are pure transformations that take an input structure and produce an output structure. They cannot have side effects except through explicit context modification.

### Function Definitions

Functions are defined statically at the top level of the module.
Each function defines a name and type of structure it can be invoked on.

Some functions require no input argument, and can omit the type specification.

A function is just a deferred block to create a structure. It can contain
private local variables, but any attributes it yields become part of the
outgoing structure.


```comp
!func greet ~{name ~string} = {
    "Hello ${name}!"
}

!func length ~{x ~number y ~number} = {
    $squared = x * x + y * y
    $squared -> math.squareroot
}
```

### Function Calls and Module References

A module defines a flat namespace of functions. These are referenced by 
prefixing the function name with a colon, like `:decode`. Functions from other
modules are are also prefixed with a colon but use the qualified name, like
`:math:absolute` or `:string:lowercase`

Functions are defined using the `!func` operator.

Functions are mostly invoked through one of the pipeline operators, like `->`.
If a function requires no argument it can be used at the start of a function
pipeline as a shorthand for passing an empty structure `{} -> :begin`.

```comp
# Local function calls
data -> :validate_input -> :process_data

# Imported function calls  
data -> :io:print
config -> :json:stringify -> :file:write("/config.json")

# No argument functions can start pipeline chains
:initialize_system -> :load_config -> :start_services
```

### Dynamic Dispatch

Multiple functions can be defined with the same name. When this happens
the functions must be defined to use unambiguous shapes. When called the
system will dispatch to the most specific implementation.

```code

!func describe ~number = {"It's a number"}
!func describe ~string = {"It's a string"}

12 -> :describe -> :io:print
```

### Functions with Block Parameters

Functions can define that they accept additional blocks. These blocks are
defined and handled with a special syntax.

When calling a function with blocks, they are appended to the end of the
function name, using a dot prefix to indeicate belonging  to the
function.

Blocks are not executed immediately. The function receives them as an
executable operation that can be invoked as many times as desired, including
never behing called.

This allows functions to create advanced flow control that resembles
the code structure from other development languages, but still fits 
comfortably into the pipeline style of flow control.

A function can define any number of blocks, but it must define the
shape of the incoming argument for each block. Blocks can be optionally
named, and allow being optionally by callers.

(TODO simple example)

Functions can accept blocks as structured parameters:

```comp
!func match ~single cases={
        #status#pending ~single
        #status#completed ~single
        else = {input -> :error("Unhandled case")}  # Default block
    } = {
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

### Nested Blocks for Side Effects

The `nest` function executes code for side effects while preserving the main pipeline data flow. This separates concerns between data transformation and ancillary operations.

```comp
user_data -> nest.{
    $email = data.contact.email
    $timestamp = :time:now
    debug.log("Processing user: ${data.name}")
} -> validate_and_save
```


## Tags 

A module can define a set of static tags at the top level of the module.
The tags work as both a unique value and a unique shape. Tags are defined
with the `!tag` operator and given a name and a structure of valid names.

The same tag name can be defined multiple times. Each definition is merged 
with other definitions and the ordering has no effect.

Tags from the same module are referenced with the hashtag, like `#status#error`.
Tags defined in other modules use the qualified name like `#math#number#float`.

Tags can also define a hierarchy of names. This helps to think of tags
as a classification of types and potential subtypes. These deeper names are
referenced by their fully qualified definition, `#animal#mammal#dog`

```code

!tag shape = {circle square triangle}
!tag shape = {triangle{icosolese equilateral}}
```

A module can also extend the tags from another module by referencing it as
a starting point. This allows it to define new potential values that it knows
about, although the base module will not understand.

When this tag inheritance happens, the tags defined in the original module and 
matching tags in the extension are considered equivalent.

### Tag Definitions

Tags organize related values into hierarchical namespaces that can be extended across modules. They serve as both type discriminators and value enumerations.

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

Functions can be specialized for specific tag values, enabling behavior that 
varies based on data content. The most specific match is always chosen at 
runtime.

Fields in a structure with a tag type help define the shape of the structure.
This allows defining overrides of functions that use differently specified

They can be used as enumerations and then used as values or field names
in structures.

Defined tags from the same module are referenced with a leading hashtag.


Fields can also define the shape of a structure. A structure field that
has one or more fields with a tag type become a way to

Tags enable polymorphic dispatch based on data content rather than traditional
inheritance hierarchies. They provide a flexible way to handle different data 
variants while maintaining type safety.

```comp
!shape Pet = {name ~string breed ~#animal age ~number}

# Polymorphic function implementations
!func speak ~{breed ~#animal#dog} = {pet -> "${pet.name} barks loudly"}
!func speak ~{breed ~#animal#cat} = {pet -> "${pet.name} meows softly"}
!func speak ~{breed ~#animal#bird} = {pet -> "${pet.name} chirps sweetly"}

# Usage - dispatch based on breed field value
my_dog = {name="Rex" breed=#animal#dog age=3}
my_dog -> :speak    # Calls dog implementation
```

### Inheritance with !super

The super mechanism allows specialized implementations to call less specific
specializations for a function with the same name. This uses a special
keyword `!super` to reference the next-most specific match for a specialized
function. 

This requires providing the name of the field that is driving
the tag specialization. It can also be given a specific level of the tag
to skip to more specific specializations.

```comp
!func process ~{emotion ~#emotions#anger} = {
    "Processing anger: ${data.intensity}"
}

!func process ~{emotion ~#emotions#anger#fury} = {
    intensity_check -> !super(emotion)  # Call anger implementation
    -> add_fury_specific_handling
}

# Specific parent targeting
result -> !super(emotion=#emotions#anger)  # Skip intermediate levels
```

## Assignment and Variables

Local variables can be assigned and referenced inside functions. These are
prefixed with `$`, like `$a=2 $b=$a+2`. The only way to access these values
are with this dollar prefix and the values are lost when the function completes.
Unlike all other scopes, these locals do not contribute to field name references.

### Contexts

Assignment operations integrate with pipeline flow, passing the assigned value 
forward in the data stream.

### Basic Assignment

Assignment stores a value in a variable and simultaneously passes that value 
to the next pipeline stage. This enables capture-and-continue patterns common 
in data processing.

```comp
$name = "Alice"          # Assign and pass "Alice" forward
$count = data.length     # Assign length and pass length forward
```

### Pipeline Value Capture

A variable assignment can be made 
The `$in` reference captures the current value flowing through the pipeline 
without interrupting the flow. This enables side-channel data extraction.

This isn't consistently needed, because the fields in this structure contribute
to the active field lookup.

```comp
config_path -> $path = $in -> :io:read_data -> process -> $path -> :fs:delete
```


### Spread Assignment

Spread assignment operators provide efficient ways to update structures with different merging behaviors, eliminating verbose manual field copying.

```comp
# Standard spread assignment
user ..= {verified=true last_login=:time:now}

# Weak assignment - only add new fields
user ..?= {preferences={theme="dark"}}

# Strong assignment - replace entirely
user ..*= {name="Updated Name"}
```

## Field Access and Quoting

Field access uses dot notation with special quoting rules to handle different types of field names. Most identifiers work without quotes, while special cases require explicit quoting.

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

Comp uses explicit variable prefixes to manage different scopes and provide dependency injection. This system enables clean separation between local state, shared context, and global application state.

(Need to define field name lookups use a combined stack of namespaces using
$out -> $in -> $mod and -> $app)

### Context Stack

The context system provides hierarchical dependency injection that flows through pipeline operations. This eliminates explicit parameter passing for cross-cutting concerns like logging and database connections.


```comp
$mod.database.connection = "prod://server"
$mod.logger.level = "DEBUG"

# Context flows through pipelines
data -> process_with_logging -> save_to_database
```

### Application State

Global application state uses explicit `$app` variables to make shared mutable state visible and intentional. This reduces hidden dependencies while providing necessary shared storage.

```comp
$app.current_user = authenticated_user
$app.session_id = session.generate()

# Application state accessible throughout program
current_permissions = $app.current_user.permissions
```

### Thread Safety

Context isolation at thread creation prevents race conditions and unexpected cross-thread modifications. Each thread gets its own copy of the parent's context at spawn time.

```comp
# Main thread context
$mod.processing.mode = "batch"

worker_thread = spawn.{
    # Thread gets copy of parent context
    $mod.processing.mode = "realtime"  # Only affects this thread
    heavy_computation -> results
}

# Main thread context unchanged
```

### Configurable Number Operators

Mathematical operators can be configured by modifying the shared context
at the application or module level (`$app` or `$mod`). 

This allows controlling integer truncation, overflow handling, and other
details.

```comp
$mod.number.epsilon = 1e-9        # Equality comparison tolerance
$mod.number.precision = 28        # Decimal precision
$mod.number.rounding = math.half_up  # Rounding method
$mod.number.int = math.round       # Fractional to integer conversion
```

## Error Handling

Error handling is integrated into pipeline flow rather than exceptions. Errors are special tagged structures that skip normal processing and flow to error handlers.

```comp
# Errors flow through pipelines
file_path -> :io:read !> {error -> "Could not read file: ${error.path}"}
-> :json:parse !> {error -> "Invalid JSON format"}  
-> validate_data !> {error -> "Data validation failed: ${error.details}"}
-> process_successfully
```

## Key Standard Library Functions

The Comp standard library provides essential functions that complement the language's pipeline philosophy.
While designing the examples and features, several notable functions stand out
as worth mentioning to provide an example of how the language is intended
to be used.

**Flow Control:**
- `:nest` - Execute block with side effects while preserving main pipeline flow
- `:match` - Pattern matching with multiple condition blocks  
- `:if` - Conditional execution with then/else blocks
- `:retry` - Retry operations with configurable attempts and backoff
- `:join` - Wait for thread completion and merge results

**Data Transformation:**
- `:filter` - Remove elements that don't match conditions
- `:reduce` - Fold collection into single value with accumulator
- `:take` - Extract first N elements from collection
- `:last` - Get last element from collection

**I/O Operations:**
- `:io:read` - Read data from files, URLs, or streams
- `:io:print` - Display data to console with formatting

**Flow Control Tags:**
User-level flow control is implemented through special tags that can be returned from iteration blocks:
- `#loop#skip` - Skip current iteration and continue to next
- `#loop#break` - Exit iteration loop entirely  

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

## Symbol Reference

**Pipeline and Flow Control:**
- `->` - Basic pipeline operator, passes data to next function
- `=>` - Iteration pipeline, applies function to each element in collection
- `?` and `|` - Ternary conditional operators for branching (`condition ? true_block | false_block`)
- `!>` - Failure handling operator, catches and processes error structures

**Type and Shape System:**
- `~` - Type annotation separator (`field ~type`)
- `~module~Shape` - Shape references  
- `#tag#value` - Tag references and hierarchical tag values
- `" "` - Quoting to create string literals
- `""" """` - Quoting for multiline string literals
- `' '` - Single quote to use an expression or value as field name

**Function and Module System:**
- `:module:function` - Function references
- `@` - Value invocation attachment (`string@formatter`)

**Language Keywords:**
- `!func` - Function definition
- `!shape` - Shape/type definition  
- `!tag` - Tag enumeration definition
- `!entry` - Module entry point function definition
- `!super` - Call parent implementation in tag hierarchy
- `!delete` - Use with assignment to remove fields

**Field access and assignment:**
- `=` - assign to value
- `*=` - strong assignment (assigns and protects)
- `?=` - weak assignment (ignore if already defined)
- `..value` - spread assignment inside a block
- `..*value` - strong spread, as if each field was strong assigned
- `..?value` - weak spread, as if each field as weak assigned
- `..=` - shorthand for spread assigning a value to itself with changes
- `..*=` - shorthand for strong spread assigning a value to itself with changes
- `..?=` - shorthand for weak spread assigning a value to itself with changes

**Mathematical operators:**
- `+` `-` `/` `*` - Only for basic number types, follows Python's definitions
- `()` - Parenthesis to control operator priority

**Informational:**
- `//` - Line comment until end of current line
- `< >` - Inline docstring
- `<<< >>>` - Multiline docstring

---

*This specification defines the core Comp language features for implementation. The language prioritizes mathematical correctness, pipeline clarity, and shape-based flexibility while maintaining strong static analysis capabilities.*