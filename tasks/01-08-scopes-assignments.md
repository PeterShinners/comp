# Phase 01-08: Scopes and Assignments

**Status**: ❌ NOT STARTED  
**Target start**: After advanced operators are complete

## Overview

Implement parsing for scope operators and references (`$ctx`, `$mod`, `$in`, `$out`, `^`, `@`) and their assignments. This phase builds the foundation for Comp's explicit scoping system which eliminates variable capture mysteries and provides predictable data flow. All scopes use explicit prefixes and have well-defined behavior for field lookup and assignment.

This phase focuses purely on parsing - the runtime behavior of scopes will be implemented in Phase 02-02 "Implement scope referencing and overwriting".

## Planned Features

### Scope References
- **`$ctx`** - Execution context shared across function calls (inherited down call stack)
- **`$mod`** - Module-level globals shared across the entire module  
- **`$in`** - Input context (current pipeline data, resets at statement boundaries)
- **`$out`** - Output context (fields being generated for return structure)
- **`$arg`** - Function arguments (rarely accessed directly)
- **`^`** - Combined scope (`$arg` + `$ctx` + `$mod` morphed to function argument shape)
- **`@`** - Function-local temporaries (cleared when function completes)

### Field Access on Scopes
- **Simple references**: `$ctx`, `$mod.config`, `@temp`, `^timeout` 
- **Special scope syntax**: `^count` (no dot required), `@local` (no dot required, no dot allowed)
- **Nested field access**: `$ctx.database.url`, `$mod.settings.retry-count`, `@user.profile.name`, `^args.timeout`
- **Deep paths**: `$out.result.data.field` (unlimited nesting depth)
- **Note**: `^` and `@` do not require a dot before their first field name

### Scope Assignments
- **Basic assignment**: `$ctx.session = token`, `@counter = 0`
- **Field assignment**: `$mod.config.port = 8080`, `$out.result.status = #success`
- **Assignment operators**: `=`, `=*` (strong), `=?` (weak)
- **Deep field assignment**: Creates new nested structures preserving immutability

### Assignment Targets in Structures
- **Scope targets**: `{$ctx.data = value}`, `{@local = temp}`
- **Field targets**: `{result.field = expression}`, `{deep.nested.path = value}`
- **Mixed operations**: `{$mod.global = setting, local-field = data, @temp = intermediate}`

## Success Criteria

### Scope Reference Parsing
- [ ] Parse `$ctx`, `$mod`, `$in`, `$out`, `$arg` with field paths
- [ ] Parse `^` and `@` standalone and with field paths  
- [ ] Support arbitrary nesting: `$scope.field.subfield.deep.path`
- [ ] Validate scope names (only predefined scope names allowed)

### Scope Assignment Parsing
- [ ] Parse scope assignments with all operators (`=`, `=*`, `=?`)
- [ ] Support assignments to deep field paths
- [ ] Parse scope assignments within structure literals
- [ ] Handle mixed scope/field assignments in same structure

### Grammar Integration
- [ ] Integrate with existing expression precedence
- [ ] Support scope references in all expression contexts
- [ ] Maintain compatibility with existing AST structure
- [ ] Proper operator precedence for scope operations

### AST Node Structure
- [ ] `ScopeReference` nodes with scope name and field path
- [ ] `ScopeTarget` nodes for assignment targets  
- [ ] `ScopeAssignment` nodes for structured scope assignments
- [ ] Field path represented as string arrays for nested access

## Implementation Plan

### Step 1: Extend Grammar for Scope References
```lark
// Add scope reference tokens
SCOPE_PREFIX: "$" | "@" | "^"
SCOPE_NAME: "ctx" | "mod" | "in" | "out" | "arg"

// Scope reference patterns  
scope_reference: SCOPE_PREFIX SCOPE_NAME field_path?     // $ctx.field.path
               | "@" IDENTIFIER field_path?              // @local.field (no dot before first identifier)
               | "^" IDENTIFIER field_path?              // ^timeout.field (no dot before first identifier)
               | "@"                                     // Bare @ scope
               | "^"                                     // Bare ^ scope

field_path: (DOT IDENTIFIER)+                           // .field.subfield.etc
```

### Step 2: Create AST Node Types
- **ScopeReference**: Represents `$mod.field.subfield` references
- **ScopeTarget**: Represents assignment targets like `$ctx.session` 
- **ScopeAssignment**: Represents `$scope.field = expression` in structures

### Step 3: Extend Structure Operation Parsing
- Support scope targets in structure literals
- Handle mixed scope/field assignments
- Maintain existing positional field support

### Step 4: Expression Integration
- Allow scope references in all expression contexts
- Proper precedence handling
- Field access chaining support

## Key Design Decisions

### Special Scope Parsing Rules
- **`^` and `@` scopes**: Do not require a dot before their first field name
  - `^timeout` parses as scope=`^`, field_path=`["timeout"]`
  - `^timeout.retry` parses as scope=`^`, field_path=`["timeout", "retry"]`
  - `@counter` parses as scope=`@`, field_path=`["counter"]`
- **`$` scopes**: Always require explicit scope name after the `$`
  - `$ctx.session` parses as scope=`$`, scope_name=`ctx`, field_path=`["session"]`
- **Scope integration**: Scopes can be used anywhere identifiers are valid
- **Scope precedence**: Scope prefixes bind more tightly than field access

### Explicit Scope Names Only
- Only predefined scopes allowed for `$`: `ctx`, `mod`, `in`, `out`, `arg`
- `^` and `@` scopes do not use explicit scope names after the prefix
- No arbitrary `$name` variables - function-local variables use `@name` format
- This ensures predictable scope behavior and prevents typos

### Field Path Representation
- Store field paths as arrays of strings: `["field", "subfield", "deep"]`
- Enables efficient field access at runtime
- Supports arbitrary nesting depth
- For `^` and `@`: First identifier goes directly in field_path (no dot required)

### Assignment Operator Support
- All assignment operators work with scopes: `=`, `=*`, `=?`
- Strong assignment (`=*`) resists overwriting when the same field is set multiple times
- Weak assignment (`=?`) only assigns if field doesn't exist

### Immutable Deep Assignment
- Deep field assignment creates new nested structures
- Preserves immutability throughout the hierarchy  
- Assignment target determines where value goes

## Examples to Support

```comp
// Basic scope references
session-id = $ctx.session
port = $mod.config.port  
input-data = $in.payload
current-result = $out.status
timeout = ^timeout           // No dot required after ^
counter = @local-counter     // No dot required after @

// Scope assignments in structures  
{
    $ctx.session = new-token
    $mod.config.retry = 3
    @temp-data = intermediate        // No dot after @
    ^user-timeout = 30              // No dot after ^
    result.field = computed-value
}

// Deep field assignments
{
    $ctx.database.connection.pool-size = 20
    $out.response.headers.content-type = "application/json"
    @cache-user.profile.updated = (|now/time)    // @ with nested path
    ^args.database.timeout = 30                  // ^ with nested path
}

// Mixed assignment operators
{
    $ctx.setting =? default-value    // Weak - only if not set
    $mod.global =* persistent-value  // Strong - resists overwriting
    @temp = temp-calculation         // Normal assignment
}

// Complex nested access
database-url = $mod.config.database.connections.primary.url
user-permissions = $ctx.auth.user.roles.permissions
response-data = $out.api.response.data.payload
retry-count = ^args.retry-count          // No dot after ^
temp-result = @calculation.intermediate  // @ with field path
```

## AST Node Specifications

### ScopeReference
```python
class ScopeReference(ASTNode):
    def __init__(self, scope_type: str, scope_name: str, field_path: list[str]):
        self.scope_type = scope_type  # "$", "@", "^"  
        self.scope_name = scope_name  # "ctx", "mod", "in", "out", "arg", or None
        self.field_path = field_path  # ["field", "subfield", ...]
```

### ScopeTarget  
```python
class ScopeTarget(ASTNode):
    def __init__(self, scope_type: str, scope_name: str, field_path: list[str]):
        self.scope_type = scope_type  # "$", "@", "^"
        self.scope_name = scope_name  # "ctx", "mod", etc., or None
        self.field_path = field_path  # ["field", "subfield", ...]
```

### ScopeAssignment
```python  
class ScopeAssignment(ASTNode):
    def __init__(self, target: ScopeTarget, operator: str, value: ASTNode):
        self.target = target         # ScopeTarget node
        self.operator = operator     # "=", "=*", "=?"
        self.value = value          # Expression being assigned
```

## Test Structure

Tests organized by scope type and functionality:
- `tests/test_scope_references.py` - Basic scope reference parsing
- `tests/test_scope_assignments.py` - Scope assignment parsing  
- `tests/test_scope_field_paths.py` - Deep field path handling
- `tests/test_scope_mixed_operations.py` - Mixed scope/field operations

## What We're NOT Building (Yet)

- Runtime scope behavior and field resolution
- Scope inheritance and context passing  
- Scope validation and error handling
- Function argument morphing into `^` scope
- Scope-based field lookup resolution

## Future Phases

- **Phase 02-02**: "Implement scope referencing and overwriting" - Runtime scope behavior
- **Phase 02-03**: "Structure creation" - How scopes integrate with structure building
- **Phase 03-XX**: "Function Definitions" - How `^` scope gets constructed from arguments