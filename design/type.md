# Core Types

*Fundamental data types in Comp: numbers, strings, and booleans*

## Overview

Comp provides three fundamental scalar types that serve as building blocks for all data. Numbers offer unlimited precision for exact computation. Strings handle text with integrated templating. Booleans represent logical values through the tag system. These scalar types automatically promote to single-element structures when used in pipelines, maintaining Comp's uniform data model.

Each type has a corresponding shape for type specifications (`~num`, `~str`, `~bool`) and standard library module for advanced operations. The type system is closed - no user-defined scalar types exist, ensuring consistent behavior throughout the language. For information about how these types integrate with structure operations, see [Structures, Spreads, and Lazy Evaluation](structure.md).

## Boolean Type

Booleans are the simplest type, represented by two built-in tags: `#true` and `#false`. They cannot be created from other types through automatic conversion - explicit functions must be used when converting values to booleans. This prevents ambiguity about truthiness that plagues other languages.

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
($in |if {{}} true-branch false-branch)          ; False branch (empty)
($in |if {0} true-branch false-branch)           ; True branch (non-empty)
($in |if {empty} true-branch false-branch)       ; True branch (non-empty)

; Preferred explicit style
($in |if {count > 0} has-items no-items)
($in |when {user.active? == #true} process)
```

## Number Type

Numbers in Comp provide unlimited precision and range, eliminating common numeric pitfalls. Whether representing integers, decimals, or huge values, numbers maintain exact precision without overflow or rounding errors. The implementation uses efficient representations internally while presenting consistent behavior to programmers.

Numbers follow Python's decimal.Decimal semantics, including preservation of significant digits through operations.

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

Number literals support multiple bases and formatting options:

```comp
; Decimal (base 10)
decimal = 42
negative = -17.5
with-underscores = 1_000_000

; Other bases
binary = 0b1010_1010          ; Base 2
octal = 0o755                 ; Base 8  
hexadecimal = 0xFF_FF         ; Base 16

; Scientific notation
scientific = 6.022e23
small = 1e-9
negative-exp = 3.14e-10
```

### Mathematical Operators

Arithmetic operators work exclusively with numbers, providing standard mathematical operations:

```comp
; Basic arithmetic
sum = a + b
difference = a - b
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
status = active           ; String "active"

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
{hello world} % ${} ${}    ; Template formatting
```

### Template Formatting

The `%` operator applies template formatting to strings. Templates use `${}` placeholders that are filled from the provided structure. The operator can be used for complex string building without concatenation.

```comp
; Template syntax with % operator
template = Hello, ${name}!
result = template % {name=Alice}     ; "Hello, Alice!"

; Positional placeholders
${} + ${} = ${} % {2 3 5}         ; "2 + 3 = 5"

; Named and positional mixing
{name=Bob Developer} % Hi ${name}, you are a ${}

; Index-based placeholders
${#1} before ${#0} % {first second}  ; "second before first"
```

Template formatting follows Python-style rules:
- Positional `${}` matches unnamed fields in order
- Named `${field}` matches named fields
- Indexed `${#n}` references specific positions
- Cannot mix positional and indexed in same template

### String Operations

String manipulation uses library functions rather than operators:

```comp
!import str = std "core/str"

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
email = "user@example.com"#email
query = SELECT * FROM users WHERE id = ${id}#sql
markup = <h1>${title}</h1>#html

; Units affect template formatting
user-id = '; DROP TABLE users; --
safe-query = SELECT * FROM users WHERE id = ${user-id}#sql % {user-id}
; SQL unit ensures proper escaping

; Unit validation
invalid = not-an-email#email       ; Fails validation
normalized = USER@EXAMPLE.COM#email ; Becomes lowercase

; Custom string units
!tag url ~str = {
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
Value: ${} % {42}                     ; Number to string
Count: ${} % {#true}                  ; Boolean to string
```

## Design Principles

The type system embodies several core principles:

- **No implicit conversion**: Types never automatically convert, preventing subtle bugs
- **Unlimited precision**: Numbers maintain exactness without overflow or rounding
- **Template unification**: All strings support formatting through the `%` operator
- **Total ordering**: Comparisons always succeed with deterministic results
- **Semantic units**: Units provide meaning and safety for primitive values
- **Closed type system**: Only built-in scalar types, ensuring consistency

These principles create a type system that is both simple and powerful. The three scalar types provide everything needed for real-world programming while avoiding the complexity and pitfalls of elaborate type hierarchies or automatic conversions. For information about how these types work with shape validation and morphing, see [Shapes, Units, and Type System](shape.md).