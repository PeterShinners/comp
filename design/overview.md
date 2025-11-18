# Comp Language Overview

## Sales Pitch

Cleaner and simpler code that gets more work done. This high level language
focuses on removing developer friction. Simple and consistent high level
features, but more build-time validation and error checking then normally
provided.

Organize and style code any way you want. A focus on minimizing delimiters,
avoiding nesting, and ignoring whitespace. Define shared contexts that allow
breaking functions into any density, across any files, defined in any order.

A minimal langauge definition that let's the language build on top of it. Flow
control, iterations, compilation and more is built in comp. Easy to extend,
customize, or completely redefine for your own use cases.

Initiate transactions to allow atomic operations, or rollback everything,
including data structures and participating resources.

Comp is at home in Python. Interoperate closely with any running interpreter.
Access existing modules, or replace them with better implementations and use
those from Python.

```comp
-- There are many hello worlds, and this one is mine
mod.package = {name="hello" version="1.0.0"}

; Line comments use semicolons, there are no separators.

entry func main 
(
    gps_detect_planet {} 
    | capitalize {}
    | print {"Greetings, ${}"}
)


func gps_detect_planet ~nil ("earth")

```

Save as `hello.comp`, run with `comp hello.comp`. That's it. No build files, no
configuration complexity, no dependency management, and no 30 file project
templates to navigate. Projects grow from here in flexible ways, only when you
are ready.

**Intro**

- Pipelines allow chaining composable functions together.
- All data is immutable and stored inside immutable structures.
- Module namespace is declarative, typos are build time errors.
- Functions look like any literal structures, and they are; mostly.
- Shapes are schemas define shapes and transformation.
- Functions define shapes to control which types of data they work on.
- All data works the same; from code literals, databases, networks, or anything.
- No classes, no constructors, but still allow concepts like polymorphism.
- A comp package is self contained in a single file, or split into directories.
- Error handling integrates with pipelines naturally and elegently.

## Big Ideas That Transform

### Structures all the way down

Comp's data type is more of a super-structure than a regular hash of defined
fields. It combines the use cases of iterators, sequences, and maps into a
flexible container that does more and does it uniformly.

It combines positional and named fields interchangeably. Imagine a data
structure that could describe arguments for a Python function.

Each structure is immutable, but has rich operations that naturally create
modified and minimal clones of data. Think of the way Python handles strings,
but now apply that to everything.

Yes, there are simple data types like numbers and text. These are also
immutable, and work interchangeably with simple structures that contain those
single, scalar values.

```comp
42                     ; Auto-promotes to {42}
{x=10 y=20}            ; Named fields
{1+1 2+2 3+3}          ; Positional fields  
{name="Alice" 30 active?=#true}  ; Mixed data
```

### Pipelines: Data Flows Like Streams

Pipelines are designed to work as a flat chain of operations. A function is code
that takes an input struct and generates a new output struct.

Flow control like conditionals and loops are just regular functions. Pass around
and create blocks, which are simple executable values.

The pipeline itself is an inspectable data struct itself. Operations can be
connected in helpful ways, or entire call graphs transformed into optimized
forms.

```comp

shape ~user = 
{
    name ~str
    email ~str|~nil = {}
    age ~num#years
    member_since ~timestamp
    purchases ~num = 0
}

func welcome_new_users ~{users ~user[]} 
(
    let recent = now() - 1#week
    users 
    | filter :(it.member_since > recent)
    | iter :(it | send-welcome-email ())
    |-| progressbar ()  ; Instrument the pipeline with progress reporting
    | print ("Finished greeting {in | length()} users")
)
```

The `~` syntax declares structural or type requirements. No inheritance
hierarchies, no interface implementations—just structural matching that works
intuitively. The shape schemas provide strongly typed data validation in a way
that is reusable and expressive.

### Tags: Enumerations and more

Tags solve the problem that enums never quite get right; they need to be
extensible, hierarchical, and carry values. Comp takes them even further by
using them for polymorphic dispatch.

Tags play a dual role in the language, acting as both values and shapes. The
language uses them to disambiguate and dispatch data structures.

```comp
!tag #status 
{
    #active = 1
    #inactive = 0  
    #pending
    #error {
        #timeout = -100
        #network = -200
        #maintenance = -300
    }
}

; Use them as values
current = #active
problem = #maintenance.error

; Use them for dispatch
handle-request 
{
    '#timeout.error.status' = :(retry-with-backoff {})
    '#error.status' = :(log-error {} use-fallback {})
}
```

### Modules and imports

Modules define a namespace that is declarative and consistent. Define and use
symbols in any order. Access and override symbols from dependencies. All is
validated and assembled and built time.

When outgrowing a single file, a module can be split into multiple files
belonging to a shared directory. References work across files with no concerns
for circular dependencies. Functions are standalone units of execution, not
forced together in unwieldy class definitions or reference order problems.

Rich imports define modules from a variety of sources. Use an OpenAPI spec
directly from a website as a complete Comp module. Let the runtime deal with
translating, caching, and packaging the external dependency.

```comp
; Use data from everywhere seamlessly
import str std "core/str"
import pygame python "pygame"
import api openapi "http://api.example.org/v1"
import time std "core/time"
import mars github+release "offworld/martiancalendar@1.0.4"

; Access through simple namespaces
let token = "username" | fetch-auth-token {} | base64/str {}
let now = now/time {} ~num#day/mars
```

### Scopes

Code executing in functions can reference and store data in a variety of scopes.
Each has different rules about visibility and being overwritten.

Functions receive data directly in an argument and input scope, although both
can be given any top level name desired. Function locals are defined and
referenced with simple tokens for names.

Modules and contexts can also contribute into the namespace of visible values.
Shapes are applied to ensure the expected types of data are provided where
needed, and can possibly transform different data into different shapes.

Assigning variables into these scopes use the `let` keyword, although not all
scopes can be overwritten with assignments. Assignments without `let` are
exported as fields inside of a structure's literal curly braces.

```comp
func process-request in ~{request} arg ~{timeout ~num} 
(
    let start = now/time {}  ; Function-local variable
    let user = in.user  ; Another local variable

    {
        response = in | validate {} | process {}  ; Struct field
        duration = now {} - start;  Field computed from local
    }

    let ctx.server.timeout = arg.timeout  ; Copy argument value to context scope
    let config = mod.settings  ; Module-level constants
)
```

The combination of scopes makes it clear where each piece of data comes from:
- Function locals that only exist within this function, these are referenced
  directly
- `arg` - Arguments passed to this function
- `ctx` - Execution context shared across function calls
- `mod` - Module-level configuration and state

For the complete reference on how these scopes are managed, see [Syntax and
Style Guide](syntax.md).

## Working with Data

### Field Access That Just Works

No matter what kind of data you're working with— API responses, database
results, or values you've computed—accessing fields follows the same logical
patterns.

```comp
user.name  ; Get the name field
settings.#0  ; First item in a list
config.'status.ok' ; Computed field name
data."Content-Type"  ; Field names with special characters
```

Arrays and objects aren't different types requiring different syntax. They're
all structures, so the same operations work everywhere.

### Numbers That Don't Betray You

Comp numbers work the way math actually works, not the way computer hardware
forces them to behave. Expect lossless precision and accurate computations.
Forget about overflows, rounding errors, or clamping.

Avoid special non-number values like "infinity" except for where you opt-in to
allowing them.

Numbers with units catch unit conversion errors at the type level, not at
runtime when your Mars lander crashes.

```comp
huge = 999_999_999_999_999_999_999_999  ; No overflow
precise = 1/3                           ; Exact rational arithmetic
scientific = 6.022e23                   ; Standard notation
binary = 0b1010                         ; Binary literals
speed = 100#seconds                     ; Units become additional types for data
duration = endtime - starttime          ; Becomes a relative time offset
```

### Strings That Know Their Context

Strings in Comp can carry information about what kind of data they represent.
This enables automatic safety features without manual work. The unit system
enhances strings by appropriately escaping substitutions by default.

```comp
name = "Alice"                          ; Regular string
query = "SELECT * FROM users"#sql       ; SQL-aware string
html = "<div>Content</div>"#html        ; HTML-aware string

; Templates respect string types
message = %"Hello, ${name}!"            ; Automatically handles escaping based on context
```

SQL injection and XSS attacks become type errors instead of security
vulnerabilities.

### Booleans Without Surprises

Booleans are strongly typed, just like everything else. There are no "truthy" or
"falsey" values. Booleans come from literals and operations that result in
booleans.

The builtin conditionals expect boolean types. No trying to guess if a string
like `"0"` represents true or false. (Although when you want this, write your
own simple conditional operators.)

The language allows question marks in valid tokens. Use consistent naming
instead of marking up functions and values with "is" or "has" or "was" naming
conventions.

```comp
active? = #true                         ; Explicit boolean values
ready? = count > 0                      ; Clear comparisons
valid? = name != "" && email != ""      ; Logical combination
```

Empty strings aren't false. Zero isn't false. Only `#false` is false, and only
`#true` is true. This eliminates a whole class of subtle bugs that plague other
languages.
