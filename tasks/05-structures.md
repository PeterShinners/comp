# Phase 05: Structures

**Depends on**: Phase 04 - Reference literals  
**Status**: Future phase  
**Target start**: After reference literals are implemented

## Overview

Add structure literals (`{}`, `{key=value}`) where all the literal types from previous phases (numbers, strings, references) can be used as both values and field names. This phase implements the foundational data structure that enables complex data composition.

## Planned Features

### Basic Structures
- **Empty structures**: `{}`
- **Named fields**: `{name="Alice" age=30}`
- **Positional fields**: `{42 "hello" #active}`
- **Mixed fields**: `{x=10 "unnamed" y=20}`
- **Nested structures**: `{user={name="Bob"} #active 123}`

### Assignment Operator
- **Basic assignment**: `=` for named fields
- **Field syntax**: `identifier=value` or `"string"=value`
- **Expression values**: Any literal type as values

### Field Names and Values
- **Identifier field names**: `{status=#active count=42}`
- **String field names**: `{"field name"="value" "complex-key"=123}`
- **Reference field names**: `{#status=#active ~type=~user}`
- **All literal values**: Numbers, strings, tags, shapes, functions
- **Positional values**: `{42 "text" #tag}` (no field names)

### Advanced Structure Features
- **Structure spreading**: `{...base extra=value}` (future)
- **Computed field names**: `{(expression)=value}` (future)
- **Pattern matching**: Structure destructuring (future)

## Success Criteria

- Parse empty structures: `{}` → `StructureLiteral([])`
- Parse named fields: `{x=1}` → `StructureLiteral([NamedField("x", NumberLiteral(1))])`
- Parse positional fields: `{42 "hello"}` → `StructureLiteral([PositionalField(NumberLiteral(42)), PositionalField(StringLiteral("hello"))])`
- Parse mixed fields: `{x=10 "unnamed" y=20}` → Mixed named and positional
- Support all literal types as values: numbers, strings, references
- Support identifier and string literal field names
- Handle nested structures correctly
- Provide clear error messages for malformed structures and assignments

## Implementation Notes

- Builds on all previous phases (numbers, strings, references)
- Introduces the `=` assignment operator for named fields
- Supports both positional and named field patterns
- Structures become the foundation for more complex language features
- Careful error handling for bracket matching, assignment syntax, and field ordering
- Foundation for future expressions and pattern matching

## Key Design Decisions

### Field Types
- **Named fields**: `key=value` syntax with explicit assignment
- **Positional fields**: Just values without names, order-dependent
- **Mixed support**: Allow both in same structure for flexibility

### Assignment Semantics
- `=` operator only for field assignment (not general expressions yet)
- Field names can be identifiers or string literals
- Values can be any literal type from previous phases

## What We're NOT Building (Yet)

- Expressions (`1 + 2`) - operator precedence
- Function calls and pipelines
- Pattern matching and destructuring
- Structure spreading and computed fields

## Future Phases

- **Phase 06**: Expressions - arithmetic, comparison, logical operations
- **Phase 07**: Pattern matching - structure destructuring and tag dispatch
- **Phase 08**: Advanced features - string templating, spreading, etc.