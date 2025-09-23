# Agent Develo## Development Process

Use **Agent-Assisted Development** with numbered phases:

### **Core Principles:**
1. **AI-readable specifications** - Clear, structured docs that agents can understand
2. **Incremental + adaptive** - Easy to adjust when design changes
3. **Context preservation** - Agents can pick up where they left off
4. **Change management** - Handle design evolution without throwing away work

### **The Development Process:**

#### **1. Phase Planning** (`tasks/XX-name.md`)
Each phase file contains:
- **Goals** (clear, specific objectives for AI context)
- **Success Criteria** (measurable checkboxes AI can verify)
- **Design References** (links to relevant design docs)
- **Implementation Notes** (architecture decisions, future considerations)

#### **2. Test-First Development** (`tests/test_feature.py`)
Tests serve as executable specifications with:
- **Specification summary** in module docstring
- **Design doc references** for authoritative behavior
- **Agent context** - what this enables, dependencies, error handling
- **Measurable assertions** that define "done"

#### **3. Implementation** (`src/comp/`)
Code includes documentation for:
- **Phase tracking** - which phase this implements
- **Test references** - which tests this satisfies
- **Design decisions** - why approach A over B
- **Future assumptions** - what this expects from later phases

#### **4. Change Management**
When design evolves:
1. **Update design docs first** (source of truth)
2. **Create new phase** for the change
3. **Update affected tests** with clear commit messages
4. **Implementation follows** test changes

### **Benefits for AI Assistance:**
- **Clear context** - AI can understand current state and goals
- **Resumable** - AI can pick up work from any phase
- **Traceable** - Easy to see why decisions were made
- **Adaptable** - Design changes have clear impact scope
- **Incremental** - Small, manageable chunks for AI to handleide for Comp Language

This document provides AI assistants with essential context for working on the Comp programming language implementation.

## Project Overview

**Comp** is a data-flow programming language where computation happens through immutable structs flowing through transformation pipelines. This is the Python implementation of the Comp interpreter/compiler.

**Key Design Principles:**
- Everything is a struct (unified data model)
- Immutable data flow (left-to-right pipelines) 
- Structural typing (shapes, not names)
- No function arguments (functions receive single struct)

## Development Process

Use **Agent-Assisted Development** with numbered phases:

1. **Phase Planning** (`tasks/XX-name.md`) - Goals, scope, success criteria
2. **Test-First** (`tests/test_XX_name.py`) - Executable specifications
3. **Implementation** (`src/comp/`) - Make tests pass
4. **Documentation** - Update phase status, document decisions

### **Current Phase**
Check `tasks/` directory for files marked "Ready to start" or "In progress".

### **Making Changes**
1. **Read the current phase file** to understand goals
2. **Check existing tests** to see what needs to work
3. **Implement incrementally** to make tests pass
4. **Update documentation** as you go

## Project Structure

```
design/          # Authoritative language design documents (READ THESE)
examples/        # Working collection of hypothetical Comp examples
tasks/           # Numbered phase planning (XX-name.md)
tests/           # Executable specifications (test_XX_name.py)  
src/comp/        # Implementation code
```

## Key Files for AI Context

### **Essential Reading:**
- `design/overview.md` - Language philosophy and core concepts
- `design/*.md` - All design documents contain authorative decisions
- Current phase file in `tasks/` - What is implementing now

### **Test Files:**
- `tests/test_feature.py` - Executable specs organized by language feature
- Tests define behavior precisely - make these pass
- Rich docstrings provide implementation context
- Tests evolve as features evolve across multiple phases

### **Implementation:**
- `src/comp/` - Python package (create as needed)
- Follow existing patterns and document decisions

## Development Workflow

### **Starting Work:**
1. Read current phase file for goals and context
2. Check if tests exist - run `pytest tests/` to see current state
3. Read relevant design docs for complete understanding
4. Implement incrementally

### **Testing:**
```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_02_basic_literals.py

# Run with verbose output
pytest -v tests/
```

### **Common Tasks:**

#### **Adding New Feature:**
1. Create new phase file: `tasks/XX-feature-name.md`
2. Write or update test specification: `tests/test_feature.py`
3. Implement in `src/comp/`
4. Update phase status when complete

#### **Changing Existing Feature:**
1. Update design/ docs first (source of truth)
2. Create task/ phase for the change
3. Update affected test/ files (may span multiple features)
4. Update implementation to match tests

## Architecture Notes

### **AST Design:**
- Simple dataclasses for AST nodes
- Preserve source information for error reporting
- Design for easy traversal and transformation

### **Testing Philosophy:**
- Tests are specifications - they define correct behavior
- Module level comprehensive docstrings explain requirements
- Link back to design documents for authority
- Test error cases and edge conditions
- Use pytest best practices
- Tests are organized by language feature, not implementation phase
- Each test file should define behavior clearly in comprehensive docstrings
- Include error cases and edge conditions
- Tests serve as both specification and verification

## Important Conventions

### **Process File Naming:**
- Task files: `XX-descriptive-name.md` (e.g., `02-basic-literals.md`)
- Test files: `test_feature.py` (e.g., `test_literals.py`, `test_structures.py`)
- Tests are organized by language feature, not implementation phase

### **Python Namespace and Conventions**
- The Python namespace is represented as a flat `comp` module
- This single import will provide the entire
- Usage is not expected to import individual values from the module (no from import)
- This module will be a package where the individual files are named with underscores
- Within the modules, they will prefer to use the public namespace and "import comp"
- To reference internal objects they will import from their siblings using "from . import _sibling"
- Sibling references will not "from import" values directly from siblings modules.
- Objects that are only intended to be used by the current module must be named with a leading underscore.
- Individual files will mark the objects intended for the public interface in the `__all__`.


### **Documentation Style:**
- Reference design docs for authoritative behavior
- Explain WHY decisions were made, not just WHAT
- Include context for future phases
- Document assumptions and dependencies

### **Code Style:**
- Follow design/syntax.md for language syntax rules
- Python code: Black formatting, clear naming
- Comprehensive docstrings with context

## Gotchas and Common Issues

### **Design Document Authority:**
- `design/` files are the source of truth for language behavior
- If tests contradict design docs, update tests first
- Implementation follows tests, not personal intuition

### **Phase Dependencies:**
- Phases build on each other - don't skip ahead
- If you need something from a future phase, create a minimal version
- Document assumptions about future implementations

### **Testing Strategy:**
- Write tests before implementation (specification-driven)
- Test both positive and negative cases
- Include edge conditions and error handling
- Tests should be readable as specifications

## Getting Help

### **Understanding Requirements:**
1. Check current phase file for immediate goals
2. Read relevant sections of design documents
3. Look at test docstrings for detailed requirements
4. Check examples/ directory for usage patterns

### **Design Questions:**
- Reference `design/overview.md` for philosophical guidance
- `design/syntax.md` for language syntax rules
- Specific design/*.md files for detailed behavior

### **Implementation Questions:**
- Check existing code patterns in `src/comp/`
- Look at similar languages for inspiration
- Keep it simple - prefer clarity over cleverness

---

**Remember:** This is incremental development. Focus on the current phase, make tests pass, document decisions, then move forward. The design documents provide the vision, the tests provide the specification, your job is to make them work together.