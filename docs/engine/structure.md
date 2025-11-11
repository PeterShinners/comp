# Structures, Spreads, and Lazy Evaluation

*Design for Comp's structure generation, manipulation, and management*

## Overview

Structures are the backbone of the Comp language. Every function receives a structure as input and generates a new structure as output. Even simple values like booleans and numbers are automatically promoted into single-element structures when used in pipeline contexts.

Structures are immutable collections that can contain any mix of named and unnamed fields. Field names can be simple tokens, complex strings, or even tag values. Fields are ordered and can be accessed by name or position. This unified approach means structures work equally well as records, arrays, or hybrid collections.

## Structure Definition and Field Access

Structures are created with `{}` braces containing field definitions. Fields can have explicit names or be positional (unnamed). Named fields use `=` for assignment, while unnamed fields are simply listed. The same field name can appear multiple times, with later definitions overriding earlier ones based on assignment strength.

Field names in structures are incredibly flexible. Arbitrary strings use double quotes for field names, and expressions use single quotes for computed field access.

```comp
; Various field types
user = {
    name = "Alice"              ; String literal value
    age = 30                    ; Number literal
    #active.status = #true      ; Tag as field name
    "Full Name" = "Alice Smith" ; String field name
    'score * 2' = 60           ; Expression field name
}

; Accessing fields - undecorated tokens for common case
user.name                    ; Token access
user.#active.status         ; Tag field access
user."Full Name"            ; String field access
user.'score * 2'            ; Expression field access
user.'$idx'                 ; Variable value as field name

; Positional fields
coords = {10 20 30}          ; Three unnamed fields
mixed = {x=5 10 y=15}        ; Mix of named and unnamed

; Index access (requires dot before #)
coords.#0                    ; 10 - first unnamed field
coords.#1                    ; 20 - second unnamed field
mixed.#0                     ; 10 - first unnamed field
#0                          ; From $in in pipeline (standalone reference)

; Chained access patterns (currently supported)
users.#1.name               ; Index then field access (requires parentheses: (users.#1).name)
data.#0.#1                  ; Nested index access (requires parentheses: (data.#0).#1)
config."servers".#0         ; String field then index access
items."metadata"."created-at"  ; String field chaining
obj.'computed'.value        ; Computed field then identifier field
data."Big Day!".#2          ; String fields with spaces/punctuation

; Complex chaining example (using parentheses for index access)
(((data."Big Day!").#2).'field').'next'  ; Full chaining with mixed access types
```

Field access distinguishes between:
- `data.field` - Named field access (identifier)
- `data.#0` - Positional index (numeric literals only) 
- `data.'expr'` - Computed field name from expression
- `data."string"` - String literal as field name

The dotted syntax creates consistent, readable access chains. String and computed field access chain naturally, while index access currently requires parentheses for continued chaining (to be resolved in future iteration).

## Spread Operations and Structure Assembly

Spread operators allow composing new structures from existing ones. The spread incorporates all fields from a source structure, with variants controlling conflict resolution. The basic spread (`..`) applies all fields, strong spread (`!..`) creates sticky fields that resist overwriting, and weak spread (`?..`) only adds missing fields.

When spreading multiple structures, fields are applied in source order. Named field conflicts are resolved by assignment strength - strong beats normal beats weak. Unnamed fields never conflict; they accumulate in order from each spread source. The spread operation preserves field ordering within each source structure.

```comp
base = {x=1 y=2 mode=default}
overlay = {y=3 z=4 mode=*fixed}

; Basic spreading with conflicts
merged = {..base ..overlay}
; Result: {x=1 y=3 z=4 mode=fixed}

; Strong spread dominates
locked = {!..base y=99}
; Result: {x=1 y=2 mode=default} - strong spread resists override

; Weak spread for defaults
config = {
    port = 8080
    ?.:{port=3000 host=localhost timeout=30}
}
; Result: {port=8080 host=localhost timeout=30}

; Spread from shapes for defaults
defaults = {..~config-shape}
custom = {..~config-shape port=3000}

; Field deletion with !delete
cleaned = {..original !delete temp-field !delete old-field}

; Unnamed fields accumulate
arrays = {.:{1 2} .:{3 4}}
; Result: {1 2 3 4}
```

The spread operators work identically in all contexts - structure literals, function parameters, and shape definitions. This consistency makes them predictable tools for structure composition.

## Assignment Operators and Field Manipulation

Assignment in Comp creates new structures rather than modifying existing ones. The assignment operators control how conflicts are resolved when the same field is set multiple times. Normal assignment (`=`) overwrites, strong assignment (`=*`) resists overwriting, and weak assignment (`=?`) only sets undefined fields.

Deep field assignment creates new nested structures at each level, preserving immutability throughout the hierarchy. The assignment target determines where the value goes - local variables with `$var`, output structure fields (no prefix), or namespace structures like `$ctx`.

```comp
; Field override behavior
config = {
    port =* 8080        ; Strong - resists override
    host = localhost    ; Normal - can be overwritten
    timeout =? 30       ; Weak - only if undefined
    
    port = 3000        ; Ignored due to strong assignment
    host = 0.0.0.0     ; Overwrites normal assignment
}

; Deep assignment preserves immutability
tree = {left={value=1} right={value=2}}
tree.left.value = 10
; Creates new structures: {..tree left={..tree.left value=10}}

; Assignment targets
!func |example = {
    $var.temp = 5                    ; Local variable
    result = [|compute]              ; Output field (implicit $pipe)
    $ctx.setting = value             ; Context namespace
    $var.data = {field=10}          ; New structure in variable
}
```

## Destructured Assignment

Destructured assignment extracts multiple fields from a structure in a single statement. Named fields are extracted by name while unnamed fields are extracted positionally. This provides a concise way to unpack structures into individual variables or fields.

```comp
; Extract named fields
{name age city} = $pipe.user
; Equivalent to: name=$pipe.user.name age=$pipe.user.age city=$pipe.user.city

; Extract with renaming
{name=username age=years} = $pipe.user
; Creates: username=$pipe.user.name years=$pipe.user.age

; Mix named and positional
{x y label=name} = $pipe.point
; Gets first two unnamed fields as x,y and 'label' field as name

; Nested destructuring
{user={name email} status} = $pipe.response
; Extracts nested fields directly

; With defaults using fallback
{port=$pipe.config.port ?? 8080 host=$pipe.config.host ?? localhost} = {}
```

Destructured assignment is particularly useful when working with function returns that provide multiple values, or when extracting configuration from nested structures.

## Field Deletion

Removing fields from structures requires creating new structures without those fields. Since structures are immutable, there's no direct deletion - only construction of new structures missing certain fields. The `!delete` operator and shape morphing provide clean approaches for controlled field removal.

```comp
; Remove fields with !delete operator
original = {x=1 y=2 z=3 temp="remove"}
cleaned = {..original !delete temp}
; Result: {x=1 y=2 z=3}

; Multiple deletions
modified = {..base !delete field1 !delete field2}

; Remove fields via shape morphing
!shape public-user = {name ~str email ~str}  ; No password field
user = {name="Alice" email="a$var.example.com" password="secret"}
public = user ~public-user  ; Result: {name=Alice email=a$var.example.com}

; Conditional field inclusion
result = {
    id = $pipe.data.id
    ?..(data.is-public |if {$in} {name=$pipe.data.name email=$pipe.data.email} {})
}
```

The pattern of using shapes to define "public" versions of structures is idiomatic in Comp, providing type safety along with field filtering.

## Lazy Evaluation

Lazy structures delay computation until fields are accessed. Created with `[]` brackets instead of `{}`, they behave like generators that compute values on demand. Once a field is computed, its value is cached for future access. After full evaluation, a lazy structure behaves identically to a regular structure.

Lazy structures capture their creation context - local variables, namespace values, and function parameters are frozen at creation time. This allows lazy computations to reference values that may change or go out of scope after creation.

```comp
; Lazy structure delays expensive operations
expensive = [
    summary = [|compute-summary]
    analysis = [|deep-analysis]
    report = [|generate-report]
]
; No computation happens yet

value = expensive.summary  ; Only computes summary field

; Context capture
!pipe {}
!args {multiplier ~num}
!func |create-processor = {
    ; Context captured when [] is created
    processor = [
        doubled = $in * $arg.multiplier * 2
        tripled = $in * $arg.multiplier * 3
    ]
    processor  ; Returns lazy structure with captured multiplier
}

; Multiple independent calls in lazy structure
$var.lazy = [
    call1 = [$in |slow-call1]     ; Explicit $in breaks chain
    call2 = [$in |slow-call2]     ; Independent call
]

; Or with parentheses
$var.lazy = [
    call1 = [|slow-call1]          ; Independent pipeline
    call2 = [|slow-call2]          ; Independent pipeline
]

; Lazy evaluation with shapes
data = [
    field1 = [|expensive1]
    field2 = [|expensive2]
    field3 = [|expensive3]
    extra = [|not-needed]
] ~{field1 field2}  ; Only computes field1 and field2
```

When a lazy structure is morphed to a shape that requires only specific fields, computation stops once those fields are resolved. This enables efficient partial evaluation of complex structures.

## Structure Comparison and Iteration

Structures can be compared for equality and ordering. Equality (`==`) checks structural equivalence - named fields must match by name and value (regardless of order), while unnamed fields must match by position. Ordering (`<`, `>`) uses lexicographic comparison, first comparing matched named fields alphabetically, then positional fields left-to-right.

The standard library provides comprehensive structure operations through the `struct/` module. These functions enable field inspection, filtering, transformation, and analysis without breaking immutability.

```comp
; Equality ignores named field order
{x=1 y=2} == {y=2 x=1}                ; true
{1 2 3} == {1 2 3}                    ; true
{x=1 2} == {2 x=1}                    ; false - positional order matters

; Ordering is deterministic
{a=1 z=3} < {a=2 b=1}                 ; true - 'a' field compared first
{x=1} < {x=1 y=2}                     ; true - subset is less

; Structure operations via standard library
!import struct = std "core/struct"

[data |field-names/struct]           ; [name age status]
[data |has-field/struct email]       ; true or false
[data |filter/struct {$pipe.value > 0}]  ; Keep positive fields
[data |map-fields/struct |upper/str] ; Transform all fields
```

## Advanced Structure Patterns

Complex structures often combine multiple composition techniques. Template functions generate structures with computed fields. Conditional spreading includes fields based on runtime conditions. Nested structures maintain immutability through all levels.

```comp
; Template function for consistent structure creation
!pipe {}
!args {status ~tag data ~any}
!func |create-response = {
    status = $arg.status
    data = $arg.data
    timestamp = [|now/time]
    metadata = {
        version = 1.0
        ?..(($arg.status >= 400) |if {$in} {error=#true} {})
    }
}

; Conditional field inclusion
user-view = {
    id = $pipe.user.id
    name = $pipe.user.name
    ?..($pipe.is-admin |if {$in} {email=$pipe.user.email role=$pipe.user.role} {})
    ?..($pipe.is-self |if {$in} {preferences=$pipe.user.preferences} {})
}

; Structure transformation pipeline
[raw-data |validate
          |{$in validated=#true timestamp=[|now/time]}
          |enhance-with-metadata
          |{$in checksum=[|calculate-checksum]}]
```

## Design Principles

The structure system embodies core Comp principles that guide its design. Immutability ensures predictable behavior and enables safe parallelism. Unified representation means arrays, records, and hybrid collections use the same structure type. Flexible field naming accommodates any data source naturally. Order preservation maintains structure and enables positional access. Compositional operations through spreading and morphing build complex structures from simple pieces.

These principles create a structure system that handles real-world data elegantly. Whether working with JSON APIs, database records, or internal computations, structures provide a consistent, powerful abstraction for data manipulation.