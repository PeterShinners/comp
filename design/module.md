# Modules and Imports

Comp modules are declarative namespaces that can be fully analyzed without
executing any code. A module defines shapes, tags, functions, and metadata that
become a fixed namespace resolved before runtime. This means the compiler knows
every reference, every type, and every dependency at build time — preventing
entire categories of errors before your code ever runs.

Modules can be single `.comp` files or directories of files. Both appear as a
single namespace. There are no circular dependency concerns because the
namespace is declarative — definitions can appear in any order across any files,
and the compiler resolves them all in one pass.

## Imports

The `!import` operator assigns a local namespace and specifies the source. The
source handler determines how the module is loaded — from the filesystem, a git
repository, a Python package, or even an API specification.

```comp
!import store {comp "std:store"}
!import utils {comp "./lib/utils"}
!import rio {comp "@gh/rio-dev/rio-comp"}
!import numpy {python "numpy"}
!import api {openapi "https://api.example.com/swagger.json"}
```

After import, the module's exports are accessed through the assigned namespace:
`rio.button`, `numpy.array`, `api.users.get`. The namespace is fixed at build
time — there is no dynamic module loading or runtime import modification.

### Import Sources

Core sources include `comp` for Comp modules (filesystem, git, URLs), `python`
for Python packages, and `main` for shared dependencies from the entry module.
Schema-based sources generate typed namespaces from structured specifications:
`openapi` for API specs, `protobuf` for Protocol Buffers, `ffi` for C
libraries. Each source handler translates external structure into Comp's type
system, giving you build-time validation against external contracts.

```comp
!import db {postgres "localhost/mydb?schema=public"}
!import proto {protobuf "./messages.proto"}

// Generated namespaces are typed and validated
!let user api.users.get[id=123]
!let result db.users.find-by-email[email="user@example.com"]
```

### Dependency Coordination

Libraries check if the main module has already imported a dependency before
using their own. This means the entry point controls which version of shared
dependencies the entire application uses, preventing version conflicts without
explicit coordination.

```comp
// In the main module — becomes the source for all libraries
!import json {comp "git@github.com:fast/json.git#v2.0"}

// In a library — automatically checks main first
!import json {comp "std:json"}
// Behaves as: main's json if available, otherwise std:json
```

## Module-Level Declarations

A module's namespace is built from several types of declarations, all using `!`
operators at the top level. These are fully resolved before any code executes.

`!func` and `!pure` define functions. Multiple definitions with the same name
create overloads dispatched by input shape. See [Functions](function.md) for
details.

`!shape` defines data schemas that serve as types, validators, and
constructors. See [Structures](struct.md) for shape semantics.

`!tag` defines hierarchical enumerations. Tags serve as both values and types,
enabling dispatch and categorization.

`!startup` defines entry points that execute when the module is invoked in a
specific context (CLI, web server, test runner).

`!mod` defines sub-modules — namespaces nested within the current module.

Module-level `!let` bindings define constants — values computed once and
available throughout the module. These can use expressions and pure function
calls.

```comp
!import py {comp "python" stdlib}
!shape handle-db ~{}
!tag isolation {deferred exclusive immediate none}
!tag fail {interface database operation integrity}

!let exception-tags {
    interface-error = fail.interface
    database-error = fail.database
}
```

## Package Metadata

Comp modules contain their own package definition — no external configuration
files. The `!package` operator defines versioning, authorship, and dependency
information that tools can query without executing the module.

```comp
!package image-processor "2.1.0"
```

## Startup and Context

The `!startup` operator defines named entry points. When Comp executes a module,
it looks for a startup function matching the requested context. The startup
function bootstraps the application, establishing initial context values that
flow through the entire call chain.

```comp
!startup main (
    {5 3 8 1 7 9}
    | reduce[initial=nil] (tree-insert)
    | tree-values
    | print
)

!startup rio {
    title = "Todo"
    state = state
    component = todo-app
}
```

Startup functions can use `!ctx` to establish context values that automatically
populate matching modifier arguments in any function called within the
application. This is how configuration, theme data, and shared state flow
through Comp applications without explicit threading.

## Platform-Specific Modules

Modules and individual files can target specific platforms. The most specific
file matching the current environment is selected during import resolution.

```comp
render.comp              // default implementation
render.windows.comp      // Windows-specific
render.linux.comp        // Linux-specific
render.wasm.comp         // WebAssembly
```

This works at both the module level (entire directory) and the file level
(individual files within a module directory). No conditional compilation or
platform-detection code is needed — the import system handles selection.

## Namespace and Aliasing

Module-level definitions take priority over imported names. Modules can create
aliases for imported objects, making them appear as local definitions and
including them in the module's exports.

```comp
sqrt = fast-math.sqrt
vec = math.vector-3d
```

After aliasing, `sqrt` and `vec` can be used as if defined locally, and other
modules importing this one will see them as part of its namespace.

## Caching and Bundling

The compiler caches compiled output, downloaded packages, and git repositories
automatically. Because the dependency graph is fully declarative, the compiler
can perform dead code elimination and bundling optimizations without executing
any module code.

Applications can be bundled with all dependencies into a single archive that
runs without network access or external files. The bundle contains the same
declarative namespace structure, just pre-resolved and pre-validated.