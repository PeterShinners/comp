# Structures, Spreads, and Lazy Evaluation

*Design for Comp's structure generation, manipulation, and management*

## Overview

Structures are the backbone of Comp, everything is designed around creating and altering structures. Every function receives a structure as input and generates a new structure as output. Even simple values like numbers promote to single-element structures when they enter pipelines, creating a unified data model that eliminates type juggling.

Structures handle real-world data naturally, they work equally well as records, arrays, or hybrid collections. Field names can be simple tokens, complex strings, or even tag values. This flexibility means you can work with JSON APIs, database records, or internal computations using the same fundamental operations.

The structure system embodies principles that eliminate data handling complexity. Immutability ensures predictable behavior—no surprising mutations. Unified representation means one data type handles arrays, records, and everything in between. Order preservation maintains structure while enabling both positional and named access.

These principles create a structure system that handles real-world data elegantly without forcing artificial distinctions between arrays and objects. Functions that operate on structures are detailed in [Functions and Blocks](function.md), while pipeline processing is covered in [Pipelines, Flow Control, and Failure Handling](pipeline.md). For controlled mutation patterns, see [Store System](store.md).

## Structure Definition and Field Access

Structures are created with `{}` braces and handle field access intuitively. Named fields use `=` for assignment, unnamed fields are just listed. Field names are incredibly flexible—simple tokens, arbitrary strings, even expressions. The system accommodates whatever field naming convention your data source uses.

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

; Index access (no period before #)
coords#0                     ; 10 - first unnamed field
coords#1                     ; 20 - second unnamed field
mixed#0                      ; 10 - first unnamed field
#0                          ; From $in in pipeline
```

Field access distinguishes between:
- `data.field` - Named field access
- `data#0` - Positional index (numeric literals only)
- `data.'expr'` - Computed field name from expression
- `data."string"` - String literal as field name

For more sophisticated navigation patterns through complex data structures, see [Trail System](trail.md).

## Spread Operations and Structure Assembly

Spread operators solve the "merge these data structures" problem elegantly. The basic spread (`..`) incorporates all fields, strong spread (`!..`) creates sticky fields that resist overwriting, and weak spread (`?..`) only adds missing fields. This covers the common patterns: override everything, lock in values, or provide defaults.

When spreading multiple structures, fields are applied in source order. Named field conflicts are resolved by assignment strength - strong beats normal beats weak. Unnamed fields never conflict; they accumulate in order from each spread source. The spread operation preserves field ordering within each source structure.

```comp
base = {x=1 y=2 mode=default}
overlay = {y=3 z=4 mode*=fixed}

; Basic spreading with conflicts
merged = {..base ..overlay}
; Result: {x=1 y=3 z=4 mode=fixed}

; Strong spread dominates
locked = {!..base y=99}
; Result: {x=1 y=2 mode=default} - strong spread resists override

; Weak spread for defaults
config = {
    port = 8080
    ?..{port=3000 host=localhost timeout=30}
}
; Result: {port=8080 host=localhost timeout=30}

; Spread from shapes for defaults
defaults = {..~config-shape}
custom = {..~config-shape port=3000}

; Field deletion with !delete
cleaned = {..original !delete temp-field !delete old-field}

; Unnamed fields accumulate
arrays = {..{1 2} ..{3 4}}
; Result: {1 2 3 4}
```

The spread operators work identically in all contexts - structure literals, function parameters, and shape definitions. This consistency makes them predictable tools for structure composition.

## Assignment Operators and Field Manipulation

Assignment in Comp creates new structures rather than modifying existing ones. The assignment operators control how conflicts are resolved when the same field is set multiple times. Normal assignment (`=`) overwrites, strong assignment (`*=`) creates persistent values, and weak assignment (`?=`) only sets undefined fields.

Deep field assignment creates new nested structures at each level, preserving immutability throughout the hierarchy. The assignment target determines where the value goes - local variables with `@var`, output structure fields (no prefix), or scope structures like `$ctx`.

```comp
; Field override behavior
config = {
    port *= 8080        ; Strong - resists override
    host = localhost    ; Normal - can be overwritten
    timeout ?= 30       ; Weak - only if undefined
    
    port = 3000        ; Ignored due to strong assignment
    host = 0.0.0.0     ; Overwrites normal assignment
}

; Deep assignment preserves immutability
tree = {left={value=1} right={value=2}}
tree.left.value = 10
; Creates new structures: {..tree left={..tree.left value=10}}

; Assignment targets
!func |example = {
    @temp = 5               ; Local variable
    result = (|compute)     ; Output field (implicit $in)
    $ctx.setting = value    ; Context scope
    @data = {field=10}      ; New structure in variable
}
```

## Field Assignment Shortcuts

When creating structures that extract fields from existing data, a trailing dot syntax provides a concise shorthand. The pattern `field=scope.` assigns the field to the value of the same-named field from the specified scope. If no scope is provided, `$in` is assumed.

```comp
; Long form field extraction
user-data = {
    name = $in.name
    email = $in.email
    status = $in.status
    created-at = $in.created-at
}

; Trailing dot shorthand
user-data = {name=. email=. status=. created-at=.}

; Mixed with explicit assignments
response = {
    id=.                    ; From $in.id
    name=.                  ; From $in.name
    status = #active        ; Explicit value
    timestamp = (|now)      ; Computed value
}

; Works with different scopes
config = {
    port=$ctx.              ; From $ctx.port
    host=$mod.              ; From $mod.host
    timeout=.               ; From $in.timeout (default scope)
}

; Works with all assignment operators
fields = {
    name=.                  ; Normal assignment
    title*=.                ; Strong assignment
    description?=.          ; Weak assignment
}

; Particularly useful in map operations
(users |map {id=. name=. email=. active=.})
```

The trailing dot syntax significantly reduces repetition when extracting multiple fields, making structure creation more readable while maintaining explicit field naming. This pattern is especially common in data transformation pipelines where input structures are filtered or reorganized.

## Destructured Assignment

Destructured assignment extracts multiple fields from a structure in a single statement. Named fields are extracted by name while unnamed fields are extracted positionally. This provides a concise way to unpack structures into individual variables or fields.

```comp
; Extract named fields
{name age city} = user
; Equivalent to: name=user.name age=user.age city=user.city

; Extract with renaming
{name=username age=years} = user
; Creates: username=user.name years=user.age

; Mix named and positional
{x y label=name} = point
; Gets first two unnamed fields as x,y and 'label' field as name

; Nested destructuring
{user={name email} status} = response
; Extracts nested fields directly

; With defaults using fallback
{port=config.port ?? 8080 host=config.host ?? localhost} = {}
```

Destructured assignment is particularly useful when working with function returns that provide multiple values, or when extracting configuration from nested structures.

## Field Deletion

Removing fields from structures requires creating new structures without those fields. Since structures are immutable, there's no direct deletion - only construction of new structures missing certain fields. The `!delete` operator and shape morphing provide clean approaches for controlled field removal.

```comp
; Remove fields with !delete operator
original = {x=1 y=2 z=3 temp=remove}
cleaned = {..original !delete temp}
; Result: {x=1 y=2 z=3}

; Multiple deletions
modified = {..base !delete field1 !delete field2}

; Remove fields via shape morphing
!shape ~public-user = {name ~str email ~str}  ; No password field
user = {name=Alice email=a@example.com password=secret}
public = user ~public-user  ; Result: {name=Alice email=a@example.com}

; Conditional field inclusion
result = {
    id = data.id
    ?..(data.is-public |if {$in} {name=data.name email=data.email} {})
}
```

The pattern of using shapes to define "public" versions of structures is idiomatic in Comp, providing type safety along with field filtering. For comprehensive information about shapes, morphing operations, and type validation, see [Shapes, Units, and Type System](shape.md).

## Lazy Evaluation

Lazy structures delay computation until fields are accessed. Created with `[]` brackets instead of `{}`, they behave like generators that compute values on demand. Once a field is computed, its value is cached for future access. After full evaluation, a lazy structure behaves identically to a regular structure.

Lazy structures capture their creation context - local variables, scope values, and function parameters are frozen at creation time. This allows lazy computations to reference values that may change or go out of scope after creation.

```comp
; Lazy structure delays expensive operations
expensive = [
    summary = (|compute-summary)
    analysis = (|deep-analysis)
    report = (|generate-report)
]
; No computation happens yet

value = expensive.summary  ; Only computes summary field

; Context capture
!func |create-processor ^{multiplier ~num} = {
    ; Context captured when [] is created
    processor = [
        doubled = $in * ^multiplier * 2
        tripled = $in * ^multiplier * 3
    ]
    processor  ; Returns lazy structure with captured multiplier
}

; Multiple independent calls in lazy structure
@lazy = [
    call1 = ($in |slow-call1)     ; Explicit $in breaks chain
    call2 = ($in |slow-call2)     ; Independent call
]

; Or with parentheses
@lazy = [
    call1 = (|slow-call1)          ; Independent pipeline
    call2 = (|slow-call2)          ; Independent pipeline
]

; Lazy evaluation with shapes
data = [
    field1 = (|expensive1)
    field2 = (|expensive2)
    field3 = (|expensive3)
    extra = (|not-needed)
] ~{field1 field2}  ; Only computes field1 and field2
```

When a lazy structure is morphed to a shape that requires only specific fields, computation stops once those fields are resolved. This enables efficient partial evaluation of complex structures.

## Structure Comparison and Iteration

Structures can be compared for equality and ordering. Equality (`==`) checks structural equivalence - named fields must match by name and value (regardless of order), while unnamed fields must match by position. Ordering (`<`, `>`) uses lexicographic comparison, first comparing matched named fields alphabetically, then positional fields left-to-right.

The standard library provides comprehensive structure operations through the `struct/` module. These functions enable field inspection, filtering, transformation, and analysis without breaking immutability. The module system and standard library organization are detailed in [Modules, Imports, and Namespaces](module.md).

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

(data |field-names/struct)           ; [name age status]
(data |has-field/struct email)       ; true or false
(data |filter/struct {value > 0})  ; Keep positive fields
(data |map-fields/struct |upper/str) ; Transform all fields
```

## Advanced Structure Patterns

Complex structures often combine multiple composition techniques. Template functions generate structures with computed fields. Conditional spreading includes fields based on runtime conditions. Nested structures maintain immutability through all levels.

```comp
; Template function for consistent structure creation
!func |create-response ^{status ~tag data ~any} = {
    status = ^status
    data = ^data
    timestamp = (|now/time)
    metadata = {
        version = 1.0
        ?..((^status >= 400) |if {$in} {error=#true} {})
    }
}

; Conditional field inclusion
user-view = {
    id = user.id
    name = user.name
    ?..(is-admin |if {$in} {email=user.email role=user.role} {})
    ?..(is-self |if {$in} {preferences=user.preferences} {})
}

; Structure transformation pipeline
(raw-data |validate
          |{$in validated=#true timestamp=(|now/time)}
          |enhance-with-metadata
          |{$in checksum=(|calculate-checksum)})
```
