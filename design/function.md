# Functions and Blocks

All statements inside parenthesis or structures inside braces can be
evaluated as deferred statements called blocks. These can take an input
object through pipelines and define their own parameters. Functions take
a block and define additional metadata and place it into a module namespace.

Comp functions are centered on a simple philosophy of operating on input data
received through the pipeline with parameters to customize how they behave. Data
flows through `|`, parameters are defined with `:` prefixed expressions. This
separation keeps function signatures clean and call sites readable.

Blocks can define special block objects which allow them to do advanced
language level features like conditionals and looping. Comp defines several
novel features like function wrappers, linking families of functions with
side channels, and pure functions that are simplified and can be evaluated
at build time, or in parallel, and other contexts.

## Defining Functions

Functions are declared at module level with `!func` or `!pure`. The input shape
follows the name on the declaration line. The body is a `()` block containing
optional metadata operators and the implementation. Functions can be defined
with a deferred `{}` structure literal, but typically this is not as common.

```comp
!func double ~num (
    $ + $
)

!pure lookup-field ~struct (
    :param field~text fallback~any

    $.'field' ?? fallback
)
```

The `!pure` declaration means this function has no side effects, it cannot
access external resources or call non-pure functions.
Pure functions can be evaluated at build time when their inputs are known, and
the compiler can safely cache, parallelize, or eliminate their calls. Use `!func`
for functions that perform side effects.

### Signature Operators

Inside the function body, metadata operators declare what the function accepts:

`:param` declares a function parameter. Each parameter can have a name, a type
constraint, and a default value. Parameters without defaults are required.
Unlike defaults in shape definitions, these parameter definitions can use full
expressions and pipelines that are only invoked if the parameter is not
provided.

`:block` declares that the function accepts a deferred block as a parameter. The
block declaration can define the input shape for the block and an optional
default.

```comp
!pure reduce ~struct (
    :param initial
    :block fold
    // implementation
)

// Called as: data | reduce :initial=0 :($ + $accumulator)
```

## Invocation Rules

Expressions that produce a callable value are **invoked by default**. This
means bare references to zero-parameter functions automatically execute, and
expressions in most positions evaluate eagerly.

```comp
!let timestamp datetime.now  // invokes, gets timestamp
!let sample random * 10      // invokes in expression
```

There are two exceptions to eager invocation. Inside a **pipeline expression**
being constructed, evaluation is deferred until the pipeline is consumed, the
pipeline describes a chain of operations, not an immediate result. And inside a
**block parameter position** (where the receiving function declared `:block`),
the expression becomes a callable that the function invokes with its own data.

```comp
| map :(uppercase)                    // block parameter, deferred
| reduce :initial=nil (tree-insert)  // block parameter, deferred
| where :($active)                    // block parameter, deferred
```

The `!defer` operator explicitly prevents invocation, capturing a callable as a
reference regardless of context. This can be used for partial application of
parameters or to capture a pipeline as a higher level object.

```comp
!let make-timestamp !defer datetime.now
!let replace-single !defer replace :limit=1
!let first-word-lower !defer (split :limit=1 | first | lowercase)
```

## Pipeline Composition

The pipeline `|` operator is Comp's primary composition mechanism. Data flows
left to right through a chain of functions, each receiving the output result of
the previous step as input.

```comp
github.issue-list :repo=repo :fields=fields
| where :($created-at >= cutoff)
| map :($thumbs-up = $reaction-groups | count :($content == "thumbs-up"))
| sort :reverse :($thumbs-up)
| first :5
```

Each function in a pipeline receives the previous result as `$`. Parameters
prefixed with `:` customize the behavior. Block parameters are must still be
wrapped in `()` or `{}` statements. The pipeline reads as a description of what
you want, not how to compute it.

## Dispatch with `!on`

The `!on` operator performs type-based dispatch, Comp's unified branching
mechanism. It evaluates an expression and selects a branch based on the type or
tag of the result, using the same matching engine as function overloading. Each
branch starts with a `~tag` or `~type` pattern. When scores tie, the branch
listed first wins.

```comp
!on (value <> $value)
~less ($left | tree-contains :value)
~greater ($right | tree-contains :value)
~equal true

!on ($id == id)
~true @update {complete = !not $complete}
~false $
```

Comp comes with several standard library functions that build on this for
higher-level branching, `if` and `else` functions, along with convenient
conditional patterns. Design or extend your own based on specific use cases.

## Function Overloading

Multiple functions with the same name can be defined with different input
shapes. At call time, the dispatch system picks the most specific match based on
the input data's shape. Each overload can define its own parameters and body.

```comp
!pure tree-insert ~nil (
    :param value~num
    tree :value=value
)
!pure tree-insert ~tree @update (
    :param value~num
    !on (value <> $value)
    ~less {left = ($left | tree-insert :value)}
    ~greater {right = ($right | tree-insert :value)}
)

!pure tree-values ~nil {}
!pure tree-values ~tree @flat (
    ($left | tree-values)
    {$value}
    ($right | tree-values)
)
```

The `~nil` overloads handle the base case (empty tree). The `~tree` overloads
handle the recursive case. When `tree-insert` is called, the runtime examines
the input, if it's `nil`, the first definition runs; if it's a `~tree` shape,
the second runs. Overloads must be unambiguous or the compiler reports an error.

## Wrappers

The `@` wrapper between the function name and its body wraps the function's
execution. A wrapper receives the input, the function body as a callable, and
the parameters. It controls whether, when, and how the inner function runs. This
is similar to Python's decorator concept but more powerful, wrappers can be
applied to any expression or block, not just function definitions. They control
the orchestration of how the inner statement executes, while remaining readable
and composable.

```comp
!pure tree-insert ~tree @update (...)
!pure tree-values ~tree @flat (...)
```

`@update` runs the body and merges the resulting struct onto the original input.
This means the body only needs to return the fields that changed, not the entire
structure. `@flat` collects multiple expressions from the body and concatenates
them into a single sequence.

Wrappers are not special language features, they follow a standard protocol
and can be defined by any library.

```comp
// A wrapper is just a function that receives the wrapping context
!func retry (
    :param times~num = 3
    :block wrapped
    // invoke wrapped, retry on failure up to `times` attempts
)

// Used as: !func flaky-fetch ~url @retry :times=5 (...)
```

## Local Bindings

Inside a block, `!let` creates a local binding. It does not use `=` which is
reserved for field assignment. The binding name is followed by the expression
whose value it captures.

```comp
!let base ($price * $quantity)
!let parent ($ | maya.get-parent)
!let transform (parent | maya.create-node :config.layer-type)
```

Locals are scoped to the function they are defined in. They are shared
across all blocks defined in the same function. Assigning new values
with `!let` are immediately set across the entire function.

In `()` blocks, the last expression is the result. In `{}` blocks, every
non-`!let` line is a field contribution. `!let` lines are bindings in both
cases, never contributing to the output.

## Scope

Functions have access to several scope layers. The pipeline input `$` provides
the data being operated on. Local bindings from `!let` are visible within the
function and all its nested blocks, like closures. These names are combined with
the named parameters and blocks a function defines.

Module-level declarations (shapes, tags, functions) are available by name
throughout the module. Imported namespaces are accessed through their import
name (`rio.button`, `py.call`). See [Modules](module.md) for namespace
resolution rules and context threading.