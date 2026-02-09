# Comp

_You should be skeptical._ This is an experiment, not a production tool. But if
you've felt friction writing robust Python—not with Python itself, but with the
ceremony it takes to get there—these ideas might interest you. Type hints that
don't quite catch what you need. Defensive None checks everywhere. Dataclass
definitions that need pydantic that need mypy. Each layer solves a real problem.
Together, they're more scaffolding than logic. Comp asks: what if the right
primitives eliminated the scaffolding?

- **Shaped** types, validation, and docs in one declaration
- **Immutable** no defensive copies, no mutation surprises
- **Declarative** imports and namespaces resolve at build time, not runtime
- **Typed Sources** config files and API specs become validated modules
- **Pipelined** data flows through transformations, not method chains

This runs inside Python, not instead of it. The goal isn't replacement, it's
handling the compositional, data-heavy parts with less ceremony. Syntax breaks
regularly. The interpreter is incomplete. But if language design interests you,
or if you've wanted a CoffeeScript for Python, there might be something here.
See more in [Why Comp?](WHY.md).

[MIT](LICENSE)

## Example

Inspired by Julian Hofer's excellent Nushell tutorial for browsing GitHub
issues:

```comp
/// Display recent starred issues from a GitHub repository.
// Inspired by https://julianhofer.eu/blog/2025/nushell/

!import gh {comp "github-comp@1.0.2"}
!import table {comp "table"}

!startup main (
    !let repo "nushell/nushell"
    !let cutoff (datetime.now - 1[week])
    !let fields {"created-at" "reaction-groups" "title" "url"}
    !let thumb "👍"

    gh.issue-list[repo=repo fields=fields]
    | where ($.created-at >= cutoff)
    | insert-each[
        'thumb' = ($.reaction-groups | tally ($.content == "thumbs-up"))
    ]
    | sort-by[thumb reverse]
    | first[5]
    | table.markdown
)
```

## Core Concepts

### Whitespace Independent

The grammar builds from a simple foundation: containers are whitespace-separated
fields. There are no line-based statements, significant indentation, or
separators. Everything builds on this, creating something lightweight and
flexible. The language has no keywords and prefers kebab-case.

```comp
!let point {3 4}
!let current-player {name="pete" score=100}
```

### Basic Types with Units

Comp provides tags, text, and numbers. Tags are hierarchical enumerations, text
is unicode strings, and numbers are precision-safe and hardware-independent.

Units extend these types with labels that control how values combine and
convert. Constants like `true` and `false` are just defined and extensible tags.

The traditional mathematic operators exist, but are only valid on numeric
values. There are separate operators for text, tags, and structures.

```comp
!let timeout 30[seconds]
!let cutoff (datetime.now - 1[week])
!let bytes $size[mb][bytes]
```

### Structures and Shapes

Comp's unified `struct` container holds both named and unnamed fields.
Comparable to Python's combined positional and keyword arguments, but as a data
structure. Every structure is immutable.

Shapes define what data looks like, not what it "is." Functions dispatch based
on whether data matches their declared shapes. Data from files, databases, or
HTTP responses works interchangeably with literals in your code.

```comp
!shape point ~{x~num y~num}
!func process @input~point ($ | "Point at $($.x), $($.y)")
```

### Pipelines and Blocks

Data flows left-to-right through a pipeline of transformations. Blocks `(| ...)`
are anonymous sub-pipelines that can be composed, passed around, and applied
later.

```comp
!let transformer[$ | from-json | where[$.active] | select {"name" "score"}]
data | $transformer | process
```

### Failure Handling

Failures propagate automatically until caught—more like fast-forwarding than
stack-unwinding. Lightweight operators handle failures where it makes sense.
Failure types form an extensible hierarchy using shapes.

```comp
config.timeout ?? 30                            // fallback for any failure
fetch-data ??(timeout) cached-data              // catch specific type
load |?(network) ($ | retry[times=3] | process) // mid-pipeline handling
```

### Declarative modules

Modules define a declarative namespace that is validated and optimized at build
time. This is combined with imported modules to generate a definitive namespace
for code to run in. Modules do not need to deal with definition orders or other
annoyances. Comp takes advantage by generating flexible naming for references
that are guaranteed to be correct.

Comp modules are also their own self-contained package format. A single file
is enough to manage dependencies, metadata. Modules may contain an extensible
list of entry points to manage running unit tests, command line, servers,
and more.

The language separates operations with side effects into opaque handles.
This allows simple definition of build time processing.

These are combined to generate comprehensive error checking and validation
that happens at build time, not run time.

Everything in a module is known before execution. Imports, definitions,
references—all resolved at build time. A whole category of runtime errors
becomes build errors. References can use shortened names when unambiguous:
`types.boolean.true` can be just `true` when nothing else conflicts.

## Quick Start

With [uv](https://github.com/astral-sh/uv):

```bash
git clone <repo>
cd comp
uv pip install -e .
uv run comp examples/tree.comp
```

## Why is this named "Comp"?

No deep meaning, it's short and it wasn't taken. Choose any combination of
"comp" words and you've got a good definition.

- Compose
- Compile
- Components
- Compelling
- Compute

Studios that generate computer graphics often use procedural compositing
applications; which often embed Python interpreters. These embody many of
the familiar concepts and ambitions for the language.

Sadly, "complete" is not yet a matching adjective.

## Inspirations

- **Python** — what's possible with an amazing language and interpreter
- **Nushell** — shell pipelines with structured data
- **Cue** — declarative configuration with unification
- **Clojure** — immutable data, functional transformation
- **Houdini** — procedural node graphs for assembling operations

The goal isn't to copy any of these, but to discover what emerges when you
combine declarative data, typed pipelines, and shell-like ergonomics.
