# Comp Language

Comp is a functional, interpreted programming language designed for general
purpose computing. It combines the flexibility of dynamic scripting with the
safety of static types, making it ideal for data processing, API integration,
and anywhere structured data flows reliably between systems.

The language is high-level and practical, inspired by JavaScript and Python's
accessibility. Developers familiar with functional languages like Clojure will
recognize the emphasis on data transformation and uniform syntax.

## Development Status

The language design is fairly established documented in the `design/` directory.
Implementation is currently underway using an agent-assisted development in a
roadmap with multiple chapters and phases. 

## Quick Start

Install and run Comp programs with `uv` (recommended)

```bash
uv pip install -e .
uv run comp examples/working/hello.comp
```

## Introduction

```comp
; Hello World example in Comp language

!main = {
    @names = {"USERNAME" "USER" "LOGNAME"} |map .{|getenv/os}
    @greeting = (@names |any ?? "World")
    
    %"Hello ${@greeting}!" |print/io
}
```

This Hello World attempt to be extra personal by looking for a login name
from a series of environment variables.

**Testimonials**

> This might be one of the most information-dense yet readable
> "hello world" examples in any language!
>
> — Claude Sonnet 4 _(on an admittedly enthusiastic moment)_

## Highlights

Start with the [Overview Document](design/overview.md) for the best summary
of features and highlights like:

- **Super Structures** - One type of data for all your data.
- **Typed Schemas** - Data is matched and morphed based on explicit schemas.
- **Pipelined** - When everything is in a pipeline, everything fits together.
- **Flow Control is Functions** - Write or extend your own loop operations, although the standard library has you well covered.

## Project Structure

```
comp/
├── design/             # Authoritative language design documents
├── examples/           # Sample Comp programs
├── tasks/              # Implementation phases and milestones
├── tests/              # Executable test specifications
├── src/                # Implementation source code
├── docs/               # Additional documentation
└── vscode/             # Syntax plugin (textmate) for VSCode
```