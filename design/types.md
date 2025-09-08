# Basic Types

*Comprehensive specification of Comp's core type system: numbers, strings, booleans, and tags*

## Overview

This document details the core data types provided by the Comp language and their implementation behavior. It covers the unified number system, string templates and formatting, boolean operations, the unit system for domain-specific constraints, and the hierarchical tag system for semantic typing.

**Core Types Covered:**
* **String** - Array of utf8 characters *(Included)*
* **Number** Number with infinite precision, not restricted to traditional hardware accuracy or limitations.  *(Included)*
* **Boolean** Primitive true or false value.  *(Included)*
* **Buffer** Container for binary, mutable data  *(Included)*
* **Structure** Flexible container for iteratable fields and values
* **Handle** handle for interacting with resources
* **Block** a structure in unexecuted form that can be invoked directly

The Comp language represents several other types of objects, but these
cannot be referenced or used as values directly. There are others, but 
they are detailed separately.

* **Shape** a schema definition that looks like a structure
* **Tag** is a predefined named hierarchy that works like a shape and a value *(Included)*
* **Module** used to access definitions from external sources

## Core Type System

### Universal Structure Model

The Number, String, and Boolean types are not considered structures. They
are lower level values used to build more complicated objects.

But these scalar values are freely promoted into a structure containing a
single value with no field name.

```comp
42                    // Scalar number
{x=1.0, y=2.0}        // Named field structure
{10 20 30}          // Unnamed field structure (array-like)
```

### Built-in Global Shapes

The language provides fundamental global shapes that cannot be redefined:

```comp
~string     // UTF-8 text data
~number     // Unified numeric type
~bool       // Boolean values (!true, !false)
~nil        // Empty/null value
```

### Union Types

Union types require tildes on each component:

```comp
~User|~nil                    // Optional user
~string|~number               // String or number
~Image|~css~Gradient|~color~Rgb  // Complex union with namespaced types
```

### Collection Constraints

Structures support size constraints using range syntax:

```comp
{User[1-]}      // 1 or more users
{string[3]}     // Exactly 3 strings  
{Item[0-10]}    // 0 to 10 items
{Tag[]}         // Any number of tags
```
## Number System

### Unified Number Type

A single number type combines the many hardware related number specifications
from other languages. This unified number type support infinite precision.
Fractional values are represented accurately and precise, without error.

**Key Properties**:
- No integer division truncation: `10 / 3` always returns `3.333...`
- No integer overflow: large numbers remain exact
- Arbitrary precision decimal support
- Consistent mathematical behavior across all operations

**Context-Controlled Behavior**:
```comp
$ctx.number.precision = 28          // Set decimal precision
$ctx.number.rounding = math.half_up  // Control rounding
$ctx.number.epsilon = 1e-9          // Equality tolerance
$ctx.number.int = math.round         // Fractional-to-integer conversion
```

**Thread-Safe Context**: Context cloned for each thread to prevent race conditions.

### Mathematical Operators

Operators are reserved exclusively for numbers:

```comp
a + b       // Addition
a - b       // Subtraction  
a * b       // Multiplication
a / b       // Division (always returns fractional result)
a % b       // Modulo
a ** b      // Exponentiation
- a         // Negative
```

**No Operator Overloading**: Other types use explicit method calls:
```comp
// Strings use methods, not operators
text1 -> :string:concat text2
path1 -> :path:join path2
list1 -> :list:append list2
```

## Booleans

Booleans are a builtin type that can only represent two values representing
true or false. Other types cannot be converted to booleans.

Conditional operators will treat any non-boolean value a `#true` except for
an empty structure `{}`.

```javascript
!shape ~onoff = {on~boolean}
yes = #true
{"car"}~onoff  // Fails, string cannot coerce

This means the language requires the use of functions or comparison operators
to generate booleans for the conditionals.

```javascript
{"car" -> :string:empty}~onoff
```

Booleans do have operators that apply logic between other conditionals. These will treat all values as `#true` other than `#false` or `{}`.

```comp
condition && other      // Logical AND
condition || other      // Logical OR
!condition             // Logical NOT (different from !true/!false)
```

## Strings

Strings are immutable

### Literals

String literals are defined by any text in between double quotation marks.
Triple quotations can be used to create multiline string literals. This also
becomes a convenient way to create literals that also have quotations in
the text.

```javascript


### String Formatting and Templates

**Design Philosophy**: No operators for strings - use explicit functions and templates instead:

```comp
// No string concatenation operator
text1 + text2           // ERROR: operators reserved for numbers

// Use explicit methods or templates
{text1, text2} -> :string:concat
{text1, text2} -> "${}{}"        // Template concatenation
{"=" 40} -> :string:repeat       // Repetition via functions
```

### String Template Syntax

String templates use `${}` interpolation syntax and are reusable values:

```comp
// Template creation (not immediately evaluated)
greeting = "Hello ${name}!"
welcome_msg = "Welcome ${name}, you have ${count} messages"

// Template invocation with data
{name="Alice"} -> greeting                    // "Hello Alice!"
{name="Bob", count=5} -> welcome_msg         // "Welcome Bob, you have 5 messages"
```

### Three Interpolation Modes

Following Python's interpolation behavior with strict rules:

**1. Positional Interpolation**:
```comp
template = "Hello ${} and ${}!"
{"World", "Pete"} -> template    // "Hello World and Pete!"

// Order matches template placeholders
{user.first_name, user.last_name} -> "Name: ${} ${}"
```

**2. Explicit Index Interpolation**:
```comp
template = "${#2} ${#0} ${#1}"   // Explicit position references
{"A", "B", "C"} -> template      // "C A B"

// Zero-indexed positioning
data = {"first", "second", "third"}
data -> "Third: ${#2}, First: ${#0}"   // "Third: third, First: first"
```

**3. Named Field Interpolation**:
```comp
template = "${name} is ${age} years old"
{name="Alice", age=30} -> template    // "Alice is 30 years old"

// Works with any structure
user -> "Hello ${name}, your role is ${role}"
```

**Mixing Rules** (Python-compatible):
```comp
// Valid: positional + named
{name="Alice", "guest"} -> "Hello ${name}, you are a ${}"

// Invalid: positional + explicit index
{"A", "B"} -> "${#0} and ${}"  // ERROR: cannot mix modes

// Valid: explicit index + named  
{name="Alice", "A", "B"} -> "${name} sees ${#0} and ${#1}"
```

### Formatting Without Format Specifiers

**No inline format specifiers** - use preprocessing pipelines instead:

```comp
// Traditional (not in Comp):
// f"π is approximately {pi:.2f}"

// Comp approach: preprocess data
{pi=3.14159} 
  -> {pi = pi -> :number:round 2}
  -> "π is approximately ${pi}"

// Complex formatting with pipeline
financial_data -> {
    amount = amount -> :number:commify -> :number:currency "USD"
    date = date -> :date:format "MMM DD"
    rate = rate -> :number:percent 1
} -> "Transaction: ${amount} on ${date} at ${rate}"
```

### Formatter Objects

Configure consistent formatting rules as data structures:

```comp
// Formatter configuration
$currency_fmt = {
    number.separators = !true
    number.digits = 2
    number.currency = "USD"
    date.format = "MMM DD, YYYY"
}

// Apply formatter during template invocation
transaction_data -> {
    @ 
    formatter = $currency_fmt
} -> "Amount: ${amount} on ${date}"

// Set as context default
$ctx.formatter = $currency_fmt
// Now all templates use this formatter by default
```

### Advanced String Features

**Invoke Handlers for Specialized Formatting**:
```comp
// Attach formatters to templates using unit-like syntax
html_template = "<h1>${title}</h1><p>${content}</p>"@html.safe
sql_template = "SELECT * FROM users WHERE id = ${id}"@sql.escape

// Context can set default handlers
$ctx.default_string_invoke = :html:safe

// Usage
{title="Welcome", content="Hello World"} -> html_template
// Automatically applies HTML escaping via @html.safe handler
```

**Type Hints for Domain Strings**:
```comp
// Type hints provide metadata for validation/processing
query = @sql"SELECT * FROM users WHERE id = ${id}"
html_content = @html"<div>${content}</div>"
shell_cmd = @shell"ls ${directory}"

// When invoked, type hints enable domain-specific processing
{id=123} -> query        // Applies SQL escaping for security
{content="<script>"} -> html_content  // Applies HTML escaping
{directory="../etc"} -> shell_cmd     // Applies shell escaping
```

### String Operations

**Core String Functions**:
```comp
// Concatenation (likely builtin shorthand)
{"ERROR: ", error_message} -> :cat    // Short Unix-style concatenation

// Standard string operations
text -> :string:length                // Get length
text -> :string:trim                  // Remove whitespace
text -> :string:uppercase             // Convert case
text -> :string:split ","            // Split on delimiter
text -> :string:replace "old" "new"   // Replace substring
```

**String Processing Patterns**:
```comp
// Preprocessing pattern for complex formatting
!func :format_financial ~{amount, date} = {
    amount = amount -> :number:commify -> :number:currency "USD"
    date = date -> :date:format "MMM DD"
}

transactions
  -> each :format_financial
  -> each {"Transaction: ${amount} on ${date}"}
  -> :string:join "\n"
```

**Logging with `:nest` Pattern**:
```comp
// Log while preserving pipeline value
recipe -> :nest {
    {op -> :string:prefix 4, count = values -> :length} 
    -> "Running ${op} with ${count} values"
    -> :log:info
} -> :run:recipe
```

### String Template Compilation

Templates are first-class values that can be stored, passed, and reused:

```comp
// Store templates in data structures
$templates = {
    error = "ERROR: ${message} at line ${line}"
    warning = "WARNING: ${message}"
    info = "INFO: ${message} (${timestamp})"
}

// Use templates from structure
error_data -> $templates.error        // "ERROR: File not found at line 42"

// Pass templates as function parameters
!func :log_with_template ~{data, template} = {
    data -> template -> :log:write
}

log_data -> :log_with_template {template=$templates.error}
```

### Integration with Security

String templates integrate with Comp's security model through units:

```comp
// Security-aware string templates
user_query = @sql"SELECT * FROM users WHERE name = ${name}"
html_output = @html"<h1>${title}</h1><p>${content}</p>"  
shell_command = @shell"ls ${directory}"

// When invoked, units provide automatic escaping
{name="'; DROP TABLE users; --"} -> user_query
// SQL unit automatically escapes dangerous input

{title="<script>alert('xss')</script>"} -> html_output  
// HTML unit escapes script tags

{directory="../../../etc/passwd"} -> shell_command
// Shell unit prevents directory traversal
```

## Unit System

### Unit Definition Syntax

```comp
!unit @distance ~number = {
    m = !nil                    // Base unit
    km = {mult=0.001}          // Conversion factor
    inch = {mult=39.3701}      // Inches per meter
    lightyear = {mult=1.057e-16}
}

!unit @temperature ~number = {
    celsius = !nil
    fahrenheit = {offset=32, mult=1.8}    // Custom conversion
    kelvin = {offset=-273.15}
}
```

### Unit Usage and Conversion

```comp
distance = 5@distance@km
converted = distance -> :units:to @distance@m    // 5000@distance@m

// Automatic validation
speed = 60@distance@km / 1@time@hour    // Type-safe unit arithmetic
```

### Unit-Aware Security

Units can apply domain-specific escaping for security:

```comp
$query = "SELECT * FROM users WHERE id=${user_id}"@sql
// @sql unit automatically applies SQL escaping

$html = "<div>${content}</div>"@html
// @html unit applies HTML escaping

$shell = "ls ${directory}"@shell  
// @shell unit applies shell escaping
```

### Custom Unit Formatters

Unit formatters must be `!pure` functions for compile-time evaluation:

```comp
!pure :format_currency ~{value @currency} = {
    "$${value -> :number:format {decimals=2}}"
}

@currency = {formatter=:format_currency}
```

## Tag System

### Basic Tag Definition with Values

Tags are compile-time metadata markers that can optionally carry values for type casting and morphing:

```comp
!tag #status = {
    active = 1
    inactive = 0  
    pending        // No value - cannot be cast from values
}

!tag #role = {
    user = "user"
    admin = "admin"
    guest = "guest"
}
```

### Auto-Value Generation

Tags can use `!pure` functions to automatically generate values:

```comp
// Built-in auto-value functions
!pure :tag:name = {ctx -> ctx.name}                    // Use tag name as string value
!pure :tag:sequence = {ctx -> ctx.prev_value + 1}      // Sequential numbers
!pure :tag:bitwise = {ctx -> 1 << ctx.index}          // Bit flags for permissions

// Usage examples
!tag #color {:tag:name} = {
    red         // Automatically gets value "red"
    green       // Automatically gets value "green"
    blue        // Automatically gets value "blue"
}

!tag #permissions {:tag:bitwise} = {
    read        // 1 (1 << 0)
    write       // 2 (1 << 1)
    execute     // 4 (1 << 2)
    all = read | write | execute  // 7 (explicit combination)
}
```

### Auto-Value Context Structure

Auto-value functions receive context about the tag being defined:

```comp
// Context passed to auto-value functions
{
    name = "car"              // Current tag name
    full = "vehicles.car"     // Full hierarchical path
    index = 1                 // Position within parent (0-based)
    prev_value = 1000         // Previous sibling's value
    parent_value = 0          // Parent tag's value (if any)
    siblings = {              // Previously defined sibling values
        truck = 1000
    }
}
```

### Hierarchical Tags with Values

Tags support both parent values and child hierarchies:

```comp
!tag #failure = {
    network = 1000 {          // network has value 1000 AND children
        timeout = 1001        // Child with explicit value
        refused = 1002
        dns_error = 1003
    }
    parse {                   // No value - pure namespace
        syntax = 2001
        semantic = 2002
        eof = 2003
    }
    system = 3000 {
        memory = 3001
        disk = 3002
    }
}
```

### Tag Type Casting and Morphing

Tags with values can be cast to and from their associated values:

```comp
// Casting from value to tag
1001 ~#failure                    // Returns #failure#network#timeout
"red" ~#color                     // Returns #color#red  
99 ~#failure                      // FAILS: no matching value

// Casting tag to value
#color#red ~string                // Returns "red"
#permissions#write ~number        // Returns 2
#failure#parse ~number            // FAILS: parse has no value

// Tags without values cannot be cast
#status#pending ~number           // FAILS: pending has no value
```

### Shape Integration with Tag Casting

Tags work as type constraints in shape definitions and automatically cast during morphing:

```comp
!shape ~Config = {
    status ~#status
    port ~number
    mode ~#mode
}

// Shape morphing with automatic value-to-tag casting
{1, 8080, "strict"} ~Config
// Result: {status=#status#active, port=8080, mode=#mode#strict}
// (assuming 1 maps to active, "strict" maps to mode)

!shape ~User = {
    role ~#role
    permissions ~#permissions
    active ~bool = !true
}

// Morphing with tag values
{"admin", 7, !false} ~User
// Result: {role=#role#admin, permissions=#permissions#all, active=!false}
```

### Tag Families as Types

Tag families (root tags) are types/namespaces, not values:

```comp
$x = #status                      // ERROR: #status is a type, not a value
$x = #status#active               // OK: Leaf tag is a value
$type = ~#status                  // OK: Tag family as type reference

// Function parameters use tag families as type constraints  
!func :process ~{mode ~#mode} = {
    mode -> match {
        #mode#strict -> "Using strict validation"
        #mode#lenient -> "Using lenient validation"  
        #mode#debug -> "Using debug mode"
    }
}

// All these calls work (assuming appropriate tag values)
1 -> :process                     // Casts to matching tag
"lenient" -> :process             // Casts to #mode#lenient
#mode#debug -> :process           // Direct tag usage
```

### Ambiguous Value Resolution

When multiple tags share the same value, resolution follows first-match policy:

```comp
!tag #permission = {
    write = 2
    modify = 2    // Same value as write
}

// Ambiguous value casting
2 ~#permission    // Returns #permission#write (first match)
                  // Alternative: Could fail as ambiguous (implementation choice)

// Explicit disambiguation
#permission#modify    // Explicit tag reference
```

### Tag Extension Across Modules

Tags can be extended in other modules:

```comp
// base.comp
!tag #error {:tag:sequence} = {
    network = 1000
    parse = 2000
}

// extended.comp  
!extend #error = {
    storage = 3000    // Continues sequence from previous values
    memory = 3001
    filesystem = 3002
}

// Usage - extended tags work across modules
storage_error -> :handle_error    // Can match #error#storage
```

### Tag Inheritance and Polymorphic Dispatch

```comp
!tag #animal = {
    mammal = 100 {
        cat = 101 {indoor=!true}
        dog = 102 {loyalty=!true}
        whale = 103 {environment="ocean"}
    }
    bird = 200 {
        penguin = 201 {flight=!false}
        eagle = 202 {flight=!true}
    }
}

// Polymorphic function dispatch with tag values
!func :feed ~{animal ~#animal} = "Feeding generic animal"
!func :feed ~{animal ~#animal#mammal} = "Feeding mammal"
!func :feed ~{animal ~#animal#bird} = "Feeding bird"
!func :feed ~{animal ~#animal#mammal#cat} = "Feeding cat with special diet"

// Most specific match wins based on tag hierarchy
101 -> :feed    // "Feeding cat with special diet" (most specific)
100 -> :feed    // "Feeding mammal" (parent level)
{type=102} -> :feed  // "Feeding mammal" (dog is mammal)
```

### Tag References and Usage Patterns

```comp
// Direct tag references
current_status = #status#active
user_role = #role#admin

// Module-qualified tag references  
http_status = http#response#success
auth_level = security#clearance#top_secret

// Tag-typed function parameters
!func :handle_request ~{status ~#http#status} = {
    status -> match {
        #http#status#success -> :process_success
        #http#status#error -> :handle_error
        #http#status#redirect -> :follow_redirect
        else -> :log_unknown
    }
}

// Tag values in structure creation
response = {
    status = #http#status#success
    data = result
    headers = default_headers
}

// Automatic casting in function calls
200 -> :handle_request    // Casts to #http#status#success (if 200 is its value)
```

### Super Calls in Tag Hierarchies

```comp
!func :process_emotion ~{data #emotion} = {
    data -> :validate -> !super(process_emotion) -> :log
}

!func :process_emotion ~{data #emotion#anger} = {
    // Calls parent #emotion handler
    data -> :intensify -> !super(process_emotion)
}

// Explicit parent targeting
!func :process_emotion ~{data #emotion#anger#fury} = {
    data -> !super(process_emotion=#emotion#anger) -> :escalate
}
```

### Cross-Module Tag Usage

```comp
// In module A
!tag #priority = {low, medium, high, critical}

// In module B  
!import prioritymod = comp ./priority_module

// Usage - values are interchangeable
local_priority = #priority#high
imported_priority = prioritymod#priority#high
same_value = local_priority == imported_priority    // !true
```

### Tag Aliasing and Extension

```comp
// Import and extend
!tag #my_priorities = {
    ..external#priority        // Import all values
    urgent = external#priority#critical    // Alias existing
    emergency = {escalate=!true}           // Add new
}

// Values remain interchangeable
#my_priorities#urgent == external#priority#critical    // !true
```



## Type Validation and Constraints

### Inline Type Validation

```comp
data : {name ~string, age ~number}    // Runtime validation
user ~User -> :process                // Shape application
```

### Future Constraint System

Reserved syntax for compile-time constraints:

```comp
// Planned constraint syntax
~number|min=1|max=100                    // Numeric constraints
~string|len>5|matches="^[A-Z]"          // String constraints  
~User|age>=18|verified=!true            // Complex constraints

// Constraints would be pure validation only
// All validation evaluable at compile-time (constexpr)
```

## Type Promotion and Conversion

### Data Type Transformations

**Promotion** - External data → Comp types:
```comp
json_data -> :json:promote      // "2024-01-15" → datetime
cli_args -> :cli:promote        // "yes" → !true
```

**Casting** - Type conversion between Comp types:
```comp
"123" -> :number:cast          // String to number
#status#ok -> :string:cast     // Tag to string  
```

**Morphing** - Structure shape transformation (see [Structures Document](structures-spreads-lazy.md#structure-transformation-and-morphing)):
```comp
{10, 20} ~ Point2d             // Positional → named fields
```

### Domain-Specific Promotion

Different contexts use different promotion rules:

```comp
:cli:promote     // "yes"→!true, "0"→!false, "3"→3
:json:promote    // ISO dates→datetime, JSON booleans→!true/!false  
:sql:promote     // 1/0→boolean, SQL dates→datetime
:env:promote     // Environment variables, selective promotion
```



## Error Handling Types

### Failure Structures

Shape application failures return structured information:

```comp
{
    #failure
    #shape_application_failed
    message = "Type validation failed"
    partial = {x="hello", y=20}         // Partial results
    mapping = {field pairing details}
    errors = {specific error list}
}
```

### Hierarchical Error Tags

```comp
!tag #error = {
    validation = {
        type_mismatch = !nil
        missing_field = !nil
        constraint_violation = !nil
    }
    runtime = {
        resource_unavailable = !nil
        permission_denied = !nil
        timeout = !nil
    }
    system = {
        memory_exhausted = !nil
        io_error = !nil
    }
}
```


## Implementation Priorities

1. **Unified Number Type**: Context-controlled precision and behavior
2. **String Template System**: `${}` interpolation, three modes, and template compilation
3. **Unit System**: Definition, conversion, and security integration  
4. **Tag Hierarchy**: Inheritance, polymorphism, and super calls
5. **String Security Integration**: Unit-based escaping for SQL, HTML, shell contexts
6. **Type Validation**: Inline validation and constraint framework
7. **Platform Variants**: Conditional compilation support

This design provides a foundation for Comp's type system that prioritizes mathematical correctness, secure string processing, semantic clarity through tags, and flexibility through structural typing while maintaining compile-time analyzability.
