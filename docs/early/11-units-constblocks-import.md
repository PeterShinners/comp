# Comp Language Design Evolution - Major Updates

## Core Terminology & Runtime Architecture

### Statements and Pipelines
**Definition**: All function calls and struct operations that produce values are "statements." Every statement belongs to a pipeline, even if it's a "pipeline of one."

**Runtime Tracking**: The language records for each statement:
- Starting position (line & character)
- Ending position (line & character)
- The structure that created it
- Snapshot of namespace stack (`.out`, `.in`, `.ctx`, `.mod`)

**Provenance System**: Every structure maintains a reference to the statement/structure that created it, similar to Python frame objects. This metadata is accessible via `!describe` operations.

**Example**:
```comp
$user = data -> :fetch_user -> :validate_email  // Pipeline of 2 statements
$result = user.name -> :format                  // Pipeline of 1 statement
```

### Enhanced !describe Functionality
`!describe` on a function now attaches the function as an invocation to the structure, making the structure itself callable. This blurs the line between data and code elegantly.

```comp
$formatter = !describe :string:format
"Hello ${name}" -> $formatter {name="World"}  // Structure becomes callable
```

## Security Model Refinements

### !block Functions - Absolute Purity
**Core Principle**: `!block` functions receive ZERO security tokens, regardless of caller context. This creates an absolute guarantee of purity through runtime enforcement rather than static analysis.

**Benefits**:
- No complex static analysis required
- Functions with optional resource usage work automatically when called with null resources
- Mathematically pure constexpr evaluation guaranteed

**Example**:
```comp
!func :process_with_logging ~{data logger=null} = {
    $result = data -> :transform
    logger -> :log "Processing complete" | {}  // Safe if logger is null
    result
}

!block :validate_data ~{data} = {
    // Works fine - logger gets null, no tokens to create resources
    data -> :process_with_logging {logger=null}
}
```

### Function Argument Blocks
**Current Decision**: All argument blocks passed to functions are treated as `!block` functions - they receive no security tokens. This restriction may be relaxed in future iterations if real-world usage demonstrates necessity.

**Rationale**: Start conservative, gather empirical evidence for when resource access in argument blocks is actually needed.

## Import System Architecture

### Two-Phase Import Model
**Phase 1 - Provider**: Responsible for providing named resources (not limited to byte streams)
**Phase 2 - Importer**: Creates runtime Comp modules from provider resources

**Syntax**:
```comp
!import <module_name> = <importer_type> <provider_arguments>
```

### Provider Auto-Selection with Type Matching
**Provider Advertisement**: Each provider declares what types of resources it can provide
**Importer Requirements**: Each importer declares what resource types it accepts
**Resolution**: Automatic matching based on type compatibility

**Example Providers & Types**:
- URI Provider: `byte_stream` from HTTP/file URLs
- Git Provider: `file_tree` from git repositories  
- Python Provider: `python_runtime` from active Python modules
- Stdlib Provider: `comp_module` from standard library
- C FFI Provider: `c_header_and_lib` from header files and shared libraries

**Example Imports**:
```comp
!import spotify = openapi http://api.spotify.com/v1/spec.json  // URI -> OpenAPI
!import pygame = python pygame                                 // Python runtime -> Python bridge
!import iter = stdlib iter                                     // Stdlib -> Comp module
!import graphics = comp $COMPPATH/graphics                     // Filesystem -> Comp module
```

### Import Conflict Resolution
**Policy**: If multiple providers claim to handle the same resource string and provide compatible types, choose one arbitrarily with a warning. This handles the extremely rare edge case without over-engineering a complex resolution system.

### External Schema Integration
**Key Insight**: External schemas (OpenAPI, Protocol Buffers, etc.) are naturally sandboxed by their format limitations. They can only create functions that operate within their defined domain (HTTP calls, data serialization, etc.) without arbitrary code execution capabilities.

**First-Class Schema Support**:
```comp
!import api = openapi http://example.com/spec.json
// Creates typed HTTP client functions automatically
$user = api -> :get_user {id=123}

!import messages = protobuf ./schema.proto  
// Creates serialization/deserialization functions
$data = messages -> :User:serialize user_struct
```

## Unit System Extensions

### Units with Custom Formatters
**Requirement**: String formatters attached to units must be `!block` functions, enabling compile-time evaluation for literal inputs.

**Security Integration**: Units can apply domain-specific escaping automatically:

```comp
$query = "SELECT * FROM users WHERE id=${user_id}"@sql
// @sql unit automatically applies SQL escaping blocks
// Prevents injection attacks by default

$html = "<div>${content}</div>"@html  
// @html unit applies HTML escaping

$shell = "ls ${directory}"@shell
// @shell unit applies shell escaping
```

**Compile-Time Optimization**: When format inputs are compile-time literals, the entire formatting operation can be resolved at compile time.

## Advanced Unit Behaviors

### Custom Unit Conversion Logic
Units can define specialized conversion functions beyond simple linear scaling:

```comp
!unit @distance ~number = {
    m = !nil
    km = {mult=0.001}
    lightyear = {mult=1.057e-16}
}

// Generic linear conversion
!block :convert ~{from @distance to @distance} = {
    from -> :units:convert_linear {definitions=$distance_conversions}
}

// Special relativistic conversion override
!block :convert ~{from @distance.lightyear to @distance} = {
    from -> :physics:relativistic_conversion to.unit
}
```

### Unit-Aware Function Dispatch
Functions can be overloaded based on unit types, enabling domain-specific behaviors while maintaining type safety.

## Integration Examples

### Secure Multi-Source Data Processing
```comp
!func :process_github_data = {
    // Restrict child function capabilities
    @ctx -> :security:drop #security#filesystem.write
    @ctx -> :security:drop #security#network
    
    // Import external schema
    !import github = openapi https://api.github.com/spec.json
    
    // Process with limited permissions
    data -> github:fetch_issues -> :validate_and_analyze
}

!block :validate_issue_format ~{issue} = {
    // Guaranteed pure - no resource access possible
    issue.title -> :string:length > 0 ? issue | #error
}
```

### Runtime Schema Integration
```comp
// Import live Python module
!import cv2 = python cv2

// Import static schema  
!import api = openapi ./service-spec.json

// Combine in processing pipeline
$image = "photo.jpg" -> :file:read
         -> cv2:imread 
         -> cv2:resize {width=800@pixels height=600@pixels}
         -> api:upload_image
```

## Remaining Open Questions

### 1. Block Argument Restrictions
Current policy restricts all function argument blocks to `!block` purity. Real-world usage may reveal legitimate needs for resource access in argument blocks (conditional threading, conditional I/O, etc.). This decision can be revisited based on empirical evidence.

### 2. Cross-Import Security
How do security tokens flow when imported modules call other imported modules? Current thinking: each import gets its own isolated security context, but inter-module calling patterns need evaluation.

### 3. Import Versioning
While git-based imports can use commit hashes for versioning, other providers (especially runtime providers like Python modules) may need additional versioning strategies.

### 4. Provider Extension API
The interface for creating custom providers and importers needs formal specification, including type declaration mechanisms and resource lifecycle management.

## Implementation Priorities

1. **Finalize `!block` security model** - Runtime token enforcement mechanism
2. **Prototype import system** - Provider/importer type matching and resolution
3. **Unit formatter integration** - Compile-time evaluation and security escaping
4. **Provenance tracking** - Statement metadata and structure genealogy
5. **Standard library design** - Core units, importers, and security token types

This evolution represents a significant maturation of Comp's design, unifying security, modularity, and type safety into a coherent system that prioritizes both safety and practical usability.