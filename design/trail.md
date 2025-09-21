# Trail System

*Structured navigation paths through Comp data*

## Overview

Trails provide a way to represent navigation paths through data as regular structures. The `/path/` syntax is syntactic sugar that creates structures containing arrays of field names and navigation operators. These structures can be stored, passed, and manipulated like any other data, then applied to navigate or modify data using trail-aware operations.

There is no special "trail" type in Comp - trails are simply structures with a conventional shape that trail operations know how to interpret. This design keeps the language core simple while enabling powerful navigation patterns through library functions. For information about the underlying structure operations that trails build upon, see [Structures, Spreads, and Lazy Evaluation](structure.md).

The trail system embodies several key principles:

- **No special types**: Trails are just structures with conventional shapes
- **Syntactic convenience**: The `/path/` syntax generates these structures easily
- **Library interpretation**: Trail operations give meaning to trail structures  
- **Data as data**: Trails can be stored, passed, and manipulated like any value
- **Clear visual marker**: The `/` delimiters make navigation operations obvious

This design keeps the language core minimal while enabling sophisticated navigation patterns through library functions. By representing trails as ordinary structures, Comp maintains its principle that everything is data while providing convenient syntax for common operations.

## Trail Fundamentals

A trail literal using `/path/` syntax creates a structure containing an array of navigation segments. Each segment is either a field name (as a string) or a navigation operator (as a tag). This structure can be stored in variables, passed to functions, or manipulated like any other data.

```comp
; Trail literal creates a structure
@path = /users.profile.theme/
; Equivalent to approximately:
; {segments=[users profile theme]}

; Apply trail structure to data
config |get /database.host/           ; Apply trail to navigate
$in |get @path                   ; Apply stored trail variable

; Setting values through trails
data |set /user.name/ Alice          ; Navigate and set value
config |set @path new-value      ; Set using trail variable
```

The trail syntax provides convenient shorthand for creating these navigation structures. The actual structure format is an implementation detail, but conceptually it's just an array of strings and operator tags that describe how to navigate through data.

## Trail Structure and Syntax

When you write a trail literal, the language parses it into a structure. The dot separators become array boundaries, and special syntax elements become operator tags that trail operations recognize.

```comp
; Simple trail - array of field names
/users.0.email/
; Creates: {segments=[users 0 email]}

; Wildcard operator becomes a tag
/users.*.email/
; Creates: {segments=[users #trail-any email]}

; Recursive descent operator
/**.error/
; Creates: {segments=[#trail-recursive error]}

; Complex navigation with operators
/items.[price < 100].name/
; Creates structure with predicate information
```

Since trails are just structures, they can be created programmatically without using the literal syntax:

```comp
; Programmatic trail construction
@dynamic-trail = {segments=[users user-id settings]}
data |set @dynamic-trail new-settings

; Trail manipulation as regular structures
@base-trail = /api.v2/
@extended = {..@base-trail segments=[..@base-trail.segments users]}
```

## Trail Operations

Trail operations are functions that know how to interpret trail structures and apply them to data. The primary operations are `get` and `set`, but the standard library provides many trail-aware functions.

```comp
; Basic trail operations
data |get /users.profile/
data |set /users.profile/ value

; The trail structure can be manipulated
@path = /users/
@extended = @path |extend/trail profile.theme
; Results in trail structure for /users.profile.theme/
```

The standard library provides trail operations that interpret these structures. For information about the module system and standard library organization, see [Modules, Imports, and Namespaces](module.md).

```comp
!import trail = std "core/trail"

; Navigation operations interpret trail structures
{data /users.*/} |select/trail      ; Get all matches
{data /path/} |exists?/trail        ; Check existence
{data /old/ /new/} |move/trail      ; Move data between paths

; Trail structures can be analyzed and modified
/users.profile.theme/ |segments/trail    ; [users profile theme]
/users.profile/ |parent/trail            ; /users/
{/base/ /extend/} |join/trail           ; Combine trail structures
```

## Trail Composition

Since trails are just structures, they compose using normal structure operations. The language provides syntax sugar to make common compositions convenient, but underneath it's standard structure manipulation.

```comp
; Trail concatenation syntax
@api = /api/
@version = /v2/
@endpoint = /users/
@full = @api/@version/@endpoint     ; Creates combined trail structure

; This is just structure manipulation
; The `/` operator between trails combines their segment arrays

; Direct structure manipulation works too
@custom-trail = {
    segments = [..@api.segments ..@version.segments ..@endpoint.segments]
}

; Both create equivalent trail structures
data |get @full == data |get @custom-trail    ; Same navigation result
```

## Navigation Patterns

Trail operations interpret certain tags and patterns in trail structures to enable sophisticated navigation:

```comp
; Numeric indices for array access
data |get /items.0/                  ; First item
data |get /items.-1/                 ; Last item

; Wildcard selection (through functions)
data |select/trail /users.*.email/     ; All user emails

; Recursive search
data |find/trail /**.error/            ; Find at any depth

; Predicate filtering (future enhancement)
data |where/trail /users.[active].name/  ; Conditional selection
```

These patterns work because trail operations recognize special tags and structures within the trail and interpret them accordingly. The trail itself remains just data.

## Type Safety and Validation

While trails are runtime values (just structures), they can still integrate with Comp's type system. Functions can specify they expect trail-shaped structures, and operations can validate trails before applying them. For comprehensive information about the shape system and validation patterns, see [Shapes, Units, and Type System](shape.md).

```comp
; Shape for trail structures (simplified)
!shape ~trail = {
    segments ~array
}

; Functions can require trail-shaped inputs
!func |navigate ^{data ~any path ~trail} = {
    ^data |apply/trail ^path
}

; Validation of trail structures
!func |safe-navigate ~{data} ^{path} = {
    $in |if {^path |valid?/trail} {
        $in |get/trail ^path
    } {
        {#trail.fail message=Invalid trail structure}
    }
}
```
