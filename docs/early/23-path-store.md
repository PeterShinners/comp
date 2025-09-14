# Path System for Comp Language

## Overview

Comp introduces a path system that provides both simple field navigation and complex data querying. Paths are first-class values that can be stored, passed, and composed. The system uses slash delimiters (`/path/`) with dot-separated segments inside, creating a clear visual distinction from direct field access.

## Core Concepts

### Path Literals
Paths are delimited by forward slashes with dots separating internal segments:

```comp
/users.profile.theme/          ; Path literal value
data//users.profile.theme/     ; Apply path to data
$path = /config.database.host/ ; Store path in variable
```

### Direct Access vs Path Access
The system distinguishes between compile-time field access and runtime path application:

```comp
; Direct field access (immediate, compile-time)
config.database.host

; Path-based access (dynamic, runtime)
config//database.host/
config/$db_path
```

### Path Operations

```comp
; Get value at path
data//users.profile.name/

; Set value at path  
data//users.profile.name/ = "Alice"

; Store and use paths
$path = /users.profile.email/
value = data/$path
data/$path = "new@example.com"
```

## Basic Selectors

### Wildcard (`*`)
Matches any single element at that position:

```comp
data//users.*.email/           ; All user emails
data//servers.*.ports.*/       ; All ports on all servers
```

### Recursive Descent (`**`)
Searches at any depth below the current position:

```comp
data//**.error/                ; Find all error fields anywhere
data//logs.**.message/         ; All messages under logs at any depth
```

### Array Indexing (`#`)
Access array elements by index:

```comp
data//users#0/                 ; First user
data//items#-1/                ; Last item  
data//matrix#5#3/              ; Matrix row 5, column 3
```

## Path Composition

Paths can be joined and extended naturally:

```comp
; Variable chaining
$base = /api.v2/
$resource = /users/
data/$base/$resource/profile/

; Path extension
$path = /config/
$extended = $path//database.host/     ; Results in /config.database.host/

; Multiple segments
$p1 = /users/
$p2 = /profile/  
$p3 = /settings/
data/$p1/$p2/$p3               ; Accesses users.profile.settings
```

## Complex Operations via Functions

More sophisticated queries use library functions:

```comp
; Multiple selection with patterns
{data /users.*.email/} -> :path:fetchall

; Bulk updates
{data /users.*.active/ false} -> :path:applyall

; Testing and queries
{data /users.admin.role/} -> :path:exists?
{data /**.error/} -> :path:hasany?

; Path manipulation
{/api.v2/ /users/} -> :path:join
/users.profile.theme/ -> :path:parent    ; Returns /users.profile/
```

## Comments

The path syntax requires a new comment character since `//` is now used for path operations. Semicolon serves this purpose:

```comp
; This is a comment
data//users.profile/           ; Get user profile
config//database.host/ = "localhost"  ; Set database host
```

## Future Extensions

The system is designed to grow into more sophisticated querying:

### Predicates (Planned)
```comp
data//users[age > 18].email/
data//items[price < 100 & instock]/
```

### Computed Fields (Planned)
```comp
data//config.'theme_${env}'/
data//crowd.'name -> :str:lowercase'/
```

### Additional Selectors (Planned)
```comp
data//users:first/              ; Pseudo-selectors
data//*:type(string)/           ; Type matching
/config.(dev|prod).host/        ; Union selection
```

## Design Principles

1. **Clear Visual Separation**: The `//` operator clearly distinguishes where data reference ends and path begins
2. **Familiar Syntax**: Dot notation inside paths matches traditional field access patterns
3. **Composability**: Paths can be stored, passed, and combined naturally
4. **Progressive Complexity**: Simple cases are simple; complex operations use explicit functions
5. **Type Safety**: Path operations are checked by the type system, preventing invalid operations

## Example Usage

```comp
; Configuration management
$env = "production"
config//servers.$env.host/

; User data access
$user_id = "12345"
name = users//users.$user_id.name/
email = users//users.$user_id.email/
users//users.$user_id.last_login/ = timestamp()

; Building API paths
$api = /api.v2/
$endpoint = $api//users.current/
response = fetch(service/$endpoint)

; Data exploration
all_errors = {logs /**.error/} -> :path:fetchall
error_count = {logs /**.error/} -> :path:countmatches
```

# Store System for Comp Language

## Overview

The Store provides controlled mutable state in Comp's otherwise immutable environment. Rather than allowing individual mutable structures, all mutable data lives in Store containers that are accessed through explicit operations. This creates a clear boundary between immutable and mutable worlds, making programs easier to reason about.

## Core Concept

```comp
; Create a store - the ONE mutable container
$store = :store:new {
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
$parent = $cursor -> :cursor:up            ; Go to /users/
$child = {$cursor /profile/} -> :cursor:down  ; Go to /users.123.profile/
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
{$store /users.*.email/} -> :path:fetchall  ; All emails
{$store /users[active]/} -> :path:query     ; Active users
{$store /**.error/} -> :path:hasany?        ; Any errors?
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
$test_store = :store:new {users={} config=default_config}
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

