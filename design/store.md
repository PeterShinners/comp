# Store System

*Controlled mutable state management in Comp*

## Overview

The Store provides controlled mutability in Comp's immutable world. Rather than allowing arbitrary mutable values, all mutable state lives in Store containers that are accessed through explicit operations. This creates a clear boundary between immutable data transformation and stateful operations, making programs easier to reason about while providing the efficiency benefits of mutation when needed.

Every interaction with a Store returns immutable data. Mutations only occur through explicit Store operations, creating a functional core with an imperative shell pattern that combines the best of both paradigms.

## Store Fundamentals

A Store is a mutable container that holds structured data. Unlike regular structures which are immutable, Stores can be modified in place through a defined set of operations. However, all data retrieved from a Store is immutable, maintaining Comp's functional programming guarantees.

```comp
# Create a store with initial data
$var.store = (| new/store {
    users = {}
    config = {theme=dark lang=en}
    cache = {}
})

# Read immutable data from store
$var.user = $var.store | get /users.123/
$var.theme = $var.store | get /config.theme/

# Explicit mutations through store operations
$var.store | set /users.123/ new_user
$var.store | update /config.theme/ light
$var.store | delete /cache.temp/
```

The separation between reading and writing is intentional and explicit. You cannot accidentally mutate data - all mutations require calling a Store operation. This makes it easy to track where state changes occur in your program.

## Store Operations

Stores provide a focused set of operations for state management. Read operations return immutable snapshots, write operations modify the Store in place, and query operations provide information about the Store's contents.

```comp
# Basic operations
$var.store | get /path/              # Read value at path
$var.store | set /path/ value        # Write value at path
$var.store | delete /path/           # Remove path and value
$var.store | exists? /path/          # Check if path exists
$var.store | clear                   # Remove all data

# Update operations with functions
$var.store | update /counter/ {$in + 1}
$var.store | modify /users/ |filter {.active}

# Bulk operations
$var.store | set_many {
    /users.new/ = new_user
    /cache.user/ = new_user.id
    /stats.count/ = count + 1
}
```

Updates receive the current value and return the new value, enabling complex transformations while maintaining immutability for the data itself. If an update function fails, the Store remains unchanged.

## Transactions

Stores support transactions for coordinating multiple mutations that should succeed or fail as a unit. Transactions provide atomicity - either all operations succeed or none do, leaving the Store in a consistent state.

```comp
# Transaction with multiple operations
$var.store | transaction {
    $in | set /users.123/ user_data
    $in | update /stats.user_count/ {$in + 1}
    $in | delete /cache.temp/
}
# All operations succeed or all rollback

# Conditional transactions
$var.store | transaction {
    $var.current = $in | get /balance/
    $in | if {$var.current >= amount} {
        $in | update /balance/ {$in - amount}
        $in | set /transactions.${id}/ {amount from=balance}
    } {
        {#insufficient_funds.fail}
    }
}
```

Transactions can be nested, with inner transactions becoming part of the outer transaction's scope. This enables building complex operations from simpler transactional pieces.

## Change Tracking

Stores provide efficient change detection through versioning. Each Store maintains an internal version that updates with every mutation. This enables efficient checking for modifications without expensive comparisons.

```comp
# Get current version (opaque value)
$var.version = $var.store | version

# Check if store changed since version
$var.store | changed? $var.version        # Returns #true or #false

# Get changes since version
$var.changes = $var.store | changes_since $var.version
# Returns: {paths=[/users.123/ /config/] new_version=...}

# Conditional updates based on version
$var.store | set_if_unchanged /path/ value since=$var.version
# Succeeds only if store hasn't changed since $var.version
```

Versions are opaque values that only the Store understands. They might be timestamps, counters, or hashes - the implementation is hidden. This allows different Store implementations to optimize version tracking for their specific use cases.

## Store Patterns

Common patterns emerge when working with Stores. These patterns provide structure for managing application state while maintaining clarity about where mutations occur.

```comp
# Centralized application state
$mod.app_store = (| new/store {
    session = {}
    ui = {theme=dark sidebar_open=#true}
    data = {}
})

# Functional core, imperative shell
func process_order pipeline{order} args{} = {
    # Pure functional processing
    validated = $in | validate
    total = validated | calculate_total
    
    # Imperative shell with store
    $mod.app_store | transaction {
        $in | set /orders.${$in.id}/ validated
        $in | update /revenue.daily/ {$in + total}
    }
    
    {success=#true order_id=$in.id total=total}
}

# Local state for UI components
func counter_component pipeline{} args{} = {
    $var.local = (| new/store {count=0})
    
    # Event handlers modify store
    on_increment = {$var.local | update /count/ {$in + 1}}
    on_reset = {$var.local | set /count/ 0}
    
    # Render from immutable snapshot
    current = $var.local | get /count/
    {value=current on_increment on_reset}
}
```

## Integration with Trails

Stores naturally integrate with the trail system for flexible path-based access. All Store operations that use paths accept trails, enabling dynamic state management.

```comp
# Use trails for dynamic access
$var.user_trail = /users.${user_id}/
$var.store | get $var.user_trail

# Bulk operations with trail patterns
$var.store | select /users.*.active/       # Get all active flags
$var.store | update_all /prices.*/ {$in * 1.1}  # Increase all prices

# Complex queries
active_users = $var.store | query /users.[active]/
$var.store | delete_matching /cache.expired.*/
```

## Design Principles

The Store system follows several guiding principles:

- **Explicit mutation**: All state changes go through Store operations
- **Immutable views**: Data retrieved from Stores cannot be mutated
- **Transactional consistency**: Multi-operation changes are atomic
- **Efficient change detection**: Version tracking without deep comparison
- **Clear boundaries**: Obvious separation between functional and stateful code

These principles create a state management system that provides the benefits of mutation - efficiency, simplicity for stateful operations - while preserving the reasoning benefits of immutability throughout the rest of the program. The Store becomes the controlled boundary where the functional and imperative worlds meet.