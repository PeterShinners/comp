# Core Types

Comp provides several fundamental, simple types designed to be reliable building
blocks. These numbers, strings, and booleans are not structures themselves. They
have no fields, but they do have their own extensible type system and are
strictly typed themselves.

- Numbers offer huge precision, avoiding integer overflow and precision
  loss. 
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
- Functions are operations that take a fixed shape to create new data
- Blocks are deferred structures, like lightweight functions that do not need
  arguments.
- Tags are predefined enumerations that define a hierharchy. Tags are used as
  both values and as shapes.
- Handles allow access to external resources like files, network, other
  languages, or anything outside control of the Comp language.
- Id is a special value that has no value but defines uniqueness among objects

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

## Boolean Type

Booleans are the simplest type, represented by two built-in tags: `#true` and
`#false`. Conditionals in Comp require booleans, which are not automatically
inferred from other value types. 

Both of these are children tags of their parent `#bool`, which can be used in
shape definitions.

Field and function names that are used to represent booleans will typeically use
a trailing `?` in their token name, like `valid?` or `enabled?`.

Operators like `&&` and `||` perform boolean **and** and **or** logic to combine
booleans. The `!!` **not** operator switches a boolean value. These operators do
not work on any other types. These operators short circuit evaluation.

Many types have a library of functions that can generate booleans. The
comparison operators like `==` and `>` are also often used to create new boolean
values.

```comp
; Boolean literals are tags
{
    valid? = #true
    enabled? = #false
}

; Comparison operators return booleans
let result? = x > 5  ; Returns #true or #false
let equal? = name == Alice  ; Explicit comparison

"text" | empty?  ; Boolean True if string has no characters

; Logical operators (short-circuiting)
; Design note: All logical operators use double-character syntax
; for consistency and visual symmetry: &&, ||, !!
a && b || !!c  ; AND - true when both true

; Short-circuit behavior
#false && (|expensive-check)     ; Never calls expensive-check
#true || (|expensive-check)      ; Never calls expensive-check

; Boolean operators only work with booleans
5 && 10            ; ERROR - not booleans
!!empty            ; ERROR - can't negate string
```


## Number Type

Numbers in Comp are not restricted to hardware representations and limitations.
Comp code does not need to be concerned over integer overflow, overpoint
precision. Numbers maintain exact precision when working with huge integers and
precise decimals.

```comp
; Unlimited range and precision
huge = 123456789012345678901234567890
precise = 1.123456789012345678901234567890
fraction = 10 / 3              ; Exact: 3.333... (repeating)

; No integer truncation
result = 7 / 2                 ; Exactly 3.5, not 3
third = 1 / 3                  ; Maintains precision as fraction

; Significant digits preserved
measurement = 2.50
doubled = measurement * 2      ; 5.00 (preserves precision)

; Scientific notation
small = 1.5e-50              ; Very small and exact
large = 2.5e50               ; Very large and still exact
```

### Number Literals

Number literals support decimal notation, alternative bases, and scientific
notation. All numbers maintain arbitrary precision and exact representation.

#### Decimal Numbers

Decimal numbers use standard base-10 notation with optional decimal points,
signs, and readability underscores:

```comp
; Basic integers and decimals
whole = 42
negative = -17
decimal = 3.14159
negative-decimal = -2.5

; Zero representations
zero = 0
zero-decimal = 0.0
negative-zero = -0

; Leading and trailing decimal points
leading = .5             ; Same as 0.5
trailing = 5.            ; Same as 5.0

; Underscores for readability (ignored during parsing)
large = 1_000_000        ; One million
precise = 3.141_592_653  ; Pi with grouped digits
mixed = 1_234.567_89     ; Underscores in both parts
```

#### Scientific Notation

Scientific notation uses `e` or `E` to specify powers of ten:

```comp
; Basic scientific notation
large = 1e6              ; 1,000,000
small = 1e-6             ; 0.000001
avogadro = 6.022e23      ; Avogadro's number

; Decimal with exponents
precise = 1.23e-4        ; 0.000123
negative = -2.5e2        ; -250.0
mixed-signs = -1.5e-3    ; -0.0015

; Case insensitive exponent
upper = 1E6              ; Same as 1e6
lower = 1e6              ; Standard form
```

#### Alternative Number Bases

Binary, octal, and hexadecimal literals use standard prefixes:

```comp
; Binary (base 2) - prefix 0b or 0B
binary = 0b1010          ; Decimal 10
binary-long = 0b1010_1010 ; With underscores
binary-upper = 0B1111    ; Capital B prefix

; Octal (base 8) - prefix 0o or 0O  
octal = 0o755            ; Decimal 493
octal-zero = 0o0         ; Zero
octal-upper = 0O644      ; Capital O prefix

; Hexadecimal (base 16) - prefix 0x or 0X
hex = 0xff               ; Decimal 255
hex-mixed = 0xDeadBeef   ; Mixed case digits
hex-underscores = 0xFF_FF ; With underscores
hex-upper = 0X1A2B       ; Capital X prefix
```

Alternative base numbers follow these rules:
- Prefixes are case-insensitive (`0b`, `0B`, `0o`, `0O`, `0x`, `0X`)
- Hex digits (`a-f`) are case-insensitive
- Underscores are allowed anywhere after the prefix for readability
- No decimal points or scientific notation in alternative bases
- Result is always converted to exact decimal representation

#### Special Numeric Values

Mathematical operations can produce special values that are represented as
tagged numbers:

```comp
; Special values from mathematical operations
positive-infinity = 1 / 0        ; Produces #inf.num
negative-infinity = -1 / 0       ; Produces #ninf.num  
not-a-number = 0 / 0            ; Produces #nan.num

; Direct special value literals (advanced)
inf-literal = #inf.num          ; Positive infinity
ninf-literal = #ninf.num        ; Negative infinity
nan-literal = #nan.num          ; Not a number
```

Special values are not regular numbers and require explicit handling:
- They cannot be used with the `~num` shape matcher
- Arithmetic with special values follows IEEE 754-like rules
- Use specific shape matchers like `~maybe-infinite` for functions that accept
  them

### Mathematical Operators

Arithmetic operators work exclusively with numbers, providing standard
mathematical operations:

```comp
; Basic arithmetic
sum = a + b
difference = a - b
subtract = a +- b       ; Explicit subtraction (disambiguates from kebab-case)
product = a * b
quotient = a / b         ; Exact division, never truncates

; Unary operators
negative = -value
positive = +value       ; Rarely needed but available

; Order of operations follows mathematic precedence
result = 2 + 3 * 4      ; 14, not 20
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
; Special values as tags
not-a-number = 0 / 0           ; Produces #nan.num
positive-inf = 1 / 0           ; Produces #inf.num  
negative-inf = -1 / 0          ; Produces #ninf.num

; These are not regular numbers
#nan.num ~num                  ; FAILS - not a regular number
value = #inf.num               ; Can be stored and passed

; Shapes for handling special values
!shape ~maybe-infinite = ~num | #inf.num | #ninf.num
!shape ~numeric-result = ~num | #nan.num | #inf.num | #ninf.num

; Testing for special values
($in |if {$in == #nan.num} {
    (Calculation undefined |log)
})
```

## String Type

Strings are immutable sequences of UTF-8 text. They cannot be modified after
creation - operations create new strings. 

String literals are created with text between double quotes. The language also
supports multiline strings using triple quote characters.

There are no operators for use with strings. Code relies on formatting calls and
a library of string related functions.

```comp
greeting = "hello"  ; String "hello"
name = "Alice" ; String "Alice"

; Quoted strings for special cases
let with-spaces = "Hello, World!"
let with-quotes = "She said \"Hi\""
let empty = ""

; Multi-line strings with triple quotes
message = """
    This is a multi-line string.
    It preserves formatting and line breaks.
    "Quotes" work naturally here.
"""

; No string operators for concatenation
"hello" +  " world"  ; ERROR - no + for strings
"ab" * 3  ; ERROR - no * for strings

; Use templates or functions instead
(hello |concat/str world)
{hello world} % %{} %{}    ; Template formatting
```

### Token literals

Comp uses a special structure literal wrapped in square brackets `[]`. Any
tokens and text in these structures are converted into positional values inside
a struct. This allows `[one two]` as a shorthand for `{"one" "two"}`

### Template Formatting

Still in progess; formatting generally involves strings with a special `${}`
referencing syntax inside.

Template formatting follows intuitive Python-style rules. Positional
placeholders fill in order, named placeholders match field names, and the
pipeline operator `|%` lets you apply templates in data flows naturally.

### String Operations

String manipulation uses library functions rather than operators:

```comp
!import str std "core/str"

; Common operations
text | length ()           ; Character count
text | upper/str ()        ; Convert to uppercase
text | lower/str ()        ; Convert to lowercase
text | trim/str ()         ; Remove whitespace
; Splitting and joining
[a b c] | split/str ()     ; Returns [a b c]
[a b c] | join/str ("-")   ; Returns "a-b-c"

; Pattern matching
(email | match/str "^[^@]+@[^@]+$") ; Regex matching
(text | contains/str search)        ; Substring check
(text | replace/str old new)        ; Substitution
```

## Comparison Operators

Comparison operators work across all types with deterministic, total ordering.
They never fail - any two values can be compared, with consistent results based
on type-specific rules.

### Equality Comparisons

Equality (`==` `!=`) tests structural equivalence:

```comp
; Numeric equality
5 == 5.0                    ; true - same numeric value
1/3 == 0.333...            ; true - exact fraction comparison

; String equality
"hello" == "hello"              ; true
"Hello" == "hello"              ; false - case sensitive

; Structural equality (auto-wrapping)
5 == {5}                    ; true - scalar wraps to structure
a == {a}                    ; true - scalar wraps to structure

; Cross-type equality
5 == "five"                 ; false - different types
#true == 1                  ; false - different types
```

### Ordering Comparisons

Ordering (`<`, `>`, `<=`, `>=`) provides total order across all values:

```comp
; Type priority ordering (always consistent)
{} < #false < #true < 0 < a < {field=1}

; Within-type ordering
10 < 20               ; Numeric comparison
"apple" < "banana"    ; Lexicographic comparison  
#false < #true        ; Boolean ordering

; Cross-type ordering is defined
5 < hello             ; true - numbers before strings
#true < 100           ; true - booleans before numbers
{} < 0                ; true - empty before everything

; Complex structure ordering
{a=1 b=2} < {a=1 b=3} ; Compares fields alphabetically
{x=1} < {x=1 y=2}     ; Subset is less than superset

; Binary template operator
template = "Hello, %{name}!"
result = {name="Alice"} % template     ; "Hello, Alice!"

; Template string prefix for immediate expansion
name = "Alice"
result = %"Hello, %{name}!"           ; "Hello, Alice!"

; Positional placeholders
%"%{} + %{} = %{}" % {2 3 5}         ; "2 + 3 = 5"

; Named and positional mixing
%"Hi %{name}, you are a %{}" % {name="Bob" "Developer"}

; Index-based placeholders
%"%{#1} before %{#0}" % {"first" "second"}  ; "second before first"

; Pipeline template operator
{greeting="World"} |% "Hello, %{greeting}!"  ; "Hello, World!"
```

## Type Conversion

Comp avoids automatic type conversion, requiring explicit operations to convert
between types. This prevents subtle bugs from implicit coercions while keeping
conversions straightforward.

```comp
; String to number conversion
number = 42 | parse-num/str ()        ; Returns 42
invalid = abc | parse-num/str ()      ; Fails

; Number to string conversion  
text = 42 |format/num ()              ; Returns "42"
formatted = 3.14159 |format/num 2 ()  ; Returns "3.14"

; Boolean conversions (explicit)
bool = 1 | to-bool/num ()              ; Returns #true (non-zero)
bool = empty | to-bool/str ()          ; Returns #false (empty)
bool = false | to-bool/str ()          ; Returns #false (special case)

; Template formatting converts automatically
Value: %{} % {42}                     ; Number to string
Count: %{} % {#true}                  ; Boolean to string
```

## Units

Units are specially defined tags that can be attached to number and string
values. These provide additional behaviors for the operators.

For numbers these usually used to attach measurements or units to values. For
example, values can be given different time units and compared and combined
logically.

For strings the units are used to assist formatting templates. Different
contexts for text can use different escaping for substituted values. A unit on
text literals can also assist developer tools to provide more context and syntax
awareness for the string contents.

```comp
email = "user@example.com"#email
markup = "<h1>%{title}</h1>"#html
safe-query = "SELECT * FROM users WHERE id = %{user-id}#sql" % {user-id}

total = 5#meter + 10#foot          ; Result in meters
speed = 100#kilometer / 1#hour     ; Compound unit

; Explicit conversion
meters = distance ~num#meter      ; 5000
```

Units follow algebraic rules: addition/subtraction require compatible units,
multiplication/division create compound units, and incompatible operations fail
immediately. For detailed information about unit hierarchies, compound units,
validation, and custom unit definitions, see [Units](unit.md).

