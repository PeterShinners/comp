# Basic Types

*Comprehensive specification of Comp's core numbers, strings, and booleans*

## Overview

This document details the core data types provided by the Comp language and
their implementation behavior. It covers the unified number system, string
templates and formatting, boolean operations, the unit system for
domain-specific constraints.

Comp also defines tags, which work as both basic values and shapes.

## Builtin Data Types

There are a handful of types defined by the language. The most common will be
`num` for numberic values, and `str` for strings of text.

Each of the types comes with a defined shape to represent it. Most of these also
provide an importable module from the standard library with additional functions
and definitions to manipulate these values.

* **String** - `~str` Array of utf8 characters
* **Number** - `~num` Number with infinite precision, not restricted to hardware
  accuracy or limitations
* **Boolean** - `~bool` Primitive true or false value

There are a handful of more specialized types, which contain separate documents
to describe their usage and implementation.

* **Buffer** - `~buffer` Container for binary, mutable data 
* **Handle** - `~handle` handle for interacting with resources

The builtin types are not considered structures. They do not contain fields or
iterable values. They cannot be directly converted from one type into another
without using functions. These builtin types are quite featureful, and can
be used to combine into more complex data types through structures.


### Definitions

A Comp module can create several other types of definitions that are used by the
language, but not representable as values or data. The syntax understands where
these types of lookups are needed and will use specially formatted references to
their names, or allowing them to be referenced from other modules.

* **Shape** a schema definition that looks like a structure
* **Module** used to access definitions from external sources
* **Block** an unexecuted stricture functions can invoke dynamically

### Structure Basics

Any plain, standalone value can be automatically converted into a structure
with that single value as an untyped field. This is what happens when invoking
a function on a simple value.

```comp
42             ; Scalar number
{x=1.0 y=2.0}  ; Named field structure
{10 20 30}     ; Unnamed field structure (array-like)
```

Structures are collections of values, including other structures. The values in
the structure can have an optionally assigned field name. The values are
ordered, and can be iterated or referenced by position in the structure.

The language allows the definition of shapes, which act like a schema for a
structure. This can define fields that belong to a structure, along with
optional default values, typing information, and documentation.

Any structure that has the required fields and positional values can be
considered compatible with a defined shape. Every function defines a required
shape, which allows any compatible structure to be used to call that function.

## Booleans

Booleans are the simplest builtin type. They can only represent one of two
possible tag values, `#true` and `#false`. The leading hash on these symbols
defines them as tag references.

Any comparison operator will result in one of these boolean values. Booleans
have a defined shape, `~bool` which can be used in shape definitions.

Booleans are a builtin type that can only represent two values representing true
or false. Other types cannot be converted to booleans.

Other types cannot automatically be converted into booleans. Attempting to morph
a string or number into a boolean will not work. 

### Boolean Operators

There are several operators in the language only for boolean types. The
operators for numbers cannot be used on booleans.

* `&&` logical _and_, when both values are #true
* `||` logical _or_, when either values is #true
* `!!` negation, switch a boolean to the opposite state

These logical  operators will "short circuit" while evaluating statements, which
means once a single value is found that defines the results, it will stop
processing additional statements.

## Numbers

The number type is a unified implementation that combines the behavior of the
various numerical values defined in other languages

* Unlimited size. There is no maximum value for a number, positive or negative.
  Once integer values exceed the capacity of hardware computation there will be
  a performance penalty, but the developer never needs to worry about overflows.
* Accurate precision. The fractional values are handled in a way that provides
  reliable and accurate precision without the unintentional errors and rounding
  of hardware fractional values. Repeating fractional values do not lose
  accuracy.
* Extendable restrictions. The language allows extending a number's type with
  Units to define restrictions that ensure they can safely be used with hardware
  numberic values.

Numbers have a shape, `~num` which can be used in shape definitions. There is
also a `num` module in the standard library with more mathematic operators and
converters.

Number shapes can also be combined with units, which helps define limits and
interactions between multiple number values.

**Key Properties**:
* No integer division truncation: `10 / 3` always returns `3.333...`
* No integer overflow: large numbers remain exact
* Arbitrary precision decimal support
* Consistent mathematical behavior across all operations
* Does not support special "infinity" and "nan" values by default

### Number Literals

Number values can be defined as literal values in the code. They use a
traditional syntax seen in other languages and data formats.
* An optional zero and letter prefix can define different bases for the number.
    The default is base 10, but `0x` hex, `0o` octal, and `0b` binary are all
    supported.
* A leading `-` negative or `+` positive can define positive or negative values,
  although positive is implied.
* Contain any number of digits, allowing a single period as decimal for base 10
  values.
* Can be interspersed with undercores which are ignored in parsing but can be
  used as a visual separators
* Can end with a scientific notation with a positive or negative "e" value.

```comp
12.3
15+e3
0b0110_1000
0o644
-.7
```

### Mathematical Operators

The language defines traditional operators for numbers. These allow numbers to
be combined in a mathematical notation. 

These operators are exclusively for number types, they cannot be used with
strings, booleans, or other values.

```comp
a + b       ; Addition
a - b       ; Subtraction  
a * b       ; Multiplication
a / b       ; Division (always returns fractional result)
a % b       ; Modulo
a ** b      ; Exponentiation
- a         ; Negative
```

**No Operator Overloading**: Other types use explicit method calls:
```comp
; Strings use methods, not operators
text1 -> :str:concat text2
path1 -> :path:join path2
list1 -> :list:append list2
```

### Illegal Numbers

Mathematical operations can generate special values. These are standard
definitions used in other hardware and languages to represent results like
"infinity". By default these values cannot be assigned to fields with a number
shape. The math module defines tags for these constants and a shape that can be
unioned with numbers for values that should allow these.

The language defines several specialied tags to define these values
* `#math#nan` The "not a number" value
* `#math#inf` Infinity value
* `#math#ninf` Negative infinity value

The `~math~inf` shape includes all three of these tags. By combining this with
numbers you can create a shape that combines these values together,
`~num|~math~inf`

## Strings

A string is an immutable sequence of UTF-8 encoded characters. There are no
operators like `+` or `*` to modify or create new string values. There is a
robust standard `str` module that defines many common and advanced string
editing and evaluation.

Strings can only represent valid and allowable UTF-8 encoded characters. For
managing binary data, the `buffer` must be used.

All string values can be used as a template for formatting. The string is parsed
for special `${}` tokens with values inside the braces. Invoking a string will
apply the formatting. 

### String Literals

Strings literals must be defined with the `"` double quotation marks. The single
quotation marks have a different meaning in Comp.

Triple quotations can also be used to create multiline string literals. This
also becomes a convenient way to create literals that also have quotations marks
in the text. Whitespace inside the multiline string literals is preserved as it
appears. But remember the whitespace outside the quotes is optional and use as
desired. This should allow positioning the opening quotes wherever is most
convenient.

**Design Philosophy**: No operators for strings - use explicit functions and
templates instead:

```comp
$name = "Peter"
$projects = 
"""
Pygame
Comp
"""

; No string concatenation operator
text1 + text2           ; ERROR: operators reserved for numbers

; Use explicit methods or templates
{text1, text2} -> :str:concat
{text1, text2} -> "${}${}"        ; Template concatenation
{"=" 40} -> :str:repeat       ; Repetition via functions
```

### Templates

The string templates will convert values to strings using generic formatting
rules. There is no way to invoke functions or apply shapes to the values inside
the template syntax. Those changes should be pipelined to the structure the
template is invoked on. For example, no `"Hello, ${name->:str:uppercase}"`

The `${}` tokens in the string template can use several values to resovle values
from the incoming structure. These rules follow the principals of Python's
string formatting lookups.

**1. Positional Interpolation**:
```comp
template = "Hello ${} and ${}!"
{"World", "Pete"} -> template    ; "Hello World and Pete!"

; Order matches template placeholders
{user.first_name, user.last_name} -> "Name: ${} ${}"
```

**2. Explicit Index Interpolation**:
```comp
template = "${#2} ${#0} ${#1}"   ; Explicit position references
{"A", "B", "C"} -> template      ; "C A B"

; Zero-indexed positioning
data = {"first", "second", "third"}
data -> "Third: ${#2}, First: ${#0}"   ; "Third: third, First: first"
```

**3. Named Field Interpolation**:
```comp
template = "${name} is ${age} years old"
{name="Alice", age=30} -> template    ; "Alice is 30 years old"

; Works with any structure
user -> "Hello ${name}, your role is ${role}"
```

**Mixing Rules** (Python-compatible):
```comp
; Valid: positional + named
{name="Alice", "guest"} -> "Hello ${name}, you are a ${}"

; Invalid: positional + explicit index
{"A", "B"} -> "${#0} and ${}"  ; ERROR: cannot mix modes

; Valid: explicit index + named  
{name="Alice", "A", "B"} -> "${name} sees ${#0} and ${#1}"
```

### String Formatters

Comp allows attaching functions to any value as an invokable attachment. All
strings default to using a basic formatting function that can be defined in the
current context. Each string can be attached to a different function to apply
templates in different ways. This is commonly used to provide language specific
escaping or quoting rules to the string template.

The `^` caret operator attach a function to a any type of value. The language
defines rules to determine how the attachment survives various data
transformations. (Tags cannot have an attached invoke)

```comp
html_template = "<h1>${title}</h1><p>${content}</p>"^:html:safe
sql_template = "SELECT * FROM users WHERE id = ${id}"^:sql:escape
```

When used with string literals this provides a hint to developer tools about how
to highlight or annotate the string contents.

These formatters are regular functions and they can be invoked directly without
attaching them to strings.

### String Operations

The core library privides a rich set of string operations in the `:str`
namespace.

```comp

; Standard string operations
text -> :length                    ; Get length
text -> :str:trim                  ; Remove whitespace
text -> :str:uppercase             ; Convert case
{text ","} -> :str:split           ; Split on delimiter
{text "old" "new"} -> :str:replace ; Replace substring
{"ERROR: " message} -> :str:cat    ; Short Unix-style concatenation
```

**String Processing Patterns**:
```comp
; Preprocessing pattern for complex formatting
!func :format_financial ~{amount, date} = {
    amount = amount -> {:num:commify "USD"} -> :num:currency
    date = {date "MMM DD"} -> :date:format
}

transactions
  => :format_financial
  =? {"Transaction: ${amount} on ${date}"}
  ..> "\n" -> :str:join
```

## Additional Plans

### Future Constraint System

Reserved syntax for compile-time constraints. These rules would come from pure
functions, and probably need access to some level of AST or parsed data to allow
the variety of syntaxes used in various languages and examples.

```comp
; Planned constraint syntax
~num|min=1|max=100                    ; Numeric constraints
~str|len>5|matches="^[A-Z]"          ; String constraints  
~User|age>=18|verified=#true            ; Complex constraints
```


### Context-Controlled Behavior

Rules and behavior for managing numbers and string formatting will be able to be
controlled through the incoming field namespace, which includes `!mod` and
`!ctx` where this behavior can be changed across parts of a codebase.

These are initial examples. The known list of settings will be defined when the
implementation is ready.

```comp
$ctx.num.precision = 28
$ctx.num.rounding = math.half_up
$ctx.num.epsilon = 1e-9
$ctx.num.int = math.round
$ctx.fmt.commas = #true
$ctx.fmt.locale = "en-US"
```
