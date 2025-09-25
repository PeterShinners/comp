# Phase 01-06: Operators

**Status**: Future phase  
**Target start**: After structure literals are complete

## Overview

Add parsing for all operator types that will be used in expressions and statements. This includes arithmetic operators, assignment operators, the spread operator, and comment syntax. This phase focuses purely on parsing operators into AST nodes - evaluation comes in Chapter 2.

## Planned Features

### Arithmetic Operators
- **Basic arithmetic**: `+`, `-`, `*`, `/`, `%` (modulo)
- **Power operator**: `**` for exponentiation
- **Unary operators**: `+42`, `-42` (positive/negative)
- **Precedence handling**: Proper operator precedence in parsing
- **Note**: No floor division (`//`) - users can do `(5 / 2) ->|floor` when needed

### Comparison Operators
- **Equality**: `==`, `!=` for value comparison
- **Ordering**: `<`, `<=`, `>`, `>=` for numeric/string comparison

### Logical Operators
- **Boolean logic**: `&&` (and), `||` (or), `!` (not)
- **Short-circuit evaluation**: Proper AST structure for lazy evaluation

### Assignment Operators
- **Basic assignment**: `=` for field assignment (already in structures)
- **Weak assignment**: `?=` only assigns if field not already defined
- **Strong assignment**: `*=` force assignment, persists beyond current scope
- **Spread assignment**: `..=` shorthand for `struct = {..struct value}`
- **Weak spread assignment**: `?..=` only adds new fields, preserves existing
- **Strong spread assignment**: `*..=` replaces structure entirely with merged result
- **Note**: Skipping inplace operators (`+=`, `-=`, etc.) due to `*=` conflict - add in future phase

### Structure Operators
- **Spread operator**: `..` for structure spreading `{..base extra=value}`
- **Field access**: `.` for accessing nested fields `user.name`
- **Index access**: `#` for array-like access `items#0`
- **Shape union**: `|` for shape type unions `~string|~number`
- **Private data attach**: `&` for attaching private data `data&{session="abc"}`
- **Private data access**: `&.` for accessing private fields `user&.session`

### Pipeline Operators
- **Pipeline compositions**: `|{}` and similar attached pipeline operations
- **Failure handling**: `|?` for handling pipeline failures
- **Note**: No bare `|` operator for pipelines - pipe is visually attached to function references

### Block Operators
- **Block definition**: `.{}` for defining code blocks
- **Block invoke**: `.|` for invoking/calling blocks

### Trail Operators
- **Trail literals**: `/path/segments/` for navigation paths
- **Trail concatenation**: `/` for joining trail segments
- **Trail assignment**: Various `/=` operations for trail-based updates
- **Expression segments**: `'expression'` within trails for dynamic paths

### Special Operators
- **Fallback**: `??` provides fallback values for failures/nil
- **Alternative fallback**: `?|` alternative fallback operator
- **Placeholder**: `???` for unimplemented code (returns not-implemented failure)
- **Parentheses**: `()` for grouping expressions and controlling precedence
- **Array brackets**: `[]` for array type definitions and sizes in shapes
- **Single quotes**: `'expression'` converts expressions to field names

### Comments
- **Line comments**: `;` single-line comments to end of line
- **Documentation comments**: Special handling for doc comments (future)

## Success Criteria

- Parse all operator types into appropriate AST nodes
- Proper operator precedence in expression parsing
- Handle unary vs binary operator disambiguation 
- Parse comments and attach to relevant AST nodes where appropriate
- Support operator combinations: `1 + 2 * 3` parses as `1 + (2 * 3)`
- Error messages for invalid operator usage
- All existing literal parsing continues to work

## Implementation Notes

- Extends the Lark grammar with operator rules and precedence
- Creates new AST node types for different operator categories
- Implements precedence climbing or similar technique for expression parsing  
- Comments may be attached as metadata to AST nodes or handled separately
- Focus on parsing correctness - actual evaluation happens in Chapter 2

## Key Design Decisions

### Operator Precedence (following standard mathematical conventions)
1. **Unary**: `+`, `-`, `!` (highest precedence)
2. **Power**: `**` (right-associative)
3. **Multiplicative**: `*`, `/`, `%`
4. **Additive**: `+`, `-`
5. **Shape Union**: `|` (for type unions like `~string|~number`)
6. **Comparison**: `<`, `<=`, `>`, `>=`
7. **Equality**: `==`, `!=`
8. **Logical AND**: `&&`
9. **Logical OR**: `||`
10. **Fallback**: `??`, `?|`
11. **Assignment**: `=`, `?=`, `*=`, `..=`, `?..=`, `*..=` (lowest precedence, right-associative)

### Comment Handling
- `;` starts a line comment that extends to end of line
- Comments are parsed but may be stripped from AST or preserved as metadata
- No multi-line comments in this phase (keep it simple)

### Spread Operator Context
- `..expression` only valid in structure literals: `{..base extra=1}`
- Creates SpreadField AST node similar to NamedField/PositionalField

## Examples to Support

```comp
; Arithmetic expressions
result = 1 + 2 * 3        ; Should parse as 1 + (2 * 3)
power = 2 ** 3 ** 2       ; Should parse as 2 ** (3 ** 2) (right-associative)

; Comparison and logic  
valid = x > 0 && y < 10
ready = count != 0 || force == #true

; Fallback and error handling
port = config.port ?? env.PORT ?? 8080
result = risky-operation |? default-value
backup = primary ?| secondary  ; Alternative fallback
temp = ???  ; Placeholder for unimplemented

; Assignment variations
config ?= default-settings    ; Only if config not already set
data *= validated-value       ; Strong assignment
user ..= {verified=#true}     ; Append to structure
prefs ?..= {theme="dark"}     ; Only add if theme not set
state *..= new-state          ; Replace entirely

; Shape unions and blocks
!shape ~Result = ~success|~error    ; Union types
block = .{ x + y }                  ; Block definition
result = block .|                   ; Block invoke

; Structure operations
user = {..defaults name="Alice" age=30}
email = user.contact.email
first = items#0
private-data = user&{session="abc123"}  ; Attach private data
session = user&.session                 ; Access private field

; Trail operations and expression control
data |get /users/profile/theme/         ; Trail navigation
config |set /cache/'key'/timeout/ 30    ; Trail with expression segment
path = /base/ / /extended/segments/     ; Trail concatenation
result = (1 + 2) * 3                    ; Parentheses for precedence
tags #user[]                            ; Array type in shape
field-name = 'computed-key'             ; Single quotes for field names

; With comments
count = items |length  ; Get the total count
; This is a documentation comment
result = process-data items
```

## What We're NOT Building (Yet)

- **Expression evaluation**: Operators parse but don't execute
- **Type checking**: No validation of operator compatibility 
- **Advanced operators**: Custom operators, operator overloading
- **Multi-line comments**: Only single-line `;` comments
- **Operator methods**: No custom operator definitions
- **Inplace operators**: `+=`, `-=`, `/=`, `%=` deferred due to `*=` conflict with strong assignment
- **Non-definition ! operators**: `!delete`, `!doc`, etc. wait for a future phase after `!func`, `!tag`, `!shape` parsing

## Future Phases

- **Chapter 2**: Expression evaluation - make operators actually work
- **Later phases**: Advanced assignment patterns, custom operators

This phase establishes the foundation for all expression parsing while keeping evaluation for the next chapter.