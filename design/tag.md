# Tag System

*Design for Comp's hierarchical enumeration and polymorphic dispatch system*

## Overview

Tags are compile-time tokens that serve as values, types, and dispatch mechanisms. They form hierarchical taxonomies that enable polymorphic behavior, provide enumerated constants, and create extensible categorization systems. Tags are always prefixed with `#` when referenced and can carry optional values while maintaining their hierarchical relationships.

The tag system bridges multiple roles - they work as simple enumerations, as type markers that influence shape matching, and as dispatch keys for polymorphic functions. Tags are declarative entities that are fully resolved and validated at module build time, ensuring type safety and enabling compile-time optimizations. This versatility makes them fundamental to Comp's approach to categorization and polymorphism.

## Tag Definition and Hierarchy

Tags are defined using the `!tag` operator, creating hierarchical structures where each tag can have both a value and children. The `#` prefix must be used consistently on each tag name in the definition. When the same tag name appears multiple times in a definition, the last assignment wins - there's no concept of strong or weak assignment for tag definitions.

Tag values can be any compile-time constant - numbers, strings, or even other tags. Tags without explicit values cannot be automatically converted from values but can still be used as markers and for dispatch. A tag can simultaneously have a value and children, and even the root of a hierarchy can carry a value.

```comp
!tag #status = "unknown" {
    #active = 1
    #inactive = 0
    #pending           ; No value - used as marker only
    #error = -1 {
        #timeout = -100
        #network = -200
        #parse            ; Child without value
    }
}

!tag #priority = {
    #low = 1
    #medium = 2
    #high = 3
    #critical = 3      ; Duplicate name - this definition wins
    #critical = 99     ; Last assignment wins: critical = 99
}
```

Tags are referenced through their full hierarchical path using `#` as the separator. The language understands the parent-child relationships and uses them for matching and dispatch specificity.

```comp
$status = #status#error#timeout
$parent = #status#error         ; Parent of timeout
$root = #status                 ; Root with value "unknown"
```

## Automatic Value Generation

The tag system supports automatic value generation through pure functions that compute values for each tag in a hierarchy. These functions receive contextual information about each tag and generate appropriate values. The `tag/` standard library module provides common generation functions.

The context passed to generation functions includes the tag's name, its position among siblings, parent values, and sibling values. This enables sophisticated generation patterns like sequential numbering, bit flags, or string derivation from names.

```comp
!import tag/ = std "core/tag"

; Use standard generators
!tag #color {:tag/name} = {
    #red              ; Value: "red"
    #green            ; Value: "green"
    #blue             ; Value: "blue"
}

!tag #permission {:tag/bitflag} = {
    #read             ; Value: 1 (1 << 0)
    #write            ; Value: 2 (1 << 1)
    #execute          ; Value: 4 (1 << 2)
    #admin = 7        ; Explicit value overrides generator
}

; Custom generator function
!pure :enum_from_100 = {ctx ->
    ctx.parent_value + (ctx.index + 1) * 100
}

!tag #error = 0 {:enum_from_100} = {
    #network          ; Value: 100
    #database         ; Value: 200
    #validation       ; Value: 300
}
```

The generation function is called for each tag that doesn't have an explicit value. Explicitly assigned values always override generated ones, and subsequent generated values account for the explicit assignments.

## Type Casting and Value Morphing

Tags with values support bidirectional casting between tags and their value types. Tag values are not exclusive - multiple tags can share the same value, which is common in status codes and error hierarchies. When casting from a value to a tag where multiple tags share that value, the first-defined tag in the hierarchy wins. Casting from tags to values extracts the associated value or fails if the tag has no value.

The morphing operators (`~`, `*~`, `?~`) handle conversions between primitive types (strings, numbers) and their corresponding tags. This bidirectional morphing enables seamless integration with external data that uses numeric codes or string identifiers.

```comp
; Value to tag casting
1 ~ #status              ; Returns #status#active (since active = 1)
99 ~ #priority           ; Returns #priority#critical
42 ~ #status             ; Fails - no status tag with value 42

; Tag to value extraction
#status#active ~ num     ; Returns 1
#status#pending ~ num    ; Fails - pending has no value
#priority#critical ~ str ; Returns "99" (with type conversion)

; Automatic morphing in shapes
!shape ~Response = {
    status #status
    priority #priority
}

{1, 99} ~ Response
; Result: {status=#status#active, priority=#priority#critical}
```

This automatic casting makes tags seamless when working with external data sources that use numeric or string codes. JSON APIs returning status codes, database enums, and configuration files can all map naturally to tag hierarchies.

## Hierarchical Comparison and Ordering

Tags support comparison operators that respect their hierarchical structure. The ordering operators (`<`, `>`, `<=`, `>=`) establish a total order based on the hierarchy depth and definition order. Parents are less than their children, and siblings are ordered by their definition sequence.

```comp
; Hierarchical ordering
#status < #status#error              ; true - parent < child
#status#error < #status#error#timeout ; true - parent < child
#status#active < #status#inactive     ; true - definition order

; Siblings maintain definition order
#priority#low < #priority#medium < #priority#high  ; true

; Cross-hierarchy comparison uses root order then depth
#status#active < #priority#low       ; Depends on root definition order
```

This ordering enables natural sorting of tagged data and supports range-based operations in the standard library. The comparison is always deterministic and never fails, even for tags from different hierarchies.

## Polymorphic Dispatch

Tags are the primary mechanism for polymorphic function dispatch in Comp. Shape definitions that include tag fields gain specificity scores based on the tag hierarchy, allowing functions to specialize behavior for specific tags while providing fallbacks for parent categories.

During dispatch, more specific tags (deeper in the hierarchy) score higher than general ones. This enables elegant pattern where general handlers can be progressively specialized without modifying existing code.

```comp
!func :handle ~{event #status} = {
    "Generic status handler"
}

!func :handle ~{event #status#error} = {
    "Error status handler"
}

!func :handle ~{event #status#error#network} = {
    "Network error specialist"
}

; Dispatch examples
{event=#status#active} -> :handle        ; "Generic status handler"
{event=#status#error#parse} -> :handle   ; "Error status handler"
{event=#status#error#network} -> :handle ; "Network error specialist"
```

## Cross-Module Tag Extension

Tags can be extended across module boundaries, allowing domain-specific categorizations while maintaining interoperability. Extensions add new leaves to existing hierarchies, and the extended tags are fully compatible with the original hierarchy for matching and dispatch.

When extending tags from another module, the new tags become part of your module's tag namespace while maintaining their relationship to the imported hierarchy. Values in extensions can use the same auto-generation functions as the parent hierarchy.

```comp
; base.comp - defines core tags
!tag #media = {
    #image {#jpeg #png #gif}
    #video {#mp4 #webm}
    #audio {#mp3 #ogg}
}

; extended.comp - adds domain-specific tags
!import base/ = comp "./base.comp"

!tag #media += {
    #image {#svg #webp}        ; Add to existing branch
    #document {#pdf #epub}     ; Add new branch
}

; Usage - extended tags work everywhere
$icon = #media#image#svg
base:process_media($icon)      ; Base functions handle extended tags
```

Extended tags maintain full compatibility with parent modules. Functions expecting parent tags can receive extended ones, enabling specialization without breaking compatibility.

## Standard Library Tag Functions

The `tag/` module provides comprehensive utilities for working with tag hierarchies. These functions enable iteration, introspection, and manipulation of tag structures at runtime.

```comp
!import tag/ = std "core/tag"

; Iterate over hierarchy
#status -> :tag/children         ; Returns {#active #inactive #pending #error}
#status -> :tag/descendants      ; Returns all tags in hierarchy
#status -> :tag/walk .{          ; Visit each tag with callback
    "Tag: ${name}, Value: ${value | 'none'}" -> :log
}

; Introspection
#status#error#timeout -> :tag/parent     ; Returns #status#error
#status#error -> :tag/depth              ; Returns 1
#status#error -> :tag/path               ; Returns ["status", "error"]
#priority#high -> :tag/value             ; Returns 99

; Relationships
:tag/is_parent #status #status#error     ; Returns #true
:tag/common_ancestor #status#error#timeout #status#active ; Returns #status

; Value lookup
:tag/find_by_value #status 1            ; Returns #status#active
:tag/all_with_value #priority 3         ; Returns tags with value 3
```

## Tag Aliasing and Composition

Tags can be aliased for convenience and composed into union types for flexible categorization. Aliases create local names for tags from other modules, while composition enables values that can match multiple tag categories.

```comp
; Simple aliasing
!alias #error = #status#error
!alias #critical = #priority#critical

; Union types for flexible matching
!tag #result = #status#active | #status#inactive | #status#pending
!tag #problem = #status#error | #priority#critical

; Usage in shapes
!shape ~TaskStatus = {
    state #result         ; Must be active, inactive, or pending
    issues #problem[]     ; Array of errors or critical priorities
}
```

## Design Principles

The tag system embodies several key design principles that guide its use throughout Comp. Tags provide hierarchical organization without class inheritance complexity. They enable polymorphic dispatch through structural matching rather than virtual methods. The automatic value generation reduces boilerplate while maintaining flexibility. Cross-module extension allows domain specialization without fragmenting the ecosystem.

Tags bridge the gap between simple enumerations and complex type hierarchies. They provide just enough structure for real-world categorization needs while remaining simple enough to reason about. The consistent `#` prefix makes them visually distinct in code, and their multiple roles as values, types, and dispatch keys create a unified approach to categorization throughout the language.