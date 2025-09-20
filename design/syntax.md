# Comp Language Syntax Reference

## Namespaces

### Variable and Pipeline Namespaces
- `$name` - Function-local variables
- `^name` - Function arguments (cascades to `$ctx`, `$mod`)
- `$in` - Pipeline input data
- `fieldname` - Undecorated tokens access pipeline fields (cascade output→input)

### Explicit Namespaces
- `$ctx.name` - Execution context
- `$mod.name` - Module-level data

## Function Definitions

### Basic Syntax
```comp
!func |name ~{pipeline-shape} ^{arguments} = { body }
```

### Multi-line Format
```comp
!doc "Description"
!pure
!require permissions
!func |function-name 
    ~{complex-shape} 
    ^{complex-args} = {
    ; Implementation
}
```

### Internal Shape Definitions
```comp
!func |complex = {
    !shape {data ~record}
    !args {options ~config}
    ; Implementation
}
```

### Key Principles
- Function names require `|` prefix
- Complex shapes defined separately for reuse
- Last expression is implicit return
- Pipeline shape uses `~` prefix
- Arguments use `^` prefix

## Blocks

### Block Syntax
- `.{}` - Block (deferred code)
- `{}` - Structure literal

### Named Blocks
```comp
transform.{$in * 2}
validate.{$in > 0}
on-error.{|log-error}
```

### Control Flow
```comp
|if .{condition} .{then-branch} .{else-branch}
|map .{$in * 2}
|filter .{score > threshold}
```

## Field Access

### Standard Access
- `fieldname` - Field lookup in pipeline
- `data.field` - Named field on structure
- `data#0` - Positional index (numeric literals only)
- `#0` - Index from `$in`

### Computed Access
- `data."string literal"` - String as field name
- `data.'expression'` - Evaluated expression as field name

## Type Literals

### Basic Types
- `"string"` - String literal
- `42` - Number literal  
- `#true`, `#false` - Boolean tags
- `#enum-value` - Tag values

### No Unquoted Strings
Undecorated tokens are field lookups, not string literals.

## Presence-Check Morphing

### Flag Arguments
```comp
!func |process ^{
    verbose ~bool = #false ?? #true
    debug ~bool = #false ?? #true
} = {
    ; verbose=#true if "verbose" appears as unnamed argument
}

; Usage
(data |process verbose debug)
```

The `??` operator defines: default value (left) and presence value (right).

## Pipeline vs Arguments

- **Pipeline (~)**: Data to transform
- **Arguments (^)**: Configuration for transformation
- **Blocks**: Deferred transformations as arguments

## Main Function

The `!main` function has no pipeline input or arguments:
```comp
!main = {
    args = |args/cmdline
    env = |env/process
    ; Implementation
}
```

## Style Conventions

- lisp-case naming
- `?` suffix for boolean fields and functions
- Attached function references: `|function`
- Tabs for indentation
- Operators at start of continuation lines