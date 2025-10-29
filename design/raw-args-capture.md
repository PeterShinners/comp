# Raw Arguments Capture Design

**Problem**: Python bridge functions (`|call`, `|call-func`) need access to ALL arguments to pass to Python functions, but placing them in the `arg` parameter causes strong morph filtering which loses extra fields.

## REVISED APPROACH (Selected)

**Use INPUT instead of ARGUMENTS for Python function parameters.**

The input value in Comp functions flows through WITHOUT strong morphing, making it perfect for passing arbitrary structures:

```comp
# NEW SYNTAX - Python args go in INPUT, function name in ARG
[{path="/tmp/data.txt" strict=#false} |call "os.path.realpath"]

# Or with arg struct:
[{url="https://example.com" scheme="https"} |call arg {name="urllib.parse.urlparse"}]

# Method calls: input = self, arg = method name
[$my-object |call "method_name" arg {x=1 y=2}]
```

This approach:
- ✅ Uses existing input morphing (which is permissive)
- ✅ No changes to morph system needed
- ✅ More compositional - can pipeline to build args
- ✅ Matches Python's `self` convention for methods
- ✅ Simpler mental model

---

## OLD ANALYSIS (Preserved for Context)

### Previous Problem Statement

When a function is called in Comp:

```comp
|some-func arg {
    name = "urllib.parse.urlparse"
    url = "https://example.com"
    scheme = "https"
    allow_fragments = #false
}
```

The function receives arguments through this pipeline:

1. **Caller provides raw args**: `{name url scheme allow_fragments}`
2. **Strong morph applied** (`~*`): Filters to only fields in `arg_shape`, adds defaults, validates types
3. **Weak morph for $ctx** (`~?`): Filters $ctx to intersection with `arg_shape`
4. **Weak morph for $mod** (`~?`): Filters $mod to intersection with `arg_shape`
5. **Function receives**: Only the filtered args

For Python bridge, if `arg_shape` is:
```comp
^{name ~str}
```

Then the function only receives `{name}` - the `url`, `scheme`, and `allow_fragments` are **lost forever**.

### Where It Happens

In `_function.py`, `FunctionDefinition.__call__()` around line 324:

```python
# Step 1: Morph arguments to arg shape with strong morph (~*)
arg_scope = args_value if args_value is not None else comp.Value({})
if self.arg_shape is not None:
    arg_morph_result = comp.strong_morph(arg_scope, self.arg_shape)
    if not arg_morph_result.success:
        return comp.fail(f"Function |{func_name}: arguments do not match argument shape")
    arg_scope = arg_morph_result.value  # ← FILTERED HERE
```

After this point, only `arg_scope` (the morphed result) is available. The original `args_value` is discarded.

## Use Cases

### Python Interop
The Python bridge needs to forward all arguments to Python functions without knowing their signatures in advance:

```comp
!import /py = stdlib "python"

# Call Python's urlparse with all its parameters
/py|call-func arg {
    name = "urllib.parse.urlparse"
    url = "https://example.com/path?query=1"
    scheme = "https"
    allow_fragments = #false
    # These should ALL reach Python, not be filtered
}
```

### Generic Wrappers
Middleware/decorator functions that wrap other functions:

```comp
!fun |with-logging arg {
    func ~block
    # ...rest of args should pass through to func
}

|with-logging arg {
    func = :{|do-something}
    x = 10
    y = 20
    debug = #true
}
```

### Dynamic Dispatch
Functions that route calls based on structure:

```comp
!fun |dispatch arg ~any {
    # Inspect all fields to decide routing
    # Forward everything to appropriate handler
}
```

## Strategy 1: Magic Shape Definition

Add a special shape syntax that opts into raw argument capture.

### Option 1a: `~any` Shape Constraint

```comp
!fun |call-func arg ~any {
    # arg_shape = ShapeDefinition with special "accept_any" flag
    # No strong morph applied - receives raw arguments
    # $arg contains all fields, not filtered
}
```

**Pros:**
- Clear declaration in function signature
- Existing shape syntax pattern
- Self-documenting (signals "this function is flexible")
- Easy to understand: `~any` means "any structure accepted"

**Cons:**
- `~any` already has meaning in morph operations (matches anything)
- Could be confused with type constraints
- Doesn't solve the $mod/$ctx filtering issue

### Option 1b: `all-args` Keyword in Definition

```comp
!fun |call-func all-args {
    # Special keyword signals "bypass strong morph"
    # $arg contains all fields passed by caller
}
```

**Pros:**
- Explicit keyword makes intent crystal clear
- Doesn't conflict with existing syntax
- Could be combined with shape: `all-args ^{name ~str}` (capture all, but validate name exists)

**Cons:**
- Adds new keyword to function definition syntax
- Less composable than shape-based approach
- Unclear how it interacts with existing arg_shape validation

### Option 1c: `~*any` or `~**` Strong-Any Morph

```comp
!fun |call-func arg ~*any {
    # Like ~* but accepts ANY fields
    # Still validates types if specified, but doesn't reject extras
}
```

**Pros:**
- Extends existing morph operators logically
- Can still validate known fields: `^{name ~str ~**}` = "name required, anything else allowed"
- Familiar to Python developers (`**kwargs`)

**Cons:**
- More complex morph semantics
- Need to define how it differs from `~?` (weak morph)
- Could be written `~**` for kwargs analogy

## Strategy 2: Special Scope Variable

Add a new scope variable that contains pre-morphed arguments.

### Option 2a: `$raw-args` Scope

```comp
!fun |call-func arg {name ~str} {
    # $arg contains morphed args: {name}
    # $raw-args contains original args: {name url scheme allow_fragments}
    
    $py|call-function input $raw-args
}
```

**Pros:**
- Doesn't change function signature syntax
- Backwards compatible - existing functions unaffected
- Clear separation: $arg = validated, $raw-args = raw
- Can still use arg_shape for validation while accessing extras

**Cons:**
- Adds another special scope variable to learn
- Naming is tricky: $raw-args, $all-args, $unfiltered-args?
- Increases cognitive load (when to use $arg vs $raw-args?)
- What about $ctx and $mod? They're also filtered

### Option 2b: `$extern` or `$caller-args` Scope

```comp
!fun |call-func arg {name ~str} {
    # $arg = {name}  (morphed)
    # $extern = {name url scheme allow_fragments}  (caller's exact structure)
}
```

**Pros:**
- More general name suggests "external input"
- Could extend to other caller metadata in future
- Clear conceptual model: $extern = what caller sent

**Cons:**
- "extern" is vague - external to what?
- Still adds complexity
- Same issues as $raw-args

### Option 2c: Modified Weak Morph for Scopes

Instead of weak morphing $ctx and $mod to arg_shape, provide full versions:

```comp
!fun |call-func arg {name ~str} {
    # $arg = {name}  (strong morphed)
    # $ctx = full context (not filtered)
    # $mod = full module scope (not filtered)
}
```

**Pros:**
- Removes filtering that might not be needed
- Simpler mental model - scopes are what they are
- One less "magic" transformation

**Cons:**
- Breaks existing assumption that $ctx/$mod are filtered
- Could expose too much data to functions
- Doesn't solve the arg capture problem

## Strategy 3: Hybrid Approach

Combine shape annotation with scope variable for maximum flexibility.

### Option 3a: `~**` Shape + $raw-args

```comp
!fun |generic-wrapper arg ~** {
    # ~** allows any extra fields beyond defined shape
    # $raw-args available if needed for metaprogramming
}

!fun |call-func arg {name ~str ~**} {
    # name is required and validated as string
    # any other fields are allowed
    # $arg contains ALL fields including extras
}
```

**Pros:**
- Best of both worlds
- Shape provides validation + documentation
- $raw-args for advanced use cases
- Flexible and powerful

**Cons:**
- Most complex option
- Two ways to access the same data could be confusing

## Analysis & Recommendations

### Core Design Questions

1. **Validation vs Access**: Should a function be able to VALIDATE some args while ACCESSING all args?
   - Strategy 1: No - it's either validate-and-filter OR accept-all
   - Strategy 2: Yes - validate through arg_shape, access raw through scope
   - Strategy 3: Yes - explicit in shape syntax

2. **Discoverability**: How does a developer know what a function expects?
   - Strategy 1: Function signature is self-documenting
   - Strategy 2: Need to read function body to see if it uses $raw-args
   - Strategy 3: Shape shows validated fields, rest implied by ~**

3. **Common Case**: What's the typical scenario?
   - Most functions want validate-and-filter (current behavior)
   - Python bridge is the outlier needing accept-all
   - Generic wrappers/middleware might also need it

### Recommended Approach: Strategy 1c with `~**`

Extend the morph operator family with `~**` (strong-any morph):

```comp
# Accept any structure (no validation)
!fun |call-func arg ~** {
    # $arg receives all fields exactly as caller provided
}

# Validate specific fields, allow extras
!fun |call-func arg {name ~str ~**} {
    # name must be present and string
    # other fields pass through unfiltered
    # $arg contains {name + everything else}
}

# Current behavior unchanged
!fun |normal-func arg {x ~num y ~num} {
    # Only x and y, extras rejected (strong morph ~*)
}
```

**Implementation Plan:**

1. Add `ACCEPT_EXTRA_FIELDS` flag to `ShapeDefinition`
2. Modify `strong_morph()` to skip extra field rejection when flag is set
3. Add `~**` syntax to shape parser
4. Update Python bridge functions to use `arg ~**` or `arg {name ~str ~**}`

**Why This Approach:**

- **Clear semantics**: `~**` is visually similar to Python's `**kwargs` - developers will understand
- **Composable**: Works with existing shape validation - can require some fields while allowing extras
- **Self-documenting**: Function signature shows exactly what's validated vs what's flexible
- **Minimal complexity**: Leverages existing morph system, just adds one flag
- **Backwards compatible**: Existing code unchanged

**Alternative Notation:**

Could also be written as:
- `^{name ~str ...}` - ellipsis suggests "and more"
- `^{name ~str *}` - asterisk suggests variadic
- `^{name ~str & ~any}` - union with any

But `~**` is most intuitive given Python's kwargs convention.

## Implementation Notes

### In _morph.py

```python
def strong_morph(value, shape):
    """Strong morph (~*): exact structural conformance with strict validation.
    
    Extended with ~** support:
    - ~** or shape with accept_extra_fields flag allows extra fields
    - Still validates defined fields for type/presence
    """
    result = morph(value, shape)
    if not result.success:
        return result
    
    if not isinstance(shape, comp.ShapeDefinition):
        return result
    
    # NEW: Check if shape accepts extras
    if getattr(shape, 'accept_extra_fields', False):
        return result  # Don't reject extras
    
    # Existing logic: reject extra fields
    allowed_names = {field.name for field in shape.fields if field.is_named}
    # ... rest of current implementation
```

### In _function.py

No changes needed! The morph system handles it.

### In python.py

Update function signatures:

```python
# Before:
module.define_function(
    path=["call"],
    body=comp.PythonFunction("call-method", call_method),
    arg_shape=???  # How to specify "name" is required but accept extras?
)

# After:
# Option A: Accept everything, validate name manually
module.define_function(
    path=["call"],
    body=comp.PythonFunction("call-method", call_method),
    arg_shape=comp.ShapeDefinition(
        name="call-args",
        fields=[],  # No required fields
        accept_extra_fields=True  # Accept all
    )
)

# Option B: Define name as required, accept extras
module.define_function(
    path=["call"],
    body=comp.PythonFunction("call-method", call_method),
    arg_shape=comp.ShapeDefinition(
        name="call-args",
        fields=[
            comp.ShapeField(name="name", type_constraint=comp.STR_SHAPE, required=True)
        ],
        accept_extra_fields=True  # Accept extras beyond 'name'
    )
)
```

## Testing Strategy

Create tests demonstrating:

1. **Basic acceptance**: Function with `~**` receives all fields
2. **Partial validation**: Function with `{name ~str ~**}` validates name but accepts extras
3. **Python bridge**: Call Python function with arbitrary kwargs
4. **Error cases**: Function without `~**` correctly rejects extras (existing behavior preserved)
5. **Overloading**: Multiple definitions with/without `~**` dispatch correctly

## Future Considerations

### Positional vs Named
How does `~**` interact with unnamed (positional) fields?

```comp
|func arg {x ~num ~**}  # Named extras allowed
|func arg {~num ~num ~**}  # Positional extras allowed?
```

Proposal: `~**` only affects named fields. For positional variadic, use `~*` (different meaning).

### Morph Operators Family

Current: `~` (normal), `~*` (strong), `~?` (weak)
Proposed: Add `~**` (strong-any)

This completes the space:
- `~`: Default, accepts extras, applies defaults, validates types
- `~*`: Strict, rejects extras, applies defaults, validates types
- `~**`: Permissive-strict, accepts extras, applies defaults, validates types
- `~?`: Intersection, no defaults, no type validation

### Named Shape for ~**

Should there be a built-in shape like `~any-struct`?

```comp
!shape ~any-struct = ~**  # Any struct with any fields

!fun |flexible arg ~any-struct {
    # Equivalent to: arg ~**
}
```

Probably not needed - the operator is clear enough.

---

## Decision Point

**Recommended**: Implement Strategy 1c with `~**` operator.

**Next Steps**:
1. Add `accept_extra_fields` flag to ShapeDefinition
2. Modify strong_morph to honor the flag
3. Add parser support for `~**` syntax
4. Update Python bridge to use new syntax
5. Write comprehensive tests
6. Update documentation

**Questions for User**:
1. Do you agree with `~**` as the syntax? Other preferences?
2. Should `~**` work standalone (`arg ~**`) or only with fields (`arg {name ~str ~**}`)?
3. Do we need `$raw-args` scope in addition, or is shape-based solution sufficient?
