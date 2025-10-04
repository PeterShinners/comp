# Phase 01-14: Complete Tag Definition Parsing

**Status:** Not Started  
**Depends On:** 01-13 (Function Definitions)  
**Goal:** Complete parsing support for all tag definition features including values, extensions, and generation functions

## Overview

Tags are currently parsed in their basic hierarchical form (from 01-11), but several advanced features are missing:
- Tag values (numbers, strings, or other tags)
- Tag extension using spread operator (`+=` or `..=`)
- Value generation functions (`{|generator}`)
- Multiple definition styles (nested, flat, mixed)

This phase implements full tag definition parsing to match the comprehensive design in `design/tag.md`.

### Design Decision: Lookahead Disambiguation

**Problem**: Ambiguity when tag has both a value and children:
```comp
!tag #data = {x=1} {#child}  ; {x=1} is value, {#child} is children
!tag #tags = {#a #b}         ; Is this value or children?
```

**Solution**: Use first token inside braces to distinguish:
- `{#...}` → Tag children (starts with `#`)
- `{..#...}` → Tag spread (starts with `..`)
- `{anything else}` → Value expression

**Edge Case - Unnamed Tag Fields**:
```comp
!tag #maybe = {#possible #perhaps}
```

This is **ambiguous** - it could be:
1. No value, two children: `#possible` and `#perhaps`
2. Value is structure `{#possible #perhaps}`, no children

**Disambiguation Rule**: Parser **always** treats `{#tag #tag ...}` as tag children, never as a value.

If you want a structure of tag references as the value, use empty children `{}`:
```comp
!tag #maybe = {#possible #perhaps} {}    ; Value={#possible #perhaps}, no children
```

This makes the common case (defining child tags) natural and the rare case (structure of tags as value) explicit.

**Grammar pattern**:
```lark
tag_value_and_body: expression tag_body    ; Value then children
                  | tag_body                ; Just children (common case)

tag_body: LBRACE tag_child+ RBRACE         ; Always starts with # or ..
        | LBRACE RBRACE                     ; Empty children (for disambiguation)
```

## Tag Definition Features

### 1. Tag Values

Tags can have values that are any build-time expression - numbers, strings, tags, structures, or complex expressions. The grammar distinguishes value structures from tag children by the first token inside braces.

```comp
; Simple values
!tag #status = "unknown"
!tag #priority = 0
!tag #friend = #buddy

; Structure values (no children)
!tag #point = {x=1 y=2}
!tag #config = {name="test" active=#true}

; Complex expression values
!tag #computed = (100 + 50)
!tag #morphed = ({x=1} ~point)

; Values with children
!tag #status = "unknown" {
    #active = 1
    #inactive = 0
    #pending           ; No value - marker only
}

; Structure value AND children
!tag #tens = {11 12 13} {
    #eleven
    #twelve  
    #thirteen
}

; Tag reference values with children
!tag #alias = #other.tag {
    #child = #different
}
```

### 2. Tag Extensions

Tags can be extended using spread-like operators to add new branches:

```comp
; Initial definition
!tag #media = {
    #image {#jpeg #png}
    #video {#mp4}
}

; Extension - adds new tags to existing hierarchy
!tag #media += {
    #image {#svg #webp}        ; Add to existing branch
    #document {#pdf #epub}     ; Add new branch
}

; Alternative syntax using spread in body
!tag #media = {
    ..#media                   ; Preserve existing
    #audio {#mp3 #ogg}        ; Add new branch
}
```

### 3. Value Generation Functions

Tags support automatic value generation through pure functions:

```comp
; Using standard library generators
!tag #color {|name/tag} = {
    #red              ; Value: "red"
    #green            ; Value: "green"
    #blue             ; Value: "blue"
}

!tag #permission {|bitflag/tag} = {
    #read             ; Value: 1
    #write            ; Value: 2
    #execute          ; Value: 4
    #admin = 7        ; Explicit value overrides
}

; Custom generator
!func |my-generator ~{ctx} = {
    ; Generate value based on context
}

!tag #error = 0 {|my-generator} = {
    #network          ; Generated value
    #database         ; Generated value
    #validation = 999 ; Explicit override
}
```

### 4. Multiple Definition Styles

All these styles should work and be equivalent:

```comp
; Nested style (current implementation)
!tag #status = {
    #active = 1
    #inactive = 0
}

; Flat style
!tag #status
!tag #status.active = 1
!tag #status.inactive = 0

; Mixed style
!tag #priority = {#low = 1 #medium = 2}
!tag #priority.critical = 99

; Multiple definitions merge
!tag #color = {#red = 1}
!tag #color = {#blue = 2}       ; Extends color
```

## Grammar Updates

### Current Grammar (from 01-11)

```lark
tag_definition: BANG_TAG tag_path                         
              | BANG_TAG tag_path ASSIGN tag_body

tag_path: "#" reference_identifiers

tag_body: LBRACE tag_child* RBRACE

tag_child: tag_path
         | tag_path ASSIGN tag_body
```

### Updated Grammar Needed

**Decision: Use lookahead to distinguish value from children**

The grammar can distinguish between value structures and tag children by looking at the first token inside braces:
- `{#...}` → tag children (starts with HASH)
- `{..#...}` → tag spread (starts with SPREAD)
- `{anything else}` → value expression

This allows any expression as a value, even structures, while keeping the grammar unambiguous.

```lark
tag_definition: BANG_TAG tag_path tag_generator? tag_extension? (ASSIGN tag_value_and_body | tag_body)

tag_path: HASH reference_identifiers

; Value and/or body after assignment
tag_value_and_body: expression tag_body    ; Value then children
                  | tag_body                ; Just children (no value)

; Value generator (optional, before assignment)
tag_generator: LBRACE function_reference RBRACE

; Extension operator (optional)
tag_extension: PLUS_ASSIGN              ; Replace ASSIGN with +=

; Tag body - always contains tag-specific constructs
tag_body: LBRACE tag_child+ RBRACE

tag_child: tag_spread                                     
         | tag_path tag_generator? (ASSIGN expression)? tag_body?

tag_spread: SPREAD tag_path
```

**Why this works**: Tag bodies always start with `#` (tag path) or `..` (spread), while value structures contain general expressions. The parser can distinguish them with just one token of lookahead.

### Key Considerations

1. **Disambiguation via First Token**: 
   - `{#...}` always means tag children (tag path starts with `#`)
   - `{..#...}` always means tag spread (starts with `..`)
   - `{x=1}` or `{123}` are value expressions (don't start with `#` or `..`)
   - **Edge case**: `{#a #b}` is children, not value. Use `{#a #b} {}` for value.
   
2. **Empty Children Disambiguator**:
   - `{}` at end forces previous structure to be treated as value
   - `!tag #x = {#a #b}` → children: #a, #b (no value)
   - `!tag #x = {#a #b} {}` → value: {#a #b}, no children
   
3. **Generator Syntax**:
   - `{|generator}` comes before `=` and value/body
   - `!tag #color {|name/tag} = {#red #green}` - generator creates values
   - Generator is optional

4. **Extension Operators**:
   - `+=` replaces `=` to extend existing tag definition
   - Spread within body: `..#existing` to include hierarchy
   - Used to merge new tags into existing hierarchy

5. **Backward Compatibility**:
   - Current nested syntax continues to work
   - `!tag #status = {#active = 1}` still valid
   - Empty tag bodies `{}` now valid (as disambiguator)

6. **Value and Children Cases**:
   - Value only: `!tag #point = {x=1 y=2}`
   - Children only: `!tag #status = {#active #inactive}`
   - Both: `!tag #status = {x=1} {#active #inactive}`
   - Disambiguated value: `!tag #tags = {#a #b} {}`

## AST Node Updates

### Current TagDefinition

```python
class TagDefinition(AstNode):
    def __init__(self, tokens: list[str] | None = None, assign_op: str = "="):
        self.tokens = list(tokens) if tokens else []
        self.assign_op = assign_op
        super().__init__()
```

### Updated TagDefinition

```python
class TagDefinition(AstNode):
    def __init__(
        self, 
        tokens: list[str] | None = None, 
        assign_op: str = "=",
        value_expr: AstNode | None = None,      # Tag value expression
        generator: AstNode | None = None,        # Generator function ref
        is_extension: bool = False               # True if using += or ..=
    ):
        self.tokens = list(tokens) if tokens else []
        self.assign_op = assign_op
        self.value_expr = value_expr
        self.generator = generator
        self.is_extension = is_extension
        super().__init__()
    
    @property
    def value(self):
        """Direct value expression if specified separately from children."""
        return self.value_expr
    
    @property
    def children_defs(self):
        """Child tag definitions (kids list)."""
        return self.kids
```

### New TagSpread Node

```python
class TagSpread(AstNode):
    """Tag spread in definition: ..#tag
    
    Used to include existing tag hierarchy in extended definitions.
    """
    
    def __init__(self):
        super().__init__()
    
    @property
    def tag_ref(self):
        """The tag reference being spread (first child)."""
        return self.kids[0] if self.kids else None
    
    def unparse(self) -> str:
        if self.tag_ref:
            return f"..{self.tag_ref.unparse()}"
        return ".."
```

## Implementation Tasks

### 1. Grammar Updates
- [ ] Add optional `tag_value`, `tag_generator`, `tag_extension` to `tag_definition`
- [ ] Support `PLUS_ASSIGN` and `SPREAD_ASSIGN` operators for extensions
- [ ] Add `tag_generator: LBRACE function_reference RBRACE` syntax
- [ ] Add `tag_spread` rule for `..#tag` in tag bodies
- [ ] Update `tag_child` to support optional values
- [ ] Ensure all definition styles parse correctly

### 2. Parser Updates
- [ ] Add `tag_spread` case to create `TagSpread` nodes
- [ ] Update `tag_definition` case to extract value, generator, extension flag
- [ ] Handle mixed definition styles (multiple `!tag` for same root)
- [ ] Parse generator function reference from `{|func}` syntax

### 3. AST Node Updates
- [ ] Add `value_expr`, `generator`, `is_extension` to `TagDefinition.__init__`
- [ ] Update `TagDefinition.fromGrammar` to extract new fields
- [ ] Update `TagDefinition.unparse` to handle all syntax variations
- [ ] Create `TagSpread` class similar to `ShapeSpread`
- [ ] Add properties for accessing value vs children

### 4. Test Coverage
- [ ] Test tags with numeric values
- [ ] Test tags with string values  
- [ ] Test tags with tag values
- [ ] Test root tag with value and children
- [ ] Test tag extensions with `+=`
- [ ] Test tag spread with `..#tag`
- [ ] Test generator syntax `{|func}`
- [ ] Test all definition styles (nested, flat, mixed)
- [ ] Test multiple definitions merging
- [ ] Roundtrip tests for all syntax variations

### 5. Edge Cases
- [ ] Tag with both value and children
- [ ] Tag with generator and explicit values (explicit wins)
- [ ] Extension of non-existent tag (parser should allow, runtime validates)
- [ ] Empty tag body `!tag #status = {}`
- [ ] Tag value that is a complex expression
- [ ] Nested extensions

## Examples to Support

```comp
; Simple values
!tag #status = "unknown"
!tag #priority = 0
!tag #friend = #buddy

; Simple value with children
!tag #status = "unknown" {
    #active = 1
    #inactive = 0
}

; Complex value without children
!tag #point = {x=1 y=2}
!tag #config = ({name="test"} ~settings)

; Complex value WITH children (now supported!)
!tag #tens = {11 12 13} {
    #eleven
    #twelve
    #thirteen
}

; Generator with values
!tag #color {|name/tag} = {
    #red
    #green
    #blue = "0000ff"    ; Override generated
}

; Extension
!tag #media = {#image {#jpeg}}
!tag #media += {#image {#png}}

; Spread in body
!tag #extended = {
    ..#media
    #audio {#mp3}
}

; Flat style
!tag #priority
!tag #priority.low = 1
!tag #priority.high = 99

; Mixed definitions
!tag #result = {#ok = 0}
!tag #result = {#error = -1}  ; Merges with above
```

## Success Criteria

- [x] All tag value types parse correctly (numbers, strings, tags)
- [x] Generator syntax `{|func}` parses and stores function reference
- [x] Extension operators (`+=`, `..=`) parse and set extension flag
- [x] Tag spread (`..#tag`) creates TagSpread nodes
- [x] All definition styles produce equivalent AST structures
- [x] Multiple definitions of same tag merge properly in parser
- [x] Roundtrip unparse/parse produces identical AST for all syntax forms
- [x] Edge cases handled correctly (value + children, overrides, etc.)
- [x] All unit tests pass

## Notes

- This phase focuses on **parsing only** - runtime semantics handled in later phases
- Generator functions are just parsed as references - execution comes later
- Extension merging is validated at parse time where possible
- Tag value expressions can be any expression but typically literals
- The `tag/` standard library module (with generators like `|name/tag`, `|bitflag/tag`) is not implemented yet

## Related Design Documents

- `design/tag.md` - Complete tag system design
- `design/function.md` - Function references and dispatch
- `design/module.md` - Cross-module tag extensions
- `design/type.md` - Tag role in type system
