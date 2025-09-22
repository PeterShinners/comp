# Functions and Blocks

*Defining and executing Comp functions.*

## Overview

Functions in Comp are designed around a simple idea: take a structure, transform it, return a new structure. This consistency makes code more predictable and composable than traditional function systems.

Every function receives pipeline input and generates new output, while arguments configure behavior separately from data flow. This separation eliminates the confusion between "what am I working on?" and "how should I work on it?" that plagues many languages.

Functions are references, not values—you can't stuff them in variables like JavaScript, but you can invoke them through pipelines and compose them with blocks. This design creates clear boundaries between code and data while enabling powerful composition patterns that feel natural to write.

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

!func |get-timestamp ^{format ~str} = {
    current = (|now/time)
    formatted = (current |format/time ^format)
    {current formatted}
}

; Functions automatically morph inputs
({10 20} |calculate-area)               ; Positional matching
({height=15 width=25} |calculate-area)  ; Named matching
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
* **Permissions** The function operator can be preceded with a `!pure` or
`!require` statements to control how permissions are handled when calling this
function.

There is no definition for the shape of the output structure from the function.
The function can use whatever flow control, error handling, or fetched data
results it wants to become its value.

```comp
; Simple inline definition
!func |double ~{~num} = { $in * 2 }

!func |add ~{~num} ^{n ~num} = { $in + ^n }

; Multi-line for clarity
!func |filter-items 
    ~{items[]} 
    ^{threshold ~num = 0} = {
    items |filter .{$in > ^threshold}
}

!func |process-order ~order-data ^process-config = {
    ; Implementation focuses on logic, not type declarations
    validated = ^validate? |if .{#true} 
        .{order |validate}
        .{order}
    
    processed = validated |apply-priority ^priority
}
```

## Lazy Functions and Deferred Execution

Functions can define lazy structures using `[]` brackets instead of `{}`. These create generators where fields compute on-demand—perfect for expensive operations or infinite sequences. Once computed, values are cached, so lazy structures eventually behave like regular ones.

This solves the common problem of expensive calculations in objects: do you compute everything upfront (slow startup) or compute on-demand every time (slow access)? Lazy structures give you the best of both worlds.

```comp
!func |infinite-sequence ^{start ~num step ~num} = [
    ($in |count |map {^start + $in * ^step})
]

!func |expensive-analysis ~{data} = [
    summary = ($in |compute-summary)
    statistics = ($in |deep-statistical-analysis)
    visualization = ($in |generate-charts)
    report = (|compile-full-report)
]

; Only computes what's needed
analysis = (data |expensive-analysis)
quick-view = analysis.summary    ; Only computes summary
full = analysis ~{summary statistics}  ; Computes two fields
```

## Privacy Structures and Explicit Output

Functions can use privacy structures with the `&{}` or `&[]` prefix to disable automatic field export. In privacy mode, statements don't automatically contribute to the function's output—only explicit modifications to the `$out` scope generate results. This is essential for functions that need many intermediate calculations without exposing internal implementation details.

Privacy structures solve the common problem of functions that need complex internal logic but simple outputs. Instead of needing separate helper functions or complex scoping, you can do all your work in one place while controlling exactly what gets exposed.

```comp
; Regular function - every statement contributes to output
!func |messy-calculation ~{data} = {
    validation = (data |validate)        ; This becomes output field
    temp-result = (validation |process)  ; This becomes output field  
    final = (temp-result |finalize)      ; This becomes output field
    ; Result: {validation=... temp-result=... final=...}
}

; Privacy function - only explicit $out modifications are exported
!func |clean-calculation ~{data} = &{
    @validation = (data |validate)        ; Internal only
    @temp-result = (@validation |process)  ; Internal only
    @final = (@temp-result |finalize)     ; Internal only
    
    ; Only these become output
    $out.result = @final
    $out.success = #true
    ; Result: {result=... success=#true}
}

; Privacy lazy function for controlled generators
!func |filtered-sequence ^{filter-fn} = &[
    @raw-data = (|get-large-dataset)      ; Internal processing
    @processed = (@raw-data |expensive-transform)
    
    ; Only expose the final filtered results
    ($in |^filter-fn @processed)
]
```

Privacy structures work with all the same mechanisms as regular structures—shape morphing, argument handling, and scope management. The only difference is that field assignment doesn't automatically export unless it targets `$out` explicitly.

```comp
; Mixed approach - some fields automatic, some controlled
!func |user-profile ~{user-id} = &{
    @user-data = (user-id |database.fetch)
    @permissions = (@user-data |calculate-permissions)
    @preferences = (@user-data |load-preferences)
    
    ; Automatic exports (these create output fields)
    display-name = @user-data.name
    avatar-url = @user-data.avatar
    
    ; Controlled exports via $out
    $out.can-admin = (@permissions.admin?)
    $out ..= (@preferences |filter-public)
}
```

## Pure Functions and Isolation

Pure functions guarantee deterministic computation without side effects. Defined with `!pure`, they receive an empty context and cannot access external resources. This enables build-time evaluation, safe parallelization, and use in shape constraints or unit definitions.

The distinction between `!pure` and regular functions is about capability, not syntax. Pure functions can call other functions, but those functions fail immediately if they attempt resource access. This creates a clear, enforceable boundary between computation and effects, no more wondering if that "simple calculation" is secretly making network calls.

```comp
!pure
!func |fibonacci ~{n ~num} = {
    ($in |if .{$in <= 1} .{$in} .{
        @a = ($in - 1 |fibonacci)
        @b = ($in - 2 |fibonacci)
        @a + @b
    })
}

!pure
!func |validate-email ~{email ~str} = {
    $in |match/str "^[^@]+@[^@]+$"
}
```

## Block Arguments

Blocks are deferred structure definitions that serve as powerful callbacks and control flow mechanisms. They solve the common problem of passing behavior to functions without the complexity of function pointers or the verbosity of interface implementations.

Blocks exist in two states: ephemeral blocks (raw `.{...}` syntax) that cannot be invoked directly, and callable blocks that have been typed with an input shape. Functions that expect blocks can also accept simple values, which are automatically wrapped in trivial blocks for convenience—write less, express more.

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

Ephemeral blocks are created with `.{...}` syntax but cannot be invoked until they are typed. When passed to function arguments, they are automatically morphed to match the expected block input shape. This provides type safety while allowing flexible block definitions.

Block arguments are determined by the function's arg shape definition. When the
parser encounters `.{}` in argument position, it creates a deferred block.
Blocks capture their definition context, allowing them to reference local
variables and scope values through the `$` (variables) and `^` (arguments)
prefixes. Simple values passed to block arguments are automatically wrapped in
blocks that return the value.

Functions invoke blocks using the `|.` operator, which executes the block with
the current pipeline value as input. Block parameters in function argument
shapes can specify the expected input shape using `~block{shape}` syntax.

```comp
!func |with-retry ~{operation} ^{on-error ~block{~str}} = {
    @attempts = 0
    ($in |while .{@attempts < 3} .{
        @result = ($in |operation |? .{
            @attempts = @attempts + 1
            @error-msg = %"Attempt ${@attempts} failed"
            (@error-msg |. ^on-error)  ; Invoke block with string input
            ($in |if .{@attempts >= 3} .{$in} .{#skip})
        })
    })
    @result
}

!func |process-items ~{items[]} ^{
    transform ~block{~item}
    validate ~block{~item} 
    callback ~block{~num ~num}
} = {
    @processed = (items |map .{$in |. ^transform})
    @valid = (@processed |filter .{$in |. ^validate})
    @count = (@valid |count)
    @total = (@valid |sum {amount})
    ({@count @total} |. ^callback)  ; Invoke with two numbers
}

; Usage with explicit blocks
(data |with-retry on-error.{error-msg |log})

; Usage with simple values - automatically wrapped
@style = (|if complete "strikethrough" "normal")
@variant = (|if priority == urgent "primary" "secondary")

; Named block arguments can use simple values too
(items |process-items 
    transform.{$in |enhance |normalize}  ; explicit block
    validate=#true                       ; simple value for block parameter
    callback.{@count @total |summarize}) ; explicit block with two inputs

; Mixed usage in conditionals
(|prepare-data .{|called-unnamed-block} named.{|called-named-block})
(|prepare-data simple-value named=simple-named-value)

; Complex control flow with mixed block styles
(items |process-batch 
    transform.{$in |enhance |normalize}
    validate.{score > threshold}
    on-success="completed")  ; Simple string wrapped automatically
```

## Block Invocation

Blocks can be invoked using the `|.` operator, which executes the block with the current pipeline value as input. This is how functions internally invoke their block arguments, but it's also available as a general pipeline operator for any block value.

```comp
; Block stored in variable
@validator = .{$in |check-format |validate-rules}
result = (data |. @validator)  ; Invoke the block

; Block in structure
handlers = {
    process = .{$in |transform |save}
    validate = .{$in.email |check-email}
}
(user |. handlers.validate)  ; Invoke validation block

; Chaining block invocations
pipeline = .{$in |step1 |step2 |step3}
final = (input |. pipeline |post-process)
```

## Argument Spreading and Presence-Check

Functions support spread operators for arguments, allowing predefined argument
sets to be reused and overridden. The presence-check morphing pattern enables
flag-style arguments where unnamed values matching field names set those fields
to their "found" value.

The `??` fallback operator in a shape definitions indicates presence-check
fields: left side is the default (field not found), right side is the value when
found in unnamed arguments. These presence checks look for the existence of an
unnamed value in the argument list.

```comp

!shape ~process-args = {
    verbose ~bool = #false ?? #true
    debug ~bool = #false ?? #true
    ..rest   ; Collect remaining fields
}

!func |process ^process-args = {
    (^verbose |when .{#true} .{
        (|log "Verbose mode enabled")
    })
    ; ^rest contains unmatched fields
}

; Natural calling syntax
(data |process verbose extra=1 more=2)
; Results in: {verbose=#true debug=#false extra=1 more=2}

; With argument spreading
@defaults = {debug}
(data |process ..@defaults verbose)
; Results in: {verbose=#true debug=#true}

; Spread operators work like Python **kwargs
@preset = {verbose debug port=8080}
(server |configure ..@preset host="localhost" port=3000)
; Results in: {verbose=#true debug=#true host="localhost" port=3000}
; Note: explicit port=3000 overrides preset port=8080
```

## Function Overloads

Functions can be defined multiple times to describe working with different
shapes of inputs. The function definitions must be unambiguous or the module
will have a build-time error. The function definition can use `?=` weak or `*=`
strong assignment operators to break ambiguous ties.

The functions use the shape matching logic to select the most specific
implementation for the given input shape.

The tag system can be greatly used to control this dispatch, which has a strong
influence how shape matching is defined. Functions can dispatch from themselves
to weaker matches based on specific tags. For detailed information about tag
hierarchies and polymorphic dispatch mechanisms, see [Tag System](tag.md).

```comp
!func |render ~point-2d = {"2D point"}
!func |render ~point-2d *= {"2D improved"}  ; Strong assignment wins
!func |render ~point-3d = {"3D point"}

({x=5 y=10} |render)           ; "2D improved" - strong assignment wins
({x=5 y=10 z=15} |render)      ; "3D point" - more specific shape
({5 10} |render)               ; "2D improved" - positional matching

; Tag-based dispatch with hierarchical scoring
!func |process ~{status=#status} = {"generic status"}
!func |process ~{status=#error.status} = {"error handler"}
!func |process ~{status=#error.network} = {"network specialist"}

({status=#timeout.error} |process)  ; "error handler"
({status=#network.error} |process)  ; "network specialist"
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
    $in |validate-user |save-user
}

!doc impl "Archives to time-series store"
!func |process ~system-data = {
    $in |validate-system |archive
}

; Single describe shows all implementations
!describe |process
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
({type=#bird} |speak)          ; "chirp"
({type=#dog.mammal} |speak)    ; "woof"
({type=#cat.mammal} |speak)    ; "meow"

; Cross-module polymorphism
creature = {type=#dog.mammal name=Rex}
(creature |speak)             ; "woof" - most specific match
```

## Function Permissions and Security

Functions can declare required permissions using the `!require` decorator. This
creates build-time documentation and enables early failure with clear error
messages. The permission system uses capability tokens that flow through the
context but cannot be stored or manipulated as values.

Pure functions implicitly drop all permissions, ensuring they cannot perform
side effects. Regular functions inherit the caller's permissions unless
explicitly restricted. The security model enables fine-grained control over
resource access. For comprehensive details about the permission system,
capability-based security, and permission inheritance patterns, see [Runtime
Security and Permissions](security.md).

```comp
!require read, write
!func |backup-file ^{source ~str dest ~str} = {
    (^source |read/file)      ; Needs read permission
    |compress
    |write/file ^dest         ; Needs write permission
}

!require net, env
!func |fetch-with-config ^{endpoint ~str} = {
    @api-key = ("API_KEY" |get/env)      ; Needs env token
    headers = {Authorization = %"Bearer ${@api-key}"}
    (^endpoint |get/http headers)      ; Needs net token
}

; Permissions flow through calls
!func |admin-operation = {
    (|backup-file)           ; Inherits admin's permissions
    
    ; Temporarily drop permissions for untrusted code
    untrusted-input = ($in |process-user-data)  ; Isolated execution
}
```
