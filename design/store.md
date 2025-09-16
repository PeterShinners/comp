# Store System for Comp Language

## Overview

The Store provides controlled mutable state in Comp's otherwise immutable environment. Rather than allowing individual mutable structures, all mutable data lives in Store containers that are accessed through explicit operations. This creates a clear boundary between immutable and mutable worlds, making programs easier to reason about.

## Core Concept

```comp
; Create a store - the ONE mutable container
$store = :store/new {
    users = {}
    config = {theme="light" lang="en"}
    cache = {}
}

; All data from store is immutable
user = $store -> :get /users.123/          ; Returns immutable struct
user.name = "Bob"                          ; ERROR - can't mutate

; Mutations go through store operations
$store -> :set /users.123.name/ <- "Bob"   ; Explicit mutation
```

## Basic Operations

### Read/Write Operations
```comp
$store -> :get /path/                      ; Read value
$store -> :set /path/ <- value             ; Write value
$store -> :update /path/ <- transformer    ; Modify value
$store -> :delete /path/                   ; Remove value
$store -> :exists? /path/                  ; Check existence
```

### Transactions
```comp
$store -> :transaction {
    :set /users.123/ <- user_data
    :update /stats.user_count/ <- {@ + 1}
    :delete /cache.temp/
}
```

## Change Detection

The Store provides layered change detection with progressive cost:

### Level 1: Global Version (Minimal Overhead)
```comp
; Get opaque version token
$v = $store -> :version

; Check if anything changed
$store -> :changed? $v                     ; Returns true/false

; Conditional update
$store -> :set_if_unchanged /path/ <- value since=$v
```

Versions are opaque values - only the store knows how to compare them. They could be timestamps, counters, UUIDs, or any implementation-specific value.

### Level 2: Path-Specific Tracking (On Demand)
```comp
; First call activates tracking for this path
$v = $store -> :modified /users/

; Check specific subtree
$store -> :changed? /users/ $v
```

Tracking is lazy - no overhead until first request, then only tracks requested paths and their descendants.

### Level 3: Change Details (Most Expensive)
```comp
$changes = $store -> :changes_since $version
; Returns: {paths={/users.123/ /config.theme/} version=<new_version>}
```

## Cursor Navigation

Cursors provide natural navigation through store data:

```comp
; Cursor maintains position context
$cursor = $store -> :cursor /users.123/
name = $cursor.value.name                  ; Access data
$cursor -> :set <- {name="Alice"}          ; Update at position

; Navigation
$parent = $cursor -> :cursor/up            ; Go to /users/
$child = {$cursor /profile/} -> :cursor/down  ; Go to /users.123.profile/
```

Cursors are simple structs:
```comp
!shape ~Cursor = {
    store ~Store
    path ~path
    value ~any
}
```

## Integration with Path System

The Store leverages Comp's path system for powerful queries:

```comp
; Simple paths for direct access
$store -> :set /users.123.email/ <- "new@example.com"

; Complex queries with selectors (via functions)
{$store /users.*.email/} -> :path/fetchall  ; All emails
{$store /users[active]/} -> :path/query     ; Active users
{$store /**.error/} -> :path/hasany?        ; Any errors?
```

## Benefits

### Clear Reasoning
```comp
; You always know where mutations happen
data -> process -> transform               ; All immutable
$store -> :set /result/ <- data           ; ONLY place mutation occurs
```

### Functional Core, Imperative Shell
```comp
; Pure functional processing
!func calculate_total = {order ->
    order -> :apply_tax -> :apply_discount
}

; Imperative shell using store
!func process_order = {order ->
    $total = calculate_total(order)        ; Pure
    $store -> :transaction {                ; Imperative
        :set /orders.$order.id/ <- order
        :update /inventory/ <- reduce_by(order.items)
    }
}
```

### Testing
```comp
; Easy to test with isolated stores
$test_store = :store/new {users={} config=default_config}
run_operation($test_store)
assert($test_store -> :get /users.123/ == expected)
```

## Future Extensions

The Store API is designed to support advanced implementations:

- **Persistent stores** - Backed by disk/database
- **Thread-safe stores** - Concurrent access control
- **IPC stores** - Shared between processes
- **Distributed stores** - Networked state

Each implementation can optimize version tracking, change detection, and storage while maintaining the same core API.

## Design Principles

1. **Explicit Mutation** - All changes go through store operations
2. **Immutable Views** - Data retrieved from store is immutable
3. **Opaque Versions** - Version tokens are meaningful only to the store
4. **Lazy Tracking** - Change detection activates only when needed
5. **Path-Based Access** - Leverages Comp's powerful path system
6. **Simple Core** - Basic stores need only minimal operations


The path system provides a powerful, unified way to navigate and manipulate structured data while maintaining Comp's philosophy of simplicity and composability.

The Store pattern gives Comp the benefits of mutability (efficiency, state management) while preserving the reasoning benefits of immutability. It's a controlled, predictable approach to state management that scales from simple variables to complex application state.

