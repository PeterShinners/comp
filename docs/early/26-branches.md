# Pipeline Branches in Comp

## Overview

Pipeline branches are special grouping constructs that modify how pipelines execute. They use parentheses with a prefix symbol to create distinct execution contexts. Each branch type addresses specific patterns that previously required operators or workarounds.

## Syntax

All branches follow the pattern: `-> X()` where X is the branch type symbol.

## Branch Types

### Group Branch: `.()`
Groups multiple pipeline operations and returns the final result directly (not wrapped in a struct).

```comp
// Returns the result of :process, not {<result>}
data -> .(:validate -> :process)

// Useful in iteration to avoid struct wrapping
users -> @(.(:validate -> :save))  // Each user becomes save result
users -> @({:validate -> :save})    // Each user becomes {<save result>}
```

**Replaces:** The need for `{..}` spreading to unwrap single pipeline results in structs.

### Iterate Branch: `@()`
Applies a pipeline to each unnamed field in a structure.

```comp
// Process each element
users -> @(:validate -> :save)

// Multi-step iteration
numbers -> @(
    .. -> :double
    -> :validate
    -> {.. processed=true}
)
```

**Replaces:** The `=>` operator. Now iteration is visually consistent with other branches and clearly shows its scope.

### Side Branch: `&()`
Executes operations for side effects while passing through the original input unchanged.

```comp
// Logging without affecting pipeline
config -> :validate
    -> &("Config validated: ${name}" -> :log)
    -> :apply

// Multiple side effects
data -> &(
    metrics -> :telemetry
    summary -> :audit_log
    "Processing..." -> :console
)
-> :continue  // data flows through unchanged
```

**Replaces:** The need for `!label` or manual pass-through patterns like `{.. -> :side_effect -> @original}`.

### Isolated Branch: `^()`
Executes with an empty context stack, preventing access to external resources.

```comp
// Pure computation only - no file/network access
user_input -> ^(:validate_pure -> :compute)

// Already existed for invoke operator
handler^(data)  // Isolated function call
```

**Maintains:** The existing `^()` invoke operator, now part of the branch family.

### Fallback Branch: `|()`
Handles failures with multiple recovery steps.

```comp
// Complex error handling
risky_op -> |(
    .. -> :log_error
    -> :cleanup_resources
    -> {status="recovered" fallback=true}
)

// Simple fallback still available
value | default_value
```

**Extends:** The `|` fallback operator for multi-statement error recovery. Simple `|` remains for basic fallbacks.

## Key Differences from Structs

- `{}` always creates a struct (even with a single pipeline inside)
- `.()` executes a pipeline and returns its result directly
- Other branches provide specialized execution contexts

```comp
// Struct constructor - returns {<result>}
data -> {:process}

// Group branch - returns raw result
data -> .(:process)
```

## Migration from Operators

```comp
// Old iteration with =>
users => :validate => :save

// New iteration with @()
users -> @(:validate -> :save)

// Old error handling with !>
risky !> :handler

// New with fallback branch (when multiple steps needed)
risky -> |(:log -> :cleanup -> :default)

// Old manual pass-through
data -> !label $d -> {.. -> :log -> $d}

// New with side branch
data -> &(.. -> :log)
```

## Removed Operators

- `=>` (iterate) - replaced by `@()`
- `!>` (error handler) - replaced by `|()` for complex cases

## Retained Operators

- `->` (invoke) - fundamental pipeline operator
- `|` (simple fallback) - for single-value fallbacks
- Conditional operators (`??`, `&?`, `?|`) - may get branch forms later

## Benefits

1. **Visual clarity** - Parentheses stand out among curly braces
2. **Consistent syntax** - All branches follow `-> X()` pattern
3. **Explicit scope** - Clear boundaries for multi-statement operations
4. **Composable** - Branches can be nested and combined
5. **Semantic meaning** - Each symbol relates to its purpose (@ for "at each", & for "and also", etc.)