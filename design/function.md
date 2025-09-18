# Functions and Higher-Order Programming

*Design for Comp's function system, dispatch algorithms, and execution model*

## Overview

Functions in Comp transform structures through pipelines of operations. Every function receives a structure as input and generates a new structure as output. This uniform approach means functions compose naturally - the output of one function flows seamlessly as input to another.

Functions are references, not values. They cannot be assigned to variables or passed as data, but they can be invoked through pipelines and accept block arguments for higher-order programming patterns. This design choice creates clear boundaries between code and data while enabling powerful composition through blocks.

## Function Definition Fundamentals

Functions are defined with the `!func` operator and require a shape specification that describes their expected input structure. The function body is essentially a deferred structure definition - fields can be computed through expressions and pipelines, temporaries can be created and referenced, and control flow operates through function calls with blocks.

The shape specification uses Comp's structural typing - any structure with compatible fields can invoke the function. Functions with no input requirements use the explicit `~nil` shape. The return type is determined at runtime based on the actual computation.

```comp
!func :calculate_area ~{width ~num height ~num} = {
    area = width * height
    perimeter = (width + height) * 2
    diagonal = (width ** 2 + height ** 2) ** 0.5
}

!func :get_timestamp ~nil = {
    current = :time/now
    formatted = current % "ISO8601"
}

; Functions automatically morph inputs
{10 20} -> :calculate_area        ; Positional matching
{height=15 width=25} -> :calculate_area  ; Named matching
```

Function bodies benefit from statement seeding - each statement implicitly begins with `.. ->` to access the input structure. This eliminates verbose field extraction while maintaining explicit data flow when needed.

## Pure Functions and Isolation

Pure functions guarantee deterministic computation without side effects. Defined with `!pure`, they receive an empty context (`!ctx`) and cannot access external resources. This isolation enables compile-time evaluation, safe parallelization, and use in shape constraints or unit definitions.

The distinction between `!pure` and `!func` is about capability, not syntax. Pure functions can call other functions, but those functions fail immediately if they attempt resource access. This creates a clear boundary between computation and effects.

```comp
!pure :fibonacci ~{n ~num} = {
    :if .{n <= 1} .{n} .{
        a = :fibonacci {n=(n - 1)}
        b = :fibonacci {n=(n - 2)}
        a + b
    }
}

!pure :validate_email ~{email ~str} = {
    email -> :str/match "^[^@]+@[^@]+$"
}

; Pure functions work at compile time
!shape ~User = {
    email ~str {validate=:validate_email}
    cache_key = :generate_key     ; Computed at compile time if pure
}

; Regular function with effects
!func :save_user ~User = {
    validated = :validate_email    ; Can call pure function
    "Saving ${email}" -> :log      ; Side effect - needs permissions
    .. -> :database/insert
}
```

## Shape-Based Dispatch

Functions use structural shapes to match incoming data, enabling multiple implementations with the same name. When multiple functions match, the most specific one is selected using lexicographic scoring that considers named field matches, tag specificity, assignment strength, and positional matches.

The dispatch scoring creates a total order over function implementations. Named field matches score highest, followed by tag depth in hierarchies. Assignment operators (`=`, `*=`, `?=`) break ties when shapes are otherwise identical. This deterministic selection enables predictable polymorphic behavior.

```comp
!func :render ~{x ~num y ~num} = "2D point"
!func :render ~{x ~num y ~num} *= "default 2D"  ; Strong assignment
!func :render ~{x ~num y ~num z ~num} = "3D point"

{x=5 y=10} -> :render           ; "default 2D" - strong assignment wins
{x=5 y=10 z=15} -> :render      ; "3D point" - more specific shape
{5 10} -> :render                ; "default 2D" - positional matching

; Tag-based dispatch with hierarchical scoring
!func :process ~{status #status} = "generic status"
!func :process ~{status #status#error} = "error handler"
!func :process ~{status #status#error#network} = "network specialist"

{status=#status#error#timeout} -> :process  ; "error handler"
{status=#status#error#network} -> :process  ; "network specialist"
```

## Blocks and Higher-Order Patterns

Blocks are deferred structure definitions passed to functions, enabling higher-order programming patterns. Each block is defined with a dot-prefixed name after the function definition, specifying its expected input shape and optional default implementation. Functions invoke their blocks as needed, controlling evaluation context and frequency.

Block names follow field naming rules - tokens and tags can be used directly, strings require quotes, and expressions use single quotes. A single unnamed block uses `.` in invocation but `.block` in definition. Blocks capture their definition context, allowing them to reference local variables and namespace values.

```comp
!func :with_retry ~{operation} = {
    attempts = 0
    :while .{attempts < 3} .{
        result = .operation !> {
            attempts = attempts + 1
            :if .{attempts >= 3} .{..} .{#skip}
        }
    }
    result
}
.operation ~{} = {#fail message="No operation provided"}

; Usage with named blocks
data -> :with_retry .operation{:risky_network_call}

!func :process_batch ~{items} = {
    items -> :map .transform
         -> :filter .validate
         -> :each .{.. -> .on_success}
}
.transform ~{} = {..}          ; Identity default
.validate ~{} = {#true}        ; Accept all default
.on_success ~{item} = {}       ; No-op default

; Complex control flow with blocks
items -> :process_batch
    .transform{:enhance -> :normalize}
    .validate{score > threshold}
    .on_success{:save_to_database}
```

## Polymorphic Tag Dispatch

Tags enable sophisticated polymorphic dispatch across module boundaries. When a tag field is invoked with a function reference using `#` syntax, the function is resolved based on the tag's origin module and hierarchy. This creates extensible polymorphism without inheritance.

The syntax `fieldname#:function` examines the tag in `fieldname`, determines its defining module, and finds the most specific function implementation. For explicit parent calls, `fieldname#parent_tag:function` temporarily masks the tag for dispatch, enabling controlled polymorphic chains.

```comp
; Base module defines animal behaviors
!tag #animal = {#mammal #bird #reptile}
!func :speak ~{type #animal} = "generic animal sound"
!func :speak ~{type #animal#mammal} = "mammalian vocalization"
!func :speak ~{type #animal#bird} = "chirp"

; Extended module adds specializations
!tag #animal#mammal += {#dog #cat}
!func :speak ~{type #animal#mammal#dog} = "woof"

; Polymorphic dispatch
{type=#animal#bird} -> :type#:speak          ; "chirp"
{type=#animal#mammal#dog} -> :type#:speak    ; "woof"
{type=#animal#mammal#dog} -> :type#mammal:speak  ; "mammalian vocalization"

; Cross-module polymorphism
creature = {type=#animal#mammal#dog name="Rex"}
creature -> external:process_animal   ; External module handles extended tag
```

## Lazy Functions and Deferred Execution

Functions can define lazy structures using `[]` brackets instead of `{}`. These create generators where fields compute on demand. Once computed, values are cached, making lazy structures eventually behave like regular structures. This enables efficient partial evaluation and infinite structures.

```comp
!func :infinite_sequence ~{start ~num step ~num} = [
    :count -> :map .{start + .. * step}
]

!func :expensive_analysis ~{data} = [
    summary = data -> :compute_summary
    statistics = data -> :deep_statistical_analysis
    visualization = data -> :generate_charts
    report = :compile_full_report
]

; Only computes what's needed
analysis = data -> :expensive_analysis
quick_view = analysis.summary    ; Only computes summary
full = analysis ~ {summary statistics}  ; Computes two fields
```

## Function Permissions and Security

Functions can declare required permissions using the `!require` operator. This creates compile-time documentation and enables early failure with clear error messages. The permission system uses capability tokens that flow through the context but cannot be stored or manipulated as values.

Pure functions implicitly drop all permissions, ensuring they cannot perform side effects. Regular functions inherit the caller's permissions unless explicitly restricted. The security model enables fine-grained control over resource access.

```comp
!require read, write
!func :backup_database ~{source ~str dest ~str} = {
    source -> :file/read      ; Needs read permission
    -> :compress
    -> :file/write dest       ; Needs write permission
}

; Permissions flow through calls
!func :admin_operation = {
    :backup_database          ; Inherits admin's permissions
    
    ; Temporarily drop permissions
    untrusted_input -> ^(:process_user_data)  ; Isolated execution
}
```

## Function Composition and Pipelines

Functions compose naturally through pipelines, with each function's output becoming the next function's input. Statement seeding means functions can operate on the same input independently, then combine results. This pattern enables elegant parallel processing and analysis.

```comp
!func :comprehensive_analysis ~{data} = {
    ; All three operate on input independently via seeding
    metrics = :calculate_metrics
    patterns = :identify_patterns
    anomalies = :detect_anomalies
    
    ; Combine results
    {metrics patterns anomalies
     summary = :generate_summary {metrics patterns anomalies}}
}

!func :pipeline_composition = {
    ; Functions naturally chain
    raw_input 
    -> :validate
    -> :normalize 
    -> :enhance {config=enhancement_config}
    -> :transform
    -> :optimize
}
```

## Performance Considerations

Function dispatch can be optimized through caching. The runtime maintains dispatch caches for frequently-called functions, avoiding repeated shape matching. Pure functions enable additional optimizations - their results can be memoized, they can be evaluated at compile time for constant inputs, and they can be safely parallelized.

```comp
; Compile-time evaluation
!pure :factorial ~{n ~num} = {
    :if .{n <= 1} .{1} .{n * :factorial {n=(n - 1)}}
}

; This evaluates at compile time
constant = :factorial {n=10}    ; 3628800 computed during compilation

; Dispatch cache example
users -> :map .{
    :process      ; Dispatch resolved once, cached for loop
}
```

## Design Principles

The function system embodies several core principles that guide its design. Functions as transformations means every function is fundamentally a structure-to-structure mapping. Structural dispatch enables polymorphism through shapes rather than classes. Explicit effects through permissions make side effects visible and controllable. Composition over inheritance creates flexible systems through function and block combinations. Deterministic selection ensures predictable behavior in polymorphic scenarios.

These principles create a function system that balances power with simplicity. Whether building simple data transformations or complex polymorphic systems, functions provide consistent, composable abstractions for computation.