# Phase 01-06: Mathematical Operators

**Status**: Future phase  
**Target start**: After structure literals are complete

## Overview

Add parsing for mathematical operators that form the foundation of expression parsing. This includes arithmetic, comparison, logical operators, and parentheses for precedence control. This phase focuses on the core mathematical operations that are common across programming languages.

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
- **Boolean logic**: `&&` (and), `||` (or), `!!` (not)
- **Short-circuit evaluation**: Proper AST structure for lazy evaluation
- **Type restriction**: Logical operators only valid on boolean types

### Expression Control
- **Parentheses**: `()` for grouping expressions and controlling precedence

### Comments
- **Line comments**: `;` single-line comments to end of line
- **Documentation comments**: Special handling for doc comments (future)

## Success Criteria

- Parse all mathematical operator types into appropriate AST nodes
- Proper operator precedence in expression parsing
- Handle unary vs binary operator disambiguation 
- Parse comments and attach to relevant AST nodes where appropriate
- Support operator combinations: `1 + 2 * 3` parses as `1 + (2 * 3)`
- Support parentheses for precedence override: `(1 + 2) * 3`
- Error messages for invalid operator usage
- All existing literal parsing continues to work

## Implementation Notes

- Extends the Lark grammar with mathematical operator rules and precedence
- Creates new AST node types for arithmetic, comparison, logical operators
- Implements precedence climbing or similar technique for expression parsing  
- Comments may be attached as metadata to AST nodes or handled separately
- Focus on parsing correctness - actual evaluation happens in Chapter 2

## Key Design Decisions

### Operator Precedence (following standard mathematical conventions)
1. **Unary**: `+`, `-`, `!!` (highest precedence)
2. **Power**: `**` (right-associative)
3. **Multiplicative**: `*`, `/`, `%`
4. **Additive**: `+`, `-`
5. **Comparison**: `<`, `<=`, `>`, `>=`
6. **Equality**: `==`, `!=`
7. **Logical AND**: `&&`
8. **Logical OR**: `||` (lowest precedence)

### Comment Handling
- `;` starts a line comment that extends to end of line
- Comments are parsed but may be stripped from AST or preserved as metadata
- No multi-line comments in this phase (keep it simple)

## Examples to Support

```comp
; Arithmetic expressions
result = 1 + 2 * 3        ; Should parse as 1 + (2 * 3)
power = 2 ** 3 ** 2       ; Should parse as 2 ** (3 ** 2) (right-associative)
negative = -42 + 10       ; Unary minus has high precedence
positive = +value * 2     ; Unary plus supported

; Comparison and logic  
valid = x > 0 && y < 10
ready = count != 0 || force == #true
negated = !!ready              ; Double-bang for logical NOT
equal = name == "Alice" && age >= 18

; Precedence control with parentheses
result = (1 + 2) * 3      ; Should parse as (1 + 2) * 3 = 9, not 1 + (2 * 3) = 7
complex = (x + y) * (a - b) / (c ** 2)

; With comments
count = items |length  ; Get the total count
; This is a documentation comment
result = (a + b) * factor  ; Parentheses override precedence
```

## What We're NOT Building (Yet)

- **Expression evaluation**: Operators parse but don't execute
- **Type checking**: No validation of operator compatibility 
- **Advanced operators**: Assignment, spread, pipeline, block operators (next phase)
- **Multi-line comments**: Only single-line `;` comments
- **Operator methods**: No custom operator definitions

## Future Phases

- **Phase 01-07**: Advanced operators (assignment, structure, pipeline, block, trail)
- **Chapter 2**: Expression evaluation - make operators actually work
- **Later phases**: Advanced assignment patterns, custom operators

This phase establishes the foundation for mathematical expression parsing while keeping the complex language-specific operators for the next phase.