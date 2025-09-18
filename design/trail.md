# Trail System

*Structured navigation paths through Comp data*

## Overview

Trails provide a way to represent navigation paths through data as regular structures. The `/path/` syntax is syntactic sugar that creates structures containing arrays of field names and navigation operators. These structures can be stored, passed, and manipulated like any other data, then applied to navigate or modify data using trail-aware operations.

There is no special "trail" type in Comp - trails are simply structures with a conventional shape that trail operations know how to interpret. This design keeps the language core simple while enabling powerful navigation patterns through library functions.

## Trail Fundamentals

A trail literal using `/path/` syntax creates a structure containing an array of navigation segments. Each segment is either a field name (as a string) or a navigation operator (as a tag). This structure can be stored in variables, passed to functions, or manipulated like any other data.

```comp
; Trail literal creates a structure
$path = /users.profile.theme/
; Equivalent to approximately:
; {segments=["users", "profile", "theme"]}

; The double-slash operator applies a trail structure to data
config//database.host/           ; Apply trail to navigate
data/$path                       ; Apply stored trail variable

; Setting values through trails
data//user.name/ = "Alice"      ; Navigate and set value
config/$path = new_value         ; Set using trail variable
```

The trail syntax provides convenient shorthand for creating these navigation structures. The actual structure format is an implementation detail, but conceptually it's just an array of strings and operator tags that describe how to navigate through data.

## Trail Structure and Syntax

When you write a trail literal, the language parses it into a structure. The dot separators become array boundaries, and special syntax elements become operator tags that trail operations recognize.

```comp
; Simple trail - array of field names
/users.0.email/
; Creates: {segments=["users", "0", "email"]}

; Wildcard operator becomes a tag
/users.*.email/
; Creates: {segments=["users", #trail_any, "email"]}

; Recursive descent operator
/**.error/
; Creates: {segments=[#trail_recursive, "error"]}

; Complex navigation with operators
/items.[price < 100].name/
; Creates structure with predicate information
```

Since trails are just structures, they can be created programmatically without using the literal syntax:

```comp
; Programmatic trail construction
$dynamic_trail = {segments=["users", user_id, "settings"]}
data/$dynamic_trail = new_settings

; Trail manipulation as regular structures
$base_trail = /api.v2/
$extended = {...$base_trail, segments=[...$base_trail.segments, "users"]}
```

## Trail Operations

Trail operations are functions that know how to interpret trail structures and apply them to data. The double-slash operator (`//`) is the primary way to apply trails, but it's really just syntactic sugar for calling trail operation functions.

```comp
; These are equivalent
data//users.profile/
data -> :trail/get /users.profile/

; Setting is also a function call internally
data//users.profile/ = value
data -> :trail/set /users.profile/ <- value

; The trail structure can be manipulated
$path = /users/
$extended = $path -> :trail/extend "profile.theme"
; Results in trail structure for /users.profile.theme/
```

The standard library provides trail operations that interpret these structures:

```comp
!import trail/ = std "core/trail"

; Navigation operations interpret trail structures
{data /users.*/} -> :trail/select      ; Get all matches
{data /path/} -> :trail/exists?        ; Check existence
{data /old/ /new/} -> :trail/move      ; Move data between paths

; Trail structures can be analyzed and modified
/users.profile.theme/ -> :trail/segments    ; ["users", "profile", "theme"]
/users.profile/ -> :trail/parent            ; /users/
{/base/ /extend/} -> :trail/join           ; Combine trail structures
```

## Trail Composition

Since trails are just structures, they compose using normal structure operations. The language provides syntax sugar to make common compositions convenient, but underneath it's standard structure manipulation.

```comp
; Trail concatenation syntax
$api = /api/
$version = /v2/
$endpoint = /users/
$full = $api/$version/$endpoint     ; Creates combined trail structure

; This is just structure manipulation
; The `/` operator between trails combines their segment arrays

; Direct structure manipulation works too
$custom_trail = {
    segments = [...$api.segments, ...$version.segments, ...$endpoint.segments]
}

; Both create equivalent trail structures
data/$full == data/$custom_trail    ; Same navigation result
```

## Navigation Patterns

Trail operations interpret certain tags and patterns in trail structures to enable sophisticated navigation:

```comp
; Numeric indices for array access
data//items.0/                  ; First item
data//items.-1/                 ; Last item

; Wildcard selection (through functions)
data -> :trail/select /users.*.email/     ; All user emails

; Recursive search
data -> :trail/find /**.error/            ; Find at any depth

; Predicate filtering (future enhancement)
data -> :trail/where /users.[active].name/  ; Conditional selection
```

These patterns work because trail operations recognize special tags and structures within the trail and interpret them accordingly. The trail itself remains just data.

## Type Safety and Validation

While trails are runtime values (just structures), they can still integrate with Comp's type system. Functions can specify they expect trail-shaped structures, and operations can validate trails before applying them.

```comp
; Shape for trail structures (simplified)
!shape ~Trail = {
    segments ~array
}

; Functions can require trail-shaped inputs
!func :navigate ~{data ~any, path ~Trail} = {
    data -> :trail/apply path
}

; Validation of trail structures
!func :safe_navigate ~{data, path} = {
    :if .{path -> :trail/valid?} .{
        data -> :trail/get path
    } .{
        {#fail#trail message="Invalid trail structure"}
    }
}
```

## Design Principles

The trail system embodies several key principles:

- **No special types**: Trails are just structures with conventional shapes
- **Syntactic convenience**: The `/path/` syntax generates these structures easily
- **Library interpretation**: Trail operations give meaning to trail structures  
- **Data as data**: Trails can be stored, passed, and manipulated like any value
- **Clear visual marker**: The `/` delimiters make navigation operations obvious

This design keeps the language core minimal while enabling sophisticated navigation patterns through library functions. By representing trails as ordinary structures, Comp maintains its principle that everything is data while providing convenient syntax for common operations.