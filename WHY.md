# Why Comp?

This is all a prototype of ideas that could make a better Python than Python.
I use Python all the time and have decades of experience. But I find a
friction when trying to write clean and composable code that seems to
grind against the idiomatic Python patterns.

What if we could make robust code the default instead of the exception?
This is no easy task. The code and ideas in this repository change frequently
and with reckless abandon. Will the experiments bear fruit? Are these ideas
the path to the future?

If it sounds like pointless complexity, that's fair, be skeptical. Python is a
great language. Most code doesn't need this. In the meantime, I'm excited to
explore the "what could be better" instead of complaining on the sidelines.

## The Ceremony Problem

There is a light, friendly, and powerful language inside Python.  But the path
to robust Python has accumulated layers:

- Type hints that don't quite catch what you need
- dataclasses/pydantic for simple structures
- mypy/pyright that fight your actual patterns
- `Optional[int]` everywhere, with defensive checks to match
- `if TYPE_CHECKING` guards for circular imports
- Protocol classes for structural typing
- `__all__` declarations for clean exports

Each layer solves a real problem. Together, they become more scaffolding than
logic.

## What Ifs?

Comp asks: what if the right primitives eliminated the scaffolding?

**What if types were validation?** In Python, you define a dataclass, then add
pydantic for validation, then add type hints for the checker. In Comp, there are
shape values which do all three: definition, validation, documentation. Data
matches or it doesn't. Data that comes from literals, json, network requests,
or databases are all the same.

**What if immutability was free?** No more defensive copies. No more wondering
if a function mutated your data. No more `frozen=True` with its gotchas.
Everything is immutable. The patterns that require mutability get explicit
syntax. The language can step in to make redefining fields and overrides
feel as easy as modifications.

**What if the namespace was declarative?** No circular import tangles or import
order puzzle games. No running code to know what a module contains. Comp's
namespaces are declarative—everything is known at build time, references resolve
before execution. This leads to whole new levels of build time errors and
static analysis. Combined with a lightweight "pure functions" concept
much of the language becomes a powerful build time excercise.

**What if your config file was typed?** Import a TOML file as a module. Typo in
a key name? Build error. Wrong type? Build error. The same for OpenAPI specs,
protobuf definitions, database schemas. Structured sources become typed
namespaces, validated before your code runs.

## The Proof

Comp aims for a language embedded in Python attempts handling the compositional,
data-heavy parts better than Python itself. Not replace Python; work alongside
it. Handle the data pipelines, the config loading, the API contracts. Let Python
do what Python does well.

Maybe it works. Maybe it doesn't. But the ideas are worth exploring:

- **Shapes** that are types, validation, and docs in one declaration
- **Immutability** that removes defensive coding entirely
- **Declarative namespaces** resolved before anything runs
- **Compilers** that turn any structured source into typed modules
- **Pipelines** that describe data flow, not execution steps
- **Tags** that make arguments self-routing and typo-proof
- **Failures** that propagate cleanly without try/catch ceremony

In the wildest version of this dream, Comp becomes a "CoffeeScript of Python";
not replacing it, but proving ideas that eventually flow back. CoffeeScript gave
JavaScript arrow functions and destructuring. What roads could Comp uncover?

## Still Here?

If this resonates, look at the [examples](examples/). Read the
[README](README.md). The syntax is still shifting, but the ideas are taking
shape.
