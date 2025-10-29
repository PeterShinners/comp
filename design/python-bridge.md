# Python Bridge Implementation

*Design notes for the Python interoperability system using handles and private data*

## Overview

The Python bridge (`stdlib/python`) provides seamless interoperability between Comp and Python by wrapping Python objects as Comp handles. This enables Comp code to call Python libraries, manipulate Python objects, and convert between Python and Comp data structures while maintaining type safety through the handle system.

**Key insight**: Python objects are stored in handle private data using wrapper objects to prevent automatic conversion by the Value constructor. This keeps Python objects opaque to the Comp runtime while allowing controlled conversion when needed.

## Handle-Based Design

All Python objects are represented as `@py-handle` instances. The handle's private data stores the actual Python object, ensuring:
1. Python objects stay opaque to Comp (no automatic tuple→struct conversion)
2. Python objects can be passed through pipelines without copying
3. Type safety through handle morphing (released handles can't be used)
4. Clean module boundary (only python module accesses private data)

```comp
; All Python bridge functions use @py-handle
!func |push/py ~any = @py-handle          ; Python object → @py-handle
!func |pull/py ~{@py-handle} = ~any       ; @py-handle → Comp value
!func |lookup/py ~{name~str} = @py-handle ; Module/function lookup
!func |call/py ~{self @py-handle} = @py-handle    ; Method calls
!func |call/py ~any = @py-handle                   ; Function calls
```

## Private Data Storage

Python objects are wrapped in `_PythonObjectWrapper` to prevent the Value constructor from auto-converting them:

```python
class _PythonObjectWrapper:
    """Wrapper to prevent Value from converting Python objects.
    
    Without this wrapper, Python tuples would be automatically converted
    to Comp structures by the Value constructor. This wrapper keeps the
    Python object opaque.
    """
    def __init__(self, obj):
        self.obj = obj
```

The wrapper is stored in the handle's private data:

```python
# In push() - create handle with wrapped Python object
handle = HandleInstance(handle_def=py_handle_def, ...)
wrapper = _PythonObjectWrapper(python_obj)
handle.private_data['__python_object__'] = wrapper

# In pull() and call_method() - extract Python object
wrapper = handle_instance.private_data.get('__python_object__')
if not isinstance(wrapper, _PythonObjectWrapper):
    raise TypeError(f"Handle does not contain a Python object")
python_obj = wrapper.obj
```

**Why this works:**
- Value constructor sees wrapper object, not the Python object
- Wrapper has no special meaning to Value, so no automatic conversion
- Python module controls wrapper creation/extraction
- Clean separation: Comp runtime never sees raw Python objects

## Function Overloads and Dispatch

The Python bridge uses two overloads for `|call` to handle both function calls and method calls:

```python
# Generic function call - accepts any input
@python_module.function("|call", comp.parse_shape("~any"))
def call_function(pipe_input, arg_struct, frame):
    # Handles: call_python_function(name, args)
    # Input: {name="print", args=["hello"]}
    ...

# Method call on Python object - more specific
@python_module.function("|call", comp.parse_shape("~{self @py-handle}"))
def call_method(pipe_input, arg_struct, frame):
    # Handles: py_obj.method(args)
    # Input: {self=@py-handle, method_name="connect", ...}
    ...
```

**Dispatch resolution:**
- Both overloads registered as PythonFunction instances
- PipeFunc detects multiple PythonFunction overloads
- Calls `select_overload()` to choose best match based on input shape
- Morph scoring ensures `~{self @py-handle}` ranks higher than `~any` when handle present
- Handle depth contributes to morph score (combined with tag depth)

This is implemented in `ast/_pipe.py` lines 178-204:

```python
# Check if ALL candidate functions are PythonFunctions
if all(isinstance(fn, PythonFunction) for fn in candidate_funcs):
    if len(candidate_funcs) == 1:
        # Single PythonFunction - fast path
        py_func = candidate_funcs[0]
        generator = py_func.invoke(...)
    else:
        # Multiple PythonFunctions - need overload selection
        selected = comp.select_overload(
            candidate_funcs,
            self.pipe_input or comp.Value(comp.Structure({})),
            self.arg_struct
        )
        generator = selected.invoke(...)
    
    # Drive generator protocol to completion
    for value in generator:
        pass  # Consume generator
    return value
```

## Morph Scoring with Handles

Handle depth is combined with tag depth in the morph scoring algorithm to ensure proper overload resolution:

```python
# In _morph.py morph scoring (line 797-804):
handle_depth_sum = sum(depth for depth, _ in handle_matches)
tag_depth_sum = sum(depth for depth, _ in tag_matches)
combined_depth = handle_depth_sum + tag_depth_sum

return MorphResult(
    named_matches=named_matches,
    tag_depth=combined_depth,  # Combined handle + tag depth
    positional_matches=positional_matches,
    value=result_value
)
```

This ensures that:
- `~{self @py-handle}` ranks higher than `~any` (handle_depth=1 vs 0)
- More specific handles rank higher in hierarchies
- Tags and handles both contribute to specificity
- Consistent scoring across all overload resolution

## API Functions

### |push/py - Convert Comp to Python

```comp
!func |push/py ~any = @py-handle
```

Converts Comp values to Python objects:
- Numbers → int/float
- Strings → str
- Booleans (#true/#false) → True/False
- Structures → dict
- Arrays → list
- Existing @py-handle → passthrough (extract Python object)

Returns `@py-handle` wrapping the Python object.

### |pull/py - Convert Python to Comp

```comp
!func |pull/py ~{@py-handle} = ~any
```

Extracts Python object from handle and converts to Comp:
- int/float → Number
- str → String
- bool → #true/#false
- dict → Structure
- list → list of Values
- tuple → list of Values (not Structure - intentional)
- None → empty structure {}

### |lookup/py - Module/Function Lookup

```comp
!func |lookup/py ~{name~str} = @py-handle
```

Imports Python module or looks up function/attribute:
- `{name="sqlite3"}` → import and return module
- `{name="os.path.join"}` → traverse dotted path, return object

Returns `@py-handle` wrapping the Python object.

### |call/py - Function/Method Calls

```comp
!func |call/py ~any = @py-handle                    ; Function call
!func |call/py ~{self @py-handle} = @py-handle      ; Method call
```

**Function call** (generic overload):
```comp
[{name="print" args=["hello"]} |call/py]
```

**Method call** (handle-specific overload):
```comp
[{name="sqlite3"} |lookup/py {method_name="connect" database=":memory:"} |call/py]
```

Both return `@py-handle` wrapping the result.

### |struct-from-object/py - Object to Struct

```comp
!func |struct-from-object/py ~{@py-handle fields~str[]} = ~any
```

Extracts specified fields from Python object into Comp structure:
```comp
[py_obj {fields=["name" "age" "email"]} |struct-from-object/py]
; Returns: {name=... age=... email=...}
```

## Usage Patterns

### Calling Python Libraries

```comp
!import /py = stdlib "python"

; Import Python module
$var.sqlite = [{name="sqlite3"} |lookup/py]

; Call Python function
$var.conn = [{
    self=$var.sqlite 
    method_name="connect" 
    database=":memory:"
} |call/py]

; Call method on Python object
$var.cursor = [{self=$var.conn method_name="cursor"} |call/py]

; Execute SQL
$var.result = [{
    self=$var.cursor 
    method_name="execute" 
    sql="CREATE TABLE users (id INTEGER, name TEXT)"
} |call/py]

; Convert result to Comp
$var.rows = [{self=$var.cursor method_name="fetchall"} |call/py |pull/py]
```

### Wrapping Python APIs

The SQLite wrapper (`stdlib/sqlite.comp`) demonstrates clean Python API wrapping:

```comp
!import /py = stdlib "python"

!func |open ~{path~str} = {
    [{name="sqlite3"} |lookup/py {
        self=$in 
        method_name="connect" 
        path=$arg.path
    } |call/py]
}

!func |execute ~{conn@py-handle sql~str} = {
    [{self=$arg.conn method_name="execute" sql=$arg.sql} |call/py]
}

!func |query ~{conn@py-handle sql~str} = {
    $var.cursor = [{conn=$arg.conn sql=$arg.sql} |execute/sqlite]
    [{self=$var.cursor method_name="fetchall"} |call/py |pull/py]
}
```

## Design Benefits

1. **Type Safety**: Handles prevent use after release, morph system catches errors
2. **Clean Separation**: Python objects stay opaque, controlled conversion at boundaries
3. **Composability**: Handles flow through pipelines naturally
4. **Dispatch Clarity**: Overload resolution based on input shape, not execution order
5. **Module Encapsulation**: Only python module accesses private data

## Implementation Files

- `src/comp/corelib/python.py` - Python bridge implementation
  - Lines 20-28: `_PythonObjectWrapper` class
  - Lines 62-103: `push()` - Comp to Python conversion
  - Lines 106-146: `pull()` - Python to Comp conversion
  - Lines 149-238: `lookup()` - Module/attribute lookup
  - Lines 352-411: `call_function()` - Generic function call
  - Lines 411-524: `call_method()` - Handle-specific method call
  - Lines 525-585: `struct_from_object()` - Object field extraction

- `src/comp/_morph.py` - Morph scoring with handles
  - Lines 790-804: Combined handle + tag depth scoring

- `src/comp/ast/_pipe.py` - PipeFunc dispatch
  - Lines 175-209: PythonFunction overload resolution

## Testing

All Python bridge functionality is validated through:
- `tests/test_python_interop.py` - 6 tests covering push/pull/lookup/call
- `tests/ct_python.comp` - 5 Comp-side tests for Python integration

All tests passing confirms:
- Handle creation and storage works
- Private data survives pipeline operations
- Overload resolution selects correct function
- Python objects stay opaque to Comp runtime
- Conversion preserves data integrity
