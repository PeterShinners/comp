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
!func |process-file arg ~{path ~str} = {
    content = [$arg.path |fetch]          ; Needs resource token
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

## Pure Functions

Pure functions execute in a completely resource-free context with strict enforcement. The `pure` keyword is placed before the function name: `!func pure |name ...`. This creates hard runtime enforcement—these functions literally cannot access the outside world.

### Syntax

```comp
; Pure function - keyword before function name
!func pure |fibonacci ~{n ~num} = {
    [n |if :{$in <= 1} :{$in} :{
        $var.a = [n - 1 |fibonacci]
        $var.b = [n - 2 |fibonacci]
        $var.a + $var.b
    }]
}

!func pure |validate-email ~{email ~str} = {
    [$in.email |match/str "^[^@]+@[^@]+$"]
}

!func pure |transform ~{data} = {
    [$in.data |normalize |validate]
}
```

### Enforcement Mechanisms

Pure functions are enforced through multiple runtime checks:

1. **Pure context flag** - When a pure function is invoked, the execution frame is marked with `pure_context=True`. This flag propagates to all child frames and cannot be revoked.

2. **Function call restrictions** - Pure functions can only call other pure functions. Attempting to call a non-pure function from pure context fails immediately with: `"Cannot call non-pure function |name from pure context (pure functions can only call other pure functions)"`

3. **Handle operations blocked** - The `!grab` operator checks the frame's pure context and fails if active: `"Cannot !grab in pure function (pure functions cannot have side effects)"`

4. **Private data restrictions** - Accessing private data on handles fails in pure context: `"Cannot access handle private data in pure function (pure functions cannot have side effects)"`
   - Note: Private data on non-handle values is allowed (no side effects)

5. **Block purity propagation** - Blocks created in pure functions maintain pure context when invoked later, even if invoked from non-pure code.

6. **Module assignments** - All `$mod.field = value` assignments evaluate in pure context to prevent side effects in module constants.

7. **Tag value expressions** - Tag value expressions (`!tag #name = expr`) evaluate in pure context to prevent side effects in tag definitions.

### What Pure Functions Cannot Do

- **No handle operations** - Cannot `!grab` handles (side effects)
- **No handle private data** - Cannot access `&` private data on handles (side effects)
- **No non-pure function calls** - Cannot call functions that aren't marked `pure`
- **No filesystem access** - Cannot read/write files or directories
- **No network operations** - Cannot make HTTP requests or open sockets
- **No system information** - Cannot access time, random numbers, or environment
- **No mutable state** - Cannot create or modify stores (which require resources)
- **No module globals** - Cannot access `$mod` mutable state
- **No describe operations** - Cannot introspect runtime state or stack traces

### What Pure Functions Can Do

- **Computation** - Any deterministic calculation on input data
- **Call pure functions** - Build complex pure computations by calling other pure functions
- **Create blocks** - Blocks inherit purity from their creation context
- **Handle errors** - Full error handling with `|?` and `??` operators
- **Access private data** - Can access private data on non-handle values (no side effects)
- **Pass resources through** - Resources can flow through without being accessed

```comp
!func pure |calculate ~{input} = {
    ; Can do complex computation
    result = $in |validate |process |optimize
    
    ; Can handle errors normally
    safe-result = result |? {
        ; Error handlers run in pure context too
        {#calculation-failed value=$in}
    }
    
    ; Can call other pure functions
    final = [safe-result |other-pure-func]
    
    ; Can pass resources through without accessing
    {result resource=input.resource}  ; Resource passes through untouched
}
```

## Store and Resource Integration

Stores require resources internally, preventing their use in pure functions. This ensures pure functions cannot smuggle mutable state:

```comp
; Store creation requires resource token
!func |create-cache = {
    $var.store = [|new/store {}]  ; Acquires resource internally
    $var.store
}

!pure
!func |pure-attempt = {
    $var.store = [|new/store {}]  ; FAILS - no resource token available
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
    $var.clock = [|acquire-resource clock]  ; Fails in pure context
    [$var.clock |read]
}

!func |random = {
    $var.rng = [|acquire-resource entropy]  ; Fails in pure context
    [$var.rng |generate]
}

!func |print ~{message} = {
    $var.output = [|acquire-resource io]    ; Fails in pure context
    [$var.output |write message]
}

; File operations through capability system
!func |fetch arg ~{path ~str} = {
    $var.fs = [|acquire-resource filesystem] ; Fails in pure context
    [$var.fs |read $arg.path]
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

## Implementation Details

### Pure Context Propagation

The `pure_context` flag on execution frames ensures purity is maintained:

1. When a pure function is invoked, `FunctionDefinition.invoke()` sets `pure_context=True` in the Compute object
2. The engine creates a frame with `pure_context=True`
3. Child frames inherit `pure_context` from parent frames
4. Once `pure_context=True`, it cannot be revoked within that execution chain
5. Blocks capture the frame's `pure_context` when created, maintaining it when invoked later

### Module Constants and Tag Values

Module assignments and tag values are evaluated in pure context:

- `$mod.field = expression` evaluates `expression` with `pure_context=True`
- `!tag #name = expression` evaluates `expression` with `pure_context=True`
- This prevents side effects in module constants and tag definitions
- Values are evaluated with `disarm_bypass=True`, so failures are stored as values

### Blocks from Pure Functions

Blocks created in pure functions maintain pure context:

```comp
!func pure |make-processor ~{} = {
    ; Block created in pure context
    processor = :{result = [|some-func]}
}

!func |invoke-block ~{b ~block} = {
    ; Block maintains pure context when invoked
    ; Can only call pure functions, cannot !grab, etc.
    [{}|:b]
}
```

This ensures that deferred computations from pure functions remain pure, even when invoked from non-pure code.

## Security Patterns

The simplified model enables clear security patterns:

```comp
; Validate untrusted data with pure functions
!func pure |validate-input ~{data} = {
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