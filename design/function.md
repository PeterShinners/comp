# Functions and Blocks

Blocks and functions are both deferred structure literals. They are
evaluated with optional input and argument data that match defined shapes.
Functions are assigned names are part of the module's namespace.

Invoking a function or block is visually represented by annotating a
structure literal as arguments for a callable.

To call a function, it must be referenced from the namespace and apply a set of
arguments, even if that set of arguments is empty. Data can be passed as an
input to the function by preceding the function with a pipe `|` operator, which
is a way of chaining function results to a series of operations.

## Definition

Blocks and definitions are defined by prefixing a structure literal with a `:`.
A simple block is just any value prefixed with the colon. 

```comp
simple = :{4 + 4}  # A hardcoded result
get-version = :{mod.version}   # Fetch constant value from module


```comp
calculate-area = ~{width ~num height ~num}
(
    area = width * height
    perimeter = (width + height) * 2
    diagonal = (width ** 2 + height ** 2) ** 0.5
)

get-timestamp arg ~{format ~str}
(
    let current = now/time
    let formatted = current | format/time arg.format
    {current formatted}
)

; Functions automatically morph inputs
{10 20} | calculate-area {}               ; Positional matching
{height=15 width=25} | calculate-area {}  ; Named matching
```

Each statement starts with fresh input. Field references cascade through output
to input. The last expression becomes the return value.

**Function arguments** control behavior (transformations, options)  
**Pipeline input** provides data to work on

## Definition Syntax

Functions consist of several parts:

- **Name** - Prefixed with `|` matching how it's referenced
- **Body** - Structure definition executed on invocation
- **Shape** - Expected input structure type (optional)
- **Arguments** - Secondary shape for configuration (optional)
- **Pure** - Keyword marking pure functions (optional)

```comp
; Simple inline
!func double ~{~num} (in * 2)

; Pure function
!pure !func add ~{~num} arg ~{n ~num} (in + arg.n)

; Multi-line with arguments
!func filter-items ~{items[]} arg ~{threshold ~num = 0}
(
    items | filter :(it > arg.threshold)
)
```

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
contents are automatically passed down the function call chain and available to
any nested function calls.

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
!func process args ~{x ~num timeout ~num = 30}
(
    {args.x args.timeout}
)

!func example-process-calls ~nil
(
    let as-arg1 = process {2}  ; {2 30}
    let as-arg2 = process {3 4}  ; {3 4}
    let as-arg3 = process {timeout=5 6}  ; {6 5}

    ctx timeout = 8
    let as-ctx1 = process {7}  ; {7 8}

    ctx x = 9
    let as-ctx2 = process {}  ; {9 8}
)
```

## Lazy Evaluation

Functions that use a body defined with `{}` curly braces will have their results
lazily computed.

This behavior is transparent to users of the structures, but it allows some
optimizations where some data is not needed. 

Functions compute fields on-demand rather than all at once:

```comp
!func expensive-analysis ~{data}
{
    summary = data | compute-summary {}
    statistics = data | deep-statistical-analysis {}
    visualization = data | generate-charts {}
    report = compile-full-report {}
}

; So far, none of the functions have been evaluated
; Only computes what's needed
let analysis = data | expensive-analysis
let quick-view = analysis.summary      ; Only computes summary
let full = analysis ~{summary statistics}  ; Computes two fields
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
!pure !func fibonacci ~{n ~num}
(
    n | if :(it <= 1) :(it) :(
        let a = (n - 1) | fibonacci
        let b = (n - 2) | fibonacci
        a + b
    )
)

!pure !func validate-email ~{email ~str}
(
    email | match/str "^[^@]+@[^@]+$"
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
!func render ~point-2d ("2D point")
!func render ~point-3d ("3D point")

{x=5 y=10} | render           ; "2D improved" - strong wins
{x=5 y=10 z=15} | render      ; "3D point" - more specific
{5 10} | render               ; "2D improved" - positional
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
link definition, but will use a `{nil}` value to specify that it has no
requirements itself.

```comp
!func engine ~nil link {nil}
(
    let link = "train says, "
)

!func car ~nil link {engine car}
(
    let link = "${link} chugga"
)

!func caboose ~str link {engine car}
(
    let link = "${link} choo choo"
)

engine() | car() | car() | caboose() ; "train says, chugga chugga choo choo"
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

!func logged-trim extends trim args ~{log ~logger}
(
    args.log |info "Someone called trim with ${extend.args}"
    in | $extend.base ($extend.args)
)
```

## Blocks and Control Flow

Any statement or structure can be wrapped in a deferred container called a
block. Blocks are use like simple functions that take no arguments.

Similar to function bodies, blocks can be defined using the different braces
like `{}` `()` and `[]`, and reuse the same rules and syntax these structure
syntaxes generate. A block definition uses one of these braces preceded with a
colon `:` character.

Blocks capture the scope of the functions they are defined in. This allows them
to acces and modify local variables shared with the function they come from.

```comp
let first-five-block = :(trim {#head size=5})

let start = "Alphabets" | first-five-block {} ;  "Alpha"
```

### Function Arguments

Blocks are often used in function arguments to define logic and behavior. The
language supports a special syntax to attach block definitions to function
arguments outside of the argument syntax. Functions using this alternative block
literals for arguments do not need to pass an empty `{}` arguments if there are
arguments.

This is commonly used for conditionals and iteration functions that allow a body
of operations to be passed as an argument.

```comp
let path = arg.path
if (path == nil) :(
    let path = "placeholder.txt"
)
read-values (path) | sum :{
    let distance = it | line-length {}
    distance * distance
}
```
