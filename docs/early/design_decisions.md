# Comp Language Design Decisions

*Core architectural decisions and rationale behind Comp's design*

## Core Philosophy

**Everything is data transformation through pipelines.** Comp treats all data as immutable structs flowing left-to-right through transformation functions. Structures cannot be modified in place - instead, new structures are created using spread operators and field assignments.

## Data Model

**Decision:** Uniform data model with automatic scalar wrapping
- All data treated as structs, including scalars
- Scalars automatically become single-element structs when passed to functions
- `5` becomes `{5` when function expects struct input
- SQL results, JSON objects, function returns, and literals handled identically

**Decision:** Unnamed field ergonomics for function parameters
- Most operations work naturally with positional arguments
- `{"hello world" " "} -> string.split` uses unnamed fields for parameters
- Eliminates need for complex parameter naming in simple operations

## Type System

**Decision:** Structural typing with inline validation
- Types defined by shape/structure rather than explicit declarations
- Inline validation syntax: `data : {name: string age: int}`
- Functions accept any data with required structure

**Decision:** Hierarchical tags for polymorphism
- Tags drive polymorphic behavior and type compatibility
- Fixed enumeration syntax: `!tag animal = {dog cat bird}`
- Open set syntax: `!tag status = {pending completed ...}`
- Shapes can extend tags: `!shape Dog = {...Animal type=animal.dog}`
- Tags enable pattern matching and dispatch

**Decision:** Collection constraints with range syntax
- `{User[1-]}` specifies 1 or more users
- `{string[3]}` specifies exactly 3 strings
- `{Item[0-10]}` specifies 0 to 10 items
- Enables compile-time validation of collection sizes

## Syntax Design

**Decision:** Left-to-right pipeline operators
- `->` for function calls and data transformation
- `->each` for iteration over collections
- `->if` for conditional execution
- `->failed` for error handling paths

**Decision:** String templating uses `${}` interpolation syntax
- `"Hello ${name}"` for simple variable interpolation
- Template strings can have invoke handlers: `"Hello ${name}"@html.safe`
- Integrates with struct invocation pattern using `@` suffix

**Decision:** Generic struct invocation with `@` suffix
- Any struct can have handlers: `data@json.stringify`
- Enables domain-specific behavior without built-in syntax
- Template strings are special case of struct invocation

## Scoping and State

**Decision:** Context stack for dependency injection
- `$ctx` provides hierarchical context access
- Functions can access injected dependencies without explicit parameters
- Context flows through pipeline calls automatically

**Decision:** Global mutable variables with explicit declaration
- `!global appState : AppState` declares global mutable state
- Explicit syntax makes global mutation visible and intentional
- Most data remains immutable; globals reserved for application state

**Decision:** Lazy evaluation with explicit marking
- `!lazy` prefix creates deferred computation blocks
- Lazy structs capture context at instantiation, not evaluation
- Enables efficient pipeline composition without premature evaluation

## Error Handling

**Decision:** Error propagation via hierarchical failure tags
- Errors flow through pipelines as tagged values
- `->failed` operator catches and handles error conditions
- Hierarchical error tags enable specific error handling patterns

## Documentation System

**Decision:** Integrated documentation with `@` syntax
- `@Target description` attaches documentation to functions and shapes
- `@ inline docs @` for inline documentation within code
- Documentation treated as first-class language feature
- Enables rich tooling and automatic documentation generation

## Assignment and Field Handling

**Decision:** Assignment order and protection rules
- Field assignments processed left-to-right within struct literals
- Later assignments can override earlier ones in same struct
- Spread operators `...other` expand at point of declaration
- Protected fields (if implemented) cannot be overridden after initial assignment
- Complex assignment scenarios follow predictable precedence rules

## Language Goals

**Decision:** Self-hosting implementation target
- Goal to implement as much of the Comp compiler in Comp itself
- Demonstrates language expressiveness and practical utility
- Creates feedback loop for language design improvements
- Standard library and tooling should be primarily Comp code

## Implementation Priorities

**Current Status:** Early design phase focusing on:
1. Core syntax and semantics
2. Type system and structural compatibility
3. Standard library design for collections and data manipulation
4. Error handling and pipeline flow control

**Next Phase:** Implementation planning for:
1. Parser and AST design
2. Type inference engine
3. Standard library implementation
4. Development tooling (syntax highlighting, LSP, etc.)

---

*These decisions form the foundation for Comp's implementation and provide rationale for key language design choices.*