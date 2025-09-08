# Comp Overview, Syntax, and Style

*Overview of the Comp language and parsing rules*

## Overview

Comp strives to create a limited vocabulary of terms and objects.

The language is whitespace agnostic, aside from each statement is required
to be separated by whitespace. This allows authors to place whitespaces
wherever and however improves readably, or nearly omit it entirely when
compact expressions are the priority. 

There are no commas between lists of fields, and no terminator or punctuation
used at the end of sentences.

All keywords and named functionality of prefixed with symbols. This is done
consistently to allow any field name to be a valid token, and will never conflict
with a keyword or operator in the language.

The top level definitions in a module is a declarative set of statements that
define the contents of the module. It is not executed like a script or runtime
language that incrementally builds the contents. This allows static analysis
and independent ordering of definitions.

## Example

```javascript
// Hello World example in Comp language

!main = {
  $names = {"USERNAME" "USER" "LOGNAME"} => :os:getenv 
  $names -> {:iter:pickone | "World"} -> "Hello ${}" 
    -> :io:print
}
```

## Style Guidelines

The standard libraries and language code will follow the style guidelines.

* Tabs for indentation. 
* Limit line lengths to 100 characters.
    * Relaxed when lines must contain exceptionally long tokens or literal values.
* When pipelines are split across multiple lines, start each new line with the continuation operator like `->` or `|`.
* Prefer line breaks between statements.
* Simple expressions should use spaces to improve clarity of operator precedence.
* When multiple statements share a line, consider compressing each statements whitespace to improve readability.
* Prefer no whitespace between a value and its shape definition, like `name~String` or `value~Record`.
* When a structure or shape definition splits multiple lines, add a level of indentation to the interior lines.
    * Prefer the leading curly brace to end on initial line.
    * Prefer the closing curly brace to end on its own line and match the indentation of the line with the leading curly brace.
* When complicated pipeline contains layers of nesting, consider a double curly brace to easily identify the entry and exit of subsections in the pipeline.

## Module contents

A module defines a set of **functions**, **shapes**, and **tags**. There are
several other definitions available, but these are the common ones.
Each of these concepts is always prefixed with a specific character.

When referencing definitions from other modules, the syntax keeps the character
prefix on the module and object reference. This prefix is used on definition
and reference of these objects.

* **Function** `:` prefixed with a colon, like `:process` or `:number:absolute`
* **Shape** `~` prefixed with tilde, like `~Rect` and `~io~Stream`
* **Tags** `#` prefixed with hash, like `#status` or `#log#severity`

Because of these prefixed characters, there is no problem with using
conflicting names for each type of definition.

## Structures

All data in Comp is represented as structures (ordered collections of fields). Scalars automatically promote to single-element structures when needed:

```comp
42                    // Scalar number
{x=1.0, y=2.0}        // Named field structure
{10, 20, 30}          // Unnamed field structure (array-like)
```

Structures are flexible containers that can mix named fields and unnamed fields.
The values in the structure are ordered and can mix and match any type.

The content of the structure defines a shape, and that structure can be passed
to any function that defines a compatible shape (or schema).

The structure is an immutable object. The language defines operators and function
that allow creating new, derived structures in ways that feel like making
changes. Be aware that these operations are creating new immutable pieces of data.

'''javascript
a = {color="red"}
b = a
a.color = "blue"
// b color is still "red"
```


## Tokens

Tokens are used for naming everything in Comp. There are several rules for
valid token names.
* Tokens must follow the UAX #31 specification for valid tokens.
  * This matches the behavior of Python and Rust.
* The `ID_Continue` set is expanded to also include the ascii hyphen.

The language convention is to use all lowercase characters where writing
purely Comp specific identifiers. When interfacing with other languages or
data specifications, use capitalizations and underscores where preferred.

The style preference is to use the hyphens as word separators instead of compacting
token names into abnormal compound words.

The style of using lowercase words with hyphen separates is referred
to as **lisp-case**.

Examples
* `html5`
* `content-accept`
* `_parity_bit`
* `用户名`

## Whitespace and Separators

The language allows any optional whitespace in between any tokens. The
only requirement is that whitespace is required between statements.

There are no commas or separators used between field definitions. There is
no semicolon or terminating symbol to mark the end of statements or pipelines.

## Field References and Namespaces

Any undecorated token represents a lookup into one of several predefined
namespaces. These namespaces are structures that the language handles specially
as it is processing. The namespaces are always referenced with a leading `.` dot.

These namespaces represent a layered hierarchy of fields, where the first
definition found overrides any of the later fields.

These namespaces are defined as

* `.out` is the structure being defined by the current execution block
* `.in` is the structure that was passed input to the current execution block
* `.ctx` is a structure that can be modified by executing function blocks and is inherited to all called functions.
* `.mod` is a module-specific namespace that can only be accessed by functions within that module.

The undecorated token references are used to lookup fields from this stack of
namespaces. An undecorated assignment to a field represent as assignment into
the `.out` namespace, which will win all future lookups.

```javascript
a = 123
b = 321 + a  // becomes 444
server-port -> :listen  // locate this port token in one of the defined namespaces
```

## Shapes

Shapes are like schema definitions for structures. They define fields,
types, default values, and more. They are defined and referenced with a
leading `~` tilde. Shapes are often applied to structures to morph their
shape to match the given definition. There are complete rules on
how this morphing is applied to arbitrary structures.

```javascript
!shape ~circle = {x~number y~number radius~number}
{12 5.5 3.13}~circle
```

## Tags

Tags are enumerated values that can be used similarly to both shapes
and values. The tags can be defined hierarchically to create a 
hierarchy, and each tag can optionally have values. Each defined tag must
be a valid token.

Tags in a structure heavily influence its shape, and can be used to create
polymorphic behaviors and overrides.

```javascript
!tag #terrain = {mountain grain grass dirt}

{location = #terrain.grass}
```

## Functions

Functions in Comp are transformations of structures. They take an incoming
structure and generate a new structure result. Since structure definitions
can contain arbitrary code these are a natural fit for functions.

There are sevaral variations on functions types and optional features like
defining additional blocks of unevaluated structures.

```javascript

!func :area ~circle = {
  radius * radius * #math#pi
}


## Local Temporaries

Function local variables can be assigned and referenced by tokens prefixed
with the `$` character. These values can only be referenced within the
same function, after they have been defined. 

There is also an even more temporary namespace for use within a single statement.
This uses the `^` caret symbol to prefix the token names. These pipeline
tokens will be lost after the pipeline they are defined in completes. They will
usually be defined with the `!label` operator to capture their values in 
mid-pipeline.

Both types of local temporaries cannot be referenced before they have been
defined.

## Comparison Operators

All values can be compared with the comparison operators. The comparison is 
based on a generic implementation by the language. It is not extensible or 
customizeable by operator overload.

Comparisons never fail, they always produce a resulting boolean. The results
are always determinisitc.

There are two families of comparisons that are implemnted differently.

* **Equality** is handled by the `==` and `!=` operators
* **Ordered** comparisons use `<` and `>` and can be used for sorting values
* **Hybrid** comparisong `<=` and `<=` check equality first and fallback on ordered.

### Equality Comparison (`==`, `!=`)
Tests for strict structural equality:
- Scalars auto-wrap to single-element structs: `5 == {5}` is true
- Named fields must match by name and value (order independent)
- Unnamed fields must match by position and value (order dependent)
- No type coercion or shape morphing occurs
- The results of `==` are always the opposite of `!=`

```javascript
{x=1 y=2} == {y=2 x=1}    // true (named field order doesn't matter)
{1 2} == {1 2}            // true (position matches)
5 == {5}                  // true (scalar auto-wrapping)
{x=1} == {x=1 y={}}       // false (different structure)
```

### Order Comparison (`<`, `>`)
Compare for ordering
- Empty struct `{}` is less than all other values
- Scalars auto-wrap to single-element structs for comparison
- Structures compare matched named fields first (alphabetically by name)
- Unmatched fields become positional and compare left-to-right
- Different types compare by priority: `boolean < tag < number < string`
- The results of `<` are always the opposite of `>`

```javascript
{} < 5 < "hello"           // true (empty < number < string)
{x=1 y=2} < {x=1 y=3}      // true (x equal, y compared)
{a=1} < {b=2}              // true (both become {1} < {2})
{42 "hi" {} true} -> :sort // [{} true 42 "hi"]
```

## Math Operators

The language provides a familiar set of operators like `+` for addition
and `*` for multiply. These operators only work with ~number values. 

The math operators are based on a generic implementation by the language. 
They are not extensible or customizeable by operator overload.


String types will rely heavily on the templating syntax and a library of
functions in the language libraries. There are no math operators for string
types.

## Basic Function Definition Syntax

Functions are defined using the `!func` keyword with optional shape constraints:

```comp
// Basic function definition
!func :function_name = {
    // Single expression that transforms input
    @in -> :some_operation -> {result=@.value}
}

// Function with input/output shape constraints
!func :calculate ~InputShape -> ~OutputShape = {
    @in.x * @in.y + @in.z
}

// Function with default parameters
!func :process ~{data, timeout=30, retries=3} = {
    data -> :transform {timeout=@in.timeout, retries=@in.retries}
}
```

## Pipeline Syntax

Comp uses pipeline operators to chain operations:

```comp
// Basic pipeline with arrow operator
data -> :transform -> :validate -> :save

// Pipeline with fallback operator  
data -> :risky_operation | default_value

// Conditional pipeline with ternary
condition ? success_pipeline | failure_pipeline
```

## Assignment Operators

Assignment uses the `=` operator in several contexts. The left side of the equal
sign is the target. Based on the type of target the assignment has different
behaviors.

* Local temporaries can be created or reassigned (`$` or `^` tokens)
* Outgoing fields are defined or overridden when the target is a plain token
* Namespaces can be modified by assigning to nested fields when the target has one of the namespace names that start with a leading dot (`.ctx`)

Remember that structures and all values are immutable read only data. The
assignment operator will use the assignments as a way to modify the original
values into a newly created, immutable structure with the assigned changes
applied.

The assignment operator is also used syntactically in all the keyword operators
that define new values. These have special meanings based on the definition
of the operator that is using them.

A variable or field assignment must always be the first part of a statement,
immediately following the target. When the assignment value is a pipeline or
flow control statement the assignment will be made with the final resulting
value, or possibly an error result.

```javascript
!function :example ~example-shape = {
    .ctx.server-port = 8000
    $temporary = 5
    outgoing = :listen
}
```

## Keyword Operators

The language uses a vocabulary of keywords for different purposes. These are
always prefixed with the `!` exclamation character. Operators often provide
custom syntax parsing that doesn't follow the standard language rules. They can
require additional tokens and values that aren't always valid syntax.

* **Definitions** like `!tag` or `!func` are used to define a new entry to the current module's namespace.
* **Module Management** Module namespace and dependencies are defined with `!import` and `!alias`.
* **Startup and Entry** Definition of entry points define special predefined function bodies like `!entry` and `!main`.
* **Internal Details** Access to internal information is done with `!discover`, even for objects not normally referenceable, like functions or modules.
* **Advanced Flow Control** Advanced interaction and creation of resources is handled with operators like `!transact`, `!release` and `!handle`.

## Weak and Strong Variants

In many contexts there are "weak" and "strong" variants of operators that
modify how conflicts are resolved.

* **Strong** make operation sticky or priority over regular operations.
* **Weak** make operation optional if conflicting values already exist.

These strength alternatives are used for
* **Assignment** using `*=` and `?=` for any kind of variable or field assignment.
* **Definition** using the weak and strong assignment in the defition operators 
  like `!func` allows multiple definitions to override or be ignored.
* **Spread** Structures can be created using spread operators from existing structs. These `..*` and `..?` spread variants act as if the strong or weak assignment was used on each
    field.

```javascript
{color='white' type*='cat' name?='felix'
 color='brown' type='dog', name?='rex'}
// results in {color=brown  type='cat' name='felix'}
```

## Flow Control

Ternary `cond ? trueval | falseval`
Fallback `| fallbackval`
Is the shortcut ternary `{cond} ?| {falseval}` still a thing? Why?

## Pipelines

## Failures

