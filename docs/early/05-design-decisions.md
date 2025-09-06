# Pettle Language Design Decisions

*Compiled from conversations: [Designing a New Programming Language](https://claude.ai/chat/2f994fe9-a223-459d-97f7-afef880c0766), [Programming Language Concept Refinement](https://claude.ai/chat/b61724ef-6eaf-4c67-add7-48c28add3e8c), [Pettle Language Design Exploration](https://claude.ai/chat/22f4fd33-61ba-4b71-b334-796d2a05856f)*

## Language Design Philosophy

**Decision:** Encourage compositional function design over monolithic functions
- Language features designed to break clumsy functions into composable pieces
- Pipeline-first approach makes function composition natural
- Context system enables clean separation of concerns
- **Context:** [Programming Language Concept Refinement](https://claude.ai/chat/b61724ef-6eaf-4c67-add7-48c28add3e8c), [Pettle Language Design Exploration](https://claude.ai/chat/22f4fd33-61ba-4b71-b334-796d2a05856f)

**Decision:** Context system enables function decomposition
- `$ctx` allows sharing state/configuration across function boundaries
- Functions can be split without losing access to shared context
- Environment stack with persistence control supports fine-grained function separation
- Mid-pipeline variable assignment (`$variable = value`) enables stateful transformations
- **Context:** [Programming Language Concept Refinement](https://claude.ai/chat/b61724ef-6eaf-4c67-add7-48c28add3e8c)

**Decision:** Minimal builtin control flow with rich library patterns
- Core operators (`->`, `=>`, `?|`, `!>`) kept intentionally simple and low-level
- Advanced control flow implemented as library functions (`retry`, `chunk`, `match`, `reduce`)
- Enables domain-specific control patterns without language complexity
- Standard library demonstrates idiomatic compositional patterns
- **Context:** [Programming Language Concept Refinement](https://claude.ai/chat/b61724ef-6eaf-4c67-add7-48c28add3e8c), [Pettle Language Design Exploration](https://claude.ai/chat/22f4fd33-61ba-4b71-b334-796d2a05856f)

**Decision:** Idiomatic patterns favor small, focused functions
- Pipeline operators encourage breaking complex logic into transformation steps
- Lazy evaluation supports expensive computations split across function boundaries
- Error handling system works better with smaller, focused functions
- Library functions provide sophisticated patterns while keeping language core simple
- **Context:** [Programming Language Concept Refinement](https://claude.ai/chat/b61724ef-6eaf-4c67-add7-48c28add3e8c), [Pettle Language Design Exploration](https://claude.ai/chat/22f4fd33-61ba-4b71-b334-796d2a05856f)

## Core Philosophy

**Everything is data transformation through pipelines.** Pettle treats all data as immutable structs flowing left-to-right through transformation functions.

## Language Name & Identity

**Decision:** Language is named "Pettle"
- **Context:** [Programming Language Concept Refinement](https://claude.ai/chat/b61724ef-6eaf-4c67-add7-48c28add3e8c)

## Scope and Variable Systems

**Decision:** Complete namespace system with explicit variable lookup
- `$ctx` - Local context (variables, explicit imports) 
- `$app` - Application-level state (project dependencies, global config, stdlib)
- `$in` - Input data from pipeline
- `$out` - Output data to pipeline  
- Local namespace `# Pettle Language Design Decisions

*Compiled from conversations: [Designing a New Programming Language](https://claude.ai/chat/2f994fe9-a223-459d-97f7-afef880c0766), [Programming Language Concept Refinement](https://claude.ai/chat/b61724ef-6eaf-4c67-add7-48c28add3e8c), [Pettle Language Design Exploration](https://claude.ai/chat/22f4fd33-61ba-4b71-b334-796d2a05856f)*

## Core Philosophy

**Everything is data transformation through pipelines.** Pettle treats all data as immutable structs flowing left-to-right through transformation functions.

## Language Name & Identity

**Decision:** Language is named "Pettle"
- **Context:** [Programming Language Concept Refinement](https://claude.ai/chat/b61724ef-6eaf-4c67-add7-48c28add3e8c)

 - not part of default variable lookup
- **Context:** [Pettle Language Design Exploration](https://claude.ai/chat/22f4fd33-61ba-4b71-b334-796d2a05856f), [Programming Language Concept Refinement](https://claude.ai/chat/b61724ef-6eaf-4c67-add7-48c28add3e8c)

**Decision:** Explicit namespacing for non-struct field references
- `$self.field` - current input struct  
- `$var.local` - local variables (explicit only)
- `$env.global` - environment stack
- Bare field names search environment then self: `field` → `$env` → `$self`
- **Context:** [Programming Language Concept Refinement](https://claude.ai/chat/b61724ef-6eaf-4c67-add7-48c28add3e8c)

**Decision:** Environment stack with assignment-controlled persistence
- `$env.value = temp` - auto-pops when function exits
- `$env.value *= persist` - persists beyond function scope  
- `$env.value ?= fallback` - conditional temporary assignment
- Functions can only modify top of stack, not intermediates
- **Context:** [Programming Language Concept Refinement](https://claude.ai/chat/b61724ef-6eaf-4c67-add7-48c28add3e8c)

**Decision:** Local variables excluded from auto-resolution
- `$var` namespace requires explicit usage only
- Does not participate in bare field name lookup
- Eliminates confusion between pipeline data and local computation
- **Context:** [Programming Language Concept Refinement](https://claude.ai/chat/b61724ef-6eaf-4c67-add7-48c28add3e8c)

## Function and Shape Definitions

**Decision:** Use `!func` and `!shape` keywords instead of assignments
- `!func name : shape = {...}` 
- `!shape name = {...}`
- Indicates compile-time definitions vs runtime assignments
- **Context:** [Pettle Language Design Exploration](https://claude.ai/chat/22f4fd33-61ba-4b71-b334-796d2a05856f)

**Decision:** Automatic positional-to-named argument promotion
- `{3 7} -> diff` promotes to `{min:3 max:7}` when calling `diff : {min:int max:int}`
- Eliminates need for `$in` in most function definitions
- **Context:** [Pettle Language Design Exploration](https://claude.ai/chat/22f4fd33-61ba-4b71-b334-796d2a05856f)

## Casting System

**Decision:** Four casting operators with clear semantics
- `:` - loose with context (most common)
- `*:` - strict with context  
- `:~` - loose without context
- `*:~` - strict without context
- **Context:** [Pettle Language Design Exploration](https://claude.ai/chat/22f4fd33-61ba-4b71-b334-796d2a05856f)

**Decision:** Function calls always use loose+context casting by default
- Can override with explicit pre-casting when needed
- **Context:** [Pettle Language Design Exploration](https://claude.ai/chat/22f4fd33-61ba-4b71-b334-796d2a05856f)

## Lazy Evaluation and Iterators

**Decision:** Two invocation operators with different evaluation strategies
- `->` (regular invoke) - forces complete evaluation 
- `=>` (iteration invoke) - maintains streaming/lazy evaluation
- **Context:** [Pettle Language Design Exploration](https://claude.ai/chat/22f4fd33-61ba-4b71-b334-796d2a05856f)

**Decision:** Lazy structs using square brackets `[...]`
- Create generator/iterator-like structures
- Fields evaluate on-demand
- **Context:** [Programming Language Concept Refinement](https://claude.ai/chat/b61724ef-6eaf-4c67-add7-48c28add3e8c), [Pettle Language Design Exploration](https://claude.ai/chat/22f4fd33-61ba-4b71-b334-796d2a05856f)

**Decision:** Support both lazy structs and iteration operators
- `[]` for conditional/lazy field evaluation
- `=>` for dynamic collection processing with flow control
- **Context:** [Programming Language Concept Refinement](https://claude.ai/chat/b61724ef-6eaf-4c67-add7-48c28add3e8c)

## Module System

**Decision:** No implicit builtins - everything in `$app`
- Standard library auto-imported to `$app` (unless `--nostdlib`)
- Project dependencies populate `$app`
- Command line args map to `$app` scope (`flo run --app.port=8000`)
- **Context:** [Pettle Language Design Exploration](https://claude.ai/chat/22f4fd33-61ba-4b71-b334-796d2a05856f)

**Decision:** Flat namespaces per library with functions/shapes separation
- Each library exposes `functions` and `shapes` namespaces only
- No direct import of individual functions
- **Context:** [Pettle Language Design Exploration](https://claude.ai/chat/22f4fd33-61ba-4b71-b334-796d2a05856f)

**Decision:** Unqualified access to imported namespaces
- `json.parse` instead of `$ctx.json.parse` 
- Use full qualification only for naming conflicts
- **Context:** [Pettle Language Design Exploration](https://claude.ai/chat/22f4fd33-61ba-4b71-b334-796d2a05856f)

## Data Types

**Decision:** Minimal primitive types only
- `int`, `float`, `bool`, `string`, `bytes`
- Only types that cannot be efficiently implemented as structs
- **Context:** [Programming Language Concept Refinement](https://claude.ai/chat/b61724ef-6eaf-4c67-add7-48c28add3e8c)

**Decision:** Numbers retain traditional operators, others use function chaining
- `+`, `-`, `*`, `/` for numbers due to essential nature
- All other types use `{data params} -> namespace.function`
- **Context:** [Programming Language Concept Refinement](https://claude.ai/chat/b61724ef-6eaf-4c67-add7-48c28add3e8c)

## Flow Control

**Decision:** Use `loop.skip` and `loop.break` for iteration control
- Eliminates need for special `yield` statements
- Works naturally with conditional expressions
- **Context:** [Pettle Language Design Exploration](https://claude.ai/chat/22f4fd33-61ba-4b71-b334-796d2a05856f)

## Pattern Matching

**Decision:** Struct-based pattern matching with computed expressions
- Patterns can reference variables from current scope
- Single quotes for non-string expression field names
- **Context:** [Pettle Language Design Exploration](https://claude.ai/chat/22f4fd33-61ba-4b71-b334-796d2a05856f)

## Function Blocks and Callbacks

**Decision:** Functions can accept named blocks as executable arguments
- Syntax: `{data} -> function_name block_name {block_body}`  
- Blocks act as deferred/lazy execution - not evaluated until function requests it
- Function controls when and how often the block executes
- **Context:** [Designing a New Programming Language](https://claude.ai/chat/2f994fe9-a223-459d-97f7-afef880c0766)

**Decision:** Block parameters defined with `block` type and associated shape
- `!shape button = {text: string onClick: block onClickShape}`
- `onClickShape` defines the expected input/output shape for the block
- Provides type safety while keeping execution deferred
- **Context:** [Designing a New Programming Language](https://claude.ai/chat/2f994fe9-a223-459d-97f7-afef880c0766)

**Decision:** Named blocks enable clean callback syntax
- `{text="save"} -> ui.button onClick {data -> saveToDatabase}`
- Multiple named blocks: `data -> validate onSuccess {->process} onError {->handle}`  
- More readable than embedding callbacks in structs
- **Context:** [Designing a New Programming Language](https://claude.ai/chat/2f994fe9-a223-459d-97f7-afef880c0766)

**Decision:** Reserved for future development
- Feature provides foundation for callback-heavy patterns (UI, async operations)
- Not immediate priority but syntax space reserved
- **Context:** [Designing a New Programming Language](https://claude.ai/chat/2f994fe9-a223-459d-97f7-afef880c0766)

## Struct Operations and Assignment

**Decision:** Deep field assignment with dot notation
- `{names.first="joe" names.last="man"}` equivalent to `{names={first="joe" last="man"}}`
- Can mix nested and flat assignment approaches
- Enables incremental struct building
- **Context:** [Programming Language Concept Refinement](https://claude.ai/chat/b61724ef-6eaf-4c67-add7-48c28add3e8c)

**Decision:** Spread operators family with `..` syntax and conflict resolution
- `..` - basic spread (last wins for conflicts)
- `..?` - conditional spread (only add missing fields, never overwrites)
- `..*` - protected spread (cannot be overridden by subsequent assignments)
- Spreads apply left-to-right, with explicit conflict resolution rules
- **Context:** [Programming Language Concept Refinement](https://claude.ai/chat/b61724ef-6eaf-4c67-add7-48c28add3e8c)

**Decision:** Destructuring assignment with explicit handling
- `{field1, field2} = struct` - extract specific fields
- `{first, second, ..rest} = data` - capture remaining fields in rest
- `{..rest} = data` - capture all fields in rest (spread destructuring)
- `{first, ..middle, last} = data` - capture first, last, and everything in between
- `..rest` spread in assignment requires explicit declaration, no silent truncation
- Assignment validates expected vs actual field counts
- **Context:** [Programming Language Concept Refinement](https://claude.ai/chat/b61724ef-6eaf-4c67-add7-48c28add3e8c)

**Decision:** Assignment operator variants for conflict resolution
- `=` - normal assignment (last wins)
- `?=` - conditional assignment (only if not already defined)
- `*=` - forced assignment (overrides protection)
- `!delete` - field deletion marker
- **Context:** [Programming Language Concept Refinement](https://claude.ai/chat/b61724ef-6eaf-4c67-add7-48c28add3e8c)

**Decision:** Flexible field name syntax
- Simple names: `user.name`
- Quoted names: `headers."Content-Type"` 
- Computed expressions: `` `n > 5`.result``
- Same syntax for both field access and field definition
- **Context:** [Designing a New Programming Language](https://claude.ai/chat/2f994fe9-a223-459d-97f7-afef880c0766)

## Pattern Matching and Control Flow

**Decision:** Struct-based pattern matching with `match` function
- Conditional expressions as field keys: `{`n < 0` = failure_result else = success_result}`
- `match` function evaluates first true condition
- Integration with lazy evaluation for unused branches
- **Context:** [Designing a New Programming Language](https://claude.ai/chat/2f994fe9-a223-459d-97f7-afef880c0766)

**Decision:** Early return and control flow in blocks
- `!return` - exit function entirely with value
- `!exit` - stop populating current block but continue function
- Spread syntax `...{value !return}` for early return with spreading
- **Context:** [Designing a New Programming Language](https://claude.ai/chat/2f994fe9-a223-459d-97f7-afef880c0766)

## Field Access and Fallback

**Decision:** Field access with fallback using ternary pattern
- `field ?| fallback` as shorthand for field existence check
- `field ? field | fallback` explicit form
- Addresses undefined field access without additional operators
- **Context:** [Programming Language Concept Refinement](https://claude.ai/chat/b61724ef-6eaf-4c67-add7-48c28add3e8c)

**Decision:** Shape validation through function calls
- `{data shape} -> lang.is` for boolean shape matching
- `{data shapes} -> lang.findMatches` for multiple shape checking  
- Avoids additional operators while providing shape introspection
- **Context:** [Programming Language Concept Refinement](https://claude.ai/chat/b61724ef-6eaf-4c67-add7-48c28add3e8c)

## Tags and Polymorphism

**Decision:** Tag-based polymorphism system with open/closed tag definitions
- `!tag animal = {...}` - open for extension (allows new values)
- `!tag status = {pending active complete}` - closed set (predefined values only)
- Tags serialize as simple strings
- **Context:** [Designing a New Programming Language](https://claude.ai/chat/2f994fe9-a223-459d-97f7-afef880c0766), [Programming Language Concept Refinement](https://claude.ai/chat/b61724ef-6eaf-4c67-add7-48c28add3e8c)

**Decision:** Structural typing with tag-based dispatch
- `!shape Animal = {type: animal name: string}`
- `!shape Dog = {...Animal type=animal.dog breed: string}`
- Function dispatch based on most specific shape match
- No explicit inheritance required - compatibility through structure
- **Context:** [Designing a New Programming Language](https://claude.ai/chat/2f994fe9-a223-459d-97f7-afef880c0766)

**Decision:** Hierarchical tags for error handling and categorization  
- `failure.math.dividebyzero` creates hierarchical error types
- Enables specific error handling while allowing fallback to general handlers
- **Context:** [Programming Language Concept Refinement](https://claude.ai/chat/b61724ef-6eaf-4c67-add7-48c28add3e8c)

**Decision:** Function overloading resolved by shape compatibility
- Multiple functions with same name but different shapes allowed
- Duplicate signatures (identical shapes) error at definition time
- Tag values make shapes distinct for dispatch purposes
- **Context:** [Designing a New Programming Language](https://claude.ai/chat/2f994fe9-a223-459d-97f7-afef880c0766)

## Struct Invocation and String Templating

**Decision:** Structs can have invoke handlers attached using suffix `@` syntax
- `"Hello ${name}"@html.safe` attaches `html.safe` function as invoke handler
- When struct is invoked, the attached handler processes the data
- **Context:** [Pettle Language Design Exploration](https://claude.ai/chat/22f4fd33-61ba-4b71-b334-796d2a05856f)

**Decision:** String templating uses `${}` interpolation syntax
- `"Hello ${name}!"` for variable interpolation (similar to Python f-strings)
- `"User ${user.name} has ${user.score} points"` for field access
- Works with struct invocation pattern for formatting
- **Context:** [Pettle Language Design Exploration](https://claude.ai/chat/22f4fd33-61ba-4b71-b334-796d2a05856f)

**Decision:** String templating uses struct invocation pattern
- Templates are strings with invoke handlers: `"Hello ${name}"@formatter`
- Usage: `{name="Alice"} -> template -> print`
- **Context:** [Pettle Language Design Exploration](https://claude.ai/chat/22f4fd33-61ba-4b71-b334-796d2a05856f)

**Decision:** Default string formatting via application context
- `$app.default_string_invoke = string.ruby_style` (updated from `$env`)
- Allows modules to customize string behavior domain-specifically
- Can still override with explicit handlers
- **Context:** [Pettle Language Design Exploration](https://claude.ai/chat/22f4fd33-61ba-4b71-b334-796d2a05856f)

**Decision:** Generic struct invocation concept
- Any data type can have invoke handlers attached
- String templating is just one application of this pattern
- **Context:** [Pettle Language Design Exploration](https://claude.ai/chat/22f4fd33-61ba-4b71-b334-796d2a05856f)

## Error Handling

**Decision:** Hierarchical failure tags with shape-based matching
- `result : retryable_tags` checks hierarchical tag membership
- Failures flow as data through pipelines
- **Context:** [Pettle Language Design Exploration](https://claude.ai/chat/22f4fd33-61ba-4b71-b334-796d2a05856f)

**Decision:** Automatic short-circuiting for failure-tagged structs
- Any struct containing a failure tag automatically short-circuits through pipeline operations
- Functions skip execution when receiving failure inputs, passing the failure through unchanged
- **Context:** [Designing a New Programming Language](https://claude.ai/chat/2f994fe9-a223-459d-97f7-afef880c0766), [Pettle Language Design Exploration](https://claude.ai/chat/22f4fd33-61ba-4b71-b334-796d2a05856f)

**Decision:** `!>` failure handling operator for error recovery  
- Only invoked when `$in` struct matches failure shape
- Can provide fallback values, resolve workarounds, or propagate new failures
- Receives current error in `$in` for conditional handling based on failure type
- **Context:** [Pettle Language Design Exploration](https://claude.ai/chat/22f4fd33-61ba-4b71-b334-796d2a05856f)

**Decision:** Automatic error chaining with `cause` field
- When `!>` block creates new failure struct, language automatically adds `cause` field with original error
- Preserves error stack for debugging while allowing contextual error messages
- **Context:** [Pettle Language Design Exploration](https://claude.ai/chat/22f4fd33-61ba-4b71-b334-796d2a05856f)

**Decision:** Failure structs use hierarchical tag system for dispatch
- `!tag failure = {...}` with hierarchy like `failure.math.dividebyzero`
- Function dispatch follows tag specificity - most specific handler called first
- Enables both general catch-all handlers and precise error-specific recovery
- **Context:** [Designing a New Programming Language](https://claude.ai/chat/2f994fe9-a223-459d-97f7-afef880c0766)

## Standard Library Design

**Decision:** Namespace organization without `std` prefix
- `$app.math.sqrt`, `$app.string.split` instead of `$app.std.math.sqrt`
- Keep frequently-used operations concise
- **Context:** [Pettle Language Design Exploration](https://claude.ai/chat/22f4fd33-61ba-4b71-b334-796d2a05856f)

## Documentation System

**Decision:** Inline documentation support for functions and shapes
- Functions and shapes support optional docstrings for short descriptions
- `@Target description` syntax for attaching documentation
- `@ inline docs @` patterns for embedded documentation
- Longer-form documentation separate from implementation
- Individual shape fields can have attached documentation
- **Context:** [Programming Language Concept Refinement](https://claude.ai/chat/b61724ef-6eaf-4c67-add7-48c28add3e8c)

**Decision:** Documentation concepts subject to future refinement
- Exact syntax and patterns will likely evolve
- Core concept of integrated documentation preserved
- Tooling integration planned for documentation generation
- **Context:** [Programming Language Concept Refinement](https://claude.ai/chat/b61724ef-6eaf-4c67-add7-48c28add3e8c)

## Outstanding Questions

- Exact syntax for some edge cases in casting system
- Standard library organization details  
- Build system integration specifics
- IDE/tooling integration approaches
- **Tag implementation in structs**: Are tags struct members (accessible as fields) or attached metadata? How are multiple tags handled? What field names are used? How does this affect serialization, field access, function dispatch, and potential conflicts with user-defined fields?
- **Multiple named blocks per function**: Should functions support multiple named blocks (e.g., `condition -> if then {success_logic} else {failure_logic}`)? How would optional blocks work? Would this enable patterns like `else if` or should it remain simple with just primary/secondary blocks?
- **Mid-pipeline variable assignment**: Design syntax for assigning variables during call chains (e.g., `data -> transform -> $temp = result -> process($temp) -> final`). Should this use special operators? How does scoping work? Does it break pipeline purity or enable useful patterns?

---
*This document captures major design decisions. Individual syntax examples and detailed explanations can be found in the linked conversations.*