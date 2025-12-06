# Comp Language Overview

## Features

Cleaner and simpler code that gets more work done. This high level language
focuses on removing developer friction. Simple and consistent high level
features with more build-time validation than similar high level approaches. The
language is whitespace independent, doesn't use separators, and avoids nested
braces.

Organize and style your code so it can look its best. Split and manage your
files in any style with no worries about circular imports or definition orders.
The language features allow splitting code into functions and files with any
desired structure and granularity.

Each module defines a declarative namespace that can be queried and validated
before runtime. A module is its own package definition, with dependencies and
metadata available for analysis. This data remains usable even when paired with
common syntactical and grammar errors within the file.

A minimal language definition that builds on itself. Everything is stored in
structures, even functions are just deferred structure literals. Flow control,
iteration, compilation and more are built in Comp. Easy to extend, customize,
and redefine for your own use cases.

Access system and external resources through handles. Anything that changes
state outside of the language is a resource. Alternatively, code that doesn't
need these resources is considered "pure" and runs without limitations, even at
build time. The handles can also participate in language level transactions;
rollback everything on failures, including data structures.

Comp is at home in Python. Interoperate closely with any running interpreter.
Access existing modules, or replace them with better implementations and use
those from Python.

```comp
There are many hello worlds, and this one is mine
___

import.hello = {"examples/hello" comp}

# Line comments use colons

main = :{
    gps_detect_planet {}
    | capitalize {}
    | print {"Greetings, ${}"}
}

gps_detect_planet = :{"earth"}

```

Save as `hello.comp`, run with `comp hello.comp`. That's it. No build files, no
configuration complexity, no dependency management, and no 30 file project
templates to navigate. Projects grow from here in flexible ways, only when you
are ready.

## Guiding Design

### Structures and Shapes

Comp data is stored in one powerful and flexible structure type that combines
positional and named data into a single container. Structures are immutable with
rich operations that naturally create modified clones of data. Even functions
are defined as structures, which run as deferred code. Fields can have names or
be defined positionally, with optional types and default values.

Shapes define schemas for data using the `~` operator. Data can be tested and
converted between compatible shapes through structural matching—no inheritance
hierarchies or interface implementations required. Shape definitions are also
callable objects used to construct or convert data. For more details, see
[Structures and Shapes](structure.md).

```comp
42                     # Auto-promotes to {42}
{x=10 y=20}            # Named fields
{1+1 2+2 3+3}          # Positional fields  
{name="Alice" 30 active?=true}  # Mixed data
```

### Pipelined Functions and Blocks

A Comp function is a deferred structure that takes input data to create a
different structure. Function calls are chained together using the pipeline `|`
operator. Flow control like conditionals and loops are just regular functions,
and anonymous functions called "blocks" use the same syntax for inline behavior.

Multiple functions can overload with the same name, dispatching to the most
specific implementation based on incoming data shapes. The pipeline itself is
exposed as a structure that can be modified by "wrench" operators for
optimization, instrumentation, or progress tracking. For more details, see
[Functions and Blocks](function.md).

```comp

user = ~{
    A shape defines a schema, which can be used to define arguments
    ___
    name ~str
    email ~optional-text = nil
    age ~num~years
    member-since ~timestamp
    purchases ~num = 0
}

optional-text = ~{text | nil}  # Union types

welcome-new-users :users~user[](
    Act on all recently registered user entries
    ___
    var.recent = now () - 1~week
    users 
    | filter :u(u.member_since > recent)
    | each :u(u | send-welcome-email ())
    |-| progressbar ()  # Wrench to report progress tracking
    | print ("Finished greeting {in | length()} users")
)
```

### Tags: Enumerations and more

Tags are declared constants that can be identified uniquely. Like all data they
can be defined hierarchically.

They work similar to enumerations, but play several important roles in the
language. Tags play a dual role in the language, acting as both values and
shapes.

Tags also have a priority role when converting structures between different
shapes. With function overloading this allows tag fields to be used like
polymorphic classes and dispatch appropriately.

Tag hierarchies can be extended by external modules, independently from the
initial definition.

All values can be used as field names in structures, including tags.

```comp
# Define tags
ok = tag {}
error = tag {}
pending = tag {}

# Hierarchical tags
visibility.all = tag {}
visibility.active = tag {}
visibility.complete = tag {}

# Use them as values
current = pending
mask = visibility.all

# Use them as types in shape definitions
arguments = ~{vis~visibility = visibility.all}

```

### Modules and imports

Modules define a namespace that is declarative and predefined. This allows
defining functions, shapes, and data in any order. It also allows validation and
resolving of direct and imported references.

Define and use symbols in any order. Access and override symbols from
dependencies. All is validated and assembled and built time.

A module can be a single, standalone file. It can also be defined by a directory
of comp files. These files are combined in an order independent way that is
treated as a single module source. There are no circular imports or confusion
in these multi-file modules. There are no class definitions or forced groups
that restrict what can go into which file. Shared contexts allow exchanging
data without directly passing large amounts of state between the calls.

The language provides a rich and extensible set of compilers. Import Python
modules at runtime, OpenAPI specs downloaded from a website, git repostories
containing toml or some other format. The build time is when all the dynamic
handling and resolution happens, not at runtime. Let the runtime deal with
translating, caching, and packaging the external dependency.

```comp
# Use data from everywhere seamlessly
import.str = {"core/str" std}
import.pygame = {"pygame" python}
import.api = {"http://api.example.org/v1" openapi}
import.time = {"core/time" std}
import.mars = {"github://offworld/martiancalendar" comp branch="edge"}

# Access through simple namespaces
mod.token = "username" | fetch-auth-token {} | base64/str {}
mod.now = now/time {} ~num#day/mars
```

### Scopes

As code is executed, a variety of scopes are available to the running code.
These are always referenced through their fully qualified name, like
`mod.version` or `arg.verbose`. In some contexts different scopes can be
written to, like `ctx.server.port = 8000`. Remember that assignment doesn't
modify existing structures since they are immutable. Instead they construct a
new data with overlayed edits (and as much shared data as possible).

Functions optionally receive separate scopes for provded arguments and for
data passed through the pipeline. The block definition can define what name
these two structs will be assigned inside the body.

The pipeline data will always match the defined shape. It may also contain
extra data and fields..

The arguments struct is stricter and only contains explicitly defined fields.
The arguments can be contributed to by other scopes like `ctx` or `mod`
if they contain data that matches the defined shapes.

The special `var` context is used for storing temporaries inside the scope.
This scope is shared with any blocks defined inside the same function.

```comp
process-request = :in ~{request} arg ~{timeout ~num} (
    var.start = time {}  ; Function-local variable
    var.user = in.user  ; Another local variable

    {
        response = in | validate {} | process {}  ; Struct field
        duration = now {} - start;  Field computed from local
    }

    var.ctx.server.timeout = arg.timeout  ; Copy argument value to context scope
    var.config = mod.settings  ; Module-level constants
)
```

For the complete reference on how these scopes are managed, see [Syntax and
Style Guide](syntax.md).

## Working with Data

### Flexible Field Access

All data in comp is handled and performs the same. There is no first class
or secondary data. Data can come from network responses, database results,
parsed json. These all work equivalently to data defined in the code as
literals or assembled through function calls.

Struct data is hierarchical and allows deep references through the hierarchy.

There are several syntaxes for different types of fields in addition to
using tokens separated with `.` dots.

```comp
user.name  # Get the name field
settings.#0  # First item in a list
config.'config-field-name {"port"}' # Computed field name
data."New York"  # Field names with special characters or spaces
```

### Proper Numbers

Comp numbers work the way math actually works, not the way computer hardware
forces them to behave. Expect lossless precision and accurate computations.
Forget about overflows, rounding errors, or clamping.

Avoid special non-number values like "infinity" except for where you opt-in to
allowing them.

Numbers with units catch unit conversion errors at the type level.

```comp
huge = 999_999_999_999_999_999_999_999  # No overflow
precise = 1/3  # Exact rational arithmetic
scientific = 6.022e23  # Standard notation
binary = 0b1010  # Binary literals
speed = 100#seconds  # Units become additional types for data
duration = endtime - starttime  # Becomes a relative time offset
```

### Strings and Templates

Strings in Comp can carry information about what kind of data they represent.
This enables automatic safety features without manual work. The unit system
enhances strings by appropriately escaping substitutions by default.

```comp
name = "Alice"  # Regular string
query = "SELECT * FROM users"#sql  # SQL-aware string
html = "<div>Content</div>"#html  # HTML-aware string

# Templates respect string types
message = format {"Hello, ${name}!"}  # Automatically handles escaping based on context
```

SQL injection and XSS attacks become type errors instead of security
vulnerabilities.
