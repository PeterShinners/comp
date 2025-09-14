# Shape Morphing System for Comp

## Core Concept

Comp uses two morphing modes: **strict** (strips unknown fields) and **weak** (preserves unknown fields). Functions default to strict morphing for predictable interfaces.

## Morphing Operators

### Type Annotations
```comp
~Shape         ; Strict: exactly these fields
?~Shape        ; Weak: at least these fields, preserve others
?~nil          ; At least nothing (accepts anything, preserves all)
```

### Explicit Morphing
```comp
data ~ Shape   ; Strict morph: strips unknown fields
data ?~ Shape  ; Weak morph: preserves unknown fields
```

## Function Behavior

Functions **default to strict morphing** - they only receive the fields they declare:

```comp
; Strict function (default) - strips unknown fields
!func process ~{x ~number y ~number} = {
    ; @ is {x=10 y=20}, field z was stripped
}
process({x=10 y=20 z=30})

; Weak function - preserves unknown fields  
!func passthrough ?~{x ~number y ~number} = {
    ; @ is {x=10 y=20 z=30}, all fields preserved
}
passthrough({x=10 y=20 z=30})

; Accept anything - no morphing
!func debug ?~nil = {
    ; @ receives exactly what was passed
}
debug({anything="at all"})
```

## Shape Matching Rules

For both strict and weak morphing:
1. Match fields by exact name
2. Match fields by tag type
3. Match remaining fields by position
4. Apply type conversions/validation

The only difference: strict drops unmatched fields, weak preserves them.

## Common Patterns

```comp
; Validation - strict to ensure no unexpected fields
!func validate_user ~User = {
    @.email -> :validate_email
    @.age >= 0 && @.age <= 150
}

; Middleware - weak to preserve context
!func add_auth ?~{request_id} = {
    {...@ auth=get_auth() timestamp=now()}
}

; Debugging - accept anything
!func log ?~nil = {
    @ -> :describe -> :print
}

; Pipeline with mixed modes
data 
    -> clean ~UserInput          ; Strip unknown fields
    -> enrich ?~UserInput        ; Add fields, preserve all
    -> validate ~User            ; Final strict validation
```

## Optional/Nullable Types

Use unions with `~nil` for optional values:

```comp
; Optional field in shape
!shape ~Config = {
    host ~string
    port ~number  
    timeout ~number|~nil         ; Can be number or empty struct
}

; Optional parameter
!func greet ~{user ~User|~nil} = {
    user == {} ?| "Hello!" | "Hello, ${user.name}!"
}
```

## Key Changes from Previous Design

1. **Functions strip by default** (previously preserved fields)
2. **`?~` prefix for weak morphing** (opt-in to preserve fields)
3. **`?~nil` means "accept anything"** (no special `~any` type yet)
4. **No `Type?` syntax** for optionals (use `Type|~nil` instead)

## Benefits

- **Predictable functions**: Only see declared fields by default
- **Explicit preservation**: `?~` clearly marks permissive functions
- **Security**: No accidental field leakage
- **Educational**: `?~nil` reinforces the morphing mental model
- **Consistent**: Same morphing rules everywhere, just strict vs weak



Exactly! The same disambiguation rules that apply to function overloading should apply to union type morphing. If it's ambiguous, it should error rather than guess.

## Disambiguation Rules

```comp
; Function overloading
!func :send ~User = { ... }
!func :send ~Group = { ... }

{name="Alice" email="alice@ex.com"} -> :send     ; Matches User (has email)
{name="Admins" members={...}} -> :send           ; Matches Group (has members)
{name="Something"} -> :send                      ; ERROR: Ambiguous!

; Same rules for union morphing
data ~ (~User|~Group)
; Tries to match User, then Group
; ERROR if matches both or neither
```

## Specificity Scoring

```comp
; The morphing system scores matches
!shape ~User = {name ~string email ~string}
!shape ~Group = {name ~string members ~User[]}

{name="X" email="y"} ~ (~User|~Group)
; User: 2/2 fields match (100%)
; Group: 1/2 fields match (50%)
; → Picks User

{name="X" members={}} ~ (~User|~Group)  
; User: 1/2 fields match (50%)
; Group: 2/2 fields match (100%)
; → Picks Group

{name="X"} ~ (~User|~Group)
; User: 1/2 fields match (50%)
; Group: 1/2 fields match (50%)
; → ERROR: Ambiguous match
```

## Array Processing

```comp
; Each element evaluated independently
mixed = {
    {name="Alice" email="a@ex.com"}      ; Clearly User
    {name="Admins" members={}}           ; Clearly Group
    {name="Bob"}                          ; ERROR: Ambiguous!
}

mixed ~ (~User|~Group)[]
; Fails on third element
```

## Explicit Disambiguation

```comp
; Using tags for clear type marking
!shape ~User = {type #user name ~string ...}
!shape ~Group = {type #group name ~string ...}

; Now unambiguous
{
    {type=#user name="Alice"}
    {type=#group name="Admins"}
} ~ (~User|~Group)[]

; Or with explicit morphing per element
mixed => {
    @.type == #user ?| @ ~ User | @ ~ Group
}
```

## Error Messages

```comp
; Clear error reporting
{name="Something"} ~ (~User|~Group)
; ERROR: Ambiguous type match
;   Matches User with 50% confidence (1/2 fields)
;   Matches Group with 50% confidence (1/2 fields)
;   Consider adding distinguishing fields or type tags

; No match
{id=123} ~ (~User|~Group)  
; ERROR: No type match
;   User requires: name, email
;   Group requires: name, members
;   Provided: id
```

## Function Overloading Uses Same Rules

```comp
!func :process ~{user ~User} = { "User: ${user.name}" }
!func :process ~{group ~Group} = { "Group of ${group.members -> :length}" }
!func :process ?~nil = { "Unknown entity" }

; Resolution order
{name="Alice" email="..."} -> :process   ; First overload
{name="Admins" members={}} -> :process   ; Second overload  
{name="Unknown"} -> :process             ; ERROR: Ambiguous
{random="data"} -> :process              ; Third overload (fallback)
```

This consistency between union morphing and function overloading is important - same mental model, same rules, same errors. The system should never guess when there's ambiguity.