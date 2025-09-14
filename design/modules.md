# Modules, Imports, Namespaces, and Entry Points

*Design for Comp's module system, import mechanisms, namespace management, and program entry points*

## Overview

Comp provides a flexible module system with multiple import providers, hierarchical namespace management, and clear entry point definitions. The system emphasizes security, explicit dependencies, and static analyzability while supporting diverse source types.

## Module System Architecture

### Modules as Namespaces

**Core Principle**: Modules are namespaces, not assignable values.

```comp
!import json = std "json"

; Correct usage - module as namespace
data -> json:stringify -> json:parse

; Invalid - modules are not values
$json_lib = json              ; ERROR: Cannot assign module to variable
data -> $json_lib:stringify   ; ERROR: Module not a value
```

**Benefits**:
- Clear distinction between modules and data
- Prevents confusion about module lifecycle
- Enables static analysis and tooling
- Consistent with namespace-oriented design

### Single Source of Truth Architecture

**Main Module Controls All Dependencies**:
- Main module has ultimate authority over all versions
- No hidden dependency sharing between libraries
- Clear, analyzable dependency tree
- Explicit version management

```comp
; Main module controls all versions
!main = {
    ; Override specific versions for entire application
    !import json *= pkg "json@2.5.1"        ; Force specific version
    !import database *= pkg "postgres@3.2"   ; Application-wide database version
    
    ; Libraries automatically use these versions
    .user_service:process_users
    .data_processor:transform_data
}
```

### Dependency Injection Through Main Override

Libraries automatically inherit main module's dependency choices:

```comp
; user_service.comp - Library module
!import json = std "json"           ; Default: standard library JSON
!import database = std "database"   ; Default: standard library database

; main.comp - Application
!import json *= pkg "fast-json@3.1"     ; Override with faster JSON library  
!import database *= pkg "postgres@3.2"  ; Override with PostgreSQL driver
!import user_service = comp "./user_service.comp"

; user_service automatically uses fast-json@3.1 and postgres@3.2
```

### Explicit Version Management

**No Version Ranges or Lock Files**:
- All versions specified exactly in source code
- Tools can analyze and update versions by parsing source
- No hidden state in external lock files
- Clear audit trail of version changes

```comp
; Explicit, analyzable versions
!import json = pkg "json@2.5.1"           ; Exact version
!import utils = git "github.com/org/utils@v1.4.2"  ; Git tag
!import api = openapi "https:;api.example.com/v2/spec.json"  ; URL with version

; Tools can parse and update these automatically
```

### Dynamic Module System

The dynamic module system maintains static safety through a **construction-time dynamic, runtime static** approach:
- Modules can be built programmatically at runtime
- Once sealed, they behave exactly like statically imported modules
- Full type safety and performance maintained

### Three-Tier Flexibility

**1. Automatic Import Translation (90% of cases)**
```comp
; Transparent imports via specialized importers
!import api = "openapi:;./swagger.json"
!import db = "postgres:;localhost/mydb?schema=public"
!import py_utils = "python:;./utils.py"
!import proto = "protobuf:;./messages.proto"

; Use normally with full type safety
api.users.get({id=123})
db.User.findById(123)
```

**2. Module Builder Pattern (9% of cases)**
```comp
; For custom scenarios beyond importer capabilities
builder = :module_builder.new()
builder -> :add_function("connect", connect_impl)
builder -> :add_shape("User", user_shape)
database_mod = builder -> !seal  ; Now immutable

; Works exactly like static import
database_mod.connect() -> database_mod.query("SELECT * FROM users")
```

**3. Manual Construction (1% of cases)**
```comp
; Full control for edge cases
user_shape = :compile_shape({name: "string", age: "number"})
validator_func = :compile_function("validate_user", user_shape, logic)

builder -> :add_shape("User", user_shape)
       -> :add_function("validate", validator_func)
       -> !seal -> user_module
```

### Intelligent Caching

Import providers implement appropriate caching strategies:

**HTTP-based importers:** ETag + Last-Modified headers
**Database importers:** Schema version + table timestamps  
**File-based importers:** File mtime + content hash

**Cache Integration:**
- Source cache: Raw downloaded/accessed content
- Translation cache: Converted Comp module definitions
- Runtime cache: Compiled/optimized module instances

**Key Benefits:**
- **Flexibility without chaos:** Multiple pathways to achieve dynamic behavior
- **Performance:** Sealed modules perform identically to static imports
- **Type safety:** Full type checking maintained even for runtime-built modules
- **Familiarity:** Builder pattern and import syntax feel natural
- **Optimization:** Intelligent caching makes repeated access fast

**Use Cases:**
- **Configuration-driven modules:** Build database connections from runtime config
- **Plugin systems:** Dynamically discover and load plugins
- **Code generation:** Generate API clients from external schemas
- **Schema reflection:** Create modules from database schemas or external APIs

## Import Statement Syntax

### Core Import Syntax

```comp
!import name = source "specifier"
```

**Components**:
- **name**: Module name (becomes namespace)
- **source**: Unquoted token (`std`, `pkg`, `comp`, `git`, `python`, `openapi`, `main`)
- **specifier**: Quoted string (allows interpolation)

### Standard Library and Package Imports

```comp
!import json = std "json"
!import http = std "http/client"  
!import math = std "math/geometry"

; Package manager with exact versions
!import json = pkg "json@2.5.1"
!import database = pkg "postgres-driver@1.8.3"
```

### External Repository and File Imports

```comp
; Git repository modules
!import utils = git "github.com/company/utils@v1.4.2"
!import crypto = git "gitlab.com/security/crypto@main"

; Local Comp files
!import config = comp "./config.comp"
!import shared = comp "../shared/utilities.comp"
!import remote = comp "https:;cdn.example.com/module.comp"
```

### Foreign Language and Schema Imports

```comp
; External schema integration
!import api = openapi "https:;api.service.com/spec.json"
!import events = protobuf "./schema.proto"

; Python runtime integration
!import numpy = python "numpy"
!import pygame = python "pygame"
```

### Automatic Main Override System

**Key Innovation**: Libraries write simple imports that are automatically overridable by the main module:

```comp
; Library writes:
!import json = std "json"

; Automatically behaves as:
!import json = main "json" | std "json"  ; Try main first, fallback to std
```

**Benefits**:
- Libraries work standalone with reasonable defaults
- Applications can override any dependency
- No complex dependency injection syntax required
- Clear single source of truth for versions

### Assignment Operators for Import Control

```comp
!import json = std "json"      ; Normal: main can override
!import json *= std "json"     ; Strong: always use this exact version
!import json ?= std "json"     ; Weak: only if not already provided  
!import json = main "json"     ; Explicit: must be provided by main module
```

**Assignment Semantics**:
- `=` - Normal assignment with automatic main override
- `*=` - Strong assignment prevents main override
- `?=` - Weak assignment, skipped if already imported
- Direct `main` source requires explicit provision

### Fallback Chain Syntax

```comp
; Multiple fallback sources using | operator
!import json = main "json" | std "json" | comp "./minimal-json.comp"

; Complex fallback with version preferences
!import database = main "database" | pkg "postgres@2.1" | pkg "sqlite@3.8"

; Platform-specific fallbacks
!import graphics = main "graphics" | pkg "opengl@4.6" | pkg "software-renderer@1.0"
```

Uses existing `|` operator for consistency with field fallback behavior.

## Module Usage Patterns

### Function Invocation

```comp
; Local function calls
result -> :local_function

; Imported module functions  
result -> io:write
data -> math:sqrt -> color:to_hex

; Qualified calls prevent naming conflicts
user_data -> validation:check_email
user_data -> http:check_email    ; Different validation logic
```

## Module Usage Patterns

### Function Invocation

```comp
; Local function calls
result -> :local_function

; Imported module functions  
result -> json:stringify -> json:parse
data -> math:sqrt -> http:post
user -> database:save

; Qualified calls prevent naming conflicts
user_data -> auth:validate_email     ; Authentication validation
user_data -> forms:validate_email    ; Form validation
```

### Cross-Module Shape and Tag Usage

```comp
; Shapes from imported modules
user_data ~ auth:UserProfile
config ~ settings:AppConfig

; Tags from imported modules  
status = .http#response#success
priority = .tasks#priority#high

; Cross-module compatibility
local_user ~ auth:UserProfile     ; Works if shapes are structurally compatible
auth_status = #status#active      ; Local tag
http_status = .http#status#200     ; Module-qualified tag
```

### Module Namespace Integration

```comp
; Modules integrate with namespace system
@app.database_url = database:get_default_url
@mod.json_config = json:parse config_text

; Module functions can access application context
user -> database:save -> {
    ; database module can access @app.connection_pool
    @app.audit_log = {...@app.audit_log, user_saved=@}
}
```

**Standalone Libraries with Defaults**:
```comp
; library.comp - Works standalone
!import json = std "json"           ; Reasonable default
!import http = std "http"           ; Standard HTTP client
!import math = std "math"           ; Built-in math functions

!func :process_api_data ~{url ~str} = {
    url -> http:get -> json:parse -> math:analyze
}
```

**Application Override**:
```comp
; app.comp - Application with specific requirements  
!import json *= pkg "fast-json@3.1"      ; High-performance JSON
!import http *= pkg "secure-http@2.0"    ; Security-focused HTTP
!import library = comp "./library.comp"  ; Library inherits overrides

; library functions now use fast-json@3.1 and secure-http@2.0
```

**Conditional Library Imports**:
```comp
; library.comp - Flexible library
!import json = std "json"                 ; Default
!import encryption ?= main "encryption"  ; Optional if provided by main
!import cache ?= std "cache"             ; Optional with standard fallback

!func :secure_process ~{data} = {
    processed = data -> json:parse
    encrypted = encryption ? (processed -> encryption:encrypt) | processed
    encrypted -> cache:store | processed  ; Cache if available
}
```

## Namespace System

### Hierarchical Namespace Access

```comp
@app.config         ; Application-level configuration
@mod.state          ; Module-level state
@env.production     ; Environment settings  
@ctx.security       ; Context-specific data
@in.data           ; Input context
@out.result        ; Output context
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
    $func.start_time = .time:now
    
    data -> :transform -> :validate
}  ; $func namespace cleared here
```

### Context Stack Hierarchy

**Resolution Order**: `$func` → `@mod` → `@app` → `@env`

```comp
; Setting values at different levels
@env.database_url = "postgres:;prod"      ; Environment
@app.max_connections = 100                 ; Application  
@mod.table_prefix = "user_"               ; Module
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
.threading:spawn {
    ; This thread has independent copy of @app and @ctx
    ; Changes here don't affect parent or sibling threads
    @ctx.processing_mode = "streaming"    ; Local to this thread
}

; Main thread unchanged
@ctx.processing_mode    ; Still "batch"
```

## Security and Permission Integration

### Module-Level Permissions

```comp
; Module declares required permissions
!require read, write, net

; Functions inherit module permissions
!func :fetch_and_save ~{url ~str} = {
    url -> .http:get -> .file:write "output.json"
}

; Permission restriction within module
!func :safe_compute = {
    @ctx -> .security:drop #net        ; Drop network access
    @ctx -> .security:drop #write      ; Drop write access
    data -> :pure_calculation
}
```

### Cross-Module Permission Flow

Each imported module gets isolated security context:

```comp
; Main module has full permissions
!require read, write, net

; Import with permission restriction
!import sandboxed = comp ./untrusted_module
; sandboxed module cannot access main module's permissions

; Explicit permission delegation (if supported)
sandboxed -> :restricted_function {
    permissions = {#read}    ; Delegate only read permission
}
```

### External Schema Security

External schemas are naturally sandboxed by format limitations:

```comp
!import api = openapi ./external-api.json
; Can only create HTTP client functions - no arbitrary code execution

!import data = protobuf ./schema.proto  
; Can only create serialization functions - no system access
```

## Entry Points

### Module Entry Points

```comp
!entry = {
    ; Module initialization - runs when imported
    @mod.initialized = !true
    @mod.version = "1.2.3" 
    :setup_module_state
}

!main = {
    ; Program execution entry point
    $args = .cli:parse_args
    $config = .config:load $args.config_file
    
    $args.command -> :match {
        "serve" -> :start_server $config
        "migrate" -> :run_migrations $config  
        "test" -> :run_tests
        else -> :show_help
    }
}
```



## Advanced Import Features

### Versioning and Dependencies

```comp
; Git-based versioning
!import utils = git @company/utils@1.4.2
!import experimental = git @company/utils@feature-branch

; Semantic version constraints (future feature)
!import compat = git @org/lib@^2.1.0    ; Compatible with 2.x
!import stable = git @org/lib@~1.2.3    ; Patch-level updates only
```

### Import Aliases and Renaming

```comp
; Alias module name
!import ui = git @company/user-interface@latest
!import db = stdlib database/postgresql

; Selective imports (future feature)
!import {hash_password, verify_password} = stdlib crypto/bcrypt
!import {Point2d as Point, Vector3d} = math geometry
```

### Conditional and Platform Imports

```comp
; Platform-specific imports
!import graphics = disk deps/basic-graphics
!import graphics.linux ?= path hardware-accelerated-linux
!import graphics.windows ?= path directx-graphics
!import graphics.macos ?= path metal-graphics

; Environment-based imports
!import database = stdlib database/sqlite       ; Development default
!import database.production ?= stdlib database/postgresql
```

## Runtime Module Management

### Module Introspection

```comp
; Query module information
!describe io -> {
    name = @.name           ; "io"
    version = @.version     ; "1.0.0"
    functions = @.functions ; List of available functions
    source = @.source       ; Import source information
}

; List all imported modules
@app.modules => {name=name, source=source} -> .debug:print
```

### Dynamic Module Loading

```comp
; Runtime module loading (requires import permission)
!require import
!func :load_plugin ~{name ~str} = {
    ; Dynamic import syntax (future feature)
    $plugin = !import_runtime plugin = path "plugins/${name}"
    $plugin -> :initialize
}

; Module builder pattern for runtime construction
!func :build_database_module ~{config ~{host ~str, port ~num}} = {
    builder = :module_builder.new()
    
    ; Add connection function
    connect_impl = :compile_function("connect", {}, {
        $func.host = config.host
        $func.port = config.port
        .database:connect {$func.host, $func.port}
    })
    
    ; Add query functions
    query_impl = :compile_function("query", {sql ~str}, {
        $func.connection -> :execute sql
    })
    
    ; Seal and return immutable module
    builder -> :add_function("connect", connect_impl)
           -> :add_function("query", query_impl)
           -> !seal
}

; Usage - works exactly like static import
$db_module = :build_database_module {host="localhost", port=5432}
$db_module.connect() -> $db_module.query("SELECT * FROM users")
```

### Module Caching and Reloading

```comp
; Module caching behavior (implementation detail)
; - Git modules: Cached by commit hash
; - Filesystem modules: Cached by modification time  
; - HTTP modules: Cached with HTTP cache headers
; - Python modules: Follow Python import caching
; - Database modules: Schema version + table timestamps
; - OpenAPI modules: ETag + Last-Modified headers

; Cache layers for optimal performance:
; 1. Source cache: Raw downloaded/accessed content
; 2. Translation cache: Converted Comp module definitions  
; 3. Runtime cache: Compiled/optimized module instances

; Explicit cache control (development feature)
!import utils = git @company/utils@latest !no-cache
!import config = disk ./config.comp !reload-on-change
!import api = openapi "https:;api.service.com/spec.json" !cache-timeout=3600
```

## Integration Examples

### Application Dependency Management

```comp
; main.comp - Application with centralized dependency control
!main = {
    ; Force specific versions for entire application
    !import json *= pkg "json@2.5.1"
    !import database *= pkg "postgres@3.2.1" 
    !import cache *= pkg "redis@4.1"
    !import logging *= pkg "structured-logs@1.8"
    
    ; Import application modules (inherit dependency versions)
    !import user_service = comp "./services/users.comp"
    !import data_processor = comp "./processors/data.comp"
    !import api_handlers = comp "./api/handlers.comp"
    
    ; Application logic
    .api_handlers:start_server {port=8080}
}
```

### Multi-Service Dependency Coordination

```comp
; services/users.comp
!import database = std "database"    ; Default, overridable
!import cache = std "cache"          ; Default, overridable  
!import json = std "json"            ; Default, overridable

!func :get_user ~{id ~str} = {
    ; Check cache first
    cached = id -> cache:get "user:${id}" | {}
    cached ? cached | {
        ; Load from database  
        id -> database:query "SELECT * FROM users WHERE id = $1"
        -> json:serialize
        -> cache:set "user:${id}" {ttl=300}
    }
}

; services/billing.comp  
!import database = std "database"    ; Same defaults
!import json = std "json"            ; Same defaults
!import payment = std "payment"      ; Payment processing

; main.comp coordinates all versions
!import database *= pkg "postgres@3.2.1"  ; All services use same DB version
!import json *= pkg "fast-json@3.1"       ; All services use same JSON library
!import user_service = comp "./services/users.comp"
!import billing_service = comp "./services/billing.comp"
```

### Platform-Specific Module Selection

```comp
; graphics.comp - Cross-platform graphics library
!import renderer = main "renderer" | std "software-renderer"

; main-linux.comp
!import renderer *= pkg "opengl@4.6"
!import graphics = comp "./graphics.comp"

; main-windows.comp  
!import renderer *= pkg "directx@12"
!import graphics = comp "./graphics.comp"

; main-web.comp
!import renderer *= pkg "webgl@2.0" 
!import graphics = comp "./graphics.comp"
```


## Platform-Specific Definitions

Functions and shapes can have platform variants:

```comp
; Generic definition
!func :file_open ~{path ~str} = {
    path -> .posix:open
}

; Windows-specific override
!func :file_open.win32 ~{path ~str} = {
    path -> .win32:CreateFile
}

; ARM64-specific buffer layout
!shape ~buffer.arm64 = {
    data ~bytes
    alignment ~num = 8
}
```

**Resolution Order**: `func.platform.arch` → `func.platform` → `func`

### Cross-Module Tag Usage

```comp
; In module A
!tag #priority = {low, medium, high, critical}

; In module B  
!import prioritymod = comp ./priority_module

; Usage - values are interchangeable
local_priority = #priority#high
imported_priority = .prioritymod#priority#high
same_value = local_priority == imported_priority    ; #true
```

### Tag Aliasing and Extension

```comp
; Import and extend
!tag #my_priorities = {
    ..external#priority        ; Import all values
    urgent = .external#priority#critical    ; Alias existing
    emergency = {escalate=#true}           ; Add new
}

; Values remain interchangeable
#my_priorities#urgent == .external#priority#critical    ; #true
```



### Development vs Production Configuration

```comp
; app.comp - Application module  
!import database = std "database"
!import logging = std "logging"
!import cache = std "cache"

; main-development.comp
!import database *= pkg "sqlite@3.8"          ; Lightweight for dev
!import logging *= pkg "console-logs@1.0"     ; Console output
!import cache *= pkg "memory-cache@2.1"       ; In-memory cache
!import app = comp "./app.comp"

; main-production.comp
!import database *= pkg "postgres@3.2.1"      ; Production database
!import logging *= pkg "structured-logs@1.8"  ; Structured logging
!import cache *= pkg "redis@4.1"              ; Redis cache
!import app = comp "./app.comp"
```


### Stable Module Identifiers

The module system generates **deterministic, portable identifiers** for dependencies that remain consistent across machines and environments.

**Identifier Generation Strategy:**
- Base identifier on package name + namespace/owner + version
- `colorlib_studio_v1` → `github.com/studio/colorlib@v1.0`
- Import providers suggest tiered specificity: preferred → scoped → versioned → canonical → collision_token

**Developer Tools:**
```bash
# Discover available module identifiers
comp module identifiers "*color*"
# Found: colorlib_studio_v1 → github.com/studio/colorlib@v1.0

# Override dependencies at runtime
comp run file.comp --override colorlib_studio_v1=./my-local-colors
comp run file.comp --override colorlib_studio_v1=github:;user/altcolorlib@1.2
```

### Static Packaging System

**Bundle Creation:**
```bash
comp staticpackage file.comp
# Creates: file.comp.bundle (self-contained archive)
```

**Bundle Usage:**
```bash
# Auto-discovery - uses bundle if found
comp run file.comp

# Manual control
comp run file.comp --bundle=./custom.bundle
comp run file.comp --no-bundle
comp run file.comp --validate-bundle
```

**Benefits:**
- Self-contained deployment artifacts
- No external dependencies in production
- Consistent execution across environments
- Verifiable and cacheable distribution


## Implementation Priorities

1. **Core Import Syntax**: Source tokens, specifiers, assignment operators
2. **Automatic Main Override**: Default behavior for library compatibility
3. **Stable Module Identifiers**: Deterministic, portable dependency identifiers
4. **Static Packaging System**: Self-contained bundle creation and deployment
5. **Standard Library Integration**: Built-in module loading with `std` source
6. **Package Manager Integration**: Exact version specification with `pkg` source
7. **Fallback Chain Processing**: Multiple source resolution with `|` operator
8. **Dynamic Module Builder**: Runtime module construction with builder pattern
9. **Intelligent Caching**: Multi-layer caching with provider-specific strategies
10. **Git Repository Support**: Remote repository loading with version/tag specification
11. **External Schema Integration**: OpenAPI, Protocol Buffers, and foreign language imports

## Key Design Principles

### Construction-Time Dynamic, Runtime Static

The dynamic module system provides a "pit of success" where:
- **Common cases are trivial**: Standard imports work transparently
- **Edge cases are possible**: Builder pattern available for complex scenarios  
- **Type system remains intact**: Full type checking maintained throughout
- **Performance is preserved**: Sealed modules perform identically to static imports

### Flexibility without Chaos

Multiple pathways to achieve dynamic behavior:
- **90% of cases**: Automatic import translation via specialized importers
- **9% of cases**: Module builder pattern for custom construction
- **1% of cases**: Manual compilation for complete control

### Developer-Friendly Tooling

Built-in tools support the complete module lifecycle:
- Module identifier discovery and resolution
- Static packaging for deployment
- Runtime dependency override for development
- Cache management and invalidation
- Bundle validation and verification

## Key Design Changes from Earlier Versions

### Design Principles Evolution
1. **Libraries are both standalone AND composable**: Default behavior handles both cases
2. **Single source of truth**: Main module controls all dependency versions  
3. **Explicit over implicit**: All versions visible in source code
4. **Minimal syntax burden**: Common case (automatic override) requires no special syntax
5. **Clear dependency trees**: Tools can analyze complete dependency graph from source
