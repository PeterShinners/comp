# Phase 02-01: Module Namespace Building

**Status**: 📝 Ready to Start  
**Started**: _Not yet started_  
**Completed**: _Not yet completed_

## Goals

Build a namespace from a parsed module AST. Take the top-level definitions (tags, shapes, functions) and create a runtime namespace that can be queried and used for execution. This is the foundation for function calling and pipeline execution.

## What We're Building

### Module to Namespace

Given a parsed `Module` AST with definitions:
```comp
!tag #status = {#active #inactive}
!shape ~point = {x ~num y ~num}
!func |double ~num = {@ * 2}
```

Build a **namespace object** containing:
- Tag definitions with their hierarchy
- Shape definitions with their structure
- Function definitions ready to call

### Namespace Structure

```python
class Namespace:
    """Runtime namespace built from module definitions."""
    
    def __init__(self):
        self.tags: dict[str, TagDef] = {}      # Tag definitions
        self.shapes: dict[str, ShapeDef] = {}   # Shape definitions  
        self.funcs: dict[str, FuncDef] = {}     # Function definitions
    
    def get_tag(self, path: list[str]) -> TagDef | None:
        """Look up tag by path like ['status', 'active']"""
        
    def get_shape(self, name: str) -> ShapeDef | None:
        """Look up shape by name like 'point'"""
        
    def get_func(self, name: str) -> FuncDef | None:
        """Look up function by name like 'double'"""
```

### Definition Objects

Wrap the AST definitions with runtime metadata:

```python
class TagDef:
    """Runtime tag definition."""
    def __init__(self, ast_node: comp.ast.TagDefinition):
        self.ast = ast_node
        self.path = ast_node.tokens  # ['status', 'active']
        self.value = None  # Evaluated later
        self.children: dict[str, TagDef] = {}
        
class ShapeDef:
    """Runtime shape definition."""
    def __init__(self, ast_node: comp.ast.ShapeDef):
        self.ast = ast_node
        self.name = ".".join(ast_node.tokens)
        self.fields = None  # Processed later
        
class FuncDef:
    """Runtime function definition."""
    def __init__(self, ast_node: comp.ast.FuncDef):
        self.ast = ast_node
        self.name = ".".join(ast_node.tokens)
        self.shape = None  # Input shape (processed later)
        self.args = None   # Arg shape (processed later)
```

## Success Criteria

- [ ] `Namespace` class that holds all definitions
- [ ] `build_namespace(module: comp.ast.Module) -> Namespace` function
- [ ] Tag definitions extracted and organized hierarchically
- [ ] Shape definitions extracted with names
- [ ] Function definitions extracted with names
- [ ] Namespace lookup methods work correctly
- [ ] Unit tests for namespace building
- [ ] Handle duplicate definition errors

## Implementation Plan

### Step 1: Namespace Class
```python
# src/comp/run/_namespace.py

class Namespace:
    """Runtime namespace containing module definitions."""
    
    def __init__(self):
        self.tags: dict[str, TagDef] = {}
        self.shapes: dict[str, ShapeDef] = {}
        self.funcs: dict[str, FuncDef] = {}
    
    def add_tag(self, tag_def: TagDef):
        """Register a tag definition."""
        path_key = ".".join(tag_def.path)
        if path_key in self.tags:
            raise NameError(f"Tag {path_key} already defined")
        self.tags[path_key] = tag_def
        
    def add_shape(self, shape_def: ShapeDef):
        """Register a shape definition."""
        if shape_def.name in self.shapes:
            raise NameError(f"Shape {shape_def.name} already defined")
        self.shapes[shape_def.name] = shape_def
        
    def add_func(self, func_def: FuncDef):
        """Register a function definition."""
        if func_def.name in self.funcs:
            raise NameError(f"Function {func_def.name} already defined")
        self.funcs[func_def.name] = func_def
```

### Step 2: Definition Wrappers
```python
# src/comp/run/_defs.py

class TagDef:
    """Runtime representation of a tag definition."""
    def __init__(self, ast_node: comp.ast.TagDefinition):
        self.ast = ast_node
        self.path = ast_node.tokens
        # Value and children processed later when needed
        
class ShapeDef:
    """Runtime representation of a shape definition."""
    def __init__(self, ast_node: comp.ast.ShapeDef):
        self.ast = ast_node
        self.name = ".".join(ast_node.tokens)
        
class FuncDef:
    """Runtime representation of a function definition."""
    def __init__(self, ast_node: comp.ast.FuncDef):
        self.ast = ast_node
        self.name = ".".join(ast_node.tokens)
```

### Step 3: Build Namespace from Module
```python
# src/comp/run/_build.py

def build_namespace(module: comp.ast.Module) -> Namespace:
    """Extract all definitions from a module into a namespace."""
    ns = Namespace()
    
    for child in module.kids:
        if isinstance(child, comp.ast.TagDefinition):
            tag_def = TagDef(child)
            ns.add_tag(tag_def)
            
        elif isinstance(child, comp.ast.ShapeDef):
            shape_def = ShapeDef(child)
            ns.add_shape(shape_def)
            
        elif isinstance(child, comp.ast.FuncDef):
            func_def = FuncDef(child)
            ns.add_func(func_def)
            
        # Ignore other top-level expressions for now
    
    return ns
```

### Step 4: Tag Hierarchy Building
```python
def build_tag_hierarchy(ns: Namespace):
    """Organize tags into hierarchy based on paths."""
    # For tag #status.active.running:
    # - Create parent #status if needed
    # - Create parent #status.active if needed  
    # - Link them together
    
    for path_key, tag_def in ns.tags.items():
        path = tag_def.path
        for i in range(len(path) - 1):
            parent_path = path[:i+1]
            parent_key = ".".join(parent_path)
            # Create implicit parent if missing
            # Link child to parent
```

## Design Decisions

### Lazy vs Eager Processing

**Decision**: **Lazy** - Don't evaluate tag values or process shape fields yet
- Just extract definitions from AST
- Keep reference to original AST node
- Process/evaluate when actually needed

**Rationale**: 
- Tags might have generator functions we can't execute yet
- Shape fields might reference undefined shapes
- Keep this phase simple and focused

### Duplicate Definitions

**Decision**: **Error on duplicates**
- Cannot define same tag/shape/function twice
- Helps catch user errors early
- Keeps namespace clean

### Hierarchical Tags

**Decision**: **Build hierarchy explicitly**
- Tag `#status.active` creates parent `#status` if needed
- Parent tags are implicit but navigable
- Makes tag lookups and comparisons easier

## What We're NOT Building (Yet)

- **Value evaluation** - Not evaluating tag values or default expressions
- **Shape validation** - Not checking if shapes are well-formed
- **Function execution** - Not calling functions yet
- **Expression evaluation** - Not evaluating any expressions
- **Type checking** - Not validating anything matches shapes

## Files to Create

- `src/comp/run/_namespace.py` - Namespace class
- `src/comp/run/_defs.py` - TagDef, ShapeDef, FuncDef classes
- `src/comp/run/_build.py` - build_namespace() function
- `src/comp/run/__init__.py` - Export public API
- `tests/test_namespace.py` - Namespace building tests
- `tests/test_tag_hierarchy.py` - Tag hierarchy tests

## Test Strategy

```python
def test_simple_namespace():
    source = """
    !tag #active
    !shape ~point = {x ~num y ~num}
    !func |double ~num = {@ * 2}
    """
    module = comp.parse_module(source)
    ns = build_namespace(module)
    
    assert ns.get_tag(['active']) is not None
    assert ns.get_shape('point') is not None
    assert ns.get_func('double') is not None

def test_tag_hierarchy():
    source = "!tag #status.active"
    module = comp.parse_module(source)
    ns = build_namespace(module)
    
    # Implicit parent created
    assert ns.get_tag(['status']) is not None
    assert ns.get_tag(['status', 'active']) is not None
```

## Expected Challenges

- **Tag hierarchy** - Creating implicit parent tags correctly
- **Name resolution** - What if shape references undefined shape?
- **Duplicate detection** - Error messages that are helpful
- **Module traversal** - Handling all AST node types gracefully

## Success Metrics

- Can extract all definition types from module
- Tag hierarchy built correctly with implicit parents
- Duplicate definitions detected and reported
- >90% test coverage for namespace building

## Next Phase

After this: **02-02 Function Calling** - Use the namespace to actually call functions with pipelines!

---

**Note**: This "top-down" approach (definitions → namespace → execution) lets us explore the interesting problems (function dispatch, pipeline execution) before getting bogged down in expression evaluation.

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
