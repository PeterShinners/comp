# Modules, Imports, Namespaces, and Entry Points

*Design for Comp's module system, imports, and namespaces*

## Overview

Comp modules are isolated collections of functions, shapes, and tags.

Modules define a declarative namespace that can be known without executing
code. The contents and definitions in a model are known and validated
analytically.

Modules can be represented by a single `.comp` file or by a directory of 
`.comd` files. In both cases the declaration and organization of the
module contents are order independent.

Module can reference one another through a flat namespace. The modules are
referenced from a variety of distribution formats, like git, websites, or
plan filesystem locations. When imported the module is assigned to a namespace
name, which is used to reference it's provided information.

The Comp language provides several builtin and standard libraries for working
with its builtin types, interacting with the system, and general computing
needs, like sorting.

Modules are a namespace used to access its defined functions, shapes, and
tags. These references are prefixed with the module's namespace and a leading
`.` dot character.

There is no way to refer to a module as a value, only its provided information.

```comp
!import json/ = std "json"

$data -> :json/stringify -> :json/parse

; Invalid - modules are not values
$json_lib = .json              ; ERROR: Cannot assign module to variable
data -> $json_lib:stringify   ; ERROR: Module not a value
```

**Benefits**:
- Clear distinction between modules and data
- Prevents confusion about module lifecycle
- Enables static analysis and tooling
- Consistent with namespace-oriented design

## Core modules

Several important modules are defined as the core of the Comp language. These
are imported automatically into every module. These are mainly related to
managing the builtin datatypes and higher level flow control. 

* `.iter` working with iteration and sequences
* `.num` working with number values and mathematics
* `.path` working with path structure values
* `.store` working with mutable data storage
* `.str` working with string values
* `.struct` high level modifications and queries for structures
* `.tag` working with tag definitions, values, and hierarchies

From these libraries there are also several specially aliased
values that can be referenced in every module, without providing the
full namespace. This is a feature any module can configure for themselves
using ~alias operarators. You can see these references are typed, based
on the type of object they contain

* `#break` iteration flow control to immediately stop processing iteratins
* `#false` false boolean tag value
* `#skip` iteration flow control to ignore a value (similar to a `continue` on other languages)
* `#true` true boolean tag value
* `~bool` shape for a boolean value
* `~nil` shape of an empty structure
* `~num` shape for a scalar numeric value
* `~str` shape for a scalar string value
* `:length` number of items in a structure

## Package Information

A module is a comp file or directory that is a standalone project, or package. 
Metadata about the package is defined globally in the module's `!mod` namespace. This
includes informtion like a publisheable name for the package, the version
number, urls for websites and repositories, and author information. There
is no separate "toml" or "json" file describing how the project is managed.

```comp
!mod.package = {
    name = "Super Advanced Project"
    version = "1.2.3"
    author = "User<name@github.com>"
}
```

## Import Statement

Modules are always imported with the `!import` operator, which will assign
a namespace name and then provide information needed to locate and import
the module data.

Each import operator imports only a single module. There is no way to directly
import specific definitions from a module, but they can be renamed
and provieded with `!alias` operations, separate from the import.

```comp
// !import name/ = source "specifier"

!import store/ = std "core/store"
!import friend/ = comp "libs/buddy"
!import rand/ = python "random"
```

### Import Sources

The language provides several defined sources for importing modules. 
These are usually related to the type of data being imported. The source
is given as a single token with no quoting or escaping used. Different
types of sources will work with different values of specificiers.

* `std` from the standard library. This will use a pathed name
    like `"core/str"` or `"dev/fractal"`
* `comp` a file or directory defined in a variety of storage locations described in the specifier.
* `python` access a Python module at runtime as a namespace. The specificer must be the fully qualified python module name.
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

Each import source can use the specificer however it needs. The language itself
comes with a rich handler for downloading and managing packages. This generates 
a cached and efficient stream of file contents to the importer source.

The system will recognize different types of strings and provide their contents.
The specifier is expected to be parsed and intrepreted so only a single best
type of import is used. It should not try to provide fallbacks through
multiple definitins.

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

### Import Fallbacks

The import statement allows defining fallbacks for a module using the `|`
operator. If any import cannot be found it will fallback on the next defined
import.

This fallback will only happen if the module is not found. Any other problems
importing the module will result in an import failure immediately.

```comp

!import jpeg/ = comp "contrib/jpeg-turbo" | comp "contrib/jpeg-basic"

; Multiple fallback sources using | operator
!import son/ = main "json" | std "json" | comp "./minimal-json.comp"

; Complex fallback with version preferences
!import atabase/ = main "database" | pkg "postgres@2.1" | pkg "sqlite@3.8"

; Platform-specific fallbacks
!import raphics/ = main "graphics" | pkg "opengl@4.6" | pkg "software-renderer@1.0"

```

### Coordinated Main Imports

The default behavior for imports is to coordinate dependencies based on whatever
is used by the main entry module. This behavior can be opted out by any
module. 

This means that every default import has an implied `main "<modulename>" |` condition.
If the main module did not import a module with the same name, it falls back
on using the regularly defined import.

```comp
; Library writes:
!import json/ = std "json"

; Automatically behaves as:
!import json/ = main "json" | std "json"  ; Try main first, fallback to std
```

**Benefits**:
- Any module work standalone with reasonable defaults (for testing or other needs)
- Applications can override any dependency
- No complex dependency injection syntax required
- Clear single source of truth for versions

This default import behavior can be overridden by using specific assignment
operators.

In the primary, main module for the program the imports have the following
meanings.

- `=` - Import normally
- `*=` - Import normally
- `?=` - Import, but do not define as an override for child libraries

Inside any imported library the assignment rules are different.
- `=` - First try dependency from the main module, otherwise normal import
- `*=` - Import normally, not overrides from the main module
- `?=` - First try dependency from the main module, otherwise normal import

In a library, these look like
```comp
!import json/ = std "json"      ; Normal: main can override
!import json/ *= std "json"     ; Strong: always use this exact version
!import json/ = main "json"     ; Explicit: must be provided by main module
```

## Security and Permission Integration

### Module-Level Permissions

```comp
; Module declares required permissions
!require read, write, net

; Functions inherit module permissions
!func :fetch_and_save ~{url ~str} = {
    url -> :http/get -> :file/write "output.json"
}

; Permission restriction within module
!func :safe_compute = {
    @ctx -> :security/drop #net        ; Drop network access
    @ctx -> :security/drop #write      ; Drop write access
    data -> :pure_calculation
}
```

### Cross-Module Permission Flow

Each imported module gets isolated security context:

```comp
; Main module has full permissions
!require read, write, net

; Import with permission restriction
!import andboxed/ = comp ./untrusted_module
; sandboxed module cannot access main module's permissions

; Explicit permission delegation (if supported)
sandboxed -> :restricted_function {
    permissions = {#read}    ; Delegate only read permission
}
```

### External Schema Security

External schemas are naturally sandboxed by format limitations:

```comp
!import pi/ = openapi ./external-api.json
; Can only create HTTP client functions - no arbitrary code execution

!import ata/ = protobuf ./schema.proto  
; Can only create serialization functions - no system access
```

## Entry Points

### Module Entry Points

```comp
!entry = {
    ; Module initialization - runs when imported
    !mod.initialized = !true
    !mod.version = "1.2.3" 
    :setup_module_state
}

!main = {
    ; Program execution entry point
    $args = :cli/parse_args
    $config = :config/load $args.config_file
    
    $args.command -> :match {
        "serve" -> :start_server $config
        "migrate" -> :run_migrations $config  
        "test" -> :run_tests
        else -> :show_help
    }
}
```

### Single Source of Truth Architecture

**Main Module Controls All Dependencies**:
- Main module has ultimate authority over all versions
- No hidden dependency sharing between libraries
- Clear, analyzable dependency tree
- Explicit version management

```comp
; Main module controls all versions
!main = {
    ; Override specific versions for entire application
    !import son/ *= pkg "json@2.5.1"        ; Force specific version
    !import atabase/ *= pkg "postgres@3.2"   ; Application-wide database version
    
    ; Libraries automatically use these versions
    :user_service/process_users
    :data_processor/transform_data
}
```

### Dependency Injection Through Main Override

Libraries automatically inherit main module's dependency choices:

```comp
; user_service.comp - Library module
!import son/ = std "json"           ; Default: standard library JSON
!import atabase/ = std "database"   ; Default: standard library database

; main.comp - Application
!import son/ *= pkg "fast-json@3.1"     ; Override with faster JSON library  
!import atabase/ *= pkg "postgres@3.2"  ; Override with PostgreSQL driver
!import ser_service/ = comp "./user_service.comp"

; user_service automatically uses fast-json@3.1 and postgres@3.2
```

### Explicit Version Management

**No Version Ranges or Lock Files**:
- All versions specified exactly in source code
- Tools can analyze and update versions by parsing source
- No hidden state in external lock files
- Clear audit trail of version changes

```comp
; Explicit, analyzable versions
!import son/ = pkg "json@2.5.1"           ; Exact version
!import tils/ = git "github.com/org/utils@v1.4.2"  ; Git tag
!import pi/ = openapi "https:;api.example.com/v2/spec.json"  ; URL with version

; Tools can parse and update these automatically
```

### Dynamic Module System

The dynamic module system maintains static safety through a **construction-time dynamic, runtime static** approach:
- Modules can be built programmatically at runtime
- Once sealed, they behave exactly like statically imported modules
- Full type safety and performance maintained

### Three-Tier Flexibility

**1. Automatic Import Translation (90% of cases)**
```comp
; Transparent imports via specialized importers
!import pi/ = "openapi:;./swagger.json"
!import b/ = "postgres:;localhost/mydb?schema=public"
!import y_utils/ = "python:;./utils.py"
!import roto/ = "protobuf:;./messages.proto"

; Use normally with full type safety
api.users.get({id=123})
db.User.findById(123)
```

**2. Module Builder Pattern (9% of cases)**
```comp
; For custom scenarios beyond importer capabilities
builder = :module_builder.new()
builder -> :add_function("connect", connect_impl)
builder -> :add_shape("User", user_shape)
database_mod = builder -> !seal  ; Now immutable

; Works exactly like static import
database_mod.connect() -> database_mod.query("SELECT * FROM users")
```

**3. Manual Construction (1% of cases)**
```comp
; Full control for edge cases
user_shape = :compile_shape({name: "string", age: "number"})
validator_func = :compile_function("validate_user", user_shape, logic)

builder -> :add_shape("User", user_shape)
       -> :add_function("validate", validator_func)
       -> !seal -> user_module
```

## Import Implementation

### Intelligent Caching

When an import source needs to generate a module, it can coordinate with
the import system to provide intelligent caching. Compiled bytecode can
be saved. The general specification providers will use automatic caching
of downloads, git repositories and more. When the source management has
finished caching its information it can release interest in the specification
provider's resources to minimize the cache space requirements.


### Versioning and Dependencies

Packages that come from versioned locations, like Github releases or 
a future package centralized package management system, are able to
use common semantic version tags. 

There is are no conflicts no technical conflicts or problems for a runtime
to have multiple versions of the same pacakge. This may run into conflicts
with extensions or system resources, but the language itself treats them
as independent. And their shapes will be just as interchangeable with anything
that has compatible shape definitions.

```comp
; Github release based versioning
!import utils/ = comp @company/utils@~1.2.3
```

### Standard Library branches

The standard library imports must specify a branch that their modules
come from. This allows the library to provide both stable and tested
implementation, along with experimental or proposed libraries.

Shipping these dependencies with the language itself isn't ideal, but
a simple and flexible solution until more general package management
solutions arrive.

The standard library branch names are

* `core/` The core language level features that should be stabilized.
* `propose/` Ideas that are worth wider evaluation but may change or drop.
* `early/` Actively developed modules that are headed for core but.
* `archive/` Unmaintained modules that will delete once they break, but still available.

It is expected that modules will import from all of these locations, even
for overlapping functionality. There will not be a lot of stability in the
standard library until the language achieves several major milestones.

This organization of modules is a concession to help balance
convenience with responsibility.

### Conditional and Platform Imports

```comp
; Platform-specific imports
!import raphics/ = disk deps/basic-graphics
!import raphics/.linux ?= path hardware-accelerated-linux
!import raphics/.windows ?= path directx-graphics
!import raphics/.macos ?= path metal-graphics

; Environment-based imports
!import atabase/ = stdlib database/sqlite       ; Development default
!import atabase/.production ?= stdlib database/postgresql
```

## Runtime Module Management

### Module Introspection

The typical `!describe` operator generates a structure with information
about a module. With modules this appears as `!describe .io`.

## Comp Module

A comp modules is defined as either
* A single, standalone `.comp` file
* A directory containing any number of `.comd` files (at least one)

When comp modules are imported they do not specific a file extension. This
allows library authors to change between single file and multi file
implementations between any version.

There is no visible difference to users of the module how it was implemented.

The files in a directory module are treated as one contiguous stream of data.
The definitions in a module are order independent.

In both single or module file modules, it is a module build error to contain
multiple conflicting definitions of the same thing.

### Platform-Specific Module Selection

Modules can be decorated with build tags that are part of the Comp runtime.
This allows different implementations of a module to be implemented on
for different platforms, architectures, and comp major versions.

Comp will automatically pick the most specific match to one of these
file variants. The comp language build and runtime provide these flags.

* `platform` operating system; windows, linux, macos, android, etc
* `runtime` implementation and major version; pycomp1
* `arch` built binary support (not yet applicable); x64, arm64, wasm32
* `environment` user definable overrides; production, development

This is available for individual files, either standalone or as part of
a directory.

* `render.comp` - fallback module for all other systems
* `render.windows.comp` - overridden implementation for platform


## Advanced Overrides

The import system provides an advanced way to override many types of imports.
Each imported dependency for the whole runtime is provided a unique,
semi-dependent identifier. This identifier can be used at startup time to
provide alternative import specifiers.

This system can be controlled directly, although it is considered low level. 
It cannot be controlled once modules begin importing dependencies, which
requires a two pass operation to identify dependency handles and then restart
to apply overrides.

The primary use case of this system is allowing packaging the full dependencies
for an application into a single archive. This archive contains the 
exact contents generated from the import specifications. This import time
overrides allows an application to run entirely from its packaged archive.

