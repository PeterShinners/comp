# Functions and Blocks

Blocks and functions are both deferred structure literals. They are evaluated
with optional input and argument data that become part of the running scope.
Functions become named values in the module's namespace, but both can be
referenced and invoked equally.

Invoking a function or block is visually represented by annotating a structure
literal as arguments for a callable.

To call a function, it must be referenced from the namespace and apply a set of
arguments, even if that set of arguments is empty. Data can be passed as an
input to the function by preceding the function with a pipe `|` operator, which
is a way of chaining function results to a series of operations.

The design is that functions operate on input data, received through the
pipeline. The arguments are used to modify how the function behaves. For
functions that construct data the concepts are more ambigious, which is why comp
allows providing data either way for these functions.

A Comp function is a deferred structure that takes input data to create a
different structure. Function calls are designed to be chained together using
the pipeline `|` operator. A deferred function is defined with a `:` preceding a
literal structure definition.

Flow control, like conditionals and loops, are just regular functions. The
language provides many traditional "if" and "map" looping operations. Users are
free to build on these for more specific operations, or create their own library
of helpers from scratch.

Functions can define special links that provide additional behevior, like `if`
`else` being separate functions, but coordinating together to create higher
level flow control.

Functions can be referenced and used like any value data. Anonymous functions
can also be created called "blocks". These use the same syntax as function
definitions and are often passed as argument to define behavior for functions
that perform flow control.

A function really is just a structure literal that runs at a later time. The
deferred structure also defines optional information about the shapes for
arguments. There are also flags, like "pure" which restrict a function from
using external resources, which can then be called during build time.

Multiple functions can overload with the same name. The language will dispatch
to the most specific implementation based on the incoming data shapes. Functions
can also wrap existing functions to inherit their behavior and definition, but
extend or change the functionality in some way; similar to middleware some
frameworks use.

The pipeline of functions is itself exposed as a structure, and can be recreated
or overridden by special "wrench" operators. These can optimize queries,
instrument code, or add progress tracking to a pipeline before it gets executed.

Calling a function or block is intended to look like an annotated structure
literal. A function reference is followed by a structure literal to define its
arguments. `sum(1 2 3)`.

These callable structures have several other states and flags they can use.

- Pure functions cannot use external resources but can be called at build time
- Extended functions wrap existing functions and inherit their functionality

## Invoking

Functions and blocks is always performed by referencing the callable and
following it with a structure literal of arguments. Even if the function takes
no arguments an empty structure literal must be used.

Calls can optionally be assembled into a pipeline where the output of each call
will be passed as input to the following call.

## Definition

Blocks and definitions are defined by prefixing a structure literal with a `:`.
A simple block is just any value prefixed with the colon.

```comp
simple = :(4 + 4)  -- A hardcoded result
get-version = :(mod.version)  -- Fetch constant value from module
```

All of a function's metadata is placed between the leading `:` colon and the
function body. This section of the grammar is called the definition and works
similarly to a shape definition.

But most functions will define required inputs. This can take the form of
traditional arguments or as input data provided by a pipeline. The function can
define using one or both of these.

If the function defines one piece of data it can be used as either an input
shape or as arguments. There are different rules about how they get prepared for
the function, but generally can work interchangeably.

The definition can use any name for the value that will be provided inside the
scope of the body.

Most functions will use a shape structure to allow multiple arguments.

```comp

-- Defining a function with one piece of information.
-- Which can be called in either style.

double = :val~num(val + val)
bigger = :args~(a~num b~num)(a > b)

var.eight = double(4)
var.six = 3 |double()

var yes = bigger(1 2)
var no = (11 4) |bigger()

```

When a function defines two named definitions the first one must be provided as
through the pipeline input. The second one only defines arguments.

```comp
sort = :data~struct args~(~reverse)(
    # implementation...
)

data | sort (reverse)
```

**Function arguments** control behavior (transformations, options)  
**Pipeline input** provides data to work on

## Argument Scope Population

Functions may optionally define a set of arguments they accept. The shape for
these arguments can an optional name and/or type. They can also define an
optional default value for the argument.

When calling functions arguments can be explicitly defined and passed as a
struct of positional and named arguments to the function. Struct morphing allows
smart pairing values with their argument definitions.

While Comp it running it has access to several other scopes. The `ctx` and `mod`
scopes are automatically used to apply arguments to function calls.

- `mod` is the module scope, which is a set of hardcoded, predefined values. Any
  variables defined at the module scope become available to prepopulate any
  function arguments when called from within that module.

- `ctx` is a special scope that can be modified inside each function call. It's
  contents are automatically passed down the function call chain and available
  to any nested function calls.

The `mod` and `ctx` scopes can only contribute values to named arguments, there
is no positional matching of arguments. The types of values in these scopes must
match the definition of the argument shapes or they will be ignored.

There is no way to access these scopes directly, they are only able to function
arguments. The ctx scope can be modified inside any function and it's contents
will be passed down the call chain. Each module also has a chance to prepopulate
the context in specially defined structures that run under specific runtime
contexts.

This means arguments for functions will resolve from these locations (from
lowest to highest priority)

- Default value in the argument shape definition
- Named fields assigned to `mod` scope
- Named fields assigned to `ctx` scope
- Named and positional fields provided as arguments using standard morphing
  rules

```comp
process = :args~(x ~num timeout ~num = 30) (
    (args.x args.timeout)
)

example-process-calls :(
(
    var.as-arg1 = process (2)  ; (2 30)
    var.as-arg2 = process (3 4)  ; (3 4)
    var.as-arg3 = process (timeout=5 6)  ; (6 5)

    ctx.timeout = 8
    var.as-ctx1 = process (7)  ; (7 8)

    ctx.x = 9
    var.as-ctx2 = process ()  ; (9 8)
)
```

## Lazy Evaluation

Functions that use a body defined with `()` curly braces will have their results
lazily computed.

This behavior is transparent to users of the structures, but it allows some
optimizations where some data is not needed.

Functions compute fields on-demand rather than all at once:

```comp
expensive-analysis = :~(data)(
    summary = data | compute-summary ()
    statistics = data | deep-statistical-analysis ()
    visualization = data | generate-charts ()
    report = compile-full-report ()
)

; So far, none of the functions have been evaluated
; Only computes what's needed
var.analysis = data |expensive-analysis()
var.quick-view = analysis.summary()  ; Only computes summary
var.full = analysis(summary statistics)  ; Computes two fields
```

As fields are computed, their results are cached and the structure eventually
behaves like a regular structure literal. There are a few restrictions on the
lazy computation.

- Any function that acquires external resources with handles will immediately
  evaluate up until the point where all potental handles have been acquired.
- This includes any calls to other functions that access handles.

## Pure Functions

Functions can optionally be marked pure. Pure functions are not allowed to
create or use `^handle` references. This means their computation is entirely
deterministic. Pure functions are able to be evaluated at build time.

Pure functions are only able to call other pure function. Pure functions can
pass through handle values, and can even drop them, making them invalid.

Pure functions are defined with a `pure func` operator.

```comp
fibonacci = :n~num pure (
    n | if:it(it <= 1) :(it) :(
        let a = (n - 1) | fibonacci
        let b = (n - 2) | fibonacci
        a + b
    )
)

validate-email = :~email~text) (
    email |match("^[^@]+@[^@]+$")
)
```

Pure functions:

- Cannot access resources (filesystem, network, time)
- Cannot call non-pure functions
- Enable build-time evaluation and caching
- Allow safe parallelization

## Function Overloads

Multiple functions can be defined with the same name. These are treated as
overloads. At runtime one of the implementations will be chosen based on
matching the shape of the input value. This dynamic dispatch is not based on the
arguments, in fact each implementation could have different arguments.

```comp
d2.render = :pt~point-2d("2D point")
d3.render = :pt~point-3d("3D point")

(x=5 y=10) |render()  # "2D improved" - strong wins
(x=5 y=10 z=15) |render()  # "3D point" - more specific
(5 10) |render()  # "2D improved" - positional
```

The overloaded implementation must be unambiguous or cause build-time error. Use
`=?` (weak) or `=*` (strong) assignment to break ties. There still may be
runtime failures if the incoming data is unable to pick one specific
implementation.

## Function Linking

Adjacent functions in a pipeline can define an additional side channel for
passing data. This is how builtin conditional functions like `if` and `else` can
coordinate as peer functions.

When a function is defined it can use the `link` keyword to define a set of
other functions it can link to. If this struct of function references does not
include a `nil` then the function must follow one of the defined functions.

When this is used an additional `link` variable is added to the function's
namespace. This value contains one field that contains the name of the defined
function that preceded this call.

This data linking only passes through a single call in a pipeline. A function
that wants to provide linked data to following functions also needs to use the
link definition, but will use a `(nil)` value to specify that it has no
requirements itself.

```comp
engine= :link=(nil) (
    link = "train says, "
)

car= :link=(engine car) (
    link = link | format("$(link) chugga")
)

caboose= :link=(engine car) (
    link = link | format("$(link) choo choo")
)

engine() |car() |car() |caboose() # "train says, chugga chugga choo choo"
```

In this example, there will be a build time failure if `car` or `caboose` are
called without a preceding engine.

## Function Extensions

A function can be defined as an extension of another function, allowing you to
wrap existing behavior with additional logic before and after the call. If
you're familiar with decorators in other languages, extensions serve a similar
purpose.

The extension inherits the original function's documentation, arguments, input
shapes, and other attributes. When you call the extension, you control whether
and when the underlying function runs.

Common uses:

- Add logging or debugging output
- Validate or transform arguments before calling the original
- Process or modify the return value
- Add optional behavior (like caching) without changing the original function

When extended the function namespace has an additional `extend` variable in the
namespace which identifies the arguments and reference to the original function.
The common `in` variable still represents the input for the function.

```comp
logged-trim = :extends=trim args~(log ~logger) (
    args.log |info("Someone called trim with $(extend.args)")
    in |extend.base(extend.args)
)
```

## Blocks and Control Flow

Any statement or structure can be wrapped in a deferred container called a
block. Blocks are use like simple functions that take no arguments.

Similar to function bodies, blocks can be defined using the different braces
like `()` `()` and `[]`, and reuse the same rules and syntax these structure
syntaxes generate. A block definition uses one of these braces preceded with a
colon `:` character.

Blocks capture the scope of the functions they are defined in. This allows them
to acces and modify local variables shared with the function they come from.

```comp
var.first-five-block = :(trim (head size=5))
var.start = "Alphabets" |first-five-block ()  # "Alpha"
```

### Function Arguments

Blocks are often used in function arguments to define logic and behavior. The
language supports a special syntax to attach block definitions to function
arguments outside of the argument syntax. Functions using this alternative block
literals for arguments do not need to pass an empty `()` arguments if there are
arguments.

This is commonly used for conditionals and iteration functions that allow a body
of operations to be passed as an argument.

```comp
var.path = arg.path
if(path == nil) : (
    var.path = "placeholder.txt"
)
read-values (path) |sum : (
    var.distance = line-length(it)
    distance * distance
)
```
