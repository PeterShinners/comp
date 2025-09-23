# Agent Development Guide for Comp Language

This document provides AI assistants with essential context for working on the Comp programming language implementation.

## Project Overview & Philosophy

**Comp** is a data-flow programming language where computation happens through immutable structs flowing through transformation pipelines. This is the Python implementation of the Comp interpreter/compiler.

### **Why Comp Exists:**
- **Unified Data Model**: Everything is a struct - no primitive vs object distinction
- **Pipeline-First**: Left-to-right data flow matches human reading patterns
- **Shape-Based Types**: Structure matters, names don't (like JSON but type-safe)
- **Mathematical Precision**: No integer overflow, decimal precision, exact calculations
- **Developer Experience**: Clear errors, predictable behavior, no surprises

### **Key Design Principles:**
- **Everything is a struct** (unified data model - no arrays vs objects)
- **Immutable data flow** (left-to-right pipelines using `->` operator)
- **Structural typing** (shapes, not names - like TypeScript interfaces)
- **No function arguments** (functions receive single struct via pipeline)
- **No implicit conversions** (explicit operations prevent subtle bugs)
- **Precision-first numbers** (decimal.Decimal, no floating-point gotchas)

### **Language Vision Example:**
```comp
!import /api = http "github-api"
!import /time = std "core/time"

!main = {
    @since = (|now/time) - 1#week
    @fields = {"title" "url" "created-at" "reactions"}
    
    {..@fields repo="nushell/nushell" since=@since}
    -> /api.issues.list
    -> issues.{created-at |sort-desc}
    -> issues.{0..4}  
    -> |display/table
}
```

## Current Implementation Status

### **✅ Phase 02: Number Literals (COMPLETE)**
- **All number formats working**: integers, decimals, scientific notation
- **Alternative bases**: binary (`0b1010`), octal (`0o755`), hex (`0xFF_FF`)  
- **Signed numbers**: `+42`, `-0xFF`, `+.5`, `-0b1010` (all formats support signs)
- **Underscores for readability**: `1_000_000`, `0xFF_FF_FF`
- **Arbitrary precision**: Uses `decimal.Decimal` for exact calculations
- **Comprehensive tests**: 10 passing tests in `tests/test_number_literals.py`

### **🔄 Phase 03: Tag & String Literals (NEXT)**
- **Tag literals**: `#true`, `#user-name`, `#http.get` (boolean system, enums, dispatch)
- **String literals**: `"hello"`, escape sequences, UTF-8 support
- **Tests prepared**: 3 skipped tests in `tests/test_string_literals.py`

### **📋 Future Phases:**
- **Phase 04**: Structures (`{}`, `{x=1}`, `{1 2 3}`)
- **Phase 05**: Expressions (arithmetic, field access)
- **Phase 06**: Pipelines (the core `->` operator)

## Architecture & Code Organization

### **Parser Architecture:**
```
comp.parse("42") → NumberLiteral(Decimal('42'))
                    ↑
              _parser.py (public API)
                    ↑  
              _numbers.py (number parsing)
                    ↑
              lark/comp.lark (grammar)
                    ↑
              lark/numbers.lark (modular grammar)
```

### **Key Implementation Patterns:**
- **Modular grammar**: `numbers.lark` imported by `comp.lark` for extensibility
- **AST nodes**: Simple dataclasses in `_ast.py` (NumberLiteral, future StringLiteral, etc.)
- **Precision-first**: All numbers become `decimal.Decimal` for exact arithmetic
- **Parse-then-refine**: Grammar matches patterns, post-processing handles details
- **Qualified imports**: Tests use `import comp` pattern, not `from comp import`

### **File Organization:**
```
src/comp/
├── __init__.py          # Public API (parse, ParseError, NumberLiteral)
├── _parser.py           # Main parser interface  
├── _numbers.py          # Number literal parsing (Phase 02)
├── _ast.py              # AST node definitions
└── lark/
    ├── comp.lark        # Main grammar (imports modules)
    └── numbers.lark     # Number grammar module
```

## Development Process

### **Agent-Assisted Development Phases:**

#### **1. Phase Planning** (`tasks/XX-name.md`)
Each phase contains:
- **Clear Goals** - What we're building and why
- **Success Criteria** - Measurable checkboxes for completion
- **Design References** - Links to authoritative behavior specs
- **Implementation Strategy** - Architecture approach and considerations

#### **2. Test-First Development** (`tests/test_feature.py`)
Tests serve as executable specifications:
- **Specification summary** in comprehensive docstrings
- **Design doc references** for authoritative behavior
- **Agent context** - what this enables, dependencies, error cases
- **Measurable assertions** that precisely define "done"

#### **3. Implementation** (`src/comp/`)
Code includes context for agents:
- **Phase tracking** - which phase this implements
- **Test references** - which tests this satisfies  
- **Design decisions** - why approach A over B (with reasoning)
- **Future assumptions** - what this expects from later phases

#### **4. Validation & Documentation**
- **Run tests**: Verify implementation works (`pytest tests/`)
- **Update phase status**: Mark completion in task files
- **Document decisions**: Record architectural choices for future phases

### **Benefits for AI Assistance:**
- **Resumable context** - Any agent can pick up from any phase
- **Clear boundaries** - Each phase has well-defined scope
- **Traceable decisions** - Easy to understand why choices were made
- **Incremental progress** - Small, manageable chunks
- **Self-validating** - Tests provide immediate feedback

## Key Files for Agent Context

### **🎯 Start Here for New Chats:**
1. **Current phase**: `tasks/03-tag-literals.md` (next to implement)
2. **Design overview**: `design/overview.md` (language philosophy)
3. **Number implementation**: `src/comp/_numbers.py` (working example)
4. **Test patterns**: `tests/test_number_literals.py` (how to structure tests)

### **📚 Essential Documentation:**
- **`design/overview.md`** - Language philosophy and core concepts
- **`design/type.md`** - Type system (numbers, strings, booleans)  
- **`design/syntax.md`** - Language syntax rules and style
- **`design/tag.md`** - Tag system for booleans, enums, dispatch
- **Current phase in `tasks/`** - Immediate implementation goals

### **🧪 Test Organization:**
- **`tests/test_number_literals.py`** - Complete Phase 02 tests (✅ passing)
- **`tests/test_string_literals.py`** - Phase 03 string tests (⏸️ skipped)
- Tests define behavior precisely - implementation makes these pass
- Each test file includes comprehensive specification docstrings
- Tests use qualified imports (`import comp`) for consistency

### **⚙️ Implementation:**
- **`src/comp/__init__.py`** - Public API surface
- **`src/comp/_parser.py`** - Main parse() function  
- **`src/comp/_numbers.py`** - Working number parsing example
- **`src/comp/_ast.py`** - AST node definitions
- **`src/comp/lark/`** - Grammar modules (modular, extensible)

## Development Workflow

### **🚀 Starting a New Chat Session:**
```bash
# 1. Understand current state
cat tasks/03-tag-literals.md        # Next phase goals
pytest tests/ -v                    # Current test status

# 2. Get oriented  
cat design/overview.md              # Language philosophy
cat src/comp/_numbers.py            # Working implementation example

# 3. Start implementing
# Follow test-first approach, implement incrementally
```

### **🔨 Implementation Workflow:**
1. **Read phase file** for goals and context
2. **Check existing tests** to understand requirements
3. **Read design docs** for authoritative behavior
4. **Implement incrementally** to make tests pass
5. **Run tests frequently** for immediate feedback
6. **Document decisions** in code and phase files

### **🎯 Proven Iterative Development Pattern:**

#### **Step 1: Get Basic Grammar Working**
```bash
# Goal: Parse basic cases, get tests passing
python -m comp._module        # Quick test
pytest tests/test_X.py -v     # Full validation
```

#### **Step 2: Question Every Manual Implementation**
- **Ask**: "Does Python stdlib already do this?"
- **Research**: `ast`, `decimal`, `pathlib`, `json`, `urllib`, etc.
- **Test**: Verify stdlib behavior with edge cases

#### **Step 3: Simplify Grammar Based on Processing**
- **Pattern**: If code handles cases identically, merge grammar rules
- **Check Lark stdlib**: `%import common.DIGIT`, etc.
- **Reduce tree depth**: Fewer levels = easier navigation


### **🧪 Testing Commands:**
```bash
# All tests (should show current progress)
pytest tests/ -v

# Specific feature tests  
pytest tests/test_number_literals.py -v    # Should pass (Phase 02 complete)
pytest tests/test_string_literals.py -v    # Should skip (Phase 03 not started)

# Quick smoke test for numbers
python -m comp._numbers                     # Shows parsing examples
```

### **📁 Code Style & Conventions:**

#### **Python Namespace:**
- **Single import pattern**: `import comp` (not `from comp import`)
- **Flat public API**: `comp.parse()`, `comp.NumberLiteral`, `comp.ParseError`
- **Internal modules**: Use `_` prefix (`_parser.py`, `_numbers.py`)
- **Sibling imports**: `from . import _sibling` (not direct imports)
- **Public interface**: Mark in `__all__` lists

#### **Documentation Style:**
- **Comprehensive docstrings** with specification details
- **Reference design docs** for authoritative behavior
- **Explain WHY** decisions were made, not just WHAT
- **Include agent context** - what this enables, dependencies
- **Document assumptions** about future phases

#### **Architecture Patterns:**
- **Parse-then-refine**: Grammar handles structure, code handles details
- **Modular grammar**: Separate `.lark` files for each language feature
- **AST simplicity**: Plain dataclasses, preserve source info for errors
- **Error handling**: Convert parser errors to clear user messages

## Common Patterns & Gotchas

### **🔄 Iterative Refinement Process (Lessons from Phase 02)**

**Expect 3-5 refinement iterations per phase** - this is normal and valuable:

#### **Iteration 1: Basic Grammar + Tests**
- **Start simple**: Get basic patterns working first
- **Test-driven**: Write comprehensive tests early
- **Don't optimize prematurely**: Focus on correctness over performance

#### **Iteration 2: Leverage Standard Libraries**
- **Question manual implementations**: Can Python's stdlib do this?
- **Example discoveries**:
  - `ast.literal_eval()` handles all integer bases, signs, underscores
  - `decimal.Decimal()` handles underscores automatically
  - Lark's `common.lark` has standard terminals (DIGIT, SIGNED_INT, etc.)


### **✅ Good Patterns:**
- **Test-first**: Write tests before implementation
- **Grammar modularity**: Import specialized `.lark` files
- **Precision numbers**: Use `decimal.Decimal` for all numeric values
- **Qualified imports**: `import comp` in tests and examples
- **Clear errors**: Convert internal errors to helpful user messages

### **🔧 Technical Implementation Insights:**

#### **Number Parsing Lessons (Phase 02)**
```python
# ❌ Original approach: Manual parsing for each base
if node.data == "binary_number":
    # 20+ lines of manual sign/prefix/underscore handling

# ✅ Refined approach: Leverage stdlib
if node.data == "integer":
    python_int = ast.literal_eval(number_text)  # Handles everything!
    return decimal.Decimal(python_int)
```

### **⚠️ Common Pitfalls:**
- **Design doc authority**: `design/` files are source of truth, not intuition
- **Phase dependencies**: Don't skip ahead - phases build on each other
- **Test as specification**: Tests define behavior, implementation follows
- **Future compatibility**: Design for extension, document assumptions

### **🔧 Implementation Notes:**
- **Grammar approach**: Use Lark for structure, Python for details
- **Number parsing**: Signs are part of terminals, post-process for extraction
- **Error context**: Preserve source location for helpful error messages
- **Module testing**: Use `python -m comp._module` for quick verification

## Understanding the Vision

### **Why This Architecture:**
- **Incremental**: Each phase builds working functionality
- **Extensible**: Grammar modules can be added without breaking existing code  
- **Precise**: `decimal.Decimal` eliminates floating-point gotchas
- **Agent-friendly**: Clear context, resumable phases, self-validating tests

### **Long-term Goals:**
- **Complete Comp interpreter** with all language features
- **VS Code extension** for syntax highlighting and IntelliSense
- **Package manager** for Comp modules and libraries
- **Documentation tools** for generating API docs from Comp code

### **Current Focus:**
**Phase 03** is the next major milestone - adding tag literals (`#true`, `#false`, `#http.get`) and string literals (`"hello"`, escape sequences). This completes the fundamental literal types before moving to structures and expressions.

---

**🎯 Quick Start for New Agents:**
1. Read `tasks/03-tag-literals.md` for current goals
2. Check `tests/test_string_literals.py` for test structure  
3. Look at `src/comp/_numbers.py` for implementation patterns
4. Run `pytest tests/ -v` to see current state
5. Start implementing incrementally!

**Remember:** Design docs are authoritative, tests are specifications, implementation makes tests pass. Focus on current phase, document decisions, build incrementally.