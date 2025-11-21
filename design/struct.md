# Structures

Structures are the backbone of Comp. Every function receives a structure as
input and generates a new structure as output. Even simple values like numbers
and booleans are automatically promoted into single-element structures when used
in pipelines.

Structures are immutable collections that combine the roles of arrays,
dictionaries, and records. They can contain any mix of named and unnamed fields,
accessed by name or position. Field names can be simple tokens, strings, or even
tag values.

## Structure Definition and Field Access

Structures are created with `{}` braces containing field definitions. Fields can
be named or positional (unnamed). Named fields use `=` for assignment, while
unnamed fields are simply listed.

```comp
; Simple structures
user = {name="Alice" age=30}
coords = {10 20 30}
mixed = {x=5 10 y=15}

; Field access
user.name                    ; Named field
coords.#0                    ; First positional field (indexed)
user.#active.status          ; Tag as field name

; String and computed field names
data."Full Name" = "Alice"   ; String field name
data.'field-' ++ suffix      ; Computed field name

; Chained access
users.#0.name                ; Index then field
config."servers".#0.host     ; String field, index, then field
```

**Field access types:**
- `data.field` - Named field (token)
- `data.#0` - Positional index
- `data.'expr'` - Computed field name
- `data."string"` - String literal field name

## Alternative Syntaxes

Structures can be created with three different bracket types, each with distinct
behavior:

- `{}` - Normal struct with evaluated expressions
- `[]` - Literal struct: tokens become strings, expressions evaluate to values
- `()` - Statement struct: evaluates to the final expression only

```comp
{1+2 three 4}    ; {3 three 4} - evaluates expression, preserves token
[1+2 three 4]    ; {3 "three" 4} - token becomes string literal
(1+2 three 4)    ; 4 - returns only final value
```

**When to use each:**

- `{}` for normal structures and function bodies building structs
- `[]` for literal lists of strings and values
- `()` for function bodies that return a computed value

Function arguments typically use `{}` since you're defining individual named or
positional fields. Function bodies use `()` when computing a single return
value, or `{}` when building a result structure field-by-field.


## Spread Operations and Structure Assembly

Spread operators compose new structures from existing ones, with variants
controlling conflict resolution:

- `..` - Normal spread: applies all fields
- `!..` - Strong spread: creates sticky fields that resist overwriting
- `?..` - Weak spread: only adds missing fields

```comp
base = {x=1 y=2}
overlay = {y=3 z=4}

; Basic spreading
merged = {..base ..overlay}    ; {x=1 y=3 z=4}

; Strong spread resists override
locked = {!..base y=99}        ; {x=1 y=2} - y=2 wins

; Weak spread provides defaults
config = {port=8080 ?..{port=3000 host="localhost"}}
; Result: {port=8080 host="localhost"}

; Field deletion
cleaned = {..original !delete temp !delete old}

; Unnamed fields accumulate
arrays = {..{1 2} ..{3 4}}     ; {1 2 3 4}
```

**Conflict resolution:** Strong beats normal beats weak. Unnamed fields never
conflict - they accumulate in order.

## Assignment Operators

Assignment creates new structures - nothing is modified in place. Three
operators control how conflicts are resolved:

- `=` - Normal assignment: overwrites previous value
- `=*` - Strong assignment: resists being overwritten
- `=?` - Weak assignment: only sets if undefined

```comp
; Override behavior
config = {
    port =* 8080       ; Strong
    host = "localhost" ; Normal
    timeout =? 30      ; Weak
    
    port = 3000        ; Ignored - strong wins
    host = "0.0.0.0"   ; Overwrites - normal replaces normal
}

; Deep assignment preserves immutability
tree = {left={value=1}}
new-tree = {..tree left={..tree.left value=10}}
```

**Assignment targets:**
- `field = value` - Creates field in output struct
- `let local = value` - Function-local variable
- `let ctx.name = value` - Context variable
- `let mod.name = value` - Module-level constant

## Destructured Assignment

Extract multiple fields from a structure in a single statement:

```comp
; Extract named fields
let {name age city} = user

; Extract with renaming
let {name=username age=years} = user

; Mix named and positional
let {x y label=name} = point
; Gets first two unnamed fields as x, y and 'label' field as name

; Nested destructuring
let {user={name email} status} = response

; With defaults
let {port ?? 8080 host ?? "localhost"} = config
```

## Field Deletion

Remove fields by creating new structures without them:

```comp
; Delete operator
cleaned = {..original !delete temp !delete old}

; Shape morphing for filtering
!shape ~public-user = {name ~str email ~str}
user = {name="Alice" email="alice@example.com" password="secret"}
public = user ~public-user  ; Password removed
```

Using shapes for field filtering is idiomatic and provides type safety.

## Structure Comparison and Iteration

Structures support equality and ordering comparisons:

```comp
; Equality - named field order doesn't matter
{x=1 y=2} == {y=2 x=1}     ; true
{1 2 3} == {1 2 3}         ; true
{x=1 2} == {2 x=1}         ; false - positional order matters

; Ordering - lexicographic comparison
{a=1} < {a=2}              ; true
{x=1} < {x=1 y=2}          ; true
```

Standard library functions from `struct/` module enable field inspection,
filtering, and transformation:

```comp
!import struct std "core/struct"

data | field-names/struct      ; ["name" "age" "status"]
data | has-field/struct "email" ; #true or #false
data | filter/struct :(value > 0)
data | map-fields/struct |upper/str
```

## Shape Morphing and Updates

The morph operator `~` transforms structures to match shapes:

```comp
!shape ~point = {x ~num y ~num}
data ~ ~point  ; Validates and transforms data to match shape
```

Morphing happens automatically when calling functions with typed parameters. See
[Shape System](shape.md) for full details.

The update operator `..` merges structures:

```comp
defaults = {port=8080 host="localhost"}
config = defaults .. {port=3000}  ; {port=3000 host="localhost"}
```

This creates a new structure combining both sources, with the right side winning
conflicts.

