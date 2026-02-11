# Core Types

Comp provides a small set of fundamental types as the reliable building
blocks. Numbers offer unlimited precision with no overflow or truncation.
Text handles strings with integrated template formatting. Booleans are
predefined tags — `true` and `false` — with no special status in the type
system. Tags provide hierarchical enumerations. Structures contain everything
else.

The type system follows three rules that eliminate entire categories of bugs.
**No implicit conversion** — types never automatically change kind. Booleans
cannot be used as numbers, strings cannot silently become numbers. **Unlimited
precision** — numeric operations maintain exactness without overflow or rounding
surprises. **Total ordering** — any two values can be compared with
deterministic results, no "cannot compare" errors.

## Numbers

Numbers maintain arbitrary precision and exact representation. There is no
distinction between integers and floats at the language level — a number is a
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
is no floor division, modulo operator, power operator, or increment syntax — the
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
"hello world" | uppercase            // "HELLO WORLD"
"  padded  " | trim                  // "padded"
"a b c" | split | join["-"]          // "a-b-c"
email | match["^[^@]+@[^@]+$"]      // regex matching
"Camp" | replace["amp" "omp"]        // "Comp"
```

### Template Formatting

String interpolation uses `%(expression)` with an optional `[format]` modifier.
A bare `%` without a following `(` is a literal percent — no escaping needed in
most cases. The `%%(` sequence produces a literal `%(` for the rare case where
that's needed.

```comp
"hello %(name)"                        // interpolate from scope
"%(count)[04d] items at 100% off"     // formatted number, literal %
"price: %($ * 1.08)[.2f]"            // expression with format spec
```

Two invocation styles provide interpolation from different data sources. The
`@fmt` decorator resolves references from the current scope. The `fmt` pipeline
function resolves references from the piped data's fields.

```comp
@fmt"welcome back, %(username)"       // username from local scope
data | fmt["row %(id): %(title)"]     // id and title from data fields
```

The format specifiers inside `[]` follow Python-style conventions for numeric
formatting (`.2f`, `04d`) and can also reference Comp functions (`upper`,
`trim`) for string transformations.

## Booleans

The values `true` and `false` are predefined tags in the `bool` hierarchy. They
have no special treatment in the language — they are produced by comparison
operators and consumed by logical operators, nothing more.

```comp
is-big = x > 5
is-alice = name == "Alice"
validated = true
```

Logical operators (`and`, `or`, `not`) work exclusively with booleans and
short-circuit evaluation. Non-boolean values cannot be used in logical
expressions — there is no concept of "truthy" or "falsy."

```comp
a and b or not c
false and (expensive-check)   // never calls expensive-check
true or (expensive-check)     // never calls expensive-check
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
are ordinary tags with no special runtime behavior — they participate in
dispatch and type matching like any other tag.

## Nil

The `nil` tag represents the absence of a value. It participates in union types
(`~num|nil`) and can be matched in dispatch (`!on` with `~nil` branch). A field
can only be `nil` if its shape explicitly allows it — `~num` can never be nil,
`~num|nil` can. The compiler enforces this, preventing surprise nil values from
leaking through untyped paths.

```comp
!shape branch ~tree|nil = nil

!pure tree-insert ~nil (
    !mods value~num
    tree[value=value]
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
formatted = 3.14 | fmt["%()[.2f]"]  // "3.14"
```

## Comparison and Ordering

All comparison operators work across types with deterministic, total ordering.
Equality (`==`, `!=`) tests structural equivalence — values of different types
are never equal. Ordering (`<`, `>`, `<=`, `>=`) follows a fixed type priority:
nil, empty struct, false, true, number, text, tag, struct. Within each type,
values use their natural ordering.

The three-way comparison operator `<>` returns a tag (`~less`, `~equal`,
`~greater`) enabling dispatch over all three cases in a single `!on` expression.
This is especially useful for binary tree operations and sorted data structures.

```comp
!on (value <> $value)
~less ($left | tree-contains[value])
~greater ($right | tree-contains[value])
~equal true
```

See [Functions](function.md) for complete `!on` dispatch documentation and
[Structures](struct.md) for units that extend numbers and text with persistent
type annotations.