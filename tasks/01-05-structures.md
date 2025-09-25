# Phase 05: Structures

**Status**: ✅ COMPLETE  
**Target start**: Complete - all features implemented and tested

## Overview

Add structure literals (`{}`, `{key=value}`) where all the literal types from previous phases (numbers, strings, references) can be used as both values and field names. This phase implements the foundational data structure that enables complex data composition.

## Planned Features

### Basic Structures
- **Empty structures**: `{}`
- **Named fields**: `{name="Alice" age=30}`
- **Positional fields**: `{42 "hello" #active}`
- **Mixed fields**: `{x=10 "unnamed" y=20}`
- **Nested structures**: `{user={name="Bob"} #active 123}`
- **Deep recursion**: `{1 2 {3 4 {5 6}} 7}` - arbitrary nesting depth
- **Complex nesting**: `{outer={inner={deep="value"}} count=42}`

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
- Parse recursive structures: `{1 {2 3} 4}` → Properly nested StructureLiteral nodes
- Handle arbitrary nesting depth: `{{{{}}}}`
- Support all literal types as values: numbers, strings, references
- Support identifier and string literal field names
- Handle nested structures correctly with proper scoping
- Provide clear error messages for malformed structures, unmatched brackets, and assignment syntax

## Implementation Notes

- Builds on all previous phases (numbers, strings, references)
- Introduces the `=` assignment operator for named fields
- Supports both positional and named field patterns
- **Recursive parsing**: Structures can contain other structures as values
- **Parser recursion**: Grammar rules must handle arbitrary nesting depth
- Structures become the foundation for more complex language features
- Careful error handling for bracket matching, assignment syntax, and field ordering
- **Memory considerations**: Deep nesting should not cause stack overflow
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

### Recursive Structure Parsing
- **Arbitrary depth**: Structures can nest indefinitely `{{{{}}}}`
- **Mixed content**: `{1 {x=2 3} {y={z=4}}}`  
- **Parser design**: Must handle recursion without stack overflow
- **AST representation**: Nested StructureLiteral nodes form tree structure
- **Error boundaries**: Clear error messages for mismatched brackets at any depth

## ✅ Implementation Complete

**AST Nodes Added**:
- `StructureLiteral(fields: list[ASTNode])` - represents `{...}` structures
- `NamedField(name: str, value: ASTNode)` - represents `key=value` assignments  
- `PositionalField(value: ASTNode)` - represents unnamed values

**Grammar Extension**:
- Added structure parsing rules to `comp.lark`
- Supports `{field1 field2 ...}` syntax with whitespace separation
- Named fields: `identifier=expression` or `string=expression`
- Positional fields: any expression from previous phases

**Parser Integration**:
- Added transformer methods in `_parser.py` 
- Proper error handling for malformed structures
- Full integration with all existing literal types

**Test Coverage**: 28 comprehensive test cases covering:
- Empty structures: `{}`
- Single/multiple fields: `{42}`, `{1 2 3}`, `{x=10 y=20}`
- Mixed named/positional: `{x=10 "unnamed" y=20}` 
- Nested structures: `{1 {2 3} 4}`, `{user={name="Bob"}}`
- All literal types: numbers, strings, identifiers, references
- Error cases: malformed syntax, invalid assignments, comma rejection

**Examples Working**:
```comp
{}                                    // StructureLiteral([])
{42}                                 // StructureLiteral([PositionalField(42)])  
{name="Alice" age=30}                // Named fields
{1 "hello" #tag ~shape |func}        // Mixed positional fields
{user={profile={name="Bob"}}}        // Nested structures
```

## What We're NOT Building (Yet)

- Expressions (`1 + 2`) - operator precedence
- Function calls and pipelines
- Pattern matching and destructuring
- Structure spreading and computed fields

## Future Phases

- **Phase 06**: Expressions - arithmetic, comparison, logical operations
- **Phase 07**: Pattern matching - structure destructuring and tag dispatch
- **Phase 08**: Advanced features - string templating, spreading, etc.