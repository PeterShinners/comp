# Comp Project - Claude Code Instructions

## Style Guide

**CRITICAL**: Always follow the code style rules in `.github/copilot-instructions.md`

Key rules (see that file for full details):
- **No type annotations** - Document types in docstrings instead
- **Double quotes only** - Always use `"` never `'`
- **Import modules not objects** - Use `import comp` not `from comp import X`
- **Clarity over performance** - Simple, readable code first
- **Minimal scope** - Don't add extras unless explicitly requested
- **Ask, don't assume** - When multiple approaches exist, ask for direction

## Project Philosophy

From `.github/copilot-instructions.md`:

1. **Clarity over performance** - Optimize for understandability. The current design should allow for future efficiency, but don't implement optimizations yet.

2. **Experimentation-friendly** - Add debugging/inspection tools (flags, output modes) that make the system easy to explore and understand.

3. **Minimal scope** - Don't add documentation files, extra features, or "nice to haves" unless explicitly requested.

4. **Ask, don't assume** - When multiple valid approaches exist, ask for direction rather than making architectural decisions.

## Before Starting Work

1. Read `.github/copilot-instructions.md` to refresh on style rules
2. Follow all conventions documented there
3. Keep code simple and direct - avoid over-engineering

## Testing

- The `tests/` directory is broken (from 2 implementations ago) - don't use it
- Create temporary test scripts in project root for testing (like `test_*.py`)
- Use `uv run` to execute scripts

## Running Code

Always use `uv run` prefix:
- `uv run comp file.comp --cop`
- `uv run python test_something.py`
