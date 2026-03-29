# Syntax and Style Guide

Comp is a whitespace and newline independent, expression-oriented language.
Source code is a series of module-level declarations and expressions using two
paired delimiters: `()` for statements and pipelines, and `{}` for structure
literals. These bracket types are the backbone of the grammar and each has
distinct semantics described throughout this guide. The language also provides
`~{}` for shape definitions, and all brackets can be prefixed with `:` to create
deferred operations `:()` and `:{}`.

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
    !param value~num
    /* block comments
       can span multiple lines /* and nest */ */
)
```

Block documentation `/** */` at the start of a file documents the module itself.
Comments positioned between declarations become section documentation, available
to documentation generators.

## Bracket Types

Comp uses two bracket types to define different constructs in the language.
These each have distinct rules about the grammar and statements they allow.
Prefixes modify the behavior of either bracket type.

**Parentheses `()`** group statements and scope pipelines. The `|` pipe
operator is valid inside parentheses and is greedy — it fills the entire scope.
A single expression in parentheses is simple precedence grouping. Multiple
statements evaluate in sequence, with the last expression as the result. Local
variables are defined with `!my` and `!ctx` scope modifiers. All `=` bindings
inside parentheses are local — nothing is exported.

**Braces `{}`** define structure literals. They hold both named and positional
fields separated by whitespace. Each non-`!my` expression inside braces
contributes a field to the resulting struct. Named fields use `=` for
assignment; bare values become positional fields. The `|` pipe operator is
not valid inside braces — use `()` to scope a sub-pipeline within a struct
field expression.

**Shapes `~{}`** are similar to structure literals. They define a set
of fields, which must have at least one of an optional name and an optional
shape. Each field can also be assigned an optional default value, which must
be a simple expression. The `~` shape can be used to reference shapes or
build union types, but with curly braces defines a literal shape.

**Angle brackets `<>`** define type limits. These can be applied to types
inside of any shape definition. This defines a set of "limits" or "conditions"
that allow advanced type matching.

```comp
{1 2 3}                                // struct with three positional fields
(1 2 3)                                // evaluates to 3 (last expression)
{name="Alice" age=30 active=true}      // struct with named fields
($.name | uppercase)                   // pipeline
(|sort reverse)                        // headless invoke
~num<integer>                          // guard on a type
```

## Deferred Blocks

Any bracket type can be prefixed with `:` to defer execution. These deferred
values are often called blocks. Deferred blocks are used as callback arguments
to functions, enabling flow control and iteration through regular function calls
rather than special syntax.

`:()` creates a deferred pipeline or statement block. The contents follow the
same rules as `()` — pipelines are valid, `=` bindings are local, last
expression is the result.

`:{}` creates a deferred structure. The contents follow `{}` rules — named and
positional exports, no pipelines.

Deferred blocks receive an input value through `$` when invoked, and can define
their own parameters.

```comp
| where :($.created-at >= cutoff)
| map :(
    !my raw = $.reaction-groups
    (raw | count :($.content == "thumbs-up"))
)
| map :{
    thumbs = ($.reactions | count :($.content == "thumbs-up"))
    title = $.title
    url = $.url
}
```

## Pipelines

The pipe `|` operator chains function calls inside parentheses `()`. Each step
passes its result as input to the next. Pipelines are Comp's primary
composition mechanism, replacing method chaining and nested function calls from
other languages.

Pipelines are **greedy** — the `|` operator fills the entire enclosing `()`
scope. This means arguments to each pipeline step are naturally terminated by
the next `|` or the closing `)`. No special delimiters are needed around
arguments.

```comp
(data
| reduce initial=nil tree-insert
| tree-values
| output
)
```

### Pipeline Input

A pipeline can start with a value expression as the initial input, or use
a leading `|` to invoke the first step with no input (headless invoke).

```comp
// Pipeline with input — expression before first |
($.items | sum :($.price * $.quantity))

// Headless invoke — leading | means "call with no input"
(|read-lines | map parse | output)
(|datetime.now)
```

The leading `|` is necessary to distinguish invocation from reference. Without
it, a bare identifier is just a value:

```comp
(datetime.now)              // reference to datetime.now
(|datetime.now)             // invoke datetime.now, get current time
(alpha beta)                // two statements, result is beta
(|alpha beta)               // invoke alpha with beta as argument
```

### Arguments in Pipelines

Each step in a pipeline receives the previous result as `$` and can take
additional arguments. Arguments are space-separated and follow the same syntax
as struct fields — named or positional.

```comp
(data
| sort reverse
| first 5
| fmt "result: %()"
)
```

Deferred blocks attach to a pipeline step as arguments using `:()` or `:{}`.
Multiple deferred blocks can be chained:

```comp
| where :($.created-at >= cutoff)
| sort reverse :($.thumbs)
| if condition :(|generate-yes) :(|generate-no)
| accumulate 50 :($.accum + $.value)
```

### Pipelines Inside Structures

The `|` operator cannot appear directly inside `{}` braces. To use a pipeline
as a struct field value, wrap it in `()`:

```comp
{
    name = (login | uppercase)
    id = (raw-id | validate | format)
    simple = 42
}
```

### Scope Modifiers in Pipelines

`!my` and `!ctx` can appear as pipeline steps. They capture a snapshot of the
current pipeline value and pass it through unchanged, acting as a tee:

```comp
(data
| !my raw-issues = $
| where :($.created-at >= cutoff)
| !ctx issue-count = ($ | length)
| map :($.thumbs = ($.reactions | count :($.content == "thumbs-up")))
)
```

## Failures and Fallbacks

The `!fail` operator raises a failure value that fast-forwards through the call
chain. Failures skip all intermediate pipeline steps and struct field
evaluations until caught. Failures carry a value, typically a struct with a
message and optional tag for categorization.

As a shortcut, the `!fail` operator can be given a qualified name from the
fail hierarchy. In this case it gets a single string value, which gets
combined into a single structure.

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
(data | find :name="alice" |? default-user)
(risky-operation |? (log-error | safe-default))

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
block or function. Field access uses dot notation on `$`.

Multiple `$` symbols can be stacked to reference the input from each outer level
of blocks inside a function.

```comp
$               // entire input value
$.name          // input's "name" field
$.items.price   // nested field access
$$              // outer scope's input (one level up)
$$.filter       // outer scope's field
```

## Namespaces

Each module defines a rich hierarchical namespace of its functions, shapes,
and tags. Comp allows nested names to be referenced by their leaf names when
there are no conflicts.

Inside of a function there is an additional namespace that is managed by the
`!my` `!ctx` and `!param` operators. These locals will shadow the module's
namespace. But explicit references starting with `mod.` and `my.` will pick only
values from one scope or the other.

## Operators

Mathematical operators follow standard precedence. All arithmetic operates on
numbers only, no string concatenation or boolean arithmetic.

```comp
+ - * /            // arithmetic
== != < > <= >=    // comparison (return true/false)
<>                 // three-way comparison (returns ~less ~equal ~greater)
!and !or !not      // logical (booleans only)
|                  // pipeline (greedy within parentheses)
|?                 // pipeline fallback
??                 // value fallback
=                  // field assignment (structs) or local binding (statements)
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
{1 2 3} == {1 2 3}        // true
5 == 5.0                  // true, same numeric value
5 == "5"                  // false, different types
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
~less ($.left | tree-contains :value)
~greater ($.right | tree-contains :value)
~equal true
```

## Text Literals and Interpolation

Text uses double quotes. Multiline text literals use triple quotes. Standard
escape sequences like `\n` and `\"` are supported. The language has no text
operators for things like concatenation or repetition. Text manipulation happens
through library functions, including powerful template formatting.

The library provides the `fmt` function that can be used in two ways to
format string substitutions into a string. The `@fmt` wrapper applies the
current scope to the string substitutions. The regular `fmt` pipeline
applies a piped input value to a string template.

See the [Type](type.md) documentation for more formatting details and examples.

```comp
@fmt "hello %(name)"                         // interpolate from scope
(data | fmt "row %($.id): %($.title)")       // fmt function for data templates
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

Inside function bodies and blocks, `!` operators handle scope modification,
dispatch, and control flow. These are available in both `()` statement blocks
and `{}` structure blocks.

`!my` modifies the scope of the following statement. In `()` blocks, all
bindings are already local, so `!my` serves to execute a statement without
contributing to the block's result, or to capture intermediate values. In `{}`
blocks, `!my` prevents a statement from being exported as a struct field —
it becomes a private local binding.

```comp
// In a () block — captures intermediate values
!my cutoff = (|datetime.now) - 1#week
!my sign = (($.#0 == "R") | pick 1 -1)

// In a {} block — prevents export
{
    !my base-price = ($.price * $.quantity)
    subtotal = base-price * 0.9
    tax = base-price * 0.08
}
```

`!ctx` works like `!my` but places the value into the context scope, making it
available as a default parameter for all downstream function calls.

```comp
!ctx repo = "nushell/nushell"
!ctx timeout = 30
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