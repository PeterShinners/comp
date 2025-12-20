# Comp Language

Comp is born from an excercise to improve the state of developing in high level
languages like Python. This requires new ideas and behaviors to avoid the ruts
and common errors these languages encourage. The goal is a lightweight and
readable language that prioritizes the developer experience.

This requires some opinionated departures from traditional high level languages.
All data is immutable and stored in structures that operate both positionally
and by field names. Data from any source becomes interchangeable with anything
loaded, generated, or defined with source. Namespaces and imports and
definitions are declarative, leading to greater analysis and improving build
time errors and reports. The result looks like a functional style language,
where there are no classes and function calls chain together into a pipeline.

The language tries to be minimal, while still presenting high level
functionality. Flow control and iteration are implemented as regular functions.
Implement your own or enhance the existing calls and they are interchangeable
with any part of the language.

Comp is design to run alongside a Python interpreter. Anywhere Python goes, Comp
should be a viable alternative, ideally even preferred.

Start with the [Overview Document](design/overview.md) for a summary of features
and highlights.

## Example

```comp
--- Hello World example in Comp language.
Try to personalize the greeting with a series of fallback environment
variable lookups.
---

main = :(
  ("USERNAME" "USER" "LOGNAME")
  |map :in (getenv(in) ? skip)
  |first(else="World")
  |print("Hello, ${}!")
)
```

## Quick Start

Install and run Comp programs with `uv` (recommended). With a checkout of this
repository;

```bash
uv pip install -e .
uv run comp examples/tree.comp
```

The barrier to entry is minimal. An entire project with metadata, dependencies,
code, and documentation all comes from a single `.comp` file. Of course, that
can eventually be structured into a helpful hierarchy of files, modules, and
dependencies as desired.

## Where Comp Shines

Comp is designed for:

- **Tool scripting** Maya, Blender, Houdini automation
- **Data pipelines** ETL, transformation, analysis
- **API integration** Clean composition of web services
- **Configuration** Type-safe, validated config files
- **Prototyping** Quick iteration with strong guarantees

## Development Status

The languge is in volatile design mode. Things are moving fast, and breaking.
The syntax is on its fourth reworking with more on the way. Nothing is nailed
down and everything slides. Many of the concepts show signs of solidifying and
are tracked in the [Design Documents](design/). The primary sandbox for
development comes from the directory of [Examples](/examples/), which are always
kept up to date with the syntax.

The [Source](src/) is written in Python (yes, an interepreted language inside an
interpreted language) but currently mostly empty after restarting with the
recent design updates.

The minimal [Vscode Extension](vscode/) does an basic job of highlighting.

The project is open source under the [MIT license](LICENSE).