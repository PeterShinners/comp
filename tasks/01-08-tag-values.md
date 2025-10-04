# Phase 08: Tag Values and Generators

**Status**: ✅ COMPLETE  
**Completion Date**: October 3, 2025

## Overview

Extended tag definitions to support:
1. Simple value assignments for tags and their children
2. Generator functions/blocks for auto-generating child values

Tag values are restricted to simple literals (numbers and strings) to avoid grammar ambiguities. Generators can be function references or inline blocks that compute values for child tags.

## Implementation Summary

### Syntax Added

**Tag with value**:
```comp
!tag #status = 1
!tag #priority = "high"
```

**Tag with generator (function reference)**:
```comp
!tag #color |name/tag = {#red #green #blue}
!tag #permission |bitflag/tag = {#read #write #execute}
```

**Tag with generator (inline block)**:
```comp
!tag #status :{[name |upper]} = {#active #inactive}
```

**Tag children with values**:
```comp
!tag #status = {
    #active = 1
    #inactive = 0
    #error = {
        #timeout = 100
        #network = 200
    }
}
```

### Grammar Changes

Updated `tag_definition` rule to support values and generators:
```lark
tag_definition: BANG_TAG tag_path                                    // Simple: !tag #status
              | BANG_TAG tag_path tag_generator ASSIGN tag_literal    // With generator and value
              | BANG_TAG tag_path tag_generator ASSIGN tag_body       // With generator and children
              | BANG_TAG tag_path ASSIGN tag_literal                  // With value: !tag #status = 42
              | BANG_TAG tag_path ASSIGN tag_body                     // With children

tag_generator: function_reference | block                 // Generator function or inline block

tag_child: tag_path                                       // Simple child: #active
         | tag_path ASSIGN tag_literal                    // Child with value: #active = 1
         | tag_path ASSIGN tag_body                       // Child with children: #error = {#timeout}

tag_literal: number | string                              // Tag values are restricted to simple literals
```

### Key Design Decisions

**Restriction to Simple Literals**: Tag values can only be `number` or `string` literals, not arbitrary expressions or structures. This avoids the grammar ambiguity where `{#tag}` could be interpreted as either:
- A structure containing a tag reference, OR
- A tag body with a tag child

**Syntax Consistency**: Tag definitions use plain `{...}` for children, consistent with:
- Shape definitions: `!shape ~point = {x ~num y ~num}` (not `~{...}`)
- Function definitions: `!func |point ~nil = {}` (not `|{...}`)

Only inline/anonymous constructs use prefixed braces:
- Inline shapes: `~{x ~num y ~num}` for anonymous shape types
- (Future) Inline blocks might use similar syntax

**Alternative Considered and Rejected**: Using `#{...}` for tag children to create symmetry with `~{...}` for inline shapes. This was rejected because:
1. Shape definitions themselves don't use `~{...}`, only inline anonymous shapes do
2. Function definitions don't use `|{...}` either
3. Introducing special syntax for tag children would be inconsistent
4. The simpler approach of restricting values to literals is cleaner

## Test Coverage

All 20 tag parsing tests pass (11 basic + 9 generator tests), including:
- Simple tags: `!tag #status`
- Tags with literal values: `!tag #status = 1`
- Tags with children: `!tag #status = {#active #inactive}`
- Nested tag hierarchies: `!tag #status = {#error = {#timeout #network}}`
- Children with values: `#active = 1`
- Tags with function generators: `!tag #color |name/tag = {#red #green}`
- Tags with inline block generators: `!tag #status :{[name |upper]} = {#active}`
- Generator with explicit values: `!tag #priority |sequential/tag = 10`
- Multiple generators in same module

## Examples Working

```comp
!tag #status = 1                              // Tag with numeric value
!tag #priority = "high"                       // Tag with string value
!tag #colors = {#red #green #blue}            // Tag with children
!tag #http = {#ok = 200 #error = 500}        // Children with values
!tag #nested = {#outer = {#inner = 42}}      // Nested hierarchy

// Generator examples
!tag #color |name/tag = {#red #green #blue}          // Function reference generator
!tag #status :{[name |upper]} = {#active #inactive}  // Inline block generator
!tag #permission |bitflag/tag = {#read #write}       // Bitflag generator
```

## Implementation Files Modified

- `src/comp/lark/comp.lark` - Added `tag_literal` and `tag_generator` rules with value and generator support
- `src/comp/_ast.py` - Added `generator` field to `TagDefinition`, `postProcess()` method, and custom `matches()` method
- `src/comp/_parser.py` - Added `tag_literal` and `tag_generator` cases, updated `_create_node` to call `postProcess()`
- `tests/test_parse_tags.py` - Tests already supported the feature after syntax clarification
- `tests/test_tag_generators.py` - New test file with 9 comprehensive generator tests

## Future Considerations

If we need more complex tag values in the future, we could:
1. Extend `tag_literal` to include other unambiguous literals (booleans, nil, etc.)
2. Consider different syntax for complex tag expressions
3. Add special syntax like `#{...}` if the use case justifies the complexity

For now, simple number and string literals cover the expected use cases for tag values (numeric codes, string labels, etc.).
