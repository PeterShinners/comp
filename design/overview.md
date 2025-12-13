# Comp Language Overview

## Features

Comp is born from an excercise to improve the state of developing in high level
languages like Python. This requires new ideas and behaviors to avoid the ruts
and common errors these languages encourage. The goal is a lightweight and
readable language that prioritizes the developer experience.

```comp
--- Get top weekly thumbed issues from GitHub
Based on: https://julianhofer.eu/blog/2025/nushell/#format-table-in-markdown-format
---

import.gh = ("github-api" comp)
import.time = ("core/time" stdlib)

main = :(
    var.after = time.now() - 1(week)
    var.fields = (created-at title url reactions)

    gh.list-issues(repo="nushell/nushell" fields=var.fields)
    |filter :issue (issue.created-at >= var.after)
    |map :repo (|mix 
        repo
        num-thumbs = repo.reactions |count :react (react.content == thumbs-up)
    )
    |sort(reverse) :repo (repo.num-thumbs)
    |first(5)
    |rename-fields(num-thumbs="👍")
    |to-markdown()
    |print()
)
```

Not all the motiviations are easy to describe, but there have been several
primary driving guidelines.

Clean and consistent syntax with minimal noise and no whitespace dependence.
This removes delimiters and allows structuring code in any desired style. It
also works hard to avoid unnecessary nesting of braces and structures.

Everything is stored in a powerful structure class and the data is all
immutable. The struct container allows both named and unnamed fields and
ordered. Even functions (executable blocks) use the same syntax as structure
literals.

Data is the same wherever it comes from. There are no classes or hierarchies,
function calls, dispatch, and behaviors are all based on the shape of the data.
Schemas define and dispatch behaviors and work the same whether the data comes
from code literals, database lookups, networked json, or api calls.

A strictly declarative namespace. The language takes advantage of knowing
everything referenced and imported. No code execution is needed to define and
create all references. This also moves a large class of high level language
errors to build time, and even more available with static analysis.

A comp file is also its own package definition. A project can be defined by a
single source file, or be split into flexible directories and organized however
the authors see fit. Import dependencies from immediate directories or reliably
across the internet.

Flow control and conditionals are implemented as regular functions. This keeps
the language minimal and lightweight. Enhance the builtin looping or match
operations with your own, or replace them entirely. The standard library prides
itself on being written in clean and idiomatic style.

Comp is at home in Python. Interoperate closely with any running interpreter.
Access existing modules, or replace them with better implementations and use
those from Python.

## Structures and Shapes

The struct container combines a variety of behaviors into a single container. It
can describe sequences, hashmaps, unordered sets, and more.

A struct is an immutable piece of data. The language provides regular functions
to combine and edit structures into new pieces of data.

Comp allows defining shapes which define the required shape for data. Functions
define required shapes for their arguments which allows rich validation. The
shapes themselves can be constructors to morph and modify data from one shape to
another.

Shapes are defined as literals prefixed with a `~` tilde, although they contain
slightly different grammar rules than a regular struct. A shape definition is
actually sugar for a function definition that automatically converts data.

The [Struct and Shape](struct.md) documentation contains much more information
like applying modifiers to shapes, morphing rules, and indexing into structures.

```comp
42  -- Auto-promotes to (42)
(x=10 y=20)  -- Named fields
(1+1 2+2 3+3)  -- Positional fields  
(name="Alice" 30 is-active=true)  -- Mixed data

player = ~(name~text score~num=0)  -- Define a shape
optional-text = ~(text | nil)  -- Union types (shapes)

spawned = player("PET")  -- Promote simple data into our shape
```

### Pipelined Functions and Blocks

Any structure literal can become a callable object by prefixing the structure
with `:`. These can be used as functions which get assigned into the module
namespace, or used as anonymous blocks as simple callbacks.

By default these callable structs take no arguments and can return any type of
data. Optional definitions can be added to define required shapes for the
arguments as well as additional behaviors and identifiers.

Multiple functions can be overloaded with the same name. The namespace keeps
track of them separately. By determining the matching shapes of data function
calls will automatically dispatch to the most specific implementation.

Calling functions and blocks requires a struct of argument but can optionally be
combined with blocks that are added to the argument list. This allows function
blocks to be passed as arguments for natural feeling flow control, iteration,
and other behaviors.

Functions and blocks can be assembled into a pipeline of operations using the
`|` pipe operator. Functions can also specificy special links in the pipeline to
allow additional behaviors when combined. The pipeline itself is a malleable
data structure that can be explicitly rewritten and enhanced with special
operators.

Pure functions can be defined that are restricted from accessing external
handles. These functions can be evaluated at build time and other special
contexts.

The [Functions and Blocks](function.md) contains more details like overloaded
dispatch, input and argument management, and runtime scopes.

```comp
welcome-new-users :users~user[] (
    -- Act on all recently registered user entries
    var.recent = now () - 1~week
    users 
    |filter :u (u.member_since > recent)
    |each :u (send-welcome-email(u))
    |-|progressbar()  # Wrench to inject progress tracking
    |log("Finished greeting $(in | length()) recent users")
)
```

## Modules and imports

Modules define a namespace that is declarative and predefined. This allows
defining functions, shapes, and data in any order. It also allows validation and
resolving of direct and imported references.

Define and use symbols in any order. Access and override symbols from
dependencies. All is validated and assembled and built time.

A module can be a single, standalone file. It can also be defined by a directory
of comp files. These files are combined in an order independent way that is
treated as a single module source.

Traditional languages resist code organization through strict import orders and
inflexible namespaces. Define functions, shapes, and data in any order across
any file. The results are declarative and validated without needing to execute
logic.

The importer allows an extensible set of compilers that allow reliable
namespaces from python modules, openapi specifications. Any of these types can
come from the network, filesystem, package libraries, git repositories, and
more. Let the import machinery and builtin packaging tools provide consistent
environemnts, reliable caching, and secure validation.

```comp
# Use data from everywhere seamlessly
import.str = ("core/str" std)
import.pygame = ("pygame" python)
import.api = ("http://api.example.org/v1" openapi)
import.time = ("core/time" std)
import.mars = ("github://offworld/martiancalendar" comp branch="edge")

# Access through simple namespaces
mod.token = "username" | fetch-auth-token () | base64/str ()
mod.now = now/time () ~num#day/mars
```

## Other unique idioms

- Structure literals can define internal temporary values by assigning and
  referencing them from the `var` namespace, like `var.counter = 1`. This
  obviously works for function/block definitions as well.
- Structure literals may begin with a special `|modifer` which defines
  operations that modify the contents or behavior of the resulting structure.
  Common ones like `|val` just uses the final result as the outgoing structure.
  Define your own.

## Types

Comp provides several lower level data types. The primary ones are numbers,
text, and tags.

These values can be passed around and used outside of structs. In most contexts
they can also be used inside simple structures with single values.

More details and a look at other builtin types are in the [Types](type.md)
documentation.

### Proper Numbers

The `~num` numeric type uses big precision numbers with accurate and correct
fractional values. The types are not restricted by tranditional computer
hardware limitations. Avoid overflows, inaccuracies, clamping, and other
mathematical problems. Opt in to special non-numeric values like "infinity" only
where specifically allowed.

Comp provides most standard numeric operators to add, multiply. These operators
only work with numbers. There are also libraries of functions to work with
numbers and large collections of data.

Number types can be extended by units, which allow defining measurements and
hardware representation restriction to numbers. Use this unit type system to
avoid mixing distance values with time values. This also allows automatic
conversion between compatible types, like kilometers and miles.

```comp
huge = 999_999_999_999_999_999_999_999  -- No overflow
precise = 1/3  -- Exact rational arithmetic
scientific = 6.022e23  -- Standard notation
binary = 0b1010  -- Binary literals
speed = 100~seconds  -- Units become additional types for data
duration = endtime - starttime  -- Becomes a relative time offset
```

### Text and Templates

Text is represented as immutable streams of unicode characters. Provided
libraries allow the standard searching, editing, and formatting of textual data.

Text can optionally be decorated with constraints that can influence how the
strings are used. This marks text with domains to enforce safe formatting and
substitution. Vulnerable SQL injection and XSS code becomes type errors instead
of security vulnerabilities.

```comp
name = "Alice"  -- Regular string
query = "SELECT * FROM users"~sql  -- SQL-aware string
html = "<div>Content</div>"~html  -- HTML-aware string

-- Templates respect string types
message = fields | format(my-select)  -- Proper escaping
```

### Tags

Tags are declared constants that can be identified uniquely. These are often
defined in named hierarchies. They work similar to enumerations and play a dual
role in the language, acting as both values and shapes.

The language provides additional builtin types and shapes that are actual tags.
Tags like `true` and `false` are the builtin boolean types.

Tag hierarchies can be extended by external modules, independently from the
initial definition.

When matching and morphing data into shapes, tags get a special priority for
matching fields. This allows tags to be arbitrarily added into data structures
and have a high influence on how shapes are matched and functions dispatched.
This allows tag fields to be used like polymorphic classes and dispatch
appropriately.

Tags are also used as the foundation for referencing external and system data,
that lives outside the control of the language.

```comp
-- Define tags
tag.ok = ~()
tag.error = ~()
tag.pending = ~()

-- Hierarchical tags
tag.visibility = ~(all active)
tag.visibility.complete = ~()

-- Use them as values
current = pending
mask = visibility.all

-- Use them as types in shape definitions
arguments = ~(vis~visibility = visibility.all)
```
