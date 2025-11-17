

## Local Scope

Variables can be defined inside a structure or function definition
to compute and store intermiedate values. These are created using
`let` assignments. These will define a new variable and assign a
value to it. These values can be referenced anywhere in the following
code.

```comp
{
    let sum = 1 + 10 + 100  ; local variable
    double-sum = sum + sum  ; outgoing field
}
```

## Context Scope

Context scope is managed differently than most others. Every time a function is
invoked it inherits the `$ctx` scope from whatever called it. Any overrides to
this context are not preserved when the function stops executing.

This is included in the `^` scope, which allows a way to set function
arguments that will be visible deeper in the call stack. 

Any function can reset this context with a call to `$ctx = {}`. When `!pure`
functions are evaluating they will only be called with an empty context.

```comp
!func |parent = {
    $ctx.session-id = "abc123"
    data |child-function  ; $ctx.session-id is available in child
}

!func |child-function ~{data} = {
    ; Inherits $ctx.session-id from parent
    log-entry = {
        session = $ctx.session-id
        action = data.action
    }
}
```



### Local Scope

This scope is used for function level temporaries. When the function completes
this scope is removed.

This scope is shared across any blocks defined inside the function. 
Modifications made to `$var` variables within blocks are visible to
the rest of the function scope.

This scope is intended to be overwritten regularly.

```comp
!func |example = {
    $var.counter = 0
    
    result = data |process :{
        $var.counter = $var.counter + 1  ; Modifies function-level $var.counter
        value = $var.counter * 2
    }
    
    $var.final = $var.counter  ; Sees the modified value from the block
}
```

### Argument Scopes

The `$arg` scope contains the arguments supplied to the function, morphed to match
the function's argument shape. The morphing combines values from `$mod`, `$ctx`,
and the directly passed arguments. If the morph cannot succeed, the function call
fails immediately at the call site.

This scope cannot be overwritten.

The function preparation code creates `$arg` by morphing like:
`{..$mod ..$ctx ..<passed-args>} ~function-arg-shape`.

```comp
; Developer knows exactly where values come from
$ctx.port = 8080
$mod.host = "default.com"

!func |connect arg ~{host ~str port ~num timeout ~num = 30} = {
    ; If $arg.port missing from all of {..$mod ..$ctx ..<passed>},
    ; function fails at call site, not deep inside
    [$arg.host |connect-to $arg.port]
}

; Function call with partial args
[|connect host="override.com"]
; $arg becomes: {host="override.com" port=8080 timeout=30}
; - host from passed args (overrides $mod)
; - port from $ctx
; - timeout from shape default
```

### Inherited Scopes

**`$ctx` - Execution context**
- Follows the call stack, inherited by called functions
- Can be modified and passed down to subsequent calls
- Persists across function boundaries within the same execution chain

```comp
!func |outer = {
    $ctx.shared-data = "available everywhere"
    inner-data |inner-function
}

!func |inner-function ~{data} = {
    ; Can access $ctx.shared-data from outer function
    result = $ctx.shared-data + data.value
}
```

**`$mod` - Module scope**
- Global to the entire module
- Shared by all functions and definitions in the same file
- Persists for the lifetime of the module

```comp
; Module-level configuration
$mod.config = {database-url="localhost" timeout=30}

!func |connect = {
    ; All functions can access module scope
    connection = $mod.config.database-url |database.connect
}
```

## Concrete Types, Not Inference

Comp uses a fundamentally different approach to types than most modern languages. Instead of inferring types from context, Comp values carry their concrete types as intrinsic properties. This design choice affects error messages, performance, and how you reason about code.

### Values Have Types, Not Variables

In most languages, variables have types that are either declared or inferred:

```typescript
// TypeScript - variable 'x' has inferred type 'number'
let x = 42;

// Rust - variable 'items' has inferred type 'Vec<i32>'
let items = vec![1, 2, 3];
```

In Comp, values themselves carry type information:

```comp
; The value 42 IS a number - no variable typing needed
x = 42

; The structure IS this shape when created
data = {name="Alice" age=30}
```
