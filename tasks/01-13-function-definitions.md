# Phase 13: Function Definitions

**Status**: ✅ **COMPLETED**  
**Created**: October 2025  
**Completed**: October 2025

## Overview

This phase implements function definitions at the module level, completing the core declarative features of Comp. Function definitions create named, reusable operations that can be invoked via pipeline operators.

All the supporting infrastructure already exists:
- ✅ Function references (`|funcname`) - Phase 4
- ✅ Pipeline operations - Phase 9
- ✅ Structures and blocks - Phase 5
- ✅ Scopes (`$in`, `^arg`, `$ctx`, `@var`) - Phase 8
- ✅ Shape morphing for parameters - Phase 12

This phase just adds the **definition** side - creating functions at module level.

### What's Included in This Phase

**Core Function Features**:
- Top-level function definitions with `!func`
- Function signatures with parameter shapes
- Function bodies (blocks)
- Default parameter values
- Variadic parameters (spread)
- Multiple dispatch via shape overloading
- Dotted function names (namespacing)

**Explicitly Deferred**:
- Function constraints and guards
- Return type annotations
- Generic/parameterized functions
- Async/concurrent functions
- Performance optimization/caching

## Function Definition Syntax

Functions are defined at module level using the `!func` operator. A function **always** has:
1. **Input shape** - defines what data the function expects from the pipeline (`$in`) - **REQUIRED**
2. **Argument shape** (optional) - defines additional parameters passed with `^{...}`
3. **Body** - a block that implements the function

**Syntax**: `!func |name ~input-shape ^{args} = {body}`

The input shape is **always required**, even for functions that don't need input data (use `~nil`). This emphasizes that functions exist to transform data flowing through pipelines.

The `^` prefix on the argument shape is **only** allowed in function definitions. Everywhere else, shapes use `~` prefix.

### Simple Function Definitions

```comp
; Function with input shape and arguments
!func |add ~{x ~num y ~num} = {
    $in.x + $in.y
}

; Input from pipeline, arguments for configuration
!func |map ~list ^{fn ~:{~any}} = {
    [$in |each fn]
}

; Input shape with arguments that have defaults
!func |greet ~str ^{greeting ~str = "Hello"} = {
    "${greeting}, ${$in}!"
}

; Input shape only, no arguments
!func |double ~num = {
    $in * 2
}

; No input data needed - explicitly use ~nil
!func |random ~nil = {
    [|system/random]
}

!func |five ~nil = {
    5
}

!func |now ~nil = {
    [|system/time]
}

; Arguments only, but still need input shape (often ~any or ~nil)
!func |create-user ~nil ^{name ~str email ~str} = {
    {
        id = [|uuid]
        name = name
        email = email
        created = [|now]
    }
}

; Positional input shape
!func |multiply ~{~num ~num} = {
    #0 * #1
}

; Tag-based arguments for flags
!func |sort ~list ^{order #sort-order = #asc} = {
    [order |match
        #asc -> {$in |sort-ascending}
        #desc -> {$in |sort-descending}
    ]
}
```

### Input Shape vs Arguments

The **input shape** (`~shape`) defines what flows through the pipeline - **always required**:
```comp
!func |double ~num = {$in * 2}

[5 |double]              ; Input: 5, Result: 10

!func |five ~nil = {5}   ; No input needed, but shape still required

[|five]                  ; No input, Result: 5
```

The **argument shape** (`^{...}`) defines explicit parameters - **optional**:
```comp
!func |add ~nil ^{x ~num y ~num} = {x + y}

[|add ^{x=5 y=10}]       ; Arguments: x=5, y=10, Result: 15
```

Both together create flexible functions:
```comp
!func |format ~str ^{prefix ~str = "" suffix ~str = ""} = {
    "${prefix}${$in}${suffix}"
}

["world" |format ^{prefix="Hello, " suffix="!"}]
; Input: "world", Arguments: prefix, suffix
; Result: "Hello, world!"
```

### Dotted Function Names (Namespacing)

```comp
; Functions can be organized with dotted names
!func |math.add ~{x ~num y ~num} = {x + y}
!func |math.multiply ~{x ~num y ~num} = {x * y}

!func |string.upper ~str = {
    [$in |system/string/upper]
}

!func |user.create ~nil ^{name ~str email ~str} = {
    {
        id = [|uuid]
        name = name
        email = email
        created = [|now]
    }
}

; Invocation uses the full dotted name
[{x=5 y=10} |math.add]        ; Input: {x=5 y=10}, Result: 15
["hello" |string.upper]       ; Input: "hello", Result: "HELLO"
[|user.create ^{name="Alice" email="a@x.co"}]  ; No input (nil), arguments only
```

### Function Overloading (Multiple Dispatch)

```comp
; Multiple function definitions with same name
; Dispatched by input shape specificity
!func |process ~num = {
    $in * 2
}

!func |process ~str = {
    "${$in}!"
}

!func |process ~num[] = {
    [$in |map :{#0 * 2}]
}

; Input shape specificity determines which overload is called
[5 |process]              ; 10 (first overload)
["hello" |process]        ; "hello!" (second overload)
[{1 2 3} |process]        ; {2 4 6} (third overload)

; More specific input shapes win
!func |handle ~any = {"generic"}
!func |handle ~user = {"user-specific"}
!func |handle ~admin-user = {"admin-specific"}

; Can also overload on argument shapes
!func |create-point ^{x ~num y ~num} = {{x=x y=y}}
!func |create-point ^{x ~num y ~num z ~num} = {{x=x y=y z=z}}
```

!func |process ^{value ~str} = {
    "${value}!"
}

!func |process ^{values ~num[]} = {
    [values |map :{#0 * 2}]
}

; Shape specificity determines which overload is called
[5 |process]              ; 10 (first overload)
["hello" |process]        ; "hello!" (second overload)
[{1 2 3} |process]        ; {2 4 6} (third overload)

; More specific shapes win
!func |handle ^{data ~any} = {"generic"}
!func |handle ^{data ~user} = {"user-specific"}
!func |handle ^{data ~admin-user} = {"admin-specific"}

; When shapes have equal specificity, order matters (first match wins)
```

### Block Return Values

```comp
; Function body is a block - last expression is the return value
!func |calculate ^{x ~num} = {
    @temp = x * 2
    @result = @temp + 10
    @result              ; Implicit return
}

; Single expression functions
!func |double ^{x ~num} = {x * 2}

; Pipeline as return value
!func |get-user ^{id ~str} = {
    [id |db/query "users" |first]
}

; Structure as return value
!func |make-point ^{x ~num y ~num} = {
    {x = x y = y}
}
```

### Functions with Context

```comp
; Functions can access $ctx for configuration
!func |log ^{message ~str level ~str = "info"} = {
    @timestamp = [|now]
    @output = {
        time = @timestamp
        level = level
        message = message
        context = $ctx
    }
    [@output |system/log]
}

; Functions can accept blocks for callbacks
!func |retry ^{operation ~:{} max-attempts ~num = 3} = {
    [1 max-attempts |range |each :{
        @result = [|: operation]
        [@result |if-error
            :{[#0 < max-attempts |if
                :{[|continue]}
                :{[#0 |throw]}
            ]}
            :{@result}
        ]
    }]
}
```

## Grammar Design

### Module-Level Function Definition

```lark
// Function definition token
BANG_FUNC: "!func"

// Function definition syntax - input shape is ALWAYS required:
function_definition: BANG_FUNC function_path input_shape arg_shape ASSIGN block
                   | BANG_FUNC function_path input_shape ASSIGN block    // No arguments

// Function path (like tag/shape paths)
function_path: PIPE TOKEN (DOT TOKEN)*

// Input shape (what comes from pipeline) - REQUIRED
input_shape: shape_type    // ~shape or ~{...} or ~nil, etc.

// Argument shape (explicit parameters with ^) - OPTIONAL
arg_shape: CARET shape_body    // ^{params}

// Reuses existing shape_type and shape_body from Phase 12
```

### Integration with Existing Grammar

The function definition integrates with Phase 12:
- `shape_type` for input shape (already implemented)
- `shape_body` for argument shape (already implemented)
- `block` for function body (already implemented)
- `function_reference` for invocation (already implemented)

**Design notes**:
- Input shape is **always required** (use `~nil` if no input needed)
- Argument shape is **optional** (omit if no arguments)
- The `^` prefix on `arg_shape` is **unique to function definitions**

## AST Node Design

### Module-Level Nodes

```python
class FuncDef(AstNode):
    """Function definition at module level: !func |name ~input ^{args} = {body}
    
    A function always has an input shape (use ~nil if no input needed).
    The argument shape is optional.
    
    Examples:
        !func |double ~num = {$in * 2}
        !func |add ~{x ~num y ~num} = {$in.x + $in.y}
        !func |greet ~str ^{greeting ~str = "Hello"} = {"${greeting}, ${$in}"}
        !func |random ~nil = {[|system/random]}
        !func |create ~nil ^{name ~str} = {{name=name}}
    """
    
    def __init__(self, tokens: list[str], input_shape: AstNode, arg_shape: AstNode | None = None):
        """Initialize function definition.
        
        Args:
            tokens: Function name parts (e.g., ["math", "add"])
            input_shape: Input shape (REQUIRED - use ~nil if no input)
            arg_shape: Argument shape (ShapeBody), or None for no arguments
        """
        self.tokens = tokens         # Function name components
        self.input_shape = input_shape  # Input shape (always present)
        self.arg_shape = arg_shape    # Argument shape or None
        super().__init__()
    
    @property
    def name(self):
        """Full function name as dotted path."""
        return ".".join(self.tokens)
    
    @property
    def body(self):
        """Function body block (first/only child)."""
        return self.kids[0] if self.kids else None
    
    def unparse(self) -> str:
        """Unparse function definition back to source code."""
        func_name = "|" + self.name
        input_str = self.input_shape.unparse()
        
        if self.arg_shape:
            arg_str = f"^{self.arg_shape.unparse()}"
            return f"!func {func_name} {input_str} {arg_str} = {self.body.unparse()}"
        else:
            return f"!func {func_name} {input_str} = {self.body.unparse()}"
    
    @classmethod
    def from_grammar(cls, tree):
        """Parse from Lark tree.
        
        Grammar:
            function_definition: BANG_FUNC function_path input_shape arg_shape ASSIGN block
                               | BANG_FUNC function_path input_shape ASSIGN block
        
        Tree structure:
            - BANG_FUNC token
            - function_path tree (contains TOKEN+)
            - input_shape tree
            - [arg_shape tree] (optional)
            - ASSIGN token
            - block tree
        """
        path_node = None
        input_node = None
        arg_node = None
        
        for child in tree.children:
            if isinstance(child, lark.Tree):
                if child.data == "function_path":
                    path_node = child
                elif child.data == "input_shape":
                    # input_shape: shape_type
                    input_node = child.children[0] if child.children else None
                elif child.data == "arg_shape":
                    # arg_shape: CARET shape_body
                    arg_node = child.children[1] if len(child.children) > 1 else None
        
        if not path_node:
            raise ValueError("Function definition missing function_path")
        if not input_node:
            raise ValueError("Function definition missing input_shape (use ~nil if no input)")
        
        # Extract tokens from path: TOKEN (DOT TOKEN)*
        tokens = [tok.value for tok in path_node.children if hasattr(tok, 'type') and tok.type == 'TOKEN']
        
        return cls(tokens=tokens, input_shape=input_node, arg_shape=arg_node)
```

## Implementation Strategy

### Phase 1: Basic Function Definitions
1. Add `BANG_FUNC` token to lexer
2. Implement `function_definition` grammar rule
3. Implement `function_path` grammar rule
4. Create `FuncDef` AST node
5. Add transformer case for `function_definition`
6. Test simple functions without parameters

### Phase 2: Function Signatures
1. Implement `function_signature` grammar rule (reuses `shape_body`)
2. Update `FuncDef` to handle signatures
3. Test functions with typed parameters
4. Test functions with defaults
5. Test functions with positional parameters

### Phase 3: Advanced Features
1. Add support for dotted function names
2. Add support for variadic parameters (shape spread)
3. Add support for block parameters
4. Test complex function definitions
5. Test multiple dispatch scenarios

### Phase 4: Integration
1. Ensure function definitions work in modules
2. Test function invocation with pipeline operators
3. Test scope access in function bodies (`$in`, `^args`, `@vars`)
4. Test roundtrip parsing

## Test Strategy

### Valid Function Definitions

```python
@comptest.params(
    "code",
    input_only=("!func |double ~num = {$in * 2}",),
    input_and_args=("!func |greet ~str ^{greeting ~str = \"Hello\"} = {greeting}",),
    nil_input=("!func |random ~nil = {[|system/random]}",),
    nil_with_args=("!func |create ~nil ^{name ~str} = {{name=name}}",),
    positional_input=("!func |multiply ~{~num ~num} = {#0 * #1}",),
    dotted_name=("!func |math.add ~{x ~num y ~num} = {$in}",),
    tag_arg=("!func |sort ~list ^{order #order = #asc} = {$in}",),
    block_arg=("!func |map ~list ^{fn ~:{~any}} = {fn}",),
    variadic_arg=("!func |sum ~nil ^{..values ~num} = {values}",),
    complex=(
        "!func |process ~{x ~num y ~num} ^{mode #mode = #fast} = {$in}",
    ),
)
def test_valid_function_definitions(key, code):
    result = comp.parse_module(code)
    assert isinstance(result, comp.Module)
    assert len(result.statements) == 1
    assert isinstance(result.statements[0], comp.FuncDef)
    comptest.roundtrip(result)
```

### Function Name Parsing

```python
@comptest.params(
    "code,expected_tokens",
    simple=("!func |add ~nil = {5}", ["add"]),
    dotted=("!func |math.add ~num = {$in}", ["math", "add"]),
    deep=("!func |a.b.c ~str = {$in}", ["a", "b", "c"]),
)
def test_function_name_tokens(key, code, expected_tokens):
    """Test that function names are parsed into correct token lists."""
    result = comp.parse_module(code)
    func_def = result.statements[0]
    assert func_def.tokens == expected_tokens
    comptest.roundtrip(result)
```

### Input and Argument Shapes

```python
@comptest.params(
    "code",
    with_args=("!func |add ~num ^{x ~num} = {$in}",),
    without_args=("!func |double ~num = {$in}",),
    nil_input=("!func |five ~nil = {5}",),
)
def test_function_shapes(key, code):
    """Test functions with and without argument shapes."""
    result = comp.parse_module(code)
    func_def = result.statements[0]
    
    # Input shape is always present
    assert func_def.input_shape is not None
    
    # Argument shape may or may not be present
    if "^{" in code:
        assert func_def.arg_shape is not None
    else:
        assert func_def.arg_shape is None
    
    comptest.roundtrip(result)
```

### Function Overloading

```python
def test_multiple_function_definitions():
    """Test multiple functions with same name (overloading)."""
    code = """
        !func |process ~num = {$in * 2}
        !func |process ~str = {$in}
    """
    code = """
        !func |process ^{x ~num} = {x * 2}
        !func |process ^{x ~str} = {x}
    """
    
    result = comp.parse_module(code)
    assert len(result.statements) == 2
    assert all(isinstance(s, comp.FuncDef) for s in result.statements)
    assert all(s.name == "process" for s in result.statements)
    
    comptest.roundtrip(result)
```

### Invalid Function Syntax

```python
@comptest.params(
    "code",
    missing_input=("!func |add ^{x ~num} = {x}",),  # Missing input shape
    missing_body=("!func |add ~num ^{x ~num}",),
    missing_pipe=("!func add ~num = {$in}",),
    no_equals=("!func |add ~num {$in}",),
    nested_func=("{!func |add ~nil = {5}}",),
)
def test_invalid_function_syntax(key, code):
    comptest.invalid_parse(code, match=r"parse error|unexpected")
```

## Success Criteria

### Function Definitions
- ✅ Parse input shape (always required): `!func |double ~num = {$in * 2}`
- ✅ Parse with ~nil input: `!func |random ~nil = {5}`
- ✅ Parse with arguments: `!func |add ~num ^{x ~num} = {$in + x}`
- ✅ Parse with defaults: `!func |greet ~str ^{greeting ~str = "World"} = {greeting}`
- ✅ Parse with positional input: `!func |multiply ~{~num ~num} = {#0 * #1}`
- ✅ Parse dotted function names: `!func |math.add ~num = {$in}`
- ✅ Parse functions with tag parameters: `!func |sort ^{order #order} = {order}`
- ✅ Parse functions with block parameters: `!func |map ^{fn ~:{}} = {fn}`
- ✅ Parse variadic functions: `!func |sum ^{..values} = {values}`
- ✅ Parse multiple functions with same name (overloading)
- ✅ Round-trip all function definitions

### Integration
- ✅ All existing tests still pass
- ✅ Function definitions work at module level only
- ✅ Function bodies are blocks with proper scope
- ✅ Signatures reuse shape_body from Phase 12

## Implementation Notes

### Signature Reuse

The function signature `^{params}` is just a shape body prefixed with `^`. This means:
- All shape field syntax works: named, positional, defaults, spreads, blocks
- Tag fields work for flag-style parameters
- Union types work for polymorphic parameters
- Everything from Phase 12 applies

### Multiple Dispatch

Multiple function definitions with the same name create overloads. At runtime:
1. All overloads with matching name are candidates
2. Shape specificity ranking determines which is called
3. Same specificity algorithm as shape union morphing (Phase 12)
4. First definition wins on ties

This is parsing only - the actual dispatch happens at runtime.

### Function Bodies

Function bodies are blocks (`{...}`), which means:
- Last expression is the return value
- Local variables with `@var`
- Access to `$in` (pipeline input)
- Access to `^param` (named parameters)
- Access to `$ctx` (context)
- Access to `#0`, `#1`, etc. (positional access)

All scope handling already implemented in Phase 8.

## Design Considerations

### Why `!func` and not `fn` or `def`?

Consistency with `!shape` and `!tag` - all module-level definitions use `!` prefix. Functions are declarative module members, not imperative statements.

### Why `^` for signatures?

The caret `^` already means "argument scope" in references (`^arg`). Using it in signatures creates symmetry:
- Definition: `!func |add ^{x ~num}` - declares what parameters exist
- Reference: `[value |add ^{x=5}]` - provides argument values
- Body: `{^x + 1}` - accesses parameter value

### Why allow no signature?

Some functions take no parameters and only use `$in` from the pipeline or context:
```comp
!func |random = {[|system/random]}
!func |now = {[|system/time]}
```

This is simpler than requiring empty signature `^{}`.

### Dotted Names vs Modules

Dotted names (`|math.add`) are just naming convention, not module system. They:
- Help organize functions
- Prevent name collisions
- Create logical grouping

Actual module imports/namespacing handled by separate `!import` (future phase).

## Estimated Complexity

**Size**: Medium (simpler than shapes or tags)
**Difficulty**: Easy (all pieces already exist)
**Risk**: Low (straightforward grammar addition)

**Breakdown**:
- Grammar rules: ~10 lines
- AST nodes: 1 new class
- Parser cases: ~3 new cases
- Tests: ~25-30 test cases

**Expected Duration**: 1-2 sessions

## Key Design Decisions

**Reused Infrastructure**:
- ✅ `shape_body` for parameter signatures (Phase 12)
- ✅ `block` for function bodies (Phase 5)
- ✅ `function_reference` for invocation (Phase 4)
- ✅ Scope system for parameter access (Phase 8)

**Design Philosophy**:
- Module-level definitions use `!` prefix for consistency
- Signatures are just shapes (reuse everything from Phase 12)
- Bodies are just blocks (reuse everything from Phase 5)
- Multiple dispatch through shape specificity (same algorithm as unions)

## Status: Ready to Begin

This phase completes the core declarative features of Comp! After this:
- ✅ Tags defined (`!tag`) and referenced (`#tag`)
- ✅ Shapes defined (`!shape`) and used (`~shape`)
- ✅ Functions defined (`!func`) and called (`|func`)

Future phases can add:
- Module system (`!import`, `!export`)
- Entry points and program structure
- Advanced function features (constraints, generics, async)
- Runtime implementation of function dispatch

All prerequisites are in place from Phases 4, 5, 8, 9, and 12.
