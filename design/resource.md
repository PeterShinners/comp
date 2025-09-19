# Resources and Transactions

*Managing external state and coordinating changes in Comp*

## Overview

Resources represent connections to the world outside Comp - files, network connections, database handles, graphics contexts. The language tracks these automatically, ensuring cleanup when they're no longer needed while allowing explicit early release. Combined with transactions, resources enable coordinated state changes that can be atomically committed or rolled back.

The design philosophy favors multiplexed, synchronous operations over traditional async/await patterns. Rather than managing concurrent promises, Comp provides tools for efficient resource pooling, automatic retry logic, and declarative coordination that eliminate most needs for explicit asynchronous programming.

## Resource Fundamentals

A resource is an opaque handle to something outside the language's control. Resources cannot be serialized, copied, or directly inspected - they exist solely as capabilities for interaction with external systems. The language automatically releases resources when they go out of scope, but programs can also explicitly release them early.

```comp
# Resources are created by system functions
$var.file = (path/to/file | open/file)
$var.conn = (postgresql://localhost/mydb | connect/db)
$var.socket = {host=api.example.com port=443} | connect/net

# Automatic cleanup when leaving scope
func process_file pipeline{} args{path} = {
    $var.file = $arg.path | open/file
    $var.file | read/file | process
    # $var.file automatically closed when function returns
}

# Explicit early release
$var.temp = (/tmp/data | open/file)
$var.temp | write/file data
$var.temp | release              # Close immediately
```

Resources flow through pipelines like any other value but maintain their special cleanup semantics. They can be stored in structures, passed to functions, and returned from operations while the runtime tracks their lifecycle.

## Transaction System

Transactions coordinate multiple operations that should succeed or fail as a unit. The `transact` construct wraps a block of operations, automatically handling commit on success or rollback on failure. Resources that support transactions participate automatically through their defined transaction hooks.

```comp
# Basic transaction with single resource
transact $database {
    (users | insert_user/db)
    (profile | insert_profile/db)
    (settings | insert_settings/db)
}
# All inserts commit together or all rollback

# Multiple coordinated resources
transact $database $cache $search {
    $var.user_id = (user | insert/db | get_id)
    (user | set/cache user:${$var.user_id})
    (user | index/search users)
}
# All three systems update atomically
```

Transactions can be nested, with inner transactions becoming part of the outer transaction's scope. This creates natural composition for complex operations built from simpler transactional pieces.

## Resource Multiplexing Patterns

Rather than async/await, Comp favors multiplexed operations that handle multiple resources efficiently. The standard library provides patterns for pooling, batching, and coordinating resources without explicit concurrency management.

```comp
# Connection pooling with automatic management
$var.pool = (| create_pool/db url=database_url max=10)

# Pool automatically multiplexes connections
(requests | map {
    $var.pool | with {$in |
        (| query SELECT * FROM users WHERE id = ${id})
    }
})

# Declarative retry logic instead of promise chains
(operation | with_retry 
    attempts=3
    backoff=|exponential
    on_error=|warn/log)

# Coordinated fanout without async
(endpoints | map {$in | get/http timeout=5000}
           | gather)   # Waits for all, handles partial failures
```

The language runtime can optimize these patterns, potentially using parallel execution or async I/O internally while presenting a synchronous interface to the programmer.

## Transaction Semantics

Transactions maintain consistency through several mechanisms that work together. State capture preserves the execution context at transaction boundaries. Resource coordination ensures all participants move through transaction phases together. Error propagation guarantees that any failure triggers a complete rollback.

```comp
# State preservation across transaction boundaries
$var.counter = 0
transact $resource {
    $var.counter = $var.counter + 1     # Local change
    (| risky_operation)                  # Might fail
}
# If operation fails, $var.counter remains 0

# Transaction hooks for custom resources
resource %custom_handler {
    on_begin = |prepare_transaction
    on_commit = |finalize_changes  
    on_rollback = |restore_state
}
```

## Design Principles

The resource system follows several guiding principles:

- **Automatic tracking** ensures cleanup without manual bookkeeping
- **Explicit control** allows early release when needed
- **Transactional coordination** provides atomic multi-resource operations
- **Synchronous interface** eliminates callback complexity
- **Multiplexed operations** achieve efficiency without explicit async

These principles create a resource model that handles real-world complexity while maintaining Comp's simplicity. Whether managing database connections, coordinating distributed updates, or handling system resources, the unified approach provides predictable, composable behavior.

## Future Considerations

As the resource system evolves, several areas deserve exploration:

**Resource Permissions**: Integration with the capability system to control which code can create or access specific resource types.

**Resource Inheritance**: How resources behave across process boundaries or when passed to isolated execution contexts.

**Custom Resource Types**: Allowing modules to define their own resource types with transaction hooks and lifecycle callbacks.

**Distributed Transactions**: Patterns for coordinating resources across network boundaries using two-phase commit or saga patterns.

**Performance Optimization**: Runtime strategies for parallel resource operations while maintaining synchronous semantics.

These extensions would build on the core model without complicating the basic resource and transaction operations that most programs need.