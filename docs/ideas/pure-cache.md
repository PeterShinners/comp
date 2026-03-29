# Memos: Pure Caching for Pure Functions

## Concept

A **memo** is a language-privileged caching mechanism for pure functions. It is a **benign effect** — mutable state that does not alter observable behavior. Same inputs always produce same outputs; the cache only affects performance, not semantics.

This makes memos safe to use inside `!pure` functions without breaking their contract of determinism and no side effects.

## Prior Art

- **Haskell**: Lazy evaluation is implicit caching of thunks. Explicit memoization typically requires `unsafePerformIO`, recognized as legitimate for this use case. Comp's approach is cleaner by making it a language primitive.
- **Clojure**: `memoize` wraps a function with an atom-backed cache. Same philosophy, no static enforcement.
- **Rust**: `OnceCell`/`LazyCell` — interior mutability permitted behind `&` because mutation is idempotent and unobservable.

## Design

The surface-level API is a **wrapper**:

```
!pure fib ~num @memoize (
    !param val~num
    !on $ < 2
    ~true 1
    ~false (fib (val - 1)) + (fib (val - 2))
)
```

The `@memoize` wrapper intercepts calls, checks the cache by key (derived from arguments), and either returns a cached result or invokes the function body and stores the result.

### Key properties

- The function body remains a plain pure function with no cache plumbing
- The wrapper sits *outside* the function's semantic boundary, so there is no shared scope between cache machinery and function logic
- Cache key defaults to all arguments (partial keying is a future refinement)

### Memo configuration via context

Memos are configured at the **context** level, separating policy (size, eviction) from mechanism (the wrapper):

```
!context main {
    fib-mem = memo.create(records=32, eviction=memo.lru)
}
```

Different deployment contexts can provide differently-configured memos for the same functions. The wrapper resolves its memo configuration from the caller's context.

### Cache management operations (clear, drop, stats) live outside pure functions

Pure functions cannot observe or trigger cache eviction. Management is handled by the runtime or impure orchestration layer, preserving the invariant that the cache is unobservable from inside pure code.

## The Purity Hole (and why wrappers avoid it)

If caching were implemented as an inline primitive (e.g., `pure-cache.lookup` inside a function body), the compute block could capture local mutable state and leak information about whether the cache was hit:

```
// BROKEN: compute block shares scope with parent
!pure sneaky ~nil (
    :pure-cache memory
    !let computed false
    memory.lookup(0, :(!on computed ~true "AA" "BB"))
)
// {sneaky sneaky sneaky} → {"AA" "BB" "BB"} — non-deterministic!
```

The wrapper approach eliminates this entirely. The function body is a **closed term** (no free variables from cache scope), so there is no channel through which cache hit/miss status can leak into the return value.

## Status

Conceptual design. Not on the immediate implementation path. Wrapper parameter resolution (how `@memoize` discovers its memo config from context) needs further exploration when implementation begins.