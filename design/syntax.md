# Syntax and Style Guide

Comp is a whitespace and newline independent, expression-oriented language.
Source code is a series of module-level declarations and expressions using three
paired delimiters: `()` for statements, `{}` for structure literals, and `[]`
for pipeline definitions. These bracket types are the backbone of the grammar
and each has distinct semantics described throughout this guide. The language
also provides uses `~{}` for shape definitions and all of the brackets can be
used to create deferred operations `:[]` `:()` and `:{}`.

Whitespace is required only between fields of a structure and between tokens
that would otherwise be ambiguous. Tabs are preferred for indentation. A
formatter tool `compfmt` will handle line-breaking and indentation choices, so
developers can write code in whatever shape feels productive and let the
formatter enforce consistency.

## Tokens and Naming

Identifiers use **kebab-case**, lowercase words separated by hyphens. Digits are
allowed after the first character and upper case letters are allowed throughout.
Leading and trailing underscores are permitted but leading or trailing hyphens
are not. Characters are case-sensitive and the full UAX #31 Unicode
specification is supported, but lower case is preferred. These unicode rules
match what Rust and Python allow for identifiers (with the addition of hyphens).
Identifiers cannot begin or end with hyphens.

```comp
valid-name      html5       _private     用户名
Content-Accept  is-active   pad-left     tree-insert
```

## Identifier Fields

Most identifiers will use a chain of dotted field names, like `one.two.three`.

There are additional ways to reference field names that do not follow token
naming rules. Any expression and value type can be used as a field name. This is
done by wrapping the name in single quotes. This allows any type of value, like
numbers, booleans, tags and anything else. Like `'2+4'` or `'#status.ok'`.

Fields can also be referenced positionally. This is done using the `#` with a
number value. Like `#3` or `#0`. This can also use a mathematical expression
wrapped in parenthesis to compute an index `#(2+2)`.

Any string can also be used as a field reference when wrapped in double quotes.
Like `"Full Name"`.

These types of field names can be combined in a single identifier.

```comp
records.#0."Owners".'my.owner-name'.active?
```

Although this does not work to reference the first level of a field name, only
nested fields can use this, string literals cannot be used as the root
name without wrapping in single quotes also.

## Comments and Documentation

Line comments use `//`. Block comments use `/* */` and nest properly. Triple-
slash `///` marks documentation comments that attach to the following
declaration. The language provides ways to get all styles of comments
attached to any value.

```comp
/// Add new value into tree, dispatched on nil vs tree
!pure tree-insert ~tree @update (
    // normal implementation comment
    !params value~num
    /* block comments
       can span multiple lines /* and nest */ */
)
```

Block documentation `/** */` at the start of a file documents the module itself.
Comments positioned between declarations become section documentation, available
to documentation generators.

## Bracket Types

Comp uses a set of bracket types to define different constructs in the
language. These all have their own customizations on the grammar and
statements they allow.

**Parentheses `()`** are used to group statements. This can be used for
simple expressions to control operator precedence. It can also be used
to group several statements into a single operation that results in the
value of its final statement. Local variables can be defined with the `!my`
and `!ctx` operators.

**Braces `{}`** define structure literals. They hold both named and positional
fields separated by whitespace. Each non-`!my` line inside braces contributes a
field to the resulting struct. Named fields use `=` for assignment; bare values
become positional fields. Local variables can be defined with the `!my`
and `!ctx` operators.

**Square Brackets `[]`** define a set of operations in a pipeline. These
can be multiple operations separated by `|` pipe operators. Each operation
in the pipeline is considered a callable object and the optional parameters
that bind to it. There can be no locals defined in a pipeline.

**Shapes `~{}`** shapes are similar to structure literals. They define a set
of fields, which must have at least one of an optional name and an optional
shape. Each field can also be assigned an optional default value, which must
be a simple expression. The `~` shape can be used to reference shapes or
build unioned types, but with the curly braces defines a literal shape.

**Angle brackets `<>`** define type limits. These can be applied to types
inside of any shape definition. This defines a set of "limits" or "conditions"
that allow advanced type matching.

```comp
{1 2 3}  // Ordered struct with three unnamed fields
(1 2 3)  // Literal 3

[$.name | uppercase]  // Pipeline
{name="Alice" age=30 active=true}  // Struct literal with named fields

[sort reverse]  // Parameter on an invokable
~num<integer>  // Guard on a type
```

## Pipelines

The pipe `|` chains function calls inside of square brackets `[]`. These pass
the result of the left side as
input to the right side. Pipelines are Comp's primary composition mechanism,
replacing method chaining and nested function calls from other languages.

A pipeline can be made of a single operation or many. The first operation in
a pipeline can be a plain valid to use as the initial input. This value seed
for the pipeline cannot have any parameters.

Parameters for each operation can either be named or unnamed, similar to the
syntax inside of a `{}` struct literal.

```comp
[{5 3 8 1 7 9}
| reduce initial=nil tree-insert
| tree-values
| output
]
```

## Failures and Fallbacks

The `!fail` operator raises a failure value that fast-forwards through the call
chain. Failures skip all intermediate pipeline steps and struct field
evaluations until caught. Failures carry a value, typically a struct with a
message and optional tag for categorization.

As a shortcut, the `!fail` operator can be given a qualified name from the
fail hierarchy. In this case it gets a single string value, which get
combined into a single structure

```comp
!fail {fail.value "expected number, got text"}
!fail.module.missing "no module named 'future'"
```

### Builtin Fail Tags

The system provides a hierarchy of fail tags for categorizing language-level
failures. All are subtags of `#fail`.

```text
fail
├── value - wrong value or type (shape mismatch, cast failure, nil where disallowed)
├── field - bad accessor: field not found, index out of bounds, key missing
├── math - arithmetic failure: division by zero, overflow, domain error
├── grab - invalid or released resource handle
├── module
│   ├── missing - module could not be found
│   └── syntax - module source could not be parsed
├── reference
│   ├── undefined - name is not defined in scope
│   └── ambiguous - partial name matches more than one definition
└── invoke - call-level failure: no overload matched, recursion limit, bad parameter count
```

### Fallbacks

Two operators catch failures. The pipeline fallback `|?` catches failures
flowing through a pipeline and provides an alternative path. The value fallback
`??` catches a failure on any single expression.

Use the most specific tag available. Catch a parent tag (`#fail.module`) to
handle all subtypes, or a leaf tag (`#fail.module.missing`) to handle a single
case.


```comp
// Pipeline fallback, catch failure from preceding pipeline
data | find :name="alice" |? default-user
risky-operation |? (log-error | safe-default)

// Value fallback, catch failure on any expression
config.optional-field ?? "default-value"
$.timeout ?? 30
```

The distinction is scope: `|?` operates on the entire pipeline result up to that
point, while `??` operates on the single expression to its left. Both replace
the failure with the right-hand value. Failures are not exceptions, they
propagate through values, not through a separate control channel, making failure
handling explicit and traceable.

## Input References

The `$` symbol accesses the pipeline input, the data flowing into the current
block or function. Field access drops the dot for the common case, using `$`
directly followed by the field name.

Multiple `$` symbols can be stacked to reference the input from each outer level
of blocks inside a function.

```comp
$              // entire input value
$.name          // input's "name" field (shorthand for $.name)
$.items.price   // nested field access still uses dots
$$             // outer scope's input (one level up)
$$.filter       // outer scope's field
```

## Namespaces

Each module defines a rich hierarchical namespace of its functions, shapes,
and tags. Comp allows nested names to be referenced by their leaf names when
there are no conflits.

Inside of a function there is an additional namespace that is managed by the
`!my` `!ctx` and `!param` operators. These local will shadow the module's
namespace. But explicit references starting with `mod.` and `my.` will pick only
values from one scope or the other.

## Operators

Mathematical operators follow standard precedence. All arithmetic operates on
numbers only, no string concatenation or boolean arithmetic.

```comp
+ - * /            // arithmetic
== != < > <= >=    // comparison (return true/false)
<>                 // three-way comparison (returns ~less ~equal ~greater)
:and :or :not      // logical (booleans only)
|                  // pipeline
|?                 // pipeline fallback
??                 // value fallback
=                  // field assignment in structs and parameters
```

The three-way comparison `<>` returns a tag rather than a boolean. The `less`,
`equal`, or `greater` result enables dispatch over all three cases in a single
`!on` expression. See the [Functions](function.md) documentation for details
about `!on`.

## Comparison and Equality

Equality (`==`, `!=`) tests structural equivalence. Values of different types
are never equal. Named field order does not matter for equality, but positional
order does.

```comp
{x=1 y=2} == {y=2 x=1}   // true, named order irrelevant
{1 2 3} == {1 2 3}       // true
5 == 5.0                 // true, same numeric value
5 == "5"                 // false, different types
```

Ordering (`<`, `>`, `<=`, `>=`) provides total ordering across all types. Any
two values can be compared with deterministic results. Types are ordered by
priority: nil, empty struct, false, true, number, text, tag, struct. Within a
type, values use their natural ordering, numeric for numbers, lexicographic for
text, field-by-field for structs.

The three-way comparison `<>` returns a tag (`~less`, `~equal`, or `~greater`)
rather than a boolean, enabling clean dispatch over all three cases.

```comp
!on (value <> $.value)
~less ($.left | tree-insert[value])
~greater ($.right | tree-insert[value])
~equal $
```

## Text Literals and Interpolation

Text use double quotes. Multiline text literals uses triple quotes. Standard
escape sequences like `\n` and `\"` are supported. The language has no text
operators for things like concatenation or repetition. Text manipulation happens
through library functions, including powerful template formatting.

The library provides the `fmt` function that can be used in two ways to
format string substitutions into a string. The `@fmt` wrapper applies the
current scope to the string subsititions. The regular `fmt` pipeline
applies a piped input value to a string template.

See the [Type](type.md) documenation for more formatting details and examples.

```comp
@fmt "hello %(name)"                 // interpolate from scope
[data | fmt "row %($.id): %($.title)"]  // fmt function for data templates
```

## Module-Level Declarations

All top-level constructs use `!` operator syntax. This is a different grammar
than used inside of the various blocks like `()` and `{}`. These declarations
build the module's namespace and are fully resolved before any code executes.

```comp
!import rio comp "@gh/rio-dev/rio-comp"     // import module
!shape todo ~{title~text complete~bool}     // define data shape
!tag visibility {all active complete}       // define tag hierarchy
!startup main (...)                         // define entry point
!func handle ~event (...)                   // define function
!pure total ~cart (...)                     // define pure function
!alias crc zlib.crc32                       // namespace alias
```

See [Modules](module.md) for import handling and namespace resolution, and
[Functions](function.md) for function definition details.

## Statement Operators

Inside function bodies and blocks, `!` operators handle local bindings,
dispatch, and control flow. These are generally available in the
`()` statement and `{}` structure blocks, but `[]` pipeline blocks are
unable to use most operators.

`!my` creates a local binding. It does not use `=`, which is reserved for
field assignment. The binding captures the value of the following expression.
That variable can be accessed using the defined name inside the function
block and all its nested block definitions.

```comp
!my base $.price * $.quantity
!my cutoff [datetime.now] - 1[week]
```

`!on` performs type-based dispatch. It evaluates an expression and branches
based on the type or tag of the result. See [Functions](function.md) for
complete dispatch documentation.

```comp
!on (value <> $.value)
~less ($.left | tree-insert :value)
~greater ($.right | tree-insert :value)
~equal $
```

`!fail` raises a failure value that fast-forwards through the call chain until
caught by a `|?` or `??` operator. See the Failures and Fallbacks section above.

## Deferred Statements

Any type of statement braces can be prefixed with a `:` to defer execution
of the statement. These are often called blocks. These work for `:{}` structure
definitions, `:()` statement definitions`, and `:[]` pipeline definitions.

To invoke a deferred statement it is put inside the pipeline brackets.
Deferred pipelines can be used to create partials, binding some parameters
to the final statement. When executing the statement additional parameters
can be defined.

```comp
!my data :{2+2 1+1 5+5}    // not evaluated immediately
!my tool :[[data] | sort]  // also not evaluated
!my result [tool reverse]  // results in {10 4 2}
```
