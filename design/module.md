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
!let user api.users.get :id=123
!let result db.users.find-by-email :email="user@example.com"
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

## Namespace Resolution

All names from a module's own definitions and its imports are combined into a
single namespace. Within this namespace, any leaf name can be used as a shortcut
when it is unambiguous. Given an import `!import web {comp "std:web"}` where the
web module defines a tag hierarchy `status = {ok error timeout}`, all of these
are equivalent references:

```comp
web.status.ok       // fully qualified
status.ok           // drop the import prefix
ok                  // just the leaf name
```

The compiler resolves the shortest unambiguous path. If two imports both define
an `ok` tag, the bare `ok` becomes ambiguous and the compiler requires
qualification. This applies equally to functions, shapes, tags, and any other
named object in the namespace. Local definitions always take priority over
imported names.

### Aliases

The `!alias` operator is a top-level module declaration that creates explicit
namespace entries. Aliases can re-export symbols from imported modules as part
of the current module's public API, choose a default implementation when
multiple imports define the same name, or simply provide a shorter name for
a deeply nested reference.

```comp
!alias crc zlib.crc32              // shortcut for deeply nested import
!alias parse json.parse            // choose json.parse as the default 'parse'
!alias sqrt fast-math.sqrt         // re-export under a different name
!alias crc& zlib.crc32             // private alias, not visible to importers
```

Aliases participate in namespace resolution like any other definition. An alias
to a function includes all of its overloads. An alias marked private with `&`
is available within the module but hidden from importers, just like any other
private declaration.

## Module-Level Declarations

A module's namespace is built from several types of declarations, all using `!`
operators at the top level. These are fully resolved before any code executes.

`!func` and `!pure` define functions. Multiple definitions with the same name
create overloads dispatched by input shape. See [Functions](function.md).

`!shape` defines data schemas that serve as types, validators, and
constructors. See [Structures](struct.md).

`!tag` defines hierarchical enumerations. Tags serve as both values and types,
enabling dispatch and categorization.

`!startup` defines entry points that execute when the module is invoked in a
specific context (CLI, web server, test runner). These are not added to the
module's namespace.

`!context` defines callables that cooperate to define the initial context
and select the name for the startup function. These are not added to the
module's namespace.

`!mod` defines module level constant values. Similar to a `!let` but this
works across function definitions inside the module. These are never
exported to importers.

`!alias` creates namespace entries that reference other definitions. See
Aliases above.

Module-level `!let` bindings define constants — values computed once and
available throughout the module. These can use expressions and pure function
calls.

```comp
!import py {comp "python" stdlib}
!shape handle-db ~{}
!tag isolation {deferred exclusive immediate none}
!tag fail {interface database operation integrity}

!mod exception-tags {
    interface-error = fail.interface
    database-error = fail.database
}
```

### Private Declarations

Any module-level declaration can be marked private with a trailing `&` on its
name. Private declarations participate fully within the module — they contribute
to overloaded dispatch, can be referenced by other definitions, and behave
identically to public declarations. They are simply invisible to anyone
importing the module.

```comp
!func resource& (...)
!shape internal-state& ~{...}
!tag fail {interface database operation integrity internal&}
```

The `&` on a tag child hides just that branch. On a parent, it hides the entire
hierarchy underneath.

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
    | reduce :initial=nil :(tree-insert)
    | tree-values
    | print
)

!startup rio {
    title = "Todo"
    state = state
    component = todo-app
}
```

### Context Scope

While the interpreter evaluates code it maintains a special scope called the
context. Functions can modify this scope with the `!ctx` operator, which works
like `!let` but affects all downstream function calls while also adding that
variable to the local scope.

Functions do not access the accumulated context directly. Instead, context
values automatically provide defaults for any invoked function whose parameters
match by name and type. This is conceptually similar to environment variables in
an operating system, but integrated with the language's type system and
available at all levels of the application.

```comp
!func outer (
    !ctx url "http://example.com/"

    !let one inner              // inner sees url from context
    !let two inner :url="http://dev.example.com/"  // explicit overrides context
)

!func inner (
    :param url~text
    @fmt"%(url)/v1/ping/"
)
```

Context values are matched by name and type against parameter declarations. A
context value only populates a parameter if both the name matches and the type
is compatible. Parameters provided explicitly always take priority over
context. Modules define their initial context through `!startup` declarations,
which establish the context before the entry point function is invoked.

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

## Caching and Bundling

The compiler caches compiled output, downloaded packages, and git repositories
automatically. Because the dependency graph is fully declarative, the compiler
can perform dead code elimination and bundling optimizations without executing
any module code.

Applications can be bundled with all dependencies into a single archive that
runs without network access or external files. The bundle contains the same
declarative namespace structure, just pre-resolved and pre-validated.