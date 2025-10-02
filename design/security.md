# Runtime Security and Permissions

*Design for Comp's simplified capability-based security model*

## Overview

Comp implements capability-based security through a simple binary model: functions either have access to external resources or they don't. The `!pure` decorator creates guaranteed isolation by executing functions in a resource-free context. This straightforward approach provides real security boundaries without the complexity of fine-grained permissions that rarely deliver on their promises.

The security model draws from proven designs while maintaining radical simplicity. A single `resource` capability token controls all external access—filesystem, network, threads, everything. Pure functions execute with no resource access, providing guaranteed determinism and safety. This binary distinction makes security boundaries clear and enforceable.

The security system embodies core principles of simplicity and honesty. Rather than pretending to offer fine-grained sandboxing that can't be properly enforced, Comp provides a clear boundary between computation and effects. Pure functions guarantee deterministic computation without side effects, while regular functions can access resources as needed. This binary model is easy to understand, simple to enforce, and actually useful for optimization and reasoning about code.

## The Resource Token

The runtime provides a single `resource` token that controls access to all external systems. Functions either have this token (can perform I/O) or don't (pure computation only). This binary model admits what permission systems are actually protecting—the boundary between computation and the outside world.

```comp
; Regular function - has resource access
!func |process-file ^{path ~str} = {
    content = [^path |fetch]          ; Needs resource token
    processed = [content |transform]   ; Pure computation
    [processed |save-to-cache]        ; Needs resource token
}

; Pure function - no resource access
!pure
!func |transform ~{data} = {
    ; Guaranteed: deterministic, no side effects
    ; Can be cached, parallelized, evaluated at build time
    validated = $in |validate
    normalized = $in |normalize
    {validated normalized}
}
```

## Pure Function Guarantees

Pure functions execute in a completely empty context with no access to resources. The `!pure` decorator isn't just a hint—it creates hard enforcement at runtime. These functions literally cannot access the outside world because the resource token doesn't exist in their context.

### What Pure Functions Cannot Do

- **No filesystem access** - Cannot read/write files or directories
- **No network operations** - Cannot make HTTP requests or open sockets
- **No system information** - Cannot access time, random numbers, or environment
- **No mutable state** - Cannot create or modify stores (which require resources)
- **No module globals** - Cannot access `$mod` mutable state
- **No describe operations** - Cannot introspect runtime state or stack traces

### What Pure Functions Can Do

- **Computation** - Any deterministic calculation on input data
- **Pass resources through** - Resources can flow through without being accessed
- **Create blocks** - Blocks inherit purity from their creation context
- **Handle errors** - Full error handling with `|?` and `??` operators
- **Call other pure functions** - Build complex pure computations

```comp
!pure
!func |calculate ~{input} = {
    ; Can do complex computation
    result = $in |validate |process |optimize
    
    ; Can handle errors normally
    safe-result = result |? {
        ; Error handlers run in pure context too
        {#calculation-failed value=$in}
    }
    
    ; Can pass resources through without accessing
    {result resource=input.resource}  ; Resource passes through untouched
}
```

## Store and Resource Integration

Stores require resources internally, preventing their use in pure functions. This ensures pure functions cannot smuggle mutable state:

```comp
; Store creation requires resource token
!func |create-cache = {
    @store = [|new/store {}]  ; Acquires resource internally
    @store
}

!pure
!func |pure-attempt = {
    @store = [|new/store {}]  ; FAILS - no resource token available
}

; Pure functions can work with immutable snapshots
!pure
!func |analyze ~{snapshot} = {
    ; Read from immutable snapshot (no resource needed)
    value = snapshot.data
    ; Cannot modify - snapshot is immutable
    value |transform
}
```

## Module Initialization and Purity

Module-level initialization has specific rules for pure functions:

- Module constants defined at top level are accessible to pure functions
- `!entry` modifications to `$mod` are NOT visible to pure functions
- Pure functions see `$mod` as it exists at build time

```comp
; Module-level constant - visible to pure functions
$mod.constant = 42

!entry = {
    ; Runtime initialization - NOT visible to pure functions
    $mod.cache = [|initialize-cache]
    $mod.runtime-config = [|load-config]
}

!pure
!func |pure-calc = {
    value = $mod.constant     ; OK - build-time constant
    ; cache = $mod.cache     ; FAILS - not available in pure context
}
```

## Standard Library Enforcement

The standard library enforces purity through internal resource requirements. Every function that could have side effects acquires a resource internally, making it impossible to call from pure functions:

```comp
; Standard library implementations
!func |current-time = {
    @clock = [|acquire-resource clock]  ; Fails in pure context
    [@clock |read]
}

!func |random = {
    @rng = [|acquire-resource entropy]  ; Fails in pure context
    [@rng |generate]
}

!func |print ~{message} = {
    @output = [|acquire-resource io]    ; Fails in pure context
    [@output |write message]
}

; File operations through capability system
!func |fetch ^{path ~str} = {
    @fs = [|acquire-resource filesystem] ; Fails in pure context
    [@fs |read ^path]
}
```

This design makes purity automatic—if a function runs in a pure context, it's actually pure. No careful labeling or trust required.

## Runtime Enforcement

Applications can control resource availability at startup:

```bash
# Run with resource access (default)
comp app.comp

# Run with no resource access (pure computation only)
comp app.comp --pure

# Future: prompt for resource access
comp app.comp --prompt
```

The runtime ensures no code can create resource tokens—they're only available through the initial runtime context. Pure functions receive an empty context with no possibility of acquiring resources.

## Benefits of Simplicity

The single resource token model provides real, enforceable benefits:

**Build-time evaluation** - Pure functions can run during compilation
**Aggressive caching** - Results are deterministic and cacheable forever  
**Parallelization** - No coordination needed between pure computations
**Testing** - Pure functions need no mocks or environment setup
**Optimization** - Compiler can reorder, deduplicate, or eliminate pure calls

This binary distinction—pure or not—is honest about what can actually be enforced while providing genuine value for optimization and reasoning about code.

## Security Patterns

The simplified model enables clear security patterns:

```comp
; Validate untrusted data with pure functions
!pure
!func |validate-input ~{data} = {
    ; Cannot access filesystem, network, or state
    ; Perfect for untrusted data validation
    data |check-format |verify-constraints
}

; Process with minimal resource exposure
!func |safe-process ~{untrusted} = {
    ; Validate in pure context first
    validated = [untrusted |validate-input]
    
    ; Only access resources after validation
    [validated |if :{$in} :{
        [$in |process-with-resources]
    } :{
        {#invalid-input.fail}
    }]
}
```

The beauty of this model is its honesty—it doesn't pretend to offer security it can't provide, while delivering real guarantees about computational behavior that enable meaningful optimizations and safer code.