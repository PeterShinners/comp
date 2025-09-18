# General Syntax

* Overview of the error handling integrated into the language. *

## Overview

Comp presents a style of error management naturally works with
its pipeline processing model. This allows handling errors wherever
is most important. Information is carefuly tracked and passed along
without forcing manual management where not needed.

## Failure Shape

A failure shape is any structure that contains a `#fail` tag value.

The language will generate these on many runtime errors, like
a missing field name, a failed type conversion, and more.

It's also simple for a function to manually generate a failure
structure.

The shape definition is trivial:

```comp
!shape ~fail = {#fail}
```

This means if functions need to cleanly pass information about
failures, these tags must be nested inside any of the fields.


## Failure Hierarchy

The language defines a `#fail` tag added to the core namespace.
This is an extensible tag that defines a hierarchy for errors.

* value
  * shape
  * missing
  * constraint
  * morph
  * operation
* reference
  * missing
  * ambiguous
* module
  * conflict
  * syntax
    * brace
    * unknown
    * illegal
* import
  * missing
  * provider
* io
  * missing
  * conflict
  * permission
  * abort
  * timeout
* resource
  * exhausted
  * busy
  * timeout
  * permission
* runtime
  * permission
  * unimplemented
* definition
  * conflict
  * syntax
    * braces
    * unknown

## Extended Tags

Any module can define additional failure tags. The typical approach is
to define new failure tags at the top level of the tag namespace.
Usually the modules `#fail` tag hierarchy is also replaced to represent
the newly modified hierarchy.

Be aware that this does not change the system tags presented to other modules.
If other modules want to share these definitions they can import and alias
them directly.

Defined failure tags should always get a simple description of a few
words as the value.

```comp

!tag #fail < #fail = {
    #yofo = "You only fail once"
}
```

## Failure Propogation

Any pipeline operator that is invoked will be skipped when the `!in`
structure contains a failure shape. This propogation will continue 
all the way through the `!main` entry point for the process.

This includes all pipeline operations like `->` `=>` `..>` and the `??` valve
conditional operators.

## Failure Fallback

The `|` fallback operator allows immediately providing an alternative
value for a statement that generates a failure. This fallback can also
be a different failure.

The statement in this receives the original structure that caused the
failure, but not the failure itself.

This behavior allows multiple `|` blocks to be chained to attempt
multiple fallbacks.

```comp
row.name | row.login | "Unknown
```

## Fallback Pipeline Operator

Only the `|>` failure operator will be invoked when `!in` contains a failure
shape. Otherwise this fail operator is normally skipped. Whatever value
is generated from this operator will become the new state of the pipeline,
which will continue execution following this operator.

If this operator provides the same failure or generates a different fail
structure, this failure propogation will continue its way out of the pipeline.

The failure operator accepts an optional failure tag wrapped
in parenthesis. This allows filtering errors to use for the failure
block. The tag can provide multiple tags combined with the `|` operator.
When multuple failure blocks are defined with different filters, the
pipeline flow will continue checking each failure operator, in the order
they are defined. Once a non-failure value is generated from one, error
handling will skip the remaining error operations.

When no filter is given, the failure block will default to using whatever
`#fail` tag is defined in the current module. This will often be the core
set of fail tags defined in the fail module at `#fail/fail`.

If a failure is generated inside of an `=>` iteration operator, the
iteration stops immediately and all downstream operations propogate the
failure that was generated.

```comp
; If :step1 fails, :step2 and :step3 are skipped
data -> :step1 -> :step2 -> :step3

; Failure propagates through iteration
users => :validate -> :save  ; Any invalid users stops processing all of them

; Spread operations also propagate failures
data ..> :load_config -> :process  ; Config loading failure stops pipeline


; Some failures produce a fallback value, others use an alternate failure
; Any other failure types will be propogated as-is
:risky-op
|> (#fail#io) {length=0 results={}}  ; Fallback value
|> (#fail#runtime#permission|#fail#resource)  {#fail#value "System says no"}
```

## Failure Details

The `!describe` operator can be used on the failure structure. This generates
the same information when describe is used on any structure value.

With this information it can be determined which function and statement
produced the failure. This also provides a copy of the locals and namespace
variables defined when the failure was generated.


## Failure Messages

Failure reporting tools will look for an initial string field in the
failure structure. This should be a short, one sentence description
of what failed.

Messages should try to be clear about which values cause a problem.
For example, use "Index ${index} must be a positive integer." instead of 
"Illegal index."

Other fields in the structure will also be displayed. Helpful fields would
reference where to find more information or suggest possible alternatives.
By using reasonable field names this information should be reported clearly.

Information about the function and statement that failed will already be
reported, so does not need to be duplicated.

```comp
?? index < 0 ?> {
    #fail#field#value 
    "Index {index} must be a positive integer."
    see = "More details in :pool"}
```

## Runtime Failures

While evaluating statements and pipelines, the langauge will generate failures
for the following operations. 

* Undefined field
* Undefined index 
* Undefined local temporary
* Cannot morph structure
* No matching implementation found
* Invalid math operator
* Invalid operator type
* Permission denied

These are different than compile errors which are only generated when importing
modules.

These are also different than resource or system errors, which only
come from functions or operators for managing these *handle* data types

## Future Implementation

* The language should keep the chain of failures that were active when
new failures were generated. This would allow introspecting lower level
failures that were wrapped with higher level information.
* It seems useful to alias failure tags from one part of the hierarchy into
another. The aliased tags would be treated like they have two parents,
which are still ordered to control which parents are most specific for
dispatch (shape matching priority). This way an applications `#fail#myapp#timeout`
could be an alias (or symlink?) to `#fail#io#timeout` and used interchangeably.
