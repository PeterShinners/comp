# Phase 12: Shape Definitions

**Status**: 📋 **PLANNED**  
**Created**: October 2025

## Overview

This phase implements shape definitions and operations, building on the module-level grammar foundation from Phase 11. Shapes provide structural typing for Comp, enabling type validation, data transformation, and API contracts without rigid class hierarchies.

### What's Included in This Phase

**Core Shape Features**:
- Top-level shape definitions with `!shape`
- Inline shape definitions (shape literals)
- Shape morph operators: `~`, `~*`, `~?` (postfix modifiers)
- Shape references (using `~shapename`)
- Tag references where shapes expected (#tag as inline shape)
- Positional fields (no field names, matched by position)
- Type aliases with defaults (`!shape ~one = ~num=1`)
- Shape spread in definitions (`..~shape`)
- Structure spread in literals (`..{struct}`)
- Union shapes with `|` operator and specificity ranking
- Block field syntax (`field ~:{input_shape}`)

**Explicitly Deferred**:
- Shape check operators: `~?`, `~*?`, `~?? ` (removed - use morph with fallback)
- Shape constraints (`{min=0 max=100}`)
- Size constraints with `[]` (e.g., `~str[1-10]`)
- Unit definitions and references
- Performance optimization/caching
- Runtime morphing implementation

## Shape Definition Syntax

Shapes are defined at module level using the `!shape` operator, similar to tag definitions but with field type specifications.

### Simple Shape Definitions

```comp
; Basic shape with typed fields
!shape ~point-2d = {
    x ~num = 0
    y ~num = 0
}

; Shape with various field types
!shape ~user = {
    name ~str
    email ~str
    age ~num = 0
    active? ~bool = #true     ; ? suffix for boolean predicate (Ruby idiom)
    tags #user-tag            ; Tag reference as type
}

; Positional shapes (no field names - matched by position)
!shape ~pair = {~num ~num}
!shape ~triple = {~str ~num ~bool}

; Mixed named and positional fields
!shape ~labeled = {~str name ~str id ~num}

; Shape inheritance via spread
!shape ~point-3d = {
    ..~point-2d              ; Inherit x, y fields
    z ~num = 0              ; Add z coordinate
}

; Multiple inheritance
!shape ~authenticated-user = {
    ..~user
    token ~str
    permissions #permission
}
```

### Inline Shape Definitions

Shapes can be defined inline wherever a shape reference is expected. Shape definitions are naturally recursive - field types can themselves be inline shape definitions:

```comp
; Inline in function signature with named fields
!func |process ^{x ~num y ~num} = {x + y}

; Inline positional shape (no field names)
!func |add ^{~num ~num} = {$0 + $1}

; Inline in morph operation
data ~{name ~str age ~num}

; Positional inline shapes
{5 10} ~{~num ~num}        ; Morph to pair of numbers
{hello 42 #true} ~{~str ~num ~bool}  ; Triple

; Inline with defaults
value ~{x ~num = 0 y ~num = 0}

; Recursive inline shapes - shapes within shapes
!shape ~circle = {
    pos ~{x ~num y ~num}    ; Nested inline shape
    radius ~num
}

; Deeply nested
!shape ~scene = {
    camera ~{
        pos ~{x ~num y ~num z ~num}
        target ~{x ~num y ~num z ~num}
    }
    objects ~list
}

; Block types use : prefix with input shape
!shape ~validator = {check ~:{x ~num y ~num}}
!shape ~transformer = {op ~:{~any}}
!shape ~generator = {produce ~:{}}

; Tag as inline shape (tag reference treated as shape)
status #active              ; Using tag as value
data ~#user-status         ; Using tag as shape (any #user-status works)
```

### Type Aliases with Defaults

Shape definitions can create type aliases with embedded default values. When these aliased shapes are used as field types, the default is inherited:

```comp
; Simple type aliases
!shape ~number = ~num
!shape ~text = ~str

; Type aliases with defaults
!shape ~one = ~num=1
!shape ~zero = ~num=0  
!shape ~active = #bool=#true
!shape ~empty-text = ~str=""

; Using aliases in shapes - defaults are inherited
!shape ~counter = {
    count ~one              ; Field gets default value 1 from ~one alias
    step ~one
    offset ~zero            ; Field gets default value 0 from ~zero alias
}

!shape ~widget = {
    enabled ~active         ; Field gets default #true from ~active alias
    label ~text             ; No default from ~text (it has none)
}

; The defaults propagate through the type system
({} ~counter)              ; Result: {count=1 step=1 offset=0}
({count=5} ~counter)       ; Result: {count=5 step=1 offset=0}

; Comprehensive example - defaults cascade through type aliases
!shape ~one = ~num=1
!shape ~active = #bool=#true

!shape ~data = {
    name ~str
    count ~one              ; Inherits default=1 from ~one
    active ~active          ; Inherits default=#true from ~active
}

({name="test"} ~data)      ; Result: {name="test" count=1 active=#true}
```

### Union Shapes

Union shapes accept multiple alternative structures:

```comp
!shape ~result = ~success | ~error
!shape ~success = {value ~any}
!shape ~error = {#fail message ~str}

!shape ~config-source = ~file-config | ~env-config | ~default-config
!shape ~file-config = {path ~str}
!shape ~env-config = {prefix ~str}
!shape ~default-config = {}

; Using unions
data ~result                ; Must match ~success or ~error
config ~config-source       ; Must match one of three shapes
```

### Recursive Shape Definitions

Shape definitions are naturally recursive - any field type can be an inline shape definition:

```comp
; Nested structures
!shape ~circle = {
    pos ~{x ~num y ~num}     ; Inline shape as field type
    radius ~num
}

; Deep nesting
!shape ~transform = {
    translate ~{x ~num y ~num z ~num}
    rotate ~{x ~num y ~num z ~num}
    scale ~{x ~num = 1 y ~num = 1 z ~num = 1}
}

; Blocks use : prefix with input shape
!shape ~validator = {check ~:{x ~num y ~num}}
!shape ~mapper = {op ~:{~any}}
!shape ~filter = {test ~:{item ~any}}

; Mix of references and inline
!shape ~entity = {
    id ~str
    transform ~transform     ; Reference to shape above
    physics ~{
        velocity ~{x ~num y ~num}
        mass ~num
    }
}
```

## Shape Morph Operators

Shape morphing transforms structures to match shape specifications:

### Morph Operations

```comp
; Normal morph - applies defaults, allows extra fields
data ~shape                 ; Transform to match shape

; Strong morph - no extra fields allowed
data *~shape                ; Strict matching only

; Weak morph - missing fields acceptable
data ?~shape                ; Partial matching OK

; Examples
{x=1 y=2 z=3} ~point-2d     ; {x=1 y=2} - z ignored
{x=1 y=2 z=3} *~point-2d    ; FAILS - extra field z
{x=1} ~point-2d             ; {x=1 y=0} - y gets default
{x=1} *~point-2d            ; FAILS - missing required field
{x=1} ?~point-2d            ; {x=1} - partial OK
```

### Check Operations

Shape check operators return `#true` or `#false`:

```comp
; Normal check - can morph with defaults?
data ~? shape               ; Returns #true or #false

; Strong check - can morph strictly?
data *~? shape              ; No extra fields?

; Weak check - can morph weakly?
data ?~? shape              ; Has minimum fields?

; Examples
{x=1 y=2 z=3} ~? point-2d   ; #true
{x=1 y=2 z=3} *~? point-2d  ; #false - has extra
{x=1} ~? point-2d           ; #true - can apply defaults
{x=1} *~? point-2d          ; #false - missing required
```

## Shape Spreading

Shapes can be spread in both shape definitions and structure literals:

### In Shape Definitions

```comp
!shape ~base = {x ~num y ~num}
!shape ~extended = {
    ..~base                 ; Inherit x, y
    z ~num                  ; Add z
}

!shape ~multi = {
    ..~base
    ..~timestamped
    status #status
}

; Spreading shapes with defaults - defaults are inherited
!shape ~defaults = {one ~num=1 active ~bool=#true}
!shape ~data = {
    name ~str
    ..~defaults             ; Inherits: one ~num=1, active ~bool=#true
}
; Equivalent to: !shape ~data = {name ~str one ~num=1 active ~bool=#true}
```

### In Structure Literals

```comp
!shape ~config = {
    port ~num = 8080
    host ~str = "localhost"
    timeout ~num = 30
}

; Apply defaults from shape
server = {..~config}                     ; All defaults
custom = {..~config port=3000}           ; Override port
partial = {?..~config host="remote"}     ; Weak spread
```

## Grammar Design

### Module-Level Shape Definition

```lark
// Shape definition token
BANG_SHAPE: "!shape"

// Shape definition syntax
shape_definition: BANG_SHAPE shape_reference ASSIGN shape_body

// Shape references
shape_reference: TILDE TOKEN                    // ~shapename
               | TILDE TOKEN DOT TOKEN          // ~module.shapename

// Shape body (similar to structure but with types)
shape_body: LBRACE shape_field* RBRACE          // Structure: {fields...}
          | shape_type [ASSIGN expression]      // Type alias with optional default: ~num=1 or ~num

shape_field: shape_spread                       // ..~shape
           | identifier shape_type [ASSIGN expression]  // named field: field ~type = default
           | identifier COLON shape_body [ASSIGN expression]  // block field: field ~:{...} = default
           | shape_type [ASSIGN expression]     // positional field: ~type (no name)

shape_spread: SPREAD shape_reference            // ..~shape
            | SPREAD QUESTION shape_reference   // ?..~shape (weak)
            | SPREAD STRONG shape_reference     // !..~shape (strong)

shape_type: shape_reference                     // ~typename
          | tag_reference                       // #tagname (tag as type)
          | TILDE LBRACE shape_body RBRACE      // ~{...} inline shape
          | shape_union                         // ~type1 | ~type2

shape_union: shape_type (PIPE shape_type)+

COLON: ":"
```

### Shape Operators in Expressions

```lark
// Morph operators
morph_expr: expression TILDE shape_type         // data ~shape
          | expression STAR_TILDE shape_type    // data *~shape
          | expression QUESTION_TILDE shape_type // data ?~shape

// Check operators
check_expr: expression TILDE_QUESTION shape_type    // data ~? shape
          | expression STAR_TILDE_QUESTION shape_type // data *~? shape
          | expression QUESTION_TILDE_QUESTION shape_type // data ?~? shape

// New tokens
TILDE: "~"
STAR_TILDE: "*~"
QUESTION_TILDE: "?~"
TILDE_QUESTION: "~?"
STAR_TILDE_QUESTION: "*~?"
QUESTION_TILDE_QUESTION: "?~?"
PIPE: "|"  // For union types
```

## AST Node Design

### Module-Level Nodes

```python
class ShapeDefinition(AstNode):
    """Shape definition at module level: !shape ~name = {...} or !shape ~name = ~type=default
    
    Can define:
    - Structural shapes: !shape ~point = {x ~num y ~num}
    - Type aliases: !shape ~number = ~num
    - Type aliases with defaults: !shape ~one = ~num=1
    - Union shapes: !shape ~result = ~success | ~error
    """
    
    def __init__(self, name: str, body: AstNode | None = None, default: AstNode | None = None):
        self.name = name        # Shape name (without ~)
        self.body = body        # ShapeBody, ShapeReference, ShapeUnion, or shape_type
        self.default = default  # Default value if this is a typed alias with default
        super().__init__()
    
    def unparse(self) -> str:
        if not self.body:
            return f"!shape ~{self.name}"
        result = f"!shape ~{self.name} = {self.body.unparse()}"
        if self.default:
            result += f"={self.default.unparse()}"
        return result
    
    @classmethod
    def fromGrammar(cls, tree):
        # Extract shape name and body from grammar tree
        pass


class ShapeBody(AstNode):
    """Shape body with fields: {x ~num y ~str = "default"}"""
    
    def unparse(self) -> str:
        fields = " ".join(kid.unparse() for kid in self.kids)
        return f"{{{fields}}}"


class ShapeField(AstNode):
    """Single field in shape: name ~type = default or name ~:{...} for blocks
    
    Fields can be named or positional:
    - Named: name ~type or name? ~type (? for boolean predicates, Ruby idiom)
    - Positional: ~type (no name, matched by position)
    - Block: name ~:{input_shape} (blocks with typed inputs)
    """
    
    def __init__(self, name: str | None = None, type_ref: AstNode | None = None,
                 default: AstNode | None = None, is_block: bool = False):
        self.name = name               # Field name (can include ? for predicates), or None for positional
        self.type_ref = type_ref      # ShapeReference, TagRef, ShapeBody (for blocks), or None
        self.default = default         # Default value expression
        self.is_block = is_block       # True if this is a block field (uses : prefix)
        super().__init__()
    
    def unparse(self) -> str:
        if not self.name:
            # Positional field: just the type
            result = self.type_ref.unparse() if self.type_ref else ""
        else:
            result = self.name
            if self.is_block:
                # Block field: name ~:{...}
                result += f" ~:{{{self.type_ref.unparse()}}}" if self.type_ref else " ~:{}"
            elif self.type_ref:
                result += f" {self.type_ref.unparse()}"
        
        if self.default:
            result += f" = {self.default.unparse()}"
        return result


class ShapeSpread(AstNode):
    """Shape spread in definition: ..~shape"""
    
    def __init__(self, shape: AstNode, mode: str = "normal"):
        self.shape = shape      # ShapeReference
        self.mode = mode        # "normal", "weak", "strong"
        super().__init__()
    
    def unparse(self) -> str:
        prefix = "?.." if self.mode == "weak" else "!.." if self.mode == "strong" else ".."
        return f"{prefix}{self.shape.unparse()}"


class ShapeUnion(AstNode):
    """Union of multiple shapes: ~shape1 | ~shape2"""
    
    def unparse(self) -> str:
        return " | ".join(kid.unparse() for kid in self.kids)
```

### Expression-Level Nodes

```python
class ShapeReference(AstNode):
    """Reference to a shape: ~shapename or ~module.shapename"""
    
    def __init__(self, name: str, module: str | None = None):
        self.name = name
        self.module = module
        super().__init__()
    
    def unparse(self) -> str:
        if self.module:
            return f"~{self.module}.{self.name}"
        return f"~{self.name}"


class MorphOp(AstNode):
    """Shape morph operation: data ~shape"""
    
    def __init__(self, mode: str = "normal"):
        self.mode = mode  # "normal" (~), "strong" (*~), "weak" (?~)
        super().__init__()
    
    @property
    def expr(self):
        return self.kids[0] if self.kids else None
    
    @property
    def shape(self):
        return self.kids[1] if len(self.kids) > 1 else None
    
    def unparse(self) -> str:
        expr_str = self.expr.unparse() if self.expr else ""
        shape_str = self.shape.unparse() if self.shape else ""
        
        op = "~" if self.mode == "normal" else f"~{self.mode[0]}"
        return f"{expr_str} {op} {shape_str}"
```

## Implementation Strategy

### Phase 1: Basic Infrastructure
1. Add shape tokens to lexer (BANG_SHAPE, TILDE, etc.)
2. Implement shape_definition grammar rule
3. Create ShapeDefinition and ShapeReference AST nodes
4. Add transformer cases for shape_definition
5. Test simple shape definitions

### Phase 2: Shape Bodies and Fields
1. Implement shape_body and shape_field grammar
2. Create ShapeBody and ShapeField AST nodes
3. Add support for type references in fields
4. Add support for positional fields (no name)
5. Add support for type aliases with defaults
6. Test shape definitions with typed fields and defaults

### Phase 3: Shape Operators
1. Add morph operator tokens (`~`, `~*`, `~?`)
2. Implement morph_expr grammar
3. Create MorphOp AST node with expr/shape properties
4. Test basic morph operations with different modes

### Phase 4: Advanced Features
1. Implement shape_union grammar
2. Create ShapeUnion AST node
3. Add shape spreading in definitions
4. Add structure spreading in literals
5. Add block field syntax (`~:{...}`)
6. Test union shapes, spreading, and block fields

## Test Strategy

### Valid Shape Definitions

```python
@comptest.params(
    "code",
    simple=("!shape ~point = {x ~num y ~num}",),
    defaults=("!shape ~point = {x ~num = 0 y ~num = 0}",),
    predicate=("!shape ~user = {name ~str active? ~bool}",),  # ? for boolean predicate
    tag_type=("!shape ~status = {value #active}",),
    spread=("!shape ~point3d = {..~point z ~num}",),
    union=("!shape ~result = ~success | ~error",),
    block=("!shape ~validator = {check ~:{x ~num}}",),
    block_any=("!shape ~transformer = {op ~:{~any}}",),
    block_empty=("!shape ~generator = {produce ~:{}}",),
    nested=("!shape ~circle = {pos ~{x ~num y ~num} radius ~num}",),
    deep_nested=("!shape ~transform = {translate ~{x ~num y ~num z ~num}}",),
    block_with_default=("!shape ~repeat = {count ~num op ~:{value ~str}}",),
    optional_via_union=("!shape ~config = {host ~str | ~nil = {}}",),  # Optional via union + default
    alias_with_default=("!shape ~one = ~num=1",),  # Type alias with default
    tag_alias_with_default=("!shape ~active = #bool=#true",),  # Tag alias with default
)
)
def test_valid_shape_definitions(key, code):
    result = comp.parse_module(code)
    assert isinstance(result, comp.Module)
    assert len(result.statements) > 0
    assert isinstance(result.statements[0], comp.ShapeDefinition)
    comptest.roundtrip(result)
```

### Shape Operators

```python
@comptest.params(
    "code",
    morph=("data ~shape",),
    strong_morph=("data *~shape",),
    weak_morph=("data ?~shape",),
    check=("data ~? shape",),
    strong_check=("data *~? shape",),
    weak_check=("data ?~? shape",),
    inline_shape=("data ~{x ~num y ~num}",),
    tag_as_shape=("value ~#status",),
)
def test_shape_operators(key, code):
    result = comp.parse_expr(code)
    assert result is not None
    comptest.roundtrip(result)
```

### Invalid Shape Syntax

```python
@comptest.params(
    "code",
    missing_body=("!shape ~point",),  # Might be valid alias
    bad_field=("!shape ~x = {field}",),  # No type
    nested_shape_def=("{!shape ~x = {}}",),  # In structure
)
def test_invalid_shape_syntax(key, code):
    comptest.invalid_parse(code, match=r"parse error|unexpected")
```

## Success Criteria

### Shape Definitions
- ✅ Parse simple shape definitions: `!shape ~point = {x ~num y ~num}`
- ✅ Parse shapes with defaults: `!shape ~point = {x ~num = 0}`
- ✅ Parse type aliases: `!shape ~number = ~num`
- ✅ Parse type aliases with defaults: `!shape ~one = ~num=1`
- ✅ Parse field names with `?` suffix: `active? ~bool` (boolean predicates, Ruby idiom)
- ✅ Parse positional fields: `!shape ~pair = {~num ~num}` (no field names)
- ✅ Parse mixed named/positional: `!shape ~mixed = {~str name ~str}`
- ✅ Parse shape inheritance: `!shape ~point3d = {..~point z ~num}`
- ✅ Parse union shapes: `!shape ~result = ~success | ~error`
- ✅ Parse optional fields via union: `email ~str | ~nil = {}`
- ✅ Round-trip all shape definitions

### Shape Operators
- ✅ Parse morph operators: `~`, `*~`, `?~`
- ✅ Parse inline shape definitions: `data ~{x ~num}`
- ✅ Round-trip all operator expressions

### Shape Spreading
- ✅ Parse shape spread in definitions: `..~shape`
- ✅ Parse spread modes: `..`, `?..`, `!..`
- ✅ Parse structure spread in literals: `{..struct}`

### Recursive Shapes
- ✅ Parse nested inline shapes: `!shape ~circle = {pos ~{x ~num y ~num} radius ~num}`
- ✅ Parse deeply nested shapes
- ✅ Parse block shapes with `:` prefix: `{op ~:{x ~num}}`

### Integration
- ✅ All existing tests still pass
- ✅ Shape definitions work at module level only
- ✅ Shape operators work in expressions
- ✅ No runtime evaluation (parsing/AST only)

## Notes for Implementation

### Block Field Syntax

Block fields in shapes use the `:` prefix followed by an inline shape definition:

```comp
!shape ~repeat-text = {
    count ~num
    op ~:{value ~str}    ; Block field expecting {value ~str}
}

!shape ~transformer = {
    op ~:{~any}          ; Block accepting any input
}

!shape ~generator = {
    produce ~:{}         ; Block with no input (empty structure)
}
```

The `:` makes block fields syntactically distinct and the shape after the colon is **mandatory** - it defines what input structure the block expects. The grammar should parse this as:
- Field identifier
- `~:` token sequence
- `{` shape_body `}`

This is cleaner than `~block{...}` because it eliminates the `block` keyword and makes the type syntax more uniform - all type references use `~`, and blocks are just a special field modifier.

**The syntax is beautifully consistent:**

```comp
~{op ~:{~str}} = :{[|length/str]}
```

Breaking this down:
- `~{...}` - inline shape definition (tilde means "shape")
- `op ~:{~str}` - field `op` is a block (colon) that accepts a string as input
- `= :{[|length/str]}` - default value is a block (colon) that gets string length

The pattern:
- **`~`** always means "shape/type reference"
- **`:`** always means "block/deferred computation"  
- **`{}`** is either a structure literal or shape body (context-dependent)

This shows how shapes, blocks, and structures compose naturally - the block type `~:{~str}` declares the input shape, while the block value `:{...}` implements the logic.

### Recursive Shape Grammar

The grammar naturally supports recursion since `shape_type` can contain `TILDE LBRACE shape_body RBRACE`, and `shape_body` contains `shape_field*`, and each `shape_field` has a `shape_type`. This means:

```comp
!shape ~deeply-nested = {
    a ~{
        b ~{
            c ~{
                value ~num
            }
        }
    }
}
```

Block shapes use the `:` prefix syntax and are parsed as a special field type that includes an inline shape body for the block's expected input.

### Operator Precedence

Shape operators should have lower precedence than arithmetic but higher than assignment:

```comp
x + y ~shape        ; (x + y) ~shape
data ~shape1 | shape2  ; data ~(shape1 | shape2)
x = y ~shape        ; x = (y ~shape)
```

### Tag-as-Shape Semantics

When a tag reference appears where a shape is expected, it should be treated as an inline shape that accepts any value with that tag:

```comp
value ~#status      ; Equivalent to: value ~{#status ~any}
```

### Union Shape Parsing

Union shapes use `|` which may conflict with pipeline operators. Ensure proper context handling:

```comp
!shape ~result = ~success | ~error     ; Union in shape definition
data ~result1 | result2                ; Ambiguous - needs precedence rules
data ~(result1 | result2)              ; Explicit parentheses
```

### Spread Operator Context

The spread operator `..` works differently in different contexts:
- In shape definitions: inherit fields from another shape
- In structure literals: copy fields from another structure
- Both should use the same AST nodes for consistency

## Estimated Complexity

**Size**: Large (similar to or bigger than tag definitions)
**Difficulty**: Medium (builds on Phase 11 patterns)
**Risk**: Medium (operator precedence, multiple contexts)

**Breakdown**:
- Grammar rules: ~50 lines
- AST nodes: ~10 new classes
- Parser cases: ~20 new cases  
- Tests: ~40-50 test cases

**Expected Duration**: 3-4 sessions

## Key Design Decisions

**Removed Features**:
- ❌ Check operators (`~?`, `~*?`, `~??`) - use morph with fallback instead
- ❌ Presence-check operators (`??`, `!exists`, `!count`) - use tag morphing + `$ctx`
- ❌ Optional field syntax (`field?`) - use union with `~nil` + defaults

**Added Features**:
- ✅ Positional fields (no field names): `{~num ~num}`
- ✅ Type aliases with defaults: `!shape ~one = ~num=1`
- ✅ Block field syntax: `field ~:{input_shape}`
- ✅ Shape spreading with defaults: `..~defaults`
- ✅ Morph operator syntax: `~`, `~*`, `~?` (postfix modifiers, tilde first)
- ✅ Union morphing with specificity ranking

**Design Philosophy**:
- Composable primitives over special-case syntax
- Let patterns emerge organically before adding convenience features
- Named properties for heterogeneous children, direct access for homogeneous

## Status: Ready to Begin

This phase establishes the complete shape system foundation. Future phases can add:
- Shape constraints and validation
- Size constraints with `[]`
- Unit system integration
- Runtime shape morphing and validation (the actual morphing algorithm)
- Performance optimization

All prerequisites are in place from Phase 11's module-level grammar work.
