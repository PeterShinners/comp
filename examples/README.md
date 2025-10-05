# Comp Examples

This directory contains example Comp programs.

## ⚠️ Implementation Status

**Currently Working** (v0.1.0): The examples in the `working/` subdirectory can be run with the current interpreter.

**Future Examples**: Most examples in this directory demonstrate the *design* of the Comp language and require features not yet implemented (blocks, loops, pattern matching, morphing, etc.).

## Working Examples (v0.1.0)

These examples work with the current implementation:

### working/hello.comp
A simple "Hello World" program that uses the builtin `upper` function:

```bash
comp examples/working/hello.comp
```

Output: `{message="Hello from Comp!" result="HELLO FROM COMP!"}`

### working/greet.comp
Demonstrates function definitions and composition:

```bash
comp examples/working/greet.comp
```

Shows how to define functions that take arguments and call them from `main`.

### working/pipeline.comp
Demonstrates pipeline composition with transformations:

```bash
comp examples/working/pipeline.comp
```

Shows how values flow through multiple function calls.

## Future Examples (Design Demonstrations)

The following examples showcase the full Comp language design but require unimplemented features:

- **cart.comp** - Shopping cart with shape morphing and reduce
- **tree.comp** - Binary search tree with pattern matching
- **wordcount.comp** - Text processing with I/O and fold operations
- **nushell.comp** - Command pipeline demonstrations
- **mayatool.comp** - 3D graphics tool integration
- **rio-todo.comp** - Todo app with UI framework
- **io-uring.comp** - Async I/O examples
- **lockless.comp** - Concurrent data structures
- **cloudflaire-ai.comp** - AI API integration

These examples will become runnable as the interpreter gains more features.

## What's Currently Supported

The v0.1.0 interpreter supports:

✅ Number and string literals  
✅ Structure literals `{field = value}`  
✅ Mathematical operators (`+`, `-`, `*`, `/`, etc.)  
✅ Pipelines `[seed |func1 |func2]`  
✅ Function definitions with parameters  
✅ Builtin functions (`print`, `double`, `upper`, `lower`)  
✅ Namespace resolution (`|func/builtin`)  
✅ Tag references (`#true`, `#false`)  

## What's Not Yet Implemented

❌ Blocks `:{ ... }`  
❌ Pattern matching `|match`  
❌ Conditionals `|if`, `|valve`  
❌ Loops `|map`, `|fold`, `|reduce`  
❌ Shape morphing `value ~shape`  
❌ Array syntax `~type[]`  
❌ I/O operations  
❌ Module imports  
❌ Advanced operators  

## Running Examples

After installing comp:

```bash
comp examples/working/hello.comp
```

Or with uv run (no install needed):

```bash
uv run comp examples/working/hello.comp
```

## Writing Your Own

Every Comp program needs a `main` function to serve as the entry point:

```comp
!func |main ~_ = {
    result = "Your code here"
}
```

The `main` function should:
- Be named exactly `main`
- Take any shape (commonly `~_` for "any")
- Return a structure with your results

See `working/` directory for complete working examples you can use as templates.
