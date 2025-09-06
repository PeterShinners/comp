# Comp Language: Resources, Security, and Transactions

## Overview

The Comp language provides a comprehensive system for managing external resources through opaque handles, capability-based security tokens, and transactal operations. This system ensures deterministic behavior for compile-time functions while providing flexible resource management for runtime operations.

## Resources (Handles)

### Definition and Properties

Resources in Comp are represented as opaque handles that provide controlled access to external system resources like files, network connections, or hardware devices.

**Key Properties:**
- **Opaque**: Handles contain no directly accessible data
- **Non-serializable**: Cannot be converted to strings, numbers, or persisted
- **Module-scoped**: Only the defining module can create instances
- **Reference counted**: Automatic cleanup when no references remain
- **Thread-aware**: Optional thread affinity controls

### Handle Declaration

```comp
// Declare a handle type
!handle %file_reader
!handle %network_socket
!handle %database_cursor
```

Handle types are module-scoped - only the module that declares a handle type can create instances of it.

### Handle Creation

```comp
!require read, write
!func open_file ~{path ~string mode ~string} = {
    $fd = {path mode} -> :syscall:open
    
    $fd -> !resource %file_reader {
        release = [$fd -> :syscall:close]
        #inherit#none
        #thread#affinity.current
    }
    & = {fd=$fd path=path mode=mode} ~FileData&
}
```

**Creation Parameters:**
- `release`: Cleanup function called when handle is released
- `#inherit#*`: Process inheritance behavior (none/explicit/always)
- `#thread#affinity.*`: Thread restrictions (primary/current/any)

### Private Data Attachment

Modules can attach private data to any value, including handles:

```comp
// Attach private data during creation
handle -> {& = {internal_state} ~PrivateData&}

// Field-specific private assignment
$handle&fd = 42 &path = "/tmp/file"

// Multiple field assignment
$handle&fd=42 &path="/tmp/file" &mode="r"
```

Private data is:
- **Module-scoped**: Each module has its own private data layer
- **Type-safe**: Can use private shapes with `&` suffix
- **Non-interfering**: Modules cannot see each other's private data

### Handle Operations

```comp
// Manual release (optional - automatic when out of scope)
handle -> !release

// Describe for debugging
handle -> :lang:describe
// Output: "%file_reader created by open_file({path="/tmp/data.txt", mode="r"})"

// Check if handle is still valid (thread-safe)
handle -> :lang:is_valid  // true/false
```

## Security Tokens

### Token System

Comp uses capability-based security where functions declare required permissions using predefined system tokens. All token checks happen at runtime when resources are accessed.

### Predefined System Tokens

Based on Deno's proven permission model with Comp-specific additions:

**Core System Tokens:**
- `read` - File system read access
- `write` - File system write access  
- `net` - Network access (TCP/UDP, HTTP)
- `env` - Environment variable access
- `run` - Subprocess execution
- `ffi` - Foreign function interface / native libraries
- `sys` - System information access

**Comp-Specific Tokens:**
- `import` - Runtime module loading
- `polling` - Hardware entropy, high-resolution timers
- `secrets` - Hardware security modules, OS keychain
- `unbounded-iteration` - Infinite loops, recursive calls

### Permission Declaration

```comp
// Function-level requirement (checked at call time)
!require read, write
!func process_file ~{path ~string} = {
    path -> :file:read -> :transform -> :file:write
}

// Inside function (checked immediately)
!func conditional_operation ~{use_network ~bool} = {
    use_network -> :if {
        !require net
        data -> :http:post "https://api.example.com"
    }
}
```

### Context Management

Security tokens are stored in the flowing `@ctx` namespace:

```comp
// Check permissions
@ctx -> :security:has #read     // true/false

// Drop permissions (irreversible)
@ctx -> :security:drop #write
@ctx -> :security:drop {#net #ffi}  // Multiple tokens

// Tokens cannot be:
// - Assigned to variables
// - Stored in .mod
// - Serialized or persisted
// - Restored once dropped
```

### Block Function Restrictions

Functions declared with `!block` receive zero security tokens, ensuring compile-time safety:

```comp
!block validate_email ~{email ~string} = {
    // @ctx = {} - no tokens available
    email -> :string:match /^[^@]+@[^@]+$/  // OK: pure computation
    email -> :file:read "config"            // ERROR: no read token
}
```

This enables:
- **Compile-time evaluation**: Block functions can run during compilation
- **Purity guarantees**: No side effects possible
- **Simple verification**: No static analysis required

### Application-Level Control

```bash
# Restrict permissions at startup
comp myapp.comp --allow=read,env --deny=net,ffi
comp myapp.comp --no-network
```

## Transactions

### Transaction Construct

**Creative Software Example:**
```comp
!transact using $maya_session {
    "ball" -> :maya:create_sphere 
           ..> {scaleX=2.0} -> :maya:xform
           ..> {translateY=5.0} -> :maya:xform
    "light" -> :maya:create_directional_light
            ..> {intensity=1.5} -> :maya:set_attr
}
// If any step fails, entire scene creation rolls back automatically
```

```comp
!transaction using $database_handle {
    // Operations here are automatically wrapped
    updates => "UPDATE users SET active=true WHERE id=${id}" -> :sql:execute
    "INSERT INTO audit_log VALUES ${timestamp}, 'activation'" -> :sql:execute
    // Automatic commit on success, rollback on error
}
```

### Multi-Resource Transactions

```comp
!transaction using $db_cursor, $cache_handle {
    // Resources coordinated in creation order
    // Cleanup happens in reverse order (LIFO)
    data -> :database:update
    data -> :cache:invalidate
}
```

### State Capture

Transactions automatically capture scope state at entry:

```comp
$counter = 5
$config = {timeout=30}

!transaction using $resource {
    // Snapshot of $counter, $config, @ctx, etc. taken here
    // Rollback restores captured state on error
    $counter = 10  // This change rolls back on error
}
// On success: $counter = 10
// On error: $counter = 5 (restored)
```

**Captured State:**
- Function-local variables (`$var`)
- Pipeline variables (`^var`) 
- Module state (`@mod`)
- Context state (`@ctx`) - excluding security tokens

### Resource Integration

Resources can implement optional transaction hooks:

```comp
// Resource with transaction support
$handle -> !resource %database_cursor {
    release = [$cursor -> :db:close]
    transaction_begin = [$cursor -> :db:begin_transaction]
    transaction_commit = [$cursor -> :db:commit]
    transaction_rollback = [$cursor -> :db:rollback]
}
```

If a resource doesn't provide transact hooks, using it in `!transact` raises an error - this prevents silent failures when users expect transactional behavior.
- `transaction_begin`: Called when transaction starts
- `transaction_commit`: Called on successful completion
- `transaction_rollback`: Called on error or explicit rollback

### Transaction Semantics

1. **Entry**: Capture all scope state, call `transaction_begin` on resources
2. **Execution**: Normal code execution with captured environment
3. **Success**: Apply state changes, call `transaction_commit` on resources
4. **Error**: Restore captured state, call `transaction_rollback` on resources

## Implementation Notes

### Thread Safety

- **Handle creation**: Thread that creates handle becomes owner (unless `#thread#affinity.any`)
- **Cross-thread access**: Runtime error if accessed from wrong thread
- **Handle passing**: References can be passed between threads safely
- **Private data**: Module-specific, no cross-thread guarantees needed

### Resource Lifecycle

1. **Creation**: `!resource` allocates handle, attaches cleanup
2. **Usage**: Functions operate on opaque handle via private data
3. **Release**: Manual `!release` or automatic when references reach zero
4. **Cleanup**: Release function called exactly once per handle

### Security Enforcement

- **Token checking**: Happens at API call sites, not function entry
- **Static warnings**: Analyzer can flag obvious violations (`!block` calling I/O)
- **Runtime authority**: Security decisions made at execution time
- **No bypass**: Tokens cannot be forged, stored, or restored

### Error Handling

```comp
// Resource operations can fail at any time
handle -> :file:read  // May fail: file deleted, permissions changed, etc.

// Transaction rollback on any error
!transaction using $handle {
    data -> :process    // If this fails, transaction rolls back
    result -> :commit   // Never reached on error
}
```

## Example: Complete File Processing Module

```comp
!handle %file_processor

!shape FileState& = {
    fd ~number
    path ~string
    lines_processed ~number
}

!require read
!func open_file ~{path ~string} = {
    $fd = {path mode="r"} -> :syscall:open
    
    $fd -> !resource %file_processor {
        release = [$fd -> :syscall:close]
        #inherit#none
        #thread#affinity.current
    }
    & = {fd=$fd path=path lines_processed=0} ~FileState&
}

!require read
!func read_line ~{handle %file_processor} = {
    $result = handle&.fd -> :syscall:read_line
    handle&.lines_processed = handle&.lines_processed + 1
    result
}

!require read, write
!func process_file_transactionally ~{input_path ~string output_path ~string} = {
    $input = input_path -> open_file
    $output = {output_path mode="w"} -> :file:open_for_write
    
    !transaction using $input, $output {
        $input => read_line => :transform => :file:write_line $output
    }
}
```

This example demonstrates:
- Handle type declaration and creation
- Private data attachment and access
- Security token requirements
- Transaction coordination with multiple resources
- Automatic cleanup and error handling

---

*This specification provides the foundation for safe, deterministic resource management in the Comp programming language.*