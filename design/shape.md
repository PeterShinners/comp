# Shapes, Units, and Type System

*Design for Comp's structural typing, unit system, and shape morphing*

## Overview

Shapes solve the type system problem that most languages get wrong—balancing flexibility with safety. Instead of forcing rigid class hierarchies, shapes use structural compatibility: any data with the right fields works, period. No inheritance ceremonies, no interface implementations, just data that fits.

The shape system integrates with units to provide semantic typing that actually matters. Units attach meaning to numbers and strings—5#meters is different from 5#seconds, and the type system keeps you from accidentally mixing them. Together, shapes and units create a type system that helps instead of hindering.

Shapes and units are a powerful tool for validating API inputs, ensuring dimensional correctness, or transforming between data formats. Comp's approach uses concrete types where morphing operations produce definite typed values rather than inferred types—see [Syntax and Style Guide](syntax.md) for how this affects the entire type system. For information about the tag system that underlies units, see [Tag System](tag.md), and for details about the core primitive types, see [Core Types](type.md).

## Shape Definition and Inheritance

Shapes are defined with the `!shape` operator. Their definition appears similar
to a structure definition, but this is focused on types and default values.

A shape is not a value. It is a referencable part of the module namespace that
is accessed within the module and other modules after !import.

```comp
!shape ~point-2d = {
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

; Positional shapes - fields matched by position, not name
!shape ~pair = {~num ~num}
!shape ~triple = {~str ~num ~bool}

; Mixed named and positional fields
!shape ~labeled = {~str name ~str id ~num}

; Shape composition with multiple inheritance
!shape ~authenticated-user = {
    ..~user
    token ~str
    permissions #permission[]
    last-login ~str = (|now/time)
}
```

Fields in shapes can specify ranges for collections, enabling precise
cardinality constraints. The syntax `[min-max]` defines acceptable element
counts, with shortcuts for common patterns.

```comp
!shape ~config = {
    servers ~server[1-]      ; At least one server
    backups ~backup[0-3]     ; Up to three backups
    nodes ~node[5-10]        ; Between 5 and 10 nodes
    options ~str[]           ; Any number of strings
}
```

### Named vs Positional Fields

Shape fields can be either **named** (matched by field name) or **positional** (matched by position in the structure). This allows shapes to describe both record-like and tuple-like data.

**Named fields** require exact field name matches during morphing:
```comp
!shape ~user = {name ~str age ~num}

{name="Alice" age=30} ~user       ; OK - field names match
{Alice 30} ~user                   ; OK - positional data fills named fields by position
{age=30 name="Alice"} ~user       ; OK - order doesn't matter for named morphing
```

**Positional fields** have no name and match purely by position:
```comp
!shape ~pair = {~num ~num}
!shape ~point = {x ~num y ~num}

{5 10} ~pair         ; OK - two numbers in order
{5 10} ~point        ; OK - fills x=5, y=10 by position
{y=10 x=5} ~point    ; OK - named fields from input match named fields in shape
{10 5} ~pair         ; OK - first positional gets 10, second gets 5
```

**Mixed shapes** combine both, with positional fields typically appearing first:
```comp
!shape ~labeled = {~str name ~str}

{"ID" name="Alice"} ~labeled      ; First positional field gets "ID"
{name="Alice" "ID"} ~labeled      ; Positional field fills from structure position
```

During morphing, the algorithm tries named matches first, then fills remaining fields positionally. This allows flexibility in how data is provided while maintaining type safety.

### Optional Fields via Union Types

Optional fields are expressed using union types with `~nil` and default values, rather than special syntax. This keeps the language orthogonal and avoids giving `~nil` privileged status before patterns emerge organically.

```comp
; Optional field using union + default
!shape ~user = {
    name ~str
    email ~str | ~nil = {}   ; Optional: accepts string or nil, defaults to {}
    age ~num | ~nil = {}     ; Optional: accepts number or nil, defaults to {}
}

; Field names with ? suffix indicate boolean predicates (Ruby idiom)
!shape ~session = {
    user ~str
    active? ~bool = #true    ; Predicate field - the ? is part of the name
    verified? ~bool = #false
}

; Pattern comparison
({name="Alice"} ~user)           ; email and age get {} default
({name="Bob" email="b@x.co"} ~user)  ; age gets {} default
({user="alice" active?=#false} ~session)  ; verified? gets #false default
```

This approach allows the language to evolve based on actual usage patterns. If optional fields prove common enough, shorthand syntax like `~str?` could be added later as sugar for `~str | ~nil`.

## Shape Morphing Algorithm

Shape morphing transforms structures to match shape specifications through a
multi-phase matching process. The algorithm considers field names, types,
positions, and defaults to create the best possible match.

The morphing process follows these phases:
1. **Named field matching** - Exact field name matches are assigned first
2. **Tag field matching** - Fields with matching tag types are assigned
3. **Positional matching** - Remaining fields match by position
4. **Default application** - Unmatched shape fields receive defaults from shape
   definition

```comp
!shape ~connection = {
    host ~str = localhost
    port ~num = 8080
    secure? ~bool = #false
}

; Basic morphing
({example.com 443 #true} ~connection)
; Result: {host=example.com port=443 secure=?#true}

; Morphing with defaults
({host=prod.example.com} ~connection)
; Result: {host=prod.example.com port=8080 secure=?#false}
; port and secure? come from shape defaults

; Function parameters automatically morph
!func |connect ~{conn ~connection} = {
    (Connecting to ${host}:${port} |log)
}
```

## Shape Application Operators

Comp provides two distinct categories of shape operations: **morphing** for data transformation and validation, and **masking** for scope filtering and argument validation. Each serves different purposes in the type system.

### Morphing Operators (`~`)

Morphing transforms data to match shape specifications, restructuring and validating as needed:

```comp
data ~shape             ; Normal morph - apply defaults, allow extra fields
data ~* shape           ; Strong morph - no extra fields allowed, strict matching
data ~? shape           ; Weak morph - missing fields acceptable, partial matching
```

**Normal morph (`~`)** is the default for function parameters and data transformation:
- Applies default values for missing fields
- Ignores extra fields not in the shape
- Restructures data to match the shape (named↔positional)
- Fails if required fields are missing or type mismatches occur

**Strong morph (`~*`)** enforces exact structural conformance:
- Applies default values for missing fields
- **Rejects extra fields** - structure must match shape exactly
- Fails if any fields don't match the shape
- Used for configuration validation and security-critical inputs

**Weak morph (`~?`)** enables partial matching and type testing:
- Does **not** apply default values
- Allows missing fields - partial match is acceptable
- Ignores extra fields not in the shape
- Used primarily for pattern matching and type tests

### Masking Operators (`^`)

Masking filters structures to expose only fields defined in a shape, without transformation or defaults:

```comp
data ^ shape            ; Permissive mask - intersection filter
data ^* shape           ; Strict mask - exact validation with defaults
```

**Permissive mask (`^`)** filters to the intersection of data and shape fields:
- Returns only fields present in **both** the data and the shape
- Does **not** apply defaults for missing fields
- Ignores extra fields silently
- Never fails - returns empty structure if no fields match
- Used for filtering scopes (`$ctx`, `$mod`) to function argument shapes

**Strict mask (`^*`)** validates and completes with defaults:
- Applies default values for missing fields
- **Rejects extra fields** - input must match shape exactly
- Fails if required fields are missing
- Equivalent to strong morph but semantically for "filtering" contexts
- Used automatically for function argument validation

### Comparison: Morph vs Mask

| Feature | Normal Morph `~` | Strong Morph `~*` | Permissive Mask `^` | Strict Mask `^*` |
|---------|------------------|-------------------|---------------------|------------------|
| **Purpose** | Transform data | Exact validation | Filter fields | Exact validation |
| **Extra fields** | Ignore | **FAIL** | **Ignore** | **FAIL** |
| **Missing required** | **FAIL** | **FAIL** | **Ignore** | **FAIL** |
| **Missing + default** | Add default | Add default | **Ignore** | Add default |
| **Restructuring** | Yes | Yes | **No** | **No** |
| **Use case** | Function params | Config validation | Scope filtering | Arg validation |

**Key distinction:** Morphing is about transformation (can restructure data), while masking is about filtering (preserves structure, only removes/validates fields).

### Usage Examples

```comp
!shape ~user = {name ~str email ~str age ~num = 0}

; Normal morph - flexible, forward-compatible
{name="Alice" email="a@example.com"} ~user
; ✅ Result: {name="Alice" email="a@example.com" age=0}

{name="Alice" email="a@example.com" extra="data"} ~user
; ✅ Result: {name="Alice" email="a@example.com" age=0}
; Extra 'extra' field is ignored

; Strong morph - exact structure required
{name="Alice" email="a@example.com" extra="data"} ~* user
; ❌ FAILS: Extra field 'extra' not in shape

; Weak morph - partial matching for tests
{name="Alice"} ~? user
; ✅ Result: {name="Alice"}
; Missing fields acceptable, no defaults applied

; Permissive mask - filter to intersection
{name="Alice" email="a@example.com" extra="data"} ^ user
; ✅ Result: {name="Alice" email="a@example.com"}
; Only fields in both data and shape (no defaults, no 'age')

; Strict mask - validate and complete
{name="Alice" email="a@example.com"} ^* user
; ✅ Result: {name="Alice" email="a@example.com" age=0}
; Adds default, would fail if 'extra' present
```

**Validation is handled through fallback operators**, not separate check operators:

```comp
; Use fallback to handle morph failures
validated = input ~user ?? {#fail message="Invalid user"}

; Conditional processing based on morph success
input ~user ?? default-user |process-user

; Pattern matching with morph attempts
data |match
    :{($in ~user) != #fail} :{$in ~user |handle-user}
    :{($in ~admin) != #fail} :{$in ~admin |handle-admin}
    :{#true} :{|reject}
```

### Union Morphing and Specificity

Unions in morphing use **specificity ranking** to select the best match, not sequential fallback:

```comp
; Union morph - picks most specific match
data ~success | ~error              ; Morph to whichever matches best
value ~num | ~str                   ; Specificity determines which wins

; Order independence (mostly)
~record | ~nil ≈ ~nil | ~record    ; Both try, most specific wins
                                    ; Ties use left-to-right order

; Union composition is safe
!shape ~result = ~success | ~error
!shape ~maybe-result = ~result | ~nil
; Expands to: ~success | ~error | ~nil (order doesn't matter)
```

**Specificity ranking considers:**
- Exact field matches over partial matches
- Named fields over positional fields
- Specific types over generic types (`~num` > `~any`)
- Structural matches over tag matches

This makes unions **order-independent** for practical use - you can reorder union members or compose unions without changing behavior, except for ties where left-to-right order serves as a tiebreaker.

### Specificity Scoring Algorithm

The specificity system uses a **lexicographic scoring tuple** to rank shape matches. When multiple shapes could match the same data (in unions or function overloads), the system compares each component in order until a winner is found.

**Score Tuple: `{named_matches, tag_depth, assignment_weight, positional_matches}`**

1. **Named field matches** - Count of exact field name matches (higher is more specific)
2. **Tag hierarchy depth** - Sum of tag depths for matched tag fields (deeper tags win)
3. **Assignment strength** - Strong assignment (`=*`) scores 1, normal (`=`) scores 0, weak (`=?`) scores -1
4. **Positional matches** - Count of positional field matches (higher is more specific)

The tuple is compared lexicographically: earlier components are more important than later ones. This ensures that a shape matching more named fields always beats one matching fewer, regardless of other factors.

```comp
!shape ~point-2d = {x ~num y ~num}
!shape ~point-3d = {x ~num y ~num z ~num}
!shape ~labeled-point = {x ~num y ~num label ~str}

; Scoring examples for input: {x=5 y=10}
; ~point-2d:       {named=2, tag=0, weight=0, pos=0}
; ~point-3d:       {named=2, tag=0, weight=0, pos=0}  ; Same score - TIE
; ~labeled-point:  {named=2, tag=0, weight=0, pos=0}  ; Same score - TIE

; For input: {x=5 y=10 z=15}
; ~point-2d:       {named=2, tag=0, weight=0, pos=0}
; ~point-3d:       {named=3, tag=0, weight=0, pos=0}  ; WINS - more named matches
; ~labeled-point:  {named=2, tag=0, weight=0, pos=0}

; For input: {5 10}
; ~point-2d:       {named=0, tag=0, weight=0, pos=2}
; ~point-3d:       {named=0, tag=0, weight=0, pos=2}  ; Same score - TIE
```

**Tag depth scoring** gives preference to more specific tags in hierarchies:

```comp
!tag #status = {#active #error}
!tag #error.status = {#network.error #timeout.error}

!shape ~generic = {state #status}           ; Tag depth = 0
!shape ~error-case = {state #error.status}  ; Tag depth = 1
!shape ~network = {state #network.error}    ; Tag depth = 2

; For input: {state=#network.error}
; ~generic:    {named=1, tag=0, weight=0, pos=0}
; ~error-case: {named=1, tag=1, weight=0, pos=0}
; ~network:    {named=1, tag=2, weight=0, pos=0}  ; WINS - deepest tag
```

**Assignment strength** breaks ties between otherwise identical shapes:

```comp
!shape ~config-default = {port ~num = 8080}
!shape ~config-locked = {port ~num =* 8080}

; For input: {port=3000}
; ~config-default: {named=1, tag=0, weight=0, pos=0}
; ~config-locked:  {named=1, tag=0, weight=1, pos=0}  ; WINS - strong assignment
```

**Percentage-based scoring for union morphing:**

When morphing to unions, the system calculates a match percentage for each candidate shape based on how many required fields match:

```comp
!shape ~user = {name ~str email ~str}
!shape ~group = {name ~str members ~user[]}

; Input: {name="Alice" email="a@example.com"}
; ~user:  2/2 required fields match = 100%  ; WINS
; ~group: 1/2 required fields match = 50%

; Input: {name="Admins" members=[]}
; ~user:  1/2 required fields match = 50%
; ~group: 2/2 required fields match = 100%  ; WINS

; Input: {name="Something"}
; ~user:  1/2 required fields match = 50%
; ~group: 1/2 required fields match = 50%   ; ERROR: Ambiguous (tie)
```

**Ambiguity handling:**

When two shapes have identical scores, the system considers the match ambiguous. In unions, this causes a morphing error. In function dispatch, left-to-right definition order breaks the tie (first defined wins), but this should be avoided through explicit assignment strength or shape refinement.

```comp
; Ambiguous union - ERROR at runtime
{name="X"} ~user | ~group
; ERROR: Ambiguous type match
;   Matches ~user with 50% confidence (1/2 fields)
;   Matches ~group with 50% confidence (1/2 fields)

; Resolved with tag discrimination
!shape ~user = {type #user name ~str email ~str}
!shape ~group = {type #group name ~str members ~user[]}

{type=#user name="X"} ~user | ~group  ; Unambiguous - tag depth wins
```

This scoring system creates predictable, composable behavior for both union morphing and function overload dispatch, with the same rules applying to both contexts.

### Function vs Block Morphing Rules

**Function invocation uses loose morphing** - extra fields in arguments are ignored, enabling forward compatibility and optional parameters:

```comp
!func |process ~{x ~num y ~num} = {x + y}
(|process x=1 y=2 z=3)  ; Works - z ignored
```

**Block invocation uses strict morphing** - extra fields cause morphing to fail, preventing accidental capture through closure:

```comp
!shape ~predicate = {test ~:{value ~num}}
@test = :{value > 10}

{value=5 extra="data"} |:@test  ; FAILS - extra field not allowed
{value=5} |:@test               ; Works - exact match
```

This distinction ensures blocks have predictable inputs while functions remain flexible for evolution and extension.

## Shape Constraints

Shapes can define constraints that validate field values beyond basic type
checking. These constraints are checked during morphing and can cause morphing
to fail if violated. Constraints use pure functions that return boolean values
or failure structures.

Constraints are evaluated during morphing, with failures generating descriptive
error structures. This enables precise validation at type boundaries while
maintaining composability.

```comp
!shape ~valid-user = {
    name ~str {min-length=3 max-length=50}
    email ~str {pattern="^[^@]+@[^@]+$"}
    age ~num {min=13 max=120}
    score ~num {validate={$in >= 0 && $in <= 100}}
}

; Constraint functions for complex validation
!pure
!func |valid-username ~{name ~str} = {
    ($in |length/str) >= 3 &&
    ($in |match/str "^[a-z][a-z0-9_]*$") &&
    !($in |contains/reserved-words)
}

!shape ~account = {
    username ~str {validate=|valid-username}
    balance ~num {min=0}
    status #account-status
}
```

## Block Type Signatures

Blocks can be typed through shape definitions that specify their expected input structure. Block fields in shapes use the `:` prefix followed by the input shape definition. This enables type-safe block parameters in functions and clear contracts for stream generators.

```comp
; Block expecting any input
!shape ~transformer = {op ~:{~any}}

; Block expecting specific structure
!shape ~validator = {check ~:{name ~str age ~num}}

; Block expecting no input (streams, generators)
!shape ~generator = {produce ~:{}}

; Block with union input types
!shape ~processor = {handle ~:{~user | ~account}}

; Multiple block parameters
!shape ~repeat-text = {
    count ~num
    op ~:{value ~str}
}

; Usage in function signatures
!func |process ^{transform ~:{~any}} = {
    [data |map ^transform]  ; Block used with map
}

!func |repeat ^{count ~num op ~:{value ~str}} = {
    [count |times :{[value |: ^op]}]
}
```

The `:` prefix makes block fields syntactically distinct from regular fields. The shape after the colon defines what input structure the block expects when invoked. When blocks are typed, they become invocable with the `|:` operator and enforce their input shape through morphing. For detailed coverage of streams, block invocation patterns, and iterator functions, see [Iteration and Streams](loop.md).

## Tag-Based Flag Arguments

Shape morphing with tag fields enables clean flag-style arguments without special syntax. Tag fields automatically match unnamed tag values during morphing, providing type-safe, composable configuration patterns.

```comp
!tag #sort-order = {#asc #desc}
!tag #stability = {#stable #unstable}

!shape ~sort-args = {
    order #sort-order = #asc
    stability #stability = #unstable
}

!func |sort ^~sort-args = {
    ; Tag fields automatically morph from unnamed tags
}

; Clean flag syntax using tags
[data |sort #desc #stable]
; Morphs to: {order=#desc stability=#stable}

[data |sort #stable]
; Morphs to: {order=#asc stability=#stable}

[data |sort]
; Morphs to: {order=#asc stability=#unstable}

; Tags in variables work naturally
@order = #desc
[data |sort @order]

; Conditional tag selection
@order = [reverse? |if :{#true} :{#desc} :{#asc}]
[data |sort @order]

; Pass through arguments
!func |process-sorted ^{order #sort-order = #asc} = {
    [data |sort ^order]  ; Forward the tag
}
```

This pattern leverages existing tag field matching in shape morphing - no special operators needed. The tag hierarchy provides type safety, defaults are explicit in the shape, and tags compose naturally with variables and other language features.

## Spreading Shape Defaults

Shapes can be used in spread operations to apply their default values in both shape definitions and structure literals:

### Spreading in Shape Definitions

```comp
; Define reusable defaults as a shape
!shape ~defaults = {one ~num=1 active ~bool=#true}

; Spread defaults into another shape
!shape ~data = {
    name ~str
    ..~defaults             ; Inherits: one ~num=1, active ~bool=#true
}
; Equivalent to: !shape ~data = {name ~str one ~num=1 active ~bool=#true}

; Multiple spreads for composition
!shape ~timestamped = {created ~str updated ~str}
!shape ~entity = {
    id ~str
    ..~defaults
    ..~timestamped
}
```

### Spreading in Structure Literals

```comp
!shape ~config = {
    port ~num = 8080
    host ~str = "localhost"
    timeout ~num = 30
    api-key ~str           ; No default - not included in spread
}

; Apply defaults from shape
server = {..~config}  ; {port=8080 host="localhost" timeout=30}
custom = {..~config port=3000}  ; Override specific defaults
```

**Two approaches to reusable defaults:**
1. **Type aliases with defaults**: `!shape ~one = ~num=1` - defaults propagate when used as field types
2. **Shape spreading**: `!shape ~defaults = {one ~num=1}; ..~defaults` - fields are directly inherited

Both patterns compose well and serve different use cases.

For detailed information about shape spreading and structure assembly patterns, see [Structures, Spreads, and Lazy Evaluation](structure.md).

The spread operation is purely mechanical - "copy all fields that have defaults"
- while morphing is semantic - "transform this structure to match this shape."
For detailed information about spread operations and structure composition, see
[Structures, Spreads, and Lazy Evaluation](structure.md).

## Shape Masking and Scope Filtering

Shape masking provides a mechanism for filtering structures to only expose fields defined in a shape. Unlike morphing, which transforms and validates data, masking purely filters - keeping the intersection of available fields and shape-defined fields without applying defaults or restructuring.

Masking is central to function argument handling, where it filters the module scope (`$mod`) and context scope (`$ctx`) to only expose fields declared in the function's argument shape. This creates disciplined function boundaries while maintaining flexibility in scope access.

### Permissive Mask (`^`)

The permissive mask operator filters a structure to only include fields present in both the data and the shape:

```comp
!shape ~api-fields = {user ~str session ~str timeout ~num}

; Large scope with many fields
full-scope = {
    user="alice"
    session="abc123"
    timeout=30
    debug=#true
    api-key="secret"
    internal-state="xyz"
}

; Filter to only API-relevant fields
filtered = full-scope ^ ~api-fields
; Result: {user="alice" session="abc123" timeout=30}
; Removed: debug, api-key, internal-state (not in shape)

; No defaults applied for missing fields
partial-data = {user="bob"} ^ ~api-fields
; Result: {user="bob"}
; Missing: session, timeout (not in data, no defaults)

; Empty result if no overlap
{a=1 b=2 c=3} ^ ~api-fields
; Result: {}
```

**Permissive mask behavior:**
- Returns intersection of data fields and shape fields
- Never applies defaults for missing fields
- Never fails - returns empty structure if no matches
- Preserves field values and structure exactly
- Used for scope filtering in function contexts

### Strict Mask (`^*`)

The strict mask operator validates that data exactly matches a shape, applying defaults and failing on mismatches:

```comp
!shape ~config = {host ~str port ~num = 8080 timeout ~num = 30}

; Valid input with defaults
validated = {host="localhost" port=3000} ^* ~config
; ✅ Result: {host="localhost" port=3000 timeout=30}
; Default 'timeout' applied

; Fails on extra fields
{host="localhost" port=3000 debug=#true} ^* ~config
; ❌ FAILS: Extra field 'debug' not in shape

; Fails on missing required fields
{port=8080} ^* ~config
; ❌ FAILS: Missing required field 'host'
```

**Strict mask behavior:**
- Validates exact shape conformance
- Applies defaults for missing fields with defaults
- Fails if extra fields present
- Fails if required fields missing
- Functionally equivalent to strong morph (`~*`)
- Used for function argument validation

### Mask vs Morph Semantics

While strict mask (`^*`) and strong morph (`~*`) are currently functionally equivalent, they represent different semantic intentions:

**Morphing** implies transformation:
- Can restructure data (named ↔ positional fields)
- Emphasis on "converting to match shape"
- Used for data transformation and API boundaries

**Masking** implies filtering:
- Preserves structure, only filters fields
- Emphasis on "exposing subset of available fields"
- Used for scope management and access control

```comp
; Morph - may restructure
{5 10} ~point-2d        ; Positional → named fields {x=5 y=10}

; Mask - preserves structure
{x=5 y=10 z=15} ^ point-2d   ; Removes z, keeps {x=5 y=10}
```

This semantic distinction guides appropriate use: morphing for data transformation, masking for scope discipline and argument validation.

### Masking in Function Contexts

Function argument shapes automatically apply masking to create disciplined scope access. This is covered in detail in [Functions and Blocks](function.md), but the basic pattern is:

```comp
!func |process ^{x ~num y ~num timeout ~num = 30} = {
    ; Automatic masking at function entry:
    ; $arg = passed_args ^* {x ~num y ~num timeout ~num = 30}
    ; $ctx_local = $ctx_shared ^ {x ~num y ~num timeout ~num = 30}
    ; $mod_local = $mod_shared ^ {x ~num y ~num timeout ~num = 30}

    ^x          ; Reads from union: $arg > $ctx > $mod
    $ctx.data   ; Can write to $ctx (adds to both local and shared)
}
```

The mask operators (`^` and `^*`) provide explicit access to the same filtering behavior used automatically in function argument processing, enabling manual scope filtering and validation patterns.

## Unit System Fundamentals

Units provide semantic typing for primitive values through the tag system. Units
are implemented as tag hierarchies with conversion rules, enabling type-safe
operations and automatic conversions. The standard library provides
comprehensive units through the `unit/` module.

```comp
!import /unit = std "core/unit"

; Units as tags
distance = 5#kilometer      ; Using shortened form
duration = 30#second
temp = 20#celsius

; Automatic conversion in operations
total = 5#meter + 10#foot         ; Result in meters
speed = 100#kilometer / 1#hour    ; Compound unit

; Explicit conversion
meters = distance ~num#meter     ; 5000
feet = distance ~num#foot        ; ~16404
kelvin = temp ~num#kelvin        ; 293.15
```

Units follow algebraic rules:
- Addition/subtraction require compatible units
- First operand's unit determines result unit
- Multiplication/division create compound units
- Incompatible operations fail immediately

## String Units and Domain Validation

String units provide semantic typing and validation for string values. They can
enforce formats, apply transformations, and control escaping in templates.
String units are particularly valuable for security, ensuring proper escaping
based on context.

```comp
!tag #email ~str = {
    validate = |match/str "^[^@]+@[^@]+$"
    normalize = |lowercase/str
}

!tag #sql ~str = {
    escape = |escape-literal/sql
    validate = |check-syntax/sql
}

!tag #html ~str = {
    escape = |escape-entities/html
    sanitize = |remove-scripts/html
}

; Usage with automatic validation
address = "User@Example.COM"#email
normalized = address ~str#email    ; user@example.com

; Template safety through units
query = SELECT * FROM users WHERE id = ${id}#sql
html = <h1>${title}</h1>#html
; Units ensure proper escaping in templates
```

## Union and Conditional Shapes

Shapes can be combined with `|` to create union types that accept multiple
structures. This enables flexible APIs that handle different input formats while
maintaining type safety. Union shapes are particularly useful for result types
and variant handling.

```comp
!shape ~result = ~success | ~error
!shape ~success = {value ~any}
!shape ~error = {#fail message ~str}

!shape ~config-source = ~file-config | ~env-config | ~default-config
!shape ~file-config = {path ~str}
!shape ~env-config = {prefix ~str}
!shape ~default-config = {}

; Conditional shape selection
!func |process ~{input} = {
    $in |match
        {$in ~? success} {value |handle-success}
        {$in ~? error} {message |log-error}
}
```

## Shape-Based Pattern Matching

Shapes integrate with pattern matching to enable type-directed control flow. The
`~?` operator tests shape compatibility, while morphing operations transform
data for processing. This creates elegant APIs where function behavior adapts to
input structure. For comprehensive information about pattern matching and
control flow patterns, see [Pipelines, Flow Control, and Failure
Handling](pipeline.md).

```comp
!shape ~get-request = {method=#get path ~str}
!shape ~post-request = {method=#post path ~str body ~any}
!shape ~delete-request = {method=#delete path ~str}

!func |handle-request ~{request} = {
    $in |match
        :{$in ~? get-request} :{
            $in ~get-request |fetch-resource
        }
        :{$in ~? post-request} :{
            $in ~post-request |create-resource
        }
        :{$in ~? delete-request} :{
            $in ~delete-request |delete-resource
        }
        :{#true} :{
            {#http.fail status=405 message=Method not allowed}
        }
}
```

## Performance Optimization

Shape operations can be optimized through caching and compilation. Repeated
morphing operations with the same shape benefit from cached validation rules.
The runtime can compile shape definitions into efficient validators,
particularly for shapes with complex constraints.

When this happens, the language understands the types used by fields,
which allows faster code paths in successive uses.

```comp
; Shapes used in hot paths should be pre-compiled
!shape ~hot-path = {
    data ~str {validate=|complex-validation}
    timestamp ~num {min=0}
    flags #flag[]
}

; First use compiles validation rules
first-result = input ~hot-path      ; Compiles and caches

; Subsequent uses reuse compiled rules
loop-results = items |map {$in ~hot-path}  ; Fast validation
```
