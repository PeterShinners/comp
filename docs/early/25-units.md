# Units in Comp Language

## Overview

Units are semantic type annotations for primitive values (numbers and strings) that enable type-safe operations, automatic conversions, and proper formatting. They use the `#` prefix and are built on Comp's tag system.

## Why Units Exist

Primitives need semantic meaning for safety and dispatch:

```comp
; Without units - ambiguous
5                           ; 5 what? Meters? Seconds?
"SELECT * FROM users"       ; Plain string or SQL?

; With units - clear meaning
5#meter                     ; Convertible to feet
"SELECT * FROM users"#sql  ; Gets SQL escaping in templates
```

Units enable:
- **Type safety** - Can't mix incompatible units
- **Automatic conversion** - Between compatible units
- **Safe formatting** - Context-aware escaping
- **Function dispatch** - Overload based on unit type

Structs don't need units - they already have shapes and tag fields for dispatch. Units give primitives the same power.

## Units vs Constraints

Units and constraints serve different purposes:

```comp
; Units: semantic meaning and conversion
5#meter                     ; WHAT it is - convertible to feet
"SELECT..."#sql            ; HOW to interpret - needs SQL escaping

; Constraints: validation and ranges  
~number|min=0|max=100      ; VALID VALUES - enforces limits
~string|regex="^.+@.+$"    ; VALID FORMAT - must match pattern

; Can combine both
!shape ~Config = {
    timeout ~number#second|min=0|max=300   ; Unit AND constraints
    ; #second for conversion/display
    ; constraints for validation
}
```

Units convert between representations. Constraints validate/restrict values.

## Using Units

### Basic Usage & Conversion
```comp
100#meter -> :convert #feet         ; Returns 328.084#feet
20#celsius -> :convert #fahrenheit  ; Returns 68#fahrenheit
100#meter -> :convert #second       ; ERROR: incompatible
```

### Templates with Auto-Escaping
```comp
user_input = "'; DROP TABLE users;"
query = "SELECT * WHERE name='${user_input}'"#sql
; Result: safely escaped SQL string
```

### Shape Matching
```comp
!shape ~Temperature = {
    value ~number#celsius       ; Expects celsius
}

{value=32#fahrenheit} ~ Temperature  ; Auto-converts to celsius
{value=5#meter} ~ Temperature        ; ERROR: wrong unit category
```

### Function Dispatch
```comp
!func :process ~{distance ~number#meter} = { ... }
!func :process ~{distance ~number#feet} = { ... }
!func :execute ~{cmd ~string#sql} = { ... }
!func :execute ~{cmd ~string#bash} = { ... }
```

## Defining New Units

### Number Unit with Conversion
```comp
; Add to volume category (converts via liters)
!tag #unit/volume = {
    liter = {"L" "L" 1.0} ~unit_definition           
    dollop = {"dollop" "dollops" 0.015} ~unit_definition
}

2#unit/volume#dollop -> :convert #unit/volume#liter  ; 0.03L
```

### String Unit with Escaping
```comp
!tag #unit/str = {
    bash
}

!func :unit:escape ~{value ~string#unit/str#bash} = {
    value -> :string:replace {"\"" "\\\""} -> "\"{}\""
}

file = "my file.txt"
"cat ${file}"#unit/str#bash        ; "cat \"my file.txt\""
```

## Key Principles

1. **Units are tags** - Built on existing tag system
2. **Primitives only** - Structs use shapes instead
3. **Semantic meaning** - Units say what values ARE, not what's valid
4. **Library extensible** - Any module can define new units

Units give primitive values semantic meaning and enable safe operations, while constraints enforce validation rules. Together they provide complete type safety.


## Comp Units System - Updated Design

### Core Concept
Units in Comp are split into two fundamental types based on their relationship to an origin:

1. **Offset units** (default: `#unit`) - Relative measurements that can be summed
2. **Origin units** (explicit: `+#unit`) - Positions/points anchored to a fixed origin

### Syntax
```comp
// Offset units (the common case - ~90% of usage)
100#meter         // a distance/size
30#seconds        // a duration  
15#gb            // a memory size
5#celsius        // a temperature difference

// Origin units (positions/coordinates - ~10% of usage)
100+#meter       // position at 100m from origin
1609459200+#timestamp  // specific point in time (Unix epoch)
0x4000+#address  // pointer/position in memory
20+#celsius      // temperature reading from absolute scale
```

### Mathematical Rules
The type system enforces semantically correct operations:

```comp
// Origin + Offset = Origin (moving a position)
100+#meter + 50#meter = 150+#meter

// Origin - Origin = Offset (distance between positions)
150+#meter - 100+#meter = 50#meter

// Offset + Offset = Offset (combining measurements)
30#meter + 20#meter = 50#meter

// Origin + Origin = ERROR (nonsensical operation)
100+#meter + 200+#meter  // ERROR: Cannot add two origin units
```

### Key Insights

**Memory pointers are just origin units:**
```comp
$ptr = 0x4000+#address      // A pointer IS a position in memory
$size = 1024#bytes          // An offset
$end_ptr = ptr + size       // Pointer arithmetic works naturally
```

**Geometric shapes encode their semantics:**
```comp
!shape point = {x+#meter y+#meter}  // A position

!shape circle = {
  center~point           // Origin units for position
  radius#meter          // Offset unit for size
}

!shape rect_bounds = {    // Edges (all origin units)
  left+#meter top+#meter right+#meter bottom+#meter
}

!shape rect_dims = {      // Position + dimensions  
  pos~point              // Origin for position
  width#meter height#meter  // Offsets for size
}
```

**Common patterns become type-safe:**
```comp
// Summing durations (offsets) - VALID
$total_time = tasks -> :map .duration -> :sum  

// Summing timestamps (origins) - ERROR
$nonsense = events -> :map .timestamp -> :sum  // Caught at compile time!

// Rectangle perimeter - works with correct types
$perimeter = 2 * rect.width + 2 * rect.height  // Offset units sum correctly
```

### Conversion System
Leverages the existing shape dispatch system:

```comp
// Unit conversion uses the ~ operator
70+#fahrenheit ~number+#celsius  // Origin unit conversion
30#minutes ~number#seconds       // Offset unit conversion

// Converters are pure functions that can run at compile time
!block :convert ~{value~temperature target~temperature} = {
  // Implementation uses !describe to access unit metadata
  // without making types first-class values
}
```

### Design Philosophy
- **Make the common case easy**: Offsets (sizes, durations, quantities) default to plain `#unit` syntax
- **Make the special case explicit**: Origins (positions, pointers, timestamps) require `+#unit` notation  
- **Prevent semantic errors**: Can't add timestamps, can't sum pointers, can't mix positions and sizes incorrectly
- **Unify concepts**: Pointers, positions, timestamps, and coordinates all follow the same origin unit rules

The `-#unit` notation exists conceptually for teaching/documentation to show the symmetry with `+#unit`, but doesn't appear in actual code since offset units are the default.

This system catches whole classes of unit-confusion bugs at compile time while keeping the syntax clean for the most common use cases.