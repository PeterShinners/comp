# Language Overview

*Essential concepts and syntax for programming in Comp*

## Introduction

Comp is a functional language where every value is an immutable structure and
every operation transforms data through pipelines. The language combines the
accessibility of dynamic scripting with the safety of structural typing, making
it ideal for data processing, API integration, and system glue code.

This overview introduces the essential concepts needed to understand Comp
programs. For detailed specifications of any feature, see the corresponding
design document in the `design/` directory.

## Getting Started

**Note: Comp is currently in design phase with no implementation. These examples
show intended syntax and behavior.**

A minimal Comp file is a complete executable application, an importable library
module, and a self-contained, managed package.

```comp
!mod.package = {name="Greeter" version="1.0.0"}

!doc "Retrieve a name to be greeted"
!func |whomst = {
	"World"
}

!main = {
	|whomst % "Hello, ${}!" |print
}
```

Save this as `hello.comp` and (once implemented) run with `comp hello.comp`.
This `!main` definition serves as the entry point, a library function can be
shared with others, and metadata allows packaging tools to process this.

## Core Concepts

### Everything is a Structure

Comp unifies all data representation into structures - ordered collections that
can contain both named and unnamed fields. This uniformity means the same
operations work whether you're handling JSON from an API, rows from a database,
or values computed in your program.

```comp
42                      
{x=10 y=20}            
{1 2 3}                
{name=Alice 30 active?=#true}
```

When a scalar value like `42` enters a pipeline, it automatically promotes to a
single-element structure `{42}`. This auto-wrapping means functions always
receive structures, simplifying the programming model. Named fields can appear
in any order and are accessed by name, while unnamed fields maintain their
position and are accessed by index.

Structures are immutable - operations create new structures rather than
modifying existing ones. This immutability ensures predictable behavior, enables
safe parallelism, and eliminates entire classes of bugs related to shared
mutable state. For detailed information about structure operations, field access
patterns, and advanced features like lazy evaluation, see [Structures, Spreads,
and Lazy Evaluation](structure.md).

### Pipeline Operations

Data transformation happens through pipelines that connect operations with the
`|` operator. Each operation in a pipeline receives the output of the previous
operation as its input, creating a clear left-to-right flow of data
transformation.

```comp
(data |validate |transform |save)

(items |map .{|process-each} |collect-results)

(risky |operation |? .{|handle-error})
```

Pipelines are enclosed in parentheses to clearly mark their boundaries, although
these can be omitted when the pipeline definition is unambiguous. The `|`
operator is a function reference, with functions written as `|function-name`. A
special `|?` operator handles failures through the pipelines, allowing graceful
error recovery without breaking the pipeline flow. For comprehensive details on
pipeline operations, control flow patterns, and failure handling strategies, see
[Pipelines, Flow Control, and Failure Handling](pipeline.md).

### Functions Transform Structures

Functions in Comp are pure transformations from one structure to another. Every
function declares its expected pipeline input shape and argument structure by
referencing a defined shape, or declaring one inline. Shapes are referenced and
defined with the `~` character. The structure that a function generates is
defined by the named (and unnamed) fields it defines. Functions can be invoked
for any structure that matches the defined shape.

```comp
!func |area ~{width ~num height ~num} = {
    result = width * height  ; result is a named number structure
}

!func |adult? ~user = {
	age >= 18  ; result is an unnamed boolean structure
}
```

For detailed information about function definition, dispatch mechanisms,
polymorphic behavior, and advanced features like blocks and lazy evaluation, see
[Functions and Blocks](function.md).

### Shapes Define Structure

Shapes act as schemas that describe the expected structure of data. They specify
field names, types, default values, and constraints. Unlike rigid class
definitions, shapes use structural matching - any data that contains the
required fields satisfies the shape.

```comp
!shape ~user = {
    name ~str
    age ~num = 0
    email ~str|~nil = {}
}
```

When used outside of shape definitions, the `~` operator converts structures
into the defined shapes. This can apply names to unnamed fields, perform type
validations and promotions, and more. This is named the morphing operator and
offers flexible machinery built on simple and logical rules. For comprehensive
coverage of the shape system, morphing algorithms, unit types, and type
validation, see [Shapes, Units, and Type System](shape.md).

### Tags for Enumeration

Tags define a hierarchy of enumerated values. They serve triple duty as
enumerated constants, data types, and polymorphic dispatch keys. Tags use `#`
when referenced.

For detailed information about hierarchical tag systems, polymorphic dispatch,
and cross-module tag extension, see [Tag System](tag.md). 

```comp
!tag #status = {
    #active = 1
    #inactive = 0  
    #pending
}

state = #active
state = #pending
```

## Module System

Every comp file is a module that can be imported into a defined namespace. This
allows functions, shapes, and tags to be referenced using the appropriate symbol
for each definition. These references are made using the object's name, and in
the case of conflicts the slashed namespace is used to disambiguate,
`~rectangle/geometry` or `|sum/math`. Tags follow this same rule, but their
hierarchy is listed from bottom to top. `#success.status.http`.

A module's namespace is declaratively defined, and clearly known and understood
before anything is executed. Name errors or ambiguities are immediate compile
errors.

Definitions in the current module always have priority over the names that come
from other modules. Ambiguous references are known and become build failures.
For complete details on the module system, import mechanisms, namespace
management, and dependency coordination, see [Modules, Imports, and
Namespaces](module.md). 

```comp
!import str = std "core/str"
!import math = std "core/math"

; Functions use reversed namespace notation
(text |upper/str)
(value |sqrt/math)

; Or create aliases for frequently used functions
!alias |sqrt = |sqrt/math
(value |sqrt)
```

## Flow Control

Comp conditionals and iteration are implemented with regular functions. Simple
operations like `if` or `map` are defined in the language. More advanced
operations like `switch` or `fold` are also functions that can be built on or
redefined freely.

Most of these functions are implemented using blocks as arguments. Blocks are
structure definitions that are not immediately invoked. The function can choose
to invoke them as many times as needed by passing different data. These blocks
can be identified as structures with a leading `.` dot prefix.

```comp
(|if value > 5 .{|prepare-additional-space} .{|handle-small-set})

($in |when .{error?} .{
    (error |log)
})

(value |match 
    .{0} .{zero}
    .{1} .{one}
    .{#true} .{other})
```

For more information about control flow patterns, iteration mechanisms, and
block usage, see [Pipelines, Flow Control, and Failure Handling](pipeline.md).

## Variables and Namespaces

Comp provides multiple namespaces for organizing data. These are used by running
logic to store and share data outside of the data pipeline.

These namespaces are represented as structures. These are immutable structures
that use Comp's assignments as instructions to create new immutable structures
with changes.

Referencing these namespaces or the fields of these namespaces will work like
regular structure references.

Most of these namespaces can be assigned to directly or modify one of these
fields. Remember that these structures are immutable. Assignments to them define
a recipe of how make a copy of the structure with changes.

Some of these namespaces define fallbacks to other namespaces. 

Any field reference not using one of these namespace will use the `$out` and
`$in` pipeline namespaces. Assignments to fields without a namespace generate
new fields in the outgoing structure.

- `$` - Function-local temporary variables
- `^` - Function argument namespace (cascades to `$ctx`, `$mod`)
- `$in` - Pipeline data from the previous operation
- `$out` - Pipeline output being generated by function
- `$ctx` - Execution namespace that follows the call stack
- `$mod` - Global namespaces shared by all functions in the module

```comp
!func |example ~{data} ^{port ~num} = {
    $sum = $in |sum
    
    server-port = ^port       ; Cascades through arg→ctx→mod
    total = $sum
    user = user               ; Undecorated field lookup
    config = $mod.config      ; Explicit module reference
}
```

## Field Access

Any namespace or structure provides fields. Fields are commonly used as token
strings. Any core data type can be used as tag values, including tags. Fields
can be referenced by their name or their absolute position in the structure.

- `data.field` - Named field
- `data#0` - Positional index (numeric literals only)
- `data.'expr'` - Computed field name
- `data."string"` - String literal field name

For detailed patterns of field access, computed access methods, and advanced
navigation using trails, see [Trail System](trail.md).

## Basic Types

Comp's basic types are not structures themselves, they have no fields. The most
common types are numbers, strings, and booleans. Values are strongly typed and
basic values are never automatically converted to other types.

### Numbers

Number values use the special `~num` shape. The `.num` module provides a large
library of functions for mathematics, conversions, and more.

Comp numbers provide huge precision without overflow or rounding errors. These
are not driven by hardware number types that suffer from overflows and accuracy
issues. Number literals can be flexibly defined in various base notations, use
placeholder underscores, and typical scientific notations.

Comp provide a range of typical mathematic operations like `+` `-` and more.
These operators only work on number values.

The language allows tags to be attached to numbers that are defined as units.
Comp comes with an extensible collection of standard measurements units. Shapes
can define the units required for their fields.

```comp
huge = 0x999999999999999999999
precise = 1/3          ; Exact fraction
5#meter + 10#foot      ; Units as tags
```

For comprehensive information about number types, mathematical operations, and
unit systems, see [Core Types](type.md).

### Strings  

String values use the special `~str` shape. The `.str` module provides a large
library of functions for strings. 

Strings are immutable UTF-8 text and can represent large blocks of data held in
memory. There are no operators that modify or concatenate strings. 

Literal string values must be surrounded by `"` double quotes. Intermediate
quotes are escaped with backslashes. String literals can also use `"""` triple
quotations to contain multiple lines.

Strings define a powerful template operator `%` that allows them to map pipeline
fields into a template language.

The language allows tags to be defined as units for strings. This is intended to
provide a hint about the type of data contained in a string. These extensible
string units also contribute to the formatting of values in the string template
to allow safe escaping and substitutions.

```comp
name = "Alice"                   ; String literal
greeting = name % "Hello ${}"    ; Templated string and operator
{name="Bob" age=30}              ; Name is field, "Bob" is string
"SELECT id, name FROM users"#sql ; Unit typed string ready for escaped substitutions
```

For more details about string operations, template formatting, and string units,
see [Core Types](type.md).

### Booleans

Booleans are represented by two tags: `#true` and `#false`. They are represented
by the special `~bool` shape.

Conditionals are written to require booleans, and do not automatically convert
"truthy values" into booleans.

The language convention is to use a trailing `?` on fields and functions that
have boolean values.

Booleans can be used with the boolean operators `!!` for negation, and logical
combinations with `||` and `&&`.

```comp
valid? = x > 0              
ready? = #true
enabled? = name == "Alice"
```

For more information about boolean operations and type conversions, see [Core
Types](type.md).

## Operators Summary

**Pipeline and function operators:**

- `()` - Pipeline boundaries
- `|` - Function reference (and application)
- `|?` - Failure handling
- `.{}` - Block delimiter

**Fallback operator:**

- `??` - Provide fallback value

**Assignment operators:**

- `=` - Normal assignment
- `*=` - Strong assignment (resists overwriting)
- `?=` - Weak assignment (only if undefined)

**Spread operators:**

- `..` - Normal spread
- `*..` - Strong spread
- `?..` - Weak spread

## Complete Example

This more complete example demonstrates how the language features work together.

```comp
!import .gh = comp "github-api"
!import .time = std "core/time"

!main = {
  $after = (|now) - 1#week
	$fields = ("title url created-at reactions"|tokenize)
    
	{$fields repo="nushell/nushell"}
	|list-issues.gh  ; applies $repo from ctx
	|filter .{created-at >= $after}
	|map {
		$thumbs-up = (reactions |count-if .{content == #thumbs-up})
		{thumbs-up=$thumbs-up title=title url=url}
	}
	|sort #reverse .{thumbs-up}
	|first 5
}
```

## Syntax Rules

### Style Guide

The standard style uses:

- Tabs for indentation
- Tokens prefer lisp-case (lowercase with hyphens)
- Prefer boolean function and fields with a trailing `?`
- Operators at the start (`|`) when splitting long lines
- Lines under 100 characters when reasonable
- Function references always attached: `|function` not `| function`
- Undecorated tokens for field access in pipelines

### Whitespace

Whitespace is completely optional in most places of the language. Whitespace
can consist of any amount of spaces, tabs, extra lines or indentation.

The only place whitespace is required is between fields of a structure
and between the operations a function or structure.

```comp
$primes = {1 3
 5      7}

!func |tight = {"oneline"}
!func 
 |spacey
={
                $first = 
    1 $second=2
}
```

### Tokens

Tokens are used for naming everything in Comp. There are several rules for valid
token names.
* Tokens must follow the UAX #31 specification for valid unicode tokens
  * This matches the behavior of Python and Rust.
* The `ID_Continue` set is expanded to also include the ascii hyphen.

The language convention is to use all lowercase characters where writing purely
Comp specific identifiers. When interfacing with other languages or data
specifications, use capitalizations and underscores where preferred.

The style preference is to use the hyphens as word separators instead of
compacting token names into abnormal compound words.

The style of using lowercase words with hyphen separates is referred to as
**lisp-case**.

Allowed tokens (although not always preferred)
* `html5`
* `content-accept`
* `_parity_bit`
* `用户名`

### Comments

The language supports line comments using the style `;` of semicolon,
similar to Clojure and Lisp. There is no support for block style comments.

The language does not do any interpretation of the comment contents.
Everything from the begin of the comment to the end of the line is strictly
ignored.

See the section on Docstrings for related information.

### Core modules

Several important modules are defined as the core of the Comp language. These
are imported automatically into every module. These are mainly related to
managing the builtin datatypes and higher level flow control. 

* `.iter` working with iteration and sequences
* `.num` working with number values and mathematics
* `.path` working with path structure values
* `.store` working with mutable data storage
* `.str` working with string values
* `.struct` high level modifications and queries for structures
* `.tag` working with tag definitions, values, and hierarchies

From these libraries there are also several specially aliased
values that can be referenced in every module, without providing the
full namespace. This is a feature any module can configure for themselves
using ~alias operators. You can see these references are typed, based
on the type of object they contain

* `#break` iteration flow control to immediately stop processing
* `#false` false boolean tag value
* `#skip` iteration flow control to ignore a value (similar to a `continue` on other languages)
* `#true` true boolean tag value
* `~bool` shape for a boolean value
* `~nil` shape of an empty structure
* `~num` shape for a scalar numeric value
* `~str` shape for a scalar string value
* `|length` number of items in a structure

## Next Steps

With these concepts, you're ready to explore Comp's design in depth. Each major
feature has a dedicated design document in the `design/` directory:

- [type.md](type.md) - Core types: numbers, strings, and booleans
- [tag.md](tag.md) - Hierarchical tag system and polymorphic dispatch
- [structure.md](structure.md) - Deep dive into structures and operations
- [shape.md](shape.md) - Shape system and morphing
- [pipeline.md](pipeline.md) - Pipeline operations and failure handling
- [function.md](function.md) - Function definition and dispatch
- [module.md](module.md) - Module system and imports
- [trail.md](trail.md) - Structured navigation paths through data
- [store.md](store.md) - Controlled mutable state management
- [security.md](security.md) - Permission system and capability-based security
- [resource.md](resource.md) - Resource management and transactions

Remember that Comp is currently in design phase. These documents describe
intended behavior that will guide implementation.