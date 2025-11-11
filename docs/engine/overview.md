# Comp Language Overview

## What Makes Comp Different?

Comp combines features and styles from several different languages. It also
provides several new and novel ideas to allow developers to write clean code
and follow best practices. This is a high level interpreted language designed
to create composable and understandable programs.

The greatest measure of any programming language is how well the standard
libraries and core code align with idiomatic best practices. Comp implements
flow control, iteration, and resources with straightforward libraries that
can be reused and extended.

```comp
!doc module "There are many hello worlds, and this one is mine"
$mod.package = {name="hello" version="1.0.0"}
; Line comments use semicolons, there are no separators.

!func |planet = { 
	World
}

!main = {
	[|planet |capitalize |format "Hello, %{}!" |print]
}
```

Save as `hello.comp`, run with `comp hello.comp`. That's it. No build files, 
no configuration complexity, no dependency management, and no creation
templates to understand. Projects grow from here in flexible ways, only when
you are ready.

**Intro**

- Pipelines allow chaining composable functions together.
- Custom symbol identifies functions, shapes, tags, and more.
- All data is immutable structures; from simple numbers, iterators, and more.
- Module namespace is declarative, typos are build time errors.
- Functions look the same as literals structures, and they are.
- All structures are equal citizens, either from code, databases, json, or anything.
- A comp module represents a fully self-described package, no sidecar yaml or toml.
- Error handling integrates with pipelines naturally and helpfully.

## Big Ideas That Transform

### Structures all the way down

Comp's data type is more of a super-structure than a regular map of defined
fields. It combines the use cases of iterators, sequences, and maps into a
flexible container that does more and does it uniformly.

The construction of a literal structure can include intermediate statements
and computed values. A function definition becomes a regular structure literal
that is deferred until needed.

Every operation ends up being something that takes a structure in and generates
a structure out. The consistency becomes its source of power.

```comp
42                     ; Auto-promotes to {42}
{x=10 y=20}            ; Named fields
{1+1 2+2 3+3}          ; Positional fields  
{name="Alice" 30 active?=#true}  ; Mixed data
```

### Pipelines: Data Flows Like Streams

Pipelines are designed to work as a flat chain of operations. Define schemas
that match and morph compatibly data structures into new forms. Functions
use these schema shapes safely run any type of data.

Flow control like conditionals and loops are just regular functions. Use
deferred execution blocks defined on the fly to pass behavior into functions.

The wrench operator (`|-|`) enables pipeline meta-operations that enhance
functionality without changing business logic. Add progress tracking, query
optimization, or debugging to any pipeline.

```comp

!shape ~user = {
    name ~str
    email ~str|~nil = {}
    age ~num#years
    member-size ~timestamp
    recent-purchases ~num = 0
}

!func |count_adult_purchases ~{users~user[]} = {
    users 
    |filter :{age >= 18} 
    |iter :{value |send-welcome-email} 
    |-|progressbar          ; Simple progress reporting, even into iterations
    |sum {recent-purchases}
    |-| debug                ; Development-time logging
}
```

Invoked functions are easily identifiable by their `|` symbolic prefix. When
chained together this allows the reader to easily follow their progress.
Pipeline modifiers with `|-|` clearly indicate meta-operations that enhance
the pipeline structure itself.

The `~` syntax declares structural or type requirements. No inheritance 
hierarchies, no interface implementations—just structural matching that 
works intuitively.

The shape schemas provide strongly typed data validation in a way that is
reusable and expressive.

### Tags: Better Than Enums

Tags solve the problem that enums never quite get right; they need to be 
extensible, hierarchical, and carry values. Comp takes them even further by
using them for polymorphic dispatch.

Reference them by their most significant leaf value, then desscribe more
hierarchy to resolve ambuguities.

```comp
!tag #status = {
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
[$in |handle-request
    '#timeout.error.status' :{|retry-with-backoff}
    '#error.status' :{[|log-error] [|use-fallback]}
]
```

Tags play a dual role in the language, acting as both values and types, promoting them 
into new extensible types that can be used for dispatch and validation.

### Modules and imports

Modules define a namespace that is declarative and consistent. Symbol errors and
mismatches are build-time errors not discovered later in the middle of
execution. This also means definitions can be used and defined in any order
desired.

Everyone has been told a key to healthy code it splitting large functions
into smaller ones, and organizing large source code files into smaller
ones. In practice, most languages make this difficult. Comp is designed
to make this as easy as possible.

When outgrowing a single file, a module can be split into multiple files
belonging to a shared directory. References work across files with no concerns
for circular dependencies or functions being tied to enormous class definitions
that cannot be divided.

Rich imports define modules from a variety of sources. Use an OpenAPI spec
directly from a website as a complete Comp module. Let the runtime deal with
translating, caching, and packaging the external dependency.

Just like tags, unambiguous references are used directly. The namespaces
for imports are deterministic. Know what is provided by dependencies at
build time or while editing code directly.

```comp
; Use data from everywhere seamlessly
!import /str = std "core/str"
!import /pygame = python "pygame"
!import /api = openapi "http://api.example.org/v1"
!import /time = std "core/time"
!import /mars = github+release "offworld/martiancalendar@1.0.4"

; Access through simple namespaces
$token = "username" |fetch-auth-token |base64/str
$now = [|now/time ~num#day/mars]
```

### Scopes

Comp keeps a variety of scopes at hand for any evaluating code. This allows
placing data in the appropriate place. Short symbols uniquely identify which
scope a field is coming from.

Use `$var` prefixed variables to work with a function's local scope. Arguments are a
special, inherited scope prefixed with `$arg`. Or work with `$mod` for shared
values at the module global level. No mysterious variable capturing, no complex
closures, no hunting through nested scopes to understand where a value came from.

```comp
!func |process-request ~{request} arg ~{timeout ~num} = {
    $var.start-time = [|now/time]          ; Function-local variable
    $var.user = request.user               ; Another local variable

    response = [request |validate |process]   ; Output field
    duration = [|now/time] - $var.start-time   ; Uses local variable

    server-timeout = $arg.timeout      ; Argument reference
    global-config = $mod.settings      ; Module-level data
}
```

The combination of scopes makes it clear where each piece of data comes from:
- `$var` - Function locals that only exist within this function
- `$arg` - Arguments passed to this function
- `$ctx` - Execution context shared across function calls
- `$mod` - Module-level configuration and state

For the complete reference on how these scopes are managed, see [Syntax and Style Guide](syntax.md).

## Working with Data

### Field Access That Just Works

No matter what kind of data you're working with—API responses, database results, or values you've computed—accessing fields follows the same logical patterns.

```comp
user.name                ; Get the name field
settings.#0              ; First item in a list
config.'server-' + env   ; Computed field name
data."Content-Type"      ; Field names with special characters
```

Arrays and objects aren't different types requiring different syntax. They're all structures, so the same operations work everywhere.

### Numbers That Don't Betray You

Comp numbers work the way math actually works, not the way computer hardware
forces them to work. Expect lossless precision and accurate computations. Forget
about overflows, rounding errors, or clamping.

Avoid special non-number values like "infinity" except for where you opt-in to
allowing them.

Numbers with units catch unit conversion errors at the type level, not at
runtime when your Mars lander crashes.

```comp
huge = 999_999_999_999_999_999_999_999  ; No overflow
precise = 1/3                           ; Exact rational arithmetic
scientific = 6.022e23                   ; Standard notation
binary = 0b1010                         ; Binary literals
speed = 100#mph                         ; Units prevent errors
duration = endtime - starttime          ; Becomes a relative time offset
```

### Strings That Know Their Context

Strings in Comp can carry information about what kind of data they represent. This 
enables automatic safety features without manual work. The unit system enhances 
strings by appropriately escaping substitutions by default.

```comp
name = "Alice"                          ; Regular string
query = "SELECT * FROM users"#sql       ; SQL-aware string
html = "<div>Content</div>"#html        ; HTML-aware string

; Templates respect string types
message = %"Hello, ${name}!"            ; Automatically handles escaping based on context
```

SQL injection and XSS attacks become type errors instead of security vulnerabilities.

### Booleans Without Surprises

Booleans are strongly typed, just like everything else. There are no
"truthy" or "falsey" values. Booleans come from literals and operations
that result in booleans.

The builtin conditionals expect boolean types. No trying to guess if a 
string like `"0"` represents true or false. (Although when you want this,
write your own simple conditional operators.)

The language allows question marks in valid tokens. Use consistent naming
instead of marking up functions and values with "is" or "has" or "was"
naming conventions.

```comp
active? = #true                         ; Explicit boolean values
ready? = count > 0                      ; Clear comparisons
valid? = name != "" && email != ""      ; Logical combination
```

Empty strings aren't false. Zero isn't false. Only `#false` is false, and only
`#true` is true. This eliminates a whole class of subtle bugs that plague other languages.

## See It All Working Together

This example shows how Comp's features combine naturally:

```comp
!import /gh = comp "github-api"
!import /time = std "core/time"

!main = {
    $var.after = [|now/time] - 1#week
    $var.fields = {"title" "url" "created-at" "reactions"}
    
    [{..$var.fields repo="nushell/nushell"}
    |list-issues/gh
    |filter :{created-at >= $var.after}
    |-| progressbar              ; Add progress tracking
    |map :{
        $var.thumbs-up = [reactions |count-if :{content == #thumbs-up}]
        {thumbs-up=$var.thumbs-up title=. url=.}
    }
    |first 5]
}
```

**What's happening here:**
- Variables store computed values (`@after`, `@fields`)  
- Structures compose cleanly (`{..$var.fields repo="nushell/nushell"}`)
- Pipelines chain operations naturally (`[|filter :{created-at >= $var.after}]`)
- Pipeline modifiers add capabilities without changing logic (`|-| progressbar`, `|-| debug`)
- Blocks capture scope and simplify syntax (`:{created-at >= $var.after}`)
- Field shorthand reduces noise (`title=.` for `title=$in.title`)
- Everything composes seamlessly

## Ready to Dive Deeper?

This barely scratches the surface. Deeper dives into topics contain
explanations, examples, and comparisons.

- **[syntax.md](syntax.md)** - Syntax rules, style guide, and formatting conventions
- **[type.md](type.md)** - Numbers, strings, booleans, and unit systems
- **[structure.md](structure.md)** - Structure operations, spreads, and lazy evaluation  
- **[shape.md](shape.md)** - Shape system, morphing, and structural typing
- **[tag.md](tag.md)** - Hierarchical tags and polymorphic dispatch
- **[pipeline.md](pipeline.md)** - Pipeline operations, failure handling, and the wrench operator (`|-|`)
- **[function.md](function.md)** - Function definition, dispatch, and composition
- **[module.md](module.md)** - Module system, imports, and namespaces
- **[trail.md](trail.md)** - Advanced navigation through complex data
- **[store.md](store.md)** - Controlled mutable state when you need it
- **[security.md](security.md)** - Security features and best practices

Comp is currently in development—these documents describe the intended behavior
that will guide implementation. The foundations are solid, the vision is clear,
and the potential is exciting.