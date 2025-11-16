# Comp Language

Comp is a functional, interpreted programming language designed to improve the
lives and enjoyment of programmers. Combine the flexibility of dynamic scripting
with the safety of static types, making it ideal for data processing, API
integration, and anywhere structured data flows reliably between systems.

The language is hosted and integrated with the Python runtime. Anything 
running Python will be immediately improved by mixing in a bit of Comp.

## Development Status

The languge is in volatile design mode. Nothing is nailed down and everything
slides. The language design is fairly well established and documented in the 
`design/`. A variety of simple and approachable examples can be found in
`examples/`. Minimal VS Code extensions exist to get syntax highlighting
and formatting basics working..

## Introduction

```comp
; Hello World example in Comp language

main (
	[USERNAME USER LOGNAME]
	| map :(in | getenv() ?? #skip)
	| default("World")
	| print("Hello, ${}!")
)
```

This Hello World attempts to be extra personal by looking for a login name
from a series of environment variables.

**Testimonials**

> This might be one of the most information-dense yet readable
> "hello world" examples in any language!
>
> — Claude Sonnet 4 _(on an admittedly enthusiastic moment)_

## Quick Start

Install and run Comp programs with `uv` (recommended)

```bash
uv pip install -e .
uv run comp examples/hello.comp
```

## Highlights

Start with the [Overview Document](design/overview.md) for the best summary
of features and highlights like:

- **Super Structures** - One immutable type of data for all your data.
- **Typed Schemas** - Data is validated and reshaped based on explicit schemas.
- **Pipelined** - When everything is in a pipeline, everything fits together.
- **Flowchart functions** - Flow control is simple functions you can create yourself.
