# Failure Handling in Comp

Comp uses a structured approach to error handling based on failure tags, the `!disarm` operator, and fallback handlers. This design allows errors to be treated as first-class values that can be inspected, transformed, or propagated.

## Failure Tags

### The #fail Tag Hierarchy

The `#fail` tag marks values as failures that should bypass normal computation and propagate up the call stack. Failure tags form a hierarchy through extension:

```comp
!tag #fail = {#database #network #validation}
```

This creates three failure types that all extend `#fail`:
- `#fail.database` - Database-related errors
- `#fail.network` - Network-related errors  
- `#fail.validation` - Validation errors

### Failure Propagation

A value is considered a failure if it has a `#fail` descendant tag **in an unnamed field**:

```comp
; These ARE failures (propagate):
{_: #fail.database}           ; Unnamed field with fail tag
{_: {error: #fail.database}}  ; Unnamed field with nested fail tag

; These are NOT failures (don't propagate):
{error: #fail.database}       ; Named field with fail tag
{status: #ok}                 ; No fail tags at all
```

This design allows error information to be carried in structures without triggering failure propagation, which is essential for error handling patterns.

### Creating Failures

Failures are typically created by:

1. **The `fail()` function** - Creates a generic failure with a message
2. **Python exceptions** - Automatically wrapped with `#fail` in unnamed field
3. **Explicit failure structures** - Manual construction with fail tags

```comp
; Generic failure
!func |validate-age ~{age} = {
    $age.years < 0 ? fail("Age cannot be negative") : $in
}

; Specific failure type
!func |connect-db ~{path} = {
    ; Returns {_: #fail.database, message: "...", ...} on error
    [{database: $path} |call-func/py "sqlite3.connect"]
}
```

## The !disarm Operator

The `!disarm` operator creates a value that contains a failure tag but **is not itself a failure**. This allows failures to be stored, compared, or used as markers without triggering propagation.

```comp
; Create disarmed failure tags for comparison
!func |check-error-type ~{error} = {
    DatabaseError = !disarm #fail.database
    NetworkError = !disarm #fail.network
    
    $error.type == DatabaseError ? "Database problem" :
    $error.type == NetworkError ? "Network problem" :
    "Unknown error"
}
```

The `!disarm` operator is particularly useful for:
- Creating failure constants for pattern matching
- Storing failure tags in configuration
- Testing error handling code

### Implementation Detail

The `!disarm` operator evaluates its expression with `disarm_bypass=True`, which tells the engine to treat `#fail` tags as data rather than control flow signals. This flag propagates through all compound expressions (structures, identifiers, field accesses) so that the entire expression can be evaluated without triggering failure propagation.

### Module Assignments and Auto-Disarm

Module-level assignments (`$mod.name = value`) automatically evaluate with `disarm_bypass=True`. This allows you to define failure tag mappings and error constants at the module level without causing the module to fail during load:

```comp
; This works - module assigns auto-disarm
$mod.exception-tags = {
    InterfaceError = #fail.interface
    DatabaseError = #fail.database
    OperationalError = #fail.operation
}

; You can also store failed expressions in module scope
$mod.error-templates = {
    not-found = {_: #fail.not_found}
    invalid = {_: #fail.validation}
}
```

**Important**: The values are stored in a "disarmed" state but become live failures when accessed:

```comp
; Storing doesn't fail (auto-disarm)
$mod.db-error = {_: #fail.database, message: "Connection failed"}

; But accessing it in a pipeline WILL propagate the failure
!func |get-error = {
    $mod.db-error  ; This will fail!
}

; To safely use it, you need to wrap it in a named field
!func |get-error-safe = {
    {error: $mod.db-error}  ; This succeeds with error in named field
}
```

This design allows modules to define error-related constants and mappings without forcing every module that imports them to handle failures immediately.

## Fallback Handlers

Fallback handlers allow you to catch and transform failures into success values or different failure types.

### Pipe Fallback Operator `|?`

The pipe fallback operator (`|?`) catches failures in a pipeline and allows you to handle them:

```comp
; Basic fallback - return a default value
!func |safe-divide ~{a b} = {
    [{a: $a, b: $b} |divide |? {result: 0, error: "Division failed"}]
}

; Transform the error
!func |connect-with-fallback ~{path} = {
    [{database: $path} 
     |call-func/py "sqlite3.connect"
     |? {error: #fail.database, message: $in.message, path: $path}]
}
```

### Accessing the Failure Value

Inside a fallback handler, `$in` contains the failure value. The handler can inspect the failure and create an appropriate response:

```comp
!func |categorize-error ~{} = {
    [|failing-operation 
     |? {
         severity: $in.type == #fail.database ? "critical" : "warning"
         message: $in.message
         timestamp: $var.now
     }]
}
```

The fallback handler evaluates with `disarm_bypass=True`, which means:
- ✅ You can read `$in` even though it contains a `#fail` tag
- ✅ You can access fields like `$in.message` or `$in.type`
- ✅ You can use the failure value in expressions
- ❌ New errors in the handler still propagate (e.g., `5 + "string"`)

### Fallback Handler Results

The result of a fallback handler determines the pipeline's outcome:

1. **Success value** - Pipeline continues successfully
   ```comp
   |? {status: #ok, default: 0}  ; Returns success
   ```

2. **Failure in named field** - Pipeline continues with error info
   ```comp
   |? {error: #fail.database, msg: $in.message}  ; Returns success with error field
   ```

3. **Failure in unnamed field** - Pipeline fails (transforms the error)
   ```comp
   |? {_: #fail.custom_error}  ; Still fails, but with custom error
   ```

4. **New error** - Handler bug propagates
   ```comp
   |? (5 + "text")  ; Arithmetic error propagates
   ```

## Combining Patterns

### Named vs Unnamed Fields

The key to flexible error handling is understanding when failures propagate:

```comp
; ✅ This succeeds - error in named field
!func |safe-query ~{sql} = {
    [$sql |execute-sql |? {error: #fail.database, sql: $sql}]
}

; ❌ This fails - error in unnamed field
!func |strict-query ~{sql} = {
    [$sql |execute-sql |? {_: #fail.database, sql: $sql}]
}
```

This allows you to choose whether to:
- **Contain** errors in structures for later handling (named fields)
- **Transform** errors while maintaining failure propagation (unnamed fields)

### Chaining Fallback Handlers

Fallback handlers only trigger on failures, so they can be chained:

```comp
!func |resilient-operation ~{} = {
    [|try-primary
     |? |try-secondary
     |? {fallback: #true}]  ; Final default
}
```

### Error Enrichment

Fallback handlers can add context to errors before re-propagating them:

```comp
!func |connect-db ~{path} = {
    [{database: $path} 
     |call-func/py "sqlite3.connect"
     |? {
         ; Keep as failure (unnamed field) but add context
         _: $in._
         context: "Failed to connect to database"
         path: $path
         original_error: $in
     }]
}
```

## Design Principles

1. **Failures are values** - They can be stored, inspected, and transformed like any other value

2. **Unnamed fields propagate** - Only `#fail` tags in unnamed fields cause failure propagation

3. **Named fields contain** - `#fail` tags in named fields allow error information without propagation

4. **disarm_bypass propagates** - The ability to inspect failures flows through all compound expressions

5. **New errors still fail** - Bugs in handlers don't get silently swallowed

This design provides:
- Automatic error propagation by default
- Controlled error handling via fallback operators
- Rich error structures with context
- Type-safe error categorization via tag hierarchy
- Clear distinction between "this failed" and "here's info about a failure"
