# Runtime Security

## Overview

The runtime provides a predefined collections of security tokens.
These live in a protected part of the calling context, which is passed
along each function call. Any code can drop security tokens, which will
be removed for all downsteam callers.

Dropped tokens can never be restored, until the call chain returns to
the point where the token was removed.

Pure functions are a slight variation of functions that drop all permissions
before they are called. This is the primary way to ensure they can be run
safely at compile-time without accessing features outside of the language's
control.


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
; Function-level requirements (checked at call time)
!require read, write
!func :process_file ~{path ~str} = {
    path -> :file/read -> :transform -> :file/write
}

; Module-level requirements
!require net, env
!import onfig/ = stdlib config

; Conditional permission requirements
!func :conditional_network ~{use_api ~bool} = {
    use_api -> {
        !require net
        data -> :http/post "https:;api.example.com"
    } | {
        data -> :local/process  
    }
}
```

### Security Context Management

Security tokens stored in flowing `@ctx` namespace:

```comp
; Check permissions
@ctx -> :security/has #read     ; !true or !false

; Drop permissions (irreversible in current context)
@ctx -> :security/drop #write
@ctx -> :security/drop {#net, #ffi}  ; Drop multiple tokens

; Create restricted context for function calls
@ctx -> :security/only {#read} -> {
    ; This block can only read, no other permissions
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
!pure :validate_email ~{email ~str} = {
    ; @ctx = {} - no tokens available
    email -> :str/match /^[^@]+@[^@]+$/  ; OK: pure computation
    email -> :file/read "config"            ; ERROR: no read token
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

## Advanced Security Patterns

### Permission Delegation

```comp
; Create restricted execution context  
!func :run_sandboxed ~{code, allowed_permissions} = {
    ; Create new context with only specified permissions
    @ctx -> :security/only allowed_permissions -> {
        code -> :evaluate
    }
}

; Usage
user_script -> :run_sandboxed {allowed_permissions={#read}}
```

### Resource Access Control

```comp
; Resources can check permissions at access time
!func :secure_file_read ~{handle %file_reader} = {
    ; Check permission when accessing resource
    @ctx -> :security/require #read
    handle&.fd -> :syscall/read -> {
        handle&.bytes_read += @.length
        @
    }
}
```

### Module Permission Isolation

```comp
; Each imported module gets isolated security context
!import ntrusted/ = comp ./third_party_module
; untrusted module cannot access main module's permissions

; Explicit permission delegation (proposed feature)
untrusted -> :restricted_function {
    permissions = {#read}    ; Delegate only read permission
    data = sensitive_data
}
```

### Security Monitoring

```comp
; Monitor permission usage
@ctx -> :security/on_permission_use {
    permission, operation -> :audit/log {
        permission = permission
        operation = operation  
        timestamp = :time/now
        stack_trace = :debug/stack_trace
    }
}

; Set up alerts for sensitive operations
@ctx -> :security/alert_on {#write, #net} -> :security/notify_admin
```