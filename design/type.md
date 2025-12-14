# Core Types

Comp provides several fundamental, simple types designed to be reliable building
blocks. These numbers, strings, and tags are not structures themselves. They
have no fields, but they do have their own extensible type system and are
strictly typed themselves.

- Numbers offer huge precision, avoiding integer overflow and precision loss.
- Strings handle text with integrated templating.
- Booleans represent concrete logical values that do not become or act like
  other types.

These simple types automatically promote to single-element structures when used
in pipelines, maintaining Comp's uniform data model without mental overhead.
Each type has a corresponding shape for specifications (`~num`, `~str`, `~bool`)
and standard library module for advanced operations.

Comp also provides several other types to represent special objects in the
language.

- Shapes are like simple structures that define a schema for structures
- Blocks are deferred structures generated from an input
- Functions are just blocked assigned to a namespace
- Tags are predefined hierarchical enumerations that can also be external handles.

The type system embodies principles that prevent common programming
frustrations:

- **No implicit conversion**: Types never automatically convert—prevents those
  "wait, why is this a string now?" moments
- **Unlimited precision**: Numbers maintain exactness without overflow or
  rounding gotchas
- **Total ordering**: Comparisons always succeed with deterministic results—no
  more "cannot compare X and Y" errors

These principles create a type system that is both simple and powerful, avoiding
the complexity and pitfalls of elaborate type hierarchies or automatic
conversions.

## Number Type

Numbers in Comp are not restricted to hardware representations and limitations.
Comp code does not need to be concerned over integer overflow, overpoint
precision. Numbers maintain exact precision when working with huge integers and
precise decimals.

```comp
-- Unlimited range and precision
huge = 123456789012345678901234567890
precise = 1.123456789012345678901234567890
fraction = 10 / 3  -- Exact: 3.333... (repeating)

-- No integer truncation
result = 7 / 2  -- Exactly 3.5, not 3
third = 1 / 3  -- Maintains precision as fraction

-- Significant digits preserved
measurement = 2.50
doubled = measurement * 2  -- 5.00 (preserves precision)

-- Scientific notation
small = 1.5e-50  -- Very small and exact
large = 2.5e50  -- Very large and still exact
```

### Number Literals

Number literals support decimal notation, alternative bases, and scientific
notation. All numbers maintain arbitrary precision and exact representation.

### Decimal Numbers

Decimal numbers use standard base-10 notation with optional decimal points,
signs, and readability underscores:

```comp
-- Basic integers and decimals
whole = 42
negative = -17
decimal = 3.14159
negative-decimal = -2.5

-- Zero representations
zero = 0
zero-decimal = 0.0
negative-zero = -0

-- Leading and trailing decimal points
leading = .5  -- Same as 0.5
trailing = 5.  -- Same as 5.0

-- Underscores for readability (ignored during parsing)
large = 1_000_000  -- One million
precise = 3.141_592_653  -- Pi with grouped digits
mixed = 1_234.567_89  -- Underscores in both parts
```

### Scientific Notation

Scientific notation uses `e` or `E` to specify powers of ten:

```comp
-- Basic scientific notation
large = 1e6  -- 1,000,000
small = 1e-6  -- 0.000001
avogadro = 6.022e23  -- Avogadro's number

-- Decimal with exponents
precise = 1.23e-4  -- 0.000123
negative = -2.5e2  -- -250.0
mixed-signs = -1.5e-3  -- -0.0015

-- Case insensitive exponent
upper = 1E6  -- Same as 1e6
lower = 1e6  -- Standard form
```

### Alternative Number Bases

Binary, octal, and hexadecimal literals use standard prefixes:

```comp
-- Binary (base 2) - prefix 0b or 0B
binary = 0b1010  -- Decimal 10
binary-long =   -- With underscores
binary-upper = 0B1111  -- Capital B prefix

-- Octal (base 8) - prefix 0o or 0O  
octal = 0o755  -- Decimal 493
octal-zero = 0o0  -- Zero
octal-upper = 0O644  -- Capital O prefix

-- Hexadecimal (base 16) - prefix 0x or 0X
hex = 0xff  -- Decimal 255
hex-mixed = 0xDeadBeef  -- Mixed case digits
hex-underscores =   -- With underscores
hex-upper = 0X1A2B  -- Capital X prefix
```

Alternative base numbers follow these rules:

- Prefixes are case-insensitive (`0b`, `0B`, `0o`, `0O`, `0x`, `0X`)
- Hex digits (`a-f`) are case-insensitive
- Underscores are allowed anywhere after the prefix for readability
- No decimal points or scientific notation in alternative bases
- Result is always converted to exact decimal representation

### Mathematical Operators

Arithmetic operators work exclusively with numbers, providing standard
mathematical operations:

```comp
-- Basic arithmetic
sum = a + b
difference = a - b
subtract = a +- b  -- Explicit subtraction (disambiguates from kebab-case)
product = a * b
quotient = a / b  -- Exact division, never truncates

-- Unary operators
negative = -value
positive = +value  -- Rarely needed but available

-- Order of operations follows mathematic precedence
result = 2 + 3 * 4  -- 14, not 20
```

The language operators do not support "floor division" or "integer division" as
seen on other languages. Those are done with provided library functions.

The language does not currently have any syntax for "in-place" updates or
increment operators. These seem useful, but are a secondary priority that will
wait for other parts of the language to settle.

### Special Numeric Values

Mathematical operations can produce special values that require explicit
handling:

```comp
-- Special values as tags
not-a-number = 0 /   -- Produces num.nan)
positive-inf = 1 /   -- Produces num.inf  
negative-inf = -1 /   -- Produces num.ninf

-- These are not regular numbers
num(nan)  -- FAILS - not a regular number
value = num.inf  -- Can be stored and passed

-- Shapes for handling special values
maybe-infinite = ~(num | num.inf | num.ninf)
numeric-result = ~(num | num.nan | num.inf | num.ninf)

-- Testing for special values
if(val == num.nan) (
    implementation()
)
```

## String Type

Strings are immutable sequences of UTF-8 text. They cannot be modified after
creation - operations create new strings.

String literals are created with text between double quotes. The language also
supports multiline strings using triple quote characters.

There are no operators for use with strings. Code relies on formatting calls and
a library of string related functions.

```comp
greeting = "hello"  -- String "hello"
name = "Alice" -- String "Alice"

-- Quoted strings for special cases
let with-spaces = "Hello, World!"
let with-quotes = "She said \"Hi\""
let empty = ""

-- Multi-line strings with triple quotes
message = """
    This is a multi-line string.
    It preserves formatting and line breaks.
    "Quotes" work naturally here.
"""

-- No string operators for concatenation
"hello" + " world"  -- ERROR - no + for strings
"ab" * 3  -- ERROR - no * for strings

-- Use templates or functions instead
concat("hello" "world")
(hello world) |format("$() $()")  -- Template formatting
```

### String Operations

String manipulation uses library functions rather than operators:

```comp
import.str = ("core/str" std)

-- Common operations
text |length()  -- Character count
text |upper()  -- Convert to uppercase
text |lower()  -- Convert to lowercase
text |trim()  -- Remove whitespace
-- Splitting and joining
("a b c") |split()  -- Returns ("a" "b" "c")
("a" "b" "c") |join("-")  -- Returns "a-b-c"

-- Pattern matching
email |match("^[^@]+@[^@]+$")  -- Regex matching
text |contains(search)  -- Substring check
text |replace(old new)  -- Substitution
```

## Comparison Operators

Comparison operators work across all types with deterministic, total ordering.
They never fail - any two values can be compared, with consistent results based
on type-specific rules.

### Equality Comparisons

Equality (`==` `!=`) tests structural equivalence:

```comp
-- Numeric equality
5 == 5.0  -- true - same numeric value
1/3 == 0.333...  -- true - exact fraction comparison

-- String equality
"hello" == "hello"  -- true
"Hello" == "hello"  -- false - case sensitive

-- Structural equality (auto-wrapping)
5 == (5)  -- true - scalar wraps to structure
a == (a)  -- true - scalar wraps to structure

-- Cross-type equality
5 == "five"  -- false - different types
true == 1  -- false - different types
```

## Ordering Comparisons

Ordering (`<`, `>`, `<=`, `>=`) provides total order across all values:

```comp
-- Type priority ordering (always consistent)
() < false < true < 0 < a < (field=1)

-- Within-type ordering
10 < 20  -- Numeric comparison
"apple" < "banana"  -- Lexicographic comparison  
false < true  -- Boolean ordering

-- Cross-type ordering is defined
5 < hello  -- true - numbers before strings
true < 100  -- true - booleans before numbers
() < 0  -- true - empty before everything

-- Complex structure ordering
(a=1 b=2) < (a=1 b=3  -- Compares fields alphabetically
(x=1) < (x=1 y=2)  -- Subset is less than superset

-- Binary template operator
template = "Hello, $(name)!"
result = format(template name="Alice  -- Hello, Alice!"

## Type Conversion

Comp avoids automatic type conversion, requiring explicit operations to convert
between types. This prevents subtle bugs from implicit coercions while keeping
conversions straightforward.

```comp
-- String to number conversion
number = 42 |parse-num  -- Returns 42
invalid = abc |parse-num  -- Fails

-- Number to string conversion  
text = 42 |format  -- Returns "42"
formatted = 3.14159 |format()  -- Returns "3.14"
bool = false |to-bool  -- Returns false (special case)
```

## Boolean Type

The language provides several tags, including the builtin boolean types. These
are simply defined tags of `bool.true` and `bool.false`. They can be referenced
as `true` or `false` in most contexts.

Values are not converted to booleans automatically. They are only the result of
comparison operators and any functions that result in the boolean literals.

Function and field names representing booleans are incouraged to use a naming
with a leading prefix like `is-` or `has-`.

Operators like `&&` and `||` perform boolean **and** and **or** logic to combine
booleans. The `!!` **not** operator switches a boolean value. These operators do
not work on any other types. These operators short circuit evaluation.

Many types have a library of functions that can generate booleans. The
comparison operators like `==` and `>` are also often used to create new boolean
values.

```comp
-- Boolean literals are tags
(
    validated = true
    enabled = false
)

-- Comparison operators return booleans
let is-big = x > 5  -- Returns true or false
let is-alice = name == Alice  -- Explicit comparison

"text" | is-empty  -- Boolean True if string has no characters

-- Logical operators (short-circuiting)
-- Design note: All logical operators use double-character syntax
-- for consistency and visual symmetry: &&, ||, !!
a && b || !!c  -- AND - true when both true

-- Short-circuit behavior
false && (|expensive-check)  -- Never calls expensive-check
true || (|expensive-check)  -- Never calls expensive-check

-- Boolean operators only work with booleans
5 && 10  -- ERROR - not booleans
!!empty  -- ERROR - can't negate string
```

## Tags

Tags are named constants that serve as both values and types. Unlike numbers or
text which carry data, tags carry identity — they represent distinct states,
categories, or markers within a program. Tags are defined in hierarchies,
allowing related concepts to be grouped together while remaining individually
addressable.

A tag's dual nature as value and type enables powerful patterns. As values, tags
can be stored in fields, passed to functions, and compared for equality. As
types, tags constrain shapes to accept only specific values from a hierarchy.
This duality replaces traditional enumerations while providing more flexibility
through hierarchical organization.

Tags are defined at module level using the tag. scope. A hierarchy is defined by
assigning a shape with child names. Leaf tags can be defined with associated
values or left empty. The hierarchy builds through dotted assignment, allowing
progressive definition across a module.

When used as a type in a shape definition, a tag reference means "any child of
this tag" — the parent tag itself is not a valid value. This mirrors how unit
families work: ~bool accepts true or false, never bool itself. A leaf tag used
as a type can only match itself, since it has no children. This makes
leaf-tag-as-type a degenerate case — valid but rarely useful since only one
value matches.

Tags can be extended by external modules independently from the initial
definition. A library might define tag.status = ~(ok error) while a consuming
module adds tag.status.error = ~(timeout validation network) to specialize error
handling. The hierarchy remains coherent across module boundaries.

```comp
-- Define a hierarchy
tag.bool = ~(true false)
tag.status = ~(ok error pending)
tag.visibility = ~(all active complete)

-- Nested hierarchies
tag.http.status = ~(
    success = ~(ok created accepted)
    error = ~(not-found forbidden server-error)
)

-- Leaf tags with associated values
tag.http.code.ok = 200
tag.http.code.created = 201
tag.http.code.not-found = 404

-- Leaf tags without values
tag.pending = ~()

-- Private tags use my.tag scope
my.tag.internal = ~(ready waiting done)

-- Use tags as values
current = http.status.success.ok
response-code = http.code.not-found

-- Retrieve associated value
value(http.code.ok)  -- 200
value(http.status.success)  -- nil (no value, has children)

-- Use tags as types in shapes
request = ~(
    method~http.method  -- any child of http.method
    status~http.status  -- any child of http.status  
    is-valid~bool  -- true or false, not bool itself
)

-- Tag matching in function dispatch
handle = :response~http.status.success (...)
handle = :response~http.status.error (...)

response |handle()  -- dispatches based on tag hierarchy
```

## Units

Units extend number and text values with type information that persists through
operations. Unlike shapes which transform data structure, units annotate what a
value represents — a number isn't just 12, it's 12 inches or 12 seconds. This
distinction enables type-safe arithmetic, automatic conversion between
compatible measurements, and domain-aware string handling.

For numbers, units typically represent measurements: lengths, durations,
temperatures, currencies. The type system prevents mixing incompatible units —
adding meters to seconds fails immediately rather than producing nonsense.
Compatible units within the same family convert automatically when needed.

For text, units mark the domain or format of string content. A SQL query, HTML
fragment, or email address carries its context through operations, enabling
proper escaping during string interpolation and helping tooling provide syntax
awareness for embedded languages.

Units are applied by calling the value with a unit tag as the argument. This
syntax reads naturally as "12 as inches" or "query as sql". Converting between
compatible units chains the same syntax, and calling with num or text strips the
unit entirely. The unit() function retrieves the unit tag from a value,
returning nil for plain numbers or text.

Units are defined as tags in the unit.num or unit.text hierarchies. Each unit
definition provides a pure conversion function that transforms values from other
compatible units. The hierarchy groups related units into families — length
contains meter, foot, inch, etc. — enabling shapes to accept any unit in a
family.

In shape definitions, unit tags serve as type annotations. A leaf unit like
meter provides a default for plain values and a conversion target. A family tag
like length requires values already have a unit in that family. Units combine
with guards and lists — the shape specifies the unit, guards constrain the
value, lists specify cardinality.

Units are separate from constraint guards and lists. These concepts can be
combined with together, see the [Shape Documentation](shape.md) for details.

```comp
-- Apply units to values
height = 12(inch)
width = 3(foot)
timeout = 30(second)
query = "SELECT * FROM users"(sql)

-- Convert between compatible units
height(foot)  -- 1 (12 inches = 1 foot)
height(meter)  -- 0.3048
timeout(minute)  -- 0.5

-- Strip units
raw = height(num)  -- 12 (plain number)
plain = query(text)  -- "SELECT * FROM users" (plain text)

-- Inspect units
unit(height)  -- inch
unit(timeout)  -- second  
unit(42)  -- nil

-- Arithmetic respects units
total = 12(inch) + 1(foot)  -- 24(inch), converts to common unit
combined = 5(meter) + 10(foot  -- result in meters

-- Incompatible units fail
mixed = 5(meter) + 3(second)  -- ERROR: incompatible units

-- Shape definitions: leaf unit provides default, converts compatible units
speed = ~(distance~meter duration~second)  
data |speed()  -- plain numbers become meters/seconds

-- Shape definitions: family requires unit already present
generic-speed = ~(distance~length duration~time)
data |generic-speed()  -- fails if values lack units

-- Units combine with guards and lists
coordinates = ~length[min=0]{3}  -- 3 non-negative length values
queries = ~sql[non-empty]{1,}  -- 1+ non-empty SQL strings
safe-timeout = ~second[positive max=300]  -- positive seconds, max 5 minutes
```
