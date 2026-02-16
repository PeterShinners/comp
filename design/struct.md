# Structures and Shapes

Structures are the backbone of Comp. They are immutable collections that unify
arrays, dictionaries, and records into a single concept. A struct can contain
any mix of named and positional fields, accessed by name or position. Fields are
always ordered. Every piece of data in Comp is either a simple type (number,
text, boolean, tag) or a structure containing other values.

Immutability is fundamental, structures cannot be modified after creation.
Operations that appear to change data actually produce new structures with
shared internals, similar to how Python handles strings.

## Structure Literals

Structure literals are created with `{}` braces. Named fields use `=` for
assignment. Positional fields are simply listed. Whitespace separates fields.

```comp
user = {name="Alice" age=30}
coords = {10 20 30}
mixed = {x=5 10 y=15}
empty = {}
```

Field access uses dot notation. Positional fields use `#` with an index.
String field names use double quotes. Computed field names use single quotes.

```comp
user.name                       // named field
coords.#0                       // first field positionally
record."Full Name"              // string field name
data.'field-name | uppercase'   // computed field name
users.#0.name                   // chained access
```

## Shapes

Shapes define structural types, they are simultaneously a schema, a validator,
and a constructor. Where other languages split these roles across dataclasses,
pydantic models, and type hints, Comp shapes handle all three. A shape
definition is also a callable: passing data to a shape validates and converts it.

Shapes are defined at module level with `!shape` using the `~` prefix on a
struct definition. Each field can specify a name, a type constraint, and a
default value.

```comp
!shape item ~{name~text price~num quantity~num=1}
!shape cart ~{items~item{} discount~num=0}
!shape point ~{x~num=0 y~num=0}
!shape branch ~tree|nil = nil
```

The `~` operator is central to the type system. It appears in shape definitions,
in function input types (`!pure total ~cart`), in field type annotations
(`name~text`), and in type union syntax (`~tree|nil`). It always means "has this
shape" or "matches this type."

### Optional Fields and Defaults

Optional fields use union types with `nil` and provide defaults. Fields without
defaults are required, missing them causes a build-time or morphing error.

```comp
!shape config ~{
    host~text = "localhost"
    port~num = 8080
    timeout~num|nil = nil
    verbose~bool = false
}
```

### Shape Morphing

When data moves through function calls and shape constructors, it is
automatically morphed to match the target shape. Morphing follows a multi-phase
process: named fields match first, then handle and tag fields, then positional
fields fill remaining slots, and finally defaults apply for anything missing.

Any value that can be successfully morphed to a shape can generate a matching
score. This allows determining the most specific match from a set of possible
shapes to any value. This is used internally for function dispatch and the `!on`
operator. Named matches beat positional, specific types beat generic types
(`~num` beats `~any`), and deeper tag hierarchies beat shallower ones. Order is
the final tiebreaker when scores are equal.

```comp
!shape point-2d ~{x~num y~num}
!shape point-3d ~{x~num y~num z~num}

{x=5 y=10 z=15} | render       // dispatches to 3d overload
{x=5 y=10} | render            // dispatches to 2d overload
```

## Tags

Tags are named constants that serve as both values and types. They represent
distinct states, categories, or markers within a program. Tags are defined in
hierarchies at module level, allowing related concepts to be grouped while
remaining individually usable.

```comp
!tag visibility {all active complete}
!tag http-status {
    success = {ok created accepted}
    error = {not-found forbidden server-error}
}
!tag http-status.offline
```

A tag's dual nature as value and type enables powerful patterns. As values,
tags can be stored in fields, passed to functions, and compared. As types, tags
constrain shapes to accept only values from a specific hierarchy. When used as a
type, a parent tag means "any child of this tag", the parent itself is not a
valid value. `~bool` accepts `true` or `false`, never `bool` itself.

Tags are the foundation of Comp's dispatch system. Function overloading,
`!on` branching, and the `<>` comparison operator all work through tag matching.
The boolean values `true` and `false` are simply predefined tags under the
`bool` hierarchy. The stream control values `done`, `skip`, and `pass` are
similarly just tags.

Tag hierarchies can be extended by external modules independently from the
initial definition. A library might define `!tag status {ok error}` while a
consuming module adds `!tag status {timeout validation}` for more specific
error handling.

## Guards and Constraints

Shapes can carry additional constraints beyond their base type. Guards validate
that values meet specific requirements during morphing. They appear in square
brackets after a type and accept any pure function as a validator.

```comp
!shape uint8 ~num[integer min=0 max=255]
!shape unix-name ~text[ascii size={1 32} match="^[a-z_][a-z0-9_-]*$"]
```

Collection size constraints use `{}` with regex-inspired syntax: `{3}` for
exactly three, `{1,5}` for one to five, `{2,}` for two or more.

```comp
!shape rgb ~uint8{3}
!shape path-segments ~text[non-empty]{1,}
!shape sprite ~{position~num{2} color~rgb layers~image{1,4}}
```

Guards validate during morphing but don't persist on values, a number that
passes `[min=0]` is still just a number. This is distinct from units, which
attach to values and persist through operations.

## Wrappers

The `@` prefix on a block or expression attaches a wrapper that controls how
the result is interpreted. Wrappers are higher-order functions, they receive
the input, the wrapped block as a callable, and the parameters, and decide the
orchestration. This is fundamentally different from piping through a function;
the wrapper controls whether and how the inner block executes.

```comp
@update {name = ($.name | upper)}   // merge result onto input
@flat {($.left | values) {$.value} ($.right | values)}  // concatenate results
@fmt"hello %(name)"                // template interpolation
```

`@update` runs the block and merges the resulting fields onto the original
input. `@flat` collects multiple expressions and concatenates them into a single
sequence. `@fmt` activates template interpolation on a string. Libraries can
define custom wrappers, `@retry[times=3]`, `@transact[scene]`,
`@cache[ttl=60]`, without any special language support. The wrapper protocol
is a standard function signature.

Wrappers appear on function definitions to control the function's behavior for
all callers, or inline on individual expressions:

```comp
// Function-level: all calls to tree-insert merge results onto input
!pure tree-insert ~tree @update (...)

// Inline: just this one map applies update semantics
| map @update {name = ($.name | upper)}
```

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

## Units

Units extend number and text values with persistent type information. A number
isn't just `12`, it's `12[inch]` or `12[second]`. The type system prevents
mixing incompatible units, and compatible units within the same family convert
automatically.

Units are defined as tags in the `unit.num` or `unit.text` hierarchies.

```comp
height = 12[inch]
width = 3[foot]
timeout = 30[second]

total = 12[inch] + 1[foot]     // 24[inch], auto-converts
height[meter]                  // 0.3048
mixed = 5[meter] + 3[second]   // ERROR, incompatible units
```

For text, units mark domain or format, a SQL query or HTML fragment carries its
context through operations, enabling proper escaping during interpolation. Units
are separate from guards: guards validate during morphing and don't persist,
while units attach to values and flow through operations.
