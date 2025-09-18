# Core Types

*Fundamental data types in Comp: numbers, strings, and booleans*

## Overview

Comp provides three fundamental scalar types that serve as building blocks for all data. Numbers offer unlimited precision for exact computation. Strings handle text with integrated templating. Booleans represent logical values through the tag system. These scalar types automatically promote to single-element structures when used in pipelines, maintaining Comp's uniform data model.

Each type has a corresponding shape for type specifications (`~num`, `~str`, `~bool`) and standard library module for advanced operations. The type system is closed - no user-defined scalar types exist, ensuring consistent behavior throughout the language.

## Boolean Type

Booleans are the simplest type, represented by two built-in tags: `#true` and `#false`. They cannot be created from other types through automatic conversion - explicit functions must be used when converting values to booleans. This prevents ambiguity about truthiness that plague other languages.

```comp
; Boolean literals are tags
valid = #true
enabled = #false

; Comparison operators return booleans
result = x > 5              ; Returns #true or #false
equal = name == "Alice"      ; Explicit comparison

; No automatic conversions
value = 1
if_value = value            ; ERROR - not a boolean
if_valid = value > 0        ; Correct - explicit comparison
```

### Boolean Operators

Boolean operations use distinct operators that short-circuit evaluation:

```comp
; Logical operators (short-circuiting)
a && b              ; AND - true when both true
a || b              ; OR - true when either true
!!a                 ; NOT - negates boolean

; Short-circuit behavior
#false && :expensive_check     ; Never calls expensive_check
#true || :expensive_check      ; Never calls expensive_check

; Boolean operators only work with booleans
5 && 10            ; ERROR - not booleans
!!""               ; ERROR - can't negate string
```

### Boolean Context

Control flow functions interpret values for conditional logic. While only `#false` and empty structures `{}` are considered false, explicit boolean values or comparisons are preferred for clarity:

```comp
; Control flow interpretation
:if .{#false} .{..} .{..}      ; False branch
:if .{{}} .{..} .{..}          ; False branch (empty)
:if .{0} .{..} .{..}           ; True branch (non-empty)
:if .{"} .{..} .{..}           ; True branch (non-empty)

; Preferred explicit style
:if .{count > 0} .{..} .{..}
:when .{user.active == #true} .{..}
```

## Number Type

Numbers in Comp provide unlimited precision and range, eliminating common numeric pitfalls. Whether representing integers, decimals, or huge values, numbers maintain exact precision without overflow or rounding errors. The implementation uses efficient representations internally while presenting consistent behavior to programmers.

```comp
; Unlimited range and precision
huge = 123456789012345678901234567890
precise = 1.123456789012345678901234567890
fraction = 10 / 3              ; Exact: 3.333... (repeating)

; No integer truncation
result = 7 / 2                 ; Exactly 3.5, not 3
third = 1 / 3                  ; Maintains precision as fraction

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
with_underscores = 1_000_000

; Other bases
binary = 0b1010_1010          ; Base 2
octal = 0o755                 ; Base 8  
hexadecimal = 0xFF_FF         ; Base 16

; Scientific notation
scientific = 6.022e23
small = 1e-9
negative_exp = 3.14e-10
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
not_a_number = 0 / 0           ; Produces #num#nan
positive_inf = 1 / 0           ; Produces #num#inf  
negative_inf = -1 / 0          ; Produces #num#ninf

; These are not regular numbers
#num#nan ~ num                 ; FAILS - not a regular number
value = #num#inf               ; Can be stored and passed

; Shapes for handling special values
!shape ~MaybeInfinite = ~num | #num#inf | #num#ninf
!shape ~NumericResult = ~num | #num#nan | #num#inf | #num#ninf

; Testing for special values
:if .{result == #num#nan} .{
    "Calculation undefined" -> :log
}
```

## String Type

Strings are immutable sequences of UTF-8 text. They cannot be modified after creation - operations create new strings. Every string supports template formatting through the `%` operator, providing a unified approach to string manipulation without concatenation operators.

```comp
; String literals with double quotes
simple = "Hello, World!"
with_quotes = "She said \"Hi\""
empty = ""

; Multi-line strings with triple quotes
message = """
    This is a multi-line string.
    It preserves formatting and line breaks.
    "Quotes" work naturally here.
"""

; No string operators for concatenation
"Hello" + "World"              ; ERROR - no + for strings
"ab" * 3                       ; ERROR - no * for strings

; Use templates or functions instead
"Hello" -> :str/concat "World"
{"Hello " name} % "${} ${}"    ; Template formatting
```

### Template Formatting

The `%` operator applies template formatting to strings. Templates use `${}` placeholders that are filled from the provided structure. The operator can be used as a prefix for statement seeding or as a binary operator.

```comp
; Template syntax with % operator
template = "Hello, ${name}!"
result = template % {name="Alice"}     ; "Hello, Alice!"

; Prefix form with seeding
!func :greet ~{name} = {
    greeting = "Welcome, ${name}" % ..  ; Apply to input
}

; Positional placeholders
"${} + ${} = ${}" % {2, 3, 5}         ; "2 + 3 = 5"

; Named and positional mixing
{name="Bob", "Developer"} % "Hi ${name}, you are a ${}"

; Index-based placeholders
"${#1} before ${#0}" % {"first", "second"}  ; "second before first"
```

Template formatting follows Python-style rules:
- Positional `${}` matches unnamed fields in order
- Named `${field}` matches named fields
- Indexed `${#n}` references specific positions
- Cannot mix positional and indexed in same template

### String Operations

String manipulation uses library functions rather than operators:

```comp
!import str/ = std "core/str"

; Common operations
text -> :length                      ; Character count
text -> :str/upper                   ; Convert to uppercase
text -> :str/lower                   ; Convert to lowercase
text -> :str/trim                    ; Remove whitespace

; Splitting and joining
"a,b,c" -> :str/split ","            ; Returns ["a", "b", "c"]
["a", "b", "c"] -> :str/join "-"     ; Returns "a-b-c"

; Pattern matching
email -> :str/match "^[^@]+@[^@]+$"  ; Regex matching
text -> :str/contains "search"       ; Substring check
text -> :str/replace "old" "new"     ; Substitution
```

### String Units

String units attach to strings using `#` followed by a tag, providing semantic meaning and controlling template behavior. Units can validate formats, apply transformations, and ensure proper escaping in templates.

```comp
; String with unit tag
email = "user@example.com"#email
query = "SELECT * FROM users WHERE id = ${id}"#sql
markup = "<h1>${title}</h1>"#html

; Units affect template formatting
user_id = "'; DROP TABLE users; --"
safe_query = "SELECT * FROM users WHERE id = ${user_id}"#sql % {user_id}
; SQL unit ensures proper escaping

; Unit validation
invalid = "not-an-email"#email       ; Fails validation
normalized = "USER@EXAMPLE.COM"#email ; Becomes lowercase

; Custom string units
!tag #url ~str = {
    validate = :url/parse
    normalize = :url/normalize
    escape = :url/encode
}
```

## Number Units

Units provide semantic typing and automatic conversion for numeric values. They attach to numbers using `#` notation, creating typed values that maintain their meaning through operations. The standard library provides comprehensive units through the `unit/` module.

```comp
!import unit/ = std "core/unit"

; Basic unit attachment
distance = 5#length#meter
duration = 30#time#second
temp = 20#temperature#celsius

; Automatic conversion in operations
total = 5#length#meter + 10#length#foot    ; Result in meters
speed = 100#length#km / 1#time#hour        ; Compound unit

; Explicit conversion
meters = distance ~ num#length#meter       ; 5
feet = distance ~ num#length#foot          ; ~16.404
kelvin = temp ~ num#temperature#kelvin     ; 293.15
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
"hello" == "hello"          ; true
"Hello" == "hello"          ; false - case sensitive

; Structural equality (auto-wrapping)
5 == {5}                    ; true - scalar wraps to structure
"a" == {"a"}               ; true - scalar wraps to structure

; Cross-type equality
5 == "5"                   ; false - different types
#true == 1                 ; false - different types
```

### Ordering Comparisons

Ordering (`<`, `>`, `<=`, `>=`) provides total order across all values:

```comp
; Type priority ordering (always consistent)
{} < #false < #true < 0 < "a" < {field=1}

; Within-type ordering
10 < 20                    ; Numeric comparison
"apple" < "banana"         ; Lexicographic comparison  
#false < #true             ; Boolean ordering

; Cross-type ordering is defined
5 < "hello"                ; true - numbers before strings
#true < 100                ; true - booleans before numbers
{} < 0                     ; true - empty before everything

; Complex structure ordering
{a=1, b=2} < {a=1, b=3}    ; Compares fields alphabetically
{x=1} < {x=1, y=2}         ; Subset is less than superset
```

The ordering rules ensure:
- Comparisons never fail or throw errors
- Results are always deterministic
- Sorting any collection always works
- Cross-type comparisons are predictable

## Type Conversion

Comp avoids automatic type conversion, requiring explicit operations to convert between types. This prevents subtle bugs from implicit coercions while keeping conversions straightforward.

```comp
; String to number conversion
number = "42" -> :str/parse_num        ; Returns 42
invalid = "abc" -> :str/parse_num      ; Fails

; Number to string conversion
text = 42 -> :num/format              ; Returns "42"
formatted = 3.14159 -> :num/format 2  ; Returns "3.14"

; Boolean conversions (explicit)
bool = 1 -> :num/to_bool              ; Returns #true (non-zero)
bool = "" -> :str/to_bool             ; Returns #false (empty)
bool = "false" -> :str/to_bool        ; Returns #false (special case)

; Template formatting converts automatically
"Value: ${}" % {42}                   ; Number to string
"Count: ${}" % {#true}                ; Boolean to string
```

## Design Principles

The type system embodies several core principles:

- **No implicit conversion**: Types never automatically convert, preventing subtle bugs
- **Unlimited precision**: Numbers maintain exactness without overflow or rounding
- **Template unification**: All strings support formatting through the `%` operator
- **Total ordering**: Comparisons always succeed with deterministic results
- **Semantic units**: Units provide meaning and safety for primitive values
- **Closed type system**: Only built-in scalar types, ensuring consistency

These principles create a type system that is both simple and powerful. The three scalar types provide everything needed for real-world programming while avoiding the complexity and pitfalls of elaborate type hierarchies or automatic conversions.