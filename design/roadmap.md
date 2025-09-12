# Comp Implementation Roadmap

## Overview

This roadmap outlines the phased implementation of Comp using Python, focusing on iterative development with working software at each phase.

## Phase 0: Foundation (Week 1)

### Goals
- Set up project structure
- Choose and integrate parsing library
- Define AST nodes
- Parse minimal expressions

### Dependencies
```bash
pip install lark pytest attrs mypy
```

### Deliverables
- [ ] Project structure created
- [ ] Lark grammar for basic expressions
- [ ] AST node classes defined
- [ ] Parse and print: numbers, strings, simple structs
- [ ] Basic test framework

### Key Files
- `src/comp/grammar.lark` - Lark grammar definition
- `src/comp/ast_nodes.py` - AST node classes
- `src/comp/parser.py` - Parser wrapper

## Phase 1: Core Language (Week 2-3)

### Goals
- Implement struct operations
- Basic pipeline operator (`->`)
- Variable bindings
- Simple evaluation

### Grammar Additions
```lark
pipeline: expression ("->" expression)*
struct: "{" field_list? "}"
field: (IDENTIFIER "=")? expression
spread: "..." expression
```

### Test Cases
```comp
// Must work by end of Phase 1
{}                           // Empty struct
{x=1 y=2}                   // Named fields
{1 2 3}                     // Unnamed fields
{...base new=1}             // Spread
data -> operation           // Pipeline
!var.x = 10                 // Variable binding
```

### Deliverables
- [ ] Struct literal evaluation
- [ ] Spread operator
- [ ] Pipeline operator
- [ ] Variable storage and lookup
- [ ] Basic built-in operations

## Phase 2: Functions & Control Flow (Week 4-5)

### Goals
- Function definitions
- Pattern matching
- Conditional pipelines
- Iteration operator (`=>`)

### New Features
```comp
!func :name = { body }
@ -> match { patterns }
data ?> condition -> action
{1 2 3} => operation
```

### Deliverables
- [ ] Function definition and calling
- [ ] Pattern matching
- [ ] Conditional execution
- [ ] Collection iteration
- [ ] Error handling basics

## Phase 3: Type System (Week 6-7)

### Goals
- Shape definitions
- Shape checking and morphing
- Tag system
- Type constraints

### New Features
```comp
!shape ~TypeName = { fields }
data ~ Shape                // Apply shape
data ~? Shape               // Check shape
#tag_name                   // Tags
~num(1..100)            // Constraints
```

### Deliverables
- [ ] Shape definition parsing
- [ ] Shape application (morphing)
- [ ] Shape checking
- [ ] Tag system
- [ ] Basic type constraints

## Phase 4: Standard Library (Week 8-9)

### Goals
- Core built-in functions
- String operations
- Number operations
- Collection operations
- I/O basics

### Library Modules
```comp
:str:*     // String operations
:num:*     // Math operations
:list:*       // Collection operations
:io:*         // Input/output
:sys:*        // System operations
```

### Deliverables
- [ ] String manipulation functions
- [ ] Mathematical operations
- [ ] Collection utilities
- [ ] Basic I/O (print, read)
- [ ] Module system basics

## Phase 5: Developer Experience (Week 10)

### Goals
- Interactive REPL
- Error messages
- Debugging support
- Documentation

### Features
- REPL with history
- Helpful error messages with location
- Stack traces
- Interactive help system
- Syntax highlighting (pygments)

### Deliverables
- [ ] Working REPL
- [ ] Error reporting with context
- [ ] Debug mode
- [ ] Help system
- [ ] Basic syntax highlighting

## Phase 6: Optimization (Future)

### Potential Optimizations
- Structural sharing for spreads
- Lazy evaluation for strings
- Pipeline fusion
- Constant folding
- Type inference caching

## Success Metrics

Each phase is complete when:
1. All test cases pass
2. Documentation is updated
3. Examples from specs work
4. No regression in previous phases

## Risk Mitigation

### Technical Risks
- **Parser complexity**: Use Lark, don't build from scratch
- **Performance**: Focus on correctness first, optimize later
- **Type system complexity**: Start with runtime checking only

### Process Risks
- **Scope creep**: Stick to phase goals
- **Over-engineering**: YAGNI principle
- **Testing gaps**: Test-first development

## Tools & Libraries

### Required
- **Lark**: Grammar-based parsing
- **pytest**: Testing framework
- **attrs/dataclasses**: Clean AST nodes

### Optional
- **mypy**: Static type checking for Python code
- **black**: Code formatting
- **pygments**: Syntax highlighting
- **rich**: Better REPL output

## Notes

- Each phase builds on the previous
- Keep interpreter simple (tree-walking is fine)
- Prioritize working software over perfect design
- Update specs based on implementation learnings
- Don't attempt self-hosting until Phase 6+