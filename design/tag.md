# Tag System

Tags are build-time tokens that serve as values, types, and dispatch mechanisms.
They form hierarchical namespaces that enable polymorphic behavior, provide
enumerated constants, and create extensible categorization systems. Tags are
always prefixed with `#` when referenced.

The tag system bridges multiple roles - they work as simple enumerations, as
type markers that influence shape matching, which can drive polymorphic function
dispatch. Tags are declarative entities that are fully resolved and validated at
module build time. This versatility makes them fundamental to Comp's approach to
categorization and polymorphism. For information about how tags integrate with
shape validation, see [Shapes, Units, and Type System](shape.md).

Tags can also be defined with a constant value at definition. This is primarily
used to assist with serialization to other formats outside of Comp. Tags from
one module can also be extended inside other modules and remain interchangeable
with the base definitions.

Tags are defined at the module level of code. They are defined and resolved and
are constant before any code in the module is evaluated.


## Tag Definition and Hierarchy

Tags are defined using the `tag` keyword in a module. The `#` prefix must be
used consistently on each tag name in the definition and reference. When the
same tag name appears multiple times in a definition, the last assignment wins.

Tags can be marked as module-private by adding a trailing `&` to the tag name
(e.g., `tag #internal-status& = {...}`). Module-private tags are only accessible
within the defining module and cannot be referenced by code in other modules.
For comprehensive information about module privacy, see [Modules, Imports, and
Namespaces](module.md).

Tag values can be any build-time constant - numbers, strings, or even other
tags. Tags without explicit values cannot be automatically converted from values
but can still be used as markers and for dispatch. A tag can simultaneously have
a value and children, and even the root of a hierarchy can carry a value.

There are two syntaxes for defining tag hierarches. They can be defined as a
hierarchical set of tag definitions. They can also be defined as a flat list of
fully qualified names. Both styles have advantages for different complexities of
tag depths and values. The styles can be intermixed.

```comp
; Traditional nested style
!tag #status {
    #active 1
    #inactive 0
    #pending           ; No value - used as marker only
    #error -1 {
        #timeout -100
        #network -200
        #parse            ; Child without value
    }
}

; Flat top-down style - useful for long paths
!tag #status unknown
!tag #status.error -1
!tag #status.error.timeout -100
!tag #status.error.network -200
!tag #status.error.parse
!tag #status.active 1
!tag #status.inactive 0
!tag #status.pending

; Mixed style - combine approaches as appropriate
!tag #priority {
    #low 1
    #medium 2
    #high 3
}
!tag #priority.critical 99       ; Add to existing hierarchy
!tag #priority.debug 0           ; Another addition

; Multiple definitions with same root - last definition wins
!tag #color {#red 1 #green 2}
!tag #color {#blue 3}          ; Replaces color with just blue
!tag #color.yellow 4             ; Adds yellow to color
```

All definition styles are equivalent and produce the same hierarchy. Choose the
style that best fits the context - nested for compact definitions, flat for long
paths, and mixed for flexibility. Note that when the same tag path is assigned
multiple times, the last assignment wins - this is different from extension
which merges hierarchies.

When the tag value is more than a simple expression (a literal with simpler
operators) it must be wrapped in parenthesis. This is required by the grammar to
disambiguate it from the optional list of child tags.

```comp
!tag #fancy (["cat" |repeat3]) {#child}
!tag #numbers ({one=1 two=2}) {#three #four}
```

## Automatic Value Generation

The tag system supports automatic value generation through pure functions that
compute values for each tag in a hierarchy. These functions receive contextual
information about each tag and generate appropriate values. The `tag/` standard
library module provides common generation functions.

The context passed to generation functions includes the tag's name, its position
among siblings, parent values, and sibling values. This enables sophisticated
generation patterns like sequential numbering, bit flags, or string derivation
from names.

```comp
!import /tag std "core/tag"

; Use standard generators
!tag #color name/tag {
    #red         ; Value: "red"
    #green       ; Value: "green"
    #blue        ; Value: "blue"
}

!tag #permission bitflag/tag {
    #read        ; Value: 1 (1 << 0)
    #write       ; Value: 2 (1 << 1)
    #execute     ; Value: 4 (1 << 2)
    #admin 7     ; Explicit value overrides generator
}

; Custom generator function
!pure !func enum-from-100 ~{ctx} = {
    parent-value + (index + 1) * 100
}

!tag #error enum-from-100 {
    #network     ; Value: 100
    #database    ; Value: 200
    #validation  ; Value: 300
}
```

The generation function is called for each tag that doesn't have an explicit
value. Explicitly assigned values always override generated ones, and subsequent
generated values account for the explicit assignments.

## Type Casting and Value Morphing

Tags with values support bidirectional morphing between tags and their value
types. Tag values are not exclusive - multiple tags can share the same value,
which is common in status codes and error hierarchies. When morphing from a
value to a tag where multiple tags share that value, the first-defined tag in
the hierarchy wins. Morphing from tags to values extracts the associated value
or fails if the tag has no value.

The morphing operators (`~`, `*~`, `?~`) handle conversions between primitive
types (strings, numbers) and their corresponding tags. This bidirectional
morphing enables seamless integration with external data that uses numeric codes
or string identifiers.

```comp
; Value to tag morphing
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

This automatic casting makes tags seamless when working with external data
sources that use numeric or string codes. JSON APIs returning status codes,
database enums, and configuration files can all map naturally to tag
hierarchies.

## Tag Equality and Ordering

Tags support equality and ordering comparison operators. Equality (`==`, `!=`)
compares tags by identity - two tag references are equal if they refer to the
same tag definition. This means tag aliases (different names referring to the
same tag) compare as equal.

Ordering operators (`<`, `>`, `<=`, `>=`) establish a lexicographical sort order
based on tag names. Tags are compared by their leaf name first, and ties are
broken by walking up the hierarchy comparing parent names. This enables natural
sorting of tagged data while remaining simple and deterministic.

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

Tag comparison is always deterministic and never fails. For hierarchical
relationship testing (parent-child relationships), use functions from the `tag/`
standard library like `|is-parent` or `|get-parent` rather than comparison
operators.

## Polymorphic Dispatch

Tags are the primary mechanism for polymorphic function dispatch in Comp. Shape
definitions that include tag fields gain specificity scores based on the tag
hierarchy, allowing functions to specialize behavior for specific tags while
providing fallbacks for parent categories.

During dispatch, more specific tags (deeper in the hierarchy) score higher than
general ones. This enables elegant patterns where general handlers can be
progressively specialized without modifying existing code. For comprehensive
information about function dispatch and polymorphic patterns, see [Functions and
Blocks](function.md).

```comp
!func handle ~{event} (generic-status-handler())
!func handle ~{event #error} (error-status-handler())
!func handle ~{event #network.error} (network-error-specialist())

; Dispatch examples
{event=#active} | handle()        ; "Generic status handler"
{event=#parse.error} | handle()   ; "Error status handler"
{event=#network.error} | handle() ; "Network error specialist"
```

## Cross-Module Tag Extension

Tags can be extended across module boundaries using the `extends` keyword,
allowing domain-specific categorizations while maintaining interoperability.
Extensions add new leaves to existing hierarchies, and the extended tags are
fully compatible with the original hierarchy for matching and dispatch.

When extending tags from another module, you define a local tag name that
extends the imported tag hierarchy. The extended tags become part of your
module's tag namespace while maintaining their relationship to the imported
hierarchy. The syntax uses `tag #local-name extends #parent-tag/module =
{children}` where the local name becomes the root of your extended hierarchy.

```comp
; base.comp - defines core tags
!tag #media {
    #image {#jpeg #png #gif}
    #video {#mp4 #webm}
    #audio {#mp3 #ogg}
}

; extended.comp - adds domain-specific tags using extends
!import base comp "./base.comp"

; Extend media with additional formats
!tag #media extends #media/base = {
    #image {#svg #webp}        ; Add to existing image branch
    #document {#pdf #epub}     ; Add new top-level branch
}

; Usage - extended tags work everywhere
let icon = #svg.image.media
(icon | process-media/base())      ; Base functions handle extended tags

; Real-world example: Extending builtin fail tags
!tag #fail extends #fail/builtin {
    #interface      ; Connection errors
    #database       ; Database file errors
    #data           ; Data type conversion errors
    #operation      ; SQL operation errors
}
```

The `extends` syntax creates a local hierarchy that inherits from the parent.
Extended tags maintain full compatibility with parent modules - functions
expecting parent tags can receive extended ones, enabling specialization without
breaking compatibility. The extended hierarchy can add both new branches at any
level and new leaves to existing branches.

Extensions can also omit the value assignment to simply extend without adding
immediate children:

```comp
; Simple extension without immediate children
!tag #status extends #status/other

; Later in the same module, add children
!tag #status.custom-state 42
```

For detailed information about module organization and cross-module
coordination, see [Modules, Imports, and Namespaces](module.md).

## Standard Library Tag Functions

The `tag/` module provides comprehensive utilities for working with tag
hierarchies. These functions enable iteration, introspection, and manipulation
of tag structures at runtime.

```comp
!import tag std "core/tag"

; Iterate over hierarchy
#status | children/tag ()         ; Returns {#active #inactive #pending #error}
#status | descendants/tag ()      ; Returns all tags in hierarchy
#status | walk/tag :(            ; Visit each tag with callback
    log ("Tag: %{name}, Value: %{value ?? none}")
)

; Introspection
#timeout.error.status | parent/tag ()     ; Returns #error.status
#error.status | depth/tag ()              ; Returns 1
#error.status | path/tag ()               ; Returns [status error]
#high.priority | value/tag ()             ; Returns 99

; Relationships
#timeout.error.status | is-a parent (#status)     ; Returns #true (checks if child is descendant of parent)
is-parent/tag {parent#status child=#error.status}     ; Returns #true
common-ancestor/tag {a=#timeout.error b=#active} ; Returns #status

; Value lookup
find-by-value/tag {root=#status value=1}    ; Returns #active
all-with-value/tag {root=#priority value=3} ; Returns tags with value 3
```

## Tag Aliasing and Composition

Tags can be aliased for convenience and composed into union types for flexible
categorization. Aliases create local names for tags from other modules, while
composition enables values that can match multiple tag categories.

```comp
; Simple aliasing
alias #error #error.status
alias #critical #critical.priority

; Union types for flexible matching
!shape ~result #active | #inactive | #pending
!shape ~problem #error.status | #critical.priority

; Usage in shapes
!shape ~task-status {
    state #result         ; Must be active, inactive, or pending
    issues #problem[]     ; Array of errors or critical priorities
}
```

## Units as Tags

Tags provide semantic typing for numeric and string values through the unit
system. Units are implemented as tag hierarchies, enabling automatic conversion
within families while preventing nonsensical operations. More details are in the
[Unit](unit.md) documentation.

```comp
; Units are tags with conversion values
!tag #length {
    #meter 1.0
    #kilometer 0.001
    #foot 3.28084
    #mile 0.000621371
}

; Usage
distance = 5#kilometer
in-meters = distance ~num#meter    ; 5000
in-miles = distance ~num#mile      ; ~3.1

; Operations maintain units
total = 5#meter + 10#foot          ; Result in meters
speed = 100#kilometer / 1#hour     ; Compound unit
```
