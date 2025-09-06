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
- `=>` for iteration over collections (replaces older `->each`)
- Custom operators `-if>` for conditional execution
- Custom operators `-failed>` for error handling paths
- Pattern creates consistent `-word>` syntax for specialized pipeline operations

**Decision:** String templating uses `${}` interpolation syntax
- `"Hello ${name}"` for simple variable interpolation
- Template strings can have invoke handlers: `"Hello ${name}"@html.safe`
- Integrates with struct invocation pattern using `@` suffix
- Triple quotes for multiline strings and embedded quotes: `"""He said "Hello!" to me."""`
- Triple quote strings support same interpolation: `"""Welcome ${user.name}!"""`

**Decision:** Generic struct invocation with `@` suffix
- Any struct can have handlers: `data@json.stringify`
- Enables domain-specific behavior without built-in syntax
- Template strings are special case of struct invocation

**Decision:** Dotted syntax for function block arguments
- Block arguments use dotted syntax: `function.{block_code}`
- Named blocks: `function.onError{error_handler}.onSuccess{success_handler}`
- Multiple blocks chain naturally: `.branch{...}.leafs{...}`
- Unambiguous parsing since field lookup on struct literals is invalid
- Resolves ambiguity between function calls with blocks vs. new struct chains

**Decision:** Assignment controls pipeline flow
- Assignment syntax: `$variable=expression` assigns and passes assigned value forward
- Pipeline capture: `$variable=$in` captures current pipeline value
- Nested blocks preserve main flow: `data -> nest.{$var=side.calculation} -> continue`
- Assignment always passes the assigned value to next pipeline stage
- Explicit flow preservation when assigning side values without disrupting main pipeline

**Decision:** Unified number type prioritizing mathematical correctness
- Single `number` type handles integers, floats, arbitrary precision, and decimal operations
- No integer division truncation: `10 / 3` always returns `3.333...`
- No integer overflow: `1000000000000000000 + 1` is always exact
- Prioritizes developer ergonomics and mathematical correctness over performance
- Eliminates type juggling in mathematical operations and data processing
- Future specialized types (int32, float64, etc.) reserved for FFI and binary interop
- Philosophy: "math just works correctly" similar to Python 3's division behavior
- Implementation starts simple/correct, optimizes based on real-world usage patterns

**Decision:** Context-controlled number behavior
- Use `$ctx.number.*` to configure numeric operation behavior across pipeline
- `$ctx.number.int = math.round|math.truncate|math.fail` controls fractional-to-integer conversion for bitwise operations
- `$ctx.number.precision = 28` sets arbitrary precision decimal places  
- `$ctx.number.rounding = math.half_up` controls rounding behavior
- `$ctx.number.epsilon = 1e-9` sets tolerance for equality comparisons to handle floating point precision
- Context flows through pipelines naturally, allowing different modules different numeric behaviors
- Similar to Python's decimal context but broader scope covering all number operations
- Standard library provides domain-specific context presets (financial, scientific, graphics)
- Eliminates "almost equal" comparison bugs: `(0.1 + 0.2) == 0.3` works correctly

**Decision:** Thread-safe context isolation
- Contexts like `$ctx` and `$app` are cloned when threads are created
- Each thread gets independent copy of parent's context at spawn time
- Context changes within thread only affect that thread - no cross-thread pollution
- Eliminates race conditions and synchronization complexity for context access
- Shared resources (mutexes, connections) must be initialized before thread creation
- Threads cannot accidentally modify parent or sibling thread contexts
- Persistent context changes require explicit communication back to main thread
- Encourages good architecture: configuration setup happens at initialization time

**Decision:** Module reference syntax and namespace disambiguation
- Use `:` for local module references: `data -> :max` calls local function
- Use `module:function` for imported function calls: `data -> io:print`  
- Unqualified names are value invokes: `data -> max` invokes on value named "max"
- Use parentheses for type syntax: `name(string)`, `data(User)`, `value(number)`
- Avoids reserving common words like `self`, `mod`, `this` as they would conflict with struct field names
- Comments use only `//` syntax - no block comments to avoid nesting complexity and formatting issues

**Decision:** Platform-specific definition overrides
- Functions and shapes can have platform/architecture-specific variants using dotted suffixes
- `!func file_open.win32(path) = {...}` for Windows-specific implementation
- `!shape buffer.arm64 = {...}` for architecture-specific data layout
- Compiler selects most specific match first, falls back to generic: `func.platform.arch` → `func.platform` → `func`
- Allows fine-grained conditional compilation without separate files for small platform differences
- Keeps related platform variants together for easier maintenance and comparison

**Decision:** Tag definition and polymorphism system  
- Tags defined with `#` syntax: `!tag priority = {low, medium, high}`
- Tag values referenced as: `#priority#high` (local) or `module#tag#value` (imported)
- Hierarchical tags support nesting: `!tag emotions = {anger = {fury, righteous}, joy = {happiness, excitement}}`
- Tags can only be extended within their defining module - no external modification
- Other modules import tag values: `!tag my_emotions = {..external#emotions, crazy, wild}`
- Tag aliasing supported: `!tag my_emotions = {joy = external#emotions#happy}`
- Imported tag values are interchangeable: `#my_emotions#happy == external#emotions#happy`
- Polymorphic dispatch based on tag-typed struct fields: `!func speak(breed=#animal#dog) = {...}`
- All tag definitions are static at module level - enables static analysis and tooling
- `!super(field)` calls parent implementation in tag hierarchy: `result -> !super(emote)`
- `!super(field=tag)` calls specific parent: `result -> !super(emote=#emotion#anger)`
- Cross-branch calling requires explicit casting: `{...$in breed=#animal#cat}(:cat) -> feed`

**Decision:** Spread assignment operator for struct updates
- `struct ..= changes` shorthand for `struct = {...struct ...changes}`
- Weak assignment `struct ..?= changes` only adds new fields, won't overwrite existing
- Strong assignment `struct ..*= changes` replaces struct entirely with merged result
- Default `..=` behavior is additive merge (add/update fields from right side)
- Complex merge behavior can use expanded syntax when needed

**Decision:** Field access quoting rules
- String identifiers need no quotes: `data.name.first`
- Tags need no quotes (visually distinct): `data.#priority#high.description`
- All other types require quotes: `matrix.'0'.'1'.value`, `settings.'true'.enabled`
- Rule: "Only string identifiers and tags can be unquoted field names"

**Decision:** Function calls can start pipelines directly
- `:function` calls can begin pipeline chains without placeholder: `:gfx:init -> :gfx:shutdown`
- Value invokes still need explicit placeholder: `{} -> string_template`
- Eliminates need for awkward `() -> :function` or `{} -> :function` patterns
- Clear disambiguation between function calls and value invokes

**Decision:** Block-based function parameters using structure syntax
- Functions accept blocks as structure fields: `cases={block1(input) block2(input)}`
- Block names become field names in structure parameter
- Dotted block syntax for calling: `value -> :match .#status#pending {...} .else {...}`
- Default values for optional blocks: `cases={else = {-> default_handler}, required(input)}`
- Variadic blocks: `cases={..(input)}` accepts any number of blocks with same signature
- Empty parameter syntax: `()` shorthand for `({})`
- Enables flexible match/dispatch functions while maintaining structural consistency

## Scoping and State

**Decision:** Context stack for dependency injection
- `$ctx` provides hierarchical context access
- Functions can access injected dependencies without explicit parameters
- Context flows through pipeline calls automatically

**Decision:** Global mutable variables with explicit declaration
- `$app.state = value` declares application-level mutable state
- Works identically to `$ctx` but visible at application scope rather than function scope
- Explicit syntax makes global mutation visible and intentional
- Most data remains immutable; globals reserved for application state

**Decision:** Lazy evaluation with explicit marking
- Square brackets `[...]` create deferred computation blocks instead of immediate execution
- Lazy functions use `[expression]` syntax instead of `{expression}` 
- Lazy structs capture context at instantiation, not evaluation
- Enables efficient pipeline composition without premature evaluation

## Error Handling

**Decision:** Error propagation via hierarchical failure tags
- Errors flow through pipelines as tagged values
- `-failed>` operator catches and handles error conditions
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



*These decisions form the foundation for Comp's implementation and provide rationale for key language design choices.*