# Modules and Imports

Comp modules are declarative namespaces that can be fully analyzed without
executing any code. A module defines shapes, tags, functions, and metadata that
become a fixed namespace resolved before runtime. This means the compiler knows
every reference, every type, and every dependency at build time, preventing
entire categories of errors before your code ever runs.

Modules can be single `.comp` files or directories of files. Both appear as a
single namespace. There are no circular dependency concerns because the
namespace is declarative, definitions can appear in any order across any files,
and the compiler resolves them all in one pass.

## Imports

The `!import` operator assigns a local namespace and specifies the source. The
source handler determines how the module is loaded, from the filesystem, a git
repository, a Python package, or even an API specification.

```comp
!import store comp "core:store"
!import utils comp "./lib/utils"
!import rio comp "@gh/rio-dev/rio-comp"
!import numpy python "numpy"
!import api openapi "https://api.example.com/swagger.json"
```

After import, the module's exports are accessed through the assigned namespace:
`rio.button`, `numpy.array`, `api.users.get`. The namespace is fixed at build
time, there is no dynamic module loading or runtime import modification.

### Import Sources

Core sources include `comp` for Comp modules (filesystem, git, URLs), `python`
for Python packages, and `main` for shared dependencies from the entry module.
Schema-based sources generate typed namespaces from structured specifications:
`openapi` for API specs, `protobuf` for Protocol Buffers, `ffi` for C
libraries. Each source handler translates external structure into Comp's type
system, giving you build-time validation against external contracts.

```comp
!import db postgres "localhost/mydb?schema=public"
!import proto protobuf "./messages.proto"

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
// In the main module, becomes the source for all libraries
!import json comp "git@github.com:fast/json.git#v2.0"

// In a library, automatically checks main first
!import json comp "core:json"
// Behaves as: main's json if available, otherwise core:json
```

## Namespace Resolution

All names from a module's own definitions and its imports are combined into a
single namespace. Within this namespace, any leaf name can be used as a shortcut
when it is unambiguous. Given an import `!import web comp "core:web"` where the
web module defines a tag hierarchy `!tag status {ok error timeout}`, all of
these are equivalent references:

```comp
web.status.ok   // fully qualified
status.ok       // drop the import prefix
ok              // just the leaf name
```

The compiler resolves the shortest unambiguous path. If two imports both define
an `ok` tag, the bare `ok` becomes ambiguous and the compiler requires
qualification. This applies equally to functions, shapes, tags, and any other
named object in the namespace. Local definitions always take priority over
imported names.


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

`!alias` creates namespace entries that reference other definitions.
`!export` re-exports an imported module's namespace under a new prefix.
See Aliases and Exports above.

Module-level `!let` bindings define constants, values computed once and
available throughout the module. These can use expressions and pure function
calls.

```comp
!import py comp "python" stdlib
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
name. Private declarations participate fully within the module, they contribute
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

### Aliases

The `!alias` operator creates namespace entries that point directly at existing
definitions. Aliases do not create new definitions — they are pure namespace
indirections resolved at build time. The referenced definition is the one that
gets compiled, optimized, and executed; the alias is just another name for it.

Aliases resolve against the module's namespace, which includes both local
definitions and imported symbols. An alias reference can use any name that
would be valid in code: a local definition, an import-prefixed reference, or
even another alias from local or external modules.

```comp
!alias crc zlib.crc32              // shortcut for deeply nested import
!alias parse json.parse            // choose json.parse as the default 'parse'
!alias sqrt fast-math.sqrt         // re-export under a different name
!alias crc& zlib.crc32             // private alias, not visible to importers
```

Multiple aliases to the same name create overloaded dispatch, combining
definitions from different sources under one entry point. Each alias must
still define a unique fully qualified name.

```comp
!import ss comp "struct"
!import tt comp "text"
!alias a.len ss.length       // struct length
!alias b.len tt.length       // text length — both available as 'len'
```

Aliases can chain through other aliases. The resolver follows the chain until it
reaches a concrete definition. Circular alias chains are detected and reported
as build errors.

```comp
!alias short medium
!alias medium long-name      // 'short' resolves to long-name's definition
```

### Exports

The `!export` operator re-exports an entire imported module's namespace under
a new prefix. Unlike `!alias` which references individual definitions,
`!export` takes an import name and surfaces all of its non-private definitions.

```comp
!import tt comp "text"
!export string tt             // all of tt's definitions under string.*
```

This makes `string.capitalize`, `string.length`, `string.split`, and every
other definition from the text module available in the current module's
namespace under the `string` prefix. The original definitions are referenced
directly — no copies are created.

Like aliases, exports are namespace-only and do not duplicate definitions.
Private definitions from the exported namespace are excluded.

## Package Metadata

Comp modules contain their own package definition, no external configuration
files. The `!package` operator defines versioning, authorship, and dependency
information that tools can query without executing the module.

```comp
!package image-processor "2.1.0"
```

## Startup and Context

Comp separates **context preparation** (`!startup`) from **entry points**
(`!main`). This two-layer design lets deep library modules initialize
themselves conditionally — based on which entry point the application
chooses — without polluting the declarative namespace.

### Context Preparation (`!startup`)

The `!startup` operator defines named context providers. Any module in the
import tree can contribute values to a named context. The body is a structure
literal whose fields become context entries.

```comp
// In stdlib/os.comp — always contributes to "default"
!startup default {
    temp-dir = [env "TMPDIR" | fallback "/tmp"]
    stdout = [stream.stdout]
    platform = [detect-platform]
}

// In lib/web.comp — depends on default context
!startup web <default> {
    server.port = [env "PORT" | fallback 8080 | as-num]
    server.host = [env "HOST" | fallback "0.0.0.0"]
}
```

`!startup` declarations are **not** added to the module namespace. They are
purely runtime initialization code.

**Dependencies.** A startup can declare dependencies on other startup contexts
using angle brackets: `!startup web <io default>`. The provider receives the
merged dependency context as `$`, allowing access to values from lower layers:

```comp
!startup web <io> {
    upload-dir = [$.io.temp-dir | path.join "uploads"]
    server.port = 8080
}
```

**Rules:**
- `!startup default` is special: it cannot declare dependencies and always
  runs as the base layer. Its `$` is always an empty struct.
- Multiple modules can contribute to the same startup name. Each runs
  independently (no sibling visibility). Their outputs merge.
- Two providers producing the same field name within the same startup layer
  is a build error (context conflict).
- A module can define multiple startup blocks with different names.
- Circular dependencies between startup layers are detected and reported as
  build errors.

### Entry Points (`!main`)

The `!main` operator defines named entry points in the root module. When Comp
executes a module, it looks for a `!main` matching the requested entry point
name and runs it.

```comp
!main console (
    [greet]
    [process-input]
)

!main serve <web> (
    [run-server]
)

!main test <testing> (
    [run-all-tests]
)
```

Entry points can declare startup dependencies using angle brackets:
`!main serve <web>`. This triggers the startup context DAG — all startup
layers needed by `web` (and its transitive dependencies) execute before the
entry point runs.

**Execution order for `!main serve <web>`:**
1. Collect the dependency DAG: `serve → web → default`
2. Execute all `!startup default` providers across the import tree. Merge.
3. Execute all `!startup web` providers. Each receives merged default context
   as `$`. Merge.
4. Assemble the full context. Run `!main serve` with context available for
   parameter matching.

The CLI selects an entry point with `--main NAME`:
```
comp app.comp --eval --main serve
comp app.comp --eval --main test
comp app.comp --list-mains       # show available entry points
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

    !let one [inner]              // inner sees url from context
    !let two [inner url="http://dev.example.com/"]  // explicit overrides context
)

!func inner ~text (
    !param url~text
    @fmt"%(url)/v1/ping/"
)
```

Context values are matched by name and type against parameter declarations. A
context value only populates a parameter if both the name matches and the type
is compatible. Parameters provided explicitly always take priority over
context.

Context values from `!startup` providers use hierarchical names like
`server.port`. These follow the same shortest-unambiguous-path resolution as
the module namespace: if `port` is only defined once across all startup layers,
a parameter `!param port~num` matches it directly. If multiple layers define
`port`, qualification is required: `!param server.port~num`.

### Design Principles

**Singletons are context.** Anything that would be a singleton, global
variable, service locator, or dependency injection binding in another language
belongs in the startup context. Database connections, configuration values,
stream handles, feature flags — these are all context entries.

**Context vs. values.** Context holds ambient state the caller shouldn't
thread through every call (similar to environment variables). Regular
parameters hold data the function operates on (similar to function arguments).

**No conditional imports.** The module namespace is fully declarative and
shared across all entry points. Different `!main` choices activate different
startup contexts (and thus different runtime resources), but the set of
available names never changes.

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
platform-detection code is needed, the import system handles selection.

## Caching and Bundling

The compiler caches compiled output, downloaded packages, and git repositories
automatically. Because the dependency graph is fully declarative, the compiler
can perform dead code elimination and bundling optimizations without executing
any module code.

Applications can be bundled with all dependencies into a single archive that
runs without network access or external files. The bundle contains the same
declarative namespace structure, just pre-resolved and pre-validated.
