# Phase 01-07: Advanced Operators

**Status**: ✅ COMPLETE  
**Target start**: After mathematical operators are complete

## Overview

Add parsing for all the advanced language-specific operators that make Comp unique. This includes assignment operators, structure manipulation, pipeline operations, block syntax, trail navigation, and special operators. These operators build on the mathematical foundation from Phase 01-06.

## Planned Features

- **Comments**: `;` single line comments


### Assignment Operators
- **Basic assignment**: `=` for field assignment (already in structures)
- **Weak assignment**: `=?` only assigns if field not already defined
- **Strong assignment**: `=*` force assignment, resists overwriting in conflicts
- **Spread assignment**: `..=` shorthand for `struct = {..struct value}`
- **Weak spread assignment**: `..=?` only adds new fields, preserves existing
- **Strong spread assignment**: `..=*` replaces structure entirely with merged result
- **Note**: Skipping inplace operators (`+=`, `-=`, etc.) due to conflict potential - add in future phase

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

### Special Operators
- **Fallback**: `??` provides fallback values for failures/nil
- **Alternative fallback**: `?|` alternative fallback operator
- **Placeholder**: `???` for unimplemented code (returns not-implemented failure)
- **Array brackets**: `[]` for array type definitions and sizes in shapes
- **Single quotes**: `'expression'` converts expressions to field names

## Deferred to Future Phase

### Trail Operators (deferred due to complexity)
- **Trail literals**: `/path/segments/` for navigation paths  
- **Trail concatenation**: `/` for joining trail segments
- **Trail assignment**: Various `/=` operations for trail-based updates
- **Expression segments**: `'expression'` within trails for dynamic paths
- **Note**: Deferred due to `/` conflict with division operator and complex expression segment parsing

## Success Criteria

- Parse all advanced operator types into appropriate AST nodes
- Integrate with mathematical operator precedence from Phase 01-06
- Handle complex operator interactions (assignment with spread, blocks with structures)
- Support all assignment operator variants with proper semantics
- Parse block definitions and invocations
- Error messages for invalid advanced operator usage
- All existing parsing (literals, structures, mathematical operators) continues to work

## Implementation Notes

- Extends the Lark grammar built in Phase 01-06 with advanced operator rules
- Creates new AST node types for assignment, structure, pipeline, block operators
- Integrates advanced operators into existing precedence system
- Block parsing requires distinguishing `.{}` from structure literals `{}`
- Focus on parsing correctness - actual evaluation happens in Chapter 2

## Key Design Decisions

### Extended Operator Precedence (building on Phase 01-06)
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
11. **Assignment**: `=`, `=?`, `=*`, `..=`, `..=?`, `..=*` (lowest precedence, right-associative)

### Spread Operator Context
- `..expression` only valid in structure literals: `{..base extra=1}`
- Creates SpreadField AST node similar to NamedField/PositionalField

### Trail Syntax Rules
- `/path/segments/` creates trail structure
- `'expression'` within trails allows dynamic segments
- `:` marks axis shifts for different navigation contexts

## Examples to Support

```comp
; Assignment variations
config =? default-settings    ; Only if config not already set
data =* validated-value       ; Strong assignment
user ..= {verified=#true}     ; Append to structure
prefs ..=? {theme="dark"}     ; Only add if theme not set
state ..=* new-state          ; Replace entirely

; Structure operations
user = {..defaults name="Alice" age=30}
email = user.contact.email
first = items#0
private-data = user&{session="abc123"}  ; Attach private data
session = user&.session                 ; Access private field

; Shape unions and blocks
!shape ~Result = ~success|~error    ; Union types
block = .{ x + y }                  ; Block definition
result = block .|                   ; Block invoke

; Pipeline operations
result = risky-operation |? default-value
data = process |{} transform

; Fallback and special operators
port = config.port ?? env.PORT ?? 8080
backup = primary ?| secondary  ; Alternative fallback
temp = ???  ; Placeholder for unimplemented

; Array types and field naming
tags #user[]                    ; Array type in shape
field-name = 'computed-key'     ; Single quotes for field names
```

## What We're NOT Building (Yet)

- **Expression evaluation**: Operators parse but don't execute
- **Type checking**: No validation of operator compatibility 
- **Advanced operators**: Custom operators, operator overloading
- **Multi-line comments**: Only single-line `;` comments
- **Operator methods**: No custom operator definitions
- **Inplace operators**: `+=`, `-=`, `/=`, `%=` deferred to avoid conflicts with assignment operators
- **Trail operators**: `/path/segments/`, trail concatenation, expression segments - deferred due to `/` division conflict
- **Non-definition ! operators**: `!delete`, `!doc`, etc. wait for a future phase after `!func`, `!tag`, `!shape` parsing

## Future Phases

- **Chapter 2**: Expression evaluation - make operators actually work
- **Later phases**: Advanced assignment patterns, custom operators, inplace operators
- **Trail operators phase**: Implement `/path/segments/`, trail concatenation, expression segments with proper `/` division disambiguation

This phase completes the foundation for most operator parsing in Comp, enabling complex expressions that combine mathematical operations with language-specific features. Trail operators are deferred to avoid the complex division operator conflicts.