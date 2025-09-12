# Structures, Spreads, and Lazy Evaluation

*Design for Comp's structure manipulation, spread operators, lazy evaluation, and immutable data transformation*

## Overview

Comp's structure system provides flexible data containers that mix named, unnamed, and tagged fields freely. All operations create new immutable structures using spread operators, field assignments, and lazy evaluation blocks. The system emphasizes composability and predictable transformations.

## Structure Fundamentals

### Universal Structure Model

All data in Comp is represented as structures - ordered collections of fields that can be:
- **Named**: `{name="Alice", age=30}`
- **Unnamed**: `{10, 20, 30}` (array-like)  
- **Tagged**: `{#priority#high, #status#active}`
- **Mixed**: `{name="Alice", 25, #status#active, city="NYC"}`

```comp
// Structure examples
user = {name="Alice", age=30}                    // Named fields
coordinates = {10.5, 20.3}                      // Unnamed fields
status_data = {#priority#high, urgent=!true}    // Tagged + named
mixed = {name="Bob", 25, #role#admin, active=!true}  // All types combined
```

### Field Ordering and Immutability

Structures maintain field insertion order and are completely immutable:

```comp
original = {a=1, b=2, c=3}
modified = {...original, b=20, d=4}    // Creates new structure
// Result: {a=1, b=20, c=3, d=4}
// original remains unchanged: {a=1, b=2, c=3}
```

### Structure Creation Patterns

```comp
// Direct construction
person = {name="Alice", age=30, city="Boston"}

// Construction from variables
$name = "Bob"
$age = 25
person = {name=$name, age=$age, active=!true}

// Construction from function results
config = {
    host = :env:get "HOST" | "localhost"
    port = :env:get "PORT" -> :num:parse | 8080
    debug = :env:get "DEBUG" -> :bool:parse | !false
}
```

## Field Access Patterns

## Field Access Patterns

### Named Field Access

```comp
// Direct access
user.name                    // "Alice"
user."field name"           // Quoted field names with spaces
user.'computed-${suffix}'    // Dynamic field names
user.'$variable'             // Computed access with variables
user.'(expression)'          // Expression-based access

// Safe access with fallbacks
user.nickname | user.name    // Use name if nickname doesn't exist
user.age | 0                 // Default to 0 if age missing
```

### Positional Access

```comp
coordinates = {10.5, 20.3, 5.7}

// Zero-indexed positional access
coordinates#0    // 10.5 (first element)
coordinates#1    // 20.3 (second element)
coordinates#2    // 5.7 (third element)
coordinates#3    // Failure (out of bounds)
coordinates#-1   // Not supported (forward-only indexing)

// Positional access with fallback
coordinates#3 | 0    // 0 (fallback for out of bounds)
```

### Tag Field Access

```comp
status_data = {#priority#high, #status#active, message="Processing"}

// Tag field access
status_data.#priority        // #priority#high
status_data.#status         // #status#active
status_data.message         // "Processing"
```

### Computed Field Access

```comp
$field = "name"
$index = 1

// Variable-based access
user.'$field'               // Same as user.name
coordinates.'#$index'       // Same as coordinates#1

// Expression-based access
user.'(compute_field_name)' // Evaluates expression for field name
data.'($prefix + "_value")' // Concatenated field name
```

### Quoting Rules for Field Access

**Rule**: Only string identifiers and tags can be unquoted field names.

```comp
data.name.first              // Strings: no quotes needed
data.#priority#high          // Tags: no quotes needed  
matrix.'0'.'1'.value         // Numbers: quotes required
settings.'true'.enabled      // Booleans: quotes required
```

## Field Assignment and Modification

### Assignment Operators

Context-aware assignment operators adapt behavior based on usage:

```comp
=     // Normal assignment
*=    // Strong assignment (force/persist, extends structure)
?=    // Weak assignment (only if field doesn't exist)
^=    // Protected assignment
~=    // Override assignment
..=   // Spread assignment (merge operator)
```

### Assignment Behavior Examples

**Named Field Assignment**:
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

**Positional Assignment**:
```comp
coordinates = {10, 20}

// Position exists - normal assignment
coordinates#0 = 15          // {15, 20} - assigns if position exists
coordinates#1 = 25          // {15, 25} - overwrites existing

// Position doesn't exist - behavior depends on operator
coordinates#3 = 30          // Fails - position 3 doesn't exist (silent skip)
coordinates#3 ?= 30         // Skips silently - conditional assignment
coordinates#3 *= 30         // Extends structure: {15, 25, undefined, 30}
```

**Spread Assignment**:
```comp
struct ..= changes           // Additive merge (default)
struct ..?= changes         // Weak merge (won't overwrite existing)
struct ..*= changes         // Strong merge (replace entirely)
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

### Spread Assignment Operators

```comp
..=     // Spread assignment (merge)
..?=    // Weak spread assignment (won't overwrite)
..*=    // Strong spread assignment (replace entirely)
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

```comp
source = {name="Bob", age=25, password="secret", admin=!true}

// Spread all except sensitive fields
public_data = {
    ...{source except password}     // Exclude password
    display_name = source.name
}

// Spread only specific fields
minimal = {
    ...{source only name age}       // Include only name and age
}
```

## Lazy Evaluation

### Lazy Structure Syntax

Square brackets create lazy evaluation blocks:

```comp
// Eager evaluation (immediate)
config = {
    database_url = :env:get "DATABASE_URL"
    max_connections = :env:get "MAX_CONN" -> :num:parse
}

// Lazy evaluation (deferred until accessed)
lazy_config = {
    database_url = [:env:get "DATABASE_URL"]
    max_connections = [:env:get "MAX_CONN" -> :num:parse]
}
```

### Lazy Field Access and Evaluation

```comp
expensive_data = {
    quick_result = 42
    slow_result = [:expensive_computation]
    cached_result = [:cache:get "key" | :expensive_fallback]
}

// Accessing lazy fields triggers evaluation
quick = expensive_data.quick_result    // Immediate: 42
slow = expensive_data.slow_result      // Triggers :expensive_computation
cached = expensive_data.cached_result  // Checks cache first
```

### Lazy Evaluation Context Capture

Lazy blocks capture context at creation time, not evaluation time:

```comp
!func :create_lazy_processor = {
    $multiplier = 10
    @func.base_value = 100
    
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

### Lazy Evaluation with Control Flow

```comp
conditional_data = {
    safe_value = 42
    risky_value = [
        condition ? :safe_operation | :risky_operation
    ]
    fallback_value = [
        :primary_source !> :backup_source
    ]
}

// Only evaluated if accessed
result = conditional_data.risky_value  // Triggers condition check and appropriate operation
```

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

## Advanced Structure Patterns

```comp
## Advanced Structure Patterns

### Structure Composition
user_profile = {
    ...user_basic_info
    ...user_preferences
    ...:load_user_permissions user.id
    computed_field = user.name -> :format_display_name
}

// Conditional composition
admin_profile = {
    ...user_profile
    ...(user.role == "admin" ? admin_permissions | {})
    audit_log = [user.id -> :load_audit_history]
}
```

### Structure Templates

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

### Structure Validation

```comp
// Validation with shape application
!shape ~ValidUser = {
    name ~str|len>0
    age ~num|min=0|max=150
    email ~str|matches=/^[^@]+@[^@]+$/
    active ~bool = !true
}

// Validate and transform
user_data -> {
    @ ~ ValidUser        // Apply shape validation
    -> :assign_user_id   // Add generated ID
    -> :hash_sensitive_data  // Process sensitive fields
}
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

## Performance Considerations

### Structure Sharing and Copy-on-Write

```comp
large_base = {
    // Large structure with many fields
    field1="value1", field2="value2", /* ... many more fields ... */
}

// Efficient - shares structure memory
variant1 = {...large_base, extra="data1"}    // Only copies references
variant2 = {...large_base, extra="data2"}    // Shares base structure
variant3 = {...large_base, field1="new"}     // Copy-on-write for modified field
```

### Lazy Evaluation Optimization

```comp
// Expensive computation only done if needed
cache_config = {
    hit_rate = [statistics.cache_hits / statistics.total_requests]
    miss_penalty = [:analyze_cache_misses]
    optimization_suggestion = [
        cache_config.hit_rate < 0.8 ? "Increase cache size" | "Cache performing well"
    ]
}

// Only compute what's accessed
report = {
    hit_rate = cache_config.hit_rate         // Triggers computation
    // miss_penalty not computed unless accessed
}
```
