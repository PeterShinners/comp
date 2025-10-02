# Parse Function Split: parse_module() and parse_expr()

**Related to**: Phase 01-11 (Tag Definitions - Module-Level Grammar)  
**Status**: 📋 **PLANNING**

## Overview

Replace the current `comp.parse()` function with two distinct functions:

- **`parse_module()`** - Parse complete modules with module-level statements (`!tag`, `!func`, etc.)
- **`parse_expr()`** - Parse single expressions for REPL, testing, and embedded contexts

This is a **clean break** - simple search-and-replace to upgrade the entire codebase at once.

## Current State

```python
# src/comp/_parser.py
def parse(text: str):
    """Parse Comp code and return an AST node."""
    # Currently uses 'start: expression' grammar
    # Returns Root node containing expression
```

```python
# tests/comptest.py
def parse_value(expression, cls=comp.AstNode, index=0):
    """Parse expression and return the specified child of Root."""
    result = comp.parse(expression)
    node = result.kids[index] if result.kids else result
    # ...
```

## New API

```python
def parse_module(text: str) -> Module:
    """Parse a complete Comp module with module-level statements."""
    # Uses 'start: module' grammar entry point
    # Returns Module node

def parse_expr(text: str) -> Root:
    """Parse a single Comp expression for REPL/testing/embedded contexts."""
    # Uses 'start: expression' grammar entry point
    # Returns Root node containing expression
```

**No backward compatibility** - `comp.parse()` is removed entirely.

## Grammar Changes

### Current Grammar

```lark
// === ENTRY POINT ===
start: expression
```

### New Grammar

```lark
// === ENTRY POINTS ===

// Module-level parsing (default for files)
?start: module

// Module contains zero or more module-level statements
module: module_statement*

?module_statement: tag_definition
                 | expression        // For compatibility/testing

// Expression-level parsing (for REPL/testing)
// This will be accessed via a separate start rule
expression_start: expression
```

### Multiple Start Rules in Lark

Lark supports multiple start rules. We'll use the `start` parameter when creating the parser:

```python
def _get_module_parser() -> lark.Lark:
    """Get parser for module-level parsing."""
    # Uses default start rule: module
    
def _get_expr_parser() -> lark.Lark:
    """Get parser for expression-level parsing."""
    # Uses start="expression" parameter
```

## Implementation Plan

### Step 1: Update Grammar
1. Change grammar entry point from `start: expression` to `start: module`
2. Add `module` and `module_statement` rules
3. Keep `expression` rule for expression parser

### Step 2: Implement New Functions
1. Rename `parse()` to `parse_module()`
2. Add `parse_expr()` using expression grammar entry point
3. Update `_get_parser()` → `_get_module_parser()` and `_get_expr_parser()`
4. Remove old `parse()` function entirely

### Step 3: Update All Callsites (Search & Replace)
1. **In `comptest.py`**: Change `comp.parse()` → `comp.parse_expr()`
2. **In `test_parse_tags.py`**: Change `comp.parse()` → `comp.parse_module()`
3. **Global search**: Verify no other direct `comp.parse()` calls exist

Done. No migration period, no deprecation warnings, clean break.

## Callsite Updates

### comptest.py
```python
# Before
def parse_value(expression, cls=comp.AstNode, index=0):
    result = comp.parse(expression)  # OLD
    # ...

def roundtrip(ast):
    reparsed = comp.parse(unparsed)  # OLD
    # ...

# After
def parse_value(expression, cls=comp.AstNode, index=0):
    result = comp.parse_expr(expression)  # NEW
    # ...

def roundtrip(ast):
    if isinstance(ast, comp.Module):
        reparsed = comp.parse_module(unparsed)  # NEW
    else:
        reparsed = comp.parse_expr(unparsed)  # NEW
    # ...
```

### test_parse_tags.py
```python
# Before
result = comp.parse("!tag #status")  # OLD

# After
result = comp.parse_module("!tag #status")  # NEW
```

All other test files use `comptest.parse_value()`, so they're updated automatically.

## Implementation Complete

### Changes Made

1. **Parser Functions** (`src/comp/_parser.py`):
   - `parse_module(text: str) -> Module` - For complete .comp files
   - `parse_expr(text: str) -> Root` - For expressions/REPL/testing
   - `grammar_module(code: str)` - Debug utility for module grammar
   - `grammar_expr(expression: str)` - Debug utility for expression grammar
   - `_get_module_parser()` - Singleton with `start="module"`
   - `_get_expr_parser()` - Singleton with `start="expression_start"`

2. **Test Infrastructure** (`tests/comptest.py`):
   - `parse_value()` → Uses `parse_expr()` internally
   - `roundtrip()` → Detects Module vs Root, uses appropriate parser

3. **Test Updates**:
   - All tests updated to use `parse_expr()` instead of `parse()`
   - New tag tests use `parse_module()` appropriately
   - No test failures introduced

## Results

✅ Clean API with clear intent  
✅ Type-safe returns (Module vs Root)  
✅ All 266 existing tests still passing  
✅ Foundation for module-level constructs established

## Status: ✅ COMPLETE

### Why Two Functions Instead of Type Parameter?

```python
# Rejected: Type parameter approach (like Python's compile)
result = comp.parse(code, mode='module')  # or mode='expr'
result = comp.parse(code, mode='expression')

# Preferred: Separate functions
module = comp.parse_module(code)
expr_root = comp.parse_expr(code)
```

**Advantages of separate functions:**

1. **Type safety**: Return types are clear (`Module` vs `Root`)
2. **Discoverability**: IDE autocomplete shows both options clearly
3. **No invalid states**: Can't pass wrong mode string
4. **Simpler API**: No optional parameters to remember
5. **Clearer intent**: Function name describes what you're doing
6. **No runtime checking**: Type checkers can validate usage

### Return Type Consistency

- **`parse_module()`** returns `Module` directly
- **`parse_expr()`** returns `Root` node (for consistency with existing code)
  - Expression is available as `result.kids[0]`
  - Matches current behavior
  - `comptest.parse_value()` unwraps automatically

## Documentation Updates

### API Reference

```python
"""
Parsing Functions
-----------------

parse_module(text: str) -> Module
    Parse a complete Comp module file with module-level statements.
    Use for: .comp files, imports, full program parsing
    
parse_expr(text: str) -> Root
    Parse a single expression.
    Use for: REPL, testing, embedded evaluation, structure fields
    
parse(text: str) -> AstNode  [DEPRECATED]
    Legacy function. Use parse_module() or parse_expr() instead.
"""
```

### Usage Examples

```python
# Parse a module file
with open("myapp.comp") as f:
    module = comp.parse_module(f.read())
    
# REPL: parse user input
user_input = "2 + 3"
result = comp.parse_expr(user_input)
print(result.kids[0].unparse())  # "2 + 3"

# Testing: parse specific constructs
struct = comp.parse_expr("{x=1, y=2}")
assert isinstance(struct.kids[0], comp.Structure)
```

## Benefits

### Clarity
- Explicit distinction between module and expression parsing
- No ambiguity about what grammar is being used
- Matches the conceptual model (module-level vs expression-level)

### Type Safety
- Return types are clear and specific
- Type checkers can validate usage patterns
- No runtime mode checking needed

### Maintainability
- Each function has single responsibility
- Grammar entry points map 1:1 to functions
- Testing is more explicit about context

### Future-Proofing
- Room for additional parse contexts if needed
- Clean migration path from legacy `parse()`
- Establishes pattern for other dual-context features

## Alternative Considered: Mode Parameter

```python
def parse(text: str, mode: Literal['module', 'expr'] = 'module') -> AstNode:
    """Parse with specified mode."""
```

**Rejected because:**
- Runtime string checking needed
- Return type is ambiguous (`AstNode`)
- Easy to typo mode string
- Less discoverable in IDE
- Two functions is clearer

## Implementation Checklist

- [ ] Update grammar: change `start: expression` to `start: module`
- [ ] Add module grammar rules (`module`, `module_statement`)
- [ ] Rename `parse()` → `parse_module()` in `_parser.py`
- [ ] Add `parse_expr()` function (uses expression grammar)
- [ ] Create `_get_module_parser()` and `_get_expr_parser()` helpers
- [ ] Update `__all__` exports: remove `parse`, add `parse_module` and `parse_expr`
- [ ] **Search & replace in tests**: `comp.parse(` → `comp.parse_expr(`
- [ ] Update `test_parse_tags.py`: use `parse_module()` instead
- [ ] Update `comptest.parse_value()`: use `parse_expr()`
- [ ] Update `comptest.roundtrip()`: check type, call appropriate parser
- [ ] Run test suite - fix any remaining issues
- [ ] Done!

## Notes

- Both parsers share the same grammar file, just different entry points
- Two singleton parser instances (cached separately)
- Breaking change, but trivial to upgrade (search & replace)
- Most test code uses helpers, so only a few files need updates
- Clean, simple API that matches the conceptual model


# Phase 11 Implementation Notes

**Date**: October 2, 2025  
**Status**: ✅ Complete

## What Was Implemented

Phase 11 introduces **module-level grammar** to the Comp language, establishing a clean separation between:
- **Module-level**: Definitions like `!tag`, `!func`, `!shape` (future)
- **Expression-level**: Values, structures, pipelines

### Key Accomplishments

1. **Parse API Split**: 
   - `parse_module(text) -> Module` - For .comp files
   - `parse_expr(text) -> Root` - For REPL/testing/expressions
   - Clean, type-safe API with no mode parameters

2. **Tag Definition Parsing**:
   - Simple: `!tag #status`
   - Nested: `!tag #status = {#active #inactive}`
   - Hierarchical: `!tag #status = {#error = {#timeout #network}}`
   - Flat: `!tag #status.error.timeout`

3. **New AST Nodes**:
   - `Module` - Container for module-level statements
   - `TagDefinition` - Tag definitions with hierarchical children

4. **Test Coverage**:
   - 11 new tag definition tests (all passing)
   - 266 existing tests (all still passing)
   - Comprehensive round-trip validation

## Technical Challenges & Solutions

### Challenge 1: Lark Grammar Rule Modifiers
**Problem**: Used `?_module_statement` combining `?` (inline) and `_` (internal) modifiers.  
**Error**: `GrammarError: Inlined rules (_rule) cannot use the ?rule modifier.`  
**Solution**: Changed to `module_statement` (removed both modifiers).

### Challenge 2: tag_child Parse Tree Structure  
**Problem**: With `?tag_child`, children weren't being parsed correctly (only 1 child instead of 3).  
**Cause**: The `?` modifier was inlining the rule, making the parse tree incompatible with transformer.  
**Solution**: Removed `?` from `tag_child` rule so it appears explicitly in the parse tree.

### Challenge 3: Nested Tag Unparsing
**Problem**: Nested tags unparsed as `!tag #status = {!tag #error}` instead of `{#error = {...}}`.  
**Cause**: Child TagDefinitions were unparsing with `!tag` prefix like top-level definitions.  
**Solution**: Added `is_child` parameter to `unparse()` to differentiate contexts.

### Challenge 4: Test Infrastructure  
**Problem**: `roundtrip()` was always using `parse_expr()` for reparsing.  
**Issue**: Module objects need `parse_module()` for round-trip validation.  
**Solution**: Updated `roundtrip()` to detect Module vs Root and use appropriate parser.

### Challenge 5: TagDefinition.fromGrammar() Context
**Problem**: Called with both `tag_definition` and `tag_child` grammar rules with different structures.  
**Error**: `AttributeError: 'Token' object has no attribute 'children'`  
**Solution**: Check `tree.data` to handle both rule types with different child indexing.

## Files Modified

### Core Implementation
- `src/comp/lark/comp.lark` - Grammar with module-level entry point
- `src/comp/_parser.py` - Split parse functions, transformer updates
- `src/comp/_ast.py` - Module and TagDefinition nodes
- `src/comp/__init__.py` - Export new parse functions

### Testing
- `tests/test_parse_tags.py` - NEW: 11 tag definition tests
- `tests/comptest.py` - Updated roundtrip() and parse helpers
- `tests/test_parse_*.py` - All updated to use `parse_expr()`

### Documentation
- `tasks/01-11-tag-definitions.md` - Complete phase documentation
- `tasks/01-11-parse-function-split.md` - Parse API split rationale
- `tasks/README.md` - Updated task status

## Code Changes Summary

### Grammar Changes
```lark
// Before
start: expression

// After  
start: module
module: module_statement*
?module_statement: tag_definition | expression
expression_start: expression  // For parse_expr()

// New rules
tag_definition: BANG_TAG tag_path [ASSIGN tag_body]
tag_path: "#" reference_identifiers
tag_body: LBRACE tag_child* RBRACE
tag_child: tag_path | tag_path ASSIGN tag_body  // No ? prefix!
```

### Parser Changes
```python
# Before
def parse(text: str):
    parser = _get_parser()
    # ...

# After
def parse_module(text: str) -> Module:
    parser = _get_module_parser()  # start="module"
    # ...

def parse_expr(text: str) -> Root:
    parser = _get_expr_parser()  # start="expression_start"
    # ...
```

### AST Changes
```python
class Module(AstNode):
    @property
    def statements(self) -> list['AstNode']:
        return self.kids
    
    def unparse(self) -> str:
        return "\n".join(kid.unparse() for kid in self.kids)

class TagDefinition(AstNode):
    def __init__(self, tokens: list[str] | None = None):
        self.tokens = list(tokens) if tokens else []
        super().__init__()
    
    def unparse(self, is_child: bool = False) -> str:
        # Different output for top-level vs nested
```

## Testing Strategy

### Test Organization
- **Valid cases**: Simple, nested, deep_nested, flat
- **Invalid cases**: no_tag_reference, empty_braces, missing_equals, invalid_tag_name, nested_no_tag  
- **Edge cases**: Multiple definitions, mixed hierarchy styles
- **Round-trip**: All valid cases must parse → unparse → parse identically

### Test Helper Updates
- `parse_value()` - Now uses `parse_expr()` internally
- `roundtrip()` - Detects Module vs Root automatically
- All existing tests - Updated to use `parse_expr()` explicitly

## Foundation for Future Work

This implementation establishes patterns for all future module-level constructs:

### Immediate Next Steps (Future Phases)
- `!func` - Function definitions
- `!shape` - Shape/type definitions
- `!import` - Module imports

### Grammar Pattern Established
```lark
BANG_<TYPE>: "!<type>"
<type>_definition: BANG_<TYPE> <params> [ASSIGN <body>]
<type>_body: LBRACE <type>_child* RBRACE
<type>_child: <params> | <params> ASSIGN <type>_body
```

### Parser Pattern Established
```python
case '<type>_definition':
    _node(_ast.<Type>Definition, walk=kids)
case '<type>_body':
    generate_ast(parent, kids)
    continue
case '<type>_child':
    _node(_ast.<Type>Definition, walk=kids)
```

## Lessons for Future Phases

1. **Lark modifiers are picky**: Test grammar changes early, watch for modifier conflicts
2. **Inlining matters**: `?` changes parse tree structure - only use when transformer expects it
3. **Context in unparsing**: Top-level vs nested may need different output formats
4. **Round-trip everything**: Best way to catch unparsing bugs early
5. **Split concerns cleanly**: Module vs expression separation was the right choice

## Performance Notes

- **Parser singletons**: Two cached parser instances (module and expr) avoid recompilation
- **Grammar size**: ~270 lines total (reasonable)
- **Test speed**: All 277 tests run in ~1-2 seconds

## What This Phase Enables

✅ Module-level tag definitions  
✅ Hierarchical tag namespaces  
✅ Foundation for all `!` operators  
✅ Clean separation of module vs expression contexts  
✅ Type-safe parsing API  

## Status: Ready for Commit

All objectives met, all tests passing, documentation complete.
