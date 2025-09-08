## Filesystem and Resource Design Summary

### Basic Filesystem Patterns (v1 Starting Point)

**Directory handles for scoped operations:**
```comp
# Open directory handle for safety and scoping
$dir = "/project" -> :fs:open_dir

# All operations relative to directory
{dir=$dir path="src/main.comp"} -> :fs:read
{dir=$dir path="build/"} -> :fs:list
{dir=$dir path="output.txt" data=$content} -> :fs:write

# Core operations
:fs:read        # Returns content
:fs:write       # Writes content  
:fs:list        # Lists directory
:fs:exists      # Checks existence
:fs:open_dir    # Creates directory handle

# Path manipulation (pure functions)
{"src" "main.comp"} -> :path:join
"/project/src/main.comp" -> :path:parent
```

This provides race-condition safety (like Linux `openat`) and natural sandboxing while keeping the API simple.

### Resource/Handle Requirements

**Structures need metadata beyond fields:**
- Provider reference (who manages this data's lifecycle)
- Capability metadata (read/write/latency/batch support)
- Source information (where this came from)
- Connection/transaction context

**Provider capabilities should describe:**
- Vectorization support (batch size, strategy)
- Connection overhead (free/cheap/expensive)
- Latency characteristics
- Authentication requirements
- Transaction boundaries

**Existing Comp infrastructure ready for this:**
- Structures already carry hidden metadata (private data, shape, invoke function)
- `!describe` operator exposes this metadata when needed
- `=>` vectorization operator can hint at batch operations

### Future Vision

The directory handle pattern naturally evolves into a universal "scope" abstraction where:
- Any hierarchical data source becomes navigable (filesystems, archives, S3, HTTP servers)
- Scopes can nest arbitrarily (ZIP file on S3, JSON within ZIP)
- Providers manage their own optimization strategies (batching, caching, pooling)
- Eventually even Comp structures themselves could be scopes, unifying all data access

The key insight: "directory" is just one type of scope. The pattern scales to any navigable data, but starting with just local filesystems proves the concept without the complexity.

## The Scope Evolution Path

**The progression from explicit to unified:**

1. **Today - Explicit pipelines (v1):**
   ```comp
   $path -> :fs:read -> :json:parse -> server.port
   ```

2. **Scope transition (v2):**
   ```comp
   $path -> :as:scope -> server.port
   ```

3. **Implicit conversion (v3):**
   ```comp
   $path -> server.port
   ```

4. **Pure unified access (final form):**
   ```comp
   $pathscope.server.port
   ```

In the final form, dot notation becomes the universal data navigation operator. No distinction between struct fields, file contents, database records, or API endpoints - it's all just data access. The providers and scopes become invisible implementation details of how `.` works.

The beauty: no syntax changes, no breaking changes, just a gradual revelation that everything was already unified. The language design naturally supported this evolution from day one.


***Followup***

All field access must remain pure, no external side effects.
A generic implementation would be something more like, `{$provider $path} -> :access -> server.port`.

If one day all values are attached to providers, a new arrow operator could make this streamlined, like `$path ~> server.port`
