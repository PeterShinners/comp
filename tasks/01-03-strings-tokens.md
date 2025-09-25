# Phase 03: String Literals and Tokens

**Status**: Complete ✅  
**Completed**: September 2025

## Overview

Add string literals (`"string"`) and introduce token parsing infrastructure that will support references in Phase 04. This phase focuses on the two remaining basic literal types before moving to references and structures.

## Planned Features

### String Literals

#### Basic Strings
- **Basic strings**: `"hello"`, `""`, `"with spaces"`
- **Escaped content**: `"say \"hi\""`, `"line1\nline2"`, `"backslash: \\"`
- **Standard escapes**: `\"`, `\\`, `\n`, `\r`, `\t`
- **Unicode escapes**: `\u0041` (4-digit hex), `\U00000041` (8-digit hex)

#### Advanced String Features
- **UTF-8 support**: Full Unicode string handling with escape sequences
- **Template strings**: `${} interpolation (future expansion)
- **Raw strings**: For complex content (future expansion)
- **String AST nodes**: `StringLiteral` with string value

### Token Infrastructure

#### Identifier Recognition
- **Basic identifiers**: `hello`, `user_name`, `parse-config`
- **Identifier rules**: Follow UAX #31 + hyphen rules (per design docs)
- **Validation**: Proper Unicode identifier validation

#### Tokenizer Enhancement
- **Token types**: Prepare infrastructure for sigil-based parsing
- **Whitespace handling**: Robust whitespace and comment skipping
- **Error recovery**: Better error messages for malformed tokens

## Success Criteria

### String Parsing
- Parse basic strings: `"hello"` → `StringLiteral("hello")`
- Handle escape sequences: `"say \"hi\""` → `StringLiteral('say "hi"')`
- Support all standard escapes: `\"`, `\\`, `\n`, `\r`, `\t`
- Support Unicode escapes: `"\u0041"` → `StringLiteral("A")`, `"\U0001F600"` → `StringLiteral("😀")`
- Error on unterminated strings: `"unterminated`
- Error on invalid Unicode escapes: `"\u123"` (too short), `"\uGHIJ"` (invalid hex)

### Token Infrastructure
- Recognize valid identifiers: `hello`, `user-name`, `parse_config`
- Error on invalid identifiers: `123abc` (starts with digit)
- Handle Unicode identifiers correctly
- Prepare for sigil-based parsing in Phase 04

### Integration
- String literals work with existing number parsing
- Proper AST node types for each literal type
- Comprehensive error handling for malformed input
- Foundation ready for reference literals in Phase 04

## Implementation Status

✅ **String Parsing Complete**
- Extended Lark grammar with string literal patterns
- Full escape sequence support (standard and Unicode)
- `StringLiteral` AST nodes integrated
- Comprehensive error handling for malformed strings

✅ **Token Infrastructure Complete**  
- Identifier recognition through Lark grammar
- UAX #31 + hyphen validation implemented
- `Identifier` AST nodes with clean parser integration
- Proper error messages for invalid identifiers

✅ **Integration Complete**
- String and identifier parsing work with existing number parsing
- All literals flow through unified `comp.parse()` method
- Comprehensive test coverage (47 tests passing)
- Foundation ready for Phase 04 reference literals

## Implementation Strategy

### Phase 1: String Parsing
1. **Extend grammar**: Add string literal patterns to existing grammar
2. **Escape handling**: Implement standard and Unicode escape processing
3. **AST integration**: Create `StringLiteral` nodes
4. **Error handling**: Comprehensive string validation

### Phase 2: Token Infrastructure  
1. **Identifier patterns**: Add identifier recognition to grammar
2. **Validation logic**: Implement UAX #31 + hyphen validation
3. **Error messages**: Clear feedback for malformed identifiers
4. **Architecture prep**: Design for Phase 04 sigil-based parsing

## Implementation Notes

- ✅ Extended the streamlined grammar from Phase 02 with strings and identifiers
- ✅ String parsing includes full escape sequence support with Unicode (`\u` and `\U`)
- ✅ Identifier parsing follows Comp language design (UAX #31 + hyphens, optional trailing `?`)
- ✅ Foundation established for Phase 04 reference literals (`#tag`, `~shape`, `|function`)
- ✅ Grammar remains streamlined following Phase 02 patterns
- 🗑️ Removed obsolete `_numbers.py` module (functionality moved to Lark grammar)

## Test Structure

Tests are organized by literal type:
- `tests/test_number_literals.py` - Phase 02 (complete)
- `tests/test_string_literals.py` - Phase 03 string tests ✅
- `tests/test_identifier_parsing.py` - Phase 03 identifier tests ✅
- `tests/test_parsing_integration.py` - Integration tests ✅
- `tests/test_reference_literals.py` - Phase 04 (pending)
- `tests/test_token_parsing.py` - Legacy test file (can be removed)

## What We're NOT Building (Yet)

- Reference literals (`#tag`, `~shape`, `|function`) → **Phase 04**
- Structures (`{}`, `{x=1}`) → **Phase 05**
- Expressions (`1 + 2`) - operator precedence  
- String templating/interpolation - advanced feature
- Field access, pipelines, functions, etc.

## Future Phases

- **Phase 04**: Reference literals - tags, shapes, functions with unified parsing
- **Phase 05**: Structures - where all literals can be used as values
- **Phase 06**: Expressions - where all literals can be compared and combined
- **Phase 07**: String templating - where strings get interpolation features

## Completion Summary

Phase 03 successfully implemented comprehensive string and identifier parsing:

**Key Achievements:**
- Full string literal support with escape sequences and Unicode
- Proper identifier recognition following language design specs
- Clean AST node architecture (`StringLiteral`, `Identifier`) 
- Unified parser flow through `comp.parse()` method
- Comprehensive test coverage (47 tests, 0 warnings)
- Removed obsolete code (`_numbers.py`)

**Architecture Established:**
- Lark grammar-based parsing with transformer pattern
- Proper error handling with specific error messages  
- Token priority system for disambiguation
- Foundation ready for sigil-based reference literals

**Ready for Phase 04:** Reference literals (`#tag`, `~shape`, `|function`)

## Notes

- Focus on solid string parsing with comprehensive escape support
- Prepare token infrastructure for the unified reference parsing in Phase 04
- Maintain the streamlined grammar approach established in Phase 02
- Keep error handling specific and educational (following number parsing patterns)