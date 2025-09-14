# Structures, Spreads, and Lazy Evaluation

*Design for Comp's structure generation, manipulation, and management.*

## Overview

Structures are the backbone of the Comp language. Every function is invoked
with a structure of data and generates a new structure. Even simple values
like booleans and numbers are automatically promoted into simple structures
with just one value.

Structures are immutable. Once created their contents are constant and fixed
until they are no longer needed.

Structures can contain any mix of named and unnamed fields. Field names can
be simple token values, or complex strings with advanced formatting. Field
names can also be tag values or as any type represented as an expression.
Structure fields can never be other structures. Unnamed fields are assigned
an incrementing numeric id as a field.

Structure fields are sorted. They can be iterated in the order of definition
and all fields can be referenced by overall position in the structure. This
allows structures to be used like arrays from other languages.

Fields can be matched and morphed by working with shape definitions, which
act a bit as schemas for structures.

The functionality and features of working with structures also applied
directly to Comp functions. Comp functions are just structure definitions
that aren't processed immediately.

## Structure Definition

### Literal Structures

The simplest structures are created from a sequence of fields wrapped
in `{}` braces. Structure can contain other structure values.

Fields that have already been assigned can by later fields.

```comp
// Structure examples
user = {name="Alice", age=30}                   // Named fields
coordinates = {10.5, 20.3}                      // Unnamed fields
mixed = {name="Bob", 25, #role#admin, active=#true}  // Multiple types

counts = {start=12 next=count+1 finish=next+1}  // Named 12 13 14 fields

deep = {name="Carl" address={"123 Road" "City, ST" 12321}}  // Nested
```

## Field References

Fields are referenced from structures with a dotted notation. Field names
can be any type of data, aside from other structures.

* **Tokens** need no special quoting, `name` `age`
* **Tags** tags can be field names (and field values), these no special quoting,
  `#status.ok` `#log.warning`
* **Strings** fields can be defined from arbitrary text, these fields are required
  to use double quotes, `"Ready?"` `"Press Start"`
* **Numbers** Numbers (and booleans) can be described with any expression wrapped in single quotes,
  `'0'` `'counter > 2'`

This same formatting syntax is used for assigning and referencing fields.

```comp

data = {token=1 #status.bad=2 "North Dakota"=3 '12/2'=4}

one = data.token
two = data.#status.bad
three = data."North Dakota"
four = data.'3+3'

user.'suffix->computed'   // Formatted field names
user.'$variable'          // Computed access with variables
```

## Indexed References

Each field in the structure has a unique positional index. This can be referenced
using the `#` operator with an integer number. The index is 0 based.

The indexing requires a zero or positive value. There is no support for indexing
backward from the end using negative indices. For these types of failures
see the library functions like `.iter:last` or `.iter:tail`

Assinging to a field index larger than the structure will result in a failure.
Using the `*=` strong assignment will force the structure to be expaded to the
size needed to contain that many fields.

```comp
color = {r=80 g=160 b=240}

color#1  // 160
color#2 = 0    // new structure with {r=80 g=160 b=0}
color#5 *= 255  // new structure with six fields
```

### Field Overrides

If the same field name is defined multiple times, the last definition will
win. 

This behavior can be influenced by using the alternative assignment operators
* `*=` **strong assignment** field cannot be overridden be other non-stron assignments
* `?=` **weak assignment** field will not be changed if it has been previously assigned

When overriding fields, the value is changed, but it's position in the
structure maintains the index that field was initially assigned to.

Fields can also be overridden by referencing 

```comp
conflicts = {
    *high=1 mid=2 low=3
    high=4  mid=5 low?=6
}
// Results in {high=1 mid=5 low=3}
```

### Spread Structures

Comp's spread operators allow filling the contents from one structure into
another. Multiple structures can be spread into the new structure being
created.

There are also variations for **strong spread** and **weak spread**. These follow
the same logic as if every individual field had been assigned using strong,
weak, or regular assignment.

* `...` **Spread** Apply each individual field to the structure
* `..*` **Strong Spread** Override each individual field to the structure
* `..?` **Weak Spread** Apply unset fields to the structure

When spreading structures, it does not matter if fields from the original
structures were assigned with weak or strong assignments. Once the structure
is created, the fields have no memory of their assignment strength.

The fields from the spread are assigned in the order they belong to their
original structures.

Unnamed fields in the structure are applied in the order of each structure
they come from. There is no overriding for unnamed fields.

```comp
redgreen = {red=1 green*=2 'alpha'}  // strong assignment has no influence on spreading
greenblue = {blue=3 green=4 'beta'}

{...redgreen ...greenblue}
// {red=1 green=4 blue=3 'alpha' 'beta'}

{green=99 ...?redgreen ...?greenblue}  
// {green=99 red=1 blue=3 'alpha' 'beta'}

{green=99 ...*redgreen ...*greenblue}
// {red=1 green=4 blue=3 'alpha' 'beta'}

{green=99 ...?redgreen ...*greenblue}
// {green=4 red=1 blue=3 'alpha' 'beta'}

{green*=99 ...?redgreen ...*greenblue}
// {green=4 red=1 blue=3 'alpha' 'beta'}
```

### Field Ordering and Immutability

Structures maintain field insertion order and are completely immutable:

```comp
original = {a=1, b=2, c=3}
modified = {...original, b=20, d=4}    // Creates new structure
// Result: {a=1, b=20, c=3, d=4}
// original remains unchanged: {a=1, b=2, c=3}
```

### Assignment Operators

Context-aware assignment operators adapt behavior based on usage:

```comp
=     // Normal assignment
*=    // Strong assignment (force/persist, extends structure)
?=    // Weak assignment (only if field doesn't exist)
..=   // Spread assignment (merge operator)
```

### Assignment Behavior Examples

```comp
user = {name="Alice", age=30}

// Normal assignment - overwrites existing
user.location = "Boston"     // {name="Alice", age=30, location="Boston"}
user.name = "Alicia"        // Overwrites existing name

// Conditional assignment - only if undefined
user.nickname ?= "Al"        // Adds nickname only if it doesn't exist
user.name ?= "Bob"          // Skips - name already exists

// Strong assignment - forces assignment, extends if needed
user.verified *= !true       // Forces assignment, extends structure if needed
```

### Deep Field Assignment

Creates new immutable structures at each level:

```comp
user = {
    profile = {
        settings = {theme="light"}
    }
}

// Deep assignment creates new structures at each level
user.profile.settings.theme = "dark"

// Equivalent to:
user = {
    ...user
    profile = {
        ...user.profile
        settings = {
            ...user.profile.settings
            theme = "dark"
        }
    }
}

// More complex deep assignment
tree.left.right.value = 42

// Equivalent to:
tree = {...tree 
    left = {...tree.left 
        right = {...tree.left.right 
            value = 42
        }
    }
}
```

## Spread Operations

### Basic Spread Syntax

```comp
...source           // Normal spread
..*source          // Strong spread (protected)
..?source          // Weak spread (conditional)
```

### Spread in Structure Creation

```comp
base = {name="Alice", age=30}
permissions = {read=!true, write=!false}

// Combine structures with spread
user = {
    ...base
    ...permissions
    active=!true
    created_at=:time:now
}
// Result: {name="Alice", age=30, read=!true, write=!false, active=!true, created_at=<timestamp>}
```

### Spread Assignment

Spread assignment may not be necessary, as it can be performed by the
spread pipeline operator. That does not provide weak or strong spreading.
When that level of control is needed, use more explicit spread statements.

```comp
struct ..= changes           // Additive merge (default)
struct ..?= changes         // Weak merge (won't overwrite existing)
struct ..*= changes         // Strong merge (replace entirely)
```

**Spread Assignment Examples**:
```comp
user = {name="Alice", age=30, active=!true}
updates = {age=31, city="Boston"}

// Normal spread assignment (additive merge)
user ..= updates
// Result: {name="Alice", age=31, active=!true, city="Boston"}

// Weak spread assignment (won't overwrite existing)
user ..?= {age=25, nickname="Al"}
// Result: {name="Alice", age=31, active=!true, city="Boston", nickname="Al"}
// age not updated because it already exists

// Strong spread assignment (replace entirely)  
user ..*= {name="Alice", verified=!true}
// Result: {name="Alice", verified=!true}
// All other fields removed
```

### Spread with Field Filtering

To avoid specific fields while spreading into a structure, the ideal solution
is to morph the data into the desired shape before spreading.

It's also possible to do a destructured assignment instead of a spread to
request individual fields.

If the data isn't expected to match a known shape, a strong assignment
can be made to that field before the regular spread.

(There was talk of a special #delete value, is that a thing?)

```comp
source = {name="Bob", age=25, password="secret", admin=!true}

individual_fields = {
    {name age admin} = source
}

shaped_spread = {
    ..source~source-without-password
}

public_data = {
    password *= {}
    ...source
}
```

## Lazy Evaluation

### Lazy Structure Syntax

Creating a structure with square brackets crete a lazy structure. This
structure will work like a generator, only executing the statements needed
to unambiguously provide the request field or index.

The lazy structure can be reused as often as needed. Once a field has been
computed. After fully iterating the lazy structure it will behae the same
as a regular structure.

```comp

// Lazy structure does not invoke functions until fields needed.
$lazy = [a=:func-one b=:func-two c=:func-three]
$value = $lazy.b  // Both :func-one and :func-two invoked


// Create structure where individual fields are resolve lazily
lazy_config = {
    database_url = ["DATABASE_URL" -> :env:get]
    max_connections = ["MAX_CONN" -> :env:get -> :num:parse]
}
```

### Lazy Evaluation Context Capture

When lazy blocks are created, they capture the state of their static
contexts and values when created. These independent copies are no
longer influenced by the runtime.

```comp
!func :create_lazy_processor = {
    $multiplier = 10
    !ctx.base_value = 100
    
    // Context captured here
    lazy_processor = [
        input -> input * $multiplier + @func.base_value
    ]
    
    $multiplier = 20           // Change doesn't affect lazy block
    lazy_processor            // Returns block with original context
}

$processor = :create_lazy_processor
$result = $processor -> :evaluate {input=5}  // Uses multiplier=10, base_value=100
```

### Lazy Morphing

When a lazy structure is strictly morphed to a shape (meaning, undefined
fields fields are ignored) the lazy structure will only be executed until
all the needed fields for the shape have been resolved.

## Advanced Structure Patterns

```comp
## Advanced Structure Patterns

### Structure Composition
user_profile = {
    ...user_basic_info
    ...user_preferences
    ...user.id -> :load_user_permissions
    computed_field = user.name -> :format_display_name
}

// Conditional composition
admin_profile = {
    ...user_profile
    -?? user.role == "admin" -&& admin_permissions
    audit_log = [user.id -> :load_audit_history]
}
```

### Structure Templates

More complicated structures can use functions to help populate
their contents, which allows actual logic, instead of the 
declartive shape definitions.

```comp
// Template function for structure creation
!func :user_template ~{name ~str, role ~str = "user"} = {
    name = name
    role = role
    permissions = role -> :get_default_permissions
    created_at = :time:now
    active = !true
    settings = {
        theme = "light"
        notifications = !true
    }
}

// Usage
admin = "Alice" -> :user_template {role="admin"}
user = "Bob" -> :user_template
```

## Structure Introspection

### Field Enumeration

```comp
user = {name="Alice", age=30, #role#admin, active=!true}

// Get field information
field_names = user -> :struct:field_names    // ["name", "age", "#role", "active"]
field_count = user -> :struct:length         // 4
has_role = user -> :struct:has_field "#role" // !true
```

### Structure Analysis

```comp
// Analyze structure composition
user -> :struct:analyze -> {
    named_fields = @.named_count      // 3
    tagged_fields = @.tagged_count    // 1
    positional_fields = @.positional_count  // 0
    field_types = @.type_summary     // {string: 1, number: 1, tag: 1, bool: 1}
}
```

### Structure Comparison

```comp
user1 = {name="Alice", age=30}
user2 = {age=30, name="Alice"}  // Different order
user3 = {name="Alice", age=30, city="Boston"}

// Structural equality (ignores field order)
user1 -> :struct:equals user2    // !true
user1 -> :struct:equals user3    // !false

// Field subset checking
user1 -> :struct:subset_of user3  // !true (user1 fields ⊆ user3 fields)
user3 -> :struct:subset_of user1  // !false
```


