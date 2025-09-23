# Phase 03: Tag Literals and String Literals

**Depends on**: Phase 02 - Number literal parsing  
**Status**: Future phase  
**Estimated start**: After numbers are implemented and tested

## Overview

Add tag literals (`#tag`) and string literals (`"string"`) which together provide the fundamental literal types needed before structures and expressions.

## Planned Features

### Tag Literals

#### Simple Tags
- **Basic tags**: `#true`, `#false`, `#red`, `#active`
- **Lisp-case naming**: `#user-name`, `#long-name`

#### Namespaced Tags  
- **Hierarchical**: `#http.get`, `#ui.button.primary`
- **Complex hierarchies**: `#error.network.timeout`

#### Integration
- **Boolean system**: `#true`/`#false` as the boolean literals
- **Tag AST nodes**: `TagLiteral` with name string
- **Design compliance**: Follow `design/tag.md` specifications

### String Literals

#### Basic Strings
- **Basic strings**: `"hello"`, `""`, `"with spaces"`
- **Escaped content**: `"say \"hi\""`, `"line1\nline2"`, `"backslash: \\"`
- **Standard escapes**: `\"`, `\\`, `\n`, `\r`, `\t`

#### Advanced String Features
- **UTF-8 support**: Full Unicode string handling
- **Template strings**: `${} interpolation (future expansion)
- **Raw strings**: For complex content (future expansion)
- **String AST nodes**: `StringLiteral` with string value

## Success Criteria

### Tag Parsing
- Parse simple tags: `#true` → `TagLiteral("true")`
- Parse namespaced tags: `#http.get` → `TagLiteral("http.get")`
- Handle lisp-case: `#user-name` → `TagLiteral("user-name")`
- Error on invalid tags: `#123`, `#` (empty)

### String Parsing
- Parse basic strings: `"hello"` → `StringLiteral("hello")`
- Handle escape sequences: `"say \"hi\""` → `StringLiteral('say "hi"')`
- Support all standard escapes: `\"`, `\\`, `\n`, `\r`, `\t`
- Error on unterminated strings: `"unterminated`

### Integration
- Both literals work with existing number parsing
- Proper AST node types for each literal type
- Comprehensive error handling for malformed input

## Implementation Notes

- Extends the grammar from Phase 02 (numbers)
- Tags follow UAX #31 + hyphen rules (per design docs)
- Dots in tag names for namespacing
- Strings use standard escape sequence parsing
- Foundation for future polymorphic dispatch (tags) and templating (strings)

## Test Structure

Tests are organized in separate files:
- `tests/test_number_literals.py` - Phase 02 (complete)
- `tests/test_string_literals.py` - Phase 03 string tests (prepared)
- Tag tests will be added to a new `tests/test_tag_literals.py`

## What We're NOT Building (Yet)

- Structures (`{}`, `{x=1}`) - complex syntax
- Expressions (`1 + 2`) - operator precedence  
- String templating/interpolation - advanced feature
- Field access, pipelines, functions, etc.

## Future Phases

- **Phase 04**: Structures - where tags and strings can be used as values
- **Phase 05**: Expressions - where all literals can be compared and combined
- **Phase 06**: Pattern matching - where tags enable dispatch
- **Phase 07**: String templating - where strings get interpolation features