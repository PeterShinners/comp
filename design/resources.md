# Resources, Transactions, and Security

*Design for Comp's resource management, transactional operations, security model, and capability-based permissions*

## Overview

Comp provides a comprehensive system for managing external resources through opaque handles, capability-based security tokens, and transactional operations. The design ensures deterministic behavior for pure functions while providing flexible resource management with automatic cleanup and permission control.

## Resource System Architecture

### Resource Handle Definitions

Resources are opaque handles that provide controlled access to external system resources:

```comp
// Handle type declarations
!handle %file_reader
!handle %network_socket  
!handle %database_cursor
!handle %graphics_context
```

**Key Properties**:
- **Opaque**: Handles contain no directly accessible data
- **Non-serializable**: Cannot be converted to strings or persisted
- **Module-scoped**: Only defining module can create instances
- **Reference counted**: Automatic cleanup when unreferenced
- **Thread-aware**: Optional thread affinity controls

### Resource Creation Syntax

```comp
!require read, write
!func :open_file ~{path ~string, mode ~string} = {
    $fd = {path=path, mode=mode} -> :syscall:open
    
    // Create resource handle with lifecycle callbacks
    $handle = $fd -> !resource %file_reader {
        release = [$fd -> :syscall:close]
        #inherit#none
        #thread#affinity.current
    }
    
    // Attach private module data
    $handle& = {fd=$fd, path=path, mode=mode, bytes_read=0}
    $handle
}
```

**Resource Creation Parameters**:
- `release`: Cleanup function called when handle released
- `#inherit#*`: Process inheritance behavior (none/explicit/always)  
- `#thread#affinity.*`: Thread restrictions (primary/current/any)

### Block-Based Resource Definitions

**New Syntax** for resource lifecycle management:

```comp
!resource %database_cursor {#thread#affinity.current}
    .release {cursor -> :db:close}
    .transact_begin {cursor -> :db:begin_transaction}
    .transact_commit {cursor -> :db:commit}
    .transact_rollback {cursor -> :db:rollback}

!resource %file_handle {}
    .release {handle -> :fs:close}
    .flush {handle -> :fs:sync}

!resource %network_connection {#inherit#explicit}
    .release {conn -> :net:close}
    .timeout {conn, seconds -> :net:set_timeout {conn=conn, timeout=seconds}}
```

**Key Points**:
- Initial struct `{}` holds resource metadata/tags
- Block names are language-defined, not arbitrary
- Blocks are callbacks that runtime controls
- `.release` typically required for cleanup
- Transaction blocks match `!transact` operator naming

### Private Data Attachment

Modules can attach private data to handles for internal state management:

```comp
// Private data during creation
$file_handle& = {
    internal_fd = file_descriptor
    bytes_processed = 0
    last_access = :time:now
    buffer_size = 4096
}

// Field-specific private assignment  
$handle&.position = 0
$handle&.cache = {}

// Multiple field assignment
$handle&.{buffer_size=8192, compression=!true, encoding="utf8"}
```

**Private Data Properties**:
- **Module-scoped**: Each module has its own private layer
- **Type-safe**: Can use private shapes with `&` suffix
- **Non-interfering**: Modules cannot access other modules' private data
- **Automatic inheritance**: Flows through pipeline operations

## Security Model

### Capability-Based Permissions

Comp uses capability-based security with predefined system tokens:

**Core System Tokens** (based on Deno's proven model):
- `read` - File system read access
- `write` - File system write access
- `net` - Network access (TCP/UDP, HTTP)
- `env` - Environment variable access
- `run` - Subprocess execution
- `ffi` - Foreign function interface/native libraries
- `sys` - System information access

**Comp-Specific Tokens**:
- `import` - Runtime module loading
- `polling` - Hardware entropy, high-resolution timers
- `secrets` - Hardware security modules, OS keychain
- `unbounded-iteration` - Infinite loops, recursive calls

### Permission Declaration

```comp
// Function-level requirements (checked at call time)
!require read, write
!func :process_file ~{path ~string} = {
    path -> :file:read -> :transform -> :file:write
}

// Module-level requirements
!require net, env
!import config = stdlib config

// Conditional permission requirements
!func :conditional_network ~{use_api ~bool} = {
    use_api -> {
        !require net
        data -> :http:post "https://api.example.com"
    } | {
        data -> :local:process  
    }
}
```

### Security Context Management

Security tokens stored in flowing `@ctx` namespace:

```comp
// Check permissions
@ctx -> :security:has #read     // !true or !false

// Drop permissions (irreversible in current context)
@ctx -> :security:drop #write
@ctx -> :security:drop {#net, #ffi}  // Drop multiple tokens

// Create restricted context for function calls
@ctx -> :security:only {#read} -> {
    // This block can only read, no other permissions
    data -> :process_with_read_only
}
```

**Token Properties**:
- Cannot be assigned to variables or stored
- Cannot be serialized or persisted  
- Cannot be restored once dropped
- Only operations: check existence and drop permissions

### Pure Function Security Isolation

Functions declared with `!pure` receive zero security tokens:

```comp
!pure :validate_email ~{email ~string} = {
    // @ctx = {} - no tokens available
    email -> :string:match /^[^@]+@[^@]+$/  // OK: pure computation
    email -> :file:read "config"            // ERROR: no read token
}
```

**Benefits**:
- **Compile-time evaluation**: Pure functions can run during compilation
- **Purity guarantees**: No side effects possible
- **Simple verification**: No static analysis required
- **Parallel safety**: Can execute in parallel without synchronization

### Application-Level Permission Control

```bash
# Restrict permissions at application startup
comp myapp.comp --allow=read,env --deny=net,ffi
comp myapp.comp --sandbox          # Minimal permissions
comp myapp.comp --no-network       # Network isolated
```

## Transaction System

### Transaction Construct

```comp
!transact using $resource {
    // Operations automatically wrapped in transaction
    data -> :update_primary
    data -> :update_secondary  
    data -> :log_changes
}
// Automatic commit on success, rollback on error
```

### Multi-Resource Transactions

```comp
!transact using $database, $cache, $search_index {
    // Resources coordinated in creation order
    // Cleanup happens in reverse order (LIFO)
    user -> :db:update -> :cache:invalidate -> :search:reindex
}
```

### Transaction State Capture

Transactions automatically capture scope state at entry:

```comp
$counter = 5
$config = {retry_limit=3}

!transact using $resource {
    // Snapshot of variables and context taken here
    $counter = $counter + 1
    @ctx.processing_mode = "batch"
    
    data -> :process
    // On success: changes committed
    // On error: $counter and @ctx restored to entry values
}
```

**Captured State**:
- Function-local variables (`$var`)
- Pipeline variables (`^var`)
- Module state (`@mod`) 
- Context state (`@ctx`) - excluding security tokens

### Resource Transaction Integration

Resources with transaction hooks:

```comp
// Create transactional resource
$db_handle -> !resource %database_cursor {
    release = [$cursor -> :db:close]
    transact_begin = [$cursor -> :db:begin_transaction]
    transact_commit = [$cursor -> :db:commit]
    transact_rollback = [$cursor -> :db:rollback]
}

// Usage in transaction
!transact using $db_handle {
    // Automatically calls transact_begin
    users => :validate -> :save_user
    // On success: calls transact_commit
    // On error: calls transact_rollback
}
```

### Transaction Semantics

1. **Entry**: Capture scope state, call `transact_begin` on all resources
2. **Execution**: Normal code execution with captured environment
3. **Success**: Apply state changes, call `transact_commit` on all resources (reverse order)
4. **Error**: Restore captured state, call `transact_rollback` on all resources (reverse order)

### Creative Application Examples

**3D Graphics Transaction**:
```comp
!transact using $maya_session {
    "sphere" -> :maya:create_sphere 
             ..> {scale={2.0, 2.0, 2.0}} -> :maya:transform
    "light" -> :maya:create_directional_light
            ..> {intensity=1.5} -> :maya:set_attr
}
// If any step fails, entire scene creation rolls back
```

**Multi-Service Update**:
```comp
!transact using $user_db, $billing_db, $notification_service {
    user -> :user_db:update_profile
    user -> :billing_db:update_subscription  
    user -> :notification_service:send_confirmation
}
// All services updated atomically or none
```

## Advanced Security Patterns

### Permission Delegation

```comp
// Create restricted execution context  
!func :run_sandboxed ~{code, allowed_permissions} = {
    // Create new context with only specified permissions
    @ctx -> :security:only allowed_permissions -> {
        code -> :evaluate
    }
}

// Usage
user_script -> :run_sandboxed {allowed_permissions={#read}}
```

### Resource Access Control

```comp
// Resources can check permissions at access time
!func :secure_file_read ~{handle %file_reader} = {
    // Check permission when accessing resource
    @ctx -> :security:require #read
    handle&.fd -> :syscall:read -> {
        handle&.bytes_read += @.length
        @
    }
}
```

### Module Permission Isolation

```comp
// Each imported module gets isolated security context
!import untrusted = comp ./third_party_module
// untrusted module cannot access main module's permissions

// Explicit permission delegation (proposed feature)
untrusted -> :restricted_function {
    permissions = {#read}    // Delegate only read permission
    data = sensitive_data
}
```

### Security Monitoring

```comp
// Monitor permission usage
@ctx -> :security:on_permission_use {
    permission, operation -> :audit:log {
        permission = permission
        operation = operation  
        timestamp = :time:now
        stack_trace = :debug:stack_trace
    }
}

// Set up alerts for sensitive operations
@ctx -> :security:alert_on {#write, #net} -> :security:notify_admin
```

## Implementation Examples

### File Processing with Resource Management

```comp
!handle %file_processor

!shape ProcessorState& = {
    fd ~number
    path ~string  
    lines_processed ~number
    last_error?
}

!require read
!func :open_processor ~{path ~string} = {
    $fd = {path=path, mode="r"} -> :syscall:open
    
    $handle = $fd -> !resource %file_processor {
        release = [$fd -> :syscall:close]
        #inherit#none
        #thread#affinity.current
    }
    
    $handle& = {fd=$fd, path=path, lines_processed=0} ~ProcessorState&
    $handle
}

!require read
!func :read_line ~{handle %file_processor} = {
    $result = handle&.fd -> :syscall:read_line !> {
        handle&.last_error = @
        #failure
    }
    
    handle&.lines_processed = handle&.lines_processed + 1
    $result
}

!require read, write  
!func :process_file_transactionally ~{input ~string, output ~string} = {
    $input_handle = input -> :open_processor
    $output_handle = {path=output, mode="w"} -> :file:open_for_write
    
    !transact using $input_handle, $output_handle {
        $input_handle 
            => :read_line
            => :transform_line  
            => :write_line $output_handle
    }
}
```

### Database Connection Pool

```comp
!handle %db_connection
!handle %connection_pool  

!resource %connection_pool {#thread#affinity.primary}
    .release {pool -> pool&.connections => :close_connection}
    .get_connection {pool -> :pool:acquire_connection}
    .return_connection {pool, conn -> :pool:release_connection {pool=pool, connection=conn}}

!require read, write
!func :create_pool ~{database_url ~string, max_connections ~number = 10} = {
    $connections = {1..max_connections} => {
        database_url -> :db:connect -> !resource %db_connection {
            release = [@ -> :db:disconnect]
            transact_begin = [@ -> :db:begin]
            transact_commit = [@ -> :db:commit]
            transact_rollback = [@ -> :db:rollback]
        }
    }
    
    $pool = {} -> !resource %connection_pool {}
    $pool& = {
        connections = $connections
        available = $connections
        in_use = {}
        max_connections = max_connections
    }
    
    $pool
}

!func :with_connection ~{pool %connection_pool, operation} = {
    $conn = pool -> :pool:get_connection
    operation -> :evaluate {connection=$conn} -> {
        pool -> :pool:return_connection $conn
        @
    } !> {
        pool -> :pool:return_connection $conn
        @  // Re-raise error
    }
}
```

### Secure API Gateway

```comp
!require net, read
!func :api_gateway ~{request} = {
    // Check API key
    api_key = request.headers."Authorization" | "" -> :extract_api_key
    
    // Load permissions for API key
    permissions = api_key -> :load_api_permissions !> {
        status = 401
        error = "Invalid API key"
        #http_response
    }
    
    // Create restricted context  
    @ctx -> :security:only permissions -> {
        request -> match {
            {path="/users/*", method="GET"} -> :handle_user_get
            {path="/users/*", method="POST"} -> :handle_user_post
            {path="/admin/*"} -> {
                // Admin endpoints require additional permission
                @ctx -> :security:require #admin -> {
                    request -> :handle_admin_request
                }
            }
            else -> {status=404, error="Endpoint not found", #http_response}
        }
    }
}
```

### Distributed Transaction Example

```comp
!handle %distributed_transaction

!func :create_distributed_transaction ~{participants %resource[]} = {
    $tx_id = :uuid:generate
    
    // Prepare phase - all participants must agree
    $prepared = participants => {
        @ -> :send_prepare {transaction_id=$tx_id}
    } -> {
        @ -> :all {vote="commit"}  // All must vote commit
    }
    
    $prepared ? {
        // Commit phase
        participants => :send_commit {transaction_id=$tx_id}
        {status="committed", transaction_id=$tx_id}
    } | {
        // Abort phase
        participants => :send_abort {transaction_id=$tx_id}  
        {status="aborted", transaction_id=$tx_id}
    }
}
```

## Performance Considerations

### Resource Pooling

```comp
// Connection pooling with automatic lifecycle
!func :with_pooled_resource ~{pool, operation} = {
    $resource = pool -> :acquire !> {
        :time:wait {milliseconds=100}  // Brief wait
        pool -> :acquire  // Retry once
    }
    
    operation -> :evaluate {resource=$resource} -> {
        pool -> :return $resource
        @
    } !> {
        pool -> :return $resource  // Always return to pool
        @
    }
}
```

### Lazy Resource Initialization

```comp
// Defer expensive resource creation
lazy_database = [
    database_url -> :create_connection_pool {max_connections=20}
]

!func :get_database = {
    @mod.database | {
        @mod.database = lazy_database -> :evaluate
        @mod.database
    }
}
```

### Thread-Safe Resource Access

```comp
!handle %thread_safe_resource

!resource %thread_safe_resource {#thread#affinity.any}
    .release {resource -> :close_safely}
    .lock {resource -> :acquire_mutex}
    .unlock {resource -> :release_mutex}

!func :thread_safe_operation ~{resource %thread_safe_resource, operation} = {
    resource -> :lock -> {
        operation -> :evaluate -> {
            resource -> :unlock
            @
        } !> {
            resource -> :unlock
            @  // Re-raise
        }
    }
}
```

## Implementation Priorities

1. **Basic Resource System**: Handle creation, private data, lifecycle management
2. **Security Token System**: Permission checking and context management
3. **Pure Function Isolation**: Empty context enforcement for `!pure` functions
4. **Transaction Framework**: State capture, resource coordination, rollback
5. **Resource Integration**: Transaction hooks and multi-resource coordination
6. **Advanced Patterns**: Permission delegation, resource pooling, monitoring
7. **Performance**: Resource sharing, lazy initialization, thread safety

## Open Design Questions

1. **Resource Inheritance**: Should child processes automatically inherit parent resources, or should inheritance be explicitly controlled?

2. **Cross-Module Resources**: Should modules be able to share resource handles directly, or should all sharing go through explicit APIs?

3. **Resource Serialization**: Should there be a way to serialize/deserialize resource references for distributed systems?

4. **Permission Granularity**: Should permissions be more fine-grained (e.g., read-specific-directory vs read-filesystem)?

5. **Transaction Nesting**: Should nested transactions be supported, and if so, what are the semantics for nested rollbacks?

6. **Async Resource Operations**: How should asynchronous resource operations integrate with the transaction system?

This design provides a comprehensive foundation for secure, transactional resource management that balances safety with practical usability, emphasizing explicit permission management and automatic resource cleanup while supporting complex coordination patterns.
