# Comp Language Design

## Core Philosophy

Comp is a high-level language that treats everything as immutable structures
flowing through pipelines. 

The focus is to create composable and friendly language for developers that
allows them to focus on best practices and creating comfortable code. This is a
high level interpreted language designed to create composable and understandable
programs. Comp implements flow control, iteration, and resources with
straightforward libraries that can be reused and extended.

Key principles:

- **Super structures** - Everything is structures, and they are immutable
- **Schemas for validation** - Shapes are structres that validate and reorganize structures
- **Pipelines compose** - Operations chain together like building blocks
- **Data beats inheritance** - Structural compatibility instead of class hierarchies


## Basic Syntax

### Values and Structures

```comp
; Simple values (auto-promote to structures in pipelines)
42                          ; Number
"hello"                     ; String  
#true                       ; Boolean tag

; Structures combine named and unnamed fields
{x=10 y=20}                ; Named fields
{1 2 3}                    ; Unnamed/positional fields
{name="Alice" 30 #active}  ; Mixed

; Field access
user.name                  ; Named field
coords.#0                  ; First unnamed field (index)
data."Full Name"           ; String field name
config.'port_key'          ; Computed field name
```

### Pipelines

Pipelines chain operations left-to-right using `->`. Each operation transforms the incoming structure:

```comp
; Basic pipeline
data -> validate -> transform -> save

; Pipeline with blocks (deferred execution)
items -> filter {.score > 100}
      -> map {name = .name, value = .score * 2}
      -> sort {.value} desc
      -> first 5

; Multiple inputs/outputs
main (
    after = now - 1.week
    
    issues = "nushell/nushell"
        -> gh.list_issues
        -> filter {.created_at >= after}
    
    pull_requests = "nushell/nushell"
        -> gh.list_pulls
        -> filter {.state == "open"}
    
    {issues pull_requests}  ; Return both
)
```

### Functions

Functions transform structures. Input comes through pipeline, arguments configure behavior:

```comp
; Simple function - shape declares expected input structure
double num (num * 2)

; Function with arguments
add number value (number + value)

; Function with shape constraints
process_user {name string email string} (
    validated = name -> validate_username
    domain = email -> extract_domain
    {validated domain}
)

; Overloading by shape
render {x num y num} ("2D point at {x}, {y}")
render {x num y num z num} ("3D point at {x}, {y}, {z}")

; Usage
5 -> double                    ; Returns 10
10 -> add 5                    ; Returns 15  
{name="Alice" email="a@b.com"} -> process_user
```

### Blocks

Blocks are deferred computations, used for control flow and callbacks:

```comp
; Conditional blocks
status -> when {. == #error} (
    log "Error occurred"
    recover_gracefully
)

; Iteration blocks
items -> map item (
    item with {processed = now}
)

; Control flow with pattern matching
input -> match_shape
    point2d p ("Point at {p.x}, {p.y}")
    color c ("RGB({c.r}, {c.g}, {c.b})")
    {radius num} r ("Circle radius {r.radius}")
    else ("Unknown shape")
```

## Type System

### Shapes

Shapes define structural types through field requirements:

```comp
; Shape definition
shape user {
    name string
    email string  
    age num = 0              ; Default value
}

; Inheritance through spreading
shape admin {
    ..user                   ; Include all user fields
    permissions []
}

; Optional fields with unions
shape config {
    port num = 8080
    host string = "localhost"
    ssl bool | nil = nil     ; Optional
}
```

### Morphing

Morphing transforms structures to match shapes:

```comp
; Basic morphing
data = {name="Alice" age=30}
u = data ~ user              ; Morph to user shape

; Different morph operators
normal = data ~ shape        ; Apply defaults, allow extra fields
strict = data ~* shape       ; No extra fields allowed
weak = data ~? shape         ; Missing fields acceptable

; Morphing in functions - automatic on call
process_user {name string email string} (
    ; Function body
)

; These all work through morphing:
{name="Alice" email="a@b.com"} -> process_user
{"Alice" "a@b.com"} -> process_user              ; Positional
{email="a@b.com" name="Alice"} -> process_user   ; Reordered
```

### Tags

Tags are hierarchical enums that serve as values and dispatch keys:

```comp
; Tag definition
tag status = #active | #inactive | #pending | #error

; Hierarchical tags  
tag error = #network | #timeout | #permission

; Tags with values
tag priority = {
    #low = 1
    #medium = 2
    #high = 3
}

; Tag dispatch for polymorphism
handle {event #status} ("Generic handler")
handle {event #error} ("Error handler")
handle {event #network} ("Network specialist")

; Usage
current = #active
problem = #timeout
level = #high
```

## Modules and Imports

```comp
; Import from various sources
import datetime from "std/datetime"
import rio from "@gh/rio-dev/rio"
import api from "https://api.example.com/openapi.json"

; Module exports everything defined with shape/tag/function
shape point {x num y num}
tag color = #red | #green | #blue

main args (
    ; Main entry point
)

; Use imported definitions
now -> datetime.format "%Y-%m-%d"
rio.app {title="My App" root=my_component}
```

## Common Patterns

### Immutable Updates

```comp
; Using 'with' for updates
original = {name="Alice" age=30}
updated = original with {age = 31}

; Nested updates
user = {
    name = "Alice"
    settings = {theme="dark" lang="en"}
}
updated = user with {
    settings = settings with {theme = "light"}
}
```

### Error Handling

```comp
; Fallback for simple cases
value = risky_operation ?? default_value

; Recovery blocks
data -> dangerous_operation
     -> catch error (
         log "Operation failed: {error.message}"
         use_fallback
     )

; Pattern matching on failures
result -> match_shape
    success s (s.value)
    error e (handle_error e)
```

### Collection Operations

```comp
; Working with collections
items 
-> filter {.active}           ; Keep active items
-> map {.name}                ; Extract names
-> unique                     ; Remove duplicates
-> sort                       ; Sort alphabetically
-> join ", "                  ; Create string

; Aggregation
data -> group_by {.category}
     -> map group (
         {
             category = group.key
             total = group.values -> sum {.amount}
             count = group.values -> length
         }
     )
```

### State Management

```comp
; Functional state updates
update_cart cart item (
    cart with {
        items = items -> upsert item {.id == item.id}
        total = calculate_total items
    }
)

; Event handling with state
todo_app state (
    #column {
        #text_input {
            text = state.input
            on_change = value (
                state with {input = value}
            )
            on_submit = (
                state with {
                    input = ""
                    todos = todos ++ [{title = state.input}]
                }
            )
        }
        
        state.todos -> each todo_item state
    }
)
```

## Pipeline Modifiers

The wrench operator (`|-|`) modifies pipeline behavior:

```comp
; Add progress tracking to iterations
data -> filter {.valid}
     -> map {expensive_transform}
     |-| progressbar

; Query optimization
users -> filter {.active}
      -> map {.name}
      |-| optimize_sql    ; Pushes to database

; Development tools
data -> complex_pipeline
     |-| debug            ; Log each stage
     |-| profile          ; Time operations
```

## Standard Library Patterns

### Core Functions

```comp
; Iteration
items -> map {.value * 2}
items -> filter {.active}
items -> reduce 0 {acc + .value}
items -> each {print .name}

; Control flow
condition -> if true_value false_value
value -> when {. > 0} {process_positive}
input -> match patterns...

; Type checking/conversion
value ~ shape           ; Morph to shape
value ~? shape          ; Try morphing
```

### Working with Time

```comp
import datetime from "std/datetime"

; Time operations
now -> datetime.format "%Y-%m-%d"
date -> datetime.add 7.days
start -> datetime.until end

; Scheduling
schedule -> cron "0 9 * * MON-FRI" {
    send_weekly_report
}
```

### File Operations

```comp
import fs from "std/fs"

; Reading files
"data.json" -> fs.read -> json.parse

; Writing files
data -> json.stringify 
     -> fs.write "output.json"

; Directory operations
"./src" -> fs.list
        -> filter {.extension == ".comp"}
        -> map {fs.read .path}
```

## Quick Reference

### Operators

```comp
; Pipeline
->          ; Function application
|-|         ; Pipeline modifier (wrench)

; Morphing
~           ; Normal morph
~*          ; Strong morph (strict)
~?          ; Weak morph (partial)

; Assignment
=           ; Normal assignment
=*          ; Strong (resists override)
=?          ; Weak (only if undefined)

; Spread
..          ; Normal spread
*..         ; Strong spread
?..         ; Weak spread

; Math (numbers only)
+ - * / %   ; Arithmetic
**          ; Power
< <= > >=   ; Comparison
== !=       ; Equality

; Boolean (booleans only)
&& || !!    ; and, or, not

; Other
??          ; Fallback
with        ; Update structure
#           ; Tag prefix
.           ; Field access
```

### Keywords

```comp
shape       ; Define structure shape
tag         ; Define tag hierarchy
import      ; Import modules
from        ; Import source
with        ; Structure update
when        ; Conditional execution
match_shape ; Pattern matching
else        ; Default case
```

### Built-in Shapes

```comp
string      ; Text type
num         ; Arbitrary precision number
bool        ; Boolean (#true or #false)
nil         ; Empty/null value
any         ; Matches anything
```

### Common Tags

```comp
#true #false     ; Boolean values
#nil            ; Empty/null marker
#skip           ; Continue in iteration
#break          ; Stop iteration
#fail           ; Error marker
```
