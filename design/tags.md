# Tags

## Basic Tag Definition with Values

Tags are compile-time tokens that can be used as both types and values. They are
prefixed with a `#` hash when referenced.

They can form a hierarchical naming structure that allows shapes to match
specific values or their organizational parents.

Placing tag values has a strong influence on the shape of that structure. This
is used to drive polymorphic behavior to the and function dispatch based on any
untyped structure.

Tags can optionally have values assigned directly, or use helper functions to
assign automatic values. When types are defined tags can be interchanged with
regular data types. A tag can have both children and a value, even the root tag
type can have a value.

Tags are referenced with the `#` on the leading hash type. Optional children
values are referenced through regular `.` dot access like field names.

Tags can also be used as fields for structures. When used this way the field is
specifically the tag object, not the optional value it contains.

```comp
!tag #status = {
    active = 1
    inactive = 0  
    pending        // No value - cannot be morphed from values
}

!tag #role = "Unknown" {
    user = "User"
    admin = "Admin"
    guest = "Guest" {
        limited = "GuestHi"
        invisible = "GuestLo"
    }
}

$dev = #other-mod#status.pending
$rol = #role.guest.limited
$who = #role

```

## Auto-Value Generation

Tags can use `!pure` functions to automatically generate values. The function
will be called on each defined tag, which gets a structure defining the states
and values of related tags.

```comp
// Built-in auto-value functions
!pure :tag:name = {ctx -> ctx.name}                // Use tag name as string value
!pure :tag:sequence = {ctx -> ctx.prev_value + 1}  // Sequential numbers
!pure :tag:bitwise = {ctx -> 1 << ctx.index}       // Bit flags for permissions

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

## Tag Type Casting and Morphing

Tags with values can be cast to and from their associated values:

```comp
// Casting from value to tag
1001 #failure                 // Returns #failure#network#timeout
"red" #color                  // Returns #color#red  
99 #failure                   // FAILS: no matching value

// Casting tag to value
#color#red ~str             // Returns "red"
#permissions#write ~num        // Returns 2
#failure#parse ~num            // FAILS: parse has no value

// Tags without values cannot be cast
#status#pending ~num           // FAILS: pending has no value

// Automatic casting in function calls
200 -> :handle_request    // Casts to #http#status#success (if 200 is its value)

```

## Shape Integration with Tag Casting

Tags work as type constraints in shape definitions and automatically cast during
morphing. When multiple tags share the same value, resolution follows
first-match policy.

```comp
!shape ~Config = {
    status #status
    port ~num
    mode #mode
}

// Shape morphing with automatic value-to-tag casting
{1, 8080, "strict"} ~Config
// Result: {status=#status#active, port=8080, mode=#mode#strict}
// (assuming 1 maps to active, "strict" maps to mode)

!shape ~User = {
    role #role
    permissions #permissions
    active ~bool = #true
}

// Morphing with tag values
{"admin", 7, #false} ~User
// Result: {role=#role#admin, permissions=#permissions#all, active=#false}
```

## Tag Extension Across Modules

Modules can extend tags defined in other modules. The values inherited will be
interchangeable with the tag values from the original module. The original
module will not see or understand the individual tags in the extension, but can
still match values based on any hierarchical structure they both share.

```comp
// base.comp
!tag #error = {
    network = 1000
    parse = 2000
}

// extended.comp  
!tag extend #base#error = {
    storage = 3000    // Continues sequence from previous values
    memory = 3001
    filesystem = 3002
}

// Usage - extended tags work across modules
storage_error -> :handle_error    // Can match #error#storage


// Possible to extend at a nested level of the tags
!tag extend #

```

When the base tag has a function to generate automatic names, it will also be
applied do these extended values. (This will cause errors if two extensions
expect an incremented id but keep getting loaded in different orders.)

