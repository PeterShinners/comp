# Shapes, Blocks, and Higher-Order Functions

*Design for Comp's shape and unit systems*

## Overview

A shape looks like a structure, but isn't a value or data itself.
The shape defines a schema that can be used to match and morph structure
data.

For each field the shape can define an optional name, an optional shape,
an optional default value, and an optional documentaion string.

When shapes are used to define function, these characteristics make them
work similar to positional and keyword arguments in languages like Python.

Values also have an extensible units system. Units attach to values and
control how they are converted with other values. The most typical use
of this system is to assign units, like weights and measurements, to
regular number values.

### Builtin shapes

Comp defined a handful of builtin shapes that are available in any namespace.
* `~nil` an alias for an empty structure, or `~{}`

Be aware that the empty structure is a shorthand of matching any possible
structure, and the default shape morphing preserves fields that are undefined
in the shape.

## Shape System

### Shape Definition Syntax

Shapes use the `!shape` operator to define new ones. Shapes live declaratively
in the module's namespace. Shapes can be defined and used in any position
inside the module.

The modules will fail to build when a shape name is defined multiple times.

```comp
!shape ~Point2d = {
    x ~num = 0
    y ~num = 0
}

!shape ~User = {
    name ~str
    age ~num
    email ~str
    active ~bool = !true
    preferences? // Optional field
    tags #user_tag[]  // Array of user tags
}
```

### Shape Inheritance with Spreading

```comp
!shape ~Point3d = {
    ...~Point2d    // Inherit x, y fields
    z ~num = 0  // Add z coordinate
}

!shape ~ColoredPoint = {
    ...~Point2d
    color ~str = "black"
}

// Function parameter spreading
!func :analyze ~{...~RawData, complexity ~num = 0} = {
    // Has all RawData fields plus complexity parameter
    @in -> :process_with_complexity
}
```

### Union Shapes

The shape for a value can be a combination of multiple shapes, combined
These are grouped with the `|` pipe operator.

Combine a shape with `~nil` definition to allow setting to an empty
structure, which represents having no value.

Any shape can be defined from an existing shape definition. 
This allows creating shortcuts or definitions to commonly used types.

```comp
!shape maybe-num = ~num|~nil
!shape recipient = ~user|~group


### Array Shapes

A shape can define a container of a type by appending `[]` square brackets
to the shape. This has several forms to define ranges of sizes.

* `[]` any number of the items allowed, including none
* `[4-8]` require at least four but no more than eight
* `[-3]` require three at the most, including zero
* `[1-]` require at least one item

Note that there are no negative sizes allowed, so `[-3]` unambiguously defines
a range like `[0-3]`.

### Shape Application Operators

```comp
data ~ Shape           // Normal morph with defaults
data *~ Shape          // Strong morph (strict, no extras allowed)
data ?~ Shape          // Weak morph (lenient, missing fields OK)
data ~@ Shape          // Include namespace lookups for defaults
```

### Shape Morphing Algorithm

**Three-Phase Field Matching Process**:

1. **Named Matches** - Exact field name matches
2. **Tag Matches** - Fields with matching tag types
3. **Positional Matches** - Remaining fields matched by position
4. **Default Application** - Unmatched optional fields get defaults

```comp
!shape ~Config = {
    host ~str = "localhost"
    port ~num = 8080
    debug ~bool = !false
}

// Morphing example
{"192.168.1.1", debug=!true, extra="ignored"} ~ Config
// Phase 1: debug=!true matches by name
// Phase 2: (no tag matches)
// Phase 3: "192.168.1.1" -> host by position
// Phase 4: port=8080 from default
// Result: {host="192.168.1.1", port=8080, debug=!true}
```

### Shape Application in Function Calls

Functions automatically apply `?~@` (weak morph with namespace) to incoming arguments:

```comp
!func :create_user ~{name ~str, age ~num, active ~bool = !true} = {
    // Automatically morphs input using ?~@
    @in -> :validate -> :save
}

// All of these work:
{name="Alice", age=30} -> :create_user                    // Uses default active=!true
{name="Bob", age=25, active=!false} -> :create_user       // Explicit active
{name="Carol", age=40, extra="data"} -> :create_user      // Extra fields ignored (weak morph)
```

## Shape Pattern Matching

### Shape-Based Pattern Matching

Shapes can be used for pattern matching and conditional processing:

```comp
!shape ~HttpResponse = {
    status #http_status
    data
    headers = {}
}

// Pattern matching on shapes
response ~ HttpResponse -> match {
    {status=#http_status#success} -> data -> :process_success
    {status=#http_status#error, data} -> data -> :handle_error  
    {status=#http_status#redirect, headers} -> headers.location -> :redirect
}
```

### Guard Conditions in Shapes

```comp
!shape ~ValidUser = {
    name ~str|len>0      // Non-empty string
    age ~num|min=0|max=150  // Reasonable age range
    email ~str|matches=/^[^@]+@[^@]+$/  // Email pattern
}

!func :create_user ~ValidUser = {
    // Input guaranteed to match validation rules
    @in -> :save_to_database
}
```

## Performance and Optimization

### Shape Compilation and Caching

```comp
// Shapes can be compiled for faster repeated application
!shape ~ValidatedUser = {
    name ~str|len>0
    email ~str|matches=/^[^@]+@[^@]+$/
    age ~num|min=0|max=150
}

// First application compiles shape rules
user_data ~ ValidatedUser  // Compiles validation rules
similar_data ~ ValidatedUser  // Uses cached compiled shape
```

## Integration Examples

### API Handler with Shape Validation

```comp
!shape ~UserCreateRequest = {
    name ~str|len>0
    email ~str|matches=/^[^@]+@[^@]+$/
    age ~num|min=13|max=120
    notifications ~bool = !true
}

!func :create_user_endpoint ~UserCreateRequest -> ~HttpResponse = {
    @in -> :validate_unique_email -> :create_user -> :send_welcome_email -> {
        status = 201
        body = {message="User created successfully", user=@}
        headers = {"Content-Type": "application/json"}
    }
}
```

## Unit System

### Unit Definition Syntax

```comp
!unit @distance ~num = {
    m = !nil                    // Base unit
    km = {mult=0.001}          // Conversion factor
    inch = {mult=39.3701}      // Inches per meter
    lightyear = {mult=1.057e-16}
}

!unit @temperature ~num = {
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
    "$${value -> :num:format {decimals=2}}"
}

@currency = {formatter=:format_currency}
```


### Unit morphing

Coercion when using operators (left wins, right gets converted) (sometimes?)


## Structure Transformation and Morphing

### Shape Morphing

Structure shape transformation allows converting between compatible structure formats:

```comp
// Positional to named fields
{10, 20} ~ Point2d             // Converts to named fields based on shape
{x=10, y=20}                   // Result if Point2d has x,y fields

// Mixed structure morphing  
{name="Alice", 30, #role#admin} ~ User
// Converts to User shape with appropriate field mapping

// Complex morphing with validation
raw_data ~ {
    ValidatedUser           // Apply shape validation
    -> :assign_defaults     // Fill in default values  
    -> :compute_derived     // Add computed fields
}
```

### Structure Template Application

```comp
!shape ~Point2d = {x ~num, y ~num}
!shape ~Point3d = {x ~num, y ~num, z ~num}

// Convert 2D to 3D with default z
point_2d = {x=10, y=20}
point_3d = {...point_2d, z=0} ~ Point3d

// Template-based conversion
points_2d = [{x=1, y=2}, {x=3, y=4}]
points_3d = points_2d => {@ ~ Point3d | {z=0}}
```

### Morphing with Type Promotion

Morphing can combine with type promotion for data transformation:

```comp
// JSON to structured data
json_input = '{"name": "Alice", "age": "30", "active": "true"}'
user = json_input -> :json:parse -> :json:promote ~ User
// Promotes "30" to number, "true" to !true, then applies User shape
```
