# Phase 02-01: Runtime Values

**Status**: 📝 Ready to Start  
**Started**: _Not yet started_  
**Completed**: _Not yet completed_

## Goals

Create the runtime value system - the actual data structures that represent Comp values during execution. This is the foundation for evaluation.

## What We're Building

### Value Types

We need runtime representations for all the data types Comp can work with:

1. **Numbers** - Integers and floats
   - Support Python numeric types
   - Handle numeric literals from AST
   
2. **Strings** - Text data
   - UTF-8 strings
   - Handle string literals from AST
   
3. **Tags** - Tagged values with hierarchy
   - Tag identity (#status.active)
   - Optional associated value
   
4. **Structures** - Key-value mappings
   - Named fields
   - Nested structures
   - Immutable by default
   
5. **Functions** - Callable operations
   - User-defined functions
   - Built-in functions
   - Closures (later)
   
6. **References** - Pointers to other values
   - Shape references
   - Function references
   - Tag references
   
7. **Nil** - Absence of value
   - Similar to None/null
   - Default for missing fields

### Value Protocol

All runtime values should support:
- **Type checking** - `isinstance(val, CompNumber)`
- **String representation** - `str(val)` for debugging
- **Equality** - Compare values
- **Immutability** - Values don't change (for now)

## Success Criteria

- [ ] Value classes defined for all core types
- [ ] Each value type has clear semantics
- [ ] Values can be constructed from AST nodes
- [ ] Values can be compared for equality
- [ ] Values have useful string representations
- [ ] Unit tests for value creation and behavior
- [ ] Documentation of value system design

## Implementation Plan

### Step 1: Base Value Class
```python
class CompValue:
    """Base class for all Comp runtime values."""
    
    def __repr__(self):
        """Debug representation."""
        raise NotImplementedError
    
    def __eq__(self, other):
        """Value equality."""
        raise NotImplementedError
    
    def comp_type(self):
        """Return the Comp type of this value."""
        raise NotImplementedError
```

### Step 2: Primitive Values
```python
class CompNumber(CompValue):
    def __init__(self, value: int | float):
        self.value = value

class CompString(CompValue):
    def __init__(self, value: str):
        self.value = value

class CompNil(CompValue):
    pass  # Singleton
```

### Step 3: Composite Values
```python
class CompStructure(CompValue):
    def __init__(self, fields: dict[str, CompValue]):
        self.fields = fields
    
    def get(self, key: str) -> CompValue:
        return self.fields.get(key, NIL)

class CompTag(CompValue):
    def __init__(self, path: list[str], value: CompValue = None):
        self.path = path  # e.g., ["status", "active"]
        self.value = value or NIL
```

### Step 4: Callable Values
```python
class CompFunction(CompValue):
    def __init__(self, name: str, params, body):
        self.name = name
        self.params = params
        self.body = body
    
    def call(self, args, context):
        """Execute the function."""
        raise NotImplementedError  # Chapter 02-06

class CompBuiltin(CompFunction):
    def __init__(self, name: str, python_func):
        super().__init__(name, None, None)
        self.python_func = python_func
```

### Step 5: Value Conversions
```python
def from_python(value: Any) -> CompValue:
    """Convert Python value to Comp value."""
    if isinstance(value, (int, float)):
        return CompNumber(value)
    elif isinstance(value, str):
        return CompString(value)
    elif value is None:
        return NIL
    elif isinstance(value, dict):
        return CompStructure({k: from_python(v) for k, v in value.items()})
    else:
        raise ValueError(f"Cannot convert {type(value)} to CompValue")

def to_python(value: CompValue) -> Any:
    """Convert Comp value to Python value."""
    if isinstance(value, CompNumber):
        return value.value
    elif isinstance(value, CompString):
        return value.value
    elif isinstance(value, CompNil):
        return None
    elif isinstance(value, CompStructure):
        return {k: to_python(v) for k, v in value.fields.items()}
    else:
        raise ValueError(f"Cannot convert {type(value)} to Python")
```

## Design Decisions

### Immutability vs Mutability

**Decision**: Start with **immutable values**
- Simpler to reason about
- Easier to implement
- Matches functional programming style
- Can add mutability later if needed

### Value Representation

**Decision**: Use Python classes, not dictionaries
- Type safety via `isinstance()`
- Better error messages
- Easier to add methods
- Clear hierarchy

### Nil vs None

**Decision**: Create `CompNil` instead of using Python's `None`
- Distinguishes "Comp nil" from "not computed yet"
- Allows nil to be a first-class value
- Can add methods if needed

### Tag Values

**Decision**: Tags store their full path
- Makes tag comparison easy
- Supports tag hierarchy naturally
- Path is `["status", "active"]` for `#status.active`

## What We're NOT Building (Yet)

- **Evaluation** - Not executing code, just representing values
- **Type checking** - Not validating types match shapes
- **Memory management** - Using Python's GC
- **Optimization** - No performance tuning yet
- **Advanced types** - No streams, resources, stores yet

## Files to Create

- `src/comp/_values.py` - All value type definitions
- `tests/test_values.py` - Value creation and behavior tests
- `tests/test_conversions.py` - Python ↔ Comp conversion tests

## Expected Challenges

- **Tag hierarchy** - How to represent and compare hierarchical tags?
- **Structure equality** - Deep comparison of nested structures
- **Function equality** - When are two functions equal?
- **Type representation** - How to represent shape types at runtime?

## Success Metrics

- All primitive types work correctly
- Structures support nested values
- Tags with hierarchy parse and compare
- Python conversions work bidirectionally
- >95% test coverage for value types

## Next Phase

After this: **02-02 Expression Evaluation** - Use these values to actually evaluate expressions!

---

**Note**: This phase lays the foundation for everything else. Get this right and evaluation becomes much easier.
