# Tag System

*Design for Comp's hierarchical enumeration and polymorphic dispatch system*

## Overview

Tags are build-time tokens that serve as values, types, and dispatch mechanisms. They form hierarchical taxonomies that enable polymorphic behavior, provide enumerated constants, and create extensible categorization systems. Tags are always prefixed with `#` when referenced and use reversed hierarchy notation where the most specific part comes first.

The tag system bridges multiple roles - they work as simple enumerations, as type markers that influence shape matching, and as dispatch keys for polymorphic functions. Tags are declarative entities that are fully resolved and validated at module build time, ensuring type safety and enabling build-time optimizations. This versatility makes them fundamental to Comp's approach to categorization and polymorphism. For information about how tags integrate with shape validation, see [Shapes, Units, and Type System](shape.md).

The tag system embodies several key design principles that guide its use throughout Comp. Tags provide hierarchical organization without class inheritance complexity. They enable polymorphic dispatch through structural matching rather than virtual methods. The reversed hierarchy notation puts the most important information first. Automatic value generation reduces boilerplate while maintaining flexibility. Cross-module extension allows domain specialization without fragmenting the ecosystem.

Tags bridge the gap between simple enumerations and complex type hierarchies. They provide just enough structure for real-world categorization needs while remaining simple enough to reason about. The consistent `#` prefix makes them visually distinct in code, and their multiple roles as values, types, and dispatch keys create a unified approach to categorization throughout the language. For details about the primitive types that tags can represent, see [Core Types](type.md).

## Tag Definition and Hierarchy

Tags are defined using the `!tag` keyword, creating hierarchical structures where each tag can have both a value and children. The `#` prefix must be used consistently on each tag name in the definition. When the same tag name appears multiple times in a definition, the last assignment wins - there's no concept of strong or weak assignment for tag definitions.

Tag values can be any build-time constant - numbers, strings, or even other tags. Tags without explicit values cannot be automatically converted from values but can still be used as markers and for dispatch. A tag can simultaneously have a value and children, and even the root of a hierarchy can carry a value.

Tag definitions support multiple definition styles that can be mixed within the same module for flexibility and readability:

```comp
; Traditional nested style
!tag #status = unknown {
    #active = 1
    #inactive = 0
    #pending           ; No value - used as marker only
    #error = -1 {
        #timeout = -100
        #network = -200
        #parse            ; Child without value
    }
}

; Flat top-down style - useful for long paths
!tag #status = unknown
!tag #status.error = -1
!tag #status.error.timeout = -100
!tag #status.error.network = -200
!tag #status.error.parse
!tag #status.active = 1
!tag #status.inactive = 0
!tag #status.pending

; Mixed style - combine approaches as appropriate
!tag #priority = {
    #low = 1
    #medium = 2
    #high = 3
}
!tag #priority.critical = 99       ; Add to existing hierarchy
!tag #priority.debug = 0           ; Another addition

; Multiple definitions with same root - merged together
!tag #color = {#red = 1 #green = 2}
!tag #color = {#blue = 3}          ; Extends color with blue
```

All definition styles are equivalent and produce the same hierarchy. Choose the style that best fits the context - nested for compact definitions, flat for long paths, and mixed for flexibility.

## Tag Reference and Notation

Tags are referenced using reversed hierarchy notation with `.` as the separator for hierarchy levels. The most specific part comes first, with parent components added only when disambiguation is needed. Partial names automatically match if unambiguous - for example, `#cat` will match `#animal.pet.cat` if there's only one tag named "cat" in the hierarchy. When tags are imported from other modules, the full reference includes the module namespace using `/` as the separator.

```comp
; Local hierarchy references
@status = #timeout.error.status
@parent = #error.status         ; Parent of timeout
@root = #status                 ; Root with value "unknown"

; Short forms when unique - partial name matching
state = #active                    ; Matches #status.active if unambiguous
error = #timeout                   ; Matches #error.timeout if unique
pet = #cat                         ; Matches #animal.pet.cat if only one 'cat'

; Disambiguation with parent context when needed
@color = #red.color                ; If #red and #red.color both exist
@fruit = #red.fruit                ; Specify which 'red' is meant

; Cross-module references with namespace
@imported = #active.status/other   ; Tag from "other" module
@std-tag = #error/std              ; Tag from standard library

; Full reference format: #tag.hierarchy/module
#specific.parent.root/namespace
```

The reference format follows the pattern `#tag.hierarchy/module` where:
- `tag` is the most specific tag name (leaf)
- `hierarchy` (optional) provides parent context for disambiguation
- `module` (optional) specifies the source module namespace
- `.` separates hierarchy levels (child.parent.grandparent)
- `/` separates tag hierarchy from module namespace

Partial name matching uses suffix matching from the tag's full path. The reference `#red` matches any tag whose full path ends with "red" (like `color.red`), and `#red.color` matches any tag ending with `color.red`. Matches must be unambiguous - if multiple tags match the partial name, an error is raised.

## Automatic Value Generation

The tag system supports automatic value generation through pure functions that compute values for each tag in a hierarchy. These functions receive contextual information about each tag and generate appropriate values. The `tag/` standard library module provides common generation functions.

The context passed to generation functions includes the tag's name, its position among siblings, parent values, and sibling values. This enables sophisticated generation patterns like sequential numbering, bit flags, or string derivation from names.

```comp
!import /tag = std "core/tag"

; Use standard generators
!tag #color {|name/tag} = {
    #red              ; Value: "red"
    #green            ; Value: "green"
    #blue             ; Value: "blue"
}

!tag #permission {|bitflag/tag} = {
    #read             ; Value: 1 (1 << 0)
    #write            ; Value: 2 (1 << 1)
    #execute          ; Value: 4 (1 << 2)
    #admin = 7        ; Explicit value overrides generator
}

; Custom generator function
!pure
!func |enum-from-100 ~{ctx} = {
    parent-value + (index + 1) * 100
}

!tag #error = 0 {|enum-from-100} = {
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
1 ~#status              ; Returns #active (since active = 1)
99 ~#priority           ; Returns #critical
42 ~#status             ; Fails - no status tag with value 42

; Tag to value extraction
#active ~num            ; Returns 1
#pending ~num           ; Fails - pending has no value
#critical ~str          ; Returns "99" (with type conversion)

; Automatic morphing in shapes
!shape ~response = {
    status #status
    priority #priority
}

({1 99} ~response)
; Result: {status=#active priority=#critical}
```

This automatic casting makes tags seamless when working with external data sources that use numeric or string codes. JSON APIs returning status codes, database enums, and configuration files can all map naturally to tag hierarchies.

## Tag Equality and Ordering

Tags support equality and ordering comparison operators. Equality (`==`, `!=`) compares tags by identity - two tag references are equal if they refer to the same tag definition. This means tag aliases (different names referring to the same tag) compare as equal.

Ordering operators (`<`, `>`, `<=`, `>=`) establish a lexicographical sort order based on tag names. Tags are compared by their leaf name first, and ties are broken by walking up the hierarchy comparing parent names. This enables natural sorting of tagged data while remaining simple and deterministic.

```comp
; Equality compares by identity
#active == #active                  ; true - same tag
#yes = #true                        ; Create alias
#yes == #true                       ; true - aliases compare equal
#active == #inactive                ; false - different tags

; Lexicographical ordering by name
#active < #inactive                 ; true - "active" < "inactive"
#red < #green < #blue              ; true - alphabetical order

; Ties walk up hierarchy
#alpha.x < #beta.x                  ; true - "alpha" < "beta" (parent comparison)
#timeout.error < #parse.error       ; true - "timeout" < "parse" (sibling comparison)

; Cross-hierarchy comparisons use root names
#active.status < #low.priority      ; Depends on "status" vs "priority"
```

Tag comparison is always deterministic and never fails. For hierarchical relationship testing (parent-child relationships), use functions from the `tag/` standard library like `|is-parent` or `|get-parent` rather than comparison operators.

## Polymorphic Dispatch

Tags are the primary mechanism for polymorphic function dispatch in Comp. Shape definitions that include tag fields gain specificity scores based on the tag hierarchy, allowing functions to specialize behavior for specific tags while providing fallbacks for parent categories.

During dispatch, more specific tags (deeper in the hierarchy) score higher than general ones. This enables elegant patterns where general handlers can be progressively specialized without modifying existing code. For comprehensive information about function dispatch and polymorphic patterns, see [Functions and Blocks](function.md).

```comp
!func |handle ~{event} = {Generic status handler}
!func |handle ~{event #error} = {Error status handler}
!func |handle ~{event #network.error} = {Network error specialist}

; Dispatch examples
({event=#active} |handle)        ; "Generic status handler"
({event=#parse.error} |handle)   ; "Error status handler"
({event=#network.error} |handle) ; "Network error specialist"
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
!import /base = comp "./base.comp"

!tag #media += {
    #image {#svg #webp}        ; Add to existing branch
    #document {#pdf #epub}     ; Add new branch
}

; Usage - extended tags work everywhere
@icon = #svg.image.media
(@icon |process-media/base)      ; Base functions handle extended tags
```

Extended tags maintain full compatibility with parent modules. Functions expecting parent tags can receive extended ones, enabling specialization without breaking compatibility. For detailed information about module organization and cross-module coordination, see [Modules, Imports, and Namespaces](module.md).

## Standard Library Tag Functions

The `tag/` module provides comprehensive utilities for working with tag hierarchies. These functions enable iteration, introspection, and manipulation of tag structures at runtime.

```comp
!import /tag = std "core/tag"

; Iterate over hierarchy
(#status |children/tag)         ; Returns {#active #inactive #pending #error}
(#status |descendants/tag)      ; Returns all tags in hierarchy
(#status |walk/tag {          ; Visit each tag with callback
    (Tag: ${name}, Value: ${value ?? none} |log)
})

; Introspection
(#timeout.error.status |parent/tag)     ; Returns #error.status
(#error.status |depth/tag)              ; Returns 1
(#error.status |path/tag)               ; Returns [status error]
(#high.priority |value/tag)             ; Returns 99

; Relationships
[#timeout.error.status |is-a parent=#status]     ; Returns #true (checks if child is descendant of parent)
(|is-parent/tag parent=#status child=#error.status)     ; Returns #true
(|common-ancestor/tag a=#timeout.error b=#active) ; Returns #status

; Value lookup
(|find-by-value/tag root=#status value=1)            ; Returns #active
(|all-with-value/tag root=#priority value=3)         ; Returns tags with value 3
```

## Tag Aliasing and Composition

Tags can be aliased for convenience and composed into union types for flexible categorization. Aliases create local names for tags from other modules, while composition enables values that can match multiple tag categories.

```comp
; Simple aliasing
!alias #error = #error.status
!alias #critical = #critical.priority

; Union types for flexible matching
!tag #result = #active | #inactive | #pending
!tag #problem = #error.status | #critical.priority

; Usage in shapes
!shape ~task-status = {
    state #result         ; Must be active, inactive, or pending
    issues #problem[]     ; Array of errors or critical priorities
}
```

## Units as Tags

Tags provide semantic typing for numeric and string values through the unit system. Units are implemented as tag hierarchies, enabling automatic conversion within families while preventing nonsensical operations.

```comp
; Units are tags with conversion values
!tag #length = {
    #meter = 1.0
    #kilometer = 0.001
    #foot = 3.28084
    #mile = 0.000621371
}

; Usage
distance = 5#kilometer
in-meters = distance ~num#meter    ; 5000
in-miles = distance ~num#mile      ; ~3.1

; Operations maintain units
total = 5#meter + 10#foot          ; Result in meters
speed = 100#kilometer / 1#hour     ; Compound unit
```
