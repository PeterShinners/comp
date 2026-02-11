# Comp Language

This project explores a programming language that could improve on the ideas
that make Python so great to work with. I enjoy my decades of experience with
Python, but I find writing clean and composable code requires clumsy repetition
and ceremeny and boilerplate. The type hints, the dataclasses, the defensive
checks and repetitive declarations are getting in the way. What if robust
patterns and designs could be the default instead?

A language should be its own best example. The Comp standard libraries
should reflect what your own good code should look like.

Comp runs inside Python, comfortably interopting in both directions. The
syntax and interpreter are still evolving, but if language design interests you
or you've wanted a CoffeeScript for Python, there might be something here.

## Example

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
    | where ($created-at >= cutoff)
    | insert-each[
        'thumb' = ($reaction-groups | tally ($content == "thumbs-up"))
    ]
    | sort-by[thumb reverse]
    | first[5]
    | table.markdown
)
```

## Concepts

Comp is exploring for the correct primitives to reduce scaffolding and improve
the developer experience.

**Types are validation** In Python, you define a dataclass, add pydantic for
validation, add type hints for the checker. In Comp, [shapes](design/struct.md)
do all three: definition, validation, documentation. Data matches a shape or it
doesn't — whether it comes from literals, JSON, network requests, or databases.

**Immutable by default** No more defensive copies, no wondering if a function
mutated your data, no `frozen=True` with its gotchas. Everything in Comp is
immutable. The [decorator system](design/struct.md#decorators) makes producing
modified copies feel as easy as mutation — `@update` merges changed fields onto
the original.

**Lightweight syntax** A refined and lightweight syntax that is not stuck on
indentation or line based statements. Get rid of the separators and noise. The
language has no keywords to get in the way of working with fields and data.

**Namespaces are declarative** No circular import tangles or import order
puzzles. No evaluating code to know what a module contains. Comp's
[modules](design/module.md) are declarative — everything is known at build time,
references resolve before execution. Combined with [pure
functions](design/function.md), much of the language becomes a powerful
build-time exercise.

**Flow control is functions** Use general library functions for flow
control, iteration, and more. Extend the ones that are there, build entirely new
conveniences for conditionals. The language provides minimal conditionals based
on type dispatch; you build the rest (or not). The language embraces pipelines
and puts data at the center instead of itself.

## Go Further

If this resonates, look at the [examples](examples/). The syntax is still
shifting, but the concepts are taking shape.

- [**Syntax and Style**](design/syntax.md) brackets, operators, formatting,
  the grammar rules
- [**Structures and Shapes**](design/struct.md) immutable data, type system,
  tags, decorators
- [**Functions and Blocks**](design/function.md) pipelines, dispatch, streams,
  invocation
- [**Modules and Imports**](design/module.md) namespaces, dependencies, schema
  imports
- [**Core Types**](design/type.md) numbers, text, booleans, comparison, units

