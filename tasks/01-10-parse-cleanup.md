# Phase 01-10: Parse Cleanup and Refactoring

**Status**: ✅ COMPLETED  

## Overview

The grammar, ast nodes, and unit tests had become too messy to continue. Significant refactoring and failed experiments polluted the code to an unusable mess. These needed to be rebuilt from a fresh start, using the knowledge gained from previous phases to create a clean and coherent design.

This phase represents a major architectural overhaul to transform the parser from a brittle, bottom-up transformer approach to an elegant, top-down visitor pattern with consistent naming and structure.

## Problems

* **Grammar chaos**: Had become un-understandable. Edits were a trial and error exercise to see what came out. Conflicting rules and delicate priorities were solving problems with basic parts of the language.
* **AST translation boilerplate**: Nodes and translation required so much boilerplate it was unreadable. 
* **Inconsistent terminology**: No naming pattern or consistent terminology across the grammar and ast nodes.
* **Brittle unit tests**: Tightly coupled to ast design; couldn't change one field or any minimal changes to the ast nodes without rewriting many tests across many files.
* **Code clutter**: Large amounts of unused and over-disabled code littered everything.
* **Bottom-up translation**: Grammar translation was written bottom-up with lark's transformer. This meant conversions had no context, and higher level conversions often dealt with mixed astnode lark trees combined together.
* **Cascading breakage**: Fix any one little thing, break 10 unrelated things.
* **No position tracking**: Ast nodes didn't track position of symbols in original source
* **Inconsistent traversal**: Walking ast nodes required conditional handling and inconsistent patterns

## Goals

- [X] Rewrite grammar using clean patterns and shared behaviors
- [X] AST node conversion as top-down visitor (not bottom-up transformer)
- [X] AST nodes must support positional tracking
- [X] Rewrite AST nodes for consistent navigation and future processing
- [X] AST nodes provide higher level calls for simpler/flexible unit testing
- [X] Unified identifier rule handling all scope cases (no separate `scope` rule)
- [X] All binary operators have consistent tree structure
- [X] Pipeline AST nodes properly created for all pipeline contexts
- [X] Rewrite parsing unit tests in more consistent style
- [X] Unit tests take advantage of simpler AST nodes and features
- [X] Maintain all language concepts from previous chapters


## What We're NOT Building (Yet)

- New concepts like definitions or imports
- Any evaluation or processing (parsing only)

## Going Forward

- The Grammar, Conversion, and Astnodes must work together and remain elegant
- Changes should be surgical and predictable, not cascading failures
- Testing should validate behavior, not implementation details

## Major Accomplishments

### 1. Grammar Unification and Elegance

**Unified Identifier Rule**: Eliminated the separate `scope` rule and unified all identifier patterns into a single `identifier` rule with 7 alternatives:
- `localscope identifier_first_field ("." identifier_next_field)*` - `@local.field`
- `argscope identifier_first_field ("." identifier_next_field)*` - `^arg.field`  
- `namescope TOKEN ("." identifier_next_field)*` - `$mod.config`
- `localscope | argscope | namescope TOKEN` - Bare scopes: `@`, `^`, `$mod`
- `identifier_first_field ("." identifier_next_field)*` - Regular identifiers: `foo.bar`

This eliminates grammar ambiguity where `{$mod.pizza=#true}` failed to parse while `{mod.pizza=#true}` worked.

**Scope Grammar Fix**: Changed `namescope` from `"$" TOKEN` (bundled) to `"$" TOKEN` (separate children) allowing proper AST translation.

**Operator Consistency**: Changed `!comp_op` to `?comp_op` to inline comparison operators, giving all binary operators identical tree structure: `[left_child, operator_token, right_child]`.

**Simplified Rules**: Eliminated `_qualified: identifier` aliasing and redundant intermediate rules.

### 2. Parser Architecture Overhaul  

**Top-Down Visitor Pattern**: Replaced Lark's bottom-up `Transformer` with a custom top-down recursive visitor that:
- Processes grammar trees from root to leaves
- Has full context when making decisions
- Can skip subtrees or control traversal order
- Eliminates mixed Lark/AST node confusion

**Eliminated Scope Case**: Removed ~60 lines of special `scope` case handling by making scopes just specialized identifiers.

**Simplified Binary Operators**: `BinaryOp.from_grammar()` reduced from 15 lines with hardcoded operator mappings to a single line: `return cls(tree.children[1].value)`.

**Pipeline Node Creation**: Fixed pipeline AST node creation so all pipeline contexts properly wrap operations:
- Parenthesized pipelines: `(|now/time)` creates Pipeline node
- Expression pipelines: `x |filter |map` creates single Pipeline with all operations
- No double-wrapping or missing Pipeline nodes

### 3. AST Node Improvements

**Consistent Structure**: All AST nodes follow uniform patterns:
- `kids` list for child nodes
- `unparse()` returns valid source code
- `tree()` for debugging visualization
- `from_grammar(cls, tree)` for construction
- `matches(other)` for hierarchical AST comparison

**Hierarchical Comparison**: New `matches()` method enables easy testing of round-trip parsing:
- Compares node types, attributes (excluding position), and all children recursively
- Perfect for unit tests validating parse → unparse → parse correctness
- Ignores position information to focus on structure

**Smart Parenthesization**: Both `BinaryOp` and `UnaryOp` automatically add parentheses when unparsing nested binary operations, ensuring correct precedence.

**Scope Field Handling**: Fixed `Identifier.unparse()` to properly handle scope prefixes:
- Changed `len(tokens) > 2` to `len(tokens) >= 2`
- Now correctly produces `@after` instead of `@.after`
- Handles both simple scopes (`@local`) and named scopes (`$mod.config`)

**Position Tracking**: All AST nodes now track source positions (line, column) for better error reporting.

### 4. Language Features Preserved

All features from phases 01-01 through 01-09 continue to work:

**Number Literals**: `42`, `3.14`, `0xFF`, `0b1010`, `1e10`

**String Literals**: `"hello"`, `'world'`, `` `backticks` ``, `"""multiline"""`

**References**: `#tag`, `#tag/namespace`, `#thumbs-up`

**Identifiers**: `foo`, `foo.bar.baz`, `@local`, `^arg`, `$mod.config`

**Structures**: `{}`, `{a b c}`, `{x=1 y=2}`, `{..spread field=value}`

**Operators**:
- Arithmetic: `+`, `-`, `*`, `/`, `**`, `%`
- Comparison: `==`, `!=`, `<`, `>`, `<=`, `>=`
- Logical: `&&`, `||`, `!!`
- Assignment: `=`, `=*`, `=?`

**Pipelines**: `x |filter |map`, `(|now/time)`, `@local |transform`

**Scope Assignments**: `{@local=42}`, `{$mod.pizza=#true}`, `{^timeout=30}`

**Complex Nesting**: `{data=(@input |validate) result=#success}`

### 5. Test Coverage

**Comprehensive Parse/Unparse Tests**: 45+ test cases covering all language features, all with stable round-trip parsing (parse -> unparse -> parse produces identical AST).

**Validated Operators**: All arithmetic, comparison, logical, and unary operators tested with correct precedence and associativity.

**Scope Validation**: All scope types tested in various contexts: standalone, with fields, in structures, in pipelines.

**Pipeline Validation**: Tested parenthesized, expression-based, and complex nested pipeline patterns.

## Key Design Decisions

### Grammar Elegance Over Micro-Optimization
Chose to unify grammar rules even if it meant slightly more complex parsing, because:
- Unified rules are easier to understand and maintain
- Fewer special cases mean fewer bugs
- Consistent patterns enable future extensions

### Top-Down Translation Over Bottom-Up
Switched from Lark's Transformer to custom visitor because:
- Parent context needed for many decisions (e.g., pipeline wrapping)
- Ability to control traversal order
- Cleaner separation between grammar and AST

### Operator Inlining
Using `?comp_op` instead of `!comp_op` gives all operators identical structure, even though it creates slightly more verbose grammar, because:
- Simpler `BinaryOp.from_grammar()` implementation
- Consistent tree structure across all operators
- Easier to add new operators in future

### Smart Unparsing with Parentheses
AST nodes add parentheses when unparsing nested operations because:
- Guarantees round-trip correctness
- Handles precedence automatically
- Eliminates ambiguity in generated code

## Current Status

**Working**: All language features through Phase 01-09 parse and unparse correctly.

**Elegant**: Grammar is clean, parser is straightforward, AST nodes are consistent.

**Ready**: Foundation is solid for implementing runtime evaluation (Phase 02) and language definitions (Phase 03).

## Critical Bugs Fixed

### Bug 1: Scope Assignment Parse Failure
**Problem**: `{$mod.pizza=#true}` failed to parse while `{mod.pizza=#true}` worked.

**Root Cause**: Grammar ambiguity - `$mod.pizza` was being parsed as FieldAccess instead of Identifier because `namescope` bundled `"$" TOKEN` as a single pattern.

**Fix**: 
1. Changed `namescope: "$" TOKEN` to treat `"$"` and `TOKEN` as separate children
2. Unified `scope` and `identifier` rules into single `identifier` rule with explicit alternatives
3. Made fields required for named scopes in grammar

**Result**: All scope assignments now parse correctly in structures.

### Bug 2: BinaryOp Grammar Copy-Paste Error
**Problem**: `BinaryOp.from_grammar()` had copy-pasted implementation from `String` class that didn't work for operators.

**Root Cause**: Hardcoded operator mapping with 15 lines of if/elif statements that were incomplete.

**Fix**: Simplified to `return cls(tree.children[1].value)` after grammar was fixed to have consistent structure.

**Result**: All binary operators (arithmetic, comparison, logical) now work uniformly.

### Bug 3: Comparison Operator Tree Structure
**Problem**: Comparison operators had different tree structure than arithmetic operators due to `!comp_op` wrapping.

**Root Cause**: `!comp_op` created an intermediate tree node, making comparison operator trees different from arithmetic trees: `[left, comp_op_tree, right]` vs `[left, token, right]`.

**Fix**: Changed `!comp_op` to `?comp_op` to inline the operators.

**Result**: All binary operators now have identical tree structure `[left_child, operator_token, right_child]`.

### Bug 4: Missing Pipeline Nodes
**Problem**: Parenthesized pipelines like `(|now/time)` didn't create Pipeline AST nodes, just bare PipeFunc.

**Root Cause**: `paren_expr` just unwrapped parentheses, and standalone `pipeline` rule didn't create Pipeline node (only `expr_pipeline` did).

**Fix**: Added pipeline detection in `paren_expr` - if middle child is `pipeline`, wrap it in Pipeline node.

**Result**: All pipeline contexts now properly create Pipeline nodes: parenthesized `(|a |b)`, expression-based `x |filter`, and structure-embedded `{data=(@in |process)}`.

### Bug 5: Scope Identifier Unparsing
**Problem**: `{@after (|now/time)}` unparsed as `{@.after (|now/time)}` with an extra dot.

**Root Cause**: `Identifier.unparse()` checked `len(tokens) > 2` before merging scope prefix with field, but `@after` only has 2 tokens.

**Fix**: Changed condition from `> 2` to `>= 2`.

**Result**: Scope identifiers now unparse correctly: `@local`, `^arg`, `$mod.config` (no extra dots).

### Bug 6: Nested Pipeline Double-Wrapping  
**Problem**: Expression pipelines like `x |filter |map` created nested Pipeline nodes instead of single flat node.

**Root Cause**: Both `expr_pipeline` and `pipeline` cases were creating Pipeline nodes, causing double wrapping.

**Fix**: Made `pipeline` case pass through children, only `expr_pipeline` and `paren_expr` (for parenthesized pipelines) create Pipeline nodes.

**Result**: Clean single-level Pipeline nodes with all operations as direct children.

## Technical Details

### Grammar Structure (src/comp/lark/comp.lark)

**Unified Identifier Rule** (lines 76-82):
```lark
identifier: localscope identifier_first_field ("." identifier_next_field)*
          | argscope identifier_first_field ("." identifier_next_field)*
          | namescope TOKEN ("." identifier_next_field)*
          | localscope | argscope | namescope TOKEN
          | identifier_first_field ("." identifier_next_field)*
```

**Scope Definitions** (line 68):
```lark
localscope: "@"
argscope: "^"
namescope: "$" TOKEN  // Note: separate children, not "$" TOKEN bundled
```

**Operator Inlining** (line 196):
```lark
?comp_op: EQUAL_EQUAL | NOT_EQUAL | LESS_THAN | LESS_EQUAL | GREATER_THAN | GREATER_EQUAL
```
The `?` prefix inlines these into parent rules, giving uniform tree structure.

**Pipeline Rules** (lines 167-175):
```lark
pipeline: (pipe_func | pipe_struct | pipe_block | pipe_wrench | pipe_fallback)+
pipe_func: function_reference function_arguments
pipe_struct: PIPE_STRUCT structure_op* RBRACE
pipe_fallback: PIPE_FALLBACK expression
pipe_block: PIPE_BLOCK _qualified
pipe_wrench: PIPE_WRENCH _function_piped
```

### Parser Architecture (src/comp/_parser.py)

**Top-Down Visitor Pattern**:
```python
def lark_to_ast(parent: _ast.AstNode, kids: list) -> _ast.AstNode:
    """Recursively convert Lark tree to AST nodes"""
    for child in kids:
        if isinstance(child, Tree):
            match child.data:
                case 'identifier':
                    _node(_ast.Identifier, walk=child.children)
                case 'binary_op':
                    # Skip operator child, only walk left and right
                    _node(_ast.BinaryOp, walk=[kids[0], kids[2]])
                case 'pipeline':
                    # Pass through children, Pipeline node created by expr_pipeline
                    lark_to_ast(parent, child.children)
                    return parent
                # ... more cases ...
```

**Pipeline Wrapping Logic** (lines 55-61):
```python
case 'paren_expr':
    # LPAREN (expression | pipeline) RPAREN
    middle_child = child.children[1]
    if middle_child.data == 'pipeline':
        _node(_ast.Pipeline, walk=[middle_child])
    else:
        lark_to_ast(parent, [middle_child])
    continue
```

This ensures `(|now/time)` creates a Pipeline node while `(x + y)` doesn't.

### AST Node Examples (src/comp/_ast.py)

**BinaryOp Simplification** (lines 203-207):
```python
@classmethod
def from_grammar(cls, tree):
    """Parse from Lark tree: binary_op with operator token"""
    # tree.children[1] is the operator token
    return cls(tree.children[1].value)
```

**Smart Unparsing** (lines 193-201):
```python
def unparse(self) -> str:
    left = self.kids[0].unparse()
    right = self.kids[1].unparse()
    
    # Add parens around nested binary operations for clarity
    if isinstance(self.kids[0], BinaryOp):
        left = f"({left})"
    if isinstance(self.kids[1], BinaryOp):
        right = f"({right})"
    
    return f'{left} {self.op} {right}'
```

**Identifier Scope Handling** (lines 338-346):
```python
def unparse(self) -> str:
    if not self.kids:
        return "???"
    
    tokens = [kid.unparse() for kid in self.kids]
    # Merge scope prefix with first field (@ + local -> @local)
    if len(tokens) >= 2 and tokens[0] in ("@", "^"):
        tokens[:2] = [tokens[0] + tokens[1]]
    return ".".join(tokens)
```

This produces `@local` instead of `@.local`, and `$mod.config` instead of `$.mod.config`.

**Hierarchical Comparison** (AstNode base class):
```python
def matches(self, other) -> bool:
    """Hierarchical comparison of AST structure.
    
    Compares node types, attributes (excluding position), and recursively
    compares all children. Useful for testing round-trip parsing.
    """
    # Must be same type
    if not isinstance(other, type(self)):
        return False
    
    # Must have same number of children
    if len(self.kids) != len(other.kids):
        return False
    
    # Compare all attributes except kids and position
    for key in self.__dict__:
        if key in ('kids', 'position'):
            continue
        if key not in other.__dict__:
            return False
        if self.__dict__[key] != other.__dict__[key]:
            return False
    
    # Recursively compare all children
    for self_kid, other_kid in zip(self.kids, other.kids, strict=True):
        if not self_kid.matches(other_kid):
            return False
    
    return True
```

This enables clean assertions in tests: `assert original.matches(reparsed)`.

## Testing Examples

### Comprehensive Feature Test
```python
import comp

# All these parse and unparse correctly
test_cases = [
    '@local',                                    # Bare scope
    '$mod.config',                               # Named scope with field
    '{@after (|now/time) - 1}',                  # Structure with pipeline
    '{$mod.pizza=#true}',                        # Scope assignment (was broken!)
    'a + b * c',                                 # Operator precedence
    'x == y && z != w',                          # Mixed comparison and logical
    '!!condition',                               # Unary operator
    'x |filter |map',                            # Pipeline chain
    '(|now/time) - 1',                           # Parenthesized pipeline in expression
    '{data=(@input |validate) result=#success}', # Complex nesting
]

for code in test_cases:
    result = comp.parse(code)
    assert result.unparse() == code or equiv(result.unparse(), code)
```

### Round-Trip Parsing
```python
# Parse -> unparse -> parse produces identical AST using matches()
original = comp.parse('{@after (|now/time) - 1}')
unparsed = original.unparse()
reparsed = comp.parse(unparsed)

# Use matches() for hierarchical comparison (ignores position info)
assert original.matches(reparsed)  # True - identical structure

# Can also use for debugging
if not original.matches(reparsed):
    print("Structure mismatch!")
    original.tree()
    reparsed.tree()
```

### Simple Round-Trip Test Suite
```python
import comp

test_cases = [
    '42',
    '@local',
    '{x=1 y=2}',
    'a + b * c',
    'x |filter |map',
    '(|now/time) - 1',
]

for code in test_cases:
    original = comp.parse(code)
    reparsed = comp.parse(original.unparse())
    assert original.matches(reparsed), f"Failed: {code}"
```

## Remaining Work

### Test Refactoring
- [X] Consolidate test files (currently split across 10+ files)
- [X] Use high-level `parse()` and `unparse()` instead of AST internals
- [X] Use `matches()` method for round-trip validation
- [X] Add more edge case coverage

## Future Phase Integration

**Phase 02 (Values and Expressions)**: Clean AST structure makes evaluation straightforward - visitor pattern can easily walk nodes and compute values.

**Phase 03 (Language Definitions)**: Grammar is ready to add new top-level forms like `!tag`, `!shape`, `!function` without disrupting existing rules.

**Phase CC (Module System)**: Position tracking in AST nodes enables precise error reporting with source locations.

**Future Optimizations**: Flat pipeline representation and consistent operator structure enable query optimization and pipeline fusion.
