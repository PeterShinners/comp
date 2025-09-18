# Pipelines and Flow Control

*Design for Comp's error handling, control flow operators, pipeline composition*

## Overview

Functions are always invoked with an `->` invoke operator. There are other
types of statements that can be applied to these invoke operators, and
these can be connected into a chain of operations called a pipeline.

Each statement in the pipeline works with the concept of accepting one
incoming structure and generating one new structure.

Specially shaped structures can be generated that are considered 
failures, and flow along this pipeline with a different set of rules.

## Pipeline Operators

There is one -> pipeline operator that is used to connect multiple
statements into a single processing pipeline. Each statement takes
the structure from before it and generates a single structure as
its result.

* `->` The traditional pipeline invoke operator

**Branch Operators**

Groups of statements within a pipeline can be grouped with branch operators.
These have different behaviors over execution. These use a symbol and parenthesis
to wrap one or multiple statements.

* `.()` **Plain Branch** uses parenthesis to customize operator precedence. It is
not regularly needed, but can help clarify or organize intention.
* `@()` **Iterate Branch** is invoked for each field of the incoming structure.
* `&()` **Side Branch** pipeline that ignores its generated structure, this passes through
whatever structure was originally given to it. This pairs with the "privacy" decorator.
* `^()` **Isolated Branch** has no access to `!ctx` or `!mod` namespaces

**Fallback Operators**

Fallbacks are for dealing with failures. Failures have specialized flow control
within the pipeline only these operators interact with them.

* `|()` **Fallback Branch** is only invoked when the incoming value has a failure shape.
* `|` **Fallback Statement** Provides an immediate fallback to any statement.

**Valve Operators**

There is also a family of operators used for conditional logic inside 
a pipeline. These are always used in a group of neighboring operations.

* `??` Begin a valve with a boolean condition
* `?>` Perform statement when condition matches
* `?&` Define additional exclusive condition (else if)
* `?|` End with optional statement when no conditions match

## Pipeline Statements

Each statement in the pipeline can be one of several operations.

* **Function** reference preceded with `:` colon.
* **Structure** define new structure literal based on incoming structure wrapped in `{}` braces.
use a pipeline of statements internally to create a sub-pipeline.
* **Lazy Structure** operates the same as the structure but is wrapped in `[]` square brackets.
It's fields are not computed until needed.
* **Condition** the condition operators require a boolean value.

## Pipeline Actions

Each pipeline is a group of statements that has one of three possible behaviors.
These behaviors are controlled by what statement is at the very start of
the pipeline. Even a single statement is still considered a pipeline.

* **Temporary Assignment** statements start with a `$` prefixed token and contain an
initial `=` assignment. This assigns
the pipeline to a local value, or a nested field to update inside the existing
value of for that temporary. This is the only action that does not contribute
to the outgoing structure being generated.
* **Named Assignement** statements start with a field name and `=` assignment.
This assigns a new field to the outgoing structure. Conflicting field name
definitions will reassign the field value, but that behavior can be modified
with the weak and strong assignment operators.
* **Unnamed Assignment** a pipeline with no `=` assignment at the beginning
defines a new unnamed field in the outgoing structure.

### Invoke Operator `->`

This is used to pass an input structure into a statement to generate a
single output structure.

If the first statement is a function reference then a pipeline can begin
immediately without needing to define an input structure and the `->`
statement.

```comp
data -> :validate -> :transform -> :save
user -> {username=name, timestamp=:time/now} -> :event
:random/bool -> :record-statistics
```

### Iterate Branch `@()`

This will invoke the branch on each field in the structure. The statement will
be invoked with a simple shape containing `{value name index~num named?}`. For
fields without a name the `name` will be `{}` and the `named?` boolean will be
`#false`

Each result of the iteration is collected into a structure of unnamed fields.

There are several builtin tags that can be used to control the iteration's flow
control.

* ``#skip`` will continue iteration, but not include this values result in the
outgoing structure. This can be considered like a `continue` statement in other
langauges, which Comp does not have.
* ``#break`` will immediately stop iteration. The generated structure will
still contain all the values that had been iterated before the break.
* **failure** If a failure structure is created the iteration stops immediately
and the iteration result is that failure structure.

```comp
; Double numbers in an array
numbers -> @(value * 2)  ; double numbers in an array

; Generate pairs of name and boolean for each user structure in array
users -> @({name=value.name, recent=value.login > $lastweek})
```

### Side Branch `&()`

The side branch is a conveience for evaluating pipeline but not contributing
back to the outer flow control. 

This branch will pass through whatever value it was provided.

Failures generated inside the side branch will still be propogated out of the
branch.

This uses the `&` symbol which is also used mark definitions as private. This
can be considered the "privacy branch". What happens in side branch stays in
side branch, but side branch is not above the law.

```comp
record -> :validate-record -> &({timestamp=when} -> :update-stamp) -> :process-record
```

### Isolate Branch `^()`

The isolate branch executes its statements with no access to the `!ctx` or
`!mod` namespaces. This can be important when needing to ensure structual
data contains specific fields with no contribution from the namespaces.

This is useful for both morphing operators and invoking functions.

This uses the caret, or "hat" operator to describe it operates in the shadows,
hidden from the namespaces.

```comp
user ~systemuser    ; Needed fields can be contributed from namespaces
^(user ~systemuser) ; Record forced to provide all fields for itself
```

### Valve Flow Control Operators

A valve group is a sequence of conditional checks that work together as a single
unit in the pipeline. The group receives an input value, evaluates conditions
against it, and outputs the result of whichever branch executes.

- **`??`** Begin conditional (if)
- **`?>`** Then action separator (and then) 
- **`?&`** Else-if continuation (or if)
- **`?|`** Else fallback (or else)

The group is implicitly attached to one another based on their adjacancy. Each
valve group must begin with the `??` opening conditional. The optional else
fallback must be the final statement if included. Only a single `?>` or `?|`
statement will be evaluate

With no `?|` else statement it is possible that none of the statements 
are invoked. When that happens the original input structure is passed through
unchanged.

**Input Flow**: The value entering the valve group (from the left side of `??`)
is available to all conditions within that group. Each condition can access and
test this input value.

**Condition Evaluation**: Conditions are evaluated in order, left to rigth. The
first condition that evaluates to true has its corresponding action executed.
Once a condition matches, no further conditions in that valve group are checked.

**Output Flow**: The valve group outputs whatever value its executed action
produces. This output then flows to the next operation in the pipeline. If no
condition matches and there's no `?|` else clause, the valve group passes
through the original input value unchanged.

#### Syntax Pattern

```comp
input_value -> 
    ?? condition ?> :action_if_true
    ?& another_condition ?> :action_if_this_true  
    ?| :action_if_all_false
-> receives_action_output
```

# Failure Operators `|>` and `|`

These statements are only invoked when the incoming structure has a failure
shape.

The `|` operator isn't quite a pipeline operator. It runs at a lower
precedence than the regular pipeline operators, so can only operate on an
immediate statement.

The `|` block also receives the original incoming structure and discards
the failure statement entirely.

```comp
user.nickname | "Anonymous"         ; Uses "Anonymous"
config.timeout | 30                 ; Uses 30
```

## Advanced Pipeline Patterns

### Pipeline Labels and Reuse

A special `!label` operator can appear as an operator as a pipeline
statement. This allows assigning the current input structure to either a
`$` local temporary value, a field in the outgoing structure, or an 
assignment to the `!mod` or `!ctx` namespaces.

This operator passes through whatever the current structure is.

```comp
; Function-scoped labels
path -> :fs/open -> !label $fd -> :process_file
$fd -> :fs/close  ; Reuse labeled value
```

