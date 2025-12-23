# Comp

Comp is an experiment: what if a language had Python's ease of use but made different foundational choices? Immutable data by default. Pipelines instead of method chains. Shapes instead of classes. No whitespace significance.

It's not trying to replace Python—it's designed to run alongside it, sharing the same ecosystem and interpreter. The question isn't "is Python bad?" (it isn't). The question is "what would feel better?"

**This is early-stage, experimental software.** The syntax is still evolving, the interpreter is incomplete, and you shouldn't build anything serious on it yet. But if language design interests you, or if you've ever thought "I wish Python did X differently," you might find something interesting here.

## A Taste

Here's a pygame example. In Python, you'd write an event loop, manually track state, handle each event type with if/elif chains, and sprinkle mutation throughout. In Comp:

```comp
--- Pygame chimp tutorial (React-style)
Punch a monkey to win prizes
---

main = :(
    !ctx.window = pg.display
    | window(1280 480 scaled=true)
    | caption("Monkey Fever")

    pg.loop(ctx.window quit-on=(event.quit key.escape)) :~frame (
        frame.events | each :e (e | handle(frame.state))
        frame.draw
        | clear(.7 .9 .7)
        | card(state.chimp)
        | card(state.fist)
    )
)

handle = :~event[type==mouse.down] ~state (|update
    fist = state.fist | move(10 90)
    if (intersect(state.fist state.chimp)) :(
        chimp.rotate = spin(360 0.5 ease-out)
        play(res.punch)
    ) | else :(
        play(res.whiff)
    )
)

handle = :~event[type==mouse.move] ~state (|update
    fist = state.fist | position(event.position)
)
```

The event handlers dispatch based on shape—`event[type==mouse.down]` matches mouse clicks, `event[type==mouse.move]` matches movement. No switch statement, no event type constants. The data's shape determines which function runs.

## Core Ideas

**Everything is a structure.** Data lives in ordered, optionally-named containers. Function definitions use the same syntax as data literals. There's one way to represent things.

```comp
point = (x=10 y=20)              -- data
player = ~(name~text score~num)  -- shape (schema)
greet = :(print("hello"))        -- function
```

**Shapes replace classes.** Define what data looks like, not what it "is." Functions dispatch based on whether data matches their declared shapes. The same function name can have multiple implementations for different shapes.

```comp
tree-insert = :tree~nil value~num (tree(value))
tree-insert = :tree~branch value~num (
    if (value < tree.value)
        :(tree | merge(left = tree-insert(tree.left value)))
    |else
        :(tree | merge(right = tree-insert(tree.right value)))
)
```

**Pipelines over method chains.** Data flows left-to-right through transformations. No `self`, no mutation, no wondering what `.sort()` returns.

```comp
users
| filter :u (u.active)
| sort :u (u.joined)
| first(10)
| each :u (send-welcome(u))
```

**Control flow is just functions.** `if`, `map`, `reduce`—these aren't special syntax, they're regular functions. You can write your own. The standard library is written in Comp.

**Declarative namespaces.** Everything in a module is known before execution. Imports, definitions, references—all resolved at build time. A whole category of runtime errors becomes build errors.

## Python Interop

Comp runs on Python and talks to Python. Import Python modules, call Python functions, or expose Comp code back to Python.

```python
import comp
coolcsv = comp.import_module("coolcsv", "contrib")
data = coolcsv.load("source.csv")
filtered = coolcsv.filter(data, filter=comp.parse("~num[min=35]"))
```

The goal is zero-friction coexistence. Use Comp where its model fits better; use Python where it doesn't. They share an interpreter and can share data.

## Status

Comp is in active development. The parser handles most of the syntax. The interpreter is coming together. The language design is still shifting—this is the fourth major syntax revision. The implementation is co-developed with AI assistants (primarily Claude)—both the code and the design exploration.

What exists today:
- A [collection of examples](examples/) showing current syntax
- [Design documents](design/) tracking decisions and rationale
- A minimal [VS Code extension](vscode/) for highlighting
- The beginnings of an interpreter in [src/](src/)

What doesn't exist yet:
- A stable language you can rely on
- Complete Python interop
- Package management
- Most of the standard library

If you're interested in following along or contributing ideas, the repo is open. If you're looking for a production-ready tool, check back later.

## Quick Start

With [uv](https://github.com/astral-sh/uv):

```bash
git clone <repo>
cd comp
uv pip install -e .
uv run comp examples/tree.comp
```

## Why "Comp"?

No deep meaning. It sits at the intersection of "compositing" (node graphs of operations), "composable" (the design philosophy), and "computing" (the obvious one). It's short and it wasn't taken.

## License

MIT [LICENSE](LICENSE)