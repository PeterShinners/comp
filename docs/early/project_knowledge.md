# Comp Programming Language - Project Knowledge Base

## Language Overview

Comp is a data transformation language built around immutable structures flowing through pipelines. It emphasizes clarity, composability, and predictable behavior through a unified data model where everything is a structure.

**Core Philosophy:**
- Everything is immutable data transformation
- Left-to-right pipeline flow
- Structural typing over nominal typing
- Explicit over magical behavior
- Mix named, unnamed, and tagged fields freely

## Current Language Specification

### Core Syntax

#### Boolean Constants
```comp
!true     // Boolean true
!false    // Boolean false
```

#### Structure Creation
```comp
{field=value, 10, name="text"}    // Mixed named/unnamed fields
[expensive = computation]         // Lazy structures (evaluated on access)
```

#### Field Access
```comp
data.field              // Named field access
data."field name"       // Quoted field names
data.'$variable'        // Computed field access
data.'(expression)'     // Expression-based field access
data#0                  // Positional access (zero-indexed)
data#1                  // Second position
```

#### Variables and Namespaces
```comp
$var = value           // Local variable
@in.field             // Input parameters
@func.setting         // Function scope (auto-cleared)
@mod.constant         // Module scope  
@env.config           // Environment scope
```

#### Pipeline Operators
```comp
data -> transform -> output      // Single item pipeline
data => transform => output      // Collection pipeline
data ..> {extra=value} -> next   // Spread arrow (merge fields)
```

#### Functions
```comp
!func name ~{parameters} = expression
!func process ~{value min=0 max=100} = { ... }
```

#### Shapes
```comp
!shape Point2d = {x(number), y(number)}
!shape Person = {name(string), age(number)=18, city?}
```

#### Assignment Operators
- `=` - Normal assignment
- `*=` - Strong assignment (force/persist)
- `?=` - Weak assignment (conditional)
- `^=` - Protected assignment
- `~=` - Override assignment

## Key Design Decisions

### 1. Structure Access Patterns

**Positional Access with #**
- Use `#` prefix for positional access: `data#0`, `data#1`
- Zero-indexed, forward-only (no negative indexing)
- Out of bounds returns failure
- Assignment operators have context-aware behavior:
  - `=` - Standard assignment (may fail if position doesn't exist)
  - `*=` - Force assignment (extends structure if needed)
  - `?=` - Conditional (skips if position invalid)

**Example:**
```comp
data = {a=1, b=2, c=3}
data#0           // 1 (even though it's named 'a')
data#3           // Failure
data#3 | "default"  // "default" (fallback)
```

### 2. Shape Morphing Algorithm

**Three-Phase Field Matching:**
1. **Named matches** - Exact field name matches
2. **Tag matches** - Fields with matching tags  
3. **Positional matches** - Remaining fields by position

**Shape Application Operators:**
- `~` - Normal morph with defaults
- `*~` - Strong morph (strict, no extras)
- `?~` - Weak morph (lenient, allow missing)
- `~@` - Include namespace lookups for defaults
- `*~@` - Strong with namespace
- `?~@` - Weak with namespace (used by default in function calls)

**Example:**
```comp
!shape Config = {host, port=8080, debug=!false}

{"localhost", debug=!true} ~ Config
// Phase 1: debug=!true matches by name
// Phase 2: (no tag matches)
// Phase 3: "localhost" → host by position
// Phase 4: port=8080 from default
// Result: {host="localhost", port=8080, debug=!true}
```

### 3. Function Dispatch Scoring

Functions with the same name but different shapes use lexicographic comparison for dispatch:

**Score tuple: {named_matches, tag_matches, assignment_weight, position_matches}**

```comp
!func render ~{x, y} = "2D"          // Score: {2, 0, 0, 0}
!func render ~{x, y} *= "priority"   // Score: {2, 0, 1, 0}  
!func render ~{x, y, z} = "3D"       // Score: {3, 0, 0, 0}

{x=5, y=10} -> render     // "priority" wins: {2,0,1,0} > {2,0,0,0}
{x=5, y=10, z=15} -> render  // "3D" wins: {3,0,0,0} > others
```

### 4. Namespace Behavior

**Scope Hierarchy:**
- `@in` - Function input parameters
- `@func` - Function-local (auto-cleared on exit)
- `@mod` - Module-level constants
- `@env` - Environment settings

The `@func` namespace provides function-scoped storage without manual cleanup:
```comp
!func process(data) = {
    @func.retries = 3      // Automatically cleared when function exits
    @func.timeout = 30
    data -> :fetch -> :parse
}
```

### 5. Spread Arrow Operator

The `..>` operator merges fields while maintaining pipeline flow:

```comp
// These are equivalent:
data ..> {min=0, max=10} -> :clamp
data -> {..$in, min=0, max=10} -> :clamp

// Works with functions and namespaces:
data ..> :get_defaults -> :process
data ..> @func -> :validate
```

### 6. Data Type Transformations

**Three distinct operations:**

1. **Promotion** - External data → Comp types
   ```comp
   json_data -> :json:promote     // "2024-01-15" → datetime
   cli_args -> :cli:promote       // "yes" → !true
   ```

2. **Morphing** - Structure shape transformation via `~`
   ```comp
   {10, 20} ~ Point2d    // → {x=10, y=20}
   ```

3. **Casting** - Type conversion
   ```comp
   "123" -> :number:cast
   #status.ok -> :string:cast
   ```

### 7. Reference Syntax Benefits

The prefix notation creates self-documenting code:
- `:function` - Function reference
- `~Shape` - Shape reference  
- `#tag` - Tag reference
- `$variable` - Local variable
- `@namespace` - Namespace access

This makes documentation and error messages clearer:
```comp
"Cannot apply ~UserProfile: :validate failed for field #status"
"Use :normalize before applying ~OutputFormat"
```

## Implementation Status

### Completed Conceptual Design
- [x] Core syntax and operators
- [x] Structure access patterns (named, computed, positional)
- [x] Shape morphing algorithm
- [x] Function dispatch rules
- [x] Namespace scoping
- [x] Pipeline operators including spread arrow
- [x] Assignment operator semantics
- [x] Boolean constants as operators
- [x] Tag system design

### To Be Designed
- [ ] Module system and imports
- [ ] Async operations
- [ ] Macro system
- [ ] Constexpr/pure functions for compile-time evaluation
- [ ] COMPON (Comp Object Notation) for configuration files
- [ ] Third-party module integration
- [ ] Standard library function classification (entry-safe, etc.)

### Design Principles to Maintain
1. **No magic** - Explicit behavior over implicit conventions
2. **Composability** - All operations should combine naturally
3. **Predictability** - Same input → same output
4. **Readability** - Code should be scannable and clear
5. **Data-first** - Focus on transformation, not control flow

## Recent Design Insights

### Emergent Patterns

**Primary Value Pattern**
Functions that transform a primary value with modifiers naturally emerge from the morphing rules:
```comp
!func clamp ~{value, min, max} = {
    value < min ? min | {value > max ? max | value}
}

// All these work correctly:
5 -> :clamp~{min=0, max=10}
5 ..> {min=0, max=10} -> :clamp
{min=0, max=10, 5} -> :clamp
```

The shape morphing ensures the primary value always ends up in the correct position regardless of how the structure is built.

**Failure as Data**
Shape application failures return structured information for debugging:
```comp
{
    #failure
    #shape_application_failed
    message = "Type validation failed"
    partial = {x="hello", y=20}     // Partial results
    mapping = {field pairing details}
    errors = {specific error list}
}
```

## Standard Library Patterns

### Entry-Safe Functions
Currently maintaining a hardcoded list of functions safe for use in `!entry`:
- `:args:*`
- `:config:load`
- `:string:*`
- `:number:*`
- Basic data transformations

Future consideration: Allow modules to declare pure/safe functions in metadata.

## Style Guidelines

### Function Design
1. Name the primary parameter (usually `value`, `data`, or domain-specific)
2. Provide defaults for optional parameters in shape definition
3. Use tags for semantic typing where appropriate
4. Keep functions focused on single transformations

### Pipeline Construction
1. Use `->` for single-item pipelines
2. Use `=>` for collection processing
3. Use `..>` to add parameters without wrapping
4. Keep pipelines readable - break long chains into named steps

### Structure Design
1. Prefer flat structures over deep nesting
2. Use meaningful field names
3. Apply tags for semantic meaning
4. Document shapes that define public interfaces

## Open Questions for Future Design

1. **Module System**: How should imports work? Namespace prefixes vs explicit imports?

2. **Async/Promises**: Should async be part of the type system or handled through conventions?

3. **Pure Functions**: Should we explicitly mark constexpr/pure functions or infer them?

4. **Custom Operators**: Should users be able to define new pipeline operators?

5. **Performance Hints**: Should there be ways to hint at optimization opportunities?

6. **Error Recovery**: How sophisticated should error recovery patterns be?

## Example Code Patterns

### Data Validation Pipeline
```comp
!shape UserInput = {
    email(string),
    age(number),
    preferences?
}

!func process_user(data) = {
    data 
    -> :json:parse
    -> :json:promote           // Convert types
    ~ UserInput                // Apply shape
    | {:error:log(@), @.partial}  // Handle failure but use partial
    -> :validate:email
    -> :store:user
}
```

### Configuration with Computation
```comp
!shape Config = {
    port(number) = 8080,
    host(string) = "localhost",
    workers(number) = {:cpu:count} * 2
}

@mod.config = {:env:load} ~@ Config  // Merge environment with defaults
```

### Collection Processing
```comp
users
=> :validate~{strict=!true}
=> {@in.age > 18 ? @ | !skip}  // Conditional filtering  
=> :transform
=> :store
```

---

*This knowledge base represents the current state of Comp language design as of September 2025. The language is in active conceptual development.*