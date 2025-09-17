# Comp Language Implementation

Comp is a functional, interpreted programming language designed for transforming
and validating data in pipelines. It combines the flexibility of dynamic
scripting with the safety of static types, making it ideal for data processing,
API integration, and anywhere structured data needs to flow reliably between
systems.

There is currently no implementation and design is under heavy iteration. The
initial implementation will be writtin in Python, and comfortably bridge between
native Comp modules and the Python runtime.

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
* Modules provide namespaced functions like `:os/getenv`
* String interpolation, fallback values with `|`, and more

**Testimonials**

> This might be one of the most information-dense yet readable
> "hello world" examples in any language!
>
> — Claude Sonnet 4 _(on an admittedly enthusiastic moment)_

## Highlights
The best detail and overview is in the [design/](design/) directory. Specifically,
[design/overview.md](design/overview.md) makes the best starting point.

- **Super Structures** - All Comp values are immutable structures that unify
  hashmaps, arrays, iterators, and single values into one flexible container.
  High-level operators make it simple to filter, combine, and reshape data
  without mutation or complex state management.
  `{1 2 final="three"}`

- **Strongly Typed Schemas** - Declarative shapes act as schemas for your
  data. Comp's morphing system automatically validates and transforms any input to
  match expected types. Basic values are strongly typed with powerful units
  and constraints to catch errors at compile time. 
  `{15#seconds "<b>accordingly</b>"#html} ~event-data`

- **Pipeline Operators** - Chains of operations are assembled into intuitive
  pipelines high level controls for branching and failure management. Every
  statement takes one value and and produces one output value.
  `data -> :validate => :compact-each |> {placeholder=#true} -> :save`

- **Freeform Code** - Split and reorganize code without friction. Every function
  is self-contained - no forward declarations, no import cycles, no header
  files. Break large functions into smaller ones at any boundary, move them to
  separate files whenever needed. The !ctx system means refactoring is just
  cut-and-paste. `!ctx.server.port = 8000`

- **Zero-Config Projects** - A minimal hello.comp file is a complete runnable
  application, an importable module, and a developer package with tooling
  support. Import directly from local paths, git repos, or registries. Scale
  from one-file scripts to multi-file projects without restructuring.
  `!mod.package = {name="Amazing" version="1.2.1"}`

### Standout Features

- **Units That Actually Work** - Math with real units that prevent bugs:
  `30#grams + 5#pounds` works, `time1+#timestamp + time2+#timestamp` 
  correctly errors. Origin vs offset units catch entire classes of errors at 
  compile time. 
  `time2+#timestamp - time1+#timestamp -> duration#seconds`
- **Query Data Like DOM** - XPath-inspired selectors work on any structure.
  Extract, filter, and transform nested data without nested loops. 
  `data / /users[age>25]/name/`
- **True Polymorphism** - Functions dispatch on actual data shape, not class
  hierarchies. Any data source is an equal citizen, the data is the class,
  no wrapping data behind interfaces, accessors, and boilerplate.
  `{pt1 pt2 pt3} ~geom/triangle -> :geom/area`
- **Transactions** - Language rolls back data structures and external resources
  on failures.
  `!transact $database, $search_index {user -> :db/update}`
- **Permissions** - Language can revoke permissions to access the external
  system before calling into restricted functions.
  `!drop network, write $handlers => :process-untrusted` 

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

