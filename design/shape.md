# Shapes, Units, and Type System

*Design for Comp's structural typing, unit system, and shape morphing*

## Overview

Shapes solve the type system problem that most languages get wrong—balancing flexibility with safety. Instead of forcing rigid class hierarchies, shapes use structural compatibility: any data with the right fields works, period. No inheritance ceremonies, no interface implementations, just data that fits.

The shape system integrates with units to provide semantic typing that actually matters. Units attach meaning to numbers and strings—5#meters is different from 5#seconds, and the type system keeps you from accidentally mixing them. Together, shapes and units create a type system that helps instead of hindering.

Shapes and units are a powerful tool for validating API inputs, ensuring dimensional correctness, or transforming between data formats. Comp's approach uses concrete types where morphing operations produce definite typed values rather than inferred types—see [Syntax and Style Guide](syntax.md) for how this affects the entire type system. For information about the tag system that underlies units, see [Tag System](tag.md), and for details about the core primitive types, see [Core Types](type.md).

## Shape Definition and Inheritance

Shapes are defined with the `!shape` operator. Their definition appears similar
to a structure definition, but this is focused on types and default values.

A shape is not a value. It is a referencable part of the module namespace that
is accessed within the module and other modules after !import.

```comp
!shape ~point-2d = {
    x ~num = 0
    y ~num = 0
}

!shape ~point-3d = {
    ..~point-2d              ; Inherit x, y fields
    z ~num = 0              ; Add z coordinate
}

!shape ~user = {
    name ~str
    email ~str
    age ~num = 0
    active? ~bool = #true
    preferences?            ; Optional field (any type)
    tags #user-tag[]        ; Array of specific tags
}

; Shape composition with multiple inheritance
!shape ~authenticated-user = {
    ..~user
    token ~str
    permissions #permission[]
    last-login ~str = (|now/time)
}
```

Fields in shapes can specify ranges for collections, enabling precise
cardinality constraints. The syntax `[min-max]` defines acceptable element
counts, with shortcuts for common patterns.

```comp
!shape ~config = {
    servers ~server[1-]      ; At least one server
    backups ~backup[0-3]     ; Up to three backups
    nodes ~node[5-10]        ; Between 5 and 10 nodes
    options ~str[]           ; Any number of strings
}
```

## Shape Morphing Algorithm

Shape morphing transforms structures to match shape specifications through a
multi-phase matching process. The algorithm considers field names, types,
positions, and defaults to create the best possible match.

The morphing process follows these phases:
1. **Named field matching** - Exact field name matches are assigned first
2. **Tag field matching** - Fields with matching tag types are assigned
3. **Positional matching** - Remaining fields match by position
4. **Default application** - Unmatched shape fields receive defaults from shape
   definition

```comp
!shape ~connection = {
    host ~str = localhost
    port ~num = 8080
    secure? ~bool = #false
}

; Basic morphing
({example.com 443 #true} ~connection)
; Result: {host=example.com port=443 secure?=#true}

; Morphing with defaults
({host=prod.example.com} ~connection)
; Result: {host=prod.example.com port=8080 secure?=#false}
; port and secure? come from shape defaults

; Function parameters automatically morph
!func |connect ~{conn ~connection} = {
    (Connecting to ${host}:${port} |log)
}
```

## Shape Application Operators

Different morphing operators control strictness and error handling. The morphing rules differ between function invocation and block invocation to provide appropriate flexibility and safety.

### Morphing Operators

```comp
data ~shape             ; Normal morph with defaults
data *~shape            ; Strong - no extra fields allowed
data ?~shape            ; Weak - missing fields acceptable

; Check operators return #true or #false
data ~? shape           ; Can morph normally?
data *~? shape          ; Can morph strictly?
data ?~? shape          ; Can morph weakly?
```

### Function vs Block Morphing Rules

**Function invocation uses loose morphing** - extra fields in arguments are ignored, enabling forward compatibility and optional parameters:

```comp
!func |process ~{x ~num y ~num} = {x + y}
(|process x=1 y=2 z=3)  ; Works - z ignored
```

**Block invocation uses strict morphing** - extra fields cause morphing to fail, preventing accidental capture through closure:

```comp
!shape ~predicate = ~block{value ~num}
@test = .{value > 10} ~predicate

{value=5 extra="data"} |.@test  ; FAILS - extra field not allowed
{value=5} |.@test               ; Works - exact match
```

This distinction ensures blocks have predictable inputs while functions remain flexible for evolution and extension.

## Shape Constraints

Shapes can define constraints that validate field values beyond basic type
checking. These constraints are checked during morphing and can cause morphing
to fail if violated. Constraints use pure functions that return boolean values
or failure structures.

Constraints are evaluated during morphing, with failures generating descriptive
error structures. This enables precise validation at type boundaries while
maintaining composability.

```comp
!shape ~valid-user = {
    name ~str {min-length=3 max-length=50}
    email ~str {pattern="^[^@]+@[^@]+$"}
    age ~num {min=13 max=120}
    score ~num {validate={$in >= 0 && $in <= 100}}
}

; Constraint functions for complex validation
!pure
!func |valid-username ~{name ~str} = {
    ($in |length/str) >= 3 && 
    ($in |match/str "^[a-z][a-z0-9_]*$") &&
    !($in |contains/reserved-words)
}

!shape ~account = {
    username ~str {validate=|valid-username}
    balance ~num {min=0}
    status #account-status
}
```

## Block Type Signatures

Blocks can be typed through shape definitions that specify their expected input structure. This enables type-safe block parameters in functions and clear contracts for stream generators.

```comp
; Block expecting any input
!shape ~transformer = ~block{~any}

; Block expecting specific structure
!shape ~validator = ~block{name ~str age ~num}

; Block expecting no input (streams)
!shape ~generator = ~block{}

; Block with union input types
!shape ~processor = ~block{~user | ~account}

; Usage in function signatures
!func |process ^{transform ~transformer} = {
    data |map transform  ; Block used with map
}

!func |stream-counter ^{start ~num = 0} -> ~generator = {
    ; Returns a generator block
}
```

When blocks are typed, they become invocable with the `|.` operator and enforce their input shape through morphing. For detailed coverage of streams, block invocation patterns, and iterator functions, see [Iteration and Streams](loop.md).

## Presence-Check Fields

Shapes support presence-check fields that are set based on whether their name
appears as an unnamed value in the input structure. This enables flag-style
arguments and configuration patterns.

These are mostly useful on shape definitions for function arguments, but
they can be used anywhere shape references are used.

```comp
!shape ~process-flags = {
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

!func |process ^~process-flags = {
    (^verbose |when {#true} {
        ("Verbose mode enabled" |log)
    })
}

; Natural calling syntax
(data |process verbose)  ; Sets verbose=#true
```

## Spreading Shape Defaults

Shapes can be used in spread operations to apply their default values:

```comp
!shape ~config = {
    port ~num = 8080
    host ~str = "localhost"
    timeout ~num = 30
    api-key ~str           ; No default - not included in spread
}

; Apply defaults from shape
server = {..~config}  ; {port=8080 host="localhost" timeout=30}
custom = {..~config port=3000}  ; Override specific defaults
```

For detailed information about shape spreading and structure assembly patterns, see [Structures, Spreads, and Lazy Evaluation](structure.md).

The spread operation is purely mechanical - "copy all fields that have defaults"
- while morphing is semantic - "transform this structure to match this shape."
For detailed information about spread operations and structure composition, see
[Structures, Spreads, and Lazy Evaluation](structure.md).

## Unit System Fundamentals

Units provide semantic typing for primitive values through the tag system. Units
are implemented as tag hierarchies with conversion rules, enabling type-safe
operations and automatic conversions. The standard library provides
comprehensive units through the `unit/` module.

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

String units provide semantic typing and validation for string values. They can
enforce formats, apply transformations, and control escaping in templates.
String units are particularly valuable for security, ensuring proper escaping
based on context.

```comp
!tag #email ~str = {
    validate = |match/str "^[^@]+@[^@]+$"
    normalize = |lowercase/str
}

!tag #sql ~str = {
    escape = |escape-literal/sql
    validate = |check-syntax/sql
}

!tag #html ~str = {
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

Shapes can be combined with `|` to create union types that accept multiple
structures. This enables flexible APIs that handle different input formats while
maintaining type safety. Union shapes are particularly useful for result types
and variant handling.

```comp
!shape ~result = ~success | ~error
!shape ~success = {value ~any}
!shape ~error = {#fail message ~str}

!shape ~config-source = ~file-config | ~env-config | ~default-config
!shape ~file-config = {path ~str}
!shape ~env-config = {prefix ~str}
!shape ~default-config = {}

; Conditional shape selection
!func |process ~{input} = {
    $in |match
        {$in ~? success} {value |handle-success}
        {$in ~? error} {message |log-error}
}
```

## Shape-Based Pattern Matching

Shapes integrate with pattern matching to enable type-directed control flow. The
`~?` operator tests shape compatibility, while morphing operations transform
data for processing. This creates elegant APIs where function behavior adapts to
input structure. For comprehensive information about pattern matching and
control flow patterns, see [Pipelines, Flow Control, and Failure
Handling](pipeline.md).

```comp
!shape ~get-request = {method=#get path ~str}
!shape ~post-request = {method=#post path ~str body ~any}
!shape ~delete-request = {method=#delete path ~str}

!func |handle-request ~{request} = {
    $in |match
        .{$in ~? get-request} .{
            $in ~get-request |fetch-resource
        }
        .{$in ~? post-request} .{
            $in ~post-request |create-resource
        }
        .{$in ~? delete-request} .{
            $in ~delete-request |delete-resource
        }
        .{#true} .{
            {#http.fail status=405 message=Method not allowed}
        }
}
```

## Performance Optimization

Shape operations can be optimized through caching and compilation. Repeated
morphing operations with the same shape benefit from cached validation rules.
The runtime can compile shape definitions into efficient validators,
particularly for shapes with complex constraints.

When this happens, the language understands the types used by fields,
which allows faster code paths in successive uses.

```comp
; Shapes used in hot paths should be pre-compiled
!shape ~hot-path = {
    data ~str {validate=|complex-validation}
    timestamp ~num {min=0}
    flags #flag[]
}

; First use compiles validation rules
first-result = input ~hot-path      ; Compiles and caches

; Subsequent uses reuse compiled rules
loop-results = items |map {$in ~hot-path}  ; Fast validation
```
