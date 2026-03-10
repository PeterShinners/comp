# Functions and Pipelines

Functions are module level definitions that use a `()` statement,
`{}` structure, or `[]` pipeline to define the body.

All statements inside parenthesis or structures inside braces can be
deferred with a leading colon `:()` and `:{}`. These can take an input
object through pipelines and define their own parameters. Functions take
a block and define additional metadata and place it into a module namespace.

Comp functions are centered on a simple philosophy of operating on input data
received through the pipeline with parameters to customize how they behave. Data
flows through `|` definitions inside of `[]` square brackets. Each term in the
pipeline has an input value from the results of the preceding function. They
also get a collection of optional parameters, which are like structure fields
inside the pipeline statement.

Inside of function bodies, deferred statements can be created. These are
often used to define operations that are managed as a parameter passed to
a function. This allows flow control and iteration to be managed by
regular functions. These deferred statements are often called blocks.

## Defining Functions

Functions are declared at module level with `!func` or `!pure` operators. Each
function must define the shape of the input data it accepts; using `~nil` if
the input is unused.

```comp
!func double ~num (
    $ + $
)

!pure lookup-field ~struct (
    !param field~text 
    !param fallback~any

    $'field' ?? fallback
)
```

The `!pure` declaration means this function has no side effects, it cannot
access external resources or call non-pure functions. Pure functions can be
evaluated at build time when their inputs are known, and the compiler can safely
cache, parallelize, or eliminate their calls. Use `!func` for functions that
perform side effects.

### Signature Operators

Inside the function body, signature operators declare metadata about the
function and any parameters it might receive.

`!param` declares a function parameter. Each parameter can have a name, a type
constraint, and a default value. Unlike defaults in shape definitions, these
parameter definitions can use full expressions and pipelines that are only
invoked if the parameter is not provided.

```comp
!pure example ~struct (
    !param initial
    !param resoure ~data = [default-data | prepare]
    // implementation
)
```

## Callables

There are several types of data that are callable. The most common are functions
referenced from the module namespace. These can be a single definition or an
overloaded set of functions that will dispatch when invoked. Shapes are also
invokable to convert data types, which also means tags can be invoked.
Deferred blocks and pipelines are also callable values.

To invoke a callable it must be placed in square brackets to define and
execute a pipeline. If a function requires no inputs or parameters the pipeline
can be as simple as the callable value, `[runme]`.

## Pipeline Composition

The pipeline `|` operator is Comp's primary composition mechanism. Data flows
left to right through a chain of functions, each receiving the output result of
the previous step as input.

```comp
[github.issue-list repo=repo fields=fields
| where :($.created-at >= cutoff)
| map :($.thumbs-up = [$.reaction-groups | count :($.content == "thumbs-up")])
| sort reverse :($.thumbs-up)
| first 5
]
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
!on (value <> $.value)
~less [$.left | tree-contains :value]
~greater [$.right | tree-contains :value]
~equal true

!on ($.id == id)
~true @update {complete = !not $.complete}
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
!pure empty.tree-insert ~nil (
    !param value~num
    tree :value=value
)
!pure some.tree-insert ~tree @update (
    !param value~num
    !on (value <> $.value)
    ~less {left = [$.left | tree-insert value]}
    ~greater {right = [$.right | tree-insert value]}
)

!pure tree-values ~nil {}
!pure tree-values ~tree @flat (
    [$.left | tree-values]
    {$.value}
    [$.right | tree-values]
)
```

The `~nil` overloads handle the base case (empty tree). The `~tree` overloads
handle the recursive case. When `tree-insert` is called, the runtime examines
the input, if it's `nil`, the first definition runs; if it's a `~tree` shape,
the second runs. Overloads must be unambiguous or the compiler reports an error.

Inside an overload body, `!forward` re-dispatches the current call to the next
less-specific overload in the same family, skipping the one currently running.
This lets a specialized overload handle its specific case and then hand off to
the broader handler without recursing into the current running function.

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
    !param times~num = 3
    !param wrapped~pipe
    // invoke wrapped, retry on failure up to `times` attempts
)

// Used as @retry [flaky-fetch times=5 (...)]
```

## Local Scope

Inside a block, `!my` creates a local binding. It takes an identifier
name to be assigned to an an expression to generate the value.

```comp
!my base ($.price * $.quantity)
!my parent [$ | maya.get-parent]
!my transform [parent | maya.create-node config.layer-type]
```

Locals are scoped to the function they are defined in. They are shared
across any blocks defined in the same function. Assigning new values
with `!my` are immediately set across the entire function.

The `!param` blocks also define local values that will be supplied when
the function or block is invoked.

The `!ctx` operator also works like `!my` but also allows the value to be
passed through nested calls.

Values in the local scope will override namespace lookups. Locals can be
explicitly referenced through the `my.` scope. Namespace references can
always be referenced through the `mod.` scope, which allows referencing
shadowed functions tags or shapes.

Functions have access to several scope layers. The pipeline input `$` provides
the data being operated on. Local bindings from `!my` are visible within the
function and all its nested blocks, like closures. These names are combined with
the named parameters and blocks a function defines.

Module-level declarations (shapes, tags, functions) are available by name
throughout the module. Imported namespaces are accessed through their import
name (`rio.button`, `py.call`). See [Modules](module.md) for namespace
resolution rules and context threading.

Functions also have access to the input value, represented with `$`.
Inside of nested blocks `$$` can be used to reference the input value for
the outer scope, and even `$$$` to continue referencing incremental scopes.