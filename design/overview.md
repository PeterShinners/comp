# Comp Overview, Syntax, and Style

*Overview of the Comp language and parsing rules*

## Overview

Comp strives to create a limited vocabulary of terms and objects.

The language is whitespace agnostic, aside from each statement is required to be
separated by whitespace. This allows authors to place whitespaces wherever and
however improves readably, or nearly omit it entirely when compact expressions
are the priority. 

There are no commas between lists of fields, and no terminator or punctuation
used at the end of sentences.

All keywords and named functionality of prefixed with symbols. This is done
consistently to allow any field name to be a valid token, and will never
conflict with a keyword or operator in the language.

The top level definitions in a module is a declarative set of statements that
define the contents of the module. It is not executed like a script or runtime
language that incrementally builds the contents. This allows static analysis and
independent ordering of definitions.

## Example

```comp
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
    * Relaxed when lines must contain exceptionally long tokens or literal
      values.
* When pipelines are split across multiple lines, start each new line with the
  continuation operator like `->` or `|`.
* Prefer line breaks between statements.
* Simple expressions should use spaces to improve clarity of operator
  precedence.
* When multiple statements share a line, consider compressing each statements
  whitespace to improve readability.
* Prefer no whitespace between a value and its shape definition, like `name~str`
  or `value~record`.
* When a structure or shape definition splits multiple lines, add a level of
  indentation to the interior lines.
    * Prefer the leading curly brace to end on initial line.
    * Prefer the closing curly brace to end on its own line and match the
      indentation of the line with the leading curly brace.
* When complicated pipeline contains layers of nesting, consider a double curly
  brace to easily identify the entry and exit of subsections in the pipeline.

## Whitespace and Separators

The language allows any optional whitespace in between any tokens. The only
requirement is that whitespace is required between statements.

There are no commas or separators used between field definitions. There is no
semicolon or terminating symbol to mark the end of statements or pipelines.

## Tokens

Tokens are used for naming everything in Comp. There are several rules for valid
token names.
* Tokens must follow the UAX #31 specification for valid tokens.
  * This matches the behavior of Python and Rust.
* The `ID_Continue` set is expanded to also include the ascii hyphen.

The language convention is to use all lowercase characters where writing purely
Comp specific identifiers. When interfacing with other languages or data
specifications, use capitalizations and underscores where preferred.

The style preference is to use the hyphens as word separators instead of
compacting token names into abnormal compound words.

The style of using lowercase words with hyphen separates is referred to as
**lisp-case**.

Examples
* `html5`
* `content-accept`
* `_parity_bit`
* `用户名`

## Comments

The language supports line comments using the style `//` of double-slashes,
similar to Javascript and Rust. There is no support for block style comments.
Everything until the end of the line will be ignored by the compiler.

See the secion on Docstrings for related information.

## Module contents

A module defines a set of **functions**, **shapes**, and **tags**. Each type of
definition uses a unique character to prefix the name when it is defined and
every time it is referenced.

When referencing definitions from other modules, the language requies the
character prefix on the module and object reference.

* **Function** `:` prefixed with a colon, like `:process` or `:num:absolute`
* **Shape** `~` prefixed with tilde, like `~Rect` and `~io~Stream`
* **Tags** `#` prefixed with hash, like `#status` or `#log#severity`

Because of these prefixed characters, there is no problem with using conflicting
names for each type of definition.

## Structures

All data in Comp is represented as structures (ordered collections of fields).
Scalars automatically promote to single-element structures when needed:

```comp
42                    // Scalar number
{x=1.0, y=2.0}        // Named field structure
{10, 20, 30}          // Unnamed field structure (array-like)
```

Structures are flexible containers that can mix named fields and unnamed fields.
The values in the structure are ordered and can mix and match any type.

The content of the structure defines a shape, and that structure can be passed
to any function that defines a compatible shape (or schema).

The structure is an immutable object. The language defines operators and
function that allow creating new, derived structures in ways that feel like
making changes. Be aware that these operations are creating new immutable pieces
of data.

```comp
a = {color="red"}
b = a
a.color = "blue"
// b color is still "red"
```

The language also supports the concept of lazy structures, which behave more
like iterators, or generators from other languages. The fields in the lazy
structure are not computed until requested. Lazy structures use the same
definitions and rules as structures, but are surrounded with `[]` square
brackets. A lazy structure is only evaluated once and preserves the values it
creates, operating like a regular structure once iteration completes. When the
fields are requested from the lazy structure, it will execute as many fields are
needed to respond to the requested field.

```comp
$expensive = [
  "server" -> :expensive-hash
  "client" -> :expensive-hash
] // returns immediately, no expensive hashing completed
```

## Field References and Namespaces

Any undecorated token represents a lookup into one of several predefined
namespaces. These namespaces are structures that the language handles specially
as it is processing. The namespaces are always referenced with a leading `.`
dot.

These namespaces represent a layered hierarchy of fields, where the first
definition found overrides any of the later fields.

These namespaces are defined as

* `!out` is the structure being defined by the current execution block
* `!in` is the structure that was passed input to the current execution block
* `!ctx` is a structure that can be modified by executing function blocks and is
  inherited to all called functions.
* `!mod` is a module-specific namespace that can only be accessed by functions
  within that module.

The undecorated token references are used to lookup fields from this stack of
namespaces. An undecorated assignment to a field represent as assignment into
the `!out` namespace, which will win all future lookups.

```comp
a = 123                 // assigned to !out namespace
b = 321 + a             // assigns 444 to !out namespace
!mod.server-port = 8080
!ctx.server-port = 8200
server-port -> :listen  // References `8200` from the context namespace
```

## Shapes

Shapes are like schema definitions for structures. They define fields, types,
default values, and more. They are defined and referenced with a leading `~`
tilde. Shapes are often applied to structures to morph their shape to match the
given definition. There are complete rules on how this morphing is applied to
arbitrary structures.

```comp
!shape ~circle = {x~num y~num radius~num}
{12 5.5 3.13}~circle
```

## Tags

Tags are enumerated values that can be used similarly to both shapes and values.
The tags can be defined hierarchically to create a hierarchy, and each tag can
optionally have values. Each defined tag must be a valid token.

Tags in a structure heavily influence its shape, and can be used to create
polymorphic behaviors and overrides.

```comp
!tag #terrain = {mountain grain grass dirt}

{location = #terrain.grass}
```

## Functions

Functions in Comp are transformations of structures. They take an incoming
structure and generate a new structure result. Since structure definitions can
contain arbitrary code these are a natural fit for functions.

There are sevaral variations on functions types and optional features like
defining additional blocks of unevaluated structures.

```comp

!func :area ~circle = {
  radius * radius * #math#pi
}

$area = {12 5.5 3.13} -> :area
```

## Local Temporaries

Function local variables can be assigned and referenced by tokens prefixed with
the `$` character. These values can only be referenced within the same function,
after they have been defined. 

There is also an even more temporary namespace for use within a single
statement. This uses the `^` caret symbol to prefix the token names. These
pipeline tokens will be lost after the pipeline they are defined in completes.
They will usually be defined with the `!label` operator to capture their values
in mid-pipeline.

Both types of local temporaries cannot be referenced before they have been
defined.

## Booleans

Booleans are represented by the special built-in tags `#true` and `#false`. No
value types can be automatically converted to a boolean. Many conditional
operations require booleans, and will interpret `#false` and `{}` (empty
structures) as false, all other values as true. 

## Comparison Operators

All values can be compared with the comparison operators. The comparison is
based on a generic implementation by the language. It is not extensible or
customizeable by operator overload.

Comparisons never fail, they always produce a resulting boolean. The results are
always determinisitc.

There are two families of comparisons that are implemnted differently.

* **Equality** is handled by the `==` and `!=` operators
* **Ordered** comparisons use `<` and `>` and can be used for sorting values
* **Hybrid** comparisons `<=` and `>=` check equality first and fallback on
  ordered.

### Equality Comparison (`==`, `!=`)
Tests for strict structural equality:
- Scalars auto-wrap to single-element structs: `5 == {5}` is true
- Named fields must match by name and value (order independent)
- Unnamed fields must match by position and value (order dependent)
- No type coercion or shape morphing occurs
- The results of `==` are always the opposite of `!=`

```comp
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

```comp
{} < 5 < "hello"           // true (empty < number < string)
{x=1 y=2} < {x=1 y=3}      // true (x equal, y compared)
{a=1} < {b=2}              // true (both become {1} < {2})
{42 "hi" {} true} -> :sort // [{} true 42 "hi"]
```

## Math Operators

The language provides a familiar set of operators like `+` for addition and `*`
for multiply. These operators only work with ~num values. 

The math operators are based on a generic implementation by the language. They
are not extensible or customizeable by operator overload.

String types will rely heavily on the templating syntax and a library of
functions in the language libraries. There are no operators for string types.

## Fallback Operator

The language also provides a simple `|` operator to provide a fallback
value for any immediate expression that may have failed. This prevents the
normal failure value from propogating to the remaining pipeline. If the
expression operates successfully then the fallback expression is ignored. This
is commonly used for attribute lookups that may not be defined.

```comp
config.volume | 100   // use the config volume field or fallback on 100
```

## Other Operators

The language provides a placeholder symbol `...` of triple dots.
This is a valid token in nearly all contexts. This will allow a module
to compile and be usable without being fully implemented. When program
flow reaches this `...` symbol it will result in an immediate failure.


## Basic Function Definition Syntax

Functions are defined using the `!func` keyword and require a shape:

```comp
// Basic function definition
!func :function-name ~{incoming} = {
    incoming -> :some-operation -> {outgoing=value}
}

// Function with input/output shape constraints
!func :calculate ~axis = {
    x * y + z
}

// Function with default parameters
!func :exclamations ~{message count=1} = {
    count -> :repeat .{"${message}!}
}
```

## Pipelines

Functions are invoked through pipeline operations. This encourages chaining
method calls in order with the `->` operator and is intended to read left to
right.

Each statement in the pipeline can be one of several types of values
* **Function** which is passed the incoming structure and passes its return.
* **Structure** defining a structure replaces (or often edits) the next
  structure used in the pipeline
* **Value** Any value can have an invoke function attached when it is used as a
  pipeline statement, this is done by default for strings to invoke formatting.

The language provides several pipeline operators that have different behaviors.
* **Invoke** `->` Pass a structure to the next in one operation.
* **Iterate** `=>` Invoke a function for each field in the structure and combine
  results.
* **Spread** `..>` Spread a new structure to merge onto the previous output.
* **Failed** `!>` Invoke a discovered upstream failure.
* **Valve** `-?` with `-&` and `-|` conditional operators.

```comp
// Basic pipeline with arrow operator
data 
-> {users=people} // rename field and remove other data
-> :transform     // invoke a method
=> :validate      // invoke a method on each entry
-> :save          // invoke method on collected data
!> {:log:error -> {}}  // log error and provide fallback
```

Functions are intended to be invoked on structures. Some functions are defined
as having no structure (they use the `~nil` shape). Normally these would need to
be invoked with `{} -> :simple-func`. As a shortcut these can be invoked
starting the expression with the function reference, `:simple-func`.

## Assignment Operators

Assignment uses the `=` operator in several contexts. The left side of the equal
sign is the target. Based on the type of target the assignment has different
behaviors.

* Local temporaries can be created or reassigned (`$` or `^` tokens)
* Outgoing fields are defined or overridden when the target is a plain token
* Namespaces can be modified by assigning to nested fields when the target has
  one of the namespace names that start with a leading dot (`!ctx`)

Remember that structures and all values are immutable read only data. The
assignment operator is only used to create new values. The assignment 
provides several high level ways to derive a new structure based on the
contents of the original.

The assignment operator is also used syntactically in all the keyword operators
that define new values. These have special meanings based on the definition of
the operator that is using them.

A variable or field assignment must always be the first part of a statement,
immediately following the target. When the assignment value is a pipeline or
_flow_ control statement the assignment will be made with the final resulting
value, or possibly an error result.

```comp
!function :example ~example-shape = {

    a = {color=”red”}
    b = a
    a.color = “blue”
    // b.color is still red; the original, immutable value

    !ctx.server-port = 8000
    $temporary = 5
    outgoing = :listen
}
```

## Keyword Operators

The language uses a vocabulary of keywords for different purposes. These are
always prefixed with the `!` exclamation character. Operators often provide
custom syntax parsing that doesn't follow the standard language rules. They can
require additional tokens and values that aren't always valid syntax.

* **Definitions** like `!tag` or `!func` are used to define a new entry to the
  current module's namespace.
* **Module Management** Module namespace and dependencies are defined with
  `!import` and `!alias`.
* **Startup and Entry** Definition of entry points define special predefined
  function bodies like `!entry` and `!main`.
* **Internal Details** Access to internal information is done with `!discover`,
  even for objects not normally referenceable, like functions or modules.
* **Advanced Flow Control** Advanced interaction and creation of resources is
  handled with operators like `!transact`, `!release` and `!handle`.

## Weak and Strong Variants

In many contexts there are "weak" and "strong" variants of operators that modify
how conflicts are resolved.

* **Strong** make operation sticky or priority over regular operations.
* **Weak** make operation optional if conflicting values already exist.

These strength alternatives are used for
* **Assignment** using `*=` and `?=` for any kind of variable or field
  assignment.
* **Definition** using the weak and strong assignment in the defition operators
  like `!func` allows multiple definitions to override or be ignored.
* **Spread** Structures can be created using spread operators from existing
    structs. These `..*` and `..?` spread variants act as if the strong or weak
    assignment was used on each field.

```comp
{color='white' type*='cat' name?='felix'
 color='brown' type='dog', name?='rex'}
// results in {color=brown  type='cat' name='felix'}
```

## Private Data Attachment

Private and unexported data uses the `&` in different ways to prevent other
modules from accessing values and definitions. Remember this by tilting your
head and imagining the symbol represents a padlock.

Each module has a private namespace `!mod` that allows storing and updating data
that no code outside the current module can reference or modify.

### Private Definitions

Shape, function, and tag definitions that are internal for the module use only.
These definitions place an `&` ampersand as a suffix on the name. This also
applies to namespace aliases which are exported by default.

```comp
!func :secret_hash& ~str = {...}
!tag @attachment& = {precall postcall}
!shape bunker& = {width~num length~num depth~num}
```

The & suffix is not used when referencing private definitions. The privacy is an
access control mechanism, not part of the interface itself.

This also applies when using the `!alias` operator. Aliases default to being
exposed definitions for the module itself. Adding the `&` ampersand suffix
allows them to be used privately.

```comp
!alias :leftpad = :str:ljust    // global definition
!alias #logsev& = #log#severity // private definition
```

### Private Data Attachment

Each module can attach private data to any structure using `&` syntax. Other
modules cannot access private data attached by different modules:

This private data exists outside the value itself, which means the shape is not
modified by hidden or internal fields.

Referencing and assigning private data can be done either individual fields or
the entire private structure.

```comp
// Create structure with private data inline
$user = {login="pete" email="pete@example.com"}&{session="abc123" id=789}

// Access private data (only in same module)
$user.login          // "pete" - public field
$user&.session       // "abc123" - private field (same module only)
$user&.id           // 789 - private field (same module only)

// Manual private data assignment
$user& = {session="abc123", internal_id=789}
```

This private data is natually transferred to every value passed through a
pipeline's chain of statement. This includes full spread operators.

```comp
$user& = {session="abc", token="xyz"}

// Automatic preservation in pipelines
$result = $user -> :transform -> :validate
// $result& = {session="abc", token="xyz"}

// Automatic preservation in full spread
$copy = {...$user extra="field"}
// $copy& = {session="abc", token="xyz"}

// Manual copying when needed
$selective = {name=$user.name}
$selective& = $user&  // Manual private data transfer
```

When the result of a structure comes from the combination of mutliple existing
structure then the private data will be merged, using "first reference wins"
collision rules. There is no way to override this merging behavior using strong
or weak operations.

When strict handling of private data is needed through complex merging
operations, the private data can always be saved and modified from earlier steps
in the operation, then applied back to the resulting object directly.

```comp
$source1& = {token="abc", shared="first"}
$source2& = {cache="xyz", shared="second"}

$merged = {field1=$source1.name, field2=$source2.email}
// $merged& = {token="abc", shared="first", cache="xyz"}
// First reference wins: $source1& merged before $source2&
```

## Docstrings

The language supports docstrings which are extended user information attached to
any shape, function, tag, or field. These are more powerful than comments
because they are recognized by the language and can be accessed at runtime.

A docstring is a string literal that follow the `!doc` operator. These can use
single or triple string quotes for single and multiline use cases. There are two
forms of these documentation strings.
* **Inline** is the simplest, it uses `!doc "Information"` to immediately apply
the docstring to whatever function, shape, tag, or field definition follows.
* **Detached** adds a reference to the object being documented, like `!doc
#severity = "Logging level strengths."

Docstrings for the module must use the detached form of `!doc module "Top level
info."`.

Multiple docstrings attached to the same definition are appended together in
file order, with a blank line inserted between each docstring. Docstring tools
will expect docstrings to use Markdown formatting to style the information.

Use inline `!doc` for:
* *Brief single-line descriptions
* *Simple field documentation

Use detached `!doc target` for:
* *Extended multi-paragraph documentation  
* *Documentation in separate files
* *Avoiding clutter in complex definitions
* *Module-level documentation (required)

More documentation guidelines:
* Single line summaries whould be written like a sentence with capitalization
  and punctuation.
* Multiple definitions of detached documentation will be joined with an empty
  line.
* When a definition only has a multiline detached docstring it should still
  include a summary line that is separated by a single blank line from the
  remaining documentation.

```comp
!tag #status = {
    pending={review approved rejected}
    !doc "Actively being developed."
    active
    !doc "All work completed and ready to deliver."
    complete
}

!doc #status "Workflow status indicators."
!doc #status.pending "Awaiting decision."
!doc #status.pending.review "Under active review."
!doc #status.pending.approved "Approved but not yet active."
```

Documentation strings are regular string literals and can include formatting
instructions `${}`. Documentation strings expanded in a special context that has
access to
* `field` lookup fields in the static module namespace
* `doc.toc` table of contents for the active object (module, shape, or tag)
* `describe` structure created using the `!describe` operator for the attached
  object

Documentation tools should attempt to auto-recognize references to functions
shapes and tags and generate properly linked references where possible.

It should not be necessary to document information clearly defined in the
language, like field shapes or default values. Tools displaying documentation
should also consider grouping multiple implementations of a function with the
same name, when defined with different shape signatures.