# Comp Core Language Specification

## Overview

Comp is a data-flow programming language where all computation happens through immutable structs flowing through transformation pipelines.

## Core Principles

1. **Everything is a struct** - All data, including scalars, are treated as structs
2. **Immutable data flow** - Data flows left-to-right through pipelines
3. **Structural typing** - Types are defined by structure, not names
4. **No function arguments** - All functions receive a single struct

## Basic Types

### Primitives

```comp
// Numbers
42
3.14
-17

// Strings  
"hello"
"interpolated ${value}"

// Booleans (implemented as tags)
#true
#false

// Nil (empty struct)
{}
```

### Structs

Structs are the fundamental data container:

```comp
// Empty struct
{}

// Named fields
{x=10 y=20}

// Unnamed fields (positional)
{1 2 3}

// Mixed
{name="Alice" 30 active=#true}

// Spread operator
{...base_struct new_field=value}
```

### Automatic Scalar Wrapping

Scalars automatically become single-element structs when needed:

```comp
5 -> increment        // 5 becomes {5}
"hello" -> uppercase  // "hello" becomes {"hello"}
```

## Pipeline Operators

### Basic Invoke (`->`)

Transforms data through functions or struct construction:

```comp
data -> function_name
data -> {result=@}           // @ is input reference
{x=1} -> {y=2 ...@}          // Result: {x=1 y=2}
```

### Iteration Pipeline (`=>`)

Iterates over unnamed fields:

```comp
{1 2 3} => double            // Each element doubled
{1 2 3} => {value=@ index=@idx}  // With index
```

### Conditional Pipeline (`?>`)

Executes only if condition is truthy:

```comp
data ?> validate -> process   // Process only if validate succeeds
```

### Failure Handler (`!>`)

Handles failures in pipeline:

```comp
risky_operation !> handle_error
risky_operation !> {fallback=true}
```

## Variables and Bindings

### Variable Declaration

```comp
!var.name = value             // Immutable binding
$name = value                 // Local binding in expression
```

### Labels

```comp
data -> process -> !label $result
$result -> further_processing
```

## Functions

### Basic Function

```comp
!func :double = {
    @ * 2
}

5 -> :double                  // Returns 10
```

### Pattern Matching Function

```comp
!func :describe = @ -> match {
    0 -> "zero"
    {x y} -> "2D point"
    _ -> "something else"
}
```

## Shapes (Types)

### Shape Definition

```comp
!shape ~Point = {
    x ~number
    y ~number
}

!shape ~Circle = {
    center ~Point
    radius ~number
}
```

### Shape Application

```comp
data ~ Shape                  // Cast to shape
data ~? Shape                 // Check if matches shape
```

## String Interpolation

```comp
name = "World"
greeting = "Hello ${name}"    // "Hello World"

// Lazy evaluation
template = "Result: ${expensive_calc}"  // Not evaluated until used
```

## Comments

```comp
// Single line comment
/* Multi-line 
   comment */
```

## Example Program

```comp
!shape ~Item = {
    name ~string
    price ~number
    quantity ~number
}

!func :calculate_total ~Item = {
    price * quantity
}

!func :process_cart = {
    items => :calculate_total -> :sum
}

!main = {
    $cart = {
        {name="Apple" price=1.00 quantity=3}
        {name="Banana" price=0.50 quantity=6}
    }
    
    $total = $cart -> :process_cart
    "Total: $${total}" -> :print
}
```

## Key Behaviors

1. **Automatic struct wrapping** for scalars in function calls
2. **Structural sharing** for performance in spread operations
3. **Lazy evaluation** for string interpolation
4. **Failure propagation** through pipelines
5. **Shape morphing** with named, tagged, and positional matching