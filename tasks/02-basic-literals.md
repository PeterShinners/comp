# Phase 02: Basic Literal Parsing (Numbers and Strings)

**Depends on**: Phase 01 - Python project setup  
**Status**: Waiting for Phase 01  
**Estimated start**: After project foundation is solid

## Overview

Once we have a proper Python project structure, implement parsing for the two most fundamental literal types: numbers and strings.

## Planned Features

### Number Literals
- **Integers**: `42`, `-17`, `0`
- **Decimals**: `3.14`, `-2.5`, `0.0`  
- **Scientific notation**: `1e3`, `1.23e-4`, `-2.5e2`
- **All become floats**: Per design docs, everything is IEEE 754 double

### String Literals
- **Basic strings**: `"hello"`, `""`, `"with spaces"`
- **Escaped content**: `"say \"hi\""`, `"line1\nline2"`, `"backslash: \\"`
- **Standard escapes**: `\"`, `\\`, `\n`, `\r`, `\t`

### Basic AST
- **NumberLiteral**: Simple node with float value
- **StringLiteral**: Simple node with string value
- **Parse function**: `parse("42")` → `NumberLiteral(42.0)`

## Success Criteria

- Can parse all number formats from design docs
- Can parse strings with proper escape handling
- Basic AST nodes represent parsed values correctly
- Error handling for malformed numbers and unterminated strings
- Simple tests pass: `assert parse("42").value == 42.0`

## What We're NOT Building (Yet)

- Tags (`#true`, `#active`) - brings in too many concepts
- Structures (`{}`, `{x=1}`) - complex syntax
- Expressions (`1 + 2`) - operator precedence
- Field access, pipelines, functions, etc.

## Implementation Notes

- Start with minimal Lark grammar for just numbers and strings
- Create simple AST nodes
- Focus on getting basic parsing working before adding complexity
- Use existing `design/type.md` for number behavior requirements

## Future Phases (After This)

- **Phase 03**: Add tags (`#tag` literals)
- **Phase 04**: Add structures (`{}`, `{x=1}`, `{1 2 3}` syntax)  
- **Phase 05**: Add expressions (basic arithmetic and field access)
- **Phase 06**: Add pipelines (the core `->` operation)