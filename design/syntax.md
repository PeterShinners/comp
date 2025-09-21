# Syntax and Style Guide

*Comp language syntax rules, style conventions, and formatting guidelines*

## Style Guide

The standard style uses:

- Tabs for indentation
- Tokens prefer lisp-case (lowercase with hyphens)
- Prefer boolean function and fields with a trailing `?`
- Operators at the start (`|`) when splitting long lines
- Lines under 100 characters when reasonable
- Function references always attached: `|function` not `| function`
- Undecorated tokens for field access in pipelines

## Whitespace

Whitespace is completely optional in most places of the language. Whitespace
can consist of any amount of spaces, tabs, extra lines or indentation.

The only place whitespace is required is between fields of a structure
and between the operations a function or structure.

```comp
@primes = {1 3
 5      7}

!func |tight = {"oneline"}
!func 
 |spacey
={
                @first = 
    1 @second=2
}
```

## Operator Reference

**Pipeline and function operators:**
- `()` - Pipeline boundaries  
- `|` - Function application
- `|?` - Failure handling
- `.{}` - Block delimiter

**Assignment operators:**
- `=` - Normal assignment
- `*=` - Strong assignment (resists overwriting)  
- `?=` - Weak assignment (only if undefined)

**Spread operators:**
- `..` - Normal spread
- `*..` - Strong spread
- `?..` - Weak spread

**Fallback operator:**
- `??` - Provide fallback value

**Special operators:**
- `~` - Shape morphing
- `???` - Placeholder for unimplemented code

## Scope Reference

Comp provides multiple namespaces for organizing data:

- `@var` - Function-local variables
- `^args` - Function arguments (cascades to `$ctx`, `$mod`)
- `$in` - Pipeline input structure from the current function
- `$out` - Current output structure being built
- `$ctx` - Execution scope that follows the call stack
- `$mod` - Global scope shared by all functions in the module

```comp
!func |example ~{data} ^{port ~num} = {
    @sum = $in |sum
    
    server-port = ^port       ; Cascades through arg→ctx→mod
    total = @sum
    user = user               ; Undecorated field lookup
    config = $mod.config      ; Explicit module reference
}
```

## Documentation Syntax

The `!doc` operator attaches documentation to functions, shapes, and other definitions:

```comp
!doc "Process different types of data appropriately"
!func |save ~{data} = {
    ; Function implementation
}

; For polymorphic functions, use !doc impl for specific implementations
!doc impl "Saves to primary database"
!func |save ~{~database.record} = {
    ; Database-specific implementation
}
```

## Tokens

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

## Comments

The language supports line comments using the style `;` of semicolon,
similar to Clojure and Lisp. There is no support for block style comments.

The language does not do any interpretation of the comment contents.
Everything from the begin of the comment to the end of the line is strictly
ignored.

See the section on Docstrings for related information.

## Nested Naming

Like tags, shapes and functions can define nested hierarchical names using dot notation. This provides organization and namespace capabilities similar to tags, enabling cleaner module organization and logical grouping of related definitions.

### Shape Hierarchies

Shapes can be defined with dotted names to create logical groupings:

```comp
; Database-related shapes
!shape ~database.connection = {host ~str port ~num}
!shape ~database.record = {id ~num data ~str}
!shape ~database.query = {sql ~str params ~str[]}

; HTTP-related shapes  
!shape ~http.request = {method ~str url ~str headers ~str{}}
!shape ~http.response = {status ~num body ~str headers ~str{}}

; Graphics shapes
!shape ~graphics.point = {x ~num y ~num}
!shape ~graphics.color = {r ~num g ~num b ~num a ~num = 1}
!shape ~graphics.transform = {..~graphics.point scale ~num = 1}
```

### Function Hierarchies

Functions can use the same dotted naming for organization:

```comp
; Database operations
!func |database.connect ~{config ~database.connection} = {
    ; Connection logic
}

!func |database.query ~{query ~database.query} = {
    ; Query execution
}

; HTTP utilities
!func |http.get ~{url ~str} = {
    ; GET request logic
}

!func |http.post ~{request ~http.request} = {
    ; POST request logic  
}

; Graphics operations
!func |graphics.translate ~{point ~graphics.point} ^{offset ~graphics.point} = {
    ; Translation logic
}
```

### Referencing Nested Names

Nested names are referenced using their full dotted path:

```comp
; Using nested shapes
user-record ~database.record = {id=123 data="user data"}

; Using nested functions  
(config |database.connect)
({sql="SELECT *" params=[]} |database.query)

; Shapes in function signatures
!func |save-user ~{user ~database.record} = {
    user |database.insert
}
```

This hierarchical organization follows the same principles as tag hierarchies—the most specific part comes first in the path, enabling natural grouping while maintaining clear, readable names.

## Core modules

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