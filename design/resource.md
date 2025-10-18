Resources and Transactions
Managing external state and coordinating changes in Comp

Overview
Resources represent connections to the outside world—files, network connections, database handles, graphics contexts. These are opaque handles that cannot be serialized, copied, or directly inspected. The language tracks them automatically, ensuring cleanup without manual bookkeeping. Combined with transactions, resources enable coordinated state changes that can be atomically committed or rolled back.

The design favors simplicity over complexity. Resources require the single resource capability token to create, making them impossible to access from pure functions. This creates a clear boundary between pure computation and effectful operations. The system provides synchronous operations with automatic retry and pooling patterns rather than explicit async/await complexity.

The resource system follows several guiding principles:

Automatic tracking ensures cleanup without manual bookkeeping
Explicit control allows early release when needed
Transactional coordination provides atomic multi-resource operations
Synchronous interface eliminates callback complexity
Pure function isolation prevents resource access in pure contexts
These principles create a resource model that handles real-world complexity while maintaining Comp's simplicity. Whether managing database connections, coordinating distributed updates, or handling system resources, the unified approach provides predictable, composable behavior.

Resource Fundamentals
A resource is an opaque handle to something outside the language's control. Resources cannot be serialized, copied, or directly inspected—they exist solely as capabilities for interaction with external systems. The language automatically releases resources when they go out of scope, but programs can also explicitly release them early.

All resource creation requires the resource capability token, which is absent in pure functions:

```comp
; Resources require capability token (fails in pure functions)
$var.file = ["/path/to/file" |open/file]      ; Needs resource token
$var.conn = ["postgresql://localhost/mydb" |connect/db]
$var.socket = [{host="api.example.com" port=443} |connect/net]

; Automatic cleanup when leaving scope
!func |process-file arg ~{path ~str} = {
    $var.file = [$arg.path |open/file]      ; Acquires resource
    [$var.file |read/file |process]
    ; $var.file automatically closed when function returns
}

; Explicit early release
$var.temp = ["/tmp/data" |open/file]
[$var.temp |write/file data]
[$var.temp |release]                      ; Close immediately

; Pure functions cannot create resources
!pure
!func |pure-process ~{data} = {
    ; $var.file = ["path" |open/file]   ; FAILS - no resource token
    [$in.data |transform]                    ; Can only do computation
}
```

Resources flow through pipelines like any other value but maintain their special cleanup semantics. They can be stored in structures, passed to functions, and returned from operations while the runtime tracks their lifecycle.

Resource Passing Through Pure Functions
While pure functions cannot create or access resources, they can pass them through as opaque values:

```comp
!pure
!func |transform-container ~{data} = {
    ; Can pass resource through without accessing it
    {
        transformed = $in.data.value |calculate
        resource = $in.data.resource     ; Passes through untouched
    }
}

; Regular function uses the resource
!func |process = {
    $var.conn = [|connect/db]
    
    container = {value=100 resource=$var.conn}
    result = [container |transform-container]  ; Pure function
    
    ; Can access resource after pure function returns it
    [result.resource |query "SELECT * FROM users"]
}
```

Transaction System
Transactions coordinate multiple operations that should succeed or fail as a unit. The !transact construct wraps a block of operations, automatically handling commit on success or rollback on failure. Resources that support transactions participate automatically through their defined transaction hooks.

```comp
; Basic transaction with single resource
!transact $database {
    [users |insert-user/db]
    [profile |insert-profile/db]
    [settings |insert-settings/db]
}
; All inserts commit together or all rollback

; Multiple coordinated resources
!transact $var.database $var.cache $var.search {
    $var.user-id = [$in.user |insert/db |get-id]
    [$in.user |set/cache "user:${$var.user-id}"]
    [$in.user |index/search "users"]
}
; All three systems update atomically
```

Transactions can be nested, with inner transactions becoming part of the outer transaction's scope. This creates natural composition for complex operations built from simpler transactional pieces.

Resource Multiplexing Patterns
Rather than async/await, Comp favors multiplexed operations that handle multiple resources efficiently. The standard library provides patterns for pooling, batching, and coordinating resources without explicit concurrency management.

```comp
; Connection pooling with automatic management
$var.pool = [|create-pool/db url="database-url" max=10]

; Pool automatically multiplexes connections
[requests |map {
    [$var.pool |with {[$in |
        [|query "SELECT * FROM users WHERE id = ${$in.id}"]
    ]}]
}]

; Declarative retry logic instead of promise chains
[operation |with-retry 
    attempts=3
    backoff=|exponential
    on-error=|warn/log]

; Coordinated fanout without async
[endpoints |map {[$in |get/http timeout=5000]}
           |gather]   ; Waits for all, handles partial failures
```

The language runtime can optimize these patterns, potentially using parallel execution or async I/O internally while presenting a synchronous interface to the programmer.

Transaction Semantics
Transactions maintain consistency through several mechanisms. State capture preserves the execution context at transaction boundaries. Resource coordination ensures all participants move through transaction phases together. Error propagation guarantees that any failure triggers a complete rollback.

```comp
; State preservation across transaction boundaries
$var.counter = 0
!transact $var.resource {
    $var.counter = $var.counter + 1     ; Local change
    [|risky-operation]                   ; Might fail
}
; If operation fails, $var.counter remains 0

; Transaction hooks for custom resources
resource ~custom-handler {
    on-begin = |prepare-transaction
    on-commit = |finalize-changes  
    on-rollback = |restore-state
}
```

Pure Functions and Resources
The integration between resources and pure functions is simple: pure functions cannot create or manipulate resources, but can pass them through as opaque values. This maintains purity while allowing resources to flow through pure transformations:

```comp
!pure
!func |route-data ~{packet} = {
    ; Can't access the connection resource
    ; But can route based on other fields
    packet.type |match
        {#priority} {{..packet queue="express"}}
        {#bulk} {{..packet queue="standard"}}
        {#true} {packet}
}

!func |network-handler = {
    $var.conn = [|open-connection]
    
    [packets |map {
        packet = {data=$in connection=$var.conn type=#bulk}
        routed = [packet |route-data]  ; Pure routing logic
        [routed.connection |send routed.data]  ; Use resource after
    }]
}
```

This separation ensures pure functions remain deterministic while still participating in resource-based workflows.

