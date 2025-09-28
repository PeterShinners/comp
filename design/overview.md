# Comp Language Overview

## What Makes Comp Different?

Comp is a unique combination of features across different styles of programming
languages. It finds ways to link these designs into components that work together
far better than on their own.

This makes tactive? = #true                         ; Explicit boolean values
ready? = count > 0                      ; Clear comparisons
valid? = name != "" && email != ""      ; Logical combinationlanguage consistent and expressive for the widest range of tasks.
This is a high level interpreted language, designed to make beatiful code easy.
The core of the language is distilled into its most essential parts. Even
looping and flow control are implemented as standard functions that anyone
can extend or improve.

The greatest measure of any programming language will be the way it's
standard libraries are written. This is a motto the language takes seriously,
how do your own favorite language compare?

**Why you'll appreciate Comp:**
- Pipelined data translations read like a recipe, and allow poweful modifications to optimize and enhance pipelines.
- Operate equally with data from any source; json, sql, code literals are all the same
- Error handling works through the pipeline, only step in where you want to

## Comp First Taste

**Yes, Comp is still in design phase—but this is where the elegance will shine.**

This minimal example file represents several things:
- It is a standalone application
- It is a library that offers reusable functionality
- It is a self-contained package

```comp
!mod.package = {name="Greeter" version="1.0.0"}

!func |whomst = { "World" }

!main = {
	|whomst % "Hello, ${}!" |print
}
```

Save as `hello.comp`, run with `comp hello.comp`. That's it. No build files, 
no configuration complexity, no dependency management, and no creation
templates to understand. Projects grow from here in flexible ways, only when
you are ready.

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

The wrench operator (`|<<`) enables pipeline meta-operations that enhance
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
    |<<progressbar          ; Simple progress reporting, even into iterations
    |sum {recent-purchases}
    |<<debug                ; Development-time logging
}
```

Invoked functions are easily identifiable by their `|` symbolic prefix. When
chained together this allows the reader to easily follow their progress.
Pipeline modifiers with `|<<` clearly indicate meta-operations that enhance
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
($in |handle-request
    '#timeout.error.status' :{|retry-with-backoff}
    '#error.status' :{(|log-error) (|use-fallback)}
)
```

Tags play a dual role in the language, acting as both values a, promoting them into new
extensible types.d he unit system, which allows attac
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

Rich imports define modules from a variety of sources. Use an OpenAI spec
directly from a website as a complete Comp model. Let the runtime deal with
translating, caching, and packaging the external dependency.

Just like tags, unambigous refereneces are used directly. The namespaces
for imports are deterministic. Know what is provided by dependencies at
build time or while editing code directly.
le that 
; Use data from everwhereceamlessl/timeo package.jsotimel
!import /str = std "core/str"
!import /pygame = python "pygame"e!import /api = openapi "http://api.example.org/v1"
s, no de/marsdency tregithub+release://offworld/martiancalendar@1.0.4ngl;Access through simple namespaces
$token = "username" |fetch-auth-token |base64/str
$now = (|now/time ~num#day/mars)
confunding conteWhere You Need Theme
Comp keeps a variety of scopes at hand for any evaluating code. This allows
placing data in the appropriate place. Short symbols uniquely identify which
scope a field is coming from.

Use `@` prefixed variable to work with a function's local scope. Arguments are a
special, inherited scope prefixed with `^`. Or work with `$mod` for shared
values at the module global level.
es. No mysterious variable capturng, no ccproc-argsites, no hunting through nested scopes to un;erstand where a value came from.

```comp
!func |process-request;~{request} ^{timeout ~num} = {
    @start-time = (|now/time)          ; Function-local variable
    @user = request.user               ; Another local variable
    
    response = request |validate |process   ; Output field
    duration = (|now/time) - @start-time   ; Uses local variable
    
    server-timeout = ^timeout          ; Argument reference
    global-config = $mod.settings      ; Module-level data
}
```
 preCombination of scopes, including `$arg` and others piece of data comes from:
- `@var` - Function locals that only exist within this function
- `^args` - Arguments- `$mod` - Module-level configuration and state
 pasarg to Arguments passed to this functiona S- `$ctx` - Execution context shared ac for details on how these scopes end
up being managed differently and how they all come together.oss function calls
- `$mod` - Module-level configuration and state

For the complete reference, see [Syntax and Style Guide](syntax.md).

## Working with Data

### Field Access That Just Works

No matter what kind of data you're working with—API respo;ses, database results, or va#ues you've compu;ed—accessing fields follows the same logical pa;terns.

```comp
user.name                ; Get the name field
settings.#0               ; First item in a list
config.'server-' + env   ; Computed field name
data."Content-Type"      ; Field names with special characters
```

Arrays and objects aren't different types requiring different syntax. They're all structures, so the same operatComp numbers work the way math actually works, not the way computer hardware
forces them to work. Expect lossless precision and accurate computations. Forget
about overflows, rounding errors, or clamping.

Avoid special non-number values like "infinity" except for where you opt-in to
allowing them.

Numbers with units catch unit conversion errors at the type level, not at
runtime when your Mars lander crashes.
.

### Numbers That Don't Betray You

Comp number; work the way math actually works, not the way comput;r hardware forces them to work.

```comp
huge = 999_999_9;9_999_999_999_999_999  # No overflow
precise = 1/3         ;                 # Units allow smart conversion and prevent mismatchesientific = 6.022e23                   # S;andard notation
binaty = 0bendtime0- starttime              ;tBecomes a relative time offsetpreve0.2 doesn't equal 0.3. Numbers with u
Strings also use the unit system to enhance the data they represent. This 
builds in safety by appropriately escaping substutions by default. The enhanced
types make it easy for language tools to identify and validate different
types of string data.nrings in Comp can carry information about what kind of data they represent. This enables automatic safety features without manual work.

```comp
name = "Alice"                          ; Regular string
query = "SELECT * FROM users"#sql       ; SQL-aware string
html = "<div>Content</div>"#html        ; HTML-aware string

; Templates respect string toise)SQL injection and XSS attacks become type errors instead of security
vulnerabilities.
y handles escaping based on the 
Booleans are strongly typed, just like everything else. There are no
"truthy" or "falsey" values. Booleans come from literals and operations
that result in booleans.

The (builtin) conditionals expect boolean types. No trying to guess if a 
string like `"0"` represents true or false. (Although when you want this,
write your own simple conditional operators.)

The language allows question marks in valid tokens. Use consistent naming
instead of marking up functions and values with "is" or "has" or "was"
naming conventions.snerabilities.

### Booleans Without Surprises

Boolean logic works the way you expect, without JavaScript-style "truthiness" confusion.

```comp
active? = #true                         ; Explicit boolean values
ready? = count > 0                      ; Clear comparisons
valid? = name != "" && email != ""      ; Logical combination
; No implicit conversions
result = Empty strings aren't false. Zero isn't false. Only `#false` is false, and only
`#true` is true. The language makes this correct and convenient.isn't false. Only `#false` is false, and only `#true` is true. This eliminates a whole class of subtle bugs that plague other languages.

## See It All Working Together

This example shows how Comp's features combine naturally:

```comp
!import /gh = comp "github-api"
!import /time = std "core/time"

!main = {
    @after = (|now/time) - 1#week
    @fields = {"title" "url" "created-at" "reactions"}
    
    {..@fields repo="nushell/nushell"}
    |list-issues/gh
    |filter :{created-at >= @after}
    |<<progressbar              ; Add progress tracking
    |map :{
        @thumbs-up = reactions |count-if :{content == #thumbs-up}
        {thumbs-up=@thumbs-up title=. url=.}
    }
    |<<debug                    ; Development logging
    |first 5
}
```

**What's happening here:**
- Variables store computed values (`@after`, `@fields`)  
- Structures compose cleanly (`{..@fields repo="nushell/nushell"}`)
- Pipelines chain operations naturally (`|filter :{created-at >= @after}`)
- Pipeline modifiers add capabilities without changing logic (`|<<progressbar`, `|<<debug`)
- Blocks capture scope and simplify syntax (`:{created-at >= @after}`)
- Field shorthand reduces noise (`title=.` for `title=$in.title`)
- Everything composes seamlessly

## Ready to Dive Deeper?

This overview shows you what makes Comp distinctive. Each concept has rich depth detailed in the design documents:

- **[syntax.md](syntax.md)** - Syntax rules, style guide, and formatting conventions
- **[type.md](type.md)** - Numbers, strings, booleans, and unit systems
- **[structure.md](structure.md)** - Structure operations, spreads, and lazy evaluation  
- **[shape.md](shape.md)** - Shape system, morphing, and structural typing
- **[tag.md](tag.md)** - Hierarchical tags and polymorphic dispatch
- **[pipeline.md](pipeline.md)** - Pipeline operations, failure handling, and the wrench operator (`|<<`)
- **[function.md](function.md)** - Function definition, dispatch, and composition
- **[module.md](module.md)** - Module system, imports, and namespaces
- **[trail.md](trail.md)** - Advanced navigation through complex data
- **[store.md](store.md)** - Controlled mutable state when you need it
- **[security.md](secuComp is currently in design phase—these documents describe the intended behavior
that will guide implementation. The foundations are solid, the vision is clear,
the reality is still coming together.ibe the intended behavior that will guide implementation. The foundations are solid, the vision is clear, and the potential is exciting.