"""Internal modules that provide built-in functionality."""

__all__ = [
    "InternalModule",
    "InternalCallable",
    "SystemModule",
    "get_internal_module",
]

import inspect
import sys
import comp
import comp._colorize


def _make_constant_cop(value):
    """Create a value.constant COP node for internal use."""
    return comp.create_cop("value.constant", [], value=value)


class InternalCallable:
    """A Python function callable from Comp code.

    Wraps a Python function so it can be invoked like a Comp block.
    The Python function receives (input_val, args_val, frame) and returns a Value.

    Args:
        name: (str) Name of the callable
        func: (callable) Python function to call

    Attributes:
        name: (str) Name for display
        func: (callable) The wrapped Python function
    """

    __slots__ = ("name", "func")

    def __init__(self, name, func):
        self.name = name
        self.func = func

    def __repr__(self):
        return f"<InternalCallable {self.name}>"


class InternalModule(comp.Module):
    """A module implemented in Python that provides internal functionality.

    Internal modules contain definitions for:
    - Tags (type constructors like `test`, `value.block`, etc.)
    - Shapes (type definitions)
    - Callables (functions implemented in Python)

    They can be imported using `!import` statements like regular modules.
    """

    def __init__(self, resource, doc):
        """Create an internal module.

        Args:
            resource: The import name for this module (e.g., "cop", "system")
        """
        # Create a minimal ModuleSource
        source = comp.ModuleSource(
            resource=resource,
            location=f"internal:{resource}",
            etag=resource,
            anchor="",
            content=""  # Internal modules have no source text
        )
        super().__init__(source)

        docs = [{"content": doc}]
        scan = {
            "docs": comp.Value.from_python(docs)
        }
        self._scan = comp.Value.from_python(scan)
        self._imports = {}
        self._definitions = {}
        self._finalized = False

    def add_tag(self, qualified_name, private=False):
        """Add a tag definition to this module.

        Args:
            qualified_name: Qualified name like "test" or "value.block"
            private: Whether this is a private tag

        Returns:
            Tag: The created Tag object
        """
        # Create the Tag object
        tag = comp.Tag(qualified_name, private)
        tag.module = self

        # Create a Definition for it
        definition = comp.Definition(
            qualified=qualified_name,
            module_id=self.token,
            original_cop=None,
            shape=comp.shape_struct  # Tags are struct-shaped values
        )
        definition.value = comp.Value.from_python(tag)
        # definition.resolved_cop = comp._fold.make_constant(None, definition.value)  # Already resolved
        # definition.original_cop = definition.resolved_cop

        self._definitions[qualified_name] = definition
        return tag

    def add_shape(self, qualified_name, shape_value):
        """Add a shape definition to this module.

        Args:
            qualified_name: Qualified name like "block" or "value"
            shape_value: The Shape object

        Returns:
            Definition: The created Definition object
        """
        definition = comp.Definition(
            qualified=qualified_name,
            module_id=self.token,
            original_cop=None,
            shape=comp.shape_shape
        )
        definition.value = comp.Value.from_python(shape_value)
        # definition.resolved_cop = comp._fold.make_constant(None, definition.value)  # Already resolved
        # definition.original_cop = definition.resolved_cop

        self._definitions[qualified_name] = definition
        return definition

    def add_callable(self, qualified_name, python_function):
        """Add a callable definition to this module.

        Args:
            qualified_name: Qualified name like "fold" or "incr"
            python_function: Python function to call. Receives (input_val, args_val)
                and returns a Value.

        Returns:
            Definition: The created Definition object
        """
        callable_obj = InternalCallable(qualified_name, python_function)
        value = comp.Value(callable_obj)
        
        definition = comp.Definition(
            qualified=qualified_name,
            module_id=self.token,
            original_cop=None,
            shape=comp.shape_block
        )
        definition.value = value
        # definition.resolved_cop = comp._fold.make_constant(None, definition.value)  # Already resolved
        # definition.original_cop = definition.resolved_cop

        self._definitions[qualified_name] = definition
        return definition

    def finalize(self):
        self._finalized = True

    def definitions(self):
        return self._definitions


class SystemModule(comp.Module):
    """System module singleton with several builtin attributes"""

    def __init__(self):
        # Create a minimal ModuleSource for system module
        source = type("obj", (object,), {"resource": "system", "content": ""})()
        super().__init__(source)
        self.token = "system#0000"

        self._imports = {}
        self._definitions = {}

        # Builtin tags
        self._add_tag("nil", comp.tag_nil)
        self._add_tag("bool", comp.tag_bool)
        self._add_tag("bool.true", comp.tag_true)
        self._add_tag("bool.false", comp.tag_false)
        self._add_tag("fail", comp.tag_fail)

        # Builtin shapes
        self._add_shape("num", comp.shape_num)
        self._add_shape("text", comp.shape_text)
        self._add_shape("struct", comp.shape_struct)
        self._add_shape("any", comp.shape_any)
        self._add_shape("func", comp.shape_block)

        # Builtin callables
        self._add_callable("incr", _builtin_incr)
        self._add_callable("answer", _builtin_answer)
        self._add_callable("wrap", _builtin_wrap)
        self._add_callable("morph", _builtin_morph)
        self._add_callable("mask", _builtin_mask)
        self._add_callable("abs", _builtin_abs)
        self._add_callable("output", _builtin_output)
        self._add_callable("fmt", _builtin_fmt)

        self.finalize()

    def _add_definition(self, name, value, shape):
        """Add a builtin definition with proper value and COP setup.

        Args:
            name: (str) Qualified name
            value: (Value) The definition's value
            shape: (Shape) The shape of the value
        """
        defn = comp.Definition(name, self.token, None, shape)
        defn.value = value
        defn.resolved_cop = _make_constant_cop(value)
        defn.original_cop = defn.resolved_cop
        self._definitions[name] = defn

    def _add_tag(self, name, tag):
        """Add a builtin tag definition."""
        self._add_definition(name, comp.Value.from_python(tag), comp.shape_struct)

    def _add_shape(self, name, shape):
        """Add a builtin shape definition."""
        self._add_definition(name, comp.Value.from_python(shape), comp.shape_shape)

    def _add_callable(self, name, func):
        """Add a builtin callable definition."""
        callable_obj = InternalCallable(name, func)
        self._add_definition(name, comp.Value(callable_obj), comp.shape_block)

    def finalize(self):
        self._finalized = True


# Builtin callable implementations

def _builtin_incr(input_val, args_val, frame):
    """Increment a number by 1."""
    val = input_val.as_scalar()
    n = val.to_python()
    return comp.Value.from_python(n + 1)


def _builtin_answer(input_val, args_val, frame):
    """Return the hardcoded constant 42. Useful for testing callables."""
    import decimal
    return comp.Value.from_python(decimal.Decimal(42))


def _builtin_wrap(input_val, args_val, frame):
    """Wrap a callable with outer wrappers.

    The compiler rewrites block wrappers to invoke this builtin function.
    """
    # This is a placeholder for now, it merely invokes the final
    # invokable instead of passing through each wrapper
    # input_val is ~(callable input args)
    ctx = input_val.data
    callable_val = ctx.get(comp.Value.from_python("callable"))
    inner_input = ctx.get(comp.Value.from_python("input"))
    inner_args = ctx.get(comp.Value.from_python("args"))

    # Invoke: inner_input | callable(inner_args)
    if callable_val is None:
        return comp.Value.from_python(None)

    # callable_val is already a Value from struct.get()
    return frame.invoke_block(callable_val, inner_args, inner_input)


def _builtin_morph(input_val, args_val, frame):
    """Morph a value to match a shape.

    Args:
        input_val: Unused (morph takes args only)
        args_val: Struct with (data shape) fields
        frame: The interpreter frame

    Returns:
        Struct with result= and score= on success, or result=nil and reason= on failure
    """
    # Extract data and shape from args
    data_val = args_val.positional(0)
    shape_val = args_val.positional(1)

    if data_val is None or shape_val is None:
        return comp.Value.from_python({
            "result": comp.tag_nil,
            "reason": "morph requires (data shape) arguments"
        })

    shape = shape_val.data
    if not isinstance(shape, (comp.Shape, comp.Tag, comp.ShapeUnion)):
        return comp.Value.from_python({
            "result": comp.tag_nil,
            "reason": f"Second argument must be a shape, got {type(shape)}"
        })

    result = comp.morph(data_val, shape, frame)

    if result.failure_reason:
        return comp.Value.from_python({
            "result": comp.tag_nil,
            "reason": result.failure_reason
        })

    score_struct = comp.Value.from_python({
        "named": result.score[0],
        "tag": result.score[1],
        "pos": result.score[2]
    })
    return comp.Value.from_python({
        "result": result.value,
        "score": score_struct
    })


def _builtin_mask(input_val, args_val, frame):
    """Mask a value to match a shape, dropping extra fields.

    Args:
        input_val: Unused (mask takes args only)
        args_val: Struct with (data shape) fields
        frame: The interpreter frame

    Returns:
        Struct with result= on success, or result=nil and reason= on failure
    """
    # Extract data and shape from args
    data_val = args_val.positional(0)
    shape_val = args_val.positional(1)

    if data_val is None or shape_val is None:
        return comp.Value.from_python({
            "result": comp.tag_nil,
            "reason": "mask requires (data shape) arguments"
        })

    shape = shape_val.data
    if not isinstance(shape, (comp.Shape, comp.Tag, comp.ShapeUnion)):
        return comp.Value.from_python({
            "result": comp.tag_nil,
            "reason": f"Second argument must be a shape, got {type(shape)}"
        })

    result_val, error = comp.mask(data_val, shape, frame)

    if error:
        return comp.Value.from_python({
            "result": comp.tag_nil,
            "reason": error
        })

    return comp.Value.from_python({
        "result": result_val
    })



# Global flag for colorization - will be replaced by context system later
_should_colorize = None

def _builtin_output(input_val, args_val, frame):
    """Output a value to stdout with optional colorization.
    
    Applies ANSI color codes from \\-X- markup when outputting to TTY.
    Respects NO_COLOR environment variable.
    """
    global _should_colorize
    
    # Initialize should_colorize on first use
    if _should_colorize is None:
        _should_colorize = comp._colorize.should_use_color(sys.stdout)
    
    # Format the value
    text = input_val.format()
    
    # Apply or strip color codes
    if _should_colorize:
        output_text = comp._colorize.apply_ansi(text)
    else:
        output_text = comp._colorize.strip_codes(text)
    
    print(output_text)
    return input_val


def _builtin_fmt(input_val, args_val, frame):
    """Format a value using a format string.

    Takes a format string as its first argument (via binding syntax).
    Substitutes %(ref) and $(name) tokens with values drawn from the piped input.

    Token syntax:
      %()     — the whole input value
      %(#N)   — Nth unnamed (positional) field, 1-based
      %(name) — named struct field 'name'

    Example:
      12 | fmt :"%()"               → "12"
      {name="pete" 3} | fmt :"%(#1) $(name)"  → "3 pete"
    """
    import comp._fmt as _fmt

    fmt_val = args_val.positional(0)
    if fmt_val is None:
        raise comp.CodeError("fmt requires a format string argument")
    if fmt_val.shape is not comp.shape_text:
        raise comp.CodeError(
            f"fmt expects a text argument, got {fmt_val.format()}"
        )

    parsed = _fmt.parse_format_text(fmt_val.data)
    result = _fmt.apply_format(parsed, input_val)
    return comp.Value.from_python(result)


def _builtin_abs(input_val, args_val, frame):
    """Return the absolute value of the first argument."""
    val = args_val.positional(0)
    if val is None:
        raise ValueError("abs requires one argument")
    scalar = val.as_scalar()
    if scalar.shape != comp.shape_num:
        raise TypeError(f"abs requires a number, got {scalar.format()}")
    import decimal
    n = scalar.data
    result = n.copy_abs() if isinstance(n, decimal.Decimal) else abs(n)
    return comp.Value(result)


# Registry of internal modules
_internal_registered = {}
_internal_modules = {}


def register_internal_module(resource):
    """Decorator for registering internal modules to a create function."""
    def fn(callback):
        _internal_registered[resource] = callback
        return callback
    return fn


def get_internal_module(resource):
    """Get an internal module by name.

    Args:
        resource: The import name (e.g., "cop", "system")

    Returns:
        InternalModule or None: The module if registered, None otherwise
    """
    module = _internal_modules.get(resource)
    if not module:
        if resource == "system":
            module = SystemModule()
        else:
            callback = _internal_registered.get(resource)
            if not callback:
                # Todo, this is begging for an exception?
                return None

            doc = inspect.getdoc(callback) or ""
            module = comp.InternalModule(resource, doc)
            callback(module)
            module.finalize()
        _internal_modules[resource] = module
    return module

