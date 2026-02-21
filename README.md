# Comp Language

Comp is an experimental project to build a general purpose, high level
programming language that works inside and alongside Python. It is definitely
inspired by Python with substantial new concepts. The goal is a developer
focused language that makes development better.

- **Lightweight syntax** Flexible syntax that with no delimiters, not line or
  indentation based, and avoids nesting.
- **Declarative** Defined namespaces avoid circular puzzles and moves problems
  to build-time, not run-time.
- **Builtin Schemas** Define your own shapes and data types, then use them to
  validate and transform your data.
- **Data Driven** Functions run on any compatible data; like having methods
  without the classes or casting hurdles.
- **Flow Control Functions** The standard library provides conditionals loops,
  and more. Or define and or extend your own.
- **Immutable values** Nothing is modified once it exists. The language has
  the tools to define modifications the easy and safe way.

One measure of a great developer language is how well the standard libraries
represent idiomatic and clean code. Comp aims for this excellence.

## Example

```comp
/// Display recent starred issues from a GitHub repository.
// Inspired by https://julianhofer.eu/blog/2025/nushell/

!import gh comp "github-comp@1.0.2"
!import table comp "table-formatter"

!startup main (
    !ctx repo "nushell/nushell"
    !let cutoff (datetime.now - 1[week])

    gh.issue-list :fields={"created-at" "reaction-groups" "title" "url"}
    | where :($created-at >= cutoff)
    | map :($thumbs-up = $reaction-groups | count :($content == "thumbs-up"))
    | sort :reverse :($thumbs-up)
    | first :5
    | select :{"thumbs-up"="👍" "title" "url"}
    | table.markdown
)
```

## Additional Concepts

Comp's novel features have been carefully assembled into a language that
minimizes developer friction and maximizes composability.

- **Struct** The structure container works as an array and a mapping.
- **Tags** Predefined, hierarchical enumerations.
- **Failures** Easier to handle than traditional exceptions.
- **Contexts** Tracked data that work like typed environment variables at any level of the language.
- **Documentation** Comments follow Rust rules for identifying documentation.
- **Overloadeds** Alternative implementations avoid conditional nests.
- **Wrappers** Like decorators but for statements, not just functions.
- **Blocks** Any statement is a deferred block and passed to functions for evaluation.
- **Imports** Powerful import system integrates with downloads, caching, and more.
- **Compilers** Multiple compilers allow compile time access to other languages and data formats.
- **Formatting** Rich text formatting functions are built in.
- **Purity** Simple functions with no side effects, that integrate with language features.
- **Kebab Case** Use idiomatic `kebab-case` for identifiers and fields.
- **Functional** Practical and composable pipelines.
- **Numbers** Represented as hardware independent values of lossless precision.
- **Units** Extensible subtypes attached to values, like units of measurement.
- **Limits** Extensible type requirements like minimum values, managed at build time.

## Discover

There [examples](examples/) provide a variety of lightweight, real-world concepts.

The [design](design/) documents go into all these concepts in further detail.

- [**Syntax and Style**](design/syntax.md) brackets, operators, formatting, the grammar rules
- [**Structures and Shapes**](design/struct.md) immutable data, type system, tags, decorators
- [**Functions and Blocks**](design/function.md) pipelines, dispatch, streams, invocation
- [**Modules and Imports**](design/module.md) namespaces, dependencies, schema imports
- [**Core Types**](design/type.md) numbers, text, booleans, comparison, units

## Design

What a fantastic journey this has been. There's so much potential for Comp, but it
still has a long way to go. Along the way I've been introduced to a massive amount
of great ideas. I'll call out a few special acknowledgements.

- **Python** is where I get the most out of my development.
- **Nushell** such a spectacular job with their syntax and approachability
- **Rhombus** showing me all these functional ideas in a style I appreciate
- **Cue** really kicked off so many ideas of merging data and definition

## Getting Started

Any Python interpreter is a home for Comp. The runtime and tools run as regular
Python modules themselves.

```bash
$ uv install comp-lang
$ uv run comp hello.comp
```

> Unfortunately, comp hasn't landed in Pypi yet, so for now that means
  clone the git repository for yourself.
