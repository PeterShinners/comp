# Core Types

*Fundamental data types in Comp: numbers, strings, and booleans*

## Overview

Comp provides three fundamental, simple types designed to be reliable building blocks. These numbers, strings, and booleans are not structures themselves. They have no fields, but they do have their own extensible type system and are strictly typed themselves.

Numbers offer unlimited precision, avoiding integer overflow and precision loss. Strings handle text with integrated templating. Booleans represent concrete logical values that do not become or act like other types.

These simple types automatically promote to single-element structures when used in pipelines, maintaining Comp's uniform data model without mental overhead. Each type has a corresponding shape for specifications (`~num`, `~str`, `~bool`) and standard library module for advanced operations.

The type system embodies principles that prevent common programming frustrations:

- **No implicit conversion**: Types never automatically convert—prevents those "wait, why is this a string now?" moments
- **Unlimited precision**: Numbers maintain exactness without overflow or rounding gotchas
- **Template unification**: All strings support formatting through the `%` operator
- **Total ordering**: Comparisons always succeed with deterministic results—no more "cannot compare X and Y" errors
- **Semantic units**: Units provide meaning and safety for primitive values
- **Closed type system**: Only three built-in types, everything else is structures
- **Concrete types**: Values carry their own type information rather than relying on inference

These principles create a type system that is both simple and powerful, avoiding the complexity and pitfalls of elaborate type hierarchies or sneaky automatic conversions. Comp uses concrete types where values intrinsically know what they are, rather than inferring types from context—see [Syntax and Style Guide](syntax.md) for details on how this affects the entire language. For information about how these types integrate with structure operations, see [Structures, Spreads, and Lazy Evaluation](structure.md).

## Boolean Type

Booleans are the simplest type, represented by two built-in tags: `#true` and `#false`. They eliminate the "is 0 true or false?" confusion that exists in many languages—there's no automatic conversion from other types. Want to check if something is truthy? Use an explicit comparison.

```comp
; Boolean literals are tags
valid = #true
enabled = #false

; Comparison operators return booleans
result = x > 5              ; Returns #true or #false
equal = name == Alice        ; Explicit comparison

; No automatic conversions
value = 1
if-value = value            ; ERROR - not a boolean
if-valid = value > 0        ; Correct - explicit comparison
```

### Boolean Operators

Boolean operations use distinct operators that short-circuit evaluation:

```comp
; Logical operators (short-circuiting)
; Design note: All logical operators use double-character syntax
; for consistency and visual symmetry: &&, ||, !!
a && b              ; AND - true when both true
a || b              ; OR - true when either true
!!a                 ; NOT - negates boolean

; Short-circuit behavior
#false && (|expensive-check)     ; Never calls expensive-check
#true || (|expensive-check)      ; Never calls expensive-check

; Boolean operators only work with booleans
5 && 10            ; ERROR - not booleans
!!empty            ; ERROR - can't negate string
```

### Boolean Context

Control flow functions interpret values for conditional logic. While only `#false` and empty structures `{}` are considered false, explicit boolean values or comparisons are preferred for clarity:

```comp
; Control flow interpretation
($in |if {#false} true-branch false-branch)      ; False branch
($in |if {#false} :{true-branch} :{false-branch}) ; Explicit block syntax
($in |if {{}} true-branch false-branch)          ; False branch (empty)
($in |if {0} true-branch false-branch)           ; True branch (non-empty)
($in |if {empty} true-branch false-branch)       ; True branch (non-empty)

; Preferred explicit style with simple values
($in |if {count > 0} "has-items" "no-items")
($in |if {count > 0} has-items no-items)
($in |when {user.active? == #true} process)
```

## Number Type

Numbers in Comp eliminate the numeric headaches that plague other languages. No integer overflow. No floating-point precision loss. No "why did my calculation get rounded?" moments. Numbers maintain exact precision whether you're working with huge integers or precise decimals.

The implementation follows Python's decimal.Decimal semantics, including preservation of significant digits through operations. This means your calculations stay accurate, and your financial software won't mysteriously lose pennies.

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
small = 1.5e-100              ; Very small but exact
large = 2.5e100               ; Very large but exact
```

### Number Literals

Number literals support decimal notation, alternative bases, and scientific notation. All numbers maintain arbitrary precision and exact representation.

#### Decimal Numbers

Decimal numbers use standard base-10 notation with optional decimal points, signs, and readability underscores:

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
- Hex digits `a-f` are case-insensitive
- Underscores are allowed anywhere after the prefix for readability
- No decimal points or scientific notation in alternative bases
- Result is always converted to exact decimal representation

#### Special Numeric Values

Mathematical operations can produce special values that are represented as tagged numbers:

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
- Use specific shape matchers like `~maybe-infinite` for functions that accept them

### Mathematical Operators

Arithmetic operators work exclusively with numbers, providing standard mathematical operations:

```comp
; Basic arithmetic
sum = a + b
difference = a - b
subtract = a +- b       ; Explicit subtraction (disambiguates from kebab-case)
product = a * b
quotient = a / b         ; Exact division, never truncates
remainder = a % b        ; Modulo operation
power = a ** b          ; Exponentiation

; Unary operators
negative = -value
positive = +value       ; Rarely needed but available

; Order of operations follows mathematics
result = 2 + 3 * 4      ; 14, not 20
```

The language does not support "floor division" or "integer division" as seen
on other languages.

The language does not currently have any syntax for "in-place" updates
or increment operators. These seem useful, but are a secondary priority
that will wait for other parts of the language to settle.

### Special Numeric Values

Mathematical operations can produce special values that require explicit handling:

```comp
; Special values as tags
not-a-number = 0 / 0           ; Produces #nan.num
positive-inf = 1 / 0           ; Produces #inf.num  
negative-inf = -1 / 0          ; Produces #ninf.num

; These are not regular numbers
#nan.num ~num                 ; FAILS - not a regular number
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

Strings are immutable sequences of UTF-8 text. They cannot be modified after creation - operations create new strings. Tokens without special prefixes are treated as string literals, dramatically reducing quotation noise in common cases.

```comp
; Unquoted tokens are string literals
greeting = hello           ; String "hello"
name = Alice              ; String "Alice"
status = active           ; String "status"

; Quoted strings for special cases
with-spaces = "Hello, World!"
with-quotes = "She said \"Hi\""
empty = ""

; Multi-line strings with triple quotes
message = """
    This is a multi-line string.
    It preserves formatting and line breaks.
    "Quotes" work naturally here.
"""

; No string operators for concatenation
hello + world              ; ERROR - no + for strings
ab * 3                    ; ERROR - no * for strings

; Use templates or functions instead
(hello |concat/str world)
{hello world} % %{} %{}    ; Template formatting
```

### Template Formatting

The `%` operator provides powerful template formatting that actually makes sense. Use `%{}` placeholders and fill them from structures—no more string concatenation headaches or format string ceremony.

Template formatting follows intuitive Python-style rules. Positional placeholders fill in order, named placeholders match field names, and the pipeline operator `|%` lets you apply templates in data flows naturally.

### String Operations

String manipulation uses library functions rather than operators:

```comp
!import /str = std "core/str"

; Common operations
(text |length)                      ; Character count
(text |upper/str)                   ; Convert to uppercase
(text |lower/str)                   ; Convert to lowercase
(text |trim/str)                    ; Remove whitespace

; Splitting and joining
(a,b,c |split/str ,)               ; Returns [a b c]
([a b c] |join/str -)              ; Returns "a-b-c"

; Pattern matching
(email |match/str "^[^@]+@[^@]+$") ; Regex matching
(text |contains/str search)        ; Substring check
(text |replace/str old new)        ; Substitution
```

### String Units

String units attach to strings using tag notation, providing semantic meaning and controlling template behavior. Units can validate formats, apply transformations, and ensure proper escaping in templates. For comprehensive information about the tag system underlying units, see [Tag System](tag.md).

```comp
; String with unit tag
email = "user$var.example.com"#email
query = SELECT * FROM users WHERE id = %{id}#sql
markup = <h1>%{title}</h1>#html

; Units affect template formatting
user-id = '; DROP TABLE users; --
safe-query = SELECT * FROM users WHERE id = %{user-id}#sql % {user-id}
; SQL unit ensures proper escaping

; Unit validation
invalid = not-an-email#email       ; Fails validation
normalized = USER@EXAMPLE.COM#email ; Becomes lowercase

; Custom string units
!tag #url ~str = {
    validate = |parse/url
    normalize = |normalize/url
    escape = |encode/url
}
```

## Number Units

Units provide semantic typing and automatic conversion for numeric values. They attach to numbers using tag notation, creating typed values that maintain their meaning through operations. Units are implemented as tag hierarchies with conversion rules.

```comp
; Units as tags
distance = 5#kilometer
duration = 30#second
temp = 20#celsius

; Automatic conversion in operations
total = 5#meter + 10#foot          ; Result in meters
speed = 100#kilometer / 1#hour     ; Compound unit

; Explicit conversion
meters = distance ~num#meter      ; 5000
feet = distance ~num#foot         ; ~16.404
kelvin = temp ~num#kelvin         ; 293.15
```

Units follow algebraic rules:
- Addition/subtraction require compatible units
- First operand's unit determines result unit  
- Multiplication/division create compound units
- Incompatible operations fail immediately

## Comparison Operators

Comparison operators work across all types with deterministic, total ordering. They never fail - any two values can be compared, with consistent results based on type-specific rules.

### Equality Comparisons

Equality (`==`, `!=`) tests structural equivalence:

```comp
; Numeric equality
5 == 5.0                    ; true - same numeric value
1/3 == 0.333...            ; true - exact fraction comparison

; String equality
hello == hello              ; true
Hello == hello              ; false - case sensitive

; Structural equality (auto-wrapping)
5 == {5}                    ; true - scalar wraps to structure
a == {a}                    ; true - scalar wraps to structure

; Cross-type equality
5 == five                   ; false - different types
#true == 1                  ; false - different types
```

### Ordering Comparisons

Ordering (`<`, `>`, `<=`, `>=`) provides total order across all values:

```comp
; Type priority ordering (always consistent)
{} < #false < #true < 0 < a < {field=1}

; Within-type ordering
10 < 20                     ; Numeric comparison
apple < banana              ; Lexicographic comparison  
#false < #true              ; Boolean ordering

; Cross-type ordering is defined
5 < hello                   ; true - numbers before strings
#true < 100                 ; true - booleans before numbers
{} < 0                      ; true - empty before everything

; Complex structure ordering
{a=1 b=2} < {a=1 b=3}       ; Compares fields alphabetically
{x=1} < {x=1 y=2}           ; Subset is less than superset

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

Comp avoids automatic type conversion, requiring explicit operations to convert between types. This prevents subtle bugs from implicit coercions while keeping conversions straightforward.

```comp
; String to number conversion
number = (42 |parse-num/str)        ; Returns 42
invalid = (abc |parse-num/str)      ; Fails

; Number to string conversion  
text = (42 |format/num)              ; Returns "42"
formatted = (3.14159 |format/num 2)  ; Returns "3.14"

; Boolean conversions (explicit)
bool = (1 |to-bool/num)              ; Returns #true (non-zero)
bool = (empty |to-bool/str)          ; Returns #false (empty)
bool = (false |to-bool/str)          ; Returns #false (special case)

; Template formatting converts automatically
Value: %{} % {42}                     ; Number to string
Count: %{} % {#true}                  ; Boolean to string
```
