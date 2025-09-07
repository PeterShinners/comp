## Comp Language Changes and Clarifications

### 1. Pure Functions (formerly `!block`)
**Change**: Renamed from `!block` to `!pure` for clarity

```comp
!pure :validate_email ~{email ~string} = {
    // Gets empty .ctx - no security tokens, no permissions
    email -> :string:match pattern  // OK: pure computation
    email -> :file:read              // FAILS: no permissions
}
```

**Key clarification**: `!pure` functions receive completely empty `.ctx` regardless of caller's permissions. This enables:
- Compile-time evaluation (including unit conversions)
- Parallel execution without locks
- Caching/memoization
- Safe execution of user-provided code

### 2. Function Blocks (formerly overloaded with `!block`)
**Clarification**: Blocks are unexecuted code passed to functions, NOT restricted functions

```comp
!func :url:dispatch ~{parsed_url} blocks={...routes} = {
    // Blocks execute with caller's full permissions when invoked
}

// Usage:
url -> :url:dispatch
    ."/favicon*" {:cloudflare:response_not_found}  // Full permissions
    ."/insert" {:insert_vectors}                    // Full permissions
    .else {:query_vectors}                          // Full permissions
```

**Important**: Function blocks run with whatever permissions the caller has at execution time, not with restricted permissions.

### 3. Resource Definition Syntax
**Change**: New block-based syntax for resource definitions

```comp
!resource %database_cursor {#thread#affinity.current}
    .release {cursor -> :db:close}
    .transact_begin {cursor -> :db:begin_transaction}
    .transact_commit {cursor -> :db:commit}
    .transact_rollback {cursor -> :db:rollback}

!resource %file_handle {}
    .release {handle -> :fs:close}
```

**Key points**:
- Initial struct `{}` holds resource metadata/tags
- Block names are language-defined (not arbitrary)
- Blocks are callbacks the runtime controls
- `.release` is typically required
- Transaction blocks match `!transact` operator naming

### 4. Permission Decorators
**New**: `!require` for declaring function permissions (replacing decorator-style approach)

```comp
!require threading
!func :process_parallel ~{data} = {
    // Can use threading
}

!require {}  // Alternative way to drop all permissions
!func :safe_compute = {
    // Similar to !pure but using decorator pattern
}
```

### 5. Entry Points
**Decision**: Only two language-defined entry points

```comp
!entry = {
    // Module initialization - runs on import
}

!main = {
    // Program execution entry point
}
```

**Rejected**: `!test`, `!docs`, `!debug`, `!commandline`, `!gui` - these should be conventions or framework concerns, not language features.

### 6. Binding Contexts
**Clarification**: Field assignment creates bindings in `.out` scope

```comp
x=2 y=x  // Creates x in .out, then y can reference it
```

The `.out` scope is the most significant layer in the resolution stack, allowing immediate reference to newly created fields.

### 7. Shape Spreading in Definitions
**Clarification**: Shape definitions can use spread operator with special rules

```comp
!shape ~Point3d = {...~Point2d z ~number = 0}
```

**Rules**:
- No weak/strong variants (unlike value spreading)
- Field name conflicts are compile-time errors
- Allows multiple shape composition
- Controls field ordering

### 8. Shape Spreading in Function Parameters
**New insight**: Can use shape spreading in function signatures

```comp
!func :analyze ~{...~RawData complexity ~number=0} = {
    // Has all RawData fields plus complexity
}

// Usage:
:load_raw_data ..> {complexity=7} -> :analyze
```

This creates compile-time checked extended parameters without defining new shapes.

### 9. Optional Type Syntax
**Confirmed**: Use `~Type|~nil` instead of `?` for optionals

```comp
!shape ~TreeNode = {
    value ~number
    left ~TreeNode|~nil = {}
    right ~TreeNode|~nil = {}
}
```

- `~nil` is a built-in global shape (like `~string`, `~number`)
- Each union component needs its tilde: `~Type|~nil` not `Type|nil`
- Type aliases can simplify: `!shape ~OptionalTree = ~TreeNode|~nil`

### 10. Security Token Behavior
**Clarification**: Security tokens in `.ctx`:
- Cannot be stored, assigned, or referenced directly
- Only operations: check existence and drop permissions
- Resources are tagged with required tokens at creation
- Tokens prevent both creation AND access to resources
- `!pure` functions get empty `.ctx` (no tokens at all)

These changes establish clearer separation between:
- **`!pure`**: Compile-time safe, no side effects
- **`!func`**: Regular functions with controlled permissions
- **blocks**: Unexecuted code passed as parameters
- **`!resource`**: Resource definitions with lifecycle callbacks