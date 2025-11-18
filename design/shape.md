# Shape System

Shapes define structural types for data validation and transformation. Instead
of rigid class hierarchies, shapes use structural compatibility: any data with
the right fields matches. No inheritance ceremonies, no interface
implementations—just data that fits.

The shape system integrates with units to provide semantic typing. Units attach
meaning to values: `5#meter` is different from `5#second`, and the type system
prevents mixing them. Together, shapes and units create compile-time validation
without runtime overhead.

For information about the tag system underlying units, see [Tag System](tag.md).
For primitive types, see [Core Types](type.md).

## Shape Definition

Shapes are defined with `shape` and referenced with `~` prefix. They specify
field types and defaults:

```comp
shape ~point = {
    x ~num = 0
    y ~num = 0
}

!shape ~point-3d = {
    ..~point-2d              ; Inherit x, y fields
    z ~num = 0              ; Add z coordinate
}

!shape ~user = {
    name ~str
    email ~str
    age ~num = 0
    active? ~bool = #true    ; ? suffix for boolean predicate (Ruby idiom)
    tags #user-tag[]         ; Array of specific tags
}

; Shape composition through spreading
shape ~point-3d = {
    ..~point
    z ~num = 0
}

; Array constraints
shape ~config = {
    servers ~server[1-]    ; At least one
    backups ~backup[0-3]   ; Up to three
    options ~str[]         ; Any number
}
```

Shapes can be module-private by adding `&` suffix: `shape ~internal-config& =
{...}`

### Named vs Positional Fields

Shape fields can be **named** (matched by name) or **positional** (matched by
position):

```comp
; Named fields
shape ~user = {name ~str age ~num}
{name="Alice" age=30} ~user      ; Named match
{"Alice" 30} ~user               ; Positional fills named

; Positional fields
shape ~pair = {~num ~num}
{5 10} ~pair                     ; Matched by position

; Mixed
shape ~labeled = {~str name ~str}
{"ID" name="Alice"} ~labeled     ; Positional then named
```

Morphing tries named matches first, then fills remaining fields by position.

### Optional Fields

Optional fields use union types with `~nil` and defaults:

```comp
shape ~user = {
    name ~str
    email ~str | ~nil = {}
    age ~num | ~nil = {}
}

; Usage
{name="Alice"} ~user
; Result: {name="Alice" email={} age={}}

{name="Bob" email="bob@example.com"} ~user
; Result: {name="Bob" email="bob@example.com" age={}}
```

The `?` suffix on field names indicates boolean predicates (convention, not
syntax):

```comp
shape ~session = {
    user ~str
    active? ~bool = #true
    verified? ~bool = #false
}
```

## Shape Morphing

Morphing transforms data to match shapes through a multi-phase process:

1. **Named field matching** - Exact field names matched first
2. **Handle field matching** - Fields with matching handle types
3. **Tag field matching** - Fields with matching tag types
4. **Positional matching** - Remaining fields by position
5. **Default application** - Missing fields get defaults

```comp
shape ~connection = {
    host ~str = "localhost"
    port ~num = 8080
    secure? ~bool = #false
}

; Morphing examples
{"example.com" 443 #true} ~connection
; Result: {host="example.com" port=443 secure?=#true}

{host="prod.example.com"} ~connection
; Result: {host="prod.example.com" port=8080 secure?=#false}

; Function parameters auto-morph
func connect ~{conn ~connection} 
(
    "Connecting to %{host}:%{port}" | log
)
```

## Morphing Operators

Three operators control morphing strictness:

```comp
data ~shape      ; Normal - apply defaults, allow extra fields
data ~*shape     ; Strong - no extra fields, strict matching
data ~?shape     ; Weak - missing fields ok, partial matching
```

Validation uses fallback operators:

```comp
; Handle morph failures
validated = input ~user ?? {#fail message="Invalid user"}

; Provide defaults
input ~user ?? default-user | process-user

; Pattern matching
data | match
    :(it ~?user) :(it ~user | handle-user)
    :(it ~?admin) :(it ~admin | handle-admin)
    :(#true) :(reject)
```

### Union Morphing

Unions use **specificity ranking** to select the best match:

```comp
data ~success | ~error   ; Picks most specific match
value ~num | ~str        ; Specificity determines winner

; Union composition
shape ~result = ~success | ~error
shape ~maybe = ~result | ~nil
; Expands to: ~success | ~error | ~nil
```

**Specificity ranking:**
- Exact field matches beat partial matches
- Named fields beat positional fields
- Specific types beat generic types (`~num` > `~any`)
- Deeper tag/handle hierarchies beat shallower ones

Order doesn't matter except for ties (left-to-right tiebreaker).

### Specificity Scoring

Specificity uses a lexicographic tuple: `(named_matches, combined_depth,
positional_matches)`

- **Named matches** beat everything else
- **Depth** comes from tag/handle hierarchies (deeper = more specific)
- **Positional matches** provide final tiebreaker

```comp
tag #status = {#active #error}
tag #error.status = {#network #timeout}

shape ~generic = {state #status}
shape ~specific = {state #network.error}

{state=#network.error} ~generic | ~specific
; Result: ~specific wins (deeper tag hierarchy)
```

**Ambiguous matches cause errors:**

```comp
shape ~user = {name ~str email ~str}
shape ~group = {name ~str members ~user[]}

{name="X"} ~user | ~group
; ERROR: Ambiguous - both match 50%

; Resolve with discriminator tag
shape ~user = {type #user name ~str email ~str}
shape ~group = {type #group name ~str members ~user[]}

{type=#user name="X"} ~user | ~group  ; Unambiguous
```

### Function vs Block Morphing

**Functions use loose morphing** - extra fields ignored:

```comp
func process ~{x ~num y ~num} (x + y)
process {x=1 y=2 z=3}  ; Works - z ignored
```

**Blocks use strict morphing** - extra fields fail:

```comp
let test = :(value > 10)
{value=5 extra="data"} |: test  ; FAILS
{value=5} |: test               ; Works
```

## Shape Constraints

Constraints validate field values during morphing:

```comp
shape ~valid-user = {
    name ~str {min-length=3 max-length=50}
    email ~str {pattern="^[^@]+@[^@]+$"}
    age ~num {min=13 max=120}
}

; Custom validation functions
pure func valid-username ~{name ~str}
(
    (name | length/str) >= 3 && 
    (name | match/str "^[a-z][a-z0-9_]*$")
)

shape ~account = {
    username ~str {validate=valid-username}
    balance ~num {min=0}
}
```

## Block Type Signatures

Blocks in shapes use `:` prefix with their expected input shape:

```comp
; Block types
shape ~transformer = {op ~:{~any}}
shape ~validator = {check ~:{name ~str age ~num}}
shape ~generator = {produce ~:{}}

; Usage
func process arg ~{transform ~:{~any}}
(
    data | map arg.transform
)

func repeat arg ~{count ~num op ~:{value ~str}}
(
    count | times :(value |: arg.op)
)
```

For iteration patterns and streams, see [Iteration and Streams](loop.md).

## Tag-Based Flag Arguments

Tag fields enable clean flag-style arguments:

```comp
tag #sort-order = {#asc #desc}
tag #stability = {#stable #unstable}

shape ~sort-args = {
    order #sort-order = #asc
    stability #stability = #unstable
}

func sort arg ~sort-args (...)

; Usage
data | sort #desc #stable  ; Morphs to {order=#desc stability=#stable}
data | sort #stable        ; Morphs to {order=#asc stability=#stable}
data | sort                ; Uses defaults

; Tags compose with variables
let order = #desc
data | sort order
```

## Spreading Shape Defaults

Spread shapes to apply their defaults:

```comp
; Shape spreading
shape ~defaults = {one ~num=1 active ~bool=#true}

shape ~data = {
    name ~str
    ..~defaults
}

; Structure literals
shape ~config = {
    port ~num = 8080
    host ~str = "localhost"
    timeout ~num = 30
}

server = {..~config}           ; Apply all defaults
custom = {..~config port=3000} ; Override specific
```

Spreading copies defaults mechanically; morphing transforms semantically. See
[Structures](struct.md) for composition patterns.

## Unit System

Units provide semantic typing through tags:

```comp
import unit std "core/unit"

; Units attach to values
distance = 5#kilometer
duration = 30#second

; Automatic conversion
total = 5#meter + 10#foot      ; Result in meters
speed = 100#kilometer / 1#hour ; Compound unit

; Explicit conversion
meters = distance ~num#meter   ; 5000
```

**Rules:**
- Addition/subtraction require compatible units
- First operand determines result unit
- Multiplication/division create compound units

See [Units](unit.md) for full details.

## String Units

String units validate and transform strings:

```comp
tag #email ~str = {
    validate = match/str "^[^@]+@[^@]+$"
    normalize = lowercase/str
}

; Usage
address = "User@Example.COM"#email
normalized = address ~str#email  ; user@example.com

; Template safety
query = "SELECT * FROM users WHERE id = %{id}"#sql
html = "<h1>%{title}</h1>"#html
; Units ensure proper escaping
```

See [Units](unit.md) for more on string units and security.

## Union Shapes

Combine shapes with `|` for variant types:

```comp
shape ~result = ~success | ~error
shape ~success = {value ~any}
shape ~error = {#fail message ~str}

; Pattern matching
func process ~{input}
(
    input | match
        :(it ~?success) :(value | handle-success)
        :(it ~?error) :(message | log-error)
)
```

## Pattern Matching with Shapes

Use `~?` for shape-based pattern matching:

```comp
shape ~get = {method=#get path ~str}
shape ~post = {method=#post path ~str body ~any}
shape ~delete = {method=#delete path ~str}

func handle-request ~{request}
(
    request | match
        :(it ~?get) :(it ~get | fetch-resource)
        :(it ~?post) :(it ~post | create-resource)
        :(it ~?delete) :(it ~delete | delete-resource)
        :(#true) :({#http.fail status=405 message="Method not allowed"})
)
```

See [Pipelines](pipeline.md) for control flow patterns.

## Performance

Shape operations are optimized through caching and compilation. The first use
compiles validation rules; subsequent uses reuse them. This makes repeated
morphing in hot paths efficient without manual optimization.
