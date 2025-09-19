# Shapes, Units, and Type System

*Design for Comp's structural typing, unit system, and shape morphing*

## Overview

Shapes define structural schemas that describe and validate data. They specify field names, types, defaults, and constraints, creating a powerful system for type checking and data transformation. Unlike nominal type systems, Comp's shapes use structural compatibility - any structure with the required fields can satisfy a shape.

The shape system integrates with units to provide semantic typing for primitive values. Units attach to numbers and strings through tags, enabling automatic conversions, type-safe operations, and domain-specific validation. Together, shapes and units create a flexible yet rigorous type system.

## Shape Definition and Inheritance

Shapes are defined with the `shape` keyword and live declaratively in the module namespace. They can be referenced anywhere within the module regardless of definition order. Shape definitions specify fields with optional types, defaults, and documentation. The spread operator enables shape composition through inheritance.

```comp
shape Point2d = {
    x ~num = 0
    y ~num = 0
}

shape Point3d = {
    ..~Point2d              # Inherit x, y fields
    z ~num = 0              # Add z coordinate
}

shape User = {
    name ~str
    email ~str
    age ~num = 0
    active ~bool = #true
    preferences?            # Optional field (any type)
    tags #user_tag[]        # Array of specific tags
}

# Shape composition with multiple inheritance
shape AuthenticatedUser = {
    ..~User
    token ~str
    permissions #permission[]
    last_login ~str = (| now/time)
}
```

Fields in shapes can specify ranges for collections, enabling precise cardinality constraints. The syntax `[min-max]` defines acceptable element counts, with shortcuts for common patterns.

```comp
shape Config = {
    servers ~Server[1-]      # At least one server
    backups ~Backup[0-3]     # Up to three backups
    nodes ~Node[5-10]        # Between 5 and 10 nodes
    options ~str[]           # Any number of strings
}
```

## Shape Morphing Algorithm

Shape morphing transforms structures to match shape specifications through a multi-phase matching process. The algorithm considers field names, types, positions, and defaults to create the best possible match. During morphing, missing fields can be sourced from the namespace stack (`$ctx` and `$mod`).

The morphing process follows these phases:
1. **Named field matching** - Exact field name matches are assigned first
2. **Tag field matching** - Fields with matching tag types are assigned
3. **Positional matching** - Remaining fields match by position
4. **Default application** - Unmatched shape fields receive defaults from shape definition
5. **Namespace lookup** - Missing fields check `$ctx` and `$mod`

```comp
shape Connection = {
    host ~str = localhost
    port ~num = 8080
    secure ~bool = #false
}

# Basic morphing
({example.com 443 #true} ~ Connection)
# Result: {host=example.com port=443 secure=#true}

# Namespace fields are automatically available
$ctx.port = 3000
({host=prod.example.com} ~ Connection)
# Result: {host=prod.example.com port=3000 secure=#false}
# port comes from $ctx, secure from shape default

# Function parameters automatically morph with namespace access
func connect pipeline{conn} args{} = {
    (Connecting to ${$in.host}:${$in.port} | log)
}
```

## Shape Application Operators

Different morphing operators control strictness and error handling. The standard morph (`~`) applies defaults and allows extra fields. Strong morph (`*~`) rejects structures with undefined fields. Weak morph (`?~`) makes all shape fields optional. Each variant has a corresponding check operator that tests compatibility without morphing.

```comp
data ~ Shape             # Normal morph with defaults
data *~ Shape            # Strong - no extra fields allowed
data ?~ Shape            # Weak - missing fields acceptable

# Check operators return #true or #false
data ~? Shape            # Can morph normally?
data *~? Shape           # Can morph strictly?
data ?~? Shape           # Can morph weakly?

# Usage in validation
($in | if {$in ~? ExpectedShape} 
         {$in ~ ExpectedShape | handle}
         {#shape.fail message=Invalid input structure})
```

## Shape Constraints

Shapes can define constraints that validate field values beyond basic type checking. These constraints are checked during morphing and can cause morphing to fail if violated. Constraints use pure functions that return boolean values or failure structures.

```comp
shape ValidUser = {
    name ~str {min_length=3 max_length=50}
    email ~str {pattern="^[^@]+@[^@]+$"}
    age ~num {min=13 max=120}
    score ~num {validate={$in >= 0 && $in <= 100}}
}

# Constraint functions for complex validation
pure valid_username pipeline{name} args{} = {
    ($in | length/str) >= 3 && 
    ($in | match/str "^[a-z][a-z0-9_]*$") &&
    !($in | contains/reserved_words)
}

shape Account = {
    username ~str {validate=|valid_username}
    balance ~num {min=0}
    status #account_status
}
```

Constraints are evaluated during morphing, with failures generating descriptive error structures. This enables precise validation at type boundaries while maintaining composability.

## Unit System Fundamentals

Units provide semantic typing for primitive values through the tag system. Units are implemented as tag hierarchies with conversion rules, enabling type-safe operations and automatic conversions. The standard library provides comprehensive units through the `unit/` module.

```comp
import unit = std "core/unit"

# Units as tags
distance = 5#kilometer      # Using shortened form
duration = 30#second
temp = 20#celsius

# Automatic conversion in operations
total = 5#meter + 10#foot         # Result in meters
speed = 100#kilometer / 1#hour    # Compound unit

# Explicit conversion
meters = distance ~ num#meter     # 5000
feet = distance ~ num#foot        # ~16.404
kelvin = temp ~ num#kelvin        # 293.15
```

Units follow algebraic rules:
- Addition/subtraction require compatible units
- First operand's unit determines result unit  
- Multiplication/division create compound units
- Incompatible operations fail immediately

## String Units and Domain Validation

String units provide semantic typing and validation for string values. They can enforce formats, apply transformations, and control escaping in templates. String units are particularly valuable for security, ensuring proper escaping based on context.

```comp
tag email ~str = {
    validate = |match/str "^[^@]+@[^@]+$"
    normalize = |lowercase/str
}

tag sql ~str = {
    escape = |escape_literal/sql
    validate = |check_syntax/sql
}

tag html ~str = {
    escape = |escape_entities/html
    sanitize = |remove_scripts/html
}

# Usage with automatic validation
address = "User@Example.COM"#email
normalized = address ~ str#email    # user@example.com

# Template safety through units
query = SELECT * FROM users WHERE id = ${id}#sql
html = <h1>${title}</h1>#html
# Units ensure proper escaping in templates
```

## Union and Conditional Shapes

Shapes can be combined with `|` to create union types that accept multiple structures. This enables flexible APIs that handle different input formats while maintaining type safety. Union shapes are particularly useful for result types and variant handling.

```comp
shape Result = ~Success | ~Error
shape Success = {value ~any}
shape Error = {#fail message ~str}

shape ConfigSource = ~FileConfig | ~EnvConfig | ~DefaultConfig
shape FileConfig = {path ~str}
shape EnvConfig = {prefix ~str}
shape DefaultConfig = {}

# Conditional shape selection
func process pipeline{input} args{} = {
    $in | match
        {$in ~? Success} {.value | handle_success}
        {$in ~? Error} {.message | log_error}
}
```

## Shape-Based Pattern Matching

Shapes integrate with pattern matching to enable type-directed control flow. The `~?` operator tests shape compatibility, while morphing operations transform data for processing. This creates elegant APIs where function behavior adapts to input structure.

```comp
shape GetRequest = {method=GET path ~str}
shape PostRequest = {method=POST path ~str body ~any}
shape DeleteRequest = {method=DELETE path ~str}

func handle_request pipeline{request} args{} = {
    $in | match
        {$in ~? GetRequest} {
            $in ~ GetRequest | fetch_resource
        }
        {$in ~? PostRequest} {
            $in ~ PostRequest | create_resource
        }
        {$in ~? DeleteRequest} {
            $in ~ DeleteRequest | delete_resource
        }
        {#true} {
            {#http.fail status=405 message=Method not allowed}
        }
}
```

## Performance Optimization

Shape operations can be optimized through caching and compilation. Repeated morphing operations with the same shape benefit from cached validation rules. The runtime can compile shape definitions into efficient validators, particularly for shapes with complex constraints.

```comp
# Shapes used in hot paths should be pre-compiled
shape HotPath = {
    data ~str {validate=|complex_validation}
    timestamp ~num {min=0}
    flags #flag[]
}

# First use compiles validation rules
first_result = input ~ HotPath      # Compiles and caches

# Subsequent uses reuse compiled rules
loop_results = items | map {$in ~ HotPath}  # Fast validation
```

## Design Principles

The shape and unit system embodies several core principles. Structural compatibility means types are defined by structure, not names, enabling flexible composition. Semantic typing through units provides meaning beyond primitive types. Gradual validation allows choosing strictness levels appropriate to each context. Namespace integration enables shapes to work with Comp's layered data model. Compile-time optimization ensures type checking doesn't sacrifice performance.

These principles create a type system that balances flexibility with safety. Whether validating API inputs, ensuring dimensional correctness in calculations, or transforming between data formats, shapes and units provide powerful tools for managing complexity in real-world applications.