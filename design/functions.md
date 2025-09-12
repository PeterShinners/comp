# Functions

*Design for Comp's function system, dispatch algorithms, and execution model*

## Overview

Any structure definition comp contains a fully executable language; fields can
be defined by expressions and pipelines, temporary values can be created and
referenced. Flow control and error handling are regular parts of these
operations.

A function defines a structure like this that is not immediately invoked. The
function is given a name that becomes part of the module namespace, and defines
a shape which defines the input shape that work like arguments.

Functions in comp are always prefixed with a `:` colon. They are not
referenceable values, but this is no limitation. Structures have their own lazy
evaluation syntaxes which work much like an anonymous function.

Functions can also be invoked with special blocks which are another form of
unexecuted structures under the control of the defining function.

A function takes an input structure, matched by the the definition of the
function's shape. The function generates a structure result, but it's type is
arbitrary and determined at runtime.

Functions are invoked by passing them to a pipeline operator, like `->`.

## Definition Basics

Functions are defined with the `!func` operator. They must define a name,
a shape, and an optional definition for blocks.

The shape can refer to defined shape, or be defined inline. Remember that
shapes can define types, defaults, and documentation for each field.

The fields that make up the input structure become available to use as
undecorated field names.

Some functions require no input arguments. These use an explicit 
`~nil` in their definition.

```comp
!func :loud-name ~data-with-name = {
    name -> :str:upper
}

!func :current-favorite = {
    70 * 7
}

!func :process ~{data settings=~web~request-settings} = {
    // data uses the first positional argument in the structure
    $clean = data -> :validate
    {$clean settings} -> :web:request
}
```

Functions can be defined as private for the current module by using
a `&` suffix on the function name. This suffix is only used on the
function definition, not when referencing or invoking the function.
Only the current module can use these function definitions.

```
!func :secret& ~number = {
    ...
}

$value = :secret  // Only internal module can access
```

### Ordering

Functions are defined as part of the module namespace. Data defined in the
module namespace is declarative. Functions can be referenced anywhere in
the module, regardless of ordering.

```comp
!func :one ~nil = {
    result = 15 * :two   // order independent reference
}

!func :two ~nil = {
    10
}
```

### Locals

As with any structure definition, functions can define and references
using a `$` prefix for function local temporaries. These values are
lost when the function exits.

### Context

The language defines a shared namespace accessed with `!ctx`.
This namespace is managed specially as it is passed down the call chain.
The fields in this namespace are available for any downstream function
to use, assuming they are not overridden by other namespaces like
`!in` and `!out`.

This means a function can define data in the context that is accessable 
to downstream calls.

```comp

!func :begin ~nil = {
    !ctx.server.port = 8000
    !mod.static-data -> :server:run_forever
}
```

## Function Usage

### Pure Functions

There is an alternative operator to define functions using `!pure`. These
work like regular functions but run in a context that cannot access any
external resources. Special features in the language will require they
are used with pure functions, which can be run at compile time.

A pure function is able to call other pure and regular functions. The 
regular functions will fail immediately if they attempt to access external 
resources like file streams or networking.

```comp

// Can be called at compile time where the language needs
!pure :titlecase !{s~str} -> {
    {$start $end} = {s 1} -> str:break
    {$start->:str:uppercase $end->:str:lowercase} -> "${}${}"
}
```

Any code can invoke any function with some or partial permissions revoked.
There is no requirement to use `!pure` to get this functionality. 

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
!pure :fibonacci ~{n ~num} -> ~num = {
    n <= 1 ? n | (:fibonacci {n=(n-1)} + :fibonacci {n=(n-2)})
}

// Can be evaluated at compile time for constant inputs
$fib_10 = 10 -> :fibonacci    // Computed at compile time: 55
```

### Pure vs Regular Functions

```comp
// Regular function - can access resources
!func :load_config ~{path ~str} = {
    // Has caller's permissions and context
    path -> :file:read -> :json:parse
}

// Pure function - isolated execution
!pure :parse_config ~{json_text ~str} = {
    // No permissions, no file access possible
    json_text -> :json:parse -> :validate_structure
}

// Combined usage
config_path -> :load_config -> :parse_config -> :apply_defaults
```

### Lazy Functions

Any structure can be defied as a lazy structure by using `[]` square brackets.
The same is true for function definitions.

```comp

def :procession ~name~str = [
    name -> :preamble
    name -> :ensemble
    $court = name -> :with-friends
    $court -> :participate
    $court -> :disperse
]
```

When this function is executed it returns a structure that has no evaluated
fields. This follows the same rules and restrictions as regular lazy structures.

The function works similar to a generator in other languages. Fields will
be computed on demand as needed. Once a field is known the data ia preserved
and the object works like a regular structure.


## Function Permissions and Security

A function can be decorated to explicitly state it requires additional
permissions before being run. This uses the `!require` operator and is given a
list of the hardcoded permission names built into Comp.

This is never required, because a function can never succeed if it tries to
access resources it has no permissions for.

These decorations are helpful for generating compile time errors and generating
clear information for developer tools.

```comp
!require read network
!func :send-csv ~{path~str where=~server~address} = {
    path -> :read_csv -> {#0 address} -> :server:upload
}
```

To reiterate; if this function did not define the `!require` it would
still fail when invoked without the correct permissions.

### Shape Dispatch

Functions use Comp's shape to morph the current namespace fields into a
single structure the function can use.

There can be multiple functions defined with the same name. These
must use unambigously different shape definitions.

All shape definitions can compute a ranked matching score for
any data. This allows the most specific function definition to
be invoked for any piece of data.

### Function Dispatch Scoring

Functions with the same name use **lexicographic scoring** for dispatch based on shape matching:

**Score Tuple**: `{named_matches, tag_matches, assignment_weight, position_matches}`

```comp
!func :render ~{x, y} = "2D rendering"
!func :render ~{x, y} *= "priority 2D"
!func :render ~{x, y, z} = "3D rendering"

// Dispatch examples
{x=5, y=10} -> :render           // "priority 2D" wins: {2,0,1,0} > {2,0,0,0}
{x=5, y=10, z=15} -> :render     // "3D rendering" wins: {3,0,0,0} > others
{x=5, y=10, extra="data"} -> :render  // "priority 2D": extra fields ignored
```

#### Assignment Weight for Disambiguation

Functions can be created using assignment operators to break ties:
- `*=` **Strong assignment** - Higher priority
- `=` **Normal assignment** - Standard priority
- `?=` **Weak assignment** - Lower priority

This allows explicit control over dispatch precedence when multiple functions would otherwise have identical scores.

### Polymorphic Dispatch with Tags

Shape morphing and matching rank is heavily inluenced by tag fields in
the structure. These are the intended system for dynamic and polymorphic
behavior.

```comp
!tag #animal = {
    mammal = 100 {
        cat = 101 {indoor=#true}
        dog = 102 {loyalty=#true}
        whale = 103 {environment="ocean"}
    }
    bird = 200 {
        penguin = 201 {flight=#false}
        eagle = 202 {flight=#true}
    }
}

// Polymorphic function dispatch with tag values
!func :feed ~{animal #animal} = "Feeding generic animal"
!func :feed ~{animal #animal#mammal} = "Feeding mammal"
!func :feed ~{animal #animal#bird} = "Feeding bird"
!func :feed ~{animal #animal#mammal#cat} = "Feeding cat with special diet"

// Most specific match wins based on tag hierarchy
101 -> :feed    // "Feeding cat with special diet" (most specific)
100 -> :feed    // "Feeding mammal" (parent level)
{type=102} -> :feed  // "Feeding mammal" (dog is mammal)
```

### Tag-Based Parent Calls

The tag dispatch mechanism allows calling parent implementations using field-based syntax, replacing the older `!super` mechanism.

#### Core Parent Call Syntax

```comp
// Normal dispatch - finds implementation based on tag's origin module
data -> :fieldname#:function

// Parent dispatch - explicitly calls parent tag's implementation  
data -> :fieldname#parent_tag:function
```

#### How Tag Dispatch Works

When a tag value is created, it carries metadata about which module defined it. The dispatch syntax uses this to find the correct implementation:

1. **`:fieldname#:function`** - Looks at the tag in `fieldname`, determines its origin module, then finds the most specific `:function` implementation for that shape
2. **`:fieldname#parent_tag:function`** - Temporarily masks the field's tag as `parent_tag` during shape matching, allowing explicit parent implementation calls

#### Complete Tag Dispatch Example

```comp
// base module
!tag #animal = {#mammal #reptile}
!tag #mammal = {#dog #cat}
!func :speak ~{#mammal ...} = "generic mammal sound"
!func :speak ~{#dog ...} = {
    $parent = @in -> :type#mammal:speak  // Explicit parent call
    "woof and ${parent}"
}

// extended module  
!tag #mammal += {#wolf}
!func :speak ~{#wolf ...} = "howl"

// Usage - works across module boundaries
my_pet = {type=#wolf, name="Luna"}
my_pet -> :type#:speak         // "howl" - finds extended:speak
my_pet -> :type#mammal:speak   // "generic mammal sound" - forces parent

### Dynamic Tag-Based Dispatch

The Comp language uses field-based tag dispatch for polymorphic behavior across modules, providing a powerful mechanism for cross-module polymorphism.

#### Core Syntax

```comp
// Normal polymorphic dispatch - finds implementation based on tag's origin module
data -> :fieldname#:function

// Parent dispatch - explicitly calls parent tag's implementation  
data -> :fieldname#parent_tag:function
```

#### How Tag Dispatch Works

When a tag value is created (e.g., `#dog`), it carries metadata about which module defined it. The dispatch syntax uses this to find the correct implementation:

1. **`:fieldname#:function`** - Looks at the tag in `fieldname`, determines its origin module, then finds the most specific `:function` implementation for that shape
2. **`:fieldname#parent_tag:function`** - Temporarily masks the field's tag as `parent_tag` during shape matching, allowing explicit parent implementation calls

#### Tag Dispatch Example

```comp
// base module
!tag #animal = {#mammal #reptile}
!tag #mammal = {#dog #cat}
!func :speak ~{#mammal ...} = "generic mammal sound"
!func :speak ~{#dog ...} = {
    $parent = .in -> :type#mammal:speak  // Explicit parent call
    "woof and ${parent}"
}

// extended module
!tag #mammal += {#wolf}
!func :speak ~{#wolf ...} = "howl"

// Usage - works across module boundaries
my_pet = {type=#wolf name="Luna"}
my_pet -> :type#:speak         // "howl" - finds extended:speak
my_pet -> :type#mammal:speak   // "generic mammal sound" - forces parent
```

#### Key Properties

- **Static module resolution** - The module is determined by the tag's origin, no dynamic searching
- **Dynamic shape matching** - Within the module, finds most specific implementation using the standard specificity tuple scoring
- **Parent-only constraint** - Can only dispatch through actual parents in the tag hierarchy (not siblings)
- **Consistent syntax** - Same mechanism works from inside implementations or external call sites

### Blocks

After the shape definition for a function can come an optional block.
This defines a series of named values that are provided to the language
through the `!block` operator.

The function can choose to invoke the block as many times as desired
with whatever structure. 

Functions can define that they accept additional blocks with specific shapes for each block parameter:

```comp
!func :match ~single cases={
        #status#pending ~single
        #status#completed ~single
        else = {input -> :error("Unhandled case")}  # Default block
    } = {
    input == #status#pending ? {input -> cases.#status#pending}
    | input == #status#completed ? {input -> cases.#status#completed}  
    | {input -> cases.else}
}
```

#### Usage with Dotted Block Syntax

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

#### Nested Blocks for Side Effects

The `:nest` function executes code for side effects while preserving the main pipeline data flow:

```comp
user_data -> :nest.{
    $email = data.contact.email
    $timestamp = :time:now
    debug.log("Processing user: ${data.name}")
} -> validate_and_save
```

#### Block Shape Definitions

Functions can define specific shapes for each block parameter:

```comp
!func :process_list ~{items} blocks={
    handler ~{item} -> ~string        // Block takes item, returns string
    error_handler ~{error} -> ~nil    // Error block takes error, returns nothing
    filter? ~{item} -> ~bool         // Optional filter block
} = {
    filtered_items = items => {
        item -> filter ? {item -> filter} | !true ? item | :skip
    }
    
    filtered_items => {
        item -> handler !> error_handler
    }
}
```

#### Variadic and Optional Block Parameters

Functions can accept variable numbers of blocks using spread syntax:

```comp
!func :url_dispatch ~{parsed_url} blocks={...routes} = {
    // Accepts any number of route blocks
    parsed_url.path -> :match_routes routes
}

!func :data_processor ~{data} blocks={
    validator ~{item} -> ~bool = {item -> :default_validate}  // Default block
    transform ~{item} -> ~item                                // Required block  
    logger? ~{message} -> ~nil                               // Optional block
    ...handlers ~{item, context} -> ~result                  // Variadic handlers
} = {
    data 
    -> :validate_with validator
    -> transform
    -> :log_if_present logger
    -> :apply_handlers handlers
}

To supply blocks to an invoked function, follow the block with a `.` dot with
or without the block name.

The intention is to use blocks as callbacks and defining optional behavior
for functions.

```comp
!func :walk-data ~{data} blocks={transform} = {
    cities => !block.transform
}

// Usage
dataset -> :rank-city-crowds .transform{population -> :math:log}
```

### Function Documentation

Documentation can be attached to functions using the `!doc` operator with string literals that support template operations:

The `!describe` operator accepts a function reference. On functions
this gives information about the function's original name, shape,
block definition, documentation, and more.
```
```comp
!doc = "Processes HTTP requests and returns formatted responses"

!func :api_endpoint ~{request ~HttpRequest} -> ~HttpResponse = {
    request -> :validate -> :process -> :format_response
}

!doc :api_endpoint = """
Additional documentation will be appended in definition order. Using triple
quotes allows multiline information and requires less escaping for quotation
characters.
"""

!describe :api_endpoint
```

The describe structure provides these fields for comprehensive function introspection and tooling support.
* name
* input_shape
* output_shape
* documentation
* module
* permissions


