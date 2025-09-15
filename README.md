# Comp Language Implementation

The Comp language is a complete programming language with standard libraries. It
is built around the concepts of immutable structures and pipelined function
chains with a focus on developer approachability and consistency.

There is no implementation and design is under heavy iteration. The initial
implementation will be writtin in Python, and comfortably bridge between native
Comp modules and the Python runtime.

The language is high-level and practical, inspired by JavaScript and Python's
accessibility. Developers familiar with functional languages like Clojure will
recognize the emphasis on data transformation and uniform syntax.

## Introduction

```comp
; Hello World example in Comp language

!main = {
  $names = {"USERNAME" "USER" "LOGNAME"} => :os/getenv 
  $names -> {.iter:any | "World"} -> "Hello ${}" 
    -> :io/print
}
```

This Hello World has a few more frills than usual - it attempts to find a
username from common environment variables. From this small example you can see:

* Whitespace is completely optional and flexible
* Functions are invoked with -> (single) and => (collection) operators
* Other modules provide namespaced functions like `:os/getenv`
* String interpolation, fallback values with `|`, and more

**Testimonials**

> This might be one of the most information-dense yet readable
> "hello world" examples in any language!
>
> — Claude Sonnet 4 _(on an admittedly enthusiastic moment)_

## Highlights

The best detail and overview is in the [design/] directory. Specifically,
[design/overview.md] makes the best starting point.

- **Everything is Data** - All values are immutable structures that flow through
pipelines. These structures unify concepts from hashmaps, arrays, and objects
into one flexible container. Data from JSON, SQL, or APIs becomes immediately
usable without parsing or mapping layers.

- **Pipeline Operators** - Transform data with intuitive left-to-right flow
using `->` for single values and `=>` for collections. No more nested function
calls or intermediate variables. Write `data -> validate -> transform -> save`
instead of `save(transform(validate(data)))`.

- **Shape System** - Define expected data shapes once, use everywhere. Shapes
act like interfaces that any structure can satisfy, regardless of source. The
same shape validates JSON input, database results, and function parameters with
automatic morphing between compatible types.

- **Pattern Matching Built-in** - Tags provide hierarchical enums with built-in
pattern matching. Write `status ~ #error#timeout` to match error subtypes, or
use shapes to destructure complex data in function signatures. No verbose switch
statements needed.

- **Zero Friction Modules** - Each `.comp` file is a complete, declarative
module. No build system, no package.json, no headers. Import directly from git
repos, local paths, or registries. The compiler handles versioning and
dependencies.

### Secondary Callouts

Besides the core design, Comp includes powerful features that eliminate common
pain points:

- **Path Selectors** - Query nested data with syntax inspired by XPath/CSS
  selectors.
- **Transactions** - Immutable data makes transactions and rollbacks reliable.
- **Unified numbers** - Single number type handles int/float/decimal with
  optional units.
- **Compile Time Execution** - Run functions at compile time for zero-cost
  abstractions.
- **Polymorphism without Classes** - Function overloading based on shapes, not
  inheritance.


## Project Structure

```
comp/
├── specs/              # Language specifications (0%)
├── examples/           # Theoretical examples in a wide variety
├── design/             # Design documents (70%)
├── tasks/              # Implementation tasks (0%)
├── src/                # Implementation source code (0%)
└── docs/               # Documentation and design notes
    ├── ancient/        # Super old notes extracted from notion (100%)
    └── early/          # Iterative design docs from claude (70%)
```

