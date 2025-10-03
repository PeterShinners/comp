# Phase 12: Shape Definitions

**Status**: 📋 **PLANNED**  
**Created**: October 2025

## Overview

This phase implements shape definitions and operations, building on the module-level grammar foundation from Phase 11. Shapes provide structural typing for Comp, enabling type validation, data transformation, and API contracts without rigid class hierarchies.

### What's Included in This Phase

**Core Shape Features**:
- Top-level shape definitions with `!shape`
- Inline shape definitions (shape literals)
- Shape morph operators: `~`, `*~`, `?~`
- Shape check operators: `~?`, `*~?`, `?~?`
- Shape references (using `~shapename`)
- Tag references where shapes expected (#tag as inline shape)
- Shape spread in definitions (`..~shape`)
- Structure spread in literals (`..{struct}`)
- Union shapes with `|` operator

**Optional (if straightforward)**:
- Presence check syntax with `??`

**Explicitly Deferred**:
- Shape constraints (`{min=0 max=100}`)
- Size constraints with `[]` (e.g., `~str[1-10]`)
- Unit definitions and references
- Performance optimization/caching

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
    active? ~bool = #true
    preferences?              ; Optional field (any type)
    tags #user-tag            ; Tag reference as type
}

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
; Inline in function signature
!func |process ~{x ~num y ~num} = {x + y}

; Inline in morph operation
data ~{name ~str age ~num}

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

; Block types are just shape references
!shape ~validator = ~block{x ~num y ~num}
!shape ~transformer = ~block{~any}

; Tag as inline shape (tag reference treated as shape)
status #active              ; Using tag as value
data ~#user-status         ; Using tag as shape (any #user-status works)
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

; Blocks are just special shape references
!shape ~validator = ~block{x ~num y ~num}
!shape ~mapper = ~block{~any}
!shape ~filter = ~block{item ~any}

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

## Presence Check (Optional)

If straightforward, include the `??` presence check syntax:

```comp
!shape ~process-flags = {
    verbose ~bool = #false ?? #true
    debug ~bool = #false ?? #true
    quiet? ~bool = #true ?? #false
}

; The ?? operator:
; - Left side: value when field name NOT in unnamed values
; - Right side: value when field name IS in unnamed values

({verbose extra=data} ~process-flags)
; Result: {verbose=#true debug=#false quiet?=#true extra=data}
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
shape_body: LBRACE shape_field* RBRACE
          | shape_reference                     // Alias
          | shape_union                         // Union type

shape_field: shape_spread                       // ..~shape
           | identifier shape_type [ASSIGN expression]  // field ~type = default
           | identifier [QUESTION] [shape_type] [ASSIGN expression] [PRESENCE_CHECK expression]  // optional fields

shape_spread: SPREAD shape_reference            // ..~shape
            | SPREAD QUESTION shape_reference   // ?..~shape (weak)
            | SPREAD STRONG shape_reference     // !..~shape (strong)

shape_type: shape_reference                     // ~typename
          | tag_reference                       // #tagname (tag as type)
          | TILDE TOKEN LBRACE shape_body RBRACE  // ~block{...} or ~any{...}
          | TILDE LBRACE shape_body RBRACE      // ~{...} inline shape
          | shape_union                         // ~type1 | ~type2

shape_union: shape_type (PIPE shape_type)+

PRESENCE_CHECK: "??"
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
    """Shape definition at module level: !shape ~name = {...}"""
    
    def __init__(self, name: str, body: AstNode | None = None):
        self.name = name        # Shape name (without ~)
        self.body = body        # ShapeBody or ShapeReference or ShapeUnion
        super().__init__()
    
    def unparse(self) -> str:
        if not self.body:
            return f"!shape ~{self.name}"
        return f"!shape ~{self.name} = {self.body.unparse()}"
    
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
    """Single field in shape: name ~type = default"""
    
    def __init__(self, name: str, type_ref: AstNode | None = None,
                 default: AstNode | None = None, optional: bool = False,
                 presence_check: AstNode | None = None):
        self.name = name
        self.type_ref = type_ref      # ShapeReference, TagRef, or None
        self.default = default         # Default value expression
        self.optional = optional       # Has ? suffix
        self.presence_check = presence_check  # Expression after ??
        super().__init__()
    
    def unparse(self) -> str:
        result = self.name
        if self.optional:
            result += "?"
        if self.type_ref:
            result += f" {self.type_ref.unparse()}"
        if self.default:
            result += f" = {self.default.unparse()}"
        if self.presence_check:
            result += f" ?? {self.presence_check.unparse()}"
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
        
        op = "~" if self.mode == "normal" else f"{self.mode[0]}~"
        return f"{expr_str} {op}{shape_str}"


class ShapeCheckOp(AstNode):
    """Shape check operation: data ~? shape"""
    
    def __init__(self, mode: str = "normal"):
        self.mode = mode  # "normal", "strong", "weak"
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
        
        if self.mode == "normal":
            op = "~?"
        elif self.mode == "strong":
            op = "*~?"
        else:
            op = "?~?"
        
        return f"{expr_str} {op} {shape_str}"
```

## Implementation Strategy

### Phase 1: Basic Infrastructure
1. Add shape tokens to lexer (BANG_SHAPE, TILDE, etc.)
2. Implement shape_definition grammar rule
3. Create ShapeDefinition and ShapeReference AST nodes
4. Add transformer cases for shape_definition
5. Test simple shape definitions

### Phase 2: Shape Bodies
1. Implement shape_body and shape_field grammar
2. Create ShapeBody and ShapeField AST nodes
3. Add support for type references in fields
4. Test shape definitions with typed fields and defaults

### Phase 3: Shape Operators
1. Add morph and check operator tokens
2. Implement morph_expr and check_expr grammar
3. Create MorphOp and ShapeCheckOp AST nodes
4. Test basic morph and check operations

### Phase 4: Advanced Features
1. Implement shape_union grammar
2. Create ShapeUnion AST node
3. Add shape spreading in definitions
4. Add structure spreading in literals
5. Test union shapes and spreading

### Phase 5: Optional Features (if straightforward)
1. Presence check syntax (`??`)
2. Tag-as-shape references

## Test Strategy

### Valid Shape Definitions

```python
@comptest.params(
    "code",
    simple=("!shape ~point = {x ~num y ~num}",),
    defaults=("!shape ~point = {x ~num = 0 y ~num = 0}",),
    optional=("!shape ~user = {name ~str email? ~str}",),
    tag_type=("!shape ~status = {value #active}",),
    spread=("!shape ~point3d = {..~point z ~num}",),
    union=("!shape ~result = ~success | ~error",),
    block=("!shape ~validator = ~block{x ~num}",),
    nested=("!shape ~circle = {pos ~{x ~num y ~num} radius ~num}",),
    deep_nested=("!shape ~transform = {translate ~{x ~num y ~num z ~num}}",),
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
- ✅ Parse shapes with optional fields: `name? ~str`
- ✅ Parse shape inheritance: `!shape ~point3d = {..~point z ~num}`
- ✅ Parse union shapes: `!shape ~result = ~success | ~error`
- ✅ Round-trip all shape definitions

### Shape Operators
- ✅ Parse morph operators: `~`, `*~`, `?~`
- ✅ Parse check operators: `~?`, `*~?`, `?~?`
- ✅ Parse inline shape definitions: `data ~{x ~num}`
- ✅ Parse tag as shape: `value ~#status`
- ✅ Round-trip all operator expressions

### Shape Spreading
- ✅ Parse shape spread in definitions: `..~shape`
- ✅ Parse spread modes: `..`, `?..`, `!..`
- ✅ Parse structure spread in literals: `{..struct}`

### Recursive Shapes
- ✅ Parse nested inline shapes: `!shape ~circle = {pos ~{x ~num y ~num} radius ~num}`
- ✅ Parse deeply nested shapes
- ✅ Parse block shapes (just special type references): `~block{x ~num}`

### Optional Features
- ⏸️ Presence check: `field ~bool = #false ?? #true` (if straightforward)

### Integration
- ✅ All existing tests still pass
- ✅ Shape definitions work at module level only
- ✅ Shape operators work in expressions
- ✅ No runtime evaluation (parsing/AST only)

## Notes for Implementation

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

Block shapes like `~block{x ~num}` are just parsed as `~block` (a shape reference to a built-in shape) followed by an inline shape body. The grammar should handle this as: `TILDE TOKEN LBRACE shape_body RBRACE`.

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
- Grammar rules: ~40 lines
- AST nodes: ~8 new classes
- Parser cases: ~15 new cases  
- Tests: ~30-40 test cases

**Expected Duration**: 2-3 sessions (with optional features)

## Status: Ready to Begin

This phase establishes the complete shape system foundation. Future phases can add:
- Shape constraints and validation
- Size constraints with `[]`
- Unit system integration
- Runtime shape morphing and validation
- Performance optimization

All prerequisites are in place from Phase 11's module-level grammar work.
