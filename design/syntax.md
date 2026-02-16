# Syntax and Style Guide

Comp is a whitespace-flexible, expression-oriented language. Source code is a
series of module-level declarations and expressions using three paired
delimiters: `()` for blocks and expressions, `{}` for struct containers. These
three bracket types are the backbone of the grammar and each has distinct
semantics described throughout this guide. The language also provides uses `~{}`
for shape definitions and `[]` inside of those for type guards and conditions.

Whitespace is required only between fields of a structure and between tokens
that would otherwise be ambiguous. Tabs are preferred for indentation. A
formatter tool `compfmt` will handle line-breaking and indentation choices, so
developers can write code in whatever shape feels productive and let the
formatter enforce consistency.

## Tokens and Naming

Identifiers use **kebab-case**, lowercase words separated by hyphens. Digits
are allowed after the first character. Leading and trailing underscores are
permitted but leading or trailing hyphens are not. Characters are case-sensitive
and the full UAX #31 Unicode specification is supported, but lower case is
preferred. These unicode rules match what Rust and Python allow for identifiers
(with the addition of hyphens). Identifiers cannot begin or end with hyphens.

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
records.#0."Owners".'$.owner-name'.active?
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

**Parentheses `()`** are used to group expressions. There are places in
the grammar where expressions can be deferred, which turns `()` statements
into blocks, or even fully defined functions. It is allowed to put multiple
statements into the parenthesis, but the statement will always evaluate to
the value of the final statement. Inside a block, `$`
references the input value. The outer statement defining a function provides
a local scope defined by `!let` variables and are shared across all internal
defined blocks, like closures.

**Braces `{}`** define structure literals. They hold both named and positional
fields separated by whitespace. Each non-`!let` line inside braces contributes a
field to the resulting struct. Named fields use `=` for assignment; bare values
become positional fields. Structure literals can also be deferred statements
and used as the bodies for function and block statements.

**Shapes `~{}`** shapes are similar to structure literals. They define a set
of fields, which must have at least one of an optional name and an optional
shape. Each field can also be assigned an optional default value, which must
be a simple expression. The `~` shape can be used to reference shapes or
build unioned types, but with the curly braces defines a literal shape.

**Square brackets `[]`** are type modifiers. These can be applied to types
inside of a shape definition. This defines a set of "guards" or "conditions"
that allow advanced type matching.

```comp
{1 2 3}  // Ordered struct with three unnamed fields
(1 2 3)  // Literal 3

($.name | uppercase)  // Block
{name="Alice" age=30 active=true}  // Struct literal with named fields

sort :reverse  // Parameter on an invokable
~num[integer]  // Guard on a type
```

## Pipeline Operator

The pipe `|` chains function calls, passing the result of the left side as
input to the right side. Pipelines are Comp's primary composition mechanism,
replacing method chaining and nested function calls from other languages.

```comp
{5 3 8 1 7 9}
| reduce :initial=nil :(tree-insert)
| tree-values
| print
```

The syntax treats it like any binary operator which can be packed into a single
expression or split however desired across multiple lines. Parameters are
attached to invokable objects as a tail of prefixed `:` expresions, which
provide either named or positional parameters.

## Failures and Fallbacks

The `!fail` operator raises a failure value that fast-forwards through the call
chain. Failures skip all intermediate pipeline steps and struct field
evaluations until caught. Failures carry a value, typically a struct with a
message and optional tag for categorization.

```comp
!fail {fail.value "index out of bounds"}
!fail {fail.database message="not found"}
```

Two operators catch failures. The pipeline fallback `|?` catches failures
flowing through a pipeline and provides an alternative path. The value fallback
`??` catches a failure on any single expression.

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

The `$` sigil accesses the pipeline input, the data flowing into the current
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
on `!on`.

## Text Literals and Interpolation

Text use double quotes. Multiline text literals uses triple quotes. Standard
escape sequences like `\n` and `\"` are supported. The language has no text
operators for things like concatenation or repetition. Text manipulation happens
through library functions, including powerful template formatting.

The formatting functions in the library use `%(expression)` with an optional
`[format]` suffix. A bare `%` without a following `(` is just a literal percent
sign, no escaping needed in most cases. Use `%%(` for the rare case of a
literal `%(`.

```comp
"hello %(name)"                      // interpolate from scope
"price: %($ * 1.08)[.2]"             // expression with format
"%(count)[04] items at 100% markup"  // format spec, literal %
data | fmt :"row %($.id): %($.title)"  // fmt function for data templates
```

The `@fmt` wrapper applies interpolation directly from the current scope. The
`fmt` pipeline function applies interpolation using the piped data's fields.
Both use identical `%(...)` syntax inside the template string.

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

## Block Level Operators

Inside function bodies and blocks, `!` operators handle local bindings,
dispatch, and control flow.

`!let` creates a local binding. It does not use `=`, which is reserved for
field assignment. The binding captures the value of the following expression.
That variable can be accessed using the defined name inside the function
block and all its nested block definitions.

```comp
!let base ($.price * $.quantity)
!let cutoff (datetime.now - 1[week])
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

`!defer` prevents automatic invocation of a callable expression, capturing it
as a reference instead. See [Functions](function.md) for invocation rules.

`!fail` raises a failure value that fast-forwards through the call chain until
caught by a `|?` or `??` operator. See the Failures and Fallbacks section above.

## Function Level Operators

Blocks used in function definition statements can define additional
operators to control the signature and metadata about the function.
Common examples are `!params`, `!block`, and `!default`. Further details
are in the [Functions](function.md) design document.

## Wrappers

The `@` prefix attaches a wrapper to any statement. Wrappers control how the
statement executes — they can modify results, retry on failure, collect multiple
values, or apply template interpolation. Wrappers work on function definitions,
inline expressions, and string literals alike.

```comp
!pure tree-insert ~tree @update (...)  // merge result onto input
| map @update {name = ($.name | upper)} // inline wrapper on expression
@fmt"hello %(name)"                    // string template wrapper
```

See [Functions](function.md) for wrapper semantics, the wrapper protocol, and
how to define custom wrappers.
