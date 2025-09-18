# Structures, Spreads, and Lazy Evaluation

*Design for Comp's structure generation, manipulation, and management*

## Overview

Structures are the backbone of the Comp language. Every function receives a structure as input and generates a new structure as output. Even simple values like booleans and numbers are automatically promoted into single-element structures when used in pipeline contexts.

Structures are immutable collections that can contain any mix of named and unnamed fields. Field names can be simple tokens, complex strings, or even tag values. Fields are ordered and can be accessed by name or position. This unified approach means structures work equally well as records, arrays, or hybrid collections.

## Structure Definition and Field Access

Structures are created with `{}` braces containing field definitions. Fields can have explicit names or be positional (unnamed). Named fields use `=` for assignment, while unnamed fields are simply listed. The same field name can appear multiple times, with later definitions overriding earlier ones based on assignment strength.

Field names in structures are incredibly flexible. Tokens need no quoting, tags can be used directly, arbitrary strings use double quotes, and expressions use single quotes. This same syntax applies when referencing fields with dot notation.

```comp
; Various field name types
user = {
    name = "Alice"              ; Token field name
    age = 30                    ; Regular assignment
    #status#active = true       ; Tag as field name
    "Full Name" = "Alice Smith" ; String field name
    'score * 2' = 60           ; Expression field name
}

; Accessing fields
user.name                       ; Token access
user.#status#active            ; Tag field access
user."Full Name"               ; String field access
user.'score * 2'               ; Expression field access

; Positional fields
coords = {10, 20, 30}          ; Three unnamed fields
mixed = {x=5, 10, y=15}        ; Mix of named and unnamed
```

Each field also has a positional index accessible with `#`. Indexing is zero-based and works regardless of whether fields are named or unnamed. Assignment to an index beyond the structure's size normally fails, but strong assignment (`*=`) extends the structure to accommodate the index.

## Spread Operations and Structure Assembly

Spread operators allow composing new structures from existing ones. The spread incorporates all fields from a source structure, with variants controlling conflict resolution. The basic spread (`...`) applies all fields, strong spread (`..*`) creates sticky fields that resist overwriting, and weak spread (`..?`) only adds missing fields.

When spreading multiple structures, fields are applied in source order. Named field conflicts are resolved by assignment strength - strong beats normal beats weak. Unnamed fields never conflict; they accumulate in order from each spread source. The spread operation preserves field ordering within each source structure.

```comp
base = {x=1, y=2, mode="default"}
overlay = {y=3, z=4, mode*="fixed"}

; Basic spreading with conflicts
merged = {...base, ...overlay}
; Result: {x=1, y=3, z=4, mode="fixed"}

; Strong spread dominates
locked = {..*base, y=99}
; Result: {x=1, y=2, mode="default"} - strong spread resists override

; Weak spread for defaults
config = {
    port = 8080
    ..?{port=3000, host="localhost", timeout=30}
}
; Result: {port=8080, host="localhost", timeout=30}

; Unnamed fields accumulate
arrays = {...{1, 2}, ...{3, 4}}
; Result: {1, 2, 3, 4}
```

The spread operators work identically in all contexts - structure literals, function parameters, and shape definitions. This consistency makes them predictable tools for structure composition.

## Assignment Operators and Field Manipulation

Assignment in Comp creates new structures rather than modifying existing ones. The assignment operators control how conflicts are resolved when the same field is set multiple times. Normal assignment (`=`) overwrites, strong assignment (`*=`) creates persistent values, and weak assignment (`?=`) only sets undefined fields.

Deep field assignment creates new nested structures at each level, preserving immutability throughout the hierarchy. The assignment target determines where the value goes - local temporaries with `$`, output structure fields, or namespace structures like `!ctx`.

```comp
; Field override behavior
config = {
    port *= 8080        ; Strong - resists override
    host = "localhost"  ; Normal - can be overwritten
    timeout ?= 30       ; Weak - only if undefined
    
    port = 3000        ; Ignored due to strong assignment
    host = "0.0.0.0"   ; Overwrites normal assignment
}

; Deep assignment preserves immutability
tree = {left={value=1}, right={value=2}}
tree.left.value = 10
; Creates new structures: {...tree, left={...tree.left, value=10}}

; Assignment targets
!func :example = {
    $temp = 5                    ; Local temporary
    result = :compute            ; Output field
    !ctx.setting = "value"       ; Context namespace
    $data.field = 10            ; New structure in temporary
}
```

## Destructured Assignment

Destructured assignment extracts multiple fields from a structure in a single statement. Named fields are extracted by name while unnamed fields are extracted positionally. This provides a concise way to unpack structures into individual variables or fields.

```comp
; Extract named fields
{name, age, city} = user
; Equivalent to: name=user.name, age=user.age, city=user.city

; Extract with renaming
{name=username, age=years} = user
; Creates: username=user.name, years=user.age

; Mix named and positional
{x, y, label=name} = point
; Gets first two unnamed fields as x,y and 'label' field as name

; Nested destructuring
{user={name, email}, status} = response
; Extracts nested fields directly

; With defaults using fallback
{port=config.port | 8080, host=config.host | "localhost"} = {}
```

Destructured assignment is particularly useful when working with function returns that provide multiple values, or when extracting configuration from nested structures.

## Field Deletion

Removing fields from structures requires creating new structures without those fields. Since structures are immutable, there's no direct deletion - only construction of new structures missing certain fields. Shape morphing provides the cleanest approach for controlled field removal.

```comp
; Remove fields via shape morphing
!shape ~PublicUser = {name ~str, email ~str}  ; No password field
user = {name="Alice", email="a@example.com", password="secret"}
public = user ~ PublicUser  ; Result: {name="Alice", email="a@example.com"}

; Explicit construction for simple cases
original = {x=1, y=2, z=3, temp="remove"}
cleaned = {x=original.x, y=original.y, z=original.z}

; Conditional field inclusion
result = {
    id = data.id
    ..?(data.is_public ?? {name=data.name email=data.email} | {})
}
```

The pattern of using shapes to define "public" versions of structures is idiomatic in Comp, providing type safety along with field filtering.

## Lazy Evaluation

Lazy structures delay computation until fields are accessed. Created with `[]` brackets instead of `{}`, they behave like generators that compute values on demand. Once a field is computed, its value is cached for future access. After full evaluation, a lazy structure behaves identically to a regular structure.

Lazy structures capture their creation context - local variables, namespace values, and function parameters are frozen at creation time. This allows lazy computations to reference values that may change or go out of scope after creation.

```comp
; Lazy structure delays expensive operations
expensive = [
    summary = :compute_summary
    analysis = :deep_analysis
    report = :generate_report
]
; No computation happens yet

value = expensive.summary  ; Only computes summary field

; Context capture
!func :create_processor ~{multiplier} = {
    ; Context captured when [] is created
    processor = [
        doubled = .. * multiplier * 2
        tripled = .. * multiplier * 3
    ]
    processor  ; Returns lazy structure with captured multiplier
}

; Lazy evaluation with shapes
data = [
    field1 = :expensive1
    field2 = :expensive2
    field3 = :expensive3
    extra = :not_needed
] ~ {field1, field2}  ; Only computes field1 and field2
```

When a lazy structure is morphed to a shape that requires only specific fields, computation stops once those fields are resolved. This enables efficient partial evaluation of complex structures.

## Structure Comparison and Iteration

Structures can be compared for equality and ordering. Equality (`==`) checks structural equivalence - named fields must match by name and value (regardless of order), while unnamed fields must match by position. Ordering (`<`, `>`) uses lexicographic comparison, first comparing matched named fields alphabetically, then positional fields left-to-right.

The standard library provides comprehensive structure operations through the `struct/` module. These functions enable field inspection, filtering, transformation, and analysis without breaking immutability.

```comp
; Equality ignores named field order
{x=1, y=2} == {y=2, x=1}                ; true
{1, 2, 3} == {1, 2, 3}                  ; true
{x=1, 2} == {2, x=1}                    ; false - positional order matters

; Ordering is deterministic
{a=1, z=3} < {a=2, b=1}                 ; true - 'a' field compared first
{x=1} < {x=1, y=2}                      ; true - subset is less

; Structure operations via standard library
!import struct/ = std "core/struct"

data -> :struct/field_names             ; ["name", "age", "status"]
data -> :struct/has_field "email"       ; true or false
data -> :struct/filter .{value > 0}     ; Keep positive fields
data -> :struct/map_fields .{:str/upper} ; Transform all fields
```

## Advanced Structure Patterns

Complex structures often combine multiple composition techniques. Template functions generate structures with computed fields. Conditional spreading includes fields based on runtime conditions. Nested structures maintain immutability through all levels.

```comp
; Template function for consistent structure creation
!func :create_response ~{status, data} = {
    status = status
    data = data
    timestamp = :time/now
    metadata = {
        version = "1.0"
        ..?(status >= 400 ?? {error=true} | {})
    }
}

; Conditional field inclusion
user_view = {
    id = user.id
    name = user.name
    ..?(is_admin ?? {email=user.email, role=user.role} | {})
    ..?(is_self ?? {preferences=user.preferences} | {})
}

; Structure transformation pipeline
raw_data 
  -> :validate
  -> {.. validated=true timestamp=:time/now}
  -> :enhance_with_metadata
  -> {.. checksum=:calculate_checksum}
```

## Design Principles

The structure system embodies core Comp principles that guide its design. Immutability ensures predictable behavior and enables safe parallelism. Unified representation means arrays, records, and hybrid collections use the same structure type. Flexible field naming accommodates any data source naturally. Order preservation maintains structure and enables positional access. Compositional operations through spreading and morphing build complex structures from simple pieces.

These principles create a structure system that handles real-world data elegantly. Whether working with JSON APIs, database records, or internal computations, structures provide a consistent, powerful abstraction for data manipulation.