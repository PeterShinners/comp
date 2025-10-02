# Modules, Imports, and Namespaces

*Comp's module and import system*

## Overview

Comp modules solve many common dependency frustrations. Each module provides a declarative namespace that can be analyzed without executing code—no more wondering what mysterious side effects might happen just to access a module's definitions.

Modules can be single `.comp` files or directories of `.comd` files. The directory approach still treats the files as a single namespace, no need to worry about circular dependencies or delicate file ordering. This internal module organization is invisible to users outside the module.

Modules reference each other through imports that create clean namespaces. The import system uses trail notation—the same `/path/` syntax used throughout Comp for hierarchical navigation. This consistency means imports immediately feel familiar. No build files, no dependency management tools, no version conflicts—just code that works.

The module system embodies several core principles that eliminate common frustrations. Declarative namespaces mean you know what a module provides without running it. Single source of truth through main module coordination prevents the "which version am I actually using?" problem. Order independence within modules eliminates those mysterious initialization race conditions.

Whether you're importing standard libraries, external packages, or local modules, the consistent import mechanism provides a solid foundation that scales from single-file scripts to large applications. For information about the security boundaries that modules create, see [Runtime Security and Permissions](security.md).

## Import Statement and Sources

The `!import` operator assigns a namespace name and specifies where to find the module content using trail notation. Each import brings exactly one module into scope—no cherry-picking specific definitions, though you can alias them afterward.

The import system's real power comes from its variety of sources. Instead of forcing everything into one package format, Comp can import from wherever your code lives: standard libraries, Python modules, OpenAPI specs, git repositories, even local files—all using the same trail notation.

```comp
; Standard library imports using trails
!import /store = std /core/store/
!import /math = std /core/math/

; Local filesystem imports
!import /utils = comp /./lib/utils/
!import /shared = comp /home/shared/libs/

; Git repository imports with trail notation
!import /project = comp /git@github.com:company/project.git/
!import /versioned = comp /git@github.com:org/lib.git/tag:/v2.0.1/

; Archive imports using axis-shift notation
!import /vendor = comp /vendor.tar/tar:/libs/database/
!import /bundled = comp /dist.zip/zip:/modules/

; URL-based imports
!import /remote = comp /https:/cdn.example.com/libs/v2/

; Python module access
!import /numpy = python "numpy"
!import /requests = python "requests"

; String literal fallback for complex cases
!import /special = custom "complex://provider?params=value"
```

### Import Sources

The language provides several defined sources for importing modules:

* `std` - Standard library modules using trail paths like `/core/str/` or `/dev/fractal/`
* `comp` - Comp modules from filesystem, git repositories, archives, or URLs using trail notation
* `python` - Python modules (string literals for module names)
* `main` - Share an imported dependency from the main entry module

Additional sources enable direct imports from other data types:

* `protobuf` - Generate namespace from Protocol Buffers specifications
* `openapi` - Generate namespace from OpenAPI specifications
* `qtui` - Generate namespace from Qt Designer definitions
* `ffi` - Basic C compatibility with header and shared library

### Trail-Based Import Specifiers

The trail notation in imports provides consistent, readable module references:

```comp
; Filesystem paths
!import /local = comp /./lib/utils/
!import /absolute = comp /opt/comp/libs/math/

; Git repositories with axis shifts
!import /lib = comp /git@github.com:user/repo.git/
!import /branch = comp /git@example.com:project.git:branch/develop/
!import /tag = comp /git@github.com:org/lib.git:tag/v1.2.3/

; Archives with axis notation
!import /archived = comp /downloads/libs.tar:tar/core/
!import /zipped = comp /backup.zip:zip/2024/modules/

; Nested archives
!import /nested = comp /dist.tar:tar/bundle.zip:zip/lib/

; URL-based imports
!import /cdn = comp /https:/cdn.example.com/comp/v3/
!import /api = openapi /https:/api.example.com/swagger.json/
```

### Import Fallbacks and Coordination

Imports can define fallbacks using the `??` operator—if a module can't be found, try the next alternative. This enables graceful degradation and platform-specific implementations without complex configuration.

```comp
; Try multiple sources in order
!import /json = main /json/ ?? std /core/json/ ?? comp /./minimal-json/

; Platform-specific fallbacks
!import /graphics = comp /./graphics-gpu/ ?? comp /./graphics-cpu/

; Version preferences with trails
!import /db = comp /git@github.com:db/postgres.git/tag:/v3.0/
            ?? comp /git@github.com:db/postgres.git/tag:/v2.0/
            ?? std /core/db/
```

By default, imports coordinate through the main entry module. Libraries check if the main module imported a module with the same name before using their own definition.

```comp
; In a library - automatically checks main first
!import /json = std /core/json/
; Behaves as: main /json/ ?? std /core/json/

; Force specific version with strong assignment
!import /json =* std /core/json/    ; Always use standard library

; In main module - becomes source for libraries
!import /json = comp /git@github.com:fast/json.git/tag:/v2.0/
```

## Entry Points and Initialization

Modules can define two special entry points that eliminate initialization headaches. The `!entry` function runs when a module is imported, while `!main` serves as the program entry point. Initialization follows a deterministic order, so dependencies are always ready.

```comp
!entry = {
    ; Called when module is imported
    ; All imports are loaded and their entry functions have run
    $mod.cache = [|initialize-cache]
    $mod.validators = [|build-validators]
    
    ; Can reference imported namespaces
    [#pi/math |validate-precision]
}

!main = {
    ; Program entry point - only in executable modules
    ; All module initialization is complete
    
    @args = [|parse/cli]
    [@args.config-file |load-config] @config =
    
    @args.command |match
        {serve} {[@config |start-server]}
        {test} {|run-tests}
        {#true} {|show-help}
}
```

## Package Information and Module Structure

A module defines its package metadata directly in the `$mod` namespace rather than juggling separate configuration files. This means a single Comp file can be a complete, self-contained package.

```comp
$mod.package = {
    name = image-processor
    version = 2.1.0
    author = Alice Smith <alice@example.com>
    homepage = https://example.com/image-processor
    repository = /git@github.com:alice/image-processor.git/
}
```

## Standard Library Organization

The standard library uses trail paths to organize modules by stability and maturity:

```comp
; Core - stable, essential functionality
!import /str = std /core/str/
!import /struct = std /core/struct/

; Proposed - experimental but promising
!import /async = std /propose/async/

; Early - actively developed, heading for core
!import /ml = std /early/ml/

; Archive - deprecated but available
!import /old-api = std /archive/old-api/
```

## Dynamic Module Loading

While most imports are static, the language supports runtime module loading through specialized importers. These maintain type safety by generating namespaces from external schemas and specifications.

```comp
; Schema-based imports generate typed namespaces
!import /api = openapi /./swagger.json/
!import /db = postgres "localhost/mydb?schema=public"
!import /proto = protobuf /./messages.proto/

; Use generated namespaces normally
user = [|get/users/api id=123]
result = [|find-by-email/users/db email=user@example.com]
```

## Module File Organization

Modules automatically select platform-specific implementations through build tags:

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

## Namespace Management and Aliasing

After import, modules provide their definitions through their namespace. The reversed notation puts the most specific part first, with namespace qualification added when needed for disambiguation.

```comp
; Reversed notation - specific first
[text |length/str]          ; Function from str module
data ~matrix/math           ; Shape from math module
#initialized.state/store    ; Tag from store module

; Short forms when unique
[text |length]              ; If only one 'length' function
data ~matrix                ; If only one 'matrix' shape
state = #initialized        ; If tag is unique

; Create local aliases for convenience
!alias |sqrt = |sqrt/math
!alias ~vec = ~vector-3d/math
!alias #error = #error.net

; Now use short forms
{[4 |sqrt] [9 |cbrt/math]}  ; Mix aliased and qualified
```

## Module Caching and Optimization

The import system coordinates with source providers for intelligent caching. Compiled bytecode, downloaded packages, and git repositories are cached to minimize redundancy.

Build tools can analyze module dependencies to generate optimal bundles. Since module contents are declarative, the full dependency graph is known at build time, enabling dead code elimination and module fusion optimizations.

## Advanced Dependency Management

The import system provides an advanced override mechanism for packaging complete applications. Each imported dependency receives a unique identifier based on its import chain.

```comp
; Build tool generates dependency manifest
dependencies = {
    "main/json" = /./bundle/json.comp/
    "main/store/utils" = /./bundle/store-utils.comp/
    "std/core/str" = /./bundle/str.comp/
}

; Runtime uses manifest for all imports
comp app.comp --dependency-bundle ./app.bundle
```

This system enables packaging entire dependency trees into single archives. The application runs entirely from its bundled dependencies without network access or external files, creating truly standalone executables that work identically across environments.