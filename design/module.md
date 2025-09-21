# Modules, Imports, and Namespaces

*Comp's module and import system*

## Overview

Comp modules solve many common dependency frustrations. Each module provides a declarative namespace that can be analyzed without executing code—no, more wondering what mysterious side effects might happen just to access a module's definitions.

Modules can be single `.comp` files or directories of `.comd` files. The directory
approach still treats the files as a single namespace, no need to worry about
circular dependencies or delicate file ordering. This internal module organization
is invisible to users outside the module.

Modules reference each other through imports that create clean namespaces. The system supports everything from the standard libraries, file system search paths, to git repositories, all through the same consistent import mechanism. No build files, no dependency management tools, no version conflicts—just code that works.

The module system embodies several core principles that eliminate common frustrations. Declarative namespaces mean you know what a module provides without running it. Single source of truth through main module coordination prevents the "which version am I actually using?" problem. Order independence within modules eliminates those mysterious initialization race conditions.

Whether you're importing standard libraries, external packages, or local modules, the consistent import mechanism provides a solid foundation that scales from single-file scripts to large applications. For information about the security boundaries that modules create, see [Runtime Security and Permissions](security.md).

## Import Statement and Sources

The `!import` operator does exactly what you'd expect: assigns a namespace name and tells the system where to find the module content. Each import brings exactly one module into scope—no cherry-picking specific definitions, though you can alias them afterward.

The import system's real power comes from its variety of sources. Instead of forcing everything into one package format, Comp can import from wherever your code lives: standard libraries, Python modules, OpenAPI specs, git repositories, even local files.

The import statement requires two values to identify a module. First is the name
of the source. These can be extended, but the language offsers several builtin
sources.

The import also needs a specifier, which is a string literal. This has different
behaviors depending on the source used.

Import sources enable seamless integration with different code formats without
precompilation. Protocol buffer definitions, OpenAPI specifications, and other
schemas can generate Comp namespaces dynamically through specialized importers.

```comp
; Import syntax: namespace = source "specifier"
!import .store = std "core/store"
!import .math = std "core/math"
!import .processor = comp "./lib/processor"
!import .external = python "numpy"

!import .store = std "core/store"
!import .friend = comp "libs/buddy"
!import .rand = python "random"
```

### Import Sources

The language provides several defined sources for importing modules. 
These are usually related to the type of data being imported. The source
is given as a single token with no quoting or escaping used. Different
types of sources will work with different values of specifiers.

* `std` from the standard library. This will use a pathed name
    like `"core/str"` or `"dev/fractal"`
* `comp` a file or directory defined in a variety of storage locations described in the specifier.
* `python` access a Python module at runtime as a namespace. The specifier must be the fully qualified python module name.
* `main` share an imported dependency from the main, entry module

The expectation is that other sources will be defined, and extendable by the
runtime. These allow directly importing other data types into a native Comp
namespace without precompiling or translating into `.comp` source code.

The source allows generating a defined and reliable namespace from a variety
of sources without needing to rely on dynamic information or precompile steps.

* `protobuf` generate Comp namespace from Protocol Buffers specifications
* `openapi` generate Comp namespace from an OpenAPI json specification
* `qtui` generate Comp namespace from a Qt Designer xml definition
* `ffi` basic C compatibility with a header and shared library

### Import Specifiers

Each import source can use the specifier however it needs. The language itself
comes with a rich handler for downloading and managing packages. This generates 
a cached and efficient stream of file contents to the importer source.

The system will recognize different types of strings and provide their contents.
The specifier is expected to be parsed and interpreted so only a single best
type of import is used. It should not try to provide fallbacks through
multiple definitions.

* Absolute file or directory on disk
* Relative file or directory from the currently importing module
* Relative file or directory from the main entry point module
* Git repository
* Github or Gitlab package releases

When importing a module from larger packages, like git repositories
or zip archives, the import is based on a single location in that container.
The packaging itself is not considered the module. For example, a
git repository could provide multiple comp modules and internally organize
itself as multiple independent modules.

### Import Fallbacks and Coordination

Imports can define fallbacks using the `??` operator—if a module can't be found, try the next alternative. This enables graceful degradation and platform-specific implementations without complex configuration.

The coordination system solves a common problem: when multiple libraries want to use the same dependency, which version wins? Comp's solution is elegant—the main entry module becomes the single source of truth. Libraries check if the main module already imported what they need before using their own fallback.

```comp
; Try multiple sources in order
!import json = main "json" ?? std "core/json" ?? comp "./minimal-json"

; Platform-specific fallbacks
!import graphics = comp "./graphics-gpu" ?? comp "./graphics-cpu"

; Version preferences
!import db = comp "@db/postgres@3.0" ?? comp "@db/postgres@2.0" ?? std "core/db"
```

By default, imports coordinate through the main entry module. Libraries check if
the main module imported a module with the same name before using their own
definition. This creates a single source of truth for dependencies without
complex resolution algorithms.

```comp
; In a library - automatically checks main first
!import json = std "core/json"
; Behaves as: main "json" ?? std "core/json"

; Force specific version with strong assignment
!import json *= std "core/json"    ; Always use standard library

; In main module - becomes source for libraries
!import json = comp "@fast-json@2.0"  ; All libraries use this
```

## Entry Points and Initialization

Modules can define two special entry points that eliminate initialization headaches. The `!entry` function runs when a module is imported, while `!main` serves as the program entry point. The key insight: initialization follows a deterministic order, so you never have to worry about whether your dependencies are ready.

Module initialization follows a deterministic order. First, all imported modules
are fully loaded, with their imports resolved recursively. Then `!entry`
functions execute in dependency order - a module's dependencies run their
entries before the module itself. By the time a module's `!entry` runs, all its
dependencies are fully initialized with their namespaces populated. For details
about function definitions and execution patterns, see [Functions and
Blocks](function.md).

```comp
!entry = {
    ; Called when module is imported
    ; All imports are loaded and their entry functions have run
    $mod.cache = (|initialize-cache)
    $mod.validators = (|build-validators)
    
    ; Can reference imported namespaces
    (#pi/math |validate-precision)
}

!main = {
    ; Program entry point - only in executable modules
    ; All module initialization is complete
    
    @args = (|parse/cli)
    @config = @args.config-file |load-config
    
    @args.command |match
        {serve} {@config |start-server}
        {test} {|run-tests}
        {#true} {|show-help}
}
```

The initialization order ensures predictable setup:
1. Import resolution (recursive, depth-first)
2. Namespace population for each module
3. `!entry` execution in dependency order
4. `!main` execution (if present)

## Package Information and Module Structure

A module defines its package metadata directly in the `$mod` namespace rather than juggling separate configuration files. This means a single Comp file can be a complete, self-contained package—no package.json, no setup.py, no build.gradle required.

This is typically done at the top level of the package using literal values.

```comp
$mod.package = {
    name = image-processor
    version = 2.1.0
    author = Alice Smith <alice@example.com>
    homepage = https://example.com/image-processor
    repository = https://github.com/alice/image-processor
}
```

## Standard Library Organization

The standard library organizes modules into branches based on stability and maturity. This lets the language evolve without breaking your code—stable functionality stays stable, while experimental features get clearly marked.

```comp
; Core - stable, essential functionality
!import str = std "core/str"
!import struct = std "core/struct"

; Proposed - experimental but promising
!import async = std "propose/async"

; Early - actively developed, heading for core
!import ml = std "early/ml"

; Archive - deprecated but available
!import old-api = std "archive/old-api"
```

This organization balances stability with innovation. You can stick with core modules for production code while exploring cutting-edge features in development.

## Dynamic Module Loading

While most imports are static, the language supports runtime module loading
through specialized importers. These maintain type safety by generating
namespaces from external schemas and specifications. Once created, dynamically
loaded modules behave identically to static imports.

```comp
; Schema-based imports generate typed namespaces
!import api = openapi "./swagger.json"
!import db = postgres "localhost/mydb?schema=public"
!import proto = protobuf "./messages.proto"

; Use generated namespaces normally
user = (|get/users/api id=123)
result = (|find-by-email/users/db email=user@example.com)
```

For cases requiring programmatic module construction, the module builder pattern
provides controlled flexibility while maintaining the same guarantees as static
modules.

## Module File Organization

Modules automatically select platform-specific implementations through build
tags. Files can be suffixed with platform identifiers, and the runtime chooses
the most specific match.

```comp
; File selection by platform
render.comp              ; Fallback for all platforms
render.windows.comp      ; Windows-specific implementation
render.linux.comp        ; Linux-specific implementation
render.wasm.comp         ; WebAssembly implementation

; Multi-file modules work the same way
graphics/core.comd       ; Shared core functionality
graphics/accel.linux.comd    ; Linux acceleration
graphics/accel.windows.comd  ; Windows acceleration
```

Platform tags include:
- `platform` - Operating system (windows, linux, macos)
- `arch` - Architecture (x64, arm64, wasm32)
- `runtime` - Implementation (pycomp1, jscomp)
- `environment` - User-defined (production, development)

## Namespace Management and Aliasing

After import, modules provide their definitions through their namespace. The
reversed notation puts the most specific part first, with namespace
qualification added when needed for disambiguation. Function names can be
shortened when unique across all imported modules. For comprehensive information
about tag naming and hierarchical notation, see [Tag System](tag.md).

```comp
; Reversed notation - specific first
(text |length/str)          ; Function from str module
data ~matrix/math           ; Shape from math module
#initialized.state/store    ; Tag from store module

; Short forms when unique
(text |length)              ; If only one 'length' function
data ~matrix                ; If only one 'matrix' shape
state = #initialized        ; If tag is unique

; Create local aliases for convenience
!alias |sqrt = |sqrt/math
!alias ~vec = ~vector-3d/math
!alias #error = #error.net

; Now use short forms
{(4 |sqrt) (9 |cbrt/math)}  ; Mix aliased and qualified
```

Aliases provide convenience without hiding origins. They're particularly useful
for frequently-used definitions or when switching between implementations.

## Module Caching and Optimization

The import system coordinates with source providers for intelligent caching.
Compiled bytecode, downloaded packages, and git repositories are cached to
minimize redundancy. When a module is no longer needed, the system can release
cached resources while preserving essential compilation results.

Build tools can analyze module dependencies to generate optimal bundles. Since
module contents are declarative, the full dependency graph is known at build
time, enabling dead code elimination and module fusion optimizations.

## Advanced Dependency Management

The import system provides an advanced override mechanism for packaging complete
applications. Each imported dependency receives a unique identifier based on its
import chain. At startup, these identifiers can be mapped to alternative
sources, enabling fully self-contained applications.

```comp
; Build tool generates dependency manifest
dependencies = {
    "main/json" = "./bundle/json.comp"
    "main/store/utils" = "./bundle/store-utils.comp"
    "std/core/str" = "./bundle/str.comp"
}

; Runtime uses manifest for all imports
comp app.comp --dependency-bundle ./app.bundle
```

This system enables packaging entire dependency trees into single archives. The
application runs entirely from its bundled dependencies without network access
or external files. This creates truly standalone executables that work
identically across environments.
