# Shapes, Units, and Type System

*Design for Comp's structural typing, unit system, and shape morphing*

## Overview

Shapes define structural schemas that describe and validate data. They specify field names, types, defaults, and constraints, creating a powerful system for type checking and data transformation. Unlike nominal type systems, Comp's shapes use structural compatibility - any structure with the required fields can satisfy a shape.

The shape system integrates with units to provide semantic typing for primitive values. Units attach to numbers and strings through tags, enabling automatic conversions, type-safe operations, and domain-specific validation. Together, shapes and units create a flexible yet rigorous type system.

## Shape Definition and Inheritance

Shapes are defined with the `!shape` keyword and live declaratively in the module namespace. They can be referenced anywhere within the module regardless of definition order. Shape definitions specify fields with optional types, defaults, and documentation. The spread operator enables shape composition through inheritance.

```comp
!shape point-2d = {
    x ~num = 0
    y ~num = 0
}

!shape point-3d = {
    ..~point-2d              ; Inherit x, y fields
    z ~num = 0              ; Add z coordinate
}

!shape user = {
    name ~str
    email ~str
    age ~num = 0
    active? ~bool = #true
    preferences?            ; Optional field (any type)
    tags #user-tag[]        ; Array of specific tags
}

; Shape composition with multiple inheritance
!shape authenticated-user = {
    ..~user
    token ~str
    permissions #permission[]
    last-login ~str = (|now/time)
}
```

Fields in shapes can specify ranges for collections, enabling precise cardinality constraints. The syntax `[min-max]` defines acceptable element counts, with shortcuts for common patterns.

```comp
!shape config = {
    servers ~server[1-]      ; At least one server
    backups ~backup[0-3]     ; Up to three backups
    nodes ~node[5-10]        ; Between 5 and 10 nodes
    options ~str[]           ; Any number of strings
}
```

## Shape Morphing Algorithm

Shape morphing transforms structures to match shape specifications through a multi-phase matching process. The algorithm considers field names, types, positions, and defaults to create the best possible match. During morphing, missing fields can be sourced from the namespace stack (`$ctx` and `$mod`).

The morphing process follows these phases:
1. **Named field matching** - Exact field name matches are assigned first
2. **Tag field matching** - Fields with matching tag types are assigned
3. **Positional matching** - Remaining fields match by position
4. **Default application** - Unmatched shape fields receive defaults from shape definition
5. **Namespace lookup** - Missing fields check `$ctx` and `$mod`

```comp
!shape connection = {
    host ~str = localhost
    port ~num = 8080
    secure? ~bool = #false
}

; Basic morphing
({example.com 443 #true} ~connection)
; Result: {host=example.com port=443 secure?=#true}

; Namespace fields are automatically available
$ctx.port = 3000
({host=prod.example.com} ~connection)
; Result: {host=prod.example.com port=3000 secure?=#false}
; port comes from $ctx, secure? from shape default

; Function parameters automatically morph with namespace access
!pipe {conn ~connection}
!func |connect = {
    (Connecting to ${$pipe.host}:${$pipe.port} |log)
}
```

## Shape Application Operators

Different morphing operators control strictness and error handling. The standard morph (`~`) applies defaults and allows extra fields. Strong morph (`*~`) rejects structures with undefined fields. Weak morph (`?~`) makes all shape fields optional. Each variant has a corresponding check operator that tests compatibility without morphing.

```comp
data ~shape             ; Normal morph with defaults
data *~shape            ; Strong - no extra fields allowed
data ?~shape            ; Weak - missing fields acceptable

; Check operators return #true or #false
data ~? shape            ; Can morph normally?
data *~? shape           ; Can morph strictly?
data ?~? shape           ; Can morph weakly?

; Usage in validation
($in |if {$in ~? expected-shape} 
         {$in ~expected-shape |handle}
         {#shape.fail message=Invalid input structure})
```

## Shape Constraints

Shapes can define constraints that validate field values beyond basic type checking. These constraints are checked during morphing and can cause morphing to fail if violated. Constraints use pure functions that return boolean values or failure structures.

```comp
!shape valid-user = {
    name ~str {min-length=3 max-length=50}
    email ~str {pattern="^[^@]+@[^@]+$"}
    age ~num {min=13 max=120}
    score ~num {validate={$in >= 0 && $in <= 100}}
}

; Constraint functions for complex validation
!pure
!pipe {name ~str}
!func |valid-username = {
    ($in |length/str) >= 3 && 
    ($in |match/str "^[a-z][a-z0-9_]*$") &&
    !($in |contains/reserved-words)
}

!shape account = {
    username ~str {validate=|valid-username}
    balance ~num {min=0}
    status #account-status
}
```

Constraints are evaluated during morphing, with failures generating descriptive error structures. This enables precise validation at type boundaries while maintaining composability.

## Presence-Check Fields

Shapes support presence-check fields that are set based on whether their name appears as an unnamed value in the input structure. This enables flag-style arguments and configuration patterns.

```comp
!shape process-flags = {
    verbose ~bool = #false ?? #true
    debug ~bool = #false ?? #true
    quiet? ~bool = #true ?? #false
}

; The ?? operator defines:
; - Left side: value when field name NOT found in unnamed values
; - Right side: value when field name IS found

; Usage
({verbose extra=data} ~process-flags)
; Result: {verbose=#true debug=#false quiet?=#true extra=data}

!args ~process-flags
!func |process = {
    ($arg.verbose |when {#true} {
        ("Verbose mode enabled" |log)
    })
}

; Natural calling syntax
(data |process verbose)  ; Sets verbose=#true
```

## Spreading Shape Defaults

Shapes can be used in spread position to provide default values. This treats shapes as "default providers" without performing validation or type coercion. Only fields with defaults in the shape are included in the spread.

```comp
!shape config = {
    port ~num = 8080
    host ~str = "localhost"
    timeout ~num = 30
    api-key ~str           ; No default - not included
}

; Spread only includes fields WITH defaults
server = {..~config}
; Result: {port=8080 host="localhost" timeout=30}
; Note: api-key NOT included

; Override some defaults
custom = {..~config port=3000 host="0.0.0.0"}
; Result: {port=3000 host="0.0.0.0" timeout=30}

; No type coercion during spread
mixed = {..~config port="not-a-number"}  
; Result: {port="not-a-number" host="localhost" timeout=30}
; port is a string now, not coerced to number
```

The spread operation is purely mechanical - "copy all fields that have defaults" - while morphing is semantic - "transform this structure to match this shape."

## Unit System Fundamentals

Units provide semantic typing for primitive values through the tag system. Units are implemented as tag hierarchies with conversion rules, enabling type-safe operations and automatic conversions. The standard library provides comprehensive units through the `unit/` module.

```comp
!import unit = std "core/unit"

; Units as tags
distance = 5#kilometer      ; Using shortened form
duration = 30#second
temp = 20#celsius

; Automatic conversion in operations
total = 5#meter + 10#foot         ; Result in meters
speed = 100#kilometer / 1#hour    ; Compound unit

; Explicit conversion
meters = distance ~num#meter     ; 5000
feet = distance ~num#foot        ; ~16404
kelvin = temp ~num#kelvin        ; 293.15
```

Units follow algebraic rules:
- Addition/subtraction require compatible units
- First operand's unit determines result unit  
- Multiplication/division create compound units
- Incompatible operations fail immediately

## String Units and Domain Validation

String units provide semantic typing and validation for string values. They can enforce formats, apply transformations, and control escaping in templates. String units are particularly valuable for security, ensuring proper escaping based on context.

```comp
!tag email ~str = {
    validate = |match/str "^[^@]+@[^@]+$"
    normalize = |lowercase/str
}

!tag sql ~str = {
    escape = |escape-literal/sql
    validate = |check-syntax/sql
}

!tag html ~str = {
    escape = |escape-entities/html
    sanitize = |remove-scripts/html
}

; Usage with automatic validation
address = "User@Example.COM"#email
normalized = address ~str#email    ; user@example.com

; Template safety through units
query = SELECT * FROM users WHERE id = ${id}#sql
html = <h1>${title}</h1>#html
; Units ensure proper escaping in templates
```

## Union and Conditional Shapes

Shapes can be combined with `|` to create union types that accept multiple structures. This enables flexible APIs that handle different input formats while maintaining type safety. Union shapes are particularly useful for result types and variant handling.

```comp
!shape result = ~success | ~error
!shape success = {value ~any}
!shape error = {#fail message ~str}

!shape config-source = ~file-config | ~env-config | ~default-config
!shape file-config = {path ~str}
!shape env-config = {prefix ~str}
!shape default-config = {}

; Conditional shape selection
!pipe {input}
!func |process = {
    $in |match
        {$in ~? success} {$pipe.value |handle-success}
        {$in ~? error} {$pipe.message |log-error}
}
```

## Shape-Based Pattern Matching

Shapes integrate with pattern matching to enable type-directed control flow. The `~?` operator tests shape compatibility, while morphing operations transform data for processing. This creates elegant APIs where function behavior adapts to input structure.

```comp
!shape get-request = {method=GET path ~str}
!shape post-request = {method=POST path ~str body ~any}
!shape delete-request = {method=DELETE path ~str}

!pipe {request}
!func |handle-request = {
    $in |match
        {$in ~? get-request} {
            $in ~get-request |fetch-resource
        }
        {$in ~? post-request} {
            $in ~post-request |create-resource
        }
        {$in ~? delete-request} {
            $in ~delete-request |delete-resource
        }
        {#true} {
            {#http.fail status=405 message=Method not allowed}
        }
}
```

## Performance Optimization

Shape operations can be optimized through caching and compilation. Repeated morphing operations with the same shape benefit from cached validation rules. The runtime can compile shape definitions into efficient validators, particularly for shapes with complex constraints.

```comp
; Shapes used in hot paths should be pre-compiled
!shape hot-path = {
    data ~str {validate=|complex-validation}
    timestamp ~num {min=0}
    flags #flag[]
}

; First use compiles validation rules
first-result = input ~hot-path      ; Compiles and caches

; Subsequent uses reuse compiled rules
loop-results = items |map {$in ~hot-path}  ; Fast validation
```

## Design Principles

The shape and unit system embodies several core principles. Structural compatibility means types are defined by structure, not names, enabling flexible composition. Semantic typing through units provides meaning beyond primitive types. Gradual validation allows choosing strictness levels appropriate to each context. Namespace integration enables shapes to work with Comp's layered data model. Compile-time optimization ensures type checking doesn't sacrifice performance.

These principles create a type system that balances flexibility with safety. Whether validating API inputs, ensuring dimensional correctness in calculations, or transforming between data formats, shapes and units provide powerful tools for managing complexity in real-world applications.