# Claude Code Instructions

## Primary Style Guide

**IMPORTANT**: Before starting any work, read and follow the style guide in `.github/copilot-instructions.md`. That file is the source of truth for code style, naming conventions, and project structure.

## Quick Reference (from .github/copilot-instructions.md)

Key style rules to remember:
- **No type annotations** - Document types in docstrings instead
- **Double quotes only** - Always use `"` never `'`
- **Import modules, not objects** - Use `import comp` not `from comp import X`
- **Google-style docstrings** with type info in Args/Returns
- **No __init__ docstrings** - Document init params in class docstring

## Claude Code Specific Notes

When starting a session:
1. Read `.github/copilot-instructions.md` to refresh on style rules
2. Follow all conventions in that file
3. Use the project structure documented there

This ensures consistency between Claude Code and GitHub Copilot suggestions.
