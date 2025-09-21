# Functions and Blocks

*Defining and executing Comp functions.*

## Overview

Functions in Comp transform structures through pipelines of operations. Every
function receives a structure as pipeline input and generates a new structure as
output. Functions also accept arguments that configure their behavior,
maintaining a clear separation between data flow and parameterization.

Functions are references, not values. They cannot be assigned to variables or
passed as data, but they can be invoked through pipelines and accept block
arguments for higher-order programming patterns. This design choice creates
clear boundaries between code and data while enabling powerful composition
through blocks.

At a basic level, a function definition and structure literal use the same
parsing and instruction rules. They use the same assignment rules and spread
rules and operate identically. The difference is that a structure literal is
evaluated immediately to provide a structure, while a function becomes a recipe
of instructions on how to create a structure. A function also has the concept of
an incoming pipeline structure it is expected to transform, and can be tied to
additional things like documentation and separate shapes to define arguments.
For more details on structure operations and assignment patterns, see
[Structures, Spreads, and Lazy Evaluation](structure.md).

The function system embodies several core principles that guide its design.
Functions as transformations means every function is fundamentally a
structure-to-structure mapping. Structural dispatch enables polymorphism through
shapes rather than classes. Explicit effects through permissions make side
effects visible and controllable. Composition over inheritance creates flexible
systems through function and block combinations. Deterministic selection ensures
predictable behavior in polymorphic scenarios.

These principles create a function system that balances power with simplicity.
Whether building simple data transformations or complex polymorphic systems,
functions provide consistent, composable abstractions for computation.

## Function Definition Fundamentals

Functions are defined with the `!func` keyword followed by the function name
(prefixed with `|`), pipeline shape (prefixed with `~`), and optional arguments
(prefixed with `^`). The function body transforms the input structure, with
fields computed through expressions and pipelines. Control flow operates through
function calls with blocks.

The pipeline shape uses Comp's structural typing - any structure with compatible
fields can invoke the function. Functions with no input requirements use an
empty shape `{}`. Arguments are specified separately, maintaining clear
distinction between data and configuration.

Comp uses its structural matching rules to determine which functions can be run
on which data. The function's shape definition can reference an externally
defined shape, or define one inline.

Functions can define a separate shape to accept arguments. The function body can
reference this argument scope with the `^` caret operator. This scope
for arguments also falls back on several other scopes Comp tracks across
function calls. For comprehensive information about the shape system, morphing
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
({10 20} |calculate-area)        ; Positional matching
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

Functions can define lazy structures using `[]` brackets instead of `{}`. These
create generators where fields compute on demand. Once computed, values are
cached, making lazy structures eventually behave like regular structures. This
enables efficient partial evaluation and infinite structures.

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

## Pure Functions and Isolation

Pure functions guarantee deterministic computation without side effects. Defined
with `!pure`, they receive an empty context and cannot access external
resources. This isolation enables build-time evaluation, safe parallelization,
and use in shape constraints or unit definitions.

The distinction between `!pure` and regular functions is about capability, not
syntax. Pure functions can call other functions, but those functions fail
immediately if they attempt resource access. This creates a clear boundary
between computation and effects.

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

Blocks are deferred structure definitions that can be passed as arguments to functions or stored as values. Blocks exist in two states: ephemeral blocks (raw `.{...}` syntax) that cannot be invoked, and callable blocks that have been typed with an input shape definition.

These are typically used to allow temporary transformations of data. They are
often used for conditional and iterative functions to manage the actions for
different branches.

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
