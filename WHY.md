# Why Comp?

*You should be skeptical.* This is an experiment, not a production tool. The syntax breaks regularly. The interpreter is incomplete. You shouldn't build anything serious on it.

But if you've felt friction in Python—not with Python itself, but with what it takes to write *robust* Python—these ideas might interest you.

## The Ceremony Problem

Python started as "quick and direct." But the path to robust Python has accumulated layers:

- Type hints that don't quite catch what you need
- dataclasses/pydantic for simple structures
- mypy/pyright that fight your actual patterns
- `Optional[int]` everywhere, with defensive checks to match
- `if TYPE_CHECKING` guards for circular imports
- Protocol classes for structural typing
- `__all__` declarations for clean exports

Each layer solves a real problem. Together, they're more scaffolding than logic.

## What If?

Comp asks: what if the right primitives eliminated the scaffolding?

**What if types were validation?** In Python, you define a dataclass, then add pydantic for validation, then add type hints for the checker. In Comp, a shape is all three: definition, validation, documentation. Data matches or it doesn't—same rules whether it came from JSON, a database, or a literal in your code.

**What if immutability was free?** No more defensive copies. No more wondering if a function mutated your data. No more `frozen=True` with its gotchas. Everything is immutable. The patterns that require mutability get explicit syntax.

**What if imports just worked?** No circular import tangles. No runtime surprises from import order. No running code to know what a module contains. Comp's namespaces are declarative—everything is known at build time, references resolve before execution.

**What if None didn't exist?** Python's `Optional[int]` creates a split where every use needs narrowing. Comp arguments have types, period. A `~num` is a number. Default values are late-evaluated expressions, not a sentinel `None` that infects your type signatures.

**What if your config file was typed?** Import a TOML file as a module. Typo in a key name? Build error. Wrong type? Build error. The same for OpenAPI specs, protobuf definitions, database schemas. Structured sources become typed namespaces, validated before your code runs.

## The Bet

Comp bets that a language embedded in Python could handle the compositional, data-heavy parts better than Python itself. Not replace Python—work alongside it. Handle the data pipelines, the config loading, the API contracts. Let Python do what Python does well.

Maybe it works. Maybe it doesn't. But the ideas are worth exploring:

- **Shapes** that are types, validation, and docs in one declaration
- **Immutability** that removes defensive coding entirely
- **Declarative namespaces** resolved before anything runs
- **Compilers** that turn any structured source into typed modules
- **Pipelines** that describe data flow, not execution steps
- **Tags** that make arguments self-routing and typo-proof
- **Failures** that propagate cleanly without try/catch ceremony

In the wildest version of this dream, Comp becomes the "CoffeeScript of Python"—not replacing it, but proving ideas that eventually flow back. CoffeeScript gave JavaScript arrow functions and destructuring. What could Comp prove?

## Still Here?

If this resonates, look at the [examples](examples/). Read the [README](README.md). The syntax is still shifting, but the ideas are taking shape.

If it sounds like pointless complexity, that's fair. Python is a great language. Most code doesn't need this. But some code—the compositional, data-heavy, needs-to-be-robust code—might benefit from a different set of tradeoffs.

That's what Comp is exploring.