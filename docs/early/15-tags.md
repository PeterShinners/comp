## Tag Implementation Specification

### Basic Tag Definition
Tags are compile-time metadata markers that can optionally carry values:

```comp
!tag #status = {
    active = 1
    inactive = 0
    pending        // No value - cannot be cast from values
}
```

### Auto-Value Generation
Tags can use `!pure` functions to generate values automatically:

```comp
// Built-in auto-value functions
!pure :tag:name = {ctx -> ctx.name}                    // "red" from red
!pure :tag:sequence = {ctx -> ctx.prev_value + 1}      // Sequential numbers
!pure :tag:bitwise = {ctx -> 1 << ctx.index}          // Bit flags

// Usage
!tag #color {:tag:name} = {
    red         // Automatically gets "red"
    green       // Automatically gets "green"
    blue        // Automatically gets "blue"
}

!tag #permissions {:tag:bitwise} = {
    read        // 1 (1 << 0)
    write       // 2 (1 << 1)
    execute     // 4 (1 << 2)
    all = read | write | execute  // 7 (explicit combination)
}
```

### Auto-Value Context
Auto-value functions receive a context structure:

```comp
{
    name = "car"              // Current tag name
    full = "vehicles.car"     // Full path
    index = 1                 // Position within parent
    prev_value = 1000        // Previous sibling's value
    parent_value = 0         // Parent's value (if any)
    siblings = {             // Previously defined siblings
        truck = 1000
    }
}
```

### Hierarchical Tags with Values
Tags can have both values and children:

```comp
!tag #failure = {
    network = 1000 {          // network gets value 1000
        timeout = 1001        // Child with explicit value
        refused = 1002
    }
    parse {                   // No value - cannot be cast
        syntax = 2001
        semantic = 2002
    }
}
```

### Type Casting and Morphing
Tags with values can be cast to/from those values:

```comp
// Casting from value to tag
1001 ~#failure                    // Returns #failure.network.timeout
"red" ~#color                     // Returns #color.red
99 ~#failure                      // FAILS: no matching value

// Casting tag to value  
#color.red ~string                // Returns "red"
#permissions.write ~number        // Returns 2
#failure.parse ~number            // FAILS: parse has no value

// In shape morphing
!shape ~Config = {status ~#status port ~number}
{1 8080} ~Config                  // {status=#status.active port=8080}
```

### Shape Integration
Tags work as types in shape definitions:

```comp
!shape ~User = {
    role ~#role
    status ~#status  
}

// Morphing automatically casts values
{2 1} ~User        // {role=#role.admin status=#status.active}
                   // (assuming 2 maps to admin, 1 to active)
```

### Tag Families as Types
Tag families (e.g., `#status`) are types, not values:

```comp
$x = #status              // ERROR: #status is a type, not a value
$x = #status.active       // OK: Leaf tag is a value

!func :process ~{mode ~#mode} = {  // ~#mode is type constraint
    mode -> match {
        #mode.strict -> ...
        #mode.lenient -> ...
    }
}
```

### Ambiguous Value Resolution
When multiple tags share the same value:

```comp
!tag #permission = {
    write = 2
    modify = 2    // Same value as write
}

2 ~#permission    // Returns first match (#permission.write)
                  // Or could fail as ambiguous (TBD)
```

### Tag Extension
Tags can be extended in other modules:

```comp
// base.comp
!tag #error {:tag:sequence} = {
    network = 1000
    parse = 2000
}

// extended.comp
!extend #error = {
    storage = 3000    // Continues sequence
    memory = 3001
}
```

### Key Principles

1. **Tags without values cannot be cast** - Must be used explicitly
2. **Root tag type is not a value** - Tag families are types/namespaces
3. **Values must match type** - Can't cast number-valued tag to string
4. **Auto-values are compile-time** - Computed by `!pure` functions
5. **First match wins** - For ambiguous values (or error - TBD)
6. **Hierarchical values supported** - Parent can have value and children

This design unifies enums, discriminated unions, and type markers into a single powerful construct that integrates naturally with Comp's type system.