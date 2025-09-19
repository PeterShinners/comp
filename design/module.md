# Modules, Imports, and Namespaces

*Design for Comp's module system, imports, and program organization*

## Overview

Comp modules are isolated collections of functions, shapes, and tags that define reusable functionality. Each module provides a declarative namespace that can be analyzed without executing code. The contents and definitions in a module are order-independent and validated at build time.

Modules can be single `.comp` files or directories of `.comd` files. They reference each other through imports that assign namespace names. The module system provides builtin and standard libraries for core functionality while supporting various distribution formats like git repositories, local files, and package registries.

## Package Information and Module Structure

A module defines its package metadata directly in the `$mod` namespace rather than separate configuration files. This includes publishable names, version numbers, author information, and project URLs. This integrated approach means a single Comp file can be a complete, self-contained package.

```comp
$mod.package = {
    name = Image Processor
    version = 2.1.0
    author = Alice Smith <alice@example.com>
    homepage = https://example.com/image-processor
    repository = https://github.com/alice/image-processor
}
```

Modules can exist as either single files or directories. A single `.comp` file contains all definitions. A directory module contains multiple `.comd` files that are treated as one contiguous module. The choice between single and multi-file organization is invisible to module users - imports work identically regardless of internal structure.

## Import Statement and Sources

The `import` keyword assigns a namespace name and specifies how to locate module content. Each import brings exactly one module into scope. There's no partial importing of specific definitions, though they can be aliased after import.

```comp
# Import syntax: namespace = source "specifier"
import store = std "core/store"
import math = std "core/math"
import processor = comp "./lib/processor"
import external = python "numpy"
```

The language provides several import sources for different module types:
- `std` - Standard library modules with paths like "core/str" or "core/tag"
- `comp` - Comp modules from files, directories, or repositories
- `python` - Python modules exposed as Comp namespaces
- `main` - Shared dependencies from the main entry module

Import sources enable seamless integration with different code formats without precompilation. Protocol buffer definitions, OpenAPI specifications, and other schemas can generate Comp namespaces dynamically through specialized importers.

## Import Fallbacks and Coordination

Imports can define fallbacks using the `??` operator. If a module cannot be found, the system tries the next alternative. This enables graceful degradation and platform-specific implementations.

```comp
# Try multiple sources in order
import json = main "json" ?? std "core/json" ?? comp "./minimal-json"

# Platform-specific fallbacks
import graphics = comp "./graphics-gpu" ?? comp "./graphics-cpu"

# Version preferences
import db = comp "@db/postgres@3.0" ?? comp "@db/postgres@2.0" ?? std "core/db"
```

By default, imports coordinate through the main entry module. Libraries check if the main module imported a module with the same name before using their own definition. This creates a single source of truth for dependencies without complex resolution algorithms.

```comp
# In a library - automatically checks main first
import json = std "core/json"
# Behaves as: main "json" ?? std "core/json"

# Force specific version with strong assignment
import json *= std "core/json"    # Always use standard library

# In main module - becomes source for libraries
import json = comp "@fast-json@2.0"  # All libraries use this
```

## Entry Points and Initialization

Modules can define two special entry points that control initialization and program execution. The `entry` function runs when a module is imported, while `main` serves as the program entry point for executable modules.

Module initialization follows a deterministic order. First, all imported modules are fully loaded, with their imports resolved recursively. Then `entry` functions execute in dependency order - a module's dependencies run their entries before the module itself. By the time a module's `entry` runs, all its dependencies are fully initialized with their namespaces populated.

```comp
entry = {
    # Called when module is imported
    # All imports are loaded and their entry functions have run
    $mod.cache = (| initialize_cache)
    $mod.validators = (| build_validators)
    
    # Can reference imported namespaces
    (#pi/math | validate_precision)
}

main = {
    # Program entry point - only in executable modules
    # All module initialization is complete
    
    $var.args = (| parse/cli)
    $var.config = $var.args.config_file | load_config
    
    $var.args.command | match
        {serve} {$var.config | start_server}
        {test} {| run_tests}
        {#true} {| show_help}
}
```

The initialization order ensures predictable setup:
1. Import resolution (recursive, depth-first)
2. Namespace population for each module
3. `entry` execution in dependency order
4. `main` execution (if present)

## Standard Library Organization

The standard library organizes modules into branches based on stability and maturity. This allows the language to evolve while maintaining stable core functionality.

```comp
# Core - stable, essential functionality
import str = std "core/str"
import struct = std "core/struct"

# Proposed - experimental but promising
import async = std "propose/async"

# Early - actively developed, heading for core
import ml = std "early/ml"

# Archive - deprecated but available
import old_api = std "archive/old_api"
```

Standard library modules often import from multiple branches, using stable implementations where possible while exploring experimental features. This organization balances stability with innovation.

## Dynamic Module Loading

While most imports are static, the language supports runtime module loading through specialized importers. These maintain type safety by generating namespaces from external schemas and specifications. Once created, dynamically loaded modules behave identically to static imports.

```comp
# Schema-based imports generate typed namespaces
import api = openapi "./swagger.json"
import db = postgres "localhost/mydb?schema=public"
import proto = protobuf "./messages.proto"

# Use generated namespaces normally
user = (| get/users/api id=123)
result = (| find_by_email/users/db email=user@example.com)
```

For cases requiring programmatic module construction, the module builder pattern provides controlled flexibility while maintaining the same guarantees as static modules.

## Module File Organization

Modules automatically select platform-specific implementations through build tags. Files can be suffixed with platform identifiers, and the runtime chooses the most specific match.

```comp
# File selection by platform
render.comp              # Fallback for all platforms
render.windows.comp      # Windows-specific implementation
render.linux.comp        # Linux-specific implementation
render.wasm.comp         # WebAssembly implementation

# Multi-file modules work the same way
graphics/core.comd       # Shared core functionality
graphics/accel.linux.comd    # Linux acceleration
graphics/accel.windows.comd  # Windows acceleration
```

Platform tags include:
- `platform` - Operating system (windows, linux, macos)
- `arch` - Architecture (x64, arm64, wasm32)
- `runtime` - Implementation (pycomp1, jscomp)
- `environment` - User-defined (production, development)

## Namespace Management and Aliasing

After import, modules provide their definitions through their namespace. The reversed notation puts the most specific part first, with namespace qualification added when needed for disambiguation. Function names can be shortened when unique across all imported modules.

```comp
# Reversed notation - specific first
(text | length/str)          # Function from str module
data ~ matrix/math           # Shape from math module
#initialized.state/store     # Tag from store module

# Short forms when unique
(text | length)              # If only one 'length' function
data ~ matrix                # If only one 'matrix' shape
.state = #initialized        # If tag is unique

# Create local aliases for convenience
alias sqrt = |sqrt/math
alias Vec = ~vector3d/math
alias error = #error.net

# Now use short forms
{(4 | sqrt) (9 | cbrt/math)}  # Mix aliased and qualified
```

Aliases provide convenience without hiding origins. They're particularly useful for frequently-used definitions or when switching between implementations.

## Module Caching and Optimization

The import system coordinates with source providers for intelligent caching. Compiled bytecode, downloaded packages, and git repositories are cached to minimize redundancy. When a module is no longer needed, the system can release cached resources while preserving essential compilation results.

Build tools can analyze module dependencies to generate optimal bundles. Since module contents are declarative, the full dependency graph is known at build time, enabling dead code elimination and module fusion optimizations.

## Advanced Dependency Management

The import system provides an advanced override mechanism for packaging complete applications. Each imported dependency receives a unique identifier based on its import chain. At startup, these identifiers can be mapped to alternative sources, enabling fully self-contained applications.

```comp
# Build tool generates dependency manifest
dependencies = {
    "main/json" = "./bundle/json.comp"
    "main/store/utils" = "./bundle/store-utils.comp"
    "std/core/str" = "./bundle/str.comp"
}

# Runtime uses manifest for all imports
comp app.comp --dependency-bundle ./app.bundle
```

This system enables packaging entire dependency trees into single archives. The application runs entirely from its bundled dependencies without network access or external files. This creates truly standalone executables that work identically across environments.

## Design Principles

The module system embodies several core principles. Declarative namespaces mean module contents are knowable without execution. Single source of truth through main module coordination prevents version conflicts. Order independence within modules eliminates initialization races. Platform transparency means users don't see whether a module is single or multi-file. Integrated metadata keeps packages self-contained without external configuration. Standalone deployment through dependency bundling enables true portability.

These principles create a module system that scales from single-file scripts to large applications. Whether importing standard libraries, external packages, or local modules, the consistent import mechanism and predictable initialization order provide a solid foundation for program organization.