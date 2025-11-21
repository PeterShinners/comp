# Modules and Imports

Comp modules provide declarative namespaces that can be analyzed without
executing code. Modules can be single `.comp` files or directories of `.comd`
files—both appear as a single namespace with no circular dependency concerns.

The module and its direct imports define a declarative namespace used by all
code running in that module. References are resolved and validated at build
time, preventing many common error situations before runtime begins.

Imports are quite advanced for the comp. There are a variety of handlers that
build a fixed namespace from a variety of sources. While comp files will be the
most common, a namespace can come from any source that has a provided handler.

The namespace for each module is fixed and precomputed. It cannot be changed
dynamically or modified at runtime.

## Syntax

A module defines several types of objects that it exports. These are defined
using top level keywords at the module level.

- Functions are defined with the `func` keyword. This allows metadata to define
the input and argument shapes. Multiple implementations can be defined for the
same function name, they are identified by a unique shape for the input
argument, which will automatically dispatch to the most specifically defined
implementation.
- Shape definitions use the `shape` keyword. They define a shape name that must
be prefixed with a `~` character. The shape body is a list of fields wrapped in
curly braces. Each field defines an optional name, an optional shape, and can
also have an optinal default value.
- Tag definitions use the `tag` keyword. They define tags that must be prefixed
with a `#` character. Tags can define a hierarchy of children as well as
optional values.
- Handle definitions are defined with the `handle` keyword. Handles have no
values or metatadata themselves, they require management by functions to be
handed to other modules.
- Module metadata can be defined with constant data and expressions. These can
define values that provide default values for function arguments in the
function. The metadata also defines package information like versioning,
dependencies, and tool definitions.
- Loose documentation is attached to the module. This can be used to
positionally define sections and overviews about the module contents. Larger
block documentation can be separate from code using the `---` symbol to start
and close the sections.
- Imports are an important part of building the module namespace.

## Imports

The `import` keyword assigns a namespace and specifies the source:

```comp
; Standard library
!import store std "core/store"
!import math std "core/math"

; Local filesystem
!import utils comp "./lib/utils"
!import shared comp "/home/shared/libs"

; Git repositories
!import project comp "git@github.com:company/project.git"
!import versioned comp "git@github.com:org/lib.git#v2.0.1"

; Python modules
!import numpy python "numpy"
!import requests python "requests"

; OpenAPI specs
!import api openapi "https://api.example.com/swagger.json"
```

### Import Sources

**Core sources:**
- `std` - Standard library modules
- `comp` - Comp modules (filesystem, git, URLs)
- `python` - Python modules
- `main` - Shared dependencies from entry module

**Schema-based sources:**
- `protobuf` - Protocol Buffers specs
- `openapi` - OpenAPI specs
- `qtui` - Qt Designer definitions
- `ffi` - C libraries

## Import Fallbacks and Coordination

Use `??` for fallback sources:

```comp
; Try multiple sources
!import json main "json" ?? std "core/json" ?? comp "./minimal-json"

; Platform-specific
!import graphics comp "./graphics-gpu" ?? comp "./graphics-cpu"
```

By default, libraries check if main module imported a dependency before using
their own:

```comp
; In library - automatically checks main first
!import json std "core/json"
; Behaves as: main "json" ?? std "core/json"

; In main module - becomes source for libraries
!import json comp "git@github.com:fast/json.git#v2.0"
```

## Contexts

As comp functions execute they define a shared context that can be updated and
passed through the call chain. Modules can coordinate and define different
contexts to be used in different environments. 

The most common context is the `cli` context, which is used by the comp command
line tool when invoking modules.

The context defines a specially named function to be the entry point. This entry
point can be defined in the module that defines it in the context, but is
typically overridden by the module that is being executed.

```comp
!context cli extends default {
    verbose = #true
    source = "connection.json"
}

!context default {
    threads = 4
}

All modules will invoke their context definitions in order

```

## Entry Points

Entry points are typical functions, but do not define their own argument shape
and have no provided input value.

External tools can query the defined contexts and entry points a module and it's
dependencies have prepared. It then chooses one of them to use to invoke the
program.

```comp
!entry !func cli {
    print ("Hello, World!")
}

```

## Package Metadata

Fields defined at the module level are private to the module during runtime.
They are available to external tools to query and analyze. 

Comp modules contain their own package definition. They do not rely on external
files or definition scripts to define their package information and
requirements. There is a shape to define this package schema.

```comp
!mod package = {
    name="image-processor"
    version="2.1.0"
    author="Joe Q Developer <joeq@example.dev>"
    homepage="https://example.com/image-processor"
}
```

## Schema-Based Imports

Imports from schemas generate typed namespaces:

```comp
!import api openapi "./swagger.json"
!import db postgres "localhost/mydb?schema=public"
!import proto protobuf "./messages.proto"

; Use generated namespaces
let user = api.users.get {id=123}
let result = db.users.find-by-email {email="user@example.com"}
```

## Platform-Specific Modules

Modules and files can define specific architectures and runtimes, which will
override files without those decorated details.

Overrides can be based on platform, like `windows`, `linux`, `macos`, `wasm`,
and others.

Overides can also be based on architecture, version of comp, or other runtime
based information.

When importing comp modules the most specific decorated file will be selected.
This also works for indiidual files inside a directory-based module.

```comp
render.comp           ; Default implementation
render.windows.comp   ; Windows-specific
render.linux.comp     ; Linux-specific
render.wasm.comp      ; WebAssembly
```

## Namespace Aliasing

Definitions in the local module will be used by default will override those from
imported modules.

Modules can also define aliases of objects defined in imported namespaces. These
aliases will be treated as if defined in the local module directly, and will
also become part of this modules exported namespace.

Aliases can also be used define alternative names for internally defined
objects.

```comp
text | length/str        ; Function from str module
data ~matrix/math        ; Shape from math module

; Create aliases
!alias sqrt = sqrt/math
!alias vec = vector-3d/math

; Use short forms
4 | sqrt
point ~vec

```

## Module Privacy

Modules control visibility through module-private definitions (marked with `&`
suffix) and private data attachments. See [Syntax and Style
Guide](syntax.md#privacy-system) for canonical syntax.

### Module-Private Definitions

Mark definitions private with `&` suffix:

```comp
; Public API
!func public-api ~{data}
(
    data | internal-worker&
)

; Private helper
!func internal-worker& ~{data}
(
    data | step1 | step2 | step3
)

!shape config& = {
    internal-cache ~str
    validation-state ~any
}

; After import
!import utils comp "./utils"

data | public-api/utils       ; Works
data | internal-worker/utils  ; ERROR - private
value ~config/utils           ; ERROR - private
```

## Import Process 

Import handlers coordinate with the import system to download, cache, and
resolve versions. This hierarchy of dependencies is computed initially and
validated before any code in any modules is evaluated.


The languages itself comes with handlers for common types of data and.

- Comp module (single file or directory of files)
- Python module
- Json schema
- OpenAPI schema

**Key principles:**
- **Declarative** - Know what a module provides without running it
- **Order independent** - Define functions in any order across any files
- **Single source** - Main module coordinates shared dependencies


### Private Data Attachments

Modules attach private metadata invisible to other modules:

```comp
; Cache module
!func with-cache ~{key ~str}
(
    let result = {key value=(key | fetch)}
    
    ; Attach private data
    let result&.cached-at = time.now
    let result&.cache-key = key
    result
)

; Session module
!func with-session ~{user-data}
(
    let result = {..user-data}
    let result&.session-id = new-session
    let result&.session-start = time.now
    result
)

; Usage - both attach private data to same structure
let user = {name="alice" email="alice@example.com"}
    | with-cache/cache
    | with-session/session

; Each module sees only its own private data
; cache sees: user&.cached-at, user&.cache-key
; session sees: user&.session-id, user&.session-start
```

## Caching and Optimization

Compiled bytecode, downloaded packages, and git repositories are cached
automatically. Build tools analyze the declarative dependency graph for dead
code elimination and bundling optimizations.

## Dependency Bundling

Package applications with all dependencies in a single archive:

```comp
; Build tool generates manifest
dependencies = {
    "main/json" = "./bundle/json.comp"
    "main/store/utils" = "./bundle/store-utils.comp"
    "std/core/str" = "./bundle/str.comp"
}

; Deploy standalone executable
comp app.comp --bundle ./app.bundle
```

Bundled apps run without network access or external files, working identically
across environments.