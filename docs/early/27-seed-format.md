# Statement Seeding and String Formatting in Comp

## Overview

Two fundamental changes improve Comp's consistency and predictability:
1. **Statement Seeding**: Every statement automatically begins with the context input
2. **String Formatting**: Templates require explicit formatting operators

## Statement Seeding

### Core Concept

Every statement in a function or branch is "seeded" with the input data through an implied `.. ->` prefix.

```comp
// These are equivalent
!func process ~data = {
    x = .. -> :validate    // Explicit seed
    y = :validate          // Implied seed (automatic)
}
```

### How It Works

Each statement starts fresh from the context input:

```comp
!func analyze ~data = {
    validated = :validate       // data -> :validate
    transformed = :transform    // data -> :transform (NOT validated -> :transform)
    summary = :summarize        // data -> :summarize
}
```

### Context Resets

The seed resets at statement boundaries:

```comp
!func process ~data = {
    // First statement: seeded with data
    result = :step1 -> :step2 -> :step3
    
    // Second statement: seeded with data again (not with result)
    other = :different_process
    
    // Pipeline continuation still works normally
    final = :stepA -> {temp = ..} -> :stepB  // .. is stepA's result
}
```

### Benefits

Parallel operations become natural:

```comp
!func analyze = {
    // All operate on input independently
    metrics = :calculate_metrics
    summary = :generate_summary  
    validation = :run_checks
    
    // Combine results
    {metrics summary validation}
}
```

### Branches and Blocks

Seeding applies uniformly to all contexts:

```comp
// Function blocks
!func process = {
    x = :validate          // Seeded with function input
}

// Branch blocks  
data -> @(
    :validate -> :save     // Each element is the seed
)

// Side branches
config -> &(
    :log                   // Seeded with config
)
```

## String Formatting Changes

### No Invoke on Values

Values can no longer be invoked directly. This affects string templates:

```comp
// OLD - strings auto-invoked for templating
template = "Hello ${name}"
result = data -> template        // Auto-formatted

// NEW - explicit formatting required
template = "Hello ${name}"  
result = data % template         // Explicit format operator
```

### The Format Operator: `%`

Templates are formatted using the `%` operator:

```comp
// Basic formatting
{name="Alice"} % "Hello ${name}"     // "Hello Alice"

// With units for escaping
{id=5} % "SELECT * FROM users WHERE id = ${id}"#sql
{title="<script>"} % "<h1>${title}</h1>"#html
```

### Prefix Format: `..%`

Format using the seed value:

```comp
!func greet = {
    // Using seeded input for formatting
    message = ..% "Welcome ${name}!"
    error = ..% "User ${id} had an error"
}

// In branches
users -> @(
    ..% "Processing user ${name}" -> :log
    -> :save
)
```

### Templates as Values

Templates are now first-class values:

```comp
// Store templates
$sql_template = "SELECT * FROM ${table} WHERE id = ${id}"#sql
$greeting = "Hello ${name}"

// Format later
result = data % $sql_template
message = user % $greeting

// Pass templates to functions
:format_message {template="Hi ${name}" data=user}
```

## Combined Examples

```comp
!func process_users ~users = {
    // Seeding: each statement starts with users
    validated = :validate_all
    count = :length
    
    // Format with seed
    summary = ..% "${count} users to process"
    
    // Iterate with formatting
    results = @(
        :check_permission
        -> &(..% "Checking ${name}" -> :log)  // Side effect with format
        -> :process
    )
    
    // Return structure
    {validated results summary}
}

// Error handling with formatting
risky_operation -> ||(
    ..% "Operation failed: ${error.message}" -> :log
    -> {fallback=true}
)
```

## Migration Guide

```comp
// Old: String invoke
data -> "Template ${field}"

// New: Explicit format
data % "Template ${field}"

// Old: Confusion about what starts a pipeline
!func process = {
    .. -> :validate -> x
    .. -> :transform -> y  // Had to be explicit
}

// New: Seeding makes it natural
!func process = {
    x = :validate
    y = :transform  // Automatically seeded
}
```

## Key Takeaways

1. **Every statement is seeded** - No need for explicit `.. ->` at statement start
2. **Seeds reset at statement boundaries** - Each statement gets fresh input
3. **String templates need explicit formatting** - Use `%` or `..%` operators
4. **Values cannot be invoked** - Removes ambiguity about invoke syntax
5. **Consistency across contexts** - Same rules for functions, branches, and blocks