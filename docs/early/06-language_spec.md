# Comp Language Specification

*Detailed technical specification for the Comp programming language*

## Overview

Comp is a programming language based on **shape-based data flow through chained pipelines**. All data is treated as immutable structures that flow through transformation functions using left-to-right pipeline operators.

### Core Philosophy

Everything in Comp is data transformation through pipelines. Structures cannot be modified in place - instead, new structures are created using spread operators and field assignments. The language treats SQL results, JSON objects, function returns, and literals identically through a uniform data model.

### Syntax Principles

- Whitespace is optional everywhere in the language, only needed to separate statements
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

This is intended to be a low level operator. The language library provides 
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

This is intended to be a low level operator. The language library provides 
more convenient and high level conditionals that build on this. Those can do 
do matching on more than two cases, provide other fallbacks, and allow
structuring the code into more readable blocks.

```comp
age >= 18 ? #ticket#adult | #ticket#child
condition ? {data -> transform} | {}  // Empty block for no-op
```

### Failure Handling Pipeline (`!>`)

When an incoming structure represents a failure, all other pipeline operators
are skipped, and the failure value is propagated past them. Using this
error invocation allows getting the error condition. This statement can
provide a fallback value for error recovery, generate a new failure that is
with better explanations, or pass through the incoming failure structure
to continue propagating the failure.

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

Strings are sequences of unicode characters supporting both single character and empty sequences.

String literals use double quotes for simple strings and triple quotes for multiline strings or strings containing embedded quotes:

```comp
name = "Peter"
message = """He said "Hello there!" and she replied 'Nice to meet you.'"""
sql_query = """
    SELECT users.name, profiles.bio
    FROM users 
    WHERE users.active = true
"""
```

Strings support template expansion with `${}` interpolation that works in both regular and triple-quoted strings:

```comp
template = "Hello ${name}"
html_template = """
    <div class="user">
        <h2>${user.name}</h2>
        <p>${user.bio}</p>
    </div>
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

Operating on resources is always non-deterministic. Any call could fail at
any time.

Resources also require cleanup. References to resources are carefully tracked
and automatically released when no longer needed. There are operators to
explicitly release and uninitialize resources even while they are still accessible.

## Lazy Structs and Evaluation

### Lazy Structs with Square Brackets

Lazy structs use square brackets `[]` instead of curly braces `{}` to create structures where fields are evaluated on-demand rather than immediately. This enables efficient conditional logic and expensive computations that may never be needed.

```comp
# Lazy struct - fields evaluate only when accessed
lazy_data = [
    cheap_field = simple_calculation
    expensive_field = heavy_computation -> complex_analysis
    conditional_field = condition ? expensive_operation | fallback_value
]

# Only evaluates expensive_field when accessed
result = lazy_data.expensive_field
```

### Lazy Function Definitions

Functions can be defined as lazy using square brackets, creating generator-like behavior where the function body executes incrementally:

```comp
!func process_items = [
    setup = initialize_resources
    data = input -> validate
    results = data => {item -> expensive_transform}
    cleanup = resources -> release
    final_result = results -> aggregate
]

# Function executes up to accessed field, then pauses
partial = process_items.setup  # Only runs initialization
complete = process_items.final_result  # Runs everything through to completion
```

### Flow Control in Lazy Structs

Lazy structs support flow control tags to stop evaluation early:

```comp
batch_processor = [
    item1 = process_first_item
    item2 = process_second_item
    should_continue ? continue_processing | #loop#break
    item3 = expensive_final_processing  # Never runs if break triggered
]
```

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

```comp
!func describe ~number = {"It's a number"}
!func describe ~string = {"It's a string"}

12 -> :describe -> :io:print
```

### Functions with Block Parameters

Functions can define that they accept additional blocks. These blocks are
defined and handled with a special syntax.

When calling a function with blocks, they are appended to the end of the
function name, using a dot prefix to indicate belonging to the
function.

Blocks are not executed immediately. The function receives them as an
executable operation that can be invoked as many times as desired, including
never being called.

This allows functions to create advanced flow control that resembles
the code structure from other development languages, but still fits 
comfortably into the pipeline style of flow control.

A function can define any number of blocks, but it must define the
shape of the incoming argument for each block. Blocks can be optionally
named, and allow being optionally by callers.

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

## Tags and Polymorphism

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

```comp
!tag shape = {circle square triangle}
!tag shape = {triangle{isosceles equilateral}}
```

A module can also extend the tags from another module by referencing it as
a starting point. This allows it to define new potential values that it knows
about, although the base module will not understand.

When this tag inheritance happens, the tags defined in the original module and 
matching tags in the extension are considered equivalent.

### Tag Hierarchies

Tags can define hierarchical relationships to create organized classification systems with nested categories:

```comp
# Simple hierarchy - emotions with subcategories
!tag emotions = {
    joy = {happiness, excitement, contentment, bliss}
    anger = {fury, irritation, rage, annoyance}
    fear = {terror, worry, anxiety, dread}
    sadness = {grief, melancholy, disappointment}
}

# Multi-level hierarchy - animals with taxonomic structure  
!tag animals = {
    mammals = {
        carnivores = {dog, cat, bear, lion}
        herbivores = {rabbit, deer, elephant}  
        primates = {human, chimpanzee, gorilla}
    }
    birds = {
        raptors = {eagle, hawk, falcon}
        songbirds = {sparrow, cardinal, robin}
    }
    fish = {sharks, salmon, goldfish}
}

# Using hierarchical tag values
pet_mood = #emotions#joy#happiness
species_type = #animals#mammals#carnivores#dog
```

### Tag Inheritance and Extensions

Tags can extend existing hierarchies from other modules:

```comp
# Extend base emotions with custom categories
!tag workplace_emotions = {
    ..emotions  # Import all base emotions
    professional = {motivated, focused, stressed, overwhelmed}  
    meeting = {engaged, bored, confused, frustrated}
}

# Reference extended hierarchy
current_state = #workplace_emotions#professional#motivated
base_emotion = #workplace_emotions#joy#contentment  # Still accessible
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

## Documentation and Docstrings

Comp provides built-in documentation syntax using angle brackets `< >` that can be attached inline or referenced externally.

### Inline Documentation

```comp
!func greet ~{name ~string} = < Process user greeting > {
    "Hello ${name}!"
}

!shape User = {
    name ~string < Full display name >
    age ~number < Age in years, may be approximate >
    active ~bool = true < Account status flag >
}
```

### Multi-line Documentation

```comp
!func complex_algorithm ~{data ~Dataset} = <<< 
    Advanced data processing algorithm that handles
    large datasets with memory-efficient streaming.
    
    Performance: O(n log n) time, O(1) space
    Requires: data.size > 0
>>> {
    data -> preprocess -> analyze -> results
}
```

### Referenced Documentation

Documentation can be defined separately and attached by reference:

```comp
< User Represents a system user with authentication >
< User.permissions Set of granted access rights >
< User.last_login Timestamp of most recent session >

!shape User = {
    name ~string
    permissions ~{string}
    last_login ~number
}
```

### Documentation Targets

- `< FunctionName Description >` - Function documentation
- `< ShapeName Description >` - Shape documentation  
- `< ShapeName.field Description >` - Field-specific documentation
- `< module:FunctionName Description >` - External function documentation

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

## Context and Scoping

Comp uses explicit variable prefixes to manage different scopes and provide dependency injection. Field name resolution follows a hierarchical lookup chain that provides predictable variable access across function calls.

### Scope Hierarchy and Field Lookup

When resolving field names, Comp searches through scopes in this specific order:

1. **`$out`** - Output context (return values being constructed)
2. **`$in`** - Input context (current pipeline data)  
3. **`$mod`** - Module context (shared module state)
4. **`$app`** - Application context (global application state)

```comp
!func process_user ~{name ~string} = {
    $mod.logger.level = "DEBUG"  # Module-level setting
    $app.current_session = session_id  # Application-level state
    
    # Field lookup searches: $out -> $in -> $mod -> $app
    greeting = "Hello ${name}"  # 'name' found in $in (input data)
    log_level = logger.level    # 'logger.level' found in $mod
    session = current_session   # 'current_session' found in $app
}
```

### Context Modifications and Persistence

Context changes are tied to the currently executing function scope and automatically inherit down to called functions. The scope of modifications depends on the assignment operator used:

```comp
!func setup_environment = {
    # Weak assignment - only sets if not already defined
    $mod.database.timeout ?= 30
    
    # Standard assignment - overwrites for current function scope
    $mod.database.connection = production_url
    
    # Strong assignment - persists beyond current function
    $mod.database.pool_size *= 10
    
    # Call child function - inherits modified context
    result = initialize_database  # Sees all above modifications
}

# After setup_environment completes:
# - timeout and connection revert to previous values  
# - pool_size persists due to strong assignment (*=)
```

### Context Stack Inheritance

Each function call creates a new context frame that inherits from its parent. Changes are visible to child functions but isolated from parent unless using strong assignment:

```comp
!func parent_function = {
    $mod.config.debug = true
    
    child_result = child_function  # Child sees debug=true
    # debug setting reverts after child_function returns
}

!func child_function = {
    $mod.config.verbose *= true  # Persists beyond this function
    debug_enabled = config.debug  # Accesses parent's debug setting
}
```

### Thread Safety and Context Isolation

When creating new threads, each thread receives a copy of the parent's context at spawn time, preventing race conditions:

```comp
!func spawn_workers = {
    $mod.worker.batch_size = 100
    
    # Each worker thread gets independent copy of context
    worker1 = spawn.{
        $mod.worker.batch_size = 50  # Only affects this thread
        heavy_computation
    }
    
    worker2 = spawn.{
        batch_size  # Still sees original value of 100
    }
}
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

## Field Access and Quoting

Field access uses dot notation with special quoting rules to handle different types of field names. Simple identifiers work without quotes, while expressions and complex values require single quotes.

### Field Access Rules

```comp
# String identifiers - no quotes needed
user.profile.name
config.database.timeout

# Tags - no quotes needed (visually distinct with mixed delimiters)
config.#priority.high.handler
status.#workflow.pending.priority

# Variables, expressions, and complex values - quotes required
matrix.'$row'.'$col'.value           # Variables as field names
settings.'(x + y)'.result            # Expressions as field names  
data.'"complex key"'.value           # Strings with special characters
positions.'{x=10 y=20} ~Point'       # Typed structures as field names
```

### Structure Keys with Types

Structures can be used as field keys when explicitly typed. The field remembers the key type for efficient lookup and automatic type conversion:

```comp
# Create typed structure keys
$origin = {x=0 y=0} ~Point
$user_id = :generate_guid

$data = {
    '$origin' = "spawn_point"                    # Variable as typed key
    '{x=10 y=20} ~Point' = "checkpoint_alpha"   # Direct typed structure as key
    '$user_id' = {name="Alice" level=5}         # GUID as key
}

# Lookup with automatic type conversion
location = data.{x=0 y=0}              # Converts to Point type for lookup
location = data.$origin                # Direct variable lookup
user_data = data.(:generate_guid -> existing_id)  # Converts result to Guid type
```

### Key Replacement with Equivalent Types

When creating new structures with spread assignment, keys that convert to the same internal representation will replace existing keys rather than creating duplicates:

```comp
# Original structure with Point2d key
$data = {
    '{x=1 y=1} ~Point2d' = "2d_value"
    other_field = "unchanged"
}

# Spread assignment with Point3d key that represents same coordinate
$data ..= {'{x=1 y=1 z=0} ~Point3d' = "3d_value"}

# Result: Point3d key replaces Point2d key (same coordinate representation)
# $data now contains:
# {
#     '{x=1 y=1 z=0} ~Point3d' = "3d_value"  # Replaced the equivalent Point2d key
#     other_field = "unchanged"               # Preserved from spread
# }

# All lookups that convert to the same representation find the current value
location1 = data.{x=1 y=1}              # Converts to Point3d, finds "3d_value"
location2 = data.{x=1 y=1} ~Point2d     # Point2d converts to Point3d representation
location3 = data.{x=1 y=1 z=0} ~Point3d # Direct match, finds "3d_value"
```

This ensures that structures maintain logical consistency - there is only one value per unique key representation, with the most recent assignment taking precedence through spread operations.

### Library Function Return Types

Library functions should return explicitly typed structures to enable their use as keys:

```comp
!func create_point ~{x ~number y ~number} = {
    {x=x y=y z=0.0} ~Point  # Returns properly typed Point structure
}

!func generate_session_id = {
    random_data -> format_as_guid -> $result ~Guid
}

# Typed returns can be used directly as keys
$session = generate_session_id
$location = create_point{x=5 y=3}
$game_state = {
    '$session' = player_data
    '$location' = {enemies=[] items=["sword"]}
}
```

## Module System and Dependencies

Comp supports both single-file modules (`.comp` extension) and directory-based modules (containing `.coms` files) for organizing code at different scales.

### Module Types

**Single-file modules** contain complete functionality in one `.comp` file:
```
graphics.comp          # Complete graphics utilities module
math-utils.comp        # Mathematical operations module
```

**Directory modules** organize related functionality across multiple `.coms` files:
```
graphics/              # Directory module
├── shapes.coms        # Shape rendering functions
├── transforms.coms    # Transformation utilities
├── rendering.coms     # Core rendering engine
└── colors.coms        # Color manipulation
```

### Package Metadata and Dependencies

Modules define package information and dependencies using `$mod` context variables:

```comp
$mod.package = {
    name = "Graphics Utilities" 
    version = "2.1.3"
    author = "Graphics Team <team@company.com>"
    description = "High-performance 2D and 3D graphics primitives"
    website = "https://github.com/company/graphics"
}

$mod.dependencies = {
    math = "@stdlib/math@2.1/math.comp"
    color = "@company/color-theory@1.4/color.comp"
}
```

### Module Entry Points and Special Behaviors

Modules can define an `!entry` function for initialization logic. The module system guarantees that all regular dependencies complete their `!entry` functions before the current module's `!entry` runs, ensuring a stable foundation for extension and configuration.

```comp
# Standard module (default behavior)
!entry = {
    :log("Module initialized")
}

# Module extending from dependencies with guaranteed order
$mod.dependencies = {
    base_emotions = "@psychology/emotions@1.2/emotions.comp"
}

$mod.entry.features = {#entry.modifies_tags}

!entry = {
    # base_emotions module has completed !entry, so its tags are finalized
    # Safe to extend from stable tag hierarchy
    workplace_emotions.base = ..base_emotions#emotions
    workplace_emotions.professional = {motivated, focused, stressed}
    workplace_emotions.meeting = {engaged, bored, frustrated}
}

# Module with manual dependency control
$mod.entry.features = {#entry.manual_dependencies #entry.modifies_tags}

$mod.dependencies = {
    animals = "@taxonomy/animals@2.1/animals.comp"  # Auto-initialized
}

$mod.manual_dependencies = {
    graphics = "@engines/graphics@4.1/graphics.comp"  # Manual control
}

!entry = {
    # animals module already completed - can safely extend its tags
    local_animals.base = ..animals#creatures
    
    # Initialize manual dependencies conditionally
    $has_gpu = :detect_gpu_capability
    $has_gpu ? :initialize_module("graphics") | {}
    
    # Configure tags based on available capabilities
    local_animals.rendered = $has_gpu ? {dragon, phoenix} | {cat, dog}
}
```

**Entry Feature Flags:**
- `#entry.manual_dependencies` - Module manually initializes some dependencies
- `#entry.modifies_tags` - Module modifies tag hierarchies during initialization
- `#entry.modifies_shapes` - Module modifies shape definitions during initialization
- `#entry.platform_conditional` - Module behavior varies by platform/architecture

### Static Analysis Hints for Dynamic Modules

Modules that modify types or tags during initialization can provide hints to help static analysis tools and IDEs offer better developer experience:

```comp
$mod.entry.features = {#entry.modifies_tags #entry.modifies_shapes}

# Hints for static analysis tools
$mod.entry.hints = {
    # Shape will be similar to existing type after entry completes
    Vector = "~:math:SimpleVector"
    Matrix = "~:math:Matrix3D"
    
    # Tag will have similar hierarchy to existing tag
    "#animal" = "#zoo#animals"
    "#status" = "#workflow#states"
}

!entry = {
    # Actual runtime configuration may differ from hints
    $platform = :detect_platform
    Vector = $platform = "gpu" ? configure_gpu_vector | configure_cpu_vector
    
    # Tag hierarchy based on detected features  
    animal.detected = :scan_available_creatures -> build_hierarchy
}
```

**Benefits of Static Hints:**
- IDEs can provide autocompletion using similar types as templates
- Static analysis tools can catch basic errors without runtime initialization
- Developers get immediate feedback while coding
- Hints serve as documentation of expected runtime behavior
- Tools can warn when hints diverge significantly from actual usage

The hints are advisory only - the actual runtime behavior takes precedence, but the hints provide a reasonable approximation for development-time tooling.

After all `!entry` functions complete, the module system locks down - no further modifications to shapes, tags, or dependencies are allowed, ensuring static analysis tools have complete and stable information.

## Error Handling

Error handling is integrated into pipeline flow rather than exceptions. Errors are special tagged structures that skip normal processing and flow to error handlers.

```comp
# Errors flow through pipelines
file_path -> :io:read !> {error -> "Could not read file: ${error.path}"}
-> :json:parse !> {error -> "Invalid JSON format"}  
-> validate_data !> {error -> "Data validation failed: ${error.details}"}
-> process_successfully
```

## Platform-Specific Variations

Comp supports conditional compilation through platform-specific function and shape definitions, allowing fine-grained customization without separate files for minor variations.

### Platform-Specific Definitions

Functions and shapes can have platform or architecture-specific variants using dotted suffixes:

```comp
# Platform-specific file operations
!func file_open.win32 ~{path ~string} = {
    path -> win32:CreateFile -> handle_to_fd
}

!func file_open.linux ~{path ~string} = {
    path -> posix:open -> validate_fd  
}

!func file_open ~{path ~string} = {  # Generic fallback
    path -> generic:file_system_open
}

# Architecture-specific data layouts
!shape buffer.x64 = {
    data ~buffer 
    size ~number 
    alignment ~number = 8
}

!shape buffer.arm64 = {
    data ~buffer
    size ~number  
    alignment ~number = 4  # Different alignment requirements
}
```

### Selection and Fallback Resolution

The compiler selects the most specific match first, falling back to less specific variants:

1. Most specific: `function.platform.architecture` (e.g., `file_open.linux.arm64`)
2. Platform-specific: `function.platform` (e.g., `file_open.linux`)  
3. Generic fallback: `function` (e.g., `file_open`)

This system allows keeping related platform variants together for easier maintenance while providing clean fallback behavior for unsupported combinations.

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

## Symbol Reference

**Pipeline and Flow Control:**
- `->` - Basic pipeline operator, passes data to next function
- `=>` - Iteration pipeline, applies function to each element in collection
- `?` and `|` - Conditional operators for branching (`condition ? true_block | false_block`) and field access fallback (`field | default_value`)
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
- `=` - assign to value or comparison operator (context-dependent)
- `*=` - strong assignment (persists beyond current scope, acts like `=` for locals)
- `?=` - weak assignment (ignore if already defined)
- `.field = value` - field assignment on structures (creates new immutable structure)
- `.field ?= value` - weak field assignment (only sets if field doesn't exist)
- `.field *= value` - strong field assignment (acts like `=` for local variables)
- `..value` - spread assignment inside a block
- `..*value` - strong spread assignment
- `..?value` - weak spread assignment
- `..=` - shorthand for spread assigning a value to itself with changes
- `..*=` - shorthand for strong spread assigning a value to itself with changes
- `..?=` - shorthand for weak spread assigning a value to itself with changes
- `&label` - reference to pipeline checkpoint label

**Mathematical operators:**
- `+` `-` `/` `*` - Only for basic number types, follows Python's definitions
- `()` - Parenthesis to control operator priority

**Informational:**
- `//` - Line comment until end of current line
- `< >` - Inline docstring
- `<<< >>>` - Multiline docstring

---

*This specification defines the core Comp language features for implementation. The language prioritizes mathematical correctness, pipeline clarity, and shape-based flexibility while maintaining strong static analysis capabilities.*