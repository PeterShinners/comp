# Functions and Blocks

*Defining and executing Comp functions.*

## Overview

Functions in Comp are designed around a simple idea: take a structure, transform it, return a new structure. This consistency makes code more predictable and composable than traditional function systems.

Every function receives pipeline input and generates new output, while arguments configure behavior separately from data flow. This separation eliminates the confusion between "what am I working on?" and "how should I work on it?" that plagues many languages.

Functions are references, not values—you can't stuff them in variables like JavaScript, but you can invoke them through pipelines and compose them with blocks. This design creates clear boundaries between code and data while enabling powerful composition patterns that feel natural to write.

Functions return lazy structures that are backed by a pipeline of operations. The pipeline behind the structure can be accessed and modified. This is most often done with the (`|-|`) pipeline wrench operator which works with a function that takes the incoming pipeline description and generates a new pipeline description. This enabling meta-operations like progress tracking, query optimization, and performance profiling.

At the core, function definitions and structure literals work identically—same parsing rules, same assignments, same operations. The difference is timing: structures evaluate immediately, functions become recipes for later execution. Functions come with a few extras, like pipeline inputs, documentation, and arguments.

This unified approach means less syntax to learn and more consistent behavior. Whether you're building a simple data transformation or a complex polymorphic system, functions provide composable abstractions that scale naturally. For more details on structure operations and assignment patterns, see [Structures, Spreads, and Lazy Evaluation](structure.md).

These principles create a function system that balances power with simplicity.
Whether building simple data transformations or complex polymorphic systems,
functions provide consistent, composable abstractions for computation.

## Function Definition Fundamentals

Functions are defined with the `!func` operator. they become part of the module
namespace and normally be referenced anywhere within the module, or by other
modules using an `!import`.

The shape a function defines is the schema used to match the definition of the incoming structure. No inheritance hierarchies required, just data that fits the expected shape.

This structural approach eliminates the type ceremony that makes other languages verbose. Your function works with any data that has the right shape, period. Arguments are specified separately, maintaining a clear distinction between what you're processing and how you want to process it.

For comprehensive information about the shape system, morphing
operations, and structural typing, see [Shapes, Units, and Type
System](shape.md).

```comp
!func |calculate-area ~{width ~num height ~num} = {
    area = width * height
    perimeter = (width + height) * 2
    diagonal = (width ** 2 + height ** 2) ** 0.5
    {area perimeter diagonal}
}

!func |get-timestamp arg ~{format ~str} = {
    current = [|now/time]
    formatted = [current |format/time $arg.format]
    {current formatted}
}

; Functions automatically morph inputs
[{10 20} |calculate-area]               ; Positional matching
[{height=15 width=25} |calculate-area]  ; Named matching
```

Each statement in the function body begins with fresh pipeline input through
`$in`. Field references use undecorated tokens that cascade through output being
built to input. The implicit return value is the last expression in the function
body.

Function arguments are intended to be used for:

* Modifying how a function behaves
* Allowing definition of transformations or operations through blocks

The pipeline input structure is intended to be used for:

* Data the function is intended to work on or transform


## Function Definition Syntax

Functions are defined with the `!func` operator at the outermost scope of a
file. A function is comprised of several required and optional parts.

* **Name** Must be prefixed with `|` pipe, which matches how this
function is referenced later. This immediately follows the `!func` operator.
* **Body** The final part of the function definition is a regular structure
definition. It's contents are not executed immediately but will be performed
when the function is invoked to create a new structure value.
* **Documentation** The `!doc` operator is used before the function definition
to attach an optional description. This is intended for a shorter summary
definition. Longer form descriptions and examples can be attached from other
parts of the module.
* **Shape** Either a shape reference or an inline shape definition. This
describes the type of data the function expects to work on. The fields this
provides will be available from the `$in` scope, or by using it's fields as
undecorated field names inside the function.
* **Arguments** Is a secondary, optional shape definition that is used to
provide arguments to the function. Arguments are intended to control the way a
function behaves, not the data it works on. Arguments can also define special
block values which are like callbacks. The arguments are available in the `^arg`
namespace, which is normally accessed through the `^` operator.
* **Pure** The function can be preceded with a `!pure` statement to guarantee
it has no side effects and executes deterministically.

There is no definition for the shape of the output structure from the function.
The function can use whatever flow control, error handling, or fetched data
results it wants to become its value.

```comp
; Simple inline definition
!func |double ~{~num} = { $in * 2 }

!pure
!func |add ~{~num} arg ~{n ~num} = { $in + $arg.n }

; Multi-line for clarity
!func |filter-items
    ~{items[]}
    arg ~{threshold ~num = 0} = {
    [items |filter :{$in > $arg.threshold}]
}

!func |process-order ~order-data arg ~process-config = {
    ; Implementation focuses on logic, not type declarations
    validated = [$arg.validate? |if :{#true}
        :{[order |validate]}
        :{order}]

    processed = [validated |apply-priority $arg.priority]
}
```

## Argument Shapes and Scope Masking

Function argument shapes serve dual purposes: they validate passed arguments and control what fields are visible in the function's scope. This creates disciplined function boundaries where functions can only access the arguments they explicitly declare, preventing accidental coupling and making dependencies visible.

### Automatic Scope Masking

When a function is invoked, its argument shape automatically masks the module scope (`$mod`) and context scope (`$ctx`) to only expose fields defined in the argument shape. This happens in addition to validating the passed arguments:

```comp
!func |process arg ~{x ~num y ~num timeout ~num = 30} = {
    ; At function entry, four automatic operations occur:

    ; 1. Strict morph for passed arguments
    ;    $arg = passed_args ~* {x ~num y ~num timeout ~num = 30}
    ;    - Validates exact structure (fails on extra/missing fields)
    ;    - Applies defaults (timeout=30)
    ;    - Result: $arg is immutable, exactly matches arg shape

    ; 2. Permissive mask for context scope
    ;    $ctx_local = $ctx_shared ~? {x ~num y ~num timeout ~num = 30}
    ;    - Filters to only fields in both $ctx and arg shape
    ;    - No defaults applied
    ;    - Example: $ctx={x=1, a=2, b=3} → $ctx_local={x=1}

    ; 3. Permissive mask for module scope
    ;    $mod_local = $mod_shared ~? {x ~num y ~num timeout ~num = 30}
    ;    - Same filtering as $ctx

    ; Access through scopes:
    ;    $arg.x, $arg.y, $arg.timeout (validated args)
    ;    $ctx.x (filtered context)
    ;    $mod.x, $mod.y (filtered module)
}
```

This masking ensures that functions can only access the arguments they declare, making function signatures honest about their dependencies.

### Scope Access and Precedence

Functions have access to multiple scopes with well-defined semantics:

| Scope | Access | Write | Masking | Description |
|-------|--------|-------|---------|-------------|
| **`$arg`** | Read-only | ❌ No | Filtered | Merged arguments from $arg/$ctx/$mod |
| **`$ctx`** | Read-write | ✅ Yes | Permissive (`~?`) | Local + shared context scope |
| **`$mod`** | Read-write | ✅ Yes | Permissive (`~?`) | Local + shared module scope |
| **`$in`** | Read-only | ❌ No | None | Pipeline input data |
| **`$out`** | Read-only | ❌ No | None | Computed output structure |
| **`$var`** | Read-write | ✅ Yes | None | Function-local variables |

**Precedence for `$arg` merging:**
1. Direct arguments passed to function (highest priority)
2. Matching fields from `$ctx` (context/environment)
3. Matching fields from `$mod` (module scope fallback)
4. Default values from argument shape

```comp
!func |example arg ~{x ~num y ~num} = {
    ; Given:
    ; Direct args = {x=5}
    ; $ctx = {y=2}
    ; $mod = {y=3}
    ; 
    ; Result: $arg = {x=5, y=2}
    ; - x from direct args
    ; - y from $ctx (overrides $mod)

    $arg.x      ; Returns 5 (from direct args)
    $arg.y      ; Returns 2 (from $ctx, not $mod)

    $ctx.x      ; Returns undefined (not in context)
    $mod.y      ; Returns 3 (from module scope)

    ; Write operations
    x = 100           ; Writes to $out.x
    $ctx.x = 200      ; Writes to $ctx (both local and shared)
    $mod.data = 300   ; Writes to $mod (both local and shared)
    $var.temp = 42    ; Writes to function-local variable
````
    ; Invalid operations
    $ctx.$x = 100     ; ❌ ERROR: $ctx$ is read-only
    $arg.x = 100      ; ❌ ERROR: $arg is immutable
}
```

### Write-Through Behavior

Writes to `$ctx` and `$mod` update both the function's local masked view and the shared scope that persists across function calls:

```comp
!func |update-context arg ~{counter ~num} = {
    ; $ctx_shared before call: {counter=0, other=10, data=20}
    ; $ctx_local after mask: {counter=0} (only 'counter' in arg shape)

    $ctx.counter = $ctx.counter + 1
    ; Updates:
    ;   - $ctx_local.counter = 1
    ;   - $ctx_shared.counter = 1

    ; Can write to fields not in arg shape - they're added to both
    $ctx.timestamp = [|now/time]
    ; Adds:
    ;   - $ctx_local.timestamp = <time>
    ;   - $ctx_shared.timestamp = <time>

    ; Read from $arg reflects passed arguments
    $arg.counter    ; Returns value from passed argument
    $ctx.counter    ; Returns 1 (updated local value)
}

; Subsequent call sees the updated shared context
[|update-context counter=5]  ; $ctx_shared.counter is now 1
```

This write-through behavior enables functions to communicate through shared scopes while maintaining argument discipline through masking.

### Isolated Function Boundaries

The masking system creates true function isolation - each function only sees the arguments it declares:

```comp
$ctx = {
    user="alice"
    session="abc123"
    admin-key="secret"
    debug=#true
}

!func |safe-handler arg ~{user ~str} = {
    ; $ctx_local = $ctx ~? {user ~str}
    ; $ctx_local = {user="alice"} only

    $arg.user       ; ✅ Can access 'user' (in arg shape)
    $ctx.user       ; ✅ Can access through $ctx
    $ctx.admin-key  ; ❌ Not visible (not in arg shape)
    $arg.debug      ; ❌ Not available (not in arg shape)

    ; This function cannot accidentally access sensitive fields
}

!func |debug-handler arg ~{user ~str debug ~bool} = {
    ; $ctx_local = $ctx ~? {user ~str debug ~bool}
    ; $ctx_local = {user="alice" debug=#true}

    $arg.debug      ; ✅ Can access 'debug' (explicitly declared)

    ; Still cannot see admin-key (not declared)
}
```

This approach makes function dependencies explicit and prevents accidental access to global state, while still allowing controlled access through declared arguments.

## Lazy Functions and Deferred Execution

Functions are lazy by default—their fields compute on-demand rather than all at once when the function is called. This creates generators where expensive operations are deferred until their results are actually needed. Once computed, values are cached, so functions eventually behave like regular structures after full evaluation.

This solves the common problem of expensive calculations in objects: do you compute everything upfront (slow startup) or compute on-demand every time (slow access)? Lazy functions give you the best of both worlds.

```comp
!func |infinite-sequence arg ~{start ~num step ~num} = {
    [range |count |map :{$arg.start + $in * $arg.step}]
}

!func |expensive-analysis ~{data} = {
    summary = [data |compute-summary]
    statistics = [data |deep-statistical-analysis]
    visualization = [data |generate-charts]
    report = [|compile-full-report]
}

; Only computes what's needed
analysis = [data |expensive-analysis]
quick-view = analysis.summary    ; Only computes summary
full = analysis ~{summary statistics}  ; Computes two fields
```

For comprehensive coverage of iteration patterns, core iterator functions like `|map` and `|filter`, and stream abstractions, see [Iteration and Streams](loop.md).

## Privacy Structures and Explicit Output

Functions can use privacy structures with the `&{}` prefix to disable automatic field export. In privacy mode, statements don't automatically contribute to the function's output—only explicit modifications to the `$out` scope generate results. This is essential for functions that need many intermediate calculations without exposing internal implementation details.

Privacy structures solve the common problem of functions that need complex internal logic but simple outputs. Instead of needing separate helper functions or complex scoping, you can do all your work in one place while controlling exactly what gets exposed.

```comp
; Regular function - every statement contributes to output
!func |messy-calculation ~{data} = {
    validation = [data |validate]        ; This becomes output field
    temp-result = [validation |process]  ; This becomes output field  
    final = [temp-result |finalize]      ; This becomes output field
    ; Result: {validation=... temp-result=... final=...}
}

; Privacy function - only explicit $out modifications are exported
!func |clean-calculation ~{data} = &{
    $var.validation = [data |validate]        ; Internal only
    $var.temp-result = [$var.validation |process]  ; Internal only
    $var.final = [$var.temp-result |finalize]     ; Internal only
    
    ; Only these become output
    $out.result = $var.final
    $out.success = #true
    ; Result: {result=... success=#true}
}

; Privacy function for controlled generators (still lazy by default)
!func |filtered-sequence arg ~{filter-fn} = &{
    $var.raw-data = [|get-large-dataset]      ; Internal processing
    $var.processed = [$var.raw-data |expensive-transform]

    ; Only expose the final filtered results
    $out.result = [data |$arg.filter-fn $var.processed]
}
```

Privacy structures work with all the same mechanisms as regular structures—shape morphing, argument handling, and scope management. The only difference is that field assignment doesn't automatically export unless it targets `$out` explicitly.

```comp
; Mixed approach - some fields automatic, some controlled
!func |user-profile ~{user-id} = &{
    $var.user-data = [user-id |database.fetch]
    $var.permissions = [$var.user-data |calculate-permissions]
    $var.preferences = [$var.user-data |load-preferences]
    
    ; Automatic exports (these create output fields)
    display-name = $var.user-data.name
    avatar-url = $var.user-data.avatar
    
    ; Controlled exports via $out
    $out.can-admin = ($var.permissions.admin?)
    $out ..= [$var.preferences |filter-public]
}
```

## Pure Functions and Isolation

Pure functions guarantee deterministic computation without side effects. Defined with `!pure`, they execute in a completely resource-free context. This enables build-time evaluation, safe parallelization, and use in shape constraints or unit definitions.

The `!pure` decorator creates hard enforcement—these functions literally cannot access the outside world because no resource token exists in their context. They cannot read files, access the network, get the current time, create stores, or access module runtime state. This creates an unforgeable boundary between computation and effects.

```comp
!pure
!func |fibonacci ~{n ~num} = {
    [n |if :{$in <= 1} :{$in} :{
        $var.a = [n - 1 |fibonacci]
        $var.b = [n - 2 |fibonacci]
        $var.a + $var.b
    }]
}

!pure
!func |validate-email ~{email ~str} = {
    [$in.email |match/str "^[^@]+@[^@]+$"]
}

!pure
!func |transform ~{data} = {
    ; Can compute, validate, transform
    ; Cannot: access files, network, time, random, stores
    ; Cannot: access $mod runtime state or |describe
    [$in.data |normalize |validate]
}
```

## Block Arguments

Blocks are deferred structure definitions that serve as powerful callbacks and control flow mechanisms. They solve the common problem of passing behavior to functions without the complexity of function pointers or the verbosity of interface implementations.

Blocks exist in two states: ephemeral blocks (raw `:{...}` syntax) that cannot be invoked directly, and callable blocks that have been typed with an input shape. Functions that expect blocks can also accept simple values, which are automatically wrapped in trivial blocks for convenience—write less, express more.

## Block Syntax

Blocks are defined using `:{...}` syntax, which creates a deferred structure that captures its definition context. For the common case of a block containing a single pipeline, the shorthand syntax `:[...]` can be used instead of `:{[...]}`, reducing nesting and improving readability.

```comp
; Standard block syntax - full structure
items |map :{
    validated = [$in |validate]
    enhanced = [validated |enhance]
    enhanced
}

; Pipeline-block shorthand - single pipeline only
items |map :[|validate |enhance]

; These are equivalent:
items |filter :{[$in.value > 10]}
items |filter :[|value > 10]
```

The `:[...]` shorthand is purely syntactic sugar and desugars to `:{[...]}` at parse time, creating identical AST structures. Use the shorthand for simple transformations and the full block syntax when multiple statements are needed.

Blocks are defined in arguments to functions like a regular structure with a `.`
dot prefix. Functions that expect block arguments can also accept simple values,
which are automatically wrapped in trivial blocks for convenience.

Functions may invoke their blocks as often as needed. The function must describe
the incoming shape used for each block. The function can control the evaluation
context and frequency of when the block is invoked.

Like regular arguments, blocks can be passed as named or positionally. When
passed as named argument they use the dotted prefix instead of an equal sign.
For simple values passed to named block parameters, use regular named argument
syntax without the dot prefix.

Ephemeral blocks are created with `:{...}` syntax but cannot be invoked until they are typed. When passed to function arguments, they are automatically morphed to match the expected block input shape. This provides type safety while allowing flexible block definitions.

Block arguments are determined by the function's arg shape definition. When the
parser encounters `:{}`, it creates a deferred block.
Blocks capture their definition context, allowing them to reference local
variables and scope values through the `$` (variables) and `^` (arguments)
prefixes. Simple values passed to block arguments are automatically wrapped in
blocks that return the value.

Functions invoke blocks using the `|:` operator, which executes the block with
the current pipeline value as input. Block parameters in function argument
shapes can specify the expected input shape using `~:{shape}` syntax.

```comp
!func |with-retry ~{operation} arg ~{on-error ~:{~str}} = {
    $var.attempts = 0
    [operation |while :{$var.attempts < 3} :{
        $var.result = [operation |execute |? :{
            $var.attempts = $var.attempts + 1
            $var.error-msg = %"Attempt %{$var.attempts} failed"
            [$var.error-msg |: $arg.on-error]  ; Invoke block with string input
            [$var.attempts |if :{$in >= 3} :{operation} :{#skip}]
        }]
    }]
    $var.result
}

!func |process-items ~{items[]} arg ~{
    transform ~:{~item}
    validate ~:{~item}
    callback ~:{~num ~num}
} = {
    $var.processed = [items |map :{[$in |: $arg.transform]}]
    $var.valid = [$var.processed |filter :{[$in |: $arg.validate]}]
    $var.count = [$var.valid |count]
    $var.total = [$var.valid |sum :{amount}]
    [{$var.count $var.total} |: $arg.callback]  ; Invoke with two numbers
}

; Usage with explicit blocks
[data |with-retry on-error:{[error-msg |log]}]

; Usage with simple values - automatically wrapped
$var.style = [complete |if :{$in} :"strikethrough" :"normal"]
$var.variant = [priority |if :{$in == $in.urgent} :"primary" :"secondary"]

; Named block arguments can use simple values too
[items |process-items
    transform:{[$in |enhance |normalize]}  ; explicit block
    validate=#true                         ; simple value for block parameter
    callback:{[$var.count $var.total |summarize]}] ; explicit block with two inputs

; Mixed usage in conditionals
[|prepare-data :{[|called-unnamed-block]} named:{[|called-named-block]}]
[|prepare-data simple-value named=simple-named-value]

; Complex control flow with mixed block styles
[items |process-batch
    transform:{[$in |enhance |normalize]}
    validate:{$in.score > $in.threshold}
    on-success="completed"]  ; Simple string wrapped automatically
```

## Block Invocation

Blocks can be invoked using the `|:` operator, which executes the block with the current pipeline value as input. This is how functions internally invoke their block arguments, but it's also available as a general pipeline operator for any block value.

```comp
; Block stored in variable
$var.validator = :{[$in |check-format |validate-rules]}
$var.result = [data |: $var.validator]  ; Invoke the block

; Block literals can be invoked directly
result = [data |: :{[$in |transform |validate]}]

; Block in structure
handlers = {
    process = :{[$in |transform |save]}
    validate = :{[$in.email |check-email]}
}
[user |: handlers.validate]  ; Invoke validation block

; Chaining block invocations
pipeline = :{[$in |step1 |step2 |step3]}
final = [input |: pipeline |post-process]
```

## Blocks as Partial Pipeline Fragments

Blocks can be used to define partial pipeline fragments—sequences of connected operations that don't specify their input data. These pipeline fragments become reusable transformation chains that can be applied to different data sources or composed into larger processing workflows.

Unlike complete pipelines that start with specific data, partial pipeline fragments begin with `$in` and chain operations from there. This creates portable transformation logic that can be shared, tested independently, and combined in flexible ways.

```comp
; Partial pipeline fragments for data processing
$var.validation-chain = :[
    $in |check-format
         |validate-schema  
         |sanitize-input
]

$var.enrichment-chain = :[
    $in |lookup-metadata
         |calculate-scores
         |add-timestamps
]

$var.output-chain = :[
    $in |format-results
         |apply-templates
         |compress-data
]

; Apply fragments to different data sources
user-data = [raw-users |: $var.validation-chain |: $var.enrichment-chain]
system-data = [raw-systems |: $var.validation-chain |: $var.output-chain]

; Compose fragments into complete workflows
$var.complete-workflow = :[
    $in |: $var.validation-chain
         |: $var.enrichment-chain  
         |: $var.output-chain
]

; Use in function arguments for flexible behavior
!func |process-data ~{data} arg ~{pipeline ~block} = {
    [$in.data |: $arg.pipeline |save-results]
}

[user-records |process-data pipeline=$var.complete-workflow]
```

Partial pipeline fragments excel at creating reusable transformation logic. They enable separation of concerns where data validation, enrichment, and formatting can be defined independently and combined as needed. Functions can accept pipeline fragments as arguments, allowing callers to customize processing behavior while maintaining type safety through block shapes.

This can also be done by defining regular functions in the module, but some situations are simplified by defining these on the fly, and passing these operations around as values.

```comp
; Library of reusable pipeline fragments
$var.fragments = {
    clean = :{[$in |trim |normalize |remove-duplicates]}
    analyze = :{[$in |extract-features |calculate-metrics]}
    secure = :{[$in |encrypt-sensitive |hash-identifiers]}
    format = :{[$in |apply-schema |compress |encode]}
}

; Flexible composition for different use cases
batch-job = :{
    [$in |: $var.fragments.clean
         |: $var.fragments.analyze
         |: $var.fragments.format]
}

secure-batch = :{
    [$in |: $var.fragments.clean
         |: $var.fragments.secure
         |: $var.fragments.format]
}

; Pipeline fragments can be modified by wrench operators too
enhanced-workflow = :{
    [$in |: $var.fragments.clean
         |-|progressbar           ; Add progress tracking
         |: $var.fragments.analyze
         |-|profile-time         ; Add timing profiling
         |: $var.fragments.format]
}
```

This pattern transforms blocks from simple callbacks into powerful pipeline construction tools. By separating the definition of transformation logic from the data it operates on, partial pipeline fragments enable more modular, testable, and reusable code architectures.

## Argument Spreading

Functions support spread operators for arguments, allowing predefined argument
sets to be reused and overridden. This enables flexible configuration patterns
and composable argument definitions.

```comp
!shape ~process-args = {
    verbose ~bool = #false
    debug ~bool = #false
    ..rest   ; Collect remaining fields
}

!func |process var process-args = {
    [|if $var.verbose :[
        |log "Verbose mode enabled"
    ]]
    ; ^rest contains unmatched fields
}

; Spread operators work like Python **kwargs
$var.preset = {verbose=#true debug=#true port=8080}
[server |configure ..$var.preset host="localhost" port=3000]
; Results in: {verbose=#true debug=#true host="localhost" port=3000}
; Note: explicit port=3000 overrides preset port=8080

; Tag-based flag arguments through shape morphing
!tag #sort-order = {#asc #desc}

!func |sort arg ~{order #sort-order = #asc} = {
    ; Tag field matches unnamed tag values during morphing
}

[$in.data |sort #desc]          ; Morphs to: {order=#desc}
[$in.data |sort]                ; Morphs to: {order=#asc} (default)

; Tags in variables work naturally
$var.order = #desc
[$in.data |sort $var.order]     ; Pass tag through variable

; Context-based configuration
$ctx.order = #desc
[$in.data |sort $ctx.order]     ; Use context value
```

## Function Overloads

Functions can be defined multiple times to describe working with different
shapes of inputs. The function definitions must be unambiguous or the module
will have a build-time error. The function definition can use `=?` weak or `=*`
strong assignment operators to break ambiguous ties.

The functions use the shape matching logic to select the most specific
implementation for the given input shape.

The tag system can be greatly used to control this dispatch, which has a strong
influence how shape matching is defined. Functions can dispatch from themselves
to weaker matches based on specific tags. For detailed information about tag
hierarchies and polymorphic dispatch mechanisms, see [Tag System](tag.md).

```comp
!func |render ~point-2d = {"2D point"}
!func |render ~point-2d =* {"2D improved"}  ; Strong assignment wins
!func |render ~point-3d = {"3D point"}

[{x=5 y=10} |render]           ; "2D improved" - strong assignment wins
[{x=5 y=10 z=15} |render]      ; "3D point" - more specific shape
[{5 10} |render]               ; "2D improved" - positional matching

; Tag-based dispatch with hierarchical scoring
!func |process ~{status=#status} = {"generic status"}
!func |process ~{status=#error.status} = {"error handler"}
!func |process ~{status=#error.network} = {"network specialist"}

[{status=#timeout.error} |process]  ; "error handler"
[{status=#network.error} |process]  ; "network specialist"
```

### Overload References

Functions references are defined by the function name. This reference uses all
possible overloaded implementations. Data like docstrings will be shared across
all implementations of the function. There is a separate `!doc impl` operator
that assigns documentation for a specific implementation, but these should be
meant for short summaries.

```comp
!doc "Process different types of data appropriately"

!doc impl "Saves to primary database"
!func |process ~user-data = {
    [data |validate-user |save-user]
}

!doc impl "Archives to time-series store"
!func |process ~system-data = {
    [data |validate-system |archive]
}

; Single describe shows all implementations
[|describe |process]
; Returns: {
;   doc: "Process different types of data appropriately"
;   module: current-module
;   implementations: [
;     {pipe: ~user-data, args: {}, impl-doc: "Saves to primary database"},
;     {pipe: ~system-data, args: {}, impl-doc: "Archives to time-series store"}
;   ]
; }
```

Even single-implementation functions follow this pattern internally, maintaining
consistency for introspection and future extension.


## Polymorphic Tag Overloads

Tags enable sophisticated polymorphic dispatch across module boundaries. When a
tag field is used for dispatch, the function is resolved based on the tag's
hierarchy. This creates extensible polymorphism without inheritance.

The tag dispatch examines the tag value, determines its hierarchy, and finds the
most specific function implementation. For explicit parent calls, partial tag
paths enable controlled polymorphic chains.

Regular overloading works when all definitions are in the same module. The base
module is not aware of any extended fields other modules may add to its tag
hierarchy. When tags are extended across different modules, the tag being used
defines where dynamic dispatch can find the correct implementation.

```comp
; Base module defines animal behaviors
!tag #animal = {#mammal #bird #reptile}

!func |speak ~{type #animal} = {"generic animal sound"}
!func |speak ~{type #mammal} = {"mammalian vocalization"}
!func |speak ~{type #bird} = {"chirp"}
!func |speak ~{type #reptile} = {"hiss"}

; Extended module adds specializations
!tag #mammal.animal = {#dog.mammal #cat.mammal}
!func |speak ~{type #dog.mammal} = {"woof"}
!func |speak ~{type #cat.mammal} = {"meow"}

; Polymorphic dispatch with nested tags
[{type=#bird} |speak]          ; "chirp"
[{type=#dog.mammal} |speak]    ; "woof"
[{type=#cat.mammal} |speak]    ; "meow"

; Cross-module polymorphism
creature = {type=#dog.mammal name=Rex}
[creature |speak]             ; "woof" - most specific match
```

## Function Security and Resource Access

Functions either have access to external resources or they don't—a simple binary model. Regular functions can access the filesystem, network, and other external systems through the single `resource` capability token. Pure functions execute in a completely resource-free context, guaranteeing deterministic behavior without side effects.

The security model is refreshingly honest: instead of pretending to offer fine-grained permissions that can't be properly enforced, Comp provides a clear boundary between pure computation and effectful operations. Regular functions inherit resource access from their callers, while pure functions operate in guaranteed isolation. For comprehensive details about the security model and resource system, see [Runtime Security and Permissions](security.md).

```comp
; Regular function with resource access
!func |backup-file arg ~{source ~str dest ~str} = {
    [$arg.source |read/file      ; Uses resource capability
                 |compress
                 |write/file $arg.dest]  ; Uses resource capability
}

; Pure function - no resource access
!pure
!func |compress ~{data} = {
    ; Deterministic compression algorithm
    ; Cannot access filesystem, network, time, etc.
    [data |apply-compression-algorithm]
}

; Mixed usage
!func |process-safely = {
    ; Validate with pure function first
    validated = [untrusted-input |validate-pure]
    
    ; Then use resources if valid
    [validated |if :{$in} :{
        [$in |save-to-disk]
    } :{
        {#invalid.fail}
    }]
}
```