# Changelog

All notable changes to the Comp language implementation will be documented in this file.

## [0.1.0] - 2025-10-05

### 🎉 First Milestone Release!

A working Comp interpreter with command-line interface. Programs can now be written in `.comp` files and executed!

### Added

#### Language Features
- **Number literals**: Integer and decimal support with multiple bases (binary, octal, hex)
- **String literals**: Full unicode support with escape sequences
- **Structure literals**: Nested structures with named and unnamed fields
- **Operators**: Mathematical (`+`, `-`, `*`, `/`, `//`, `%`, `**`) and string concatenation
- **Identifiers**: Field access with scopes (`@`, `^`, `$name`)
- **Pipelines**: Data transformation with `[seed |func1 |func2]` syntax
- **Pipe operations**: Function calls (`|func`), struct transforms (`|{field=expr}`)
- **Tag references**: `#tag` and `#tag/namespace`
- **Shape references**: `~shape` and `~shape/namespace`
- **Function references**: `|func` and `|func/namespace`

#### Runtime System
- **Module system**: Parse, process, and resolve Comp modules
- **Function definitions**: Multiple implementations with shape matching
- **Tag definitions**: With value expressions
- **Shape definitions**: Type constraints (basic structure)
- **Scope handling**: `$in`, `$out`, `$arg`, `$ctx`, `$mod` scopes
- **Namespace resolution**: Module references with fallback search
- **Pipeline execution**: Multi-stage data transformations
- **Python function integration**: `PythonFuncImpl` for native functions

#### Builtin Functions
- `print` - Debug output (passthrough)
- `double` - Double numeric values
- `upper` - String uppercase conversion
- `lower` - String lowercase conversion

#### Builtin Tags
- `#true` and `#false` - Singleton boolean tags
- `#skip` and `#break` - Control flow tags

#### Command-Line Interface
- `comp` command to run `.comp` files
- Main function invocation
- Helpful error messages
- Exit codes for success/failure

#### Developer Tools
- 537 passing tests across all features
- Comprehensive test coverage
- Example programs demonstrating features
- Documentation for CLI usage

### Technical Highlights

- **Namespace-based module system**: Builtins accessed via shared module reference
- **Singleton tag instances**: Ensures `#true` is the same object across all modules
- **Scope chaining**: Proper resolution order for identifiers
- **Pipeline scoping**: Arguments evaluated with pipeline value as `$in`
- **Python interoperability**: Native functions integrate seamlessly

### Examples

Three working example programs included:
- `hello.comp` - Simple greeting with string transformation
- `greet.comp` - Function composition
- `pipeline.comp` - Multi-step data processing

### Documentation

- Updated README with Quick Start
- CLI usage guide
- Examples directory README
- Inline code documentation

### Known Limitations

This release implements core language features. Not yet implemented:
- Shape morphing (`~` operator)
- Blocks and block invocation
- Fallback operators (`??`, `|?`)
- Loop constructs
- Conditional constructs (valve)
- Module imports
- File I/O
- More comprehensive standard library

---

## [0.0.1] - 2024-2025

### Initial Development

- Grammar definition with Lark parser
- AST node structure
- Basic parsing implementation
- Test framework setup
- Agent-assisted development process
- Design documents in `design/` directory

---

[0.1.0]: https://github.com/PeterShinners/comp/releases/tag/v0.1.0
[0.0.1]: https://github.com/PeterShinners/comp/commits/main
