# Core Types

Comp provides a small set of fundamental types as the reliable building
blocks. Numbers offer unlimited precision with no overflow or truncation.
Text handles strings with integrated template formatting. Booleans are
predefined tags, `true` and `false`, with no special status in the type
system. Tags provide hierarchical enumerations. Structures contain everything
else.

The type system follows three rules that eliminate entire categories of bugs.
**No implicit conversion**, types never automatically change kind. Booleans
cannot be used as numbers, strings cannot silently become numbers. **Unlimited
precision**, numeric operations maintain exactness without overflow or rounding
surprises. **Total ordering**, any two values can be compared with
deterministic results, no "cannot compare" errors.

## Numbers

Numbers maintain arbitrary precision and exact representation. There is no
distinction between integers and floats at the language level, a number is a
number. Division never truncates: `7 / 2` is exactly `3.5`, and `1 / 3`
maintains full precision as a repeating fraction. Significant digits are
preserved through operations: `2.50 * 2` produces `5.00`.

```comp
huge = 123456789012345678901234567890
precise = 1.123456789012345678901234567890
fraction = 10 / 3       // exact repeating fraction
measurement = 2.50 * 2  // 5.00, preserves precision
```

Number literals support decimal notation with optional sign, decimals, and
scientific notation. Underscores improve readability and are ignored during
parsing. Alternate bases use `0x` (hex), `0o` (octal), and `0b` (binary)
prefixes for integer values only.

```comp
large = 1_000_000
pi = 3.141_592_653
small = 1.5e-50
binary = 0b1010
hex = 0xff_25
```

Arithmetic operators (`+`, `-`, `*`, `/`) work exclusively with numbers. There
is no floor division, modulo operator, power operator, or increment syntax, the
standard library provides `divmod`, `pow`, and other mathematical functions.
Because kebab-case uses hyphens, subtraction of variables may require spaces
`a - b` or an operation like `a+-b`.

## Text

Text values are immutable UTF-8 strings. The language intentionally provides no
text operators like joining or repetition. The standard libraries provide a rich
set of templating, formatting, and collection of text manipulation functions.

```comp
greeting = "hello"
with-quotes = "she said \"hi\""
multiline = """
    This preserves formatting
    and line breaks naturally.
"""
```

String operations come from the standard library and work through pipelines:

```comp
"hello world" | uppercase         // "HELLO WORLD"
"  padded  " | trim               // "padded"
"a b c" | split | join["-"]       // "a-b-c"
email | match :"^[^@]+@[^@]+$"    // regex matching
"Camp" | replace :"amp" :"omp"    // "Comp"
```

### Template Formatting

String interpolation uses `%(expression)` with an optional `[format]` suffix.
A bare `%` without a following `(` is a literal percent, no escaping needed in
most cases. The `%%(` sequence produces a literal `%(` for the rare case where
that's needed.

```comp
"hello %(name)"                      // interpolate from scope
"%(count)[04d] items at 100% off"    // formatted number, literal %
"price: %($ * 1.08)[.2f]"            // expression with format spec
```

Two invocation styles provide interpolation from different data sources. The
`@fmt` wrapper resolves references from the current scope. The `fmt` pipeline
function resolves references from the piped data's fields.

```comp
@fmt"welcome back, %(username)"       // username from local scope
data | fmt["row %(id): %(title)"]     // id and title from data fields
```

The format specifiers inside `[]` follow Python-style conventions for numeric
formatting (`.2f`, `04d`) and can also reference Comp functions (`upper`,
`trim`) for string transformations.

### Output Styling

The default way to output text with comp is the builtin `output` function. This
will apply Comp's formatting to a simple string and write it to the configured
output stream (usually standard out).

The output function can also apply simple coloring to the output when
appropriate, and avoid it when not desired.

Colors are applied to a string using a backlash followed by letters surrounded
be dashes. Each letter applies a color or font style.

Syntax:
    \\-r-  red        \\-g-  green      \\-b-  blue       \\-y-  yellow
    \\-c-  cyan       \\-m-  magenta    \\-w-  white      \\-k-  black
    \\-s-  strong (bold/bright)         \\-d-  dim
    \\-n-  normal (reset all)

Multiple letters can be combined into one expression like `\-gb- for bold green
text. Each format code completely resets the color and style for the following
text.

This colorization is used by default for terminal outputs, and can be
controlled with the standard `$NO_COLOR` environment variable.

```comp
"Hello, \-s-World" | output

"\-s-Bold text\-n- normal"         // strong (bold)
"\-r-Red error\-n-"                // red color
"\-rs-Bold red alert\-n-"          // combined: red + strong
"\-g-Success\-n- \-d-details\-n-"  // multiple regions
```

## Booleans

The values `true` and `false` are predefined tags in the `bool` hierarchy. They
have no special treatment in the language, they are produced by comparison
operators and consumed by logical operators, nothing more.

```comp
{
  is-big = x > 5
  is-alice = name == "Alice"
  validated = true
}
```

Logical operators (`:and`, `:or`, `:not`) work exclusively with booleans and
short-circuit evaluation. Non-boolean values cannot be used in logical
expressions, there is no concept of "truthy" or "falsy."

```comp
a :and b :or :not c
false :and (expensive-check)   // never calls expensive-check
true :or (expensive-check)     // never calls expensive-check
```

## Tags

Tags are named constants that define identity rather than carry data. They
represent states, categories, and markers. Tags are defined at module level
in hierarchies using `!tag` and serve as both values and types. See
[Structures](struct.md) for full tag documentation.

```comp
!tag visibility {all active complete}
!tag bool {true false}

current = visibility.active
```

Several tags are predefined by the language: `true` and `false` for booleans,
`nil` for absence of value, and `done`, `skip`, `pass` for flow control. These
are ordinary tags with no special runtime behavior, they participate in
dispatch and type matching like any other tag.

## Nil

The `nil` tag represents the absence of a value. It participates in union types
(`~num|nil`) and can be matched in dispatch (`!on` with `~nil` branch). A field
can only be `nil` if its shape explicitly allows it, `~num` can never be nil,
`~num|nil` can. The compiler enforces this, preventing surprise nil values from
leaking through untyped paths.

```comp
!shape branch ~tree|nil = nil

!pure tree-insert ~nil (
    :param value~num
    tree :value
)
```

There is no separate `undefined` or `null` concept. `nil` is the single
representation of "no value," and it must always be explicitly allowed in the
type system.

## Type Conversion

Comp requires explicit conversion between types. The standard library provides
conversion functions that return failures for invalid input rather than
producing garbage values.

```comp
number = "42" | parse-num       // 42
invalid = "abc" | parse-num     // failure
text = 42 | fmt                 // "42"
formatted = pi | fmt :"%()[.2f]"  // "3.14"
```

## Comparison and Ordering

All comparison operators work across types with deterministic, total ordering.
Equality (`==`, `!=`) tests structural equivalence, values of different types
are never equal. Ordering (`<`, `>`, `<=`, `>=`) follows a fixed type priority:
nil, empty struct, false, true, number, text, tag, struct. Within each type,
values use their natural ordering.

The three-way comparison operator `<>` returns a tag (`~less`, `~equal`,
`~greater`) enabling dispatch over all three cases in a single `!on` expression.
This is especially useful for binary tree operations and sorted data structures.

```comp
!on (value <> $.value)
~less ($.left | tree-contains :value)
~greater ($.right | tree-contains :value)
~equal true
```

See [Functions](function.md) for complete `!on` dispatch documentation and
[Structures](struct.md) for units that extend numbers and text with persistent
type annotations.

## Units

Units extend number and text values with persistent type metadata using `[]`.
A number isn't just `12`, it's `12[inch]` or `30[second]`. A string isn't just
text, it's `"select * from users"[sql]`. Units persist through operations and
enable the type system to prevent nonsensical combinations while allowing safe
conversions within the same family.

Units are defined as tags in the `unit.num` or `unit.text` hierarchies. Each
unit family is a flat category with children representing specific units.

```comp
// Numeric units
height = 12[inch]
timeout = 30[second]
elapsed[second] + 1[minute]     // converts, produces seconds

// Text units, mark domain/format for tooling and escaping
!let query "select * from users where name = %(name)"[sql]
!let fragment "<div class='%(cls)'>%(content)</div>"[html]
!let pattern "^[a-z_][a-z0-9_-]*$"[regex]
```

Text units serve two purposes. They provide a standardized indicator for IDEs to
apply nested language highlighting inside the string. They also allow the
formatting engine to perform context-aware escaping, a value interpolated into
a `[sql]` string gets SQL-escaped, an `[html]` string gets HTML-escaped.

### Unit Conversion Rules

Converting between unit and non-unit values is always safe. Adding a unit to a
bare value attaches metadata. Stripping a unit removes it. Converting between
units in the same family requires a defined converter function. Converting
between different families fails.

```comp
load-json-number | num[seconds]   // bare to unit, always works
elapsed[seconds] | num            // unit to bare, always works
elapsed[seconds] | num[minutes]   // same family, converter exists
elapsed[seconds] | num[celsius]   // different family, fails
raw-num | num[celsius]            // bare to unit, always works
```

The escape hatch for unusual situations is always to strip the unit and reapply:
`value | num | num[celsius]`. Two explicit steps, visible in the code.

Converter functions are defined as pure functions that take a value and a target
unit tag. The dispatch system chains converters within a family automatically.

### Unit Matching and Dispatch

Units participate in shape matching with distinct score levels. When dispatch
selects an overload, unit compatibility contributes to the match quality.

Most functions should declare the unit family rather than a specific unit,
`~num[time]` rather than `~num[seconds]`, so they accept any time unit without
conversion.

The matching levels from strongest to weakest are: an exact unit match
(`5[seconds]` → `~num[seconds]`), a child tag match where the value's unit is a
child of the shape's unit tag (`5[seconds]` → `~num[time]`), a moderate match
where a bare value matches a unit shape (`5` → `~num[time]`), and a weak match
where a sibling unit could be converted (`5[minutes]` → `~num[seconds]`). Values
from a different unit family produce no match at all.

## Limits

Limits are validation constraints on types, defined with `<>` angle brackets
after the type name. Each limit is a pure function that checks whether a value
satisfies a condition during shape morphing. Limits validate but never transform
— a value either passes or the morph fails.

```comp
!shape uint8 ~num<integer min=0 max=255>
!shape positive ~num<above=0>
!shape probability ~num<min=0 max=1>
!shape unix-name ~text<ascii size={1-32} match="^[a-z_][a-z0-9_-]*$">
!shape email ~text<size={3-254} match="^[^@]+@[^@]+$">
```

Bound limits come in inclusive and exclusive variants. `min` and `max` are
inclusive, "at least" and "at most." `above` and `below` are exclusive,
"greater than" and "less than."

```comp
~num<min=0 max=255>       // 0 through 255 inclusive
~num<above=0 below=1>     // between 0 and 1, exclusive both ends
~num<above=0 max=100>     // greater than 0, up to 100 inclusive
```

Other common limits include `integer` (no fractional part), `ascii` (ASCII
characters only), `size` (length constraint on text or collections), and `match`
(regex pattern matching on text). Limits are ordinary pure functions, libraries
can define custom limits without special language support.

Limits do not affect dispatch scoring. A value matches `~num<min=0 integer>`
with the same dispatch score as `~num`. Limits validate after dispatch selects
the winning overload. This prevents fragile dispatch ordering where overlapping
limit ranges would create ambiguous matches.

Limits can be combined with units. The unit specifies what kind of value it is,
the limits specify what range is acceptable.

```comp
!shape index ~num[num.index]<min=0 integer>
!shape timeout ~num[second]<min=0>
!shape temperature ~num[celsius]<above=-273.15>
```

## Collections

Collection constraints use `*` after a type to specify how many elements are
expected. The base type defines what each element must match, and the star
defines the count requirement. Field names on elements are not regarded during
collection matching, only the count and element types matter.

```comp
~num*3             // exactly 3 numbers
~text*1+           // one or more text values
~image*0-4         // up to four images
~uint8*3           // exactly 3 uint8 values (e.g., RGB)
```

Sizing uses literal non-negative integers with `-` for ranges.

```comp
*N                 // exactly N
*N+                // N or more, no upper bound
*N-M               // N to M inclusive
*                  // zero or more (any count)
```

Both bounds must be literal integers. When a range is used, the minimum is
always required, `*-4` is not valid, write `*0-4`. A bare `*` without
any number means "zero or more," accepting any count of elements.

Collection constraints combine naturally with limits. Each suffix addresses
a different concern: the type says what, limits say how constrained, and star
says how many.

```comp
!shape rgb ~num<min=0 max=255>*3
!shape polygon ~point*3-
!shape temperature-series ~num<min=-273.15>*1+
```
