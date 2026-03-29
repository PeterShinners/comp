# Python Style

1. **No Type Annotations**: Never use type hints or annotations. Do not import from `typing` module.
   - Document types in docstrings using Google-style format instead

2. **Docstrings**: Use Google-style docstrings
   ```python
   def example(name, count):
       """Brief description of function.

       Longer description if needed.

       Args:
           name: (str) Description of name parameter
           count: (int) Description of count parameter

       Returns:
           (bool) Description of return value

       Raises:
           ValueError: When something is wrong
       """
   ```

3. **No __init__ docstrings**: Document initialization parameters in the class docstring, not in `__init__`

4. **Imports**:
   - Always `import comp` to access sibling modules through public interface
   - For internal cross-module access: `comp._sibling.internal_func()`
   - Avoid `from X import Y` - use qualified names like `decimal.Decimal`
   - Import modules, not objects: `import decimal` not `from decimal import Decimal`

5. **Naming**:
   - Use `snake_case` for functions, methods, variables
   - Use `PascalCase` for classes
   - Follow PEP 8 conventions strictly

6. **Quotes**: Always use double quotes `"` for strings, never single quotes `'`

7. **Module structure**:
   - Internal modules are prefixed with underscore: `_value.py`, `_parse.py`
   - Public API is exposed through `__init__.py`

## Project Philosophy

- **Clarity over performance** - Optimize for understandability, not speed. Design for future efficiency but don't implement optimizations yet.
- **Experimentation-friendly** - Add debugging/inspection tools (flags, output modes) that make the system easy to explore and understand.
- **Minimal scope** - Don't add documentation files, extra features, or "nice to haves" unless explicitly requested.
- **Ask, don't assume** - When multiple valid approaches exist, ask for direction rather than making architectural decisions.

