# Phase 04: Reference Literals (Tags, Shapes, Functions)

**Depends on**: Phase 03 - String literals and token infrastructure  
**Status**: ✅ **COMPLETE**  
**Completed**: September 2025

## Completion Summary

Phase 4 has been successfully implemented with full Unicode support and grammar refactoring:

### ✅ Implemented Features
- **All reference types**: Tags (`#tag`), shapes (`~shape`), functions (`|function`) 
- **All patterns**: Simple, hierarchical (`.`), module (`/`), and combined references
- **Unicode support**: Full UAX #31 compliance using `[^\W\d]` pattern for identifier starts
- **Grammar refactoring**: Eliminated duplication by reusing identifier patterns
- **Comprehensive testing**: 26/26 reference tests passing, full Unicode coverage

### ✅ Technical Achievements  
- **Modular grammar**: `references.lark` imports from `identifiers.lark` to eliminate duplication
- **Unicode compliance**: Support for international identifiers (Greek, Arabic, etc.)
- **Error handling**: Proper validation for malformed references
- **AST integration**: Clean `TagReference`, `ShapeReference`, `FunctionReference` nodes
- **Terminology**: Updated "literal" to "expression" for semantic accuracy

### ✅ Test Results
- **Reference tests**: 26/26 passing (100%)
- **Total test suite**: 75/75 passing (100%) 
- **Unicode coverage**: International characters, boolean forms, error cases
- **Integration**: Works seamlessly with existing number and string parsing

## Overview

Add reference literals (`#tag`, `~shape`, `|function`) using the unified parsing pattern. This phase leverages the token infrastructure from Phase 03 to implement the three reference types that share 99% of their parsing logic.

## Unified Reference Pattern

Tags, shapes, and functions all follow the identical parsing pattern by design:
- **Local references**: `#identifier`, `~identifier`, `|identifier`
- **Hierarchical references**: `#identifier.qualified.path`, `~identifier.qualified.path`, `|identifier.qualified.path`
- **Module references**: `#identifier/module`, `~identifier/module`, `|identifier/module`
- **Full references**: `#identifier.qualified.path/module`

This means 99% of the parsing logic is shared - just different sigils (`#`, `~`, `|`) with the same identifier, dotted path, and module namespace rules.

## Planned Features

### Reference Literals (Unified Pattern)

#### Tag References
- **Simple tags**: `#true`, `#false`, `#red`, `#active`
- **Hierarchical tags**: `#http.get`, `#ui.button.primary`, `#error.network.timeout`
- **Module tags**: `#error/std`, `#active.status/other`
- **Lisp-case naming**: `#user-name`, `#long-name`

#### Shape References  
- **Simple shapes**: `~num`, `~str`, `~bool`
- **Hierarchical shapes**: `~database.record`, `~ui.component`, `~math.vector`
- **Module shapes**: `~record/database`, `~component/ui`
- **Custom shapes**: `~user-profile`, `~api-response`

#### Function References
- **Simple functions**: `|connect`, `|validate`, `|process`
- **Hierarchical functions**: `|database.query`, `|json.parse`, `|math.sqrt`
- **Module functions**: `|query/database`, `|parse/json`
- **Kebab-case naming**: `|parse-config`, `|send-email`

#### Shared Implementation
- **Identifier rules**: Follow UAX #31 + hyphen rules (established in Phase 03)
- **Dotted paths**: Support hierarchical namespacing with `.` separator
- **Module paths**: Support module namespacing with `/` separator
- **Full format**: `sigil + identifier[.hierarchy][/module]`
- **AST nodes**: `TagLiteral`, `ShapeLiteral`, `FunctionLiteral` with name strings

### String Literals (Removed)

String literals moved to **Phase 03: Strings and Tokens**

## Success Criteria

### Reference Parsing (All Types)
- Parse simple references: `#true` → `TagLiteral("true")`, `~num` → `ShapeLiteral("num")`, `|connect` → `FunctionLiteral("connect")`
- Parse hierarchical references: `#http.get` → `TagLiteral("http.get")`, `~database.record` → `ShapeLiteral("database.record")`
- Parse module references: `#error/std` → `TagLiteral("error/std")`, `~record/database` → `ShapeLiteral("record/database")`
- Parse full references: `#active.status/other` → `TagLiteral("active.status/other")`
- Handle lisp/kebab-case: `#user-name`, `~api-response`, `|parse-config`
- Error on invalid references: `#123`, `~`, `|` (empty), `#.invalid` (malformed path), `#/empty` (missing module)

### Integration
- Reference literals work with existing number and string parsing (from Phases 02-03)
- Proper AST node types for each reference type
- Comprehensive error handling for malformed references
- Leverages token infrastructure from Phase 03

## Implementation Completed

### Grammar Architecture
- **Modular design**: `src/comp/lark/references.lark` imports patterns from `identifiers.lark`
- **Unified parsing**: 99% shared logic across tags/shapes/functions with different sigils
- **Unicode support**: `[^\W\d]` pattern provides full international character support
- **Grammar reuse**: Eliminated regex duplication by importing identifier patterns

### AST Integration  
- Clean `TagReference`, `ShapeReference`, `FunctionReference` AST nodes
- Proper transformer methods in `_parser.py` with identifier path processing
- Updated terminology from "literal" to "expression" for semantic accuracy
- Integration with existing number and string parsing from Phases 02-03

### Parser Features
- **Reference types**: All three types (`#`, `~`, `|`) fully implemented
- **All patterns**: Simple, hierarchical (`.`), module (`/`), combined references  
- **Unicode identifiers**: International characters supported (Greek, Arabic, etc.)
- **Error handling**: Comprehensive validation for malformed references
- **Naming conventions**: Supports lisp-case and kebab-case naming

## Test Structure

Tests are organized by literal type:
- `tests/test_number_literals.py` - Phase 02 (complete)
- `tests/test_invalid_numbers.py` - Phase 02 validation (complete)
- `tests/test_string_literals.py` - Phase 03 (complete)
- `tests/test_token_parsing.py` - Phase 03 (complete)
- `tests/test_reference_literals.py` - Phase 04 reference tests (tags, shapes, functions)

## What We're NOT Building (Yet)

- Definitions of tags, shapes, or functions
- Structures (`{}`, `{x=1}`) → **Phase 05**
- Expressions (`1 + 2`) - operator precedence  
- String templating/interpolation - advanced feature
- Field access, pipelines, functions, etc.

## Future Phases

- **Phase 05**: Structures - where all literals (numbers, strings, references) can be used as values
- **Phase 06**: Expressions - where all literals can be compared and combined
- **Phase 07**: Pattern matching - where tags enable dispatch
- **Phase 08**: String templating - where strings get interpolation features