# Phase 11: Tag Definitions (Module-Level Grammar)

**Status**: 🔄 **IN PROGRESS**  
**Started**: October 2025

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

The grammar entry point needs to change from single expression parsing to module-level parsing:

**Current (expression-level)**:
```lark
start: expression
```

**New (module-level)**:
```lark
start: module

module: module_statement*

?module_statement: tag_definition
                 | expression        // For REPL and testing compatibility
```

This allows the parser to handle both complete modules and single expressions (for REPL/testing).

### Tag Definition Grammar

```lark
// === MODULE-LEVEL DEFINITIONS ===

BANG_TAG: "!tag"

tag_definition: BANG_TAG tag_reference
              | BANG_TAG tag_reference ASSIGN tag_body

tag_body: LBRACE tag_children RBRACE

tag_children: tag_child*

?tag_child: tag_reference                    // Simple: #active
          | tag_reference ASSIGN tag_body    // With children: #error = {...}
```

### Integration Considerations

- **Backward compatibility**: Existing expression tests should still work
- **REPL support**: Single expressions should parse as valid modules
- **Error messages**: Clear distinction between module-level and expression-level contexts
- **Future expansion**: Architecture supports adding `!func`, `!shape`, `!import` later

## AST Node Design

### TagDefinition Node

```python
@dataclass
class TagDefinition(AstNode):
    """
    Represents a tag definition at module level.
    
    Examples:
        !tag #status
        !tag #status = {#active #inactive}
        !tag #status.error.timeout
    """
    tag: TagReference      # The tag being defined (e.g., #status.error)
    children: list[TagDefinition] | None  # Child tag definitions, if any
    
    def unparse(self) -> str:
        if self.children is None:
            return f"!tag {self.tag.unparse()}"
        
        # Format children
        child_strs = [child.unparse() for child in self.children]
        children_formatted = " ".join(child_strs)
        
        return f"!tag {self.tag.unparse()} = {{{children_formatted}}}"
```

### Module Node

```python
@dataclass  
class Module(AstNode):
    """
    Represents a complete Comp module (file).
    
    Contains module-level statements: tag definitions, function definitions,
    imports, and potentially top-level expressions (for REPL compatibility).
    """
    statements: list[AstNode]  # List of module-level statements
    
    def unparse(self) -> str:
        return "\n".join(stmt.unparse() for stmt in self.statements)
```

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

- ✅ All existing tests pass (backward compatibility)
- ✅ New tag definition tests pass (all styles)
- ✅ Module-level grammar works correctly
- ✅ Foundation ready for `!func`, `!shape`, `!import`
- ✅ Clear error messages for context mismatches
- ✅ Documentation updated with new concepts

This phase is foundational - it establishes the module-level grammar architecture that all future definition syntax will build upon.
