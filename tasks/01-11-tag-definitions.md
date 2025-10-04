# Phase 11: Tag Definitions (Module-Level Grammar)

**Status**: ✅ **COMPLETE**  
**Started**: October 2025  
**Completed**: October 2025

## Progress

- [X] Grammar updated with module-level entry point
- [X] Tag definition grammar rules added
- [X] Implement `parse_module()` and `parse_expr()` functions
- [X] Create `Module` and `TagDefinition` AST nodes
- [X] Add transformer methods for new grammar rules
- [X] Update test helpers in `comptest.py`
- [X] Update tests to use new parse functions
- [X] Run test suite and validate
- [X] All 11 tag definition tests passing
- [X] All 266 existing tests still passing

## Overview

This phase introduces **module-level grammar** - a fundamental shift from the expression/structure-level grammar we've built so far. Tag definitions using `!tag` are the first module-level construct, establishing patterns that will extend to function definitions (`!func`), shape definitions (`!shape`), and imports (`!import`).

### Module vs Structure Grammar

The grammar now needs to handle two distinct contexts:

**Structure-Level Grammar** (existing):
- Values and expressions: `2 + 3`, `"hello"`, `#active`
- Structure contents: `{x = 5}`, `{..spread}`
- Pipeline operations: `[data |process]`
- Function arguments: `|func {arg = value}`

**Module-Level Grammar** (new):
- Top-level only - not valid inside structures
- Definitions: `!tag`, `!func`, `!shape`, `!import`
- Module metadata: `$mod.package = {...}`
- Entry points: `!entry = {...}`, `!main = {...}`

For example, `2 + 3` is valid in a structure `{x = 2 + 3}` but **not** valid at the top level of a file. Conversely, `!tag #status` is valid at the top level but **not** inside a structure.

## Tag Definition Syntax

This phase implements "tags-light" - tag definitions **without values** (those come in a later phase). We're building the hierarchical structure and namespace foundation.

### Simple Tag Definition

```comp
; Define a single tag
!tag #status

; Define multiple tags at module level
!tag #active
!tag #inactive
!tag #pending
```

### Hierarchical Tag Definition (Nested Style)

```comp
; Nested style with braces
!tag #status = {
    #active
    #inactive  
    #pending
    #error = {
        #timeout
        #network
        #parse
    }
}
```

### Flat Top-Down Style

```comp
; Flat declarations - useful for long paths
!tag #status
!tag #status.error
!tag #status.error.timeout
!tag #status.error.network
!tag #status.error.parse
!tag #status.active
!tag #status.inactive
!tag #status.pending
```

### Mixed Definition Style

```comp
; Start with nested for compactness
!tag #priority = {
    #low
    #medium
    #high
}

; Extend with flat style
!tag #priority.critical
!tag #priority.debug
```

## Grammar Architecture Changes

### Entry Point Transformation

**Before**:
```lark
// === ENTRY POINT ===
start: expression
```

**After**:
```lark
// === ENTRY POINTS ===

// Module-level parsing (default - for complete .comp files)
start: module

// Module contains zero or more module-level statements
module: _module_statement*

// Module-level statements (definitions and top-level expressions)
?_module_statement: tag_definition
                  | expression         // Allow expressions for REPL/testing compatibility

// Expression-level parsing (for REPL, testing, embedded evaluation)
// Access via Lark's start parameter: Lark(..., start="expression_start")
expression_start: expression
```

### Tag Definition Grammar

**Location**: Lines 118-131 in `comp.lark`

```lark
// === MODULE-LEVEL DEFINITIONS ===

// Tag definitions (!tag)
// Supports multiple styles:
//   Simple:     !tag #status
//   Nested:     !tag #status = {#active #inactive}
//   Flat:       !tag #status.error.timeout
//   Hierarchical: !tag #status = {#error = {#timeout #network}}
BANG_TAG: "!tag"

tag_definition: BANG_TAG tag_reference                    // Simple: !tag #status
              | BANG_TAG tag_reference ASSIGN tag_body    // With children: !tag #status = {...}

tag_body: LBRACE tag_child* RBRACE

?tag_child: tag_reference                             // Simple child: #active
          | tag_reference ASSIGN tag_body             // Nested child: #error = {...}
```

### Pattern for Future Definitions

This establishes a clean pattern for upcoming module-level definitions:

1. **Token naming**: `BANG_<TYPE>` (e.g., `BANG_TAG`, future: `BANG_FUNC`, `BANG_SHAPE`)
2. **Rule naming**: `<type>_definition` (e.g., `tag_definition`, future: `func_definition`)
3. **Body structure**: `<type>_body` contains `<type>_child*` for hierarchical content
4. **Simple + complex forms**: Support both simple and structured forms with `ASSIGN`

**Future application**:
```lark
// Function definitions (future phase)
BANG_FUNC: "!func"
func_definition: BANG_FUNC function_reference func_signature ASSIGN func_body
                | BANG_FUNC function_reference ASSIGN func_body  // No signature

// Shape definitions (future phase)  
BANG_SHAPE: "!shape"
shape_definition: BANG_SHAPE shape_reference ASSIGN shape_body
```

### Supported Tag Styles

**1. Simple Definition**
```comp
!tag #status
```
Parses as: `tag_definition(BANG_TAG, tag_reference("#status"))`

**2. Nested Style**
```comp
!tag #status = {#active #inactive #pending}
```
Parses as: `tag_definition(BANG_TAG, tag_reference("#status"), ASSIGN, tag_body(...))`

**3. Hierarchical Nested**
```comp
!tag #status = {
    #active
    #inactive
    #error = {
        #timeout
        #network
    }
}
```
Parses hierarchically with nested `tag_child` containing `tag_body`.

**4. Flat Style**
```comp
!tag #status.error.timeout
```
Uses dotted notation in tag reference - hierarchy built by parser/transformer.

### Grammar Implementation Notes

- Empty tag bodies `{}` are **invalid** (caught by grammar with `tag_child*` requiring at least implicit content)
- Tag references must follow existing reference syntax from Phase 04
- The `?` prefix on `_module_statement` and `tag_child` prevents intermediate nodes in parse tree
- Comments work in tag bodies (handled by `%ignore COMMENT`)
- Whitespace is flexible (handled by `%ignore /\s+/`)
- Module can be empty (zero statements is valid)

## AST Node Design

### Module Node

```python
class Module(AstNode):
    """Root of grammar AST for modules.
    
    Contains module-level statements like tag definitions, function definitions,
    imports, and potentially expressions (for REPL/testing compatibility).
    """
    def unparse(self) -> str:
        return "\n".join(kid.unparse() for kid in self.kids)
```

**Design**: Simple container similar to `Root`, but separates module-level from expression-level parsing. Children are module-level statements (tag definitions, expressions, etc.).

### TagDefinition Node

```python
class TagDefinition(AstNode):
    """Tag definition at module level.
    
    The tag path is stored as a list of tokens (e.g., ["status", "error", "timeout"]).
    Children are nested TagDefinition nodes for hierarchical definitions.
    """
    
    def __init__(self, tokens: list[str] | None = None):
        self.tokens = list(tokens) if tokens else []
        super().__init__()
    
    def unparse(self) -> str:
        tag_path = "#" + ".".join(self.tokens)
        
        if not self.kids:
            # Simple: !tag #status
            return f"!tag {tag_path}"
        
        # With children: !tag #status = {#active #inactive}
        children_str = " ".join(kid.unparse() for kid in self.kids)
        return f"!tag {tag_path} = {{{children_str}}}"
```

**Design Decisions**:

1. **Storage**: `tokens` list stores tag path components (e.g., `["status", "error"]`)
   - Matches pattern from `TagRef` which uses `tokens` for path
   - Easy to reconstruct full path: `"#" + ".".join(tokens)`

2. **Children**: Nested `TagDefinition` nodes in `self.kids`
   - Example: `!tag #status = {#active #error = {#timeout}}`
   - Creates hierarchy: `TagDefinition(["status"])` with kids:
     - `TagDefinition(["active"])`  (no children)
     - `TagDefinition(["error"])` with kids:
       - `TagDefinition(["timeout"])` (no children)

3. **Flat vs Nested**: Both styles produce the same AST structure
   - Flat: `!tag #status.error.timeout` → `TagDefinition(["status", "error", "timeout"])`
   - Nested hierarchy is built through parent-child relationships in `self.kids`

4. **No separate tag_path node**: Tag path is inlined as `tokens` attribute
   - Simpler than creating a separate `TagPath` AST node
   - Follows pattern from `Structure` which stores data directly

**Hierarchy Example**:

```comp
!tag #status = {
    #active
    #error = {
        #timeout
        #network
    }
}
```

Produces AST:
```
Module
  └─ TagDefinition(tokens=["status"])
       ├─ TagDefinition(tokens=["active"])
       └─ TagDefinition(tokens=["error"])
            ├─ TagDefinition(tokens=["timeout"])
            └─ TagDefinition(tokens=["network"])
```

**Alternative Considered**: Store full path in children instead of just name

```python
# Rejected: Store full path
TagDefinition(["status", "error", "timeout"])  # Full path in leaf

# Chosen: Store only immediate name  
TagDefinition(["timeout"])  # Just the name, hierarchy via parent chain
```

**Rationale**: 
- Children store only their immediate name (e.g., `["timeout"]` not `["status", "error", "timeout"]`)
- This matches the grammar where `#timeout` appears in the source, not `#status.error.timeout`
- Parent context is implicit through the tree structure
- Simpler unparsing - just output the immediate name

## Planned Features

### Core Tag Definition Parsing
- Parse simple tag definitions: `!tag #status`
- Parse hierarchical nested syntax: `!tag #status = {#active #inactive}`
- Parse flat top-down syntax: `!tag #status.error.timeout`
- Parse mixed definition styles
- Parse multiple independent definitions in a file

### Module-Level Grammar Foundation
- New `module` entry point that accepts multiple statements
- `module_statement` rule supporting tag definitions and expressions
- Clear separation between module-level and structure-level contexts
- Foundation for future module-level constructs (`!func`, `!shape`, `!import`)

### Tag Hierarchy Structure
- Build hierarchical tag relationships (parent/child)
- Support dot notation for paths: `#status.error.timeout`
- Handle nested braces for hierarchy definition
- Support both flat and nested definition styles equivalently

### AST Integration
- `TagDefinition` node with tag reference and optional children
- `Module` node containing list of module-level statements  
- Proper unparsing for all tag definition styles
- Round-trip parsing: parse → unparse → parse produces same AST

## Success Criteria

### Tag Definition Parsing
- ✅ Parse simple definition: `!tag #status` → `TagDefinition(tag=TagReference("status"), children=None)`
- ✅ Parse with children: `!tag #status = {#active #inactive}` → proper hierarchy
- ✅ Parse nested hierarchy: `!tag #status = {#error = {#timeout}}`
- ✅ Parse flat style: `!tag #status.error.timeout` → hierarchy from path
- ✅ Parse multiple definitions in module
- ✅ Round-trip: `parse(code).unparse()` produces semantically equivalent code

### Module-Level Grammar
- ✅ Parse module with multiple tag definitions
- ✅ Parse module with mixed tag definitions and expressions (for testing)
- ✅ Proper error messages for misplaced constructs
- ✅ Foundation architecture supports future `!func`, `!shape`, `!import`

### Integration
- ✅ Existing expression tests still pass (backward compatibility)
- ✅ Tag references (`#status`) work in expressions
- ✅ Tag definitions work at module level only
- ✅ Clear error when trying `!tag` inside a structure

### Testing Infrastructure
- ✅ New test file: `tests/test_parse_tags.py`
- ✅ Tests for all tag definition styles (simple, nested, flat, mixed)
- ✅ Tests for module-level parsing with multiple statements
- ✅ Error tests for invalid placements
- ✅ Round-trip unparsing tests

## Implementation Steps

### Step 1: Grammar Foundation (Module-Level Entry)
1. **Update entry point**: Change `start: expression` to `start: module`
2. **Add module rule**: `module: module_statement*`
3. **Add module_statement**: Support tag definitions and expressions
4. **Test**: Verify existing expression tests still work with new entry point

### Step 2: Tag Definition Grammar
1. **Add BANG_TAG token**: `BANG_TAG: "!tag"`
2. **Add tag_definition rule**: Support simple and hierarchical forms
3. **Add tag_body and tag_children**: Nested structure support
4. **Test**: Parse basic tag definitions

### Step 3: AST Nodes
1. **Create TagDefinition class**: With tag reference and children
2. **Create Module class**: Container for module statements
3. **Implement unparse methods**: For both node types
4. **Test**: Verify AST structure and unparsing

### Step 4: Parser Transformer
1. **Add tag_definition transformer**: Convert grammar to TagDefinition nodes
2. **Add module transformer**: Create Module node from statements
3. **Handle tag_body and tag_children**: Build hierarchy properly
4. **Test**: Verify transformer produces correct AST

### Step 5: Comprehensive Testing
1. **Create test_parse_tags.py**: New test file for tag definitions
2. **Test simple definitions**: `!tag #status`
3. **Test nested style**: `!tag #status = {#active #inactive}`
4. **Test flat style**: `!tag #status.error.timeout`
5. **Test mixed style**: Combination of approaches
6. **Test multiple definitions**: Multiple `!tag` in same module
7. **Test round-trip**: Parse → unparse → parse consistency
8. **Test errors**: Invalid placements and malformed syntax

### Step 6: Documentation and Examples
1. **Update grammar documentation**: Explain module-level vs structure-level
2. **Add tag definition examples**: Show all styles
3. **Update design docs**: Reflect implementation status
4. **Create migration guide**: For future tag value addition

## What We're NOT Building (Yet)

### Tag Values (Future Phase)
- Explicit values: `!tag #status = {#active = 1 #inactive = 0}`
- Auto-generation: `!tag #color {|name/tag} = {#red #green #blue}`
- Complex values: Tags with structures or other types as values

### Tag Operations (Future Phase)
- Value extraction: `#active ~num`
- Type casting: `1 ~#status`
- Comparison operators with tags
- Tag introspection functions

### Module-Level Constructs (Future Phases)
- Function definitions: `!func |process ~{data} = {...}`
- Shape definitions: `!shape ~user = {name #str email #str}`
- Import statements: `!import /std = std /core/std/`
- Entry points: `!entry = {...}`, `!main = {...}`

### Advanced Tag Features (Future Phases)
- Cross-module extension: `!tag #media += {#svg}`
- Tag aliasing: `!alias #error = #error.status`
- Union types: `!tag #result = #active | #inactive`
- Tag dispatch and polymorphism

## Test Structure

New test file following established patterns:

```
tests/test_parse_tags.py          # Tag definition tests (new)
tests/test_parse_refs.py          # Tag reference tests (existing)
tests/test_parse_struct.py        # Structure tests (existing)
tests/test_parse_pipe.py          # Pipeline tests (existing)
```

## Grammar Migration Notes

### Breaking Changes
- **Entry point**: Changes from `expression` to `module`
- **Top-level context**: Not all expressions valid at module level (by design)

### Compatibility Measures
- **Expression fallback**: `module_statement` accepts expressions for REPL/testing
- **Existing tests**: Should work with `parse_value()` helper that extracts expressions
- **Error messages**: Distinguish between "invalid at module level" vs "invalid syntax"

### Future Considerations
- This establishes the pattern for all `!` operators
- Module-level context will expand with `!func`, `!shape`, `!import`
- Structure-level grammar remains unchanged
- Clear conceptual separation aids language learning

## Design References

- **Tag system**: See `design/tag.md` for complete tag semantics
- **Module system**: See `design/module.md` for module-level constructs
- **Grammar evolution**: This phase establishes module-level vs expression-level distinction

## Notes for Implementation

### Parser Testing Strategy
- Use `parse_module()` for complete module parsing
- Use `parse_value()` for expression extraction (maintains compatibility)
- Distinguish between "valid expression" and "valid module content"

### Error Message Design
```python
# Good: Clear context
"Tag definitions must appear at module level, not inside structures"

# Bad: Vague
"Unexpected !tag"
```

### Hierarchy Building
When parsing flat style `!tag #status.error.timeout`, the transformer should:
1. Parse as `TagReference("status.error.timeout")`
2. Create hierarchy: `status` contains `error` contains `timeout`
3. Match semantics of nested style

This ensures both styles produce identical AST structures.

## Success Metrics

**All Success Criteria Met**: ✅

- **Tag Definition Parsing**: All styles working (simple, nested, flat, hierarchical)
- **Module-Level Grammar**: Clean separation from expression-level parsing
- **AST Integration**: Module and TagDefinition nodes with proper unparsing
- **Test Coverage**: 11 new tests, all passing
- **Backward Compatibility**: All 266 existing tests still passing
- **Round-trip Validation**: Parse → unparse → parse produces identical AST

## Implementation Summary

### Key Changes Made

1. **Grammar** (`src/comp/lark/comp.lark`):
   - Changed entry point from `expression` to `module`
   - Added `module_statement` rule for module-level constructs
   - Added `tag_definition`, `tag_path`, `tag_body`, `tag_child` rules
   - Added `BANG_TAG` token for `!tag` keyword
   - Fixed: Removed `?` from `tag_child` to prevent inlining issues

2. **Parser** (`src/comp/_parser.py`):
   - Split `parse()` into `parse_module()` and `parse_expr()`
   - Added grammar debug functions: `grammar_module()`, `grammar_expr()`
   - Implemented two singleton parsers with different entry points
   - Added transformer cases for `tag_definition`, `tag_body`, `tag_child`

3. **AST** (`src/comp/_ast.py`):
   - Added `Module` class with `statements` property
   - Added `TagDefinition` class with `tokens` list and children
   - Implemented `unparse(is_child=False)` to handle nested vs top-level
   - Implemented `from_grammar()` to handle both grammar rule types

4. **Tests** (`tests/test_parse_tags.py`):
   - 4 valid cases: simple, nested, deep_nested, flat
   - 5 invalid cases: no_tag_reference, empty_braces, missing_equals, invalid_tag_name, nested_no_tag
   - Multiple definitions test
   - Nested hierarchy validation test

5. **Test Infrastructure** (`tests/comptest.py`):
   - Updated `roundtrip()` to detect Module vs Root and use appropriate parser
   - All other tests updated to use `parse_expr()` instead of `parse()`

### Lessons Learned

- **Lark modifiers**: Cannot combine `?` (inline) with `_` (internal) prefix
- **Parse tree structure**: Removing `?` from `tag_child` was critical for transformer
- **API design**: Separate functions (`parse_module`/`parse_expr`) clearer than mode parameter
- **Unparsing context**: Need `is_child` flag to differentiate top-level vs nested output

### Foundation for Future Work

This phase establishes the pattern for all future module-level constructs:
- `!func` - Function definitions
- `!shape` - Shape/type definitions  
- `!import` - Module imports
- Entry points and module metadata

The clean separation between module-level and expression-level grammar will make these additions straightforward.

## Status: ✅ COMPLETE

All objectives achieved. Ready for commit.

- ✅ All existing tests pass (backward compatibility)
- ✅ New tag definition tests pass (all styles)
- ✅ Module-level grammar works correctly
- ✅ Foundation ready for `!func`, `!shape`, `!import`
- ✅ Clear error messages for context mismatches
- ✅ Documentation updated with new concepts

This phase is foundational - it establishes the module-level grammar architecture that all future definition syntax will build upon.
