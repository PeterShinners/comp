# Handle Management System

*Design for Comp's capability-based handle lifecycle management*

## Overview

Handles are opaque runtime values that represent external objects requiring cleanup (file handles, network connections, database cursors, graphics contexts). Unlike tags (`#`) which are compile-time constants, handles exist at runtime and must be properly managed to ensure cleanup when no longer needed.

Handles use the `@` symbol to distinguish them from tags (`#`) and shapes (`~`). They are tracked automatically through frame-based reference counting and integrate seamlessly with the shape morphing system for type-safe dispatch.

## Key Principles

1. **Capability-Based**: Creating a handle requires a resource token that grants permission
2. **Type Identity**: Each handle has a specific type defined with `!handle`
3. **Automatic Cleanup**: Handles are automatically cleaned up when no frames reference them
4. **Immutability-Based Tracking**: Handle sets are cached on immutable Values
5. **Morph-Based Validation**: Released handles fail to morph, preventing usage after cleanup
6. **Frame Reference Counting**: Handles track which frames can reach them (not value-level reference counting)

## Handle Definition

Handles are defined at module level using `!handle`, similar to `!tag` and `!shape`:

```comp
!handle @filehandle
!handle @http.connection
!handle @database.cursor
```

Handles can be marked as module-private by adding a trailing `&` to the handle name (e.g., `!handle @session.token&`). Module-private handles are only accessible within the defining module and cannot be referenced by code in other modules. This enables modules to provide public APIs around effectful resources while keeping low-level handle types internal. See [Module Privacy and Visibility](module.md#module-privacy-and-visibility) for details.

Handle definitions establish:
- Handle type identity (for morphing and dispatch)
- Namespace scope (can be imported from other modules)
- Future: Cleanup hooks, transaction support, capability requirements

## Handle Creation

Handles are created by builtin functions that wrap Python objects:

```comp
!func |open-file ~{path~str} = {
    ; Python builtin creates @filehandle
    [path |py-open @filehandle]
}

!func |connect-db ~{url~str} = {
    ; Creates @connection handle
    [url |py-connect @connection]
}
```

The `@filehandle` parameter tells the builtin:
1. What handle type to create
2. Which HandleDefinition to attach
3. What cleanup callback to register

## Handle Usage

Functions specify required handle types in their input shape:

```comp
!func |read-file ~{@filehandle} = {
    ; Automatically fails if handle is released
    [$in |py-read]
}

!func |write-data ~{@filehandle data~str} = {
    ; Can combine handle with other fields
    [$in.data $in |py-write]
}

!func |query-db ~{@connection sql~str} = {
    [$in.sql $in.connection |py-query]
}
```

Handles in shapes work like tags - they eagerly match fields:

```comp
{handle=@filehandle path="file.txt"} ~{@filehandle path~str}
; Success - @filehandle field found, path is string
```

## Handle Lifecycle

### Frame-Based Reference Counting

Handles track which frames can reach them through bidirectional references:

```
Handle.frames ↔ Frame.handles
```

**Registration Process:**
1. When a Value containing handles is assigned to a scope variable, all handles in that Value are registered with the current frame
2. Registration adds the frame to each handle's `frames` set
3. Registration adds each handle to the frame's `handles` set

**Cleanup Process:**
1. When a frame drops (function returns, block exits), it unregisters all its handles
2. Unregistration removes the frame from each handle's `frames` set
3. If a handle's `frames` set becomes empty, cleanup is triggered

**Emergent Ownership:**
```comp
!func |process-file ~{path~str} = {
    ; Frame A creates handle
    handle = [path |open-file]           ; Handle registered with Frame A
    
    ; Frame A calls function, passing handle
    result = [handle |read-file]         ; Handle registered with Frame B (read-file's frame)
    
    ; Frame B exits                       ; Frame B unregisters
    ; (read-file returns)                 ; Handle still alive (Frame A holds it)
    
    [handle |close-file]                 ; Explicit close
}
; Frame A exits                          ; Frame A unregisters
; Handle.frames is empty                 ; Cleanup triggered automatically
```

### Immutability-Based Optimization

Since Values are immutable, handle sets can be computed once and cached:

```python
class Value:
    def __init__(self, data, ...):
        self.data = data
        # Compute and cache handles at creation
        self.handles: frozenset[Handle] | None = self._compute_handles()
    
    def _compute_handles(self) -> frozenset[Handle] | None:
        """Recursively find all handles in this value."""
        if isinstance(self.data, Handle):
            return frozenset([self.data])
        elif isinstance(self.data, Structure):
            # Recursively collect from all field values
            all_handles = set()
            for field_value in self.data.fields.values():
                if field_value.handles:
                    all_handles.update(field_value.handles)
            return frozenset(all_handles) if all_handles else None
        else:
            return None
```

**Benefits:**
- O(1) registration: just add frame to each handle in Value.handles
- No expensive recursive scans at registration time
- Handle set computed once at Value creation
- Immutability guarantees correctness

### Nested Handle Example

```comp
!func |open-both ~{path1~str path2~str} = {
    ; Create structure with two handles
    {
        a = [path1 |open-file]    ; @filehandle
        b = [path2 |open-file]    ; @filehandle
    }
}

result = ["file1.txt" "file2.txt" |open-both]
; result.handles = frozenset([handle_a, handle_b])
; Both handles registered with current frame
```

## Handle Release

Handles can be explicitly released before automatic cleanup:

```comp
!func |close-file ~{@filehandle} = {
    [$in |release]  ; Builtin function
}
```

The `|release` builtin:
1. Sets `handle.released = True`
2. Unregisters handle from all frames
3. Calls the cleanup callback
4. Released handles can no longer morph to their type

## Morphing Behavior

Resources integrate with the shape morphing system for type-safe dispatch:

### Active Resource Morphing

```comp
; Active resource matches its type
active_resource ~@filehandle     ; Success

; Structure containing resource
{handle=@filehandle path="file.txt"} ~{@filehandle path~str}
; Success - eager field matching finds @filehandle
```

### Released Resource Morphing

```comp
; Released resources fail to morph
[resource |close-file]
resource ~@filehandle    ; FAIL - resource has been released
```

This provides automatic safety:

```comp
!func |read-file ~{@filehandle} = { ... }

[handle |close-file]      ; Release resource
[handle |read-file]       ; Morph fails - function not called!
```

**No explicit checks needed** - the type system handles it automatically.

### Resource Type Checking

```comp
; Different resource types don't match
@filehandle ~@connection     ; FAIL - type mismatch
```

### Morph Rules Summary

1. **Type Matching**: Resource matches if types match exactly
2. **Released Check**: Released resources match nothing (like #fail)
3. **Eager Matching**: Resources eagerly match fields (like tags)
4. **Opaque Values**: Resources have no accessible internal structure

## Grammar Syntax

### Resource References

```lark
// Resource references use @ symbol
RESOURCE_AT: "@"
resource_reference: RESOURCE_AT reference_identifiers reference_namespace?
```

Examples:
- `@filehandle`
- `@http.connection`
- `@database.cursor/mydb`

### Resource Definitions

```lark
// Resource definitions at module level
BANG_RESOURCE: "!resource"
resource_definition: BANG_RESOURCE resource_path resource_body?
resource_path: RESOURCE_AT reference_identifiers
resource_body: LBRACE resource_option* RBRACE
```

Examples:
```comp
!resource @filehandle
!resource @connection
!resource @handle { ; Future: cleanup hooks, capabilities
    cleanup=|close-handle
    requires=@security.fileaccess
}
```

### Resources in Shapes

```lark
// In shape context
shape_type_atom: ...
    | resource_reference    // @filehandle as type

// In atom context  
atom: ...
    | resource_reference    // @handle as value
```

Examples:
```comp
!func |read ~{@filehandle} = { ... }         ; Input shape requires resource
!shape ~file = {@filehandle path~str}        ; Shape with resource field
```

## Implementation Classes

### Resource Runtime Value

```python
class Resource:
    """Runtime resource value."""
    
    resource_def: ResourceDefinition  # The @filehandle definition
    handle: object                     # Python object being wrapped
    cleanup: callable                  # Cleanup function to call
    frames: set[Frame]                # Which frames reference this
    released: bool                     # Has been released?
    
    def morph_to(self, shape):
        """Check if this resource matches a shape."""
        if self.released:
            return fail("Resource has been released")
        
        if isinstance(shape, ResourceRef):
            # Check if resource type matches
            if self.resource_def == shape.definition:
                return self  # Success
            return fail(f"Resource type mismatch")
        
        return fail("Resource cannot morph to non-resource shape")
    
    def release(self):
        """Explicitly release this resource."""
        if self.released:
            return
        
        self.released = True
        
        # Unregister from all frames
        for frame in list(self.frames):
            frame.resources.discard(self)
        self.frames.clear()
        
        # Call cleanup callback
        if self.cleanup:
            self.cleanup(self.handle)
```

### ResourceDefinition Entity

```python
class ResourceDefinition(Entity):
    """Resource type definition from !resource."""
    
    path: list[str]              # ["filehandle"] or ["http", "connection"]
    namespace: str | None        # Module namespace
    cleanup_hook: callable | None  # Optional default cleanup
    
    # Future: transaction support, capability requirements
```

### ResourceRef AST Node

```python
class ResourceRef(BaseRef):
    """Resource reference in AST: @filehandle"""
    
    SYMBOL = "@"
    path: list[str]
    namespace: str | None
    definition: ResourceDefinition | None  # Resolved reference
```

### Value Integration

```python
class Value:
    """Immutable value with cached resource set."""
    
    def __init__(self, data, ...):
        self.data = data
        self.resources: frozenset[Resource] | None = self._compute_resources()
    
    def _compute_resources(self) -> frozenset[Resource] | None:
        """Recursively collect all resources in this value."""
        # Implementation shown in Immutability-Based Optimization section
        ...
```

### Frame Integration

```python
class Frame:
    """Execution frame with resource tracking."""
    
    def __init__(self, ...):
        self.resources: set[Resource] = set()  # Resources reachable from this frame
        ...
    
    def register_value(self, value: Value):
        """Register all resources in a value with this frame."""
        if value.resources:
            for resource in value.resources:
                self.resources.add(resource)
                resource.frames.add(self)
    
    def cleanup_resources(self):
        """Cleanup resources when frame drops."""
        for resource in list(self.resources):
            resource.frames.discard(self)
            
            # If no more frames reference it, cleanup
            if not resource.frames:
                resource.release()
        
        self.resources.clear()
```

## Registration Points

Resources need to be registered at these evaluation points:

1. **Scope Assignments**: `$var = value` → register value with current frame
2. **Function Arguments**: When value passed as argument → register with callee frame
3. **Function Returns**: When returning value → register with caller frame
4. **Structure Fields**: Resources in structure fields registered when structure registered
5. **Block Captures**: Variables captured in blocks → register with block's frame

## Standard Library Functions

```comp
!import /resource = std "core/resource"

; Check resource state
[resource |is-released/resource]    ; Returns #true or #false
[resource |frames/resource]         ; Returns count of frames holding resource

; Manual management
[resource |release]                 ; Explicitly release resource
[resource |try-release]             ; Release if last frame (no-op otherwise)

; Debugging
[resource |type/resource]           ; Returns resource type reference
[resource |handle-id/resource]      ; Returns internal handle identifier
```

## Transaction Support (Future)

Resources can participate in transaction boundaries:

```comp
!func |with-transaction ~{@connection block~:{}} = {
    [connection |begin-transaction]
    
    result = [block |try {:{ $in }} {
        ; Success path
        [connection |commit]
        result=#success
    } {
        ; Failure path  
        [connection |rollback]
        result=#error
    }]
}
```

Transaction coordination with multiple resources:

```comp
; Multiple coordinated resources
!transact @database @cache @search {
    $var.user-id = [user @database |insert |get-id]
    [user @cache |set %"user:%{$var.user-id}"]
    [user @search |index "users"]
}
; All three systems update atomically
```

## Comparison with Tags

| Aspect | Tags (#) | Resources (@) |
|--------|----------|---------------|
| **Nature** | Compile-time constants | Runtime values |
| **Lifecycle** | Static, no cleanup | Managed, cleanup required |
| **Identity** | Hierarchical enumerations | Opaque external handles |
| **Morphing** | Type-level dispatch | Type + state validation |
| **Mutability** | Immutable by nature | State changes (released flag) |
| **Usage** | Error codes, enums, flags | File handles, connections |

## Design Benefits

1. **Safety**: Morph system prevents use of released resources
2. **Simplicity**: No explicit ownership tracking - emergent from frame references
3. **Performance**: Immutability enables O(k) registration, not O(depth) scanning
4. **Clarity**: `@` symbol clearly distinguishes resources from tags and shapes
5. **Flexibility**: Works with nested resources in structures
6. **Automatic**: Cleanup happens automatically when frames drop

## Migration Path

**Phase 1: Grammar and AST**
- Add `@` symbol support to grammar
- Add `!resource` definitions
- Add `ResourceRef` AST nodes
- Pattern after existing `TagRef` implementation

**Phase 2: Runtime Values**
- Implement `Resource` class with morph_to method
- Add resource creation builtins
- Implement morph checking for resources
- Test basic resource creation and morphing

**Phase 3: Frame Integration**
- Add `Frame.resources` set
- Add `Value.resources` frozenset
- Implement registration at key points (assignments, returns)
- Test frame cleanup

**Phase 4: Cleanup System**
- Implement frame cleanup on drop
- Add `|release` builtin
- Test nested resources in structures
- Test emergent ownership scenarios

**Phase 5: Standard Library**
- Create `resource/` module
- Add inspection functions
- Add manual management tools
- Document patterns

## Related Design Documents

- `design/tag.md` - Tag system comparison and hierarchical enumerations
- `design/shape.md` - Shape morphing system and type dispatch
- `design/function.md` - Function dispatch and morphing integration
- `design/type.md` - Type system integration
- `design/module.md` - Cross-module resource imports

