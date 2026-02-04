# Comp

Comp is a programming language experiment. After decades of Python, I still love
it—but writing clear, composable code increasingly fights against the grain. The
patterns I want require unwanted ceremony and feel heavy. Python still *allows*
me to program how I want, but the results less and less idiomatic.

But what would work better? I don't think it has been invented yet. Comp runs
natively inside a Python interpreter but brings genuinely different ideas to the
table. The goal: a lighter-weight language that's easier to read and reason
about.

- Whitespace-independent grammar
- Declarative namespaces resolved at build time
- Immutable values throughout
- Unified `struct` container for all data
- Typed shapes for matching and transformation

**This is experimental.** Examples exist and work, but syntax and rules break
frequently.

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
  $repo = "nushell/nushell"
  $cutoff = datetime.now - 1[week]
  
  | gh.issue-list repo=$repo fields=t"created-at reaction-groups title url"
  | where (| $.created-at >= $cutoff)
  | insert "thumbs-up" (| $.reaction-groups | count-where (| $.content == "thumbs-up"))
  | sort-by "thumbs-up" reverse
  | first 5
  | table.markdown
)
```

## Core Concepts

### Whitespace Independent

The grammar builds from a simple foundation: containers are whitespace-separated
fields. No line-based statements. No significant indentation. No semicolons or commas.
Everything builds on this, creating something lightweight and flexible. The
language has no keywords and prefers kebab-case.

```comp
$point = {3 4}
$current-player = {name="pete" score=100}
```

### Basic Types with Units

Comp provides tags, text, and numbers. Tags are hierarchical enumerations. Text
is unicode. Numbers are precision-safe and hardware-independent.

Units extend these types with labels that control how values combine and
convert. Even `true` and `false` are just tags—no magic keywords.

```comp
$timeout = 30[seconds]
$cutoff = datetime.now - 1[week]
$bytes = $size[mb][bytes]
```

### Structures and Shapes

Comp's unified container holds both named and unnamed fields—think of it like
Python's combined positional and keyword arguments, but as a data structure.
Every structure is immutable.

Shapes define what data looks like, not what it "is." Functions dispatch based
on whether data matches their declared shapes. Data from files, databases, or
HTTP responses works interchangeably with literals in your code.

```comp
!shape point ~{x~num y~num}
!func process @input ~point (| $"Point at $($.x), $($.y)")
!func process @input ~player (| $"$($.name) scored $($.score)")
```

Same function name, different implementations selected by input shape.

### Pipelines and Blocks

Data flows left-to-right through transformations. Blocks `(| ...)` are anonymous
sub-pipelines that can be composed, passed around, and applied later. The `$`
references implicit pipeline input; `$.field` accesses its fields.

```comp
$transformer = (| from-json | where (| $.active) | select t"name score")
$data | $transformer | process
```

### Tags for Type-Safe Arguments

Tags route positional arguments by type, not position. A function expecting an
`ordering` tag will match `reverse` or `forward` wherever they appear in the
call—no need to remember argument order, and typos become build errors.

```comp
data | sort-by "score" reverse
data | sort-by reverse "score"    // same thing
```

### Failure Handling

Failures propagate automatically until caught—more like fast-forwarding than
stack-unwinding. Lightweight operators handle failures where it makes sense.
Failure types form an extensible hierarchy using shapes.

```comp
config.timeout ?? 30                           // fallback for any failure
fetch-data ??(timeout) cached-data             // catch specific type
load |?(network) (| retry times=3) | process   // mid-pipeline handling
```

### Side Channels

Some functions communicate through side channels—metadata flowing alongside the
main value. This enables patterns like `if`/`else` pairing and optional detail
extraction without cluttering the primary data flow.

```comp
value | if ($.score > 90) (| "A") | else (| "F")
message | replace {"error"="FAILED"} | details   // {changed=1 matches=...}
scores | do (| sum | print $"total=$()") | continue-processing
```

### Function Wrapping

Functions can inherit and customize another function's interface—essential for
building reusable abstractions. Remove parameters, override defaults, or add new
ones while preserving the wrapped function's documentation and behavior.

```comp
!func top-issues
@inherit gh.issue-list
  -fields
  repo="nushell/nushell"
@args ~{count~num=10}
(| gh.issue-list fields=t"created-at title" @pass | first $count)
```

### Declarative Namespaces

Everything in a module is known before execution. Imports, definitions,
references—all resolved at build time. A whole category of runtime errors
becomes build errors. References can use shortened names when unambiguous:
`types.boolean.true` can be just `true` if nothing else conflicts.

## Quick Start

With [uv](https://github.com/astral-sh/uv):

```bash
git clone <repo>
cd comp
uv pip install -e .
uv run comp examples/tree.comp
```

## Why "Comp"?

No deep meaning. It sits at the intersection of "compositing" (node graphs of
operations), "composable" (the design philosophy), and "computing" (the obvious
one). It's short and it wasn't taken.

## Inspirations

- **Python** — what's possible with an amazing language and interpreter
- **Nushell** — shell pipelines with structured data
- **Cue** — declarative configuration with unification
- **Clojure** — immutable data, functional transformation
- **Houdini** — procedural node graphs for assembling operations

The goal isn't to copy any of these, but to discover what emerges when you
combine declarative data, typed pipelines, and shell-like ergonomics.
