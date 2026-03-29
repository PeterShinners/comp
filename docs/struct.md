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
The `|` pipe operator is not valid inside `{}` — use `()` to scope any pipeline
used as a field value.

```comp
user = {name="Alice" age=30}
coords = {10 20 30}
mixed = {x=5 10 y=15}
empty = {}
processed = {
    name = (login | uppercase)
    id = (raw-id | validate | format)
    simple = 42
}
```

Field access uses dot notation. Positional fields use `#` with an index.
String field names use double quotes. Computed field names use single quotes.

```comp
user.name                       // named field
coords.#0                       // first field positionally
record."Full Name"              // string field name
data.'(field-name | uppercase)' // computed field name
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
!shape branch ~(tree|nil) = nil
```

The `~` operator is central to the type system. It appears in shape definitions,
in function input types (`!pure total ~cart`), in field type annotations
(`name~text`), and in type union syntax (`~text|nil`). It always means "has
this shape" or "matches this type." Union types use `|` directly after `~`
without requiring parentheses when the meaning is unambiguous:
`~text|nil`, `~num|text|nil`.

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