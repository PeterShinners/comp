# Functions and Blocks

Functions and blocks are deferred computations. A function is a named deferred
block stored in the module's namespace. A block is an anonymous deferred
expression, typically passed as an argument. Both receive input data through the
pipeline, accept modifiers through `[]`, and produce a result. The distinction
is purely organizational — they share identical invocation and scoping rules.

Comp's function design centers on a simple philosophy: functions operate on
input data received through the pipeline, and modifiers customize how they
behave. Data flows through `|`, configuration lives in `[]`, and callable
arguments arrive in `()` or `{}`. This separation keeps function signatures
clean and call sites readable.

## Defining Functions

Functions are declared at module level with `!func` or `!pure`. The input shape
follows the name on the declaration line. The body is a `()` block containing
optional metadata operators and the implementation.

```comp
!pure tree-contains ~tree (
    !mods value~num

    !on (value <> $value)
    ~less ($left | tree-contains[value])
    ~greater ($right | tree-contains[value])
    ~equal true
)
```

The `!pure` declaration means this function has no side effects — it cannot
access external resources, call non-pure functions, or observe mutable state.
Pure functions can be evaluated at build time when their inputs are known, and
the compiler can safely cache, parallelize, or eliminate their calls. Use `!func`
for functions that perform side effects.

Inside the body, metadata operators declare what the function accepts:

`!mods` declares modifier arguments — what callers pass in `[]`. Each modifier
can have a name, a type constraint, and a default value. Modifiers without
defaults are required.

`!block` declares that the function accepts a callable block argument. The block
declaration specifies the expected type and an optional default. Functions can
accept multiple blocks.

```comp
!pure reduce ~struct (
    !mods initial
    !block fold
    // implementation
)

// Called as: data | reduce[initial=0] ($ + $accumulator)
```

`!ctx` binds a context value, making it available to all nested function calls.
Context values automatically populate named modifier arguments in any function
called within the current scope, enabling implicit configuration threading.

## Invocation Rules

Expressions that produce a callable value are **invoked by default**. This
means bare references to zero-argument functions automatically execute, and
expressions in most positions evaluate eagerly.

```comp
!let when datetime.now              // invokes, gets timestamp
!let cutoff (datetime.now - 1[week]) // invokes in expression
```

There are two exceptions to eager invocation. Inside a **pipeline expression**
being constructed, evaluation is deferred until the pipeline is consumed — the
pipeline describes a chain of operations, not an immediate result. And inside a
**block argument position** (where the receiving function declared `!block`),
the expression becomes a callable that the function invokes with its own data.

```comp
| map (uppercase)                    // block argument — deferred
| reduce[initial=nil] (tree-insert)  // block argument — deferred
| where ($active)                    // block argument — deferred
```

When a function has a declared input type but no input is available in the
current position, the reference becomes **partial application** rather than
invocation:

```comp
!let replace-single replace[limit=1]  // no input, partial application
data | replace[limit=1]               // has input, invokes
```

The `!defer` operator explicitly prevents invocation, capturing a callable as a
reference regardless of context:

```comp
!let gen !defer datetime.now              // holds the function, doesn't call it
!let pipeline !defer ($items | sort | first[5])  // captures pipeline as callable
```

For the rare case of referencing a zero-argument function without invoking it,
wrap it in a block: `($ | datetime.now)`. The compiler recognizes this pattern
and optimizes it to a direct reference.

## Pipeline Composition

The pipeline `|` operator is Comp's primary composition mechanism. Data flows
left to right through a chain of functions, each receiving the output of the
previous step as input.

```comp
gh.issue-list[repo=repo fields=fields]
| where ($created-at >= cutoff)
| insert-each[thumb = ($reaction-groups | tally ($content == "thumbs-up"))]
| sort-by[thumb reverse]
| first[5]
| table.markdown
```

Each function in a pipeline receives the previous result as `$`. Modifiers in
`[]` customize behavior. Blocks in `()` define callable logic that the function
invokes per-element or as needed. The pipeline reads as a description of what
you want, not how to compute it.

The fallback operator `|?` catches failures and provides an alternative path:

```comp
$user | find[name="alice"] |? default-user
config.optional-field |? "default-value"
```

## Dispatch with `!on`

The `!on` operator performs type-based dispatch — Comp's unified mechanism for
branching. Instead of separate `if/else/match/when` constructs, `!on` evaluates
an expression and selects a branch based on the type or tag of the result. This
is the same matching engine used for function overloading, brought inline.

```comp
!on ($age)
~num[0..13] "child"
~num[13..20] "teenager"
~num[20..] "adult"
~text "not a number"
~nil "nothing"
```

Each branch starts with a `~tag` or `~type` pattern. The matching system scores
each branch for specificity — constrained types beat unconstrained, specific
tags beat parent tags — and selects the best match. When scores tie, the branch
listed first wins. This is where `!on` differs from function dispatch, which
requires unambiguous matches.

The three-way comparison `<>` pairs naturally with `!on`, returning `~less`,
`~equal`, or `~greater` tags:

```comp
!on (value <> $value)
~less ($left | tree-contains[value])
~greater ($right | tree-contains[value])
~equal true
```

Boolean dispatch uses `~true` and `~false` — booleans are just tags:

```comp
!on ($id == id)
~true @update {complete = (not $complete)}
~false $
```

## Function Overloading

Multiple functions with the same name can be defined with different input
shapes. At call time, the dispatch system picks the most specific match based on
the input data's shape. Each overload can define its own modifiers and body.

```comp
!pure tree-insert ~nil (
    !mods value~num
    tree[value=value]
)

!pure tree-insert ~tree @update (
    !mods value~num
    !on (value <> $value)
    ~less {left = ($left | tree-insert[value])}
    ~greater {right = ($right | tree-insert[value])}
)

!pure tree-values ~nil ({})
!pure tree-values ~tree @flat (
    ($left | tree-values)
    {$value}
    ($right | tree-values)
)
```

The `~nil` overloads handle the base case (empty tree). The `~tree` overloads
handle the recursive case. When `tree-insert` is called, the runtime examines
the input — if it's `nil`, the first definition runs; if it's a `~tree` shape,
the second runs. Overloads must be unambiguous or the compiler reports an error.

## Decorators on Functions

The `@` decorator between the function name and its body wraps the function's
execution. A decorator receives the input, the function body as a callable, and
the modifier arguments. It controls whether, when, and how the inner function
runs. This is fundamentally different from a pipeline step — the decorator
orchestrates rather than transforms.

```comp
!pure tree-insert ~tree @update (...)
!pure tree-values ~tree @flat (...)
!func handle ~event @transact[scene] (...)
```

`@update` runs the body and merges the resulting struct onto the original input.
This means the body only needs to return the fields that changed, not the entire
structure. `@flat` collects multiple expressions from the body and concatenates
them into a single sequence.

Decorators are not special language features — they follow a standard protocol
and can be defined by any library:

```comp
// A decorator is just a function that receives the wrapping context
!func retry (
    !mods times~num=3
    !block wrapped
    // invoke wrapped, retry on failure up to `times` attempts
)

// Used as: !func flaky-fetch ~url @retry[times=5] (...)
```

## Local Bindings and Side Effects

Inside a block, `!let` creates a local binding. It does not use `=` (which is
reserved for field assignment). The binding name is followed by the expression
whose value it captures.

```comp
!let base ($price * $quantity)
!let parent ($ | maya.get-parent)
!let transform (parent | maya.create-node[config.layer-type])
```

Locals are scoped to the block they appear in. Blocks defined inside a function
share the function's local namespace — this is how closures work. A `!let`
inside a nested block is visible to the enclosing function.

For side effects that don't produce a needed value, pipe the result to `ignore`
or use `tee` to branch without disrupting the main pipeline:

```comp
$ | tee (res.punch | play) | continue-processing
result | ignore
```

In `()` blocks, the last expression is the result. In `{}` blocks, every
non-`!let` line is a field contribution. `!let` lines are bindings in both
cases, never contributing to the output.

## Failure Handling

The `!fail` operator raises a failure value that fast-forwards through the call
chain. Failures skip all intermediate pipeline steps until caught by the `|?`
fallback operator. Failures carry a value — typically a struct with a message
and optional tag for categorization.

```comp
!fail "index out of bounds"
!fail {message="not found" tag=fail.database}

// Caught by fallback
risky-operation |? safe-default
data | find[name="alice"] |? (fail["user not found" tag=fail.missing])
```

Failures are not exceptions. They propagate through values, not through a
separate control channel. A failure in a struct field makes the entire struct a
failure. This makes failure handling explicit and traceable — you can always see
where failures are caught by looking for `|?` operators.

## Streams and Lazy Evaluation

Streams are blocks that yield values on repeated invocation. They signal
completion with the `done` tag and omission with the `skip` tag. The `pass`
tag represents the identity function — a default that returns its input
unchanged.

A stream is created by defining a block with `!let` rebinding for state
progression. Each invocation produces the next value and advances the state:

```comp
!pure counter (
    !mods start~num=0 step~num=1
    !let n start
    (
        n
        !let n (n + step)
    )
)

!pure range (
    !mods start~num=0 end~num step~num=1
    !let n start
    (
        !on (n >= end)
        ~true done
        ~false (n  !let n (n + step))
    )
)
```

The `!let` rebinding inside a stream is not mutation — it creates a new binding
that the next invocation sees. The block is a closure that captures and rebinds.
This mechanism enables the entire iteration library to be built from two
primitives: `consume` (drive a stream for side effects) and `collect` (drive a
stream and gather results). Everything else — `map`, `filter`, `reduce`, `each`,
`any?`, `all?`, `find` — composes from these.

```comp
!pure map ~struct (
    !block op
    $ | enumerate | collect ($value | op)
)

!pure filter ~struct (
    !block test
    $ | enumerate | collect (
        !on ($value | test)
        ~true $value
        ~false skip
    )
)
```

## Scope and Context

Functions have access to several scope layers. The pipeline input `$` provides
the data being operated on. Local bindings from `!let` are visible within the
block and any nested blocks. Module-level declarations (shapes, tags, functions)
are available by name throughout the module. Imported namespaces are accessed
through their import name (`rio.button`, `py.call`).

The context system (`!ctx`) provides implicit argument threading. When a
function sets a context value, that value automatically populates matching
named modifiers in any function called within the current scope. This replaces
explicit argument passing for cross-cutting concerns like configuration,
authentication tokens, or UI themes.

```comp
!func todo-app ~state (
    !ctx state $
    // all nested function calls can now access 'state' through their modifiers
    rio.column[spacing=2] { ... }
)
```

Context values are matched by name and type against modifier declarations. A
context value only populates a modifier if the name matches and the type is
compatible. Values provided explicitly in `[]` always take priority over context.