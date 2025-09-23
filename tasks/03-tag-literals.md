# Phase 03: Tag Literals

**Depends on**: Phase 02 - Basic literal parsing  
**Status**: Future phase  
**Estimated start**: After numbers and strings are solid

## Overview

Add tag literals (`#tag`) which are fundamental to Comp's design for enums, booleans, and polymorphic dispatch.

## Planned Features

### Simple Tags
- **Basic tags**: `#true`, `#false`, `#red`, `#active`
- **Lisp-case naming**: `#user-name`, `#long-name`

### Namespaced Tags  
- **Hierarchical**: `#http.get`, `#ui.button.primary`
- **Complex hierarchies**: `#error.network.timeout`

### Integration
- **Boolean system**: `#true`/`#false` as the boolean literals
- **Tag AST nodes**: `TagLiteral` with name string
- **Design compliance**: Follow `design/tag.md` specifications

## Success Criteria

- Parse simple tags: `#true` → `TagLiteral("true")`
- Parse namespaced tags: `#http.get` → `TagLiteral("http.get")`
- Handle lisp-case: `#user-name` → `TagLiteral("user-name")`
- Error on invalid tags: `#123`, `#` (empty)
- Integration with existing number/string parsing

## Implementation Notes

- Extends the grammar from Phase 02
- Tags follow UAX #31 + hyphen rules (per design docs)
- Dots in tag names for namespacing
- Foundation for future polymorphic dispatch

## Future Phases

- **Phase 04**: Structures - where tags can be used as values
- **Phase 05**: Expressions - where tags can be compared
- **Phase 06**: Pattern matching - where tags enable dispatch