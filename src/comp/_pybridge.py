"""Python bridge for working with Comp code from Python.

This module provides Pythonic interfaces for:
- Loading and importing Comp modules
- Calling Comp functions from Python
- Converting between Python and Comp values
- Accessing module definitions (tags, functions, shapes)

Example:
    import comp
    
    # Load a comp module
    sqlite = comp.load_module("comp", "stdlib/sqlite.comp")
    
    # Call functions with automatic conversion
    db = sqlite.func.connect(input="demo.db")
    
    # Access tags
    success_tag = sqlite.tag.success
"""

__all__ = [
    "CompError",
    "load_module",
    "from_python",
    "to_python",
    "parse_value",
    "ModuleProxy",
]

import decimal
import pathlib

import comp


class CompError(Exception):
    """Exception raised when a Comp function returns a failure value.
    
    This wraps a Comp failure Value and provides Python-friendly error reporting.
    
    Attributes:
        failure: The original Comp failure Value
        message: Formatted error message
    """
    
    def __init__(self, failure):
        """Initialize CompError from a Comp failure Value.
        
        Args:
            failure: Comp Value that is a failure
        """
        self.failure = failure
        self.message = comp.format_failure(failure)
        super().__init__(self.message)
    
    def __str__(self):
        return self.message


def from_python(value):
    """Convert a Python value to a Comp Value.
    
    Conversion rules:
    - None → empty struct {}
    - bool → #true or #false tag
    - int/float → Decimal number
    - str → string
    - dict → struct (recursively converts keys and values)
    - list/tuple → struct with unnamed fields
    - Decimal → number (passed through)
    - comp.Value → passed through unchanged
    
    Args:
        value: Python value to convert
        
    Returns:
        comp.Value: Converted Comp value
        
    Examples:
        >>> from_python(42)
        Value(Decimal('42'))
        >>> from_python({'x': 1, 'y': 2})
        Value({Value('x'): Value(Decimal('1')), Value('y'): Value(Decimal('2'))})
        >>> from_python([1, 2, 3])
        Value({Unnamed(0): Value(Decimal('1')), Unnamed(1): Value(Decimal('2')), ...})
    """
    # Already a Comp Value
    if isinstance(value, comp.Value):
        return value
    
    # None becomes empty struct
    if value is None:
        return comp.Value({})
    
    # Booleans become tags
    if isinstance(value, bool):
        builtin = comp.builtin.get_builtin_module()
        if value:
            return comp.Value(comp.TagRef(builtin.tags["true"]))
        else:
            return comp.Value(comp.TagRef(builtin.tags["false"]))
    
    # Numbers
    if isinstance(value, (int, float)):
        return comp.Value(decimal.Decimal(str(value)))
    
    if isinstance(value, decimal.Decimal):
        return comp.Value(value)
    
    # Strings
    if isinstance(value, str):
        return comp.Value(value)
    
    # Dictionaries become structs with named fields
    if isinstance(value, dict):
        struct = {}
        for k, v in value.items():
            key = comp.Value(k) if isinstance(k, str) else from_python(k)
            struct[key] = from_python(v)
        return comp.Value(struct)
    
    # Lists and tuples become structs with unnamed fields
    if isinstance(value, (list, tuple)):
        struct = {}
        for item in value:
            struct[comp.Unnamed()] = from_python(item)
        return comp.Value(struct)
    
    # Fallback: try to create a Value directly
    try:
        return comp.Value(value)
    except Exception as e:
        raise TypeError(f"Cannot convert Python value of type {type(value).__name__} to Comp Value: {e}")


def to_python(value):
    """Convert a Comp Value to a Python value.
    
    Conversion rules:
    - Numbers → int or float (Decimal preserved if fractional)
    - Strings → str
    - Tags → bool for #true/#false, otherwise string tag name
    - Structs → dict or list depending on field names
    - Handles → raises ValueError (cannot convert)
    - Failures → raises CompError
    
    Args:
        value: Comp Value to convert
        
    Returns:
        Python value
        
    Raises:
        CompError: If value is a failure
        ValueError: If value cannot be converted (e.g., handles)
        
    Examples:
        >>> to_python(comp.Value(decimal.Decimal('42')))
        42
        >>> to_python(comp.Value({'x': comp.Value(1), 'y': comp.Value(2)}))
        {'x': 1, 'y': 2}
    """
    if not isinstance(value, comp.Value):
        raise TypeError(f"Expected comp.Value, got {type(value).__name__}")
    
    # Check for failure first
    if value.is_fail:
        raise CompError(value)
    
    # Unwrap to scalar
    value = value.as_scalar()
    
    # Handle different data types
    if value.is_number:
        # Convert Decimal to int if it's a whole number, otherwise float
        num = value.data
        if num % 1 == 0:
            return int(num)
        return float(num)
    
    if value.is_string:
        return value.data
    
    if value.is_tag:
        # Special handling for boolean tags
        tag_ref = value.data
        if tag_ref.full_name == "true":
            return True
        elif tag_ref.full_name == "false":
            return False
        # Other tags return their name as a string
        return tag_ref.full_name
    
    if value.is_struct:
        # Determine if this is a list (all unnamed fields) or dict (any named fields)
        has_named = False
        has_unnamed = False
        
        for key in value.data.keys():
            if isinstance(key, comp.Unnamed):
                has_unnamed = True
            else:
                has_named = True
        
        # If only unnamed fields, return as list
        if has_unnamed and not has_named:
            # Return items in iteration order (dict preserves insertion order in Python 3.7+)
            items = []
            for key, val in value.data.items():
                if isinstance(key, comp.Unnamed):
                    items.append(to_python(val))
            return items
        
        # Otherwise return as dict
        result = {}
        unnamed_counter = 0
        for key, val in value.data.items():
            if isinstance(key, comp.Unnamed):
                # Use counter for unnamed fields in mixed structs
                result[f"_{unnamed_counter}"] = to_python(val)
                unnamed_counter += 1
            elif isinstance(key, comp.Value) and key.is_string:
                result[key.data] = to_python(val)
            else:
                # Convert key to python too
                result[to_python(key)] = to_python(val)
        return result
    
    if value.is_handle:
        raise ValueError("Cannot convert Comp handle to Python value")
    
    # Fallback: return the raw data
    return value.data


def parse_value(text, module=None):
    """Parse a Comp expression and return a Value.
    
    This is useful for creating Comp values from literal syntax:
    
    Args:
        text: Comp expression string (e.g., "{x=1 y=2}", "[1, 2, 3]", "#success")
        module: Optional module for tag/shape lookups (default: builtin)
        
    Returns:
        comp.Value: The parsed and evaluated value
        
    Raises:
        comp.ParseError: If text has invalid syntax
        CompError: If evaluation fails
        
    Examples:
        >>> parse_value("{x=1 y=2}")
        Value({Value('x'): Value(Decimal('1')), Value('y'): Value(Decimal('2'))})
        >>> parse_value("#success")
        Value(TagRef(...))
    """
    # Parse the expression
    ast = comp.parse_expr(text)
    
    # Use builtin module if none provided
    if module is None:
        module = comp.builtin.get_builtin_module()
    
    # Evaluate using the engine
    engine = comp.Engine()
    result = engine.run(ast, module=module)
    
    # Check for failure
    if isinstance(result, comp.Value) and result.is_fail:
        raise CompError(result)
    
    return result


class FunctionProxy:
    """Proxy for calling a Comp function from Python.
    
    Provides a Pythonic interface with keyword arguments and automatic
    conversion between Python and Comp values.
    """
    
    def __init__(self, func_def, module, engine):
        """Initialize function proxy.
        
        Args:
            func_def: Comp FunctionDefinition
            module: Comp Module containing the function
            engine: Comp Engine for execution
        """
        self.func_def = func_def
        self.module = module
        self.engine = engine
        self._name = func_def.name
    
    def __call__(self, input=None, **kwargs):
        """Call the Comp function with Python values.
        
        Args:
            input: Input value (becomes $in), converted from Python
            **kwargs: Argument fields (become ^arg), converted from Python
            
        Returns:
            Python value (converted from Comp Value)
            
        Raises:
            CompError: If function returns a failure
        """
        # Convert input
        if input is None:
            input_value = comp.Value({})
        else:
            input_value = from_python(input)
        
        # Convert arguments to struct
        if kwargs:
            arg_value = from_python(kwargs)
        else:
            arg_value = comp.Value({})
        
        # Prepare the function call (handles overload selection and setup)
        # Note: func_defs is a list of FunctionDefinitions (overloads)
        func_defs = [self.func_def]
        ctx_scope = self.engine.ctx_scope
        
        compute = comp.prepare_function_call(func_defs, input_value, arg_value, ctx_scope)
        
        # If preparation failed, compute is a fail Value
        if isinstance(compute, comp.Value):
            return to_python(compute)  # Will raise CompError
        
        # Run the prepared function (compute is a Compute object with node and scopes)
        result = self.engine.run(compute.node, **compute.scopes)
        
        # Convert result to Python, raising CompError if it's a failure
        return to_python(result)
    
    def __repr__(self):
        return f"<CompFunction |{self._name}>"


class TagContainer:
    """Container for accessing module tags as attributes.
    
    Example:
        tags = TagContainer(module)
        success = tags.success  # Returns comp.Value(TagRef(...))
    """
    
    def __init__(self, module):
        """Initialize tag container.
        
        Args:
            module: Comp Module containing tags
        """
        self._module = module
        self._tags = {}
        
        # Build flat tag lookup
        def add_tags(tag_defs, prefix=""):
            for path, tag_def in tag_defs.items():
                full_name = f"{prefix}{path}" if prefix else path
                self._tags[path.replace(".", "_")] = tag_def
                # Also store with dots for nested access
                self._tags[path] = tag_def
        
        add_tags(module.tags)
    
    def __getattr__(self, name):
        """Get tag by name.
        
        Args:
            name: Tag name (dots replaced with underscores)
            
        Returns:
            comp.Value containing TagRef
            
        Raises:
            AttributeError: If tag not found
        """
        # Try with underscores first, then with dots
        tag_name = name
        if tag_name not in self._tags:
            tag_name = name.replace("_", ".")
        
        if tag_name not in self._tags:
            raise AttributeError(f"Tag '{name}' not found in module")
        
        tag_def = self._tags[tag_name]
        return comp.Value(comp.TagRef(tag_def))
    
    def __dir__(self):
        """List available tags."""
        return list(self._tags.keys())
    
    def __repr__(self):
        tag_names = ", ".join(sorted(self._tags.keys())[:5])
        if len(self._tags) > 5:
            tag_names += ", ..."
        return f"<CompTags: {tag_names}>"


class FunctionContainer:
    """Container for accessing module functions as attributes.
    
    Example:
        funcs = FunctionContainer(module, engine)
        result = funcs.connect(input="demo.db", mode="rw")
    """
    
    def __init__(self, module, engine):
        """Initialize function container.
        
        Args:
            module: Comp Module containing functions
            engine: Comp Engine for execution
        """
        self._module = module
        self._engine = engine
        self._functions = {}
        
        # Build function lookup
        # module.functions is a dict mapping names to lists of FunctionDefinitions
        for name, func_defs in module.functions.items():
            # For now, just use the first definition (TODO: handle overloading)
            func_def = func_defs[0] if isinstance(func_defs, list) else func_defs
            # Replace dots with underscores for attribute access
            attr_name = name.replace(".", "_").replace("-", "_")
            self._functions[attr_name] = func_def
            # Also store original name
            self._functions[name] = func_def
    
    def __getattr__(self, name):
        """Get function by name.
        
        Args:
            name: Function name (dots/hyphens replaced with underscores)
            
        Returns:
            FunctionProxy for calling the function
            
        Raises:
            AttributeError: If function not found
        """
        # Try direct lookup first
        if name not in self._functions:
            # Try with hyphens
            name_with_hyphens = name.replace("_", "-")
            if name_with_hyphens not in self._functions:
                raise AttributeError(f"Function '{name}' not found in module")
            name = name_with_hyphens
        
        func_def = self._functions[name]
        return FunctionProxy(func_def, self._module, self._engine)
    
    def __dir__(self):
        """List available functions."""
        return list(self._functions.keys())
    
    def __repr__(self):
        func_names = ", ".join(sorted(self._functions.keys())[:5])
        if len(self._functions) > 5:
            func_names += ", ..."
        return f"<CompFunctions: {func_names}>"


class ModuleProxy:
    """Pythonic proxy for a Comp module.
    
    Provides attribute-based access to module definitions:
    - .func - Container of callable functions
    - .tag - Container of tag values
    - .shape - Container of shape definitions
    
    Example:
        sqlite = comp.load_module("comp", "stdlib/sqlite.comp")
        db = sqlite.func.connect(input="demo.db")
        success_tag = sqlite.tag.success
    """
    
    def __init__(self, module, engine=None):
        """Initialize module proxy.
        
        Args:
            module: Comp Module to wrap
            engine: Optional Comp Engine (creates new one if not provided)
        """
        self._module = module
        self._engine = engine or comp.Engine()
        self._func = None
        self._tag = None
    
    @property
    def func(self):
        """Get function container for calling module functions."""
        if self._func is None:
            self._func = FunctionContainer(self._module, self._engine)
        return self._func
    
    @property
    def tag(self):
        """Get tag container for accessing module tags."""
        if self._tag is None:
            self._tag = TagContainer(self._module)
        return self._tag
    
    @property
    def shape(self):
        """Get shape definitions (returns raw dict for now)."""
        return self._module.shapes
    
    def __repr__(self):
        return f"<CompModule: {self._module.module_id}>"


def load_module(source, path):
    """Load a Comp module and return a Python proxy.
    
    Args:
        source: Import source type ("comp", "stdlib", etc.)
        path: Module path (filepath for "comp", module name for "stdlib")
        
    Returns:
        ModuleProxy: Pythonic interface to the module
        
    Raises:
        FileNotFoundError: If module file not found
        comp.ParseError: If module has syntax errors
        CompError: If module evaluation fails
        
    Examples:
        # Load from filesystem
        >>> utils = comp.load_module("comp", "lib/utils.comp")
        >>> result = utils.func.process(input=data)
        
        # Load from stdlib
        >>> sqlite = comp.load_module("stdlib", "sqlite")
        >>> db = sqlite.func.connect(input="demo.db")
    """
    # Handle different source types
    if source == "comp":
        # Load from filesystem
        filepath = pathlib.Path(path)
        if not filepath.exists():
            raise FileNotFoundError(f"Module file not found: {filepath}")
        
        code = filepath.read_text(encoding="utf-8")
        ast_module = comp.parse_module(code, filename=str(filepath))
        
    elif source == "stdlib":
        # Load from stdlib using corelib
        module = comp.corelib.get_stdlib_module(path)
        if module is None:
            raise ValueError(f"Stdlib module '{path}' not found")
        return ModuleProxy(module)
        
    else:
        raise ValueError(f"Unknown import source: {source}")
    
    # Create engine and evaluate module
    engine = comp.Engine()
    module_result = engine.run(ast_module)
    
    # Check for failure
    if isinstance(module_result, comp.Value) and module_result.is_fail:
        raise CompError(module_result)
    
    if not isinstance(module_result, comp.Module):
        raise ValueError(f"Expected Module, got {type(module_result).__name__}")
    
    module = module_result
    
    # Prepare the module
    try:
        module.prepare(ast_module, engine)
    except ValueError as e:
        raise ValueError(f"Module preparation error: {e}")
    
    return ModuleProxy(module, engine)
