# Namespaces and Field Lookups

* Description of how field lookups and assignments are handled.

## Overview

Whenever a field name is referenced, it comes from one of several predefined
namespaces. Any function being executed exists in a stack of namespaces
that override each other to define all available fields.

This is separate from the function temporary namespace, where all varianles
are prefixed with `$` dollar sign.




## Namespace System

### Hierarchical Namespace Access

```comp
@app.config         ; Application-level configuration
!mod.state          ; Module-level state
@env.production     ; Environment settings  
@ctx.security       ; Context-specific data
!in.data           ; Input context
!out.result        ; Output context
$func.temporary    ; Function-scoped (auto-cleared)
```

### Namespace Flow Through Pipelines

Context flows automatically through pipeline operations:

```comp
; Context preservation
@ctx.timeout = 30
data -> :fetch -> :validate -> :process
; All functions can access @ctx.timeout

; Function-scoped isolation
!func :process_data = {
    $func.retries = 3        ; Function-local only
    $func.start_time = :time/now
    
    data -> :transform -> :validate
}  ; $func namespace cleared here
```

### Context Stack Hierarchy

**Resolution Order**: `$func` → `!mod` → `@app` → `@env`

```comp
; Setting values at different levels
@env.database_url = "postgres:;prod"      ; Environment
@app.max_connections = 100                 ; Application  
!mod.table_prefix = "user_"               ; Module
$func.batch_size = 50                     ; Function

; Access uses first match in hierarchy
connection_limit = @ctx.max_connections    ; Finds @app.max_connections
```

### Thread-Safe Context Management

**Context Isolation**: Each thread gets independent copy of parent context at spawn time.

```comp
; Main thread
@app.config = {debug=!true, workers=4}
@ctx.processing_mode = "batch"

; Spawned thread gets copy
:threading/spawn {
    ; This thread has independent copy of @app and @ctx
    ; Changes here don't affect parent or sibling threads
    @ctx.processing_mode = "streaming"    ; Local to this thread
}

; Main thread unchanged
@ctx.processing_mode    ; Still "batch"
```



## Runtime Introspection

Description of !describe and it's values

