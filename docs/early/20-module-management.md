# Comp Language: Module System Design

## Dependency Packaging & Override System

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
comp run file.comp --override colorlib_studio_v1=github://user/altcolorlib@1.2
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

## Dynamic Module System

### Design Philosophy

Dynamic modules maintain static safety through a **construction-time dynamic, runtime static** approach:
- Modules can be built programmatically at runtime
- Once sealed, they behave exactly like statically imported modules
- Full type safety and performance maintained

### Three-Tier Flexibility

**1. Automatic Import Translation (90% of cases)**
```comp
// Transparent imports via specialized importers
!import api = "openapi://./swagger.json"
!import db = "postgres://localhost/mydb?schema=public"
!import py_utils = "python://./utils.py"
!import proto = "protobuf://./messages.proto"

// Use normally with full type safety
api.users.get({id=123})
db.User.findById(123)
```

**2. Module Builder Pattern (9% of cases)**
```comp
// For custom scenarios beyond importer capabilities
builder = :module_builder.new()
builder -> :add_function("connect", connect_impl)
builder -> :add_shape("User", user_shape)
database_mod = builder -> !seal  // Now immutable

// Works exactly like static import
database_mod.connect() -> database_mod.query("SELECT * FROM users")
```

**3. Manual Construction (1% of cases)**
```comp
// Full control for edge cases
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

### Key Benefits

**Flexibility without chaos:** Multiple pathways to achieve dynamic behavior
**Performance:** Sealed modules perform identically to static imports
**Type safety:** Full type checking maintained even for runtime-built modules
**Familiarity:** Builder pattern and import syntax feel natural
**Optimization:** Intelligent caching makes repeated access fast

### Use Cases

- **Configuration-driven modules:** Build database connections from runtime config
- **Plugin systems:** Dynamically discover and load plugins
- **Code generation:** Generate API clients from external schemas
- **Schema reflection:** Create modules from database schemas or external APIs

The system provides a "pit of success" where common cases are trivial, edge cases are possible, and the type system remains intact throughout.