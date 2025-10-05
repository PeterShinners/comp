# Comp CLI Usage Guide

The `comp` command-line tool allows you to run Comp programs from `.comp` files.

## Installation

Install comp in your Python environment:

```bash
# Using uv (recommended)
uv pip install -e .

# Or with pip
pip install -e .
```

## Basic Usage

```bash
comp <file.comp>
```

The tool will:
1. Read and parse the `.comp` file
2. Create a runtime module with builtin functions
3. Look for a `main` function
4. Execute the `main` function
5. Print the result

## Example Program

Create a file `hello.comp`:

```comp
!func |main ~_ = {
    message = "Hello from Comp!"
    result = [message |upper]
}
```

Run it:

```bash
comp hello.comp
```

Output:
```
{message="Hello from Comp!" result="HELLO FROM COMP!"}
```

## With uv run

You can also use `uv run` without installing:

```bash
uv run comp examples/working/hello.comp
```

## Implementation Status

**Note**: The `examples/` directory contains both:
- `working/` - Examples that run with v0.1.0 
- Root level - Design demonstrations requiring unimplemented features

Always use examples from `examples/working/` to test the current implementation.

## Requirements

Every Comp program must have a `main` function:

```comp
!func |main ~_ = {
    // Your code here
}
```

The `main` function:
- Must be named exactly `main`
- Can take any shape parameter (commonly `~_` for "any shape")
- Will be invoked with empty scopes (`$in`, `$ctx`, `$mod`, `$arg` all empty)
- Should return a structure with your results

## Builtin Functions

The following builtin functions are automatically available:

- `print` - Prints the input value and passes it through (useful for debugging)
- `double` - Doubles numeric values or all numeric fields in a structure
- `upper` - Converts strings to uppercase
- `lower` - Converts strings to lowercase

Example using builtins:

```comp
!func |main ~_ = {
    text = "hello world"
    loud = [text |upper]
    check = [loud |print]
}
```

## Error Handling

### File Not Found
```bash
$ comp missing.comp
Error: File not found: missing.comp
```

### No Main Function
```bash
$ comp myfile.comp
Error: No 'main' function found in myfile.comp

Define a main function like:
  !func |main ~_ = {
    ...
  }
```

### Parse Error
```bash
$ comp bad.comp
Parse error in bad.comp:
  Parse error: Unexpected token...
```

### Runtime Error
```bash
$ comp crash.comp
Error running crash.comp:
  ValueError: Field 'x' not found in scope
```

## Exit Codes

- `0` - Success
- `1` - Error (file not found, parse error, runtime error, or missing main function)

## Examples

See the `examples/working/` directory for complete working programs:

- `examples/working/hello.comp` - Simple hello world
- `examples/working/greet.comp` - Function composition
- `examples/working/pipeline.comp` - Data transformation pipelines

The main `examples/` directory contains design demonstrations that require features not yet implemented.

## Tips

1. **Start simple**: Begin with a basic `main` function and add complexity gradually
2. **Use builtins**: Leverage builtin functions for common operations
3. **Print for debugging**: Use `|print` in pipelines to see intermediate values
4. **Check syntax**: Make sure all structures use `{...}` and pipelines use `[...]`

## Common Patterns

### Processing Data

```comp
!func |main ~_ = {
    data = {value = 42}
    result = [data |double]
}
```

### String Manipulation

```comp
!func |main ~_ = {
    text = "comp language"
    formatted = [text |upper]
}
```

### Multi-step Pipelines

```comp
!func |process ~{x ~num} = {
    result = x + 10
}

!func |main ~_ = {
    value = [{x = 5} |double |process]
}
```
