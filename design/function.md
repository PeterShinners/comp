# Functions and Higher-Order Programming

*Design for Comp's function system, dispatch algorithms, and execution model*

## Overview

Functions in Comp transform structures through pipelines of operations. Every function receives a structure as pipeline input and generates a new structure as output. Functions also accept arguments that configure their behavior, maintaining a clear separation between data flow and parameterization.

Functions are references, not values. They cannot be assigned to variables or passed as data, but they can be invoked through pipelines and accept block arguments for higher-order programming patterns. This design choice creates clear boundaries between code and data while enabling powerful composition through blocks.

## Function Definition Fundamentals

Functions are defined with the `func` keyword and specify two shapes: one for pipeline input and one for arguments. The function body transforms the input structure, with fields computed through expressions and pipelines. Control flow operates through function calls with blocks.

The pipeline shape uses Comp's structural typing - any structure with compatible fields can invoke the function. Functions with no input requirements use an empty shape `{}`. Arguments are specified separately, maintaining clear distinction between data and configuration.

```comp
func calculate_area pipeline{shape} args{} = {
    area = $in.width * $in.height
    perimeter = ($in.width + $in.height) * 2
    diagonal = ($in.width ** 2 + $in.height ** 2) ** 0.5
    {area perimeter diagonal}
}

func get_timestamp pipeline{} args{format} = {
    current = (| now/time)
    formatted = (current | format/time $arg.format)
    {current formatted}
}

# Functions automatically morph inputs
({10 20} | calculate_area)        # Positional matching
({height=15 width=25} | calculate_area)  # Named matching
```

Each statement in the function body begins with fresh pipeline input through `$in`. This eliminates verbose field extraction while maintaining explicit data flow when needed.

## Pure Functions and Isolation

Pure functions guarantee deterministic computation without side effects. Defined with `pure`, they receive an empty context and cannot access external resources. This isolation enables compile-time evaluation, safe parallelization, and use in shape constraints or unit definitions.

The distinction between `pure` and `func` is about capability, not syntax. Pure functions can call other functions, but those functions fail immediately if they attempt resource access. This creates a clear boundary between computation and effects.

```comp
pure fibonacci pipeline{n} args{} = {
    ($in | if {$in <= 1} {$in} {
        $var.a = ($in - 1 | fibonacci)
        $var.b = ($in - 2 | fibonacci)
        $var.a + $var.b
    })
}

pure validate_email pipeline{email} args{} = {
    $in | match/str "^[^@]+@[^@]+$"
}

# Pure functions work at compile time
shape User = {
    email ~str {validate=|validate_email}
    cache_key = (| generate_key)    # Computed at compile time if pure
}

# Regular function with effects
func save_user pipeline{user} args{} = {
    validated = ($in | validate_email)    # Can call pure function
    (Saving ${$in.email} | log)          # Side effect - needs permissions
    ($in | insert/database)
}
```

## Shape-Based Dispatch

Functions use structural shapes to match incoming data, enabling multiple implementations with the same name. When multiple functions match, the most specific one is selected using lexicographic scoring that considers named field matches, tag specificity, assignment strength, and positional matches.

The dispatch scoring creates a total order over function implementations. Named field matches score highest, followed by tag depth in hierarchies. Assignment operators (`=`, `*=`, `?=`) break ties when shapes are otherwise identical. This deterministic selection enables predictable polymorphic behavior.

```comp
func render pipeline{point} args{} = 2D point
func render pipeline{point} *= default 2D  # Strong assignment
func render pipeline{x y z} args{} = 3D point

({x=5 y=10} | render)           # "default 2D" - strong assignment wins
({x=5 y=10 z=15} | render)      # "3D point" - more specific shape
({5 10} | render)               # "default 2D" - positional matching

# Tag-based dispatch with hierarchical scoring
func process pipeline{status} args{} = generic status
func process pipeline{status #error} args{} = error handler
func process pipeline{status #network.error} args{} = network specialist

({status=#timeout.error} | process)  # "error handler"
({status=#network.error} | process)  # "network specialist"
```

## Blocks and Higher-Order Patterns

Blocks are deferred structure definitions passed as arguments to functions, enabling higher-order programming patterns. Functions specify block arguments in their args shape, with optional type specifications and default implementations. Functions invoke their blocks as needed, controlling evaluation context and frequency.

Block arguments are just another argument type in the args shape. Blocks capture their definition context, allowing them to reference local variables and namespace values.

```comp
func with_retry pipeline{operation} args{on_error} = {
    $var.attempts = 0
    ($in | while {$var.attempts < 3} {
        $var.result = ($in | operation |? {
            $var.attempts = $var.attempts + 1
            ($in | if {$var.attempts >= 3} {$in} {#skip})
        })
    })
    $var.result
}

# Usage with blocks as arguments
(data | with_retry operation=|risky_network_call on_error=|log_error)

func process_batch pipeline{items} args{transform validate on_success} = {
    $in | map transform
        | filter validate
        | each {$in | on_success}
}

# Complex control flow with blocks
(items | process_batch 
    transform={$in | enhance | normalize}
    validate={.score > .threshold}
    on_success={$in | save_to_database})
```

## Polymorphic Tag Dispatch

Tags enable sophisticated polymorphic dispatch across module boundaries. When a tag field is used for dispatch, the function is resolved based on the tag's hierarchy. This creates extensible polymorphism without inheritance.

The tag dispatch examines the tag value, determines its hierarchy, and finds the most specific function implementation. For explicit parent calls, partial tag paths enable controlled polymorphic chains.

```comp
# Base module defines animal behaviors
tag animal = {#mammal #bird #reptile}
func speak pipeline{type} args{} = generic animal sound
func speak pipeline{type #mammal} args{} = mammalian vocalization
func speak pipeline{type #bird} args{} = chirp

# Extended module adds specializations
tag animal += {#dog.mammal #cat.mammal}
func speak pipeline{type #dog.mammal} args{} = woof

# Polymorphic dispatch
({type=#bird} | speak)          # "chirp"
({type=#dog.mammal} | speak)    # "woof"

# Cross-module polymorphism
creature = {type=#dog.mammal name=Rex}
(creature | process_animal/external)   # External module handles extended tag
```

## Lazy Functions and Deferred Execution

Functions can define lazy structures using `[]` brackets instead of `{}`. These create generators where fields compute on demand. Once computed, values are cached, making lazy structures eventually behave like regular structures. This enables efficient partial evaluation and infinite structures.

```comp
func infinite_sequence pipeline{} args{start step} = [
    ($in | count | map {$arg.start + $in * $arg.step})
]

func expensive_analysis pipeline{data} args{} = [
    summary = ($in | compute_summary)
    statistics = ($in | deep_statistical_analysis)
    visualization = ($in | generate_charts)
    report = (| compile_full_report)
]

# Only computes what's needed
analysis = (data | expensive_analysis)
quick_view = analysis.summary    # Only computes summary
full = analysis ~ {summary statistics}  # Computes two fields
```

## Function Permissions and Security

Functions can declare required permissions using the `require` keyword. This creates compile-time documentation and enables early failure with clear error messages. The permission system uses capability tokens that flow through the context but cannot be stored or manipulated as values.

Pure functions implicitly drop all permissions, ensuring they cannot perform side effects. Regular functions inherit the caller's permissions unless explicitly restricted. The security model enables fine-grained control over resource access.

```comp
require read, write
func backup_database pipeline{} args{source dest} = {
    ($arg.source | read/file)      # Needs read permission
    | compress
    | write/file $arg.dest         # Needs write permission
}

# Permissions flow through calls
func admin_operation pipeline{} args{} = {
    (| backup_database)          # Inherits admin's permissions
    
    # Temporarily drop permissions for untrusted code
    untrusted_input = ($in | process_user_data)  # Isolated execution
}
```

## Function Composition and Pipelines

Functions compose naturally through pipelines, with each function's output becoming the next function's input. The `$in` reference resets at each statement boundary, enabling elegant parallel processing and analysis patterns.

```comp
func comprehensive_analysis pipeline{data} args{} = {
    # All three operate on input independently
    metrics = $in | calculate_metrics
    patterns = $in | identify_patterns
    anomalies = $in | detect_anomalies
    
    # Combine results
    {metrics patterns anomalies
     summary=(| generate_summary data={metrics patterns anomalies})}
}

func pipeline_composition pipeline{raw_input} args{} = {
    # Functions naturally chain
    $in | validate
        | normalize 
        | enhance config=.enhancement_config
        | transform
        | optimize
}
```

## Performance Considerations

Function dispatch can be optimized through caching. The runtime maintains dispatch caches for frequently-called functions, avoiding repeated shape matching. Pure functions enable additional optimizations - their results can be memoized, they can be evaluated at compile time for constant inputs, and they can be safely parallelized.

```comp
# Compile-time evaluation
pure factorial pipeline{n} args{} = {
    $in | if {$in <= 1} {1} {$in * ($in - 1 | factorial)}
}

# This evaluates at compile time
constant = (10 | factorial)    # 3628800 computed during compilation

# Dispatch cache example
(users | map {$in | process})  # Dispatch resolved once, cached for loop
```

## Design Principles

The function system embodies several core principles that guide its design. Functions as transformations means every function is fundamentally a structure-to-structure mapping. Structural dispatch enables polymorphism through shapes rather than classes. Explicit effects through permissions make side effects visible and controllable. Composition over inheritance creates flexible systems through function and block combinations. Deterministic selection ensures predictable behavior in polymorphic scenarios.

These principles create a function system that balances power with simplicity. Whether building simple data transformations or complex polymorphic systems, functions provide consistent, composable abstractions for computation.