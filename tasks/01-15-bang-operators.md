# Phase 01-15: Non-Definition Bang Operators

**Status**: ⏸️ DEFERRED  
**Reason**: Not needed for Chapters 02-04. Will implement when actually required.

## Deferred Operators

The following bang operators exist in the design docs but aren't needed yet:

- `!import` - Module imports (Chapter ~06+)
- `!doc` - Documentation (Chapter ~05+)
- `!pure` - Pure function marking (Chapter ~03+)
- `!delete` - Field deletion (Chapter ~03+)
- `!main` / `!entry` - Entry points (Chapter ~06+)
- `!alias` - Aliasing (TBD)
- `!transact` - Transactions (Chapter ~08+)
- `!describe` - Descriptions (Chapter ~07+)

## Current Parser Completeness

**Chapter 01 is COMPLETE!** We can parse:

✅ Numbers, strings, identifiers, references  
✅ Structures with fields, nesting, spreading  
✅ Mathematical, comparison, logical operators  
✅ Pipelines with all pipe operators  
✅ Tag definitions with values, bodies, generators  
✅ Shape definitions with fields, unions, inline shapes  
✅ Function definitions with args and bodies  

**This is sufficient to begin Chapter 02: Values and Expressions!**

## When to Revisit

We'll implement these operators when we actually need them:
- Chapter 02-04: Focus on evaluation, not new syntax
- Chapter 05+: Add operators as semantics require them

---

**Decision**: Move forward to implementing runtime behavior rather than parsing more syntax we won't use yet.

## Goals

Implement parsing for all remaining bang (`!`) operators that aren't definition forms (`!tag`, `!shape`, `!func` are already done). These operators provide module-level directives, documentation, deletion, and other metadata.

## What We're Building

### Bang Operators to Implement

The following operators need grammar rules and AST nodes:

1. **`!import`** - Import modules from various sources
   ```comp
   !import /store = std /core/store/
   !import /utils = comp /./lib/utils/
   !import /numpy = python "numpy"
   !import /api = openapi /https:/api.example.com/swagger.json/
   ```

2. **`!doc`** - Documentation strings for definitions
   ```comp
   !doc "Process different types of data appropriately"
   !func |process ~data = {???}
   
   !doc impl "Saves to primary database"
   !func |process #database ~data = {???}
   ```

3. **`!pure`** - Mark function as pure (no side effects)
   ```comp
   !pure
   !func |add ~num ^{b ~num} = {@ + b}
   ```

4. **`!delete`** - Delete field from structure (used in structure expressions)
   ```comp
   cleaned = {..original !delete temp-field !delete old-field}
   ```

5. **`!main`** - Mark module entry point
   ```comp
   !main = {
       |start-app
   }
   ```

6. **`!test`** - Define test cases (likely future, but worth considering)
   ```comp
   !test "addition works correctly" = {
       result = |add 2 3
       result == 5
   }
   ```

### AST Nodes Needed

- `ImportStatement` - For `!import` directives
  - Properties: namespace name, source type (std/comp/python/etc), trail/path, fallbacks
  
- `DocString` - For `!doc` directives
  - Properties: text content, target (next definition or specific impl)
  
- `PureDirective` - For `!pure` markers
  - Properties: (minimal, just marks next function as pure)
  
- `DeleteOp` - For `!delete` in structures
  - Properties: field name to delete
  
- `MainDirective` - For `!main` entry points
  - Properties: body expression
  
- `TestDirective` - For `!test` (optional for now)
  - Properties: name, test body

## Success Criteria

- [ ] Grammar rules for all 6 bang operators
- [ ] AST nodes created with proper `from_grammar()` methods
- [ ] Parser handles all operator variants
- [ ] Unit tests for each operator type
- [ ] Roundtrip (parse → unparse → parse) works correctly
- [ ] Documentation of operator semantics

## Implementation Plan

### Step 1: Import Statement
- [ ] Add `!import` grammar rule with source variants (std, comp, python, etc.)
- [ ] Create `ImportStatement` AST node
- [ ] Handle trail notation in import paths
- [ ] Support fallback syntax (`??`)
- [ ] Tests for various import forms

### Step 2: Documentation
- [ ] Add `!doc` grammar rule
- [ ] Create `DocString` AST node
- [ ] Handle plain doc vs `!doc impl`
- [ ] Tests for documentation attachment

### Step 3: Pure Directive
- [ ] Add `!pure` grammar rule (simple marker)
- [ ] Create `PureDirective` AST node
- [ ] Tests for pure function marking

### Step 4: Delete Operator
- [ ] Add `!delete` grammar rule (in structure context)
- [ ] Create `DeleteOp` AST node
- [ ] Tests for field deletion in structures

### Step 5: Main Entry Point
- [ ] Add `!main` grammar rule
- [ ] Create `MainDirective` AST node
- [ ] Tests for main entry points

### Step 6: Test Directive (Optional)
- [ ] Add `!test` grammar rule
- [ ] Create `TestDirective` AST node
- [ ] Tests for test definitions

## Grammar Considerations

### Module-Level vs Expression-Level

Most of these are **module-level** statements (appear at top level of module):
- `!import` - Module-level only
- `!doc` - Module-level, before definitions
- `!pure` - Module-level, before function
- `!main` - Module-level only
- `!test` - Module-level only

Exception:
- `!delete` - Expression-level, used inside structures

### Ordering Rules

Some operators must appear in specific orders:
- `!doc` must come before the definition it documents
- `!pure` must come before the function definition it marks
- `!import` typically at module top, but can appear anywhere

## What We're NOT Building (Yet)

- **Execution/evaluation** - Just parsing to AST, no runtime behavior
- **Import resolution** - Not loading actual modules
- **Documentation extraction** - Not generating docs
- **Test execution** - Not running tests
- **Validation** - Not checking if imports exist or docs are valid

## Design Questions to Resolve

1. **Import paths**: How to represent trail notation in AST? Store as string or parse into structure?
2. **Doc attachment**: Should `DocString` be a child of the thing it documents, or a separate node?
3. **Pure validation**: Should parser validate that `!pure` is followed by a function?
4. **Delete scope**: Can `!delete` only appear in structures, or also in other contexts?

## Expected Challenges

- **Trail parsing**: Import paths use complex trail notation - may need separate parser
- **Operator context**: Some operators valid only in specific contexts
- **Order dependencies**: `!doc` and `!pure` must precede what they modify
- **Fallback syntax**: Import fallbacks use `??` which is also used elsewhere

## Files to Create/Modify

- `src/comp/lark/comp.lark` - Grammar rules for all operators
- `src/comp/_ast.py` - New AST node classes
- `src/comp/_parser.py` - Parser match cases for new nodes
- `tests/test_parse_import.py` - Import statement tests
- `tests/test_parse_doc.py` - Documentation tests  
- `tests/test_parse_directives.py` - Pure, main, test tests
- `tests/test_parse_delete.py` - Delete operator tests

## Success Metrics

- All 6 operators parse correctly
- AST nodes have complete metadata
- Roundtrip parsing maintains fidelity
- Parser provides clear errors for malformed operators
- Code coverage >90% for new parsing code

## Next Steps After Completion

With all parsing complete:
1. Move to Chapter 02: Values and Expressions
2. Begin implementing runtime evaluation
3. Start building the actual language semantics

---

**Note**: This is the final parsing phase of Chapter 01. After this, we have a complete parser that can handle all Comp syntax. The next chapter focuses on making the parsed AST actually *do* something.
