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

Comp data is stored in one powerful and flexible structure type. It combines
positional and named data into a single container. It combines the use cases of
iterators, sequences, and maps into a flexible container that does more and does
it uniformly.

Even functions are defined as structures, which run in as deferred code. A
structure definition can define and reference local temporary values, which
works comfortably for both literal values and function definitions. It combines
positional and named fields interchangeably. Imagine a data structure that could
describe arguments for a Python function.

Imagine a data structure that could define the argument signature for a Python
function. Fields can have names or be defined positionally. They can also have
optional types and optional default values.

Each structure is immutable, but has rich operations that naturally create
modified and minimal clones of data. Think of the way Python handles strings,
but now apply that to everything.

There are simple data types like numbers and text. These are also immutable, and
work interchangeably with simple structures that containing single, scalar
values.

Comp uses shape values to define a schema for data. Data can be tested and
converted between compatible shapes. The language doesn't use classes or
restrictive definitions, any function can be called an compatible data. Shapes
are defined using the `~` operator on a structure and can be referenced and used
like any regular value.

The `~` is used to define the shapes, and internally applied to individual
fields to define their own shapes.. No inheritance hierarchies, no interface
implementations—just structural matching that works intuitively. The shape
schemas provide strongly typed data validation in a way that is reusable and
expressive.

A shape definition is also a callable object which is used to construct or
convert data into the defined shape.

Structure literals can be defines with two syntaxes. The traditional uses curly
brackets `{}` to define individual fields. Parenthesis `()` can also be used
when assembling structures from predefined calls or data. Both can be used
interchangeably in function calls, argument definitions, or any place structures
are needed. They both produce the same structure object types, they just provide
alternative ways of getting to the same destination.

Structures are not classes. Comp has no traditional class definitions and
behaviors. There are ways to perform many similar operations that traditional
classes define, but they are done in a way that makes the data the priority, not
the code.

```comp
42                     # Auto-promotes to {42}
{x=10 y=20}            # Named fields
{1+1 2+2 3+3}          # Positional fields  
{name="Alice" 30 active?=true}  # Mixed data
```

### Pipelined Functions and Blocks

A Comp function is a deferred structure that takes input data to create a
different structure. Function calls are designed to be chained together using
the pipeline `|` operator. A deferred function is defined with a `:` preceding a
literal structure definition.

Flow control, like conditionals and loops, are just regular functions. The
language provides many traditional "if" and "map" looping operations. Users are
free to build on these for more specific operations, or create their own library
of helpers from scratch.

Functions can define special links that provide additional behevior, like `if`
`else` being separate functions, but coordinating together to create higher
level flow control.

Functions can be referenced and used like any value data. Anonymous functions
can also be created called "blocks". These use the same syntax as function
definitions and are often passed as argument to define behavior for functions
that perform flow control.

A function really is just a structure literal that runs at a later time. The
deferred structure also defines optional information about the shapes for
arguments. There are also flags, like "pure" which restrict a function from
using external resources, which can then be called during build time.

Multiple functions can overload with the same name. The language will dispatch
to the most specific implementation based on the incoming data shapes. Functions
can also wrap existing functions to inherit their behavior and definition, but
extend or change the functionality in some way; similar to middleware some
frameworks use.

The pipeline of functions is itself exposed as a structure, and can be recreated
or overridden by special "wrench" operators. These can optimize queries,
instrument code, or add progress tracking to a pipeline before it gets executed.

Calling a function or block is intended to look like an annotated structure
literal. A function reference is followed by a structure literal to define its
arguments. `sum {1 2 3}`.

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

### Field Access That Just Works

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

### Strict Booleans

Booleans are strongly typed, just like everything else. There are no "truthy" or
"falsey" values. Booleans come from literals and operations that result in
booleans.

The booleans are simply builtin tags named `true` and `false`. There is a
builtin union type named `bool` to represent either one as a type.

The builtin conditionals expect boolean types. No trying to guess if a string
like `"0"` represents true or false. (Although when you want this, write your
own simple conditional operators.)

The language allows question marks in valid tokens. Use consistent naming
instead of marking up functions and values with "is" or "has" or "was" naming
conventions.

```comp
active? = true                         ; Explicit boolean values
ready? = count > 0                      ; Clear comparisons
valid? = name != "" && email != ""      ; Logical combination
```

Empty strings aren't false. Zero isn't false. Only `false` is false, and only
`#true` is true. This eliminates a whole class of subtle bugs that plague other
languages.
