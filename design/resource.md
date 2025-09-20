# Resources and Transactions

*Managing external state and coordinating changes in Comp*

## Overview

Resources represent connections to the world outside Comp - files, network
connections, database handles, graphics contexts. The language tracks these
automatically, ensuring cleanup when they're no longer needed while allowing
explicit early release. Combined with transactions, resources enable coordinated
state changes that can be atomically committed or rolled back.

The design philosophy favors multiplexed, synchronous operations over
traditional async/await patterns. Rather than managing concurrent promises, Comp
provides tools for efficient resource pooling, automatic retry logic, and
declarative coordination that eliminate most needs for explicit asynchronous
programming. For information about how resource access integrates with the
permission system, see [Runtime Security and Permissions](security.md).

The resource system follows several guiding principles:

- **Automatic tracking** ensures cleanup without manual bookkeeping
- **Explicit control** allows early release when needed
- **Transactional coordination** provides atomic multi-resource operations
- **Synchronous interface** eliminates callback complexity
- **Multiplexed operations** achieve efficiency without explicit async

These principles create a resource model that handles real-world complexity
while maintaining Comp's simplicity. Whether managing database connections,
coordinating distributed updates, or handling system resources, the unified
approach provides predictable, composable behavior. For patterns that complement
resource management with controlled state mutation, see [Store
System](store.md).

## Resource Fundamentals

A resource is an opaque handle to something outside the language's control.
Resources cannot be serialized, copied, or directly inspected - they exist
solely as capabilities for interaction with external systems. The language
automatically releases resources when they go out of scope, but programs can
also explicitly release them early.

```comp
; Resources are created by system functions
$file = (path/to/file |open/file)
$conn = (postgresql://localhost/mydb |connect/db)
$socket = {host=api.example.com port=443} |connect/net

; Automatic cleanup when leaving scope
!func |process-file ^{path ~str} = {
    $file = ^path |open/file
    $file |read/file |process
    ; $file automatically closed when function returns
}

; Explicit early release
$temp = (/tmp/data |open/file)
$temp |write/file data
$temp |release              ; Close immediately
```

Resources flow through pipelines like any other value but maintain their special
cleanup semantics. They can be stored in structures, passed to functions, and
returned from operations while the runtime tracks their lifecycle.

## Transaction System

Transactions coordinate multiple operations that should succeed or fail as a
unit. The `!transact` construct wraps a block of operations, automatically
handling commit on success or rollback on failure. Resources that support
transactions participate automatically through their defined transaction hooks.

Be aware that the language's use of transactions is more focused on rolling
back errors. There is currently no focus on isolation of concurrent 
transactions, outside of resources that naturally provide this, like databases.

```comp
; Basic transaction with single resource
!transact $database {
    (users |insert-user/db)
    (profile |insert-profile/db)
    (settings |insert-settings/db)
}
; All inserts commit together or all rollback

; Multiple coordinated resources
!transact $database $cache $search {
    $user-id = (user |insert/db |get-id)
    (user |set/cache user:${$user-id})
    (user |index/search users)
}
; All three systems update atomically
```

Transactions can be nested, with inner transactions becoming part of the outer
transaction's scope. This creates natural composition for complex operations
built from simpler transactional pieces.

## Resource Multiplexing Patterns

Rather than async/await, Comp favors multiplexed operations that handle multiple
resources efficiently. The standard library provides patterns for pooling,
batching, and coordinating resources without explicit concurrency management.

```comp
; Connection pooling with automatic management
$pool = (|create-pool/db url=database-url max=10)

; Pool automatically multiplexes connections
(requests |map {
    $pool |with {$in |
        (|query SELECT * FROM users WHERE id = ${id})
    }
})

; Declarative retry logic instead of promise chains
(operation |with-retry 
    attempts=3
    backoff=|exponential
    on-error=|warn/log)

; Coordinated fanout without async
(endpoints |map {$in |get/http timeout=5000}
           |gather)   ; Waits for all, handles partial failures
```

The language runtime can optimize these patterns, potentially using parallel
execution or async I/O internally while presenting a synchronous interface to
the programmer.

## Transaction Semantics

Transactions maintain consistency through several mechanisms that work together.
State capture preserves the execution context at transaction boundaries.
Resource coordination ensures all participants move through transaction phases
together. Error propagation guarantees that any failure triggers a complete
rollback.

```comp
; State preservation across transaction boundaries
$counter = 0
!transact $resource {
    $counter = $counter + 1     ; Local change
    (|risky-operation)                  ; Might fail
}
; If operation fails, $counter remains 0

; Transaction hooks for custom resources
resource %custom-handler {
    on-begin = |prepare-transaction
    on-commit = |finalize-changes  
    on-rollback = |restore-state
}
```
