# Functions and Higher-Order Programming

*Design for Comp's function system, dispatch algorithms, and execution model*

## Overview

Functions in Comp transform structures through pipelines of operations. Every function receives a structure as pipeline input and generates a new structure as output. Functions also accept arguments that configure their behavior, maintaining a clear separation between data flow and parameterization.

Functions are references, not values. They cannot be assigned to variables or passed as data, but they can be invoked through pipelines and accept block arguments for higher-order programming patterns. This design choice creates clear boundaries between code and data while enabling powerful composition through blocks.

## Function Definition Fundamentals

Functions are defined with the `!func` keyword followed by the function name (prefixed with `|`), pipeline shape (prefixed with `~`), and optional arguments (prefixed with `^`). The function body transforms the input structure, with fields computed through expressions and pipelines. Control flow operates through function calls with blocks.

The pipeline shape uses Comp's structural typing - any structure with compatible fields can invoke the function. Functions with no input requirements use an empty shape `{}`. Arguments are specified separately, maintaining clear distinction between data and configuration.

```comp
!func |calculate-area ~{width ~num height ~num} = {
    area = width * height
    perimeter = (width + height) * 2
    diagonal = (width ** 2 + height ** 2) ** 0.5
    {area perimeter diagonal}
}

!func |get-timestamp ^{format ~str} = {
    current = (|now/time)
    formatted = (current |format/time ^format)
    {current formatted}
}

; Functions automatically morph inputs
({10 20} |calculate-area)        ; Positional matching
({height=15 width=25} |calculate-area)  ; Named matching
```

Each statement in the function body begins with fresh pipeline input through `$in`. Field references use undecorated tokens that cascade through output being built to input. The implicit return value is the last expression in the function body.

## Function Definition Syntax

Functions can be defined with inline shapes and arguments for simple cases, or with separate shape definitions for complex cases. The inline syntax uses `~` for pipeline shape and `^` for arguments.

```comp
; Simple inline definition
!func |double ~{~num} = { $in * 2 }

!func |add ~{~num} ^{n ~num} = { $in + ^n }

; Multi-line for clarity
!func |filter-items 
    ~{items[]} 
    ^{threshold ~num = 0} = {
    items |filter .{$in > ^threshold}
}

; Complex shapes defined separately
!shape order-data = {
    order ~order
    items ~item[]
    customer ~customer
}

!shape process-config = {
    validate? ~bool = #true
    priority ~tag = #normal
}

!func |process-order ~order-data ^process-config = {
    ; Implementation focuses on logic, not type declarations
    validated = ^validate? |if .{#true} 
        .{order |validate}
        .{order}
    
    processed = validated |apply-priority ^priority
    processed
}
```

For complex functions that need internal shape definitions, they can be placed inside the function body:

```comp
!func |complex-processor = {
    !shape {data ~record options ~config}
    !args {retries ~num = 3}
    
    ; Function implementation
    data |process-with-retries ^retries
}
```

## Pure Functions and Isolation

Pure functions guarantee deterministic computation without side effects. Defined with `!pure`, they receive an empty context and cannot access external resources. This isolation enables compile-time evaluation, safe parallelization, and use in shape constraints or unit definitions.

The distinction between `!pure` and regular functions is about capability, not syntax. Pure functions can call other functions, but those functions fail immediately if they attempt resource access. This creates a clear boundary between computation and effects.

```comp
!pure
!func |fibonacci ~{n ~num} = {
    ($in |if .{$in <= 1} .{$in} .{
        $a = ($in - 1 |fibonacci)
        $b = ($in - 2 |fibonacci)
        $a + $b
    })
}

!pure
!func |validate-email ~{email ~str} = {
    $in |match/str "^[^@]+@[^@]+$"
}

; Pure functions work at compile time
!shape user = {
    email ~str {validate=|validate-email}
    cache-key = (|generate-key)    ; Computed at compile time if pure
}

; Regular function with effects
!func |save-user ~{user} = {
    validated = ($in |validate-email)    ; Can call pure function
    (|log "Saving ${email}")             ; Side effect - needs permissions
    ($in |insert/database)
}
```

## Shape-Based Dispatch

Functions use structural shapes to match incoming data, enabling multiple implementations with the same name. When multiple functions match, the most specific one is selected using lexicographic scoring that considers named field matches, tag specificity, assignment strength, and positional matches.

The dispatch scoring creates a total order over function implementations. Named field matches score highest, followed by tag depth in hierarchies. Assignment operators (`=`, `*=`, `?=`) break ties when shapes are otherwise identical. This deterministic selection enables predictable polymorphic behavior.

```comp
!pipe {point}
!func |render = {2D point}

!pipe {point}
!func |render *= {default 2D}  ; Strong assignment

!pipe {x ~num y ~num z ~num}
!func |render = {3D point}

({x=5 y=10} |render)           ; "default 2D" - strong assignment wins
({x=5 y=10 z=15} |render)      ; "3D point" - more specific shape
({5 10} |render)               ; "default 2D" - positional matching

; Tag-based dispatch with hierarchical scoring
!pipe {status}
!func |process = {generic status}

!pipe {status #error}
!func |process = {error handler}

!pipe {status #network.error}
!func |process = {network specialist}

({status=#timeout.error} |process)  ; "error handler"
({status=#network.error} |process)  ; "network specialist"
```

## Function Overloading and Documentation

When function names are overloaded, the language treats the group of definitions as a single set. They share documentation and appear as a single object during introspection, with multiple implementations differentiated by their shapes. Dispatch is driven solely by pipeline shape - argument shapes don't affect selection.

```comp
!doc "Process different types of data appropriately"

!pipe {data ~user-data}
!doc impl "Saves to primary database"
!func |process = {
    $pipe.data |validate-user |save-user
}

!pipe {data ~system-data}
!doc impl "Archives to time-series store"
!func |process = {
    $pipe.data |validate-system |archive
}

; Single describe shows all implementations
!describe |process
; Returns: {
;   doc: "Process different types of data appropriately"
;   module: current-module
;   implementations: [
;     {pipe: ~user-data, args: {}, impl-doc: "Saves to primary database"},
;     {pipe: ~system-data, args: {}, impl-doc: "Archives to time-series store"}
;   ]
; }
```

Even single-implementation functions follow this pattern internally, maintaining consistency for introspection and future extension.

## Blocks and Higher-Order Patterns

Blocks are deferred structure definitions passed as arguments to functions, enabling higher-order programming patterns. Blocks are prefixed with `.{}` to distinguish them from structure literals. Functions specify block arguments in their args shape, with optional type specifications and default implementations. Functions invoke their blocks as needed, controlling evaluation context and frequency.

Block arguments are determined by the function's arg shape definition. When the parser encounters `.{}` in argument position, it creates a deferred block. Blocks capture their definition context, allowing them to reference local variables and namespace values through the `# Functions and Higher-Order Programming

*Design for Comp's function system, dispatch algorithms, and execution model*

## Overview

Functions in Comp transform structures through pipelines of operations. Every function receives a structure as pipeline input and generates a new structure as output. Functions also accept arguments that configure their behavior, maintaining a clear separation between data flow and parameterization.

Functions are references, not values. They cannot be assigned to variables or passed as data, but they can be invoked through pipelines and accept block arguments for higher-order programming patterns. This design choice creates clear boundaries between code and data while enabling powerful composition through blocks.

## Function Definition Fundamentals

Functions are defined with the `!func` keyword followed by the function name (prefixed with `|`), pipeline shape (prefixed with `~`), and optional arguments (prefixed with `^`). The function body transforms the input structure, with fields computed through expressions and pipelines. Control flow operates through function calls with blocks.

The pipeline shape uses Comp's structural typing - any structure with compatible fields can invoke the function. Functions with no input requirements use an empty shape `{}`. Arguments are specified separately, maintaining clear distinction between data and configuration.

```comp
!func |calculate-area ~{width ~num height ~num} = {
    area = width * height
    perimeter = (width + height) * 2
    diagonal = (width ** 2 + height ** 2) ** 0.5
    {area perimeter diagonal}
}

!func |get-timestamp ^{format ~str} = {
    current = (|now/time)
    formatted = (current |format/time ^format)
    {current formatted}
}

; Functions automatically morph inputs
({10 20} |calculate-area)        ; Positional matching
({height=15 width=25} |calculate-area)  ; Named matching
```

Each statement in the function body begins with fresh pipeline input through `$in`. Field references use undecorated tokens that cascade through output being built to input. The implicit return value is the last expression in the function body.

## Function Definition Syntax

Functions can be defined with inline shapes and arguments for simple cases, or with separate shape definitions for complex cases. The inline syntax uses `~` for pipeline shape and `^` for arguments.

```comp
; Simple inline definition
!func |double ~{~num} = { $in * 2 }

!func |add ~{~num} ^{n ~num} = { $in + ^n }

; Multi-line for clarity
!func |filter-items 
    ~{items[]} 
    ^{threshold ~num = 0} = {
    items |filter .{$in > ^threshold}
}

; Complex shapes defined separately
!shape order-data = {
    order ~order
    items ~item[]
    customer ~customer
}

!shape process-config = {
    validate? ~bool = #true
    priority ~tag = #normal
}

!func |process-order ~order-data ^process-config = {
    ; Implementation focuses on logic, not type declarations
    validated = ^validate? |if .{#true} 
        .{order |validate}
        .{order}
    
    processed = validated |apply-priority ^priority
    processed
}
```

For complex functions that need internal shape definitions, they can be placed inside the function body:

```comp
!func |complex-processor = {
    !shape {data ~record options ~config}
    !args {retries ~num = 3}
    
    ; Function implementation
    data |process-with-retries ^retries
}
```

## Pure Functions and Isolation

Pure functions guarantee deterministic computation without side effects. Defined with `!pure`, they receive an empty context and cannot access external resources. This isolation enables compile-time evaluation, safe parallelization, and use in shape constraints or unit definitions.

The distinction between `!pure` and regular functions is about capability, not syntax. Pure functions can call other functions, but those functions fail immediately if they attempt resource access. This creates a clear boundary between computation and effects.

```comp
!pure
!func |fibonacci ~{n ~num} = {
    ($in |if .{$in <= 1} .{$in} .{
        $a = ($in - 1 |fibonacci)
        $b = ($in - 2 |fibonacci)
        $a + $b
    })
}

!pure
!func |validate-email ~{email ~str} = {
    $in |match/str "^[^@]+@[^@]+$"
}

; Pure functions work at compile time
!shape user = {
    email ~str {validate=|validate-email}
    cache-key = (|generate-key)    ; Computed at compile time if pure
}

; Regular function with effects
!func |save-user ~{user} = {
    validated = ($in |validate-email)    ; Can call pure function
    (|log "Saving ${email}")             ; Side effect - needs permissions
    ($in |insert/database)
}
```

## Shape-Based Dispatch

Functions use structural shapes to match incoming data, enabling multiple implementations with the same name. When multiple functions match, the most specific one is selected using lexicographic scoring that considers named field matches, tag specificity, assignment strength, and positional matches.

The dispatch scoring creates a total order over function implementations. Named field matches score highest, followed by tag depth in hierarchies. Assignment operators (`=`, `*=`, `?=`) break ties when shapes are otherwise identical. This deterministic selection enables predictable polymorphic behavior.

```comp
!pipe {point}
!func |render = {2D point}

!pipe {point}
!func |render *= {default 2D}  ; Strong assignment

!pipe {x ~num y ~num z ~num}
!func |render = {3D point}

({x=5 y=10} |render)           ; "default 2D" - strong assignment wins
({x=5 y=10 z=15} |render)      ; "3D point" - more specific shape
({5 10} |render)               ; "default 2D" - positional matching

; Tag-based dispatch with hierarchical scoring
!pipe {status}
!func |process = {generic status}

!pipe {status #error}
!func |process = {error handler}

!pipe {status #network.error}
!func |process = {network specialist}

({status=#timeout.error} |process)  ; "error handler"
({status=#network.error} |process)  ; "network specialist"
```

## Function Overloading and Documentation

When function names are overloaded, the language treats the group of definitions as a single set. They share documentation and appear as a single object during introspection, with multiple implementations differentiated by their shapes. Dispatch is driven solely by pipeline shape - argument shapes don't affect selection.

```comp
!doc "Process different types of data appropriately"

!pipe {data ~user-data}
!doc impl "Saves to primary database"
!func |process = {
    $pipe.data |validate-user |save-user
}

!pipe {data ~system-data}
!doc impl "Archives to time-series store"
!func |process = {
    $pipe.data |validate-system |archive
}

; Single describe shows all implementations
!describe |process
; Returns: {
;   doc: "Process different types of data appropriately"
;   module: current-module
;   implementations: [
;     {pipe: ~user-data, args: {}, impl-doc: "Saves to primary database"},
;     {pipe: ~system-data, args: {}, impl-doc: "Archives to time-series store"}
;   ]
; }
```

Even single-implementation functions follow this pattern internally, maintaining consistency for introspection and future extension.

 (variables) and `^` (arguments) prefixes.

```comp
!func |with-retry ~{operation} ^{on-error ~block} = {
    $attempts = 0
    ($in |while .{$attempts < 3} .{
        $result = ($in |operation |? .{
            $attempts = $attempts + 1
            ($in |if .{$attempts >= 3} .{$in} .{#skip})
        })
    })
    $result
}

; Usage with blocks as arguments
(data |with-retry on-error.{|log-error})

!func |process-batch ~{items} ^{transform ~block validate ~block on-success ~block} = {
    $in |map ^transform
        |filter ^validate
        |each .{$in |^on-success}
}

; Complex control flow with blocks
(items |process-batch 
    transform.{$in |enhance |normalize}
    validate.{score > threshold}
    on-success.{$in |save-to-database})
```

For functions with multiple unnamed blocks (like control flow), blocks are accessed positionally:

```comp
!func |if ~{} ^{condition ~block ~block ~block} = {
    $in |^condition |if-true
        .{$in |^#1}   ; Then block
        .{$in |^#2}   ; Else block
}

; Clean calling syntax
$in |if .{value > 5} .{value * 2} .{value / 2}
```

## Argument Spreading and Presence-Check

Functions support spread operators for arguments, allowing predefined argument sets to be reused and overridden. The presence-check morphing pattern enables flag-style arguments where unnamed values matching field names set those fields to their "found" value.

```comp
!func |process ^{
    verbose ~bool = #false ?? #true
    debug ~bool = #false ?? #true
    ..rest   ; Collect remaining fields
} = {
    (^verbose |when .{#true} .{
        (|log "Verbose mode enabled")
    })
    ; ^rest contains unmatched fields
}

; Natural calling syntax
(data |process verbose extra=1 more=2)
; Results in: {verbose=#true debug=#false extra=1 more=2}

; With argument spreading
$defaults = {debug}
(data |process ..$defaults verbose)
; Results in: {verbose=#true debug=#true}
```

The `??` operator in shape definitions indicates presence-check fields: left side is the default (field not found), right side is the value when found in unnamed arguments.

## Polymorphic Tag Dispatch

Tags enable sophisticated polymorphic dispatch across module boundaries. When a tag field is used for dispatch, the function is resolved based on the tag's hierarchy. This creates extensible polymorphism without inheritance.

The tag dispatch examines the tag value, determines its hierarchy, and finds the most specific function implementation. For explicit parent calls, partial tag paths enable controlled polymorphic chains.

```comp
; Base module defines animal behaviors
!tag animal = {#mammal #bird #reptile}

!pipe {type}
!func |speak = {generic animal sound}

!pipe {type #mammal}
!func |speak = {mammalian vocalization}

!pipe {type #bird}
!func |speak = {chirp}

; Extended module adds specializations
!tag animal += {#dog.mammal #cat.mammal}

!pipe {type #dog.mammal}
!func |speak = {woof}

; Polymorphic dispatch
({type=#bird} |speak)          ; "chirp"
({type=#dog.mammal} |speak)    ; "woof"

; Cross-module polymorphism
creature = {type=#dog.mammal name=Rex}
(creature |process-animal/external)   ; External module handles extended tag
```

## Lazy Functions and Deferred Execution

Functions can define lazy structures using `[]` brackets instead of `{}`. These create generators where fields compute on demand. Once computed, values are cached, making lazy structures eventually behave like regular structures. This enables efficient partial evaluation and infinite structures.

```comp
!pipe {}
!args {start ~num step ~num}
!func |infinite-sequence = [
    ($in |count |map {$arg.start + $in * $arg.step})
]

!pipe {data}
!func |expensive-analysis = [
    summary = ($in |compute-summary)
    statistics = ($in |deep-statistical-analysis)
    visualization = ($in |generate-charts)
    report = (|compile-full-report)
]

; Only computes what's needed
analysis = (data |expensive-analysis)
quick-view = analysis.summary    ; Only computes summary
full = analysis ~{summary statistics}  ; Computes two fields
```

## Function Permissions and Security

Functions can declare required permissions using the `!require` decorator. This creates compile-time documentation and enables early failure with clear error messages. The permission system uses capability tokens that flow through the context but cannot be stored or manipulated as values.

Pure functions implicitly drop all permissions, ensuring they cannot perform side effects. Regular functions inherit the caller's permissions unless explicitly restricted. The security model enables fine-grained control over resource access.

```comp
!require read, write
!pipe {}
!args {source ~str dest ~str}
!func |backup-file = {
    ($arg.source |read/file)      ; Needs read permission
    |compress
    |write/file $arg.dest         ; Needs write permission
}

!require net, env
!pipe {}
!args {endpoint ~str}
!func |fetch-with-config = {
    $var.api-key = (API_KEY |get/env)      ; Needs env token
    headers = {Authorization = Bearer ${$var.api-key}}
    ($arg.endpoint |get/http headers)      ; Needs net token
}

; Permissions flow through calls
!func |admin-operation = {
    (|backup-file)           ; Inherits admin's permissions
    
    ; Temporarily drop permissions for untrusted code
    untrusted-input = ($in |process-user-data)  ; Isolated execution
}
```

## Function Composition and Pipelines

Functions compose naturally through pipelines, with each function's output becoming the next function's input. The `$in` reference resets at each statement boundary, enabling elegant parallel processing and analysis patterns.

```comp
!pipe {data}
!func |comprehensive-analysis = {
    ; All three operate on input independently
    metrics = $in |calculate-metrics
    patterns = $in |identify-patterns
    anomalies = $in |detect-anomalies
    
    ; Combine results
    {metrics patterns anomalies
     summary=(|generate-summary data={metrics patterns anomalies})}
}

!pipe {raw-input}
!func |pipeline-composition = {
    ; Functions naturally chain
    $in |validate
        |normalize 
        |enhance config=$pipe.enhancement-config
        |transform
        |optimize
}
```

## Performance Considerations

Function dispatch can be optimized through caching. The runtime maintains dispatch caches for frequently-called functions, avoiding repeated shape matching. Pure functions enable additional optimizations - their results can be memoized, they can be evaluated at compile time for constant inputs, and they can be safely parallelized.

```comp
; Compile-time evaluation
!pure
!pipe {n ~num}
!func |factorial = {
    $in |if {$in <= 1} {1} {$in * ($in - 1 |factorial)}
}

; This evaluates at compile time
constant = (10 |factorial)    ; 3628800 computed during compilation

; Dispatch cache example
(users |map {$in |process})  ; Dispatch resolved once, cached for loop
```

## Design Principles

The function system embodies several core principles that guide its design. Functions as transformations means every function is fundamentally a structure-to-structure mapping. Structural dispatch enables polymorphism through shapes rather than classes. Explicit effects through permissions make side effects visible and controllable. Composition over inheritance creates flexible systems through function and block combinations. Deterministic selection ensures predictable behavior in polymorphic scenarios.

These principles create a function system that balances power with simplicity. Whether building simple data transformations or complex polymorphic systems, functions provide consistent, composable abstractions for computation.