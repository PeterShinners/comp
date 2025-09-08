# Comp Language Implementation

A spec-driven implementation of the Comp programming language in Python.

## Project Structure

```
comp/
├── LICENSE             # Project license
├── README.md           # This file
├── specs/              # Language specifications
│   ├── core-spec.md    # Core language specification
│   └── examples/       # Example programs
│       └── basic-examples.md
├── design/             # Design documents
│   ├── roadmap.md      # Implementation roadmap
│   ├── builtin-types-operators-units-tags.md
│   ├── modules-imports-namespaces-entry.md
│   ├── functions-shapes-blocks-pure.md
│   ├── structures-spreads-lazy.md
│   ├── failures-flow-control-pipelines.md
│   └── resources-transactions.md
├── tasks/              # Implementation tasks
│   └── phase0-setup.md # Current phase setup tasks
├── src/                # Implementation source code
│   └── comp/
│       └── grammar.lark # Language grammar definition
├── implementation/     # (Currently empty)
├── docs/               # Documentation and design notes
│   ├── ancient/        # Super old notes extracted from notion
│   └── early/          # Iterative design docs from claude
└── tests/              # Test suites
    └── test_specs/     # (Currently empty)
```

## Quick Start

1. **Review Specs**: Start with `specs/core-spec.md` for language overview
2. **Check Roadmap**: See `design/roadmap.md` for implementation phases
3. **Current Task**: Check `tasks/` for current implementation focus
4. **Run Tests**: `pytest tests/` to verify implementation matches specs

## Development Workflow

### Spec-Driven Development Process

1. **Spec First**: Every feature starts with a specification
2. **Examples Next**: Write example code that should work
3. **Tasks Breakdown**: Break implementation into small tasks
4. **Test Driven**: Write tests from examples before implementing
5. **Implement**: Build feature following the spec
6. **Validate**: Ensure all examples pass

### Adding a New Feature

1. Write/update specification in `specs/`
2. Add examples to `specs/examples/`
3. Create tasks in `tasks/`
4. Write tests in `tests/`
5. Implement in `src/comp/`
6. Update `design/decisions.md` with any design choices made

## Dependencies

```bash
pip install lark pytest attrs
```

## Current Status

- [ ] Phase 0: Project Setup
- [ ] Phase 1: Basic Parser
- [ ] Phase 2: Core Evaluator
- [ ] Phase 3: Type System
- [ ] Phase 4: Standard Library
- [ ] Phase 5: REPL & Dev Tools

## Resources

- Original design discussions: [See design/decisions.md]
- Language philosophy: [See design/philosophy.md]
- Implementation roadmap: [See design/roadmap.md]