# Runtime Security and Permissions

*Design for Comp's capability-based security model and permission system*

## Overview

Comp implements capability-based security through permission tokens that flow through the execution context. These tokens cannot be stored, serialized, or manipulated as values - they exist only in the protected context namespace and control access to system resources. Any code can drop permissions for downstream calls, but dropped permissions cannot be restored until returning to the scope that held them.

The security model draws from proven designs like Deno's permission system while adding Comp-specific features. Permissions are declarative, enabling static analysis and clear documentation of function requirements. Pure functions provide guaranteed isolation by executing with no permissions, making them safe for untrusted code and compile-time evaluation.

## Permission Token System

The runtime defines a fixed set of permission tokens that control access to system resources. These tokens live in the protected portion of the `!ctx` namespace and flow through function calls. Programs start with a set of permissions determined by runtime flags, and these can only be reduced, never expanded, during execution.

Core system tokens based on proven models:
- `read` - File system read access
- `write` - File system write access  
- `net` - Network access (TCP/UDP, HTTP)
- `env` - Environment variable access
- `run` - Subprocess execution
- `ffi` - Foreign function interface access
- `sys` - System information queries

Comp-specific tokens for language features:
- `import` - Runtime module loading
- `unbounded` - Infinite loops and recursion
- `timing` - High-resolution timers
- `random` - Hardware entropy access

```comp
; Check current permissions
!ctx -> :security/has #read           ; Returns #true or #false
!ctx -> :security/list                ; Returns list of current tokens

; Drop permissions for downstream code
!ctx -> :security/drop #write         ; Remove write permission
!ctx -> :security/drop {#net #ffi}    ; Drop multiple tokens

; Create restricted execution context
!ctx -> :security/only {#read} -> {
    ; This block can only read files
    data -> :process_untrusted
}
```

## Function Permission Requirements

Functions declare required permissions using the `!require` decorator. This serves as documentation, enables compile-time verification where possible, and provides clear error messages when permissions are missing. The decorator appears before the function definition and lists required tokens.

```comp
!require read, write
!func :backup_file ~{source ~str dest ~str} = {
    source -> :file/read        ; Needs read token
    -> :compress
    -> :file/write dest         ; Needs write token
}

!require net, env
!func :fetch_with_config ~{endpoint ~str} = {
    api_key = "API_KEY" -> :env/get      ; Needs env token
    headers = {"Authorization" = "Bearer ${api_key}"}
    endpoint -> :http/get headers        ; Needs net token
}

; Permissions flow through call chains
!func :admin_operation = {
    :backup_file           ; Inherits caller's permissions
    :fetch_with_config     ; Also inherits permissions
}
```

When a function requiring permissions is called without them, it fails immediately with a clear error identifying the missing permission and the operation that required it. This fail-fast approach prevents security violations and makes permission requirements explicit.

## Pure Functions and Guaranteed Isolation

Pure functions provide deterministic computation without side effects. The `!pure` decorator on a function definition creates guaranteed isolation - these functions receive an empty `!ctx` with no permission tokens, preventing any resource access.

```comp
!pure
!func :calculate ~{x ~num y ~num} = {
    result = x * y + 42
    normalized = result % 100
}

!pure
!func :validate_structure ~{data} = {
    ; Can perform computation
    valid = data ~? ExpectedShape
    score = :calculate_score
    
    ; Cannot access resources
    ; data -> :file/write "log"     ; ERROR: no write permission
    ; :random/secure                ; ERROR: no random permission
}

; Pure functions enable optimizations
!shape ~Config = {
    cache_key = :generate_key    ; Evaluated at compile time
    validator = :validate_structure
}
```

The `!pure` decorator syntax emphasizes that purity is an additional constraint on a function, not a different kind of entity. Pure functions can call other functions, but those calls execute in the same restricted context, failing if they attempt any resource access.

## Isolated Execution Contexts

The `^()` branch creates isolated execution contexts for untrusted code. Code within this branch receives an empty context, similar to pure functions, but applied dynamically at runtime. This enables safe execution of user-provided code or untrusted modules.

```comp
!func :run_user_code ~{code} = {
    ; Full permissions available here
    config = :load_config
    
    ; Isolated execution - no permissions
    result = code -> ^(
        :evaluate    ; Cannot access files, network, etc.
    )
    
    ; Permissions restored after branch
    result -> :save_result
}

; Gradual permission reduction
!func :process_stages = {
    sensitive_data -> :encrypt           ; Full permissions
    
    -> :security/drop #write -> {
        :analyze                          ; Can read but not write
    }
    
    -> ^(:pure_compute)                  ; No permissions at all
}
```

## Module Permission Boundaries

Each module import creates a permission boundary. Imported modules cannot access the importing module's permissions unless explicitly delegated. This prevents supply chain attacks where compromised dependencies could abuse the main application's permissions.

```comp
; Main application has full permissions
!require read, write, net

; Import untrusted module - gets no permissions by default
!import processor/ = comp "./untrusted"

!func :process_with_untrusted ~{data} = {
    ; Untrusted module operates without permissions
    processed = data -> processor:transform
    
    ; Delegate specific permission for one operation
    !ctx -> :security/only {#read} -> {
        processor:load_config
    }
}
```

Modules can declare their permission requirements, making dependencies' security needs transparent. Build tools can analyze the permission tree to identify the total permission surface of an application.

## Runtime Permission Control

Applications specify their permission requirements at startup through command-line flags or configuration. The runtime enforces that no code can exceed these initial permissions, creating a security sandbox for the entire program.

```bash
# Run with specific permissions
comp app.comp --allow read,env --deny net,ffi

# Run with no permissions (sandbox mode)
comp app.comp --sandbox

# Run with all permissions (development mode)
comp app.comp --allow-all

# Prompt for permissions interactively
comp app.comp --prompt
```

The runtime can also implement permission prompting, where users are asked to grant permissions when first needed. Granted permissions can be remembered for future runs, creating a trust model similar to mobile applications.

## Permission Inheritance and Dropping

Permissions follow a strict inheritance model through the call stack. Each function receives its caller's permissions by default. Functions can drop permissions for downstream calls, but cannot add permissions they didn't receive. This creates a monotonic security model where permissions only decrease along call paths.

```comp
!require read, write, net
!func :main_application = {
    ; Has all three permissions
    :full_operation
    
    ; Drop network for file operations
    !ctx -> :security/drop #net
    :file_only_operation      ; Has read, write
    
    ; Further restriction
    !ctx -> :security/drop #write  
    :read_only_operation      ; Has only read
    
    ; Permissions restored when returning
}

!func :mixed_permissions = {
    ; Selective dropping in branches
    sensitive -> :if .{is_production} .{
        !ctx -> :security/drop #write
        :production_mode
    } .{
        :development_mode     ; Keeps all permissions
    }
}
```

## Security Patterns and Best Practices

The permission system enables several security patterns that promote safe code. The principle of least privilege guides permission usage - functions should require only the minimum permissions needed. Permissions should be dropped as soon as they're no longer needed, reducing the attack surface for downstream code.

```comp
!func :secure_pipeline ~{user_input} = {
    ; Validate with no permissions
    validated = user_input -> ^(:validate_pure)
    
    ; Read configuration with minimal permissions
    config = !ctx -> :security/only {#read} -> {
        :load_config
    }
    
    ; Process with required permissions only
    result = !ctx -> :security/only {#read #net} -> {
        validated -> :process_with_config config
    }
    
    ; Drop all permissions for logging
    ^(:log_result result)
}

; Audit permission usage
!func :audited_operation = {
    !ctx -> :security/on_drop .{permission}{
        "Permission dropped: ${permission}" -> :audit/log
    }
    
    ; Normal operations with audit trail
    :perform_operations
}
```

## Design Principles

The security system embodies several core principles. Capability-based design means permissions are unforgeable tokens, not strings or flags that can be manipulated. Monotonic reduction ensures permissions only decrease, never increase, along execution paths. Fail-fast behavior makes permission violations immediate and clear. Declarative requirements enable static analysis and documentation. Module isolation prevents supply chain attacks through permission boundaries.

These principles create a security model that balances safety with usability. Whether running trusted applications or sandboxing untrusted code, the permission system provides clear, enforceable boundaries that protect system resources while enabling necessary operations.