# Structures and Shapes

Structures are the backbone of Comp. Every function receives a structure as
input and generates a new structure as output. Even simple values like numbers
and booleans are automatically promoted into single-element structures when used
in pipelines.

Structures are immutable collections that combine the roles of arrays,
dictionaries, and records. They can contain any mix of named and unnamed fields,
accessed by name or position. Field names can be simple tokens, strings, or even
tag values.

Comp data is stored in one powerful and flexible structure type. It combines
positional and named data into a single container. It combines the use cases of
iterators, sequences, and maps into a flexible container that does more and does
it uniformly.

Even functions are defined as structures, which run in as deferred code. A
structure definition can define and reference local temporary values, which
works comfortably for both literal values and function definitions. It combines
positional and named fields interchangeably. Imagine a data structure that could
describe arguments for a Python function.

Imagine a data structure that could define the argument signature for a Python
function. Fields can have names or be defined positionally. They can also have
optional types and optional default values.

Each structure is immutable, but has rich operations that naturally create
modified and minimal clones of data. Think of the way Python handles strings,
but now apply that to everything.

There are simple data types like numbers and text. These are also immutable, and
work interchangeably with simple structures that containing single, scalar
values.

Comp uses shape values to define a schema for data. Data can be tested and
converted between compatible shapes. The language doesn't use classes or
restrictive definitions, any function can be called an compatible data. Shapes
are defined using the `~` operator on a structure and can be referenced and used
like any regular value.

The `~` is used to define the shapes, and internally applied to individual
fields to define their own shapes.. No inheritance hierarchies, no interface
implementations—just structural matching that works intuitively. The shape
schemas provide strongly typed data validation in a way that is reusable and
expressive.

A shape definition is also a callable object which is used to construct or
convert data into the defined shape.

Structure literals can be defines with two syntaxes. The traditional uses curly
brackets `()` to define individual fields. Parenthesis `()` can also be used
when assembling structures from predefined calls or data. Both can be used
interchangeably in function calls, argument definitions, or any place structures
are needed. They both produce the same structure object types, they just provide
alternative ways of getting to the same destination.

Structures are not classes. Comp has no traditional class definitions and
behaviors. There are ways to perform many similar operations that traditional
classes define, but they are done in a way that makes the data the priority, not
the code.

## Structure Definition and Field Access

Structures are created with `()` parenthesis containing field definitions.
Fields can be named or positional (unnamed). Named fields use `=` for
assignment, while unnamed fields are simply listed.

```comp
# Simple structures
user = (name="Alice" age=30)
coords = (10 20 30)
mixed = (x=5 10 y=15)

# Field access
user.name  -- Named field
coords.#0  -- First positional field (indexed)
user.#active.status  -- Tag as field name

# String and computed field names
data."Full Name" = "Alice"  -- String field name
data.'field-' ++ suffix  -- Computed field name

# Chained access
users.#0.name  -- Index then field
config."servers".#0.host  -- String field, index, then field
```

**Field access types:**

- `data.field` - Named field (token)
- `data.#0` - Positional index
- `data.'expr'` - Computed field name
- `data."string"` - String literal field name

## Literal decorators

Any structure literal (including function/block definitions) can be prefixed
with a decorator. This is a pure defined function that modifies the
interpretation of the structure literal. These are prefixed with a `|` pipe
symbol at the begining of the struct.

The libraries provide several common decorators.

- `val` - Whatever the final evaluated value in this structure becomes the
  resulting value of this literal.
- `mix` - Merge all the values and fields in this single structure
- `flat` - Sequentially order all the fields and values defined in this
  structure

```comp
(|val 1+2 three (4 5))  -- (4 5) - returns only final value
(|flat 1+2 three (4 5))  -- (3 three 4 5) - values unwrapped

(|mix (one=1 two=2) (three=3)) -- (one=1 two=2 three=3)
(|flat (one=1 two=2) (three=3)) -- (1 2 3)
```

## Assignment Operators

Assignment creates new structures - nothing is modified in place.

```comp
-- Override behavior
config = (
    port = 8080
    host = "localhost"
    timeout = 30
    log = (severity=warning ignore="http")
)
```

**Assignment targets:**

- `field = value` - Creates field in output struct
- `var.local = value` - Function-local variable
- `ctx.name = value` - Context variable

## Destructured Assignment

Extract multiple fields from a structure in a single statement:

```comp
-- Extract named fields
(name age city) = user

-- Extract with renaming
(name=username age=years) = user

-- Mix named and positional
(x y label=name) = point
-- Gets first two unnamed fields as x, y and 'label' field as name

-- Nested destructuring
(user=(name email) status) = response

-- With defaults
(port ? 8080 host ? "localhost") = config
```

## Field Deletion

Remove fields by creating new structures without them:

```comp
-- Delete operator
cleaned = mix(original temp=delete old=delete)
cleaned = original |remove-fields("temp" "old")

-- Shape morphing for filtering
public-user = ~(name~str email~str)
user = (name="Alice" email="alice@example.com" password="secret")
public = public-user(user)  -- Password removed
```

Using shapes for field filtering is idiomatic and provides type safety.

## Structure Comparison and Iteration

Structures support equality and ordering comparisons:

```comp
-- Equality - named field order doesn't matter
(x=1 y=2) == (y=2 x=1)  -- true
(1 2 3) == (1 2 3)  -- true
(x=1 2) == (2 x=1)  -- false - positional order matters

-- Ordering - lexicographic comparison
(a=1) < (a=2)  -- true
(x=1) < (x=1 y=2)  -- true
```

Standard library functions from `struct/` module enable field inspection,
filtering, and transformation:

```comp
import.struct = ("core/struct" std)

data |field-names() -- ("name" "age" "status")
data |has-field() "email"  -- true or false
data |filter:(value > 0)
data |map-fields() |upper()
```

## Shapes

Shapes define structural types for data validation and transformation. Instead
of rigid class hierarchies, shapes use structural compatibility: any data with
the right fields matches.

Shape definitions are actually functions that can be used to construct and
convert data and arguments into specific shapes.

The shape system integrates with units to provide semantic typing. Units attach
meaning to values: `5~meter` is different from `5~second`, and the type system
prevents mixing them. Together, shapes and units create compile-time validation
without runtime overhead.

Defined tags are also valid shapes. The hierarchical parent of tags can be used
as a type specification for any of its children.

## Shape Definition

Shapes are defined like structs with a `~` prefix but use a slightly different
syntax. Each field in the struct can define an optional name, an optional type,
and an optional default value. Without a name fields are considered as
positional values.

The default value can only use literal values or expressions. They cannot use
function calls of their own. (Perhaps one day pure calls will be allowed?)

```comp
point = ~(
    x~num = 0
    y~num = 0
)

point-3d = ~(
    ..~point-2d  # Inherit x, y fields
    z~num = 0  # Add z coordinate
)

user = ~(
    name~text
    email~text
    age~num = 0
    is-active~bool = true
    user-tag[]  # Array of specific tags
)

-- Shape composition through spreading
point-3d = ~(
    ..~point  -- todo, need a syntax for this?
    z~num = 0
)

-- Array constraints
config = ~(
    servers~server[1-]  -- At least one
    backups~backup[0-3]  -- Up to three
    options~text[]  -- Any number
)
```

### Named vs Positional Fields

Shape fields can be **named** (matched by name) or **positional** (matched by
position):

```comp
# Named fields
user = ~(name~text age~num)
(name="Alice" age=30) ~user  # Named match
("Alice" 30) ~user  # Positional fills named

# Positional fields
pair = (~num ~num)
(5 10) ~pair  # Matched by position

# Mixed
labeled = (~text name ~text)
("ID" name="Alice") ~labeled  # Positional then named
```

Morphing tries named matches first, then fills remaining fields by position.

### Optional Fields

Optional fields use union types with `~nil` and defaults:

```comp
user = ~(
    name~text
    email~(text | nil) = ()
    age~(num | nil) = ()
)

# Usage
user(name="Alice")
# Result: (name="Alice" email=() age=()

user(name="Bob" email="bob@example.com")
# Result: (name="Bob" email="bob@example.com" age=()
```

```comp
session = ~(
    user~text
    is-active~bool = true
    is-verified~bool = false
)
```

### Shape Morphing

Data is automatically morphed as it moves through function input and arguments.
There are different rules applied.

This is also used to determine a most specific match when functions are
overloaded with multiple implementations. A shape can score itself how
specifically it matches a piece of data.

Morph shapes allow data to match one of multiple shapes and will choose only the
most specific shape that matches and convert to that.

Morphing transforms data to match shapes through a multi-phase process:

1. **Named field matching** - Exact field names matched first
2. **Handle field matching** - Fields with matching handle types
3. **Tag field matching** - Fields with matching tag types
4. **Positional matching** - Remaining fields by position
5. **Default application** - Missing fields get defaults

**Specificity ranking:**

- Exact field matches beat partial matches
- Named fields beat positional fields
- Specific types beat generic types (`~num` > `~any`)
- Deeper tag/handle hierarchies beat shallower ones

Order doesn't matter except for ties (left-to-right tiebreaker).

### Specificity Scoring

Specificity uses a lexicographic tuple: `(named_matches, combined_depth,
positional_matches)`

- **Named matches** beat everything else
- **Depth** comes from tag/handle hierarchies (deeper = more specific)
- **Positional matches** provide final tiebreaker

```comp

-- This is a mess, what is going on here (too many syntax replacement ops?)

tag.status = ~(ok error)

generic = (  #status)
specific = (  #network.error)

(state=#network.error) ~generic | ~specific
-- Result: ~specific wins (deeper tag hierarchy)

-- Ambiguous matches cause errors:**
user = (name ~text email ~text)
group = (name ~text members ~user[])

(name="X") ~user | ~group
-- ERROR: Ambiguous - both match 50%

-- Resolve with discriminator tag
user = (  #user name ~text email ~text)
group = (  #group name ~text members ~user[])

(type=#user name="X") ~user | ~group  -- Unambiguous
```

## Guards and Lists Constraints

Shapes can be enhanced with additional constraints. Guards validate that values
meet specific requirements beyond their base type. Lists specify how many values
of a shape can appear in a sequence. Both can be combined to create precise type
definitions that are reusable throughout a module.

Guards are specified in square brackets [] after a shape. Each guard is a pure
function that validates the value. If any guard fails, the value cannot morph to
that shape. Multiple guards can be listed together and all must pass. Common
guards include numeric bounds like min and max, text constraints like non-empty
and ascii, and pattern matching with match for regular expressions.

List constraints use curly braces {} with syntax borrowed from regular
expressions. A single number specifies an exact count, two comma-separated
numbers specify a range (inclusive), and omitting a number leaves that bound
open. For example, {3} means exactly three, {1,5} means one to five, {2,} means
two or more, and {,8} means up to eight.

Any pure function can serve as a guard if it takes the appropriate type and
optionally an argument, returning a failure when the value doesn't satisfy the
constraint.

```comp
-- Define constrained types
uint8 = num[integer min=0 max=255]
unix-name = text[ascii size=(1 32) match="^[a-z_][a-z0-9_-]*$"]

-- Build on constrained types with lists
rgb = uint8{3}
path-segments = text[non-empty]{1,}

-- Use in shape definitions
sprite = ~(
    position~num{2}
    color~rgb
    layers~image{1,4}
)

-- Custom guard function
divisible-by = :val~num divisor~num pure (|val
    if(divmod(val divisor).#1 != 0) :(
        fail("$(val) is not divisible by $(divisor)")
    )
)

-- Use custom guards alongside builtins
grid-size = num[positive integer divisible-by=8]
```

Comp also defines a system called units as a way to extend number and text
values. These are separate from these constraints, and the two concepts can be
combined. See [Type Documentation](type.md) for more unit details.

Guards and lists are separate from units. Guards validate during morphing but
don't persist on values — a number that passes [min=0] is still just a number.
Units are tags that attach to numbers and text and persist through operations,
enabling dispatch and conversion between compatible measurements.

