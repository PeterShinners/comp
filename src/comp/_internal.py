"""Internal modules that provide built-in functionality."""

__all__ = [
    "InternalModule",
    "InternalCallable",
    "SystemModule",
    "get_internal_module",
]

import copy
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

    If input_shape is provided, the piped/input value is morphed to that shape
    before the function is called.  A morph failure raises CompFail, causing the
    call site to fail-through (exactly like a regular Comp function whose input
    type does not match).  Pass None to skip pre-morph and let the function
    perform its own type checking.

    Args:
        name: (str) Name of the callable
        func: (callable) Python function to call
        pure: (bool) True if this callable has no side effects
        input_shape: (Shape | None) Shape to morph input against before
            calling func, or None to skip pre-morph

    Attributes:
        name: (str) Name for display
        func: (callable) The wrapped Python function
        pure: (bool) Whether the callable is considered pure
        input_shape: (Shape | None) Pre-morph shape, or None
    """

    __slots__ = ("name", "func", "pure", "input_shape")

    def __init__(self, name, func, pure=False, input_shape=None):
        self.name = name
        self.func = func
        self.pure = pure
        self.input_shape = input_shape

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
        self._interp_phase = 2  # Internal modules are always fully available

        docs = [{"content": doc}]
        scan = {
            "docs": comp.Value.from_python(docs)
        }
        self._scan = comp.Value.from_python(scan)
        self._imports = {}
        self._definitions = {}

    def add_tag(self, qualified_name, private=False):
        """Add a tag definition to this module.

        Automatically creates parent tag definitions for hierarchical
        names (e.g. "entry-type.dir" also creates "entry-type") matching
        the behavior of source-defined tags.

        Args:
            qualified_name: Qualified name like "test" or "value.block"
            private: Whether this is a private tag

        Returns:
            Tag: The created Tag object
        """
        # Create parent tag definitions for hierarchical names
        parts = qualified_name.split(".")
        for i in range(1, len(parts)):
            parent_name = ".".join(parts[:i])
            if parent_name not in self._definitions:
                parent_tag = comp.Tag(parent_name, private=False)
                parent_tag.module = self
                parent_def = comp.Definition(
                    qualified=parent_name,
                    module_id=self.token,
                    original_cop=None,
                    shape=comp.shape_struct
                )
                parent_def.value = comp.Value.from_python(parent_tag)
                self._definitions[parent_name] = parent_def

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

    def add_callable(self, qualified_name, python_function, pure=False, input_shape=None):
        """Add a callable definition to this module.

        Args:
            qualified_name: Qualified name like "fold" or "incr"
            python_function: Python function to call. Receives (input_val, args_val)
                and returns a Value.
            pure: (bool) True if the callable has no side effects
            input_shape: (Shape | None) Shape to morph input against before
                calling; None means the function does its own type checks

        Returns:
            Definition: The created Definition object
        """
        callable_obj = InternalCallable(qualified_name, python_function, pure=pure, input_shape=input_shape)
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

    def definitions(self):
        return self._definitions


class SystemModule(comp.Module):
    """System module singleton with several builtin attributes"""

    def __init__(self):
        # Create a minimal ModuleSource for system module
        source = type("obj", (object,), {"resource": "system", "content": ""})()
        super().__init__(source)
        self.token = "system#0000"
        self._interp_phase = 2  # System module is always fully available

        self._imports = {}
        self._definitions = {}

        # Builtin tags
        self._add_tag("nil", comp.tag_nil)
        self._add_tag("bool", comp.tag_bool)
        self._add_tag("bool.true", comp.tag_true)
        self._add_tag("bool.false", comp.tag_false)
        self._add_tag("fail", comp.tag_fail)
        self._add_tag("fail.value", comp.tag_fail_value)
        self._add_tag("fail.field", comp.tag_fail_field)
        self._add_tag("fail.math", comp.tag_fail_math)
        self._add_tag("fail.grab", comp.tag_fail_grab)
        self._add_tag("fail.module", comp.tag_fail_module)
        self._add_tag("fail.module.missing", comp.tag_fail_module_missing)
        self._add_tag("fail.module.syntax", comp.tag_fail_module_syntax)
        self._add_tag("fail.reference", comp.tag_fail_reference)
        self._add_tag("fail.reference.undefined", comp.tag_fail_reference_undefined)
        self._add_tag("fail.reference.ambiguous", comp.tag_fail_reference_ambiguous)
        self._add_tag("fail.invoke", comp.tag_fail_invoke)
        self._add_tag("flow-control", comp.tag_flow)
        self._add_tag("flow-control.skip", comp.tag_flow_skip)
        self._add_tag("flow-control.stop", comp.tag_flow_stop)
        self._add_tag("less", comp.tag_less)
        self._add_tag("equal", comp.tag_equal)
        self._add_tag("greater", comp.tag_greater)  
        self._add_tag("ord.less", comp.tag_less)
        self._add_tag("ord.equal", comp.tag_equal)
        self._add_tag("ord.greater", comp.tag_greater)  

        # Shelf handle tag
        self._add_shape("num", comp.shape_num)
        self._add_shape("text", comp.shape_text)
        self._add_shape("struct", comp.shape_struct)
        self._add_shape("any", comp.shape_any)
        self._add_shape("block", comp.shape_block)
        self._add_shape("invokable", comp.shape_invokable)
        self._add_shape("handle", comp.shape_handle)
        self._add_shape("shape", comp.shape_shape)

        # invoke-data shape — build here to avoid circular-import issues
        _invoke_data = comp.Shape("invoke-data", private=False)
        _invoke_data.fields = [
            comp.ShapeField(name="statement", shape=comp.shape_any, default=None),
            comp.ShapeField(name="input", shape=comp.shape_any, default=None),
            comp.ShapeField(name="locals", shape=comp.shape_struct, default=None),
            comp.ShapeField(name="context", shape=comp.shape_struct, default=None),
        ]
        self._add_shape("invoke-data", _invoke_data)
        self._add_shape("failure", comp.shape_failure)

        # Builtin callables
        self._add_callable("pass", _builtin_pass, pure=True)
        self._add_callable("tee", _builtin_tee, pure=True)
        self._add_callable("fit", _builtin_fit, pure=True, input_shape=comp.shape_num)
        self._add_callable("output", _builtin_output)

        self._add_callable("morph", _builtin_morph, pure=True)
        self._add_callable("mask", _builtin_mask, pure=True)

        self._add_callable("field-at", _builtin_item_at, pure=True)
        self._add_callable("field-name", _builtin_field_name, pure=True)
        self._add_callable("field-value", _builtin_field_value, pure=True)
        self._add_callable("merge", _builtin_merge, pure=True)
        self._add_callable("collect", _builtin_collect, pure=True, input_shape=comp.shape_struct)

        self._add_callable("wrap", _builtin_wrap)
        self._add_callable("fmt", _builtin_fmt, pure=True)
        self._add_callable("invoke", _builtin_invoke, pure=True)
        self._add_callable("namespace-lookup",_builtin_namespace_lookup, pure=True)
        self._add_callable("dispatch", _builtin_dispatch)
        self._add_callable("promote-root", _builtin_promote_root)
        self._add_callable("strip-unit", _builtin_strip_unit, pure=True)
        self._add_callable("to-text", _builtin_to_text, pure=True)
        self._add_callable("substitute", _builtin_substitute, pure=True)
        self._add_callable("update", _builtin_update)
        self._add_callable("flat", _builtin_flat)
        self._add_callable("reduce", _builtin_reduce)
        self._add_callable("forever", _builtin_forever, pure=True)
        self._add_callable("is-pure", _builtin_is_pure, pure=True)
        self._add_callable("walk-cop", _builtin_walk_cop, pure=True)
        self._add_callable("apply", _builtin_apply, pure=True)

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
        tag.module = self
        self._add_definition(name, comp.Value.from_python(tag), comp.shape_struct)

    def _add_shape(self, name, shape):
        """Add a builtin shape definition."""
        self._add_definition(name, comp.Value.from_python(shape), comp.shape_shape)

    def _add_callable(self, name, func, pure=False, input_shape=None):
        """Add a builtin callable definition.

        Args:
            name: (str) Qualified name of the callable
            func: (callable) Python function (input_val, args_val, frame) -> Value
            pure: (bool) True if the callable has no side effects
            input_shape: (Shape | None) Shape to morph input to before calling;
                None means the function handles its own type checking
        """
        callable_obj = InternalCallable(name, func, pure=pure, input_shape=input_shape)
        self._add_definition(name, comp.Value(callable_obj), comp.shape_block)


# Builtin callable implementations

def _builtin_pass(input_val, args_val, frame):
    """Return the piped input unchanged (identity function)."""
    return input_val


def _builtin_tee(input_val, args_val, frame):
    """Invoke a callable with the piped input, then return the original input.

    Usage: value | tee :some-callable
    The callable is called for its side effects; the original value flows through.
    """
    expr_val = args_val.positional(0)
    if expr_val is not None:
        frame.invoke_block(expr_val, comp.Value.from_python({}), piped=input_val)
    return input_val


def _builtin_fit(input_val, args_val, frame):
    """Fit a number into a bounded integer shape using wrapping (modular) arithmetic.

    Destructively remaps the input into the target shape's [ge, le] range.
    Use this when you know the value may be out of range and want C-style
    overflow behaviour rather than a morph failure.

    Usage: 1000 | fit uint8   => 232
           -1   | fit uint8   => 255
           200  | fit int8    => -56

    The target shape must have both ge= and le= limits defined.
    The value is first truncated to remove any fractional part, then wrapped.
    """

    shape_val = args_val.positional(0)
    if shape_val is None:
        raise comp.CodeError("fit requires a shape as its argument, e.g. fit :uint8")

    shape = shape_val.data
    if not isinstance(shape, comp.Shape):
        raise comp.CodeError(f"fit requires a shape argument, got {shape_val.format()}")

    # Scan the shape's first field for ge= and le= limit params
    ge_val = None
    le_val = None
    if shape.fields:
        for limit_name, param_val in shape.fields[0].limits:
            if limit_name == "ge" and param_val is not None:
                ge_val = param_val.data
            elif limit_name == "le" and param_val is not None:
                le_val = param_val.data

    if ge_val is None or le_val is None:
        raise comp.CodeError(
            f"fit: shape ~{shape.qualified} has no ge/le bounds — "
            "fit only works with bounded integer shapes like uint8"
        )

    # Truncate fractional part, then wrap into [ge, le]
    v = comp.num_floor_int(input_val.data)
    ge_int = comp.num_floor_int(ge_val)
    le_int = comp.num_floor_int(le_val)
    modulus = le_int - ge_int + 1
    result = (v - ge_int) % modulus + ge_int
    return comp.Value((result, 1, 0))


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
        return comp.Value.from_python({"result": comp.tag_nil})

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


def _builtin_item_at(input_val, args_val, frame):
    """Get a single item struct from the positional index of an existing struct.

    This single item struct will contain exactly one value, with either
    a named or unnamed field.
    
    """
    if input_val.shape != comp.shape_struct:
        raise comp.CodeError("field-at requires struct input")

    indexval = args_val.positional(0)
    if indexval.shape != comp.shape_num:   # needs to be an index integer, maybe allows negative lookup?
        raise comp.CodeError("field-at param must be an integer number")
    indexnum = indexval.to_python()
    index = int(indexnum)
    if index != indexnum:
        raise comp.CodeError("field-at param must be an integer")
    if index < 0:
        raise comp.CodeError(f"field-at index {index} cannot be negative")
    if index >= len(input_val.data):
        raise comp.CodeError(f"field-at index {index} outside struct length")

    items = list(input_val.data.items())
    item = items[index]

    if isinstance(item[0], comp.Unnamed):
        item = [item[1]]
    else:
        item = {item[0]: item[1]}
    return comp.Value.from_python(item)


def _builtin_field_name(input_val, args_val, frame):
    """Get the name for a simple single item struct.

    This is expected to work on a simple, single-item structure, as returned
    by `field-at`.
    
    This will fail if the field has no name or the struct doesn't have a
    single value.
        
    """
    if input_val.shape != comp.shape_struct:
        raise comp.CodeError("field-name requires struct input")
    if not input_val.data:
        raise comp.CodeError("field-name got an empty struct")
    if len(input_val.data) != 1:
        raise comp.CodeError("field-name struct must be a single item")

    key = list(input_val.data.keys())[0]
    if isinstance(key, comp.Unnamed):
        raise comp.CodeError("field-name field is unnamed")
    return key


def _builtin_field_value(input_val, args_val, frame):
    """Get the value for a simple single item struct.

    This is expected to work on a simple, single-item structure, as returned
    by `field-at`.
    
    This will fail if the struct doesn't have a single value.
        
    """
    if input_val.shape != comp.shape_struct:
        raise comp.CodeError("field-value requires struct input")
    if not input_val.data:
        raise comp.CodeError("field-value got an empty struct")
    if len(input_val.data) != 1:
        raise comp.CodeError("field-value struct must be a single item")

    value = list(input_val.data.values())[0]
    return value


def _builtin_merge(input_val, args_val, frame):
    """Merge multiple structs into a single resulting structure.

    Fields each struct are appended into a new structure, or if given
    a conflicting field name will insert the new value at the original position.
    
    This will fail if the struct is empty.
        
    """
    if input_val.shape != comp.shape_struct:
        raise comp.CodeError("merge requires struct input")
    if len(input_val.data) == 0:
        return comp.Value.from_python({})

    result = {}
    for container in input_val.data.values():
        if container.shape != comp.shape_struct:
            raise comp.CodeError("merge input values must be structs")
        for key, value in container.data.items():
            if isinstance(key, comp.Unnamed):
                key = comp.Unnamed()
            result[key] = value

    return comp.Value.from_python(result)


def _builtin_forever(input_val, args_val, frame):
    """Loop forever, calling a block repeatedly until it returns ~stop.

    The piped input is the initial accumulator.  The first positional
    argument is the block to invoke on each iteration.  The block
    receives the current accumulator as piped input ($).

    Flow-control tags returned by the block:
        ~flow-control.stop  — exit the loop, return current accumulator
        ~flow-control.skip  — skip this iteration (acc unchanged), continue

    Any other value becomes the new accumulator for the next iteration.

    Usage:  initial | forever :(... body ...)

    Example:
        0 | forever :(
            !on $ >= 10
            ~true stop
            ~false ($ + 1)
        )
        /// returns 10
    """
    args_data = args_val.data if isinstance(args_val.data, dict) else {}

    # Get the block from the first positional arg
    block_val = None
    for k, v in args_data.items():
        if isinstance(k, comp.Unnamed):
            block_val = v
            break

    if block_val is None:
        raise comp.CodeError("forever requires a callable as positional argument")

    _empty_args = comp.Value.from_python({})
    acc = input_val

    while True:
        value = frame.invoke_block(block_val, _empty_args, piped=acc)
        if isinstance(value.data, comp.Tag):
            if value.data is comp.tag_flow_stop:
                break
            if value.data is comp.tag_flow_skip:
                continue
        acc = value

    return acc

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


def _builtin_invoke(input_val, args_val, frame):
    """Invoke an invoke-data struct: call $.statement with $.input piped in.

    This is the counterpart to the wrapper mechanism.  A wrapper receives
    invoke-data as its piped input ($) and may call `invoke` to actually
    execute the wrapped statement.

    If $.statement is callable (Block, InternalCallable, Callable) it is
    invoked with $.input as the piped value and an empty args struct.
    Non-callable statements are returned as-is.
    """
    ctx = input_val.data
    if not isinstance(ctx, dict):
        raise comp.CodeError("invoke requires invoke-data as piped input")

    _key = comp.Value.from_python
    statement = ctx.get(_key("statement"))
    input_v   = ctx.get(_key("input"))
    params    = ctx.get(_key("params")) or comp.Value.from_python({})

    if statement is None:
        return comp.Value.from_python(comp.tag_nil)

    if isinstance(statement.data, (comp.Callable, comp.InternalCallable)):
        return frame.invoke_block(statement, params, piped=input_v)
    return statement


def _clone_block_with_extra(body_block, extra_instr):
    """Shallow-clone a Block and append one extra instruction to its body.

    Args:
        body_block: (Block) The original comp.Block to clone
        extra_instr: (Instruction) Instruction to append after the body

    Returns:
        (Block) New Block identical to the original but with an extended body
    """
    new_block = copy.copy(body_block)
    if body_block.body_instructions is not None:
        last_reg = len(body_block.body_instructions) - 1
        new_block.body_instructions = list(body_block.body_instructions) + [
            extra_instr(last_reg)
        ]
    new_block.wrapper = None
    return new_block


def _builtin_update(input_val, args_val, frame):
    """@update wrapper: clone body block with a MergeWithPiped tail instruction.

    Called at DEFINITION TIME with invoke-data.  Returns a new Block whose body
    is the original body plus a MergeWithPiped instruction.  At runtime that
    instruction overlays the body's partial result onto the original piped struct
    so callers receive the fully-merged record.

    Use case — write only the changed fields in a pure function:

        !pure move-right ~point @update(
            {x = ($.x + 10)}
        )
    """
    import comp._instructions as _instr_mod
    ctx = input_val.data
    if not isinstance(ctx, dict):
        raise comp.CodeError("update requires invoke-data as piped input")

    _key = comp.Value.from_python
    statement = ctx.get(_key("statement"))

    if statement is None:
        raise comp.CodeError("update: no statement in invoke-data")

    block = None
    if isinstance(statement.data, comp.Callable):
        block = statement.data.scalar()
    elif isinstance(statement.data, comp.Block):
        block = statement.data

    inner_input = ctx.get(_key("input"))

    if block is not None:
        new_block = _clone_block_with_extra(
            block,
            lambda last_reg: _instr_mod.MergeWithPiped(cop=None, result_reg=last_reg),
        )
        callable_obj = comp.Callable(new_block.qualified)
        callable_obj.add(new_block)
        return frame.invoke_block(comp.Value(callable_obj), args_val, piped=inner_input)

    # Struct value (e.g. @update {b=2}) — synthesise a trivial block that
    # returns the constant struct and then merges it over piped input.
    if isinstance(statement.data, dict):
        const_val = statement
        new_block = comp.Block("update.const")
        new_block.input_name = "$"
        new_block.closure_env = {}
        new_block.captured_dollar_vars = {}
        new_block.body_instructions = [
            _instr_mod.Const(cop=None, value=const_val),
            _instr_mod.MergeWithPiped(cop=None, result_reg=0),
        ]
        callable_obj = comp.Callable("update.const")
        callable_obj.add(new_block)
        return frame.invoke_block(comp.Value(callable_obj), args_val, piped=inner_input)

    raise comp.CodeError("update requires a block or struct statement")


def _builtin_flat(input_val, args_val, frame):
    """Flatten a struct-of-structs into a single flat struct.

    Two modes:

    Wrapper mode — invoked via @flat:
      input_val is an invoke-data struct.  Returns a new Block whose body
      is the original body plus a FlattenFields instruction.  At runtime
      that instruction concatenates the inner struct fields of the body's
      result into a single flat struct.

    Pipeline mode — invoked via value | flat:
      input_val is a struct whose values may themselves be structs.
      Returns a new struct with all inner fields concatenated in order.

    Examples:
      !pure tree-values ~tree @flat {
          ($.left  | tree-values)
          {$.value}
          ($.right | tree-values)
      }

      {{1 2} {3 4}} | flat   → {1 2 3 4}
    """
    import comp._instructions as _instr_mod

    # Wrapper mode: input is invoke-data (has a "statement" key)
    if isinstance(input_val.data, dict):
        _key = comp.Value.from_python
        statement = input_val.data.get(_key("statement"))
        inner_input = input_val.data.get(_key("input"))

        if statement is not None:
            block = None
            if isinstance(statement.data, comp.Callable):
                block = statement.data.scalar()
            elif isinstance(statement.data, comp.Block):
                block = statement.data

            if block is None:
                raise comp.CodeError("@flat requires a block statement")

            new_block = _clone_block_with_extra(
                block,
                lambda last_reg: _instr_mod.FlattenFields(cop=None, result_reg=last_reg),
            )
            callable_obj = comp.Callable(new_block.qualified)
            callable_obj.add(new_block)
            return frame.invoke_block(comp.Value(callable_obj), args_val, piped=inner_input)

    # Pipeline mode: flatten struct-of-structs at runtime
    if not isinstance(input_val.data, dict):
        return input_val

    combined = {}
    for _k, sub_val in input_val.data.items():
        if isinstance(sub_val.data, dict):
            for sub_k, sub_v in sub_val.data.items():
                if isinstance(sub_k, comp.Unnamed):
                    combined[comp.Unnamed()] = sub_v
                else:
                    combined[sub_k] = sub_v
        else:
            combined[comp.Unnamed()] = sub_val
    return comp.Value(combined)


def _builtin_reduce(input_val, args_val, frame):
    """Reduce a struct of values to a single accumulator.

    Iterates all fields of the piped input (positional and named) in order,
    calling fold(item) with the current accumulator piped in for each element.

    Args form: :initial=<acc>  <fold-callable> (positional)

    Example: {5 3 8} | reduce :initial=nil :tree-insert
      => nil | tree-insert({5}) => t1
         t1  | tree-insert({3}) => t2
         t2  | tree-insert({8}) => t3
    """
    args_data = args_val.data if isinstance(args_val.data, dict) else {}

    # Get initial accumulator from :initial named arg
    _key = comp.Value.from_python
    initial_key = _key("initial")
    acc = args_data.get(initial_key)
    if acc is None:
        acc = comp.Value(comp.tag_nil)

    # Get fold callable from the first positional arg
    fold_val = None
    for k, v in args_data.items():
        if isinstance(k, comp.Unnamed):
            fold_val = v
            break

    if fold_val is None:
        raise comp.CodeError("reduce requires a fold callable as positional argument")

    # Iterate over input struct fields in order
    items = list(input_val.data.values()) if isinstance(input_val.data, dict) else []

    _empty_args = comp.Value.from_python({})
    for item in items:
        # Pass item as the first positional arg, acc as piped input
        item_args = comp.Value({comp.Unnamed(): item})
        acc = frame.invoke_block(fold_val, item_args, piped=acc)

    return acc


def _builtin_make_raw_tag(input_val, args_val, frame):
    """Create a RawTag from a text identifier, an existing RawTag, or a Tag.

    Accepts:
      - ~text: validates the string is a qualified identifier, returns a new RawTag
      - ~raw-tag (RawTag value): passes through unchanged
      - ~tag (Tag value): creates a RawTag from the tag's qualified name

    Usage:
      "server.status.ok" | make-raw-tag
      some-raw-tag       | make-raw-tag
      some-tag           | make-raw-tag

    Args:
        input_val: (Value) Text, RawTag, or Tag value
        args_val: Unused
        frame: The interpreter frame

    Returns:
        (Value) A Value wrapping a RawTag
    """
    import re
    data = input_val.data
    if isinstance(data, comp.RawTag):
        return input_val
    if isinstance(data, comp.Tag):
        return comp.Value(comp.RawTag(data.qualified))
    if isinstance(data, str):
        if not re.match(r'^[^\W\d][\w-]*(\.[^\W\d][\w-]*)*\??$', data):
            raise comp.CodeError(f"make-raw-tag: {data!r} is not a valid qualified identifier")
        return comp.Value(comp.RawTag(data))
    raise comp.CodeError(
        f"make-raw-tag: expected text, raw-tag, or tag, got {input_val.format()}"
    )


def _builtin_fmt(input_val, args_val, frame):
    """Format a value using a format string.

    Two modes:

    Wrapper mode — invoked via @fmt "template":
      input_val is an invoke-data struct.  The format string is taken from
      $.statement.  %(name) tokens resolve from local variables captured
      at the call site, and %($) resolves to the piped input.

    Pipeline mode — invoked via value | fmt :"template":
      input_val is the value to format.  The format string is the first
      positional argument.  %(ref) tokens draw from input_val.

    Token syntax:
      %()     — the whole piped input
      %(#N)   — Nth unnamed positional field of the piped input, 1-based
      %(name) — named field 'name' of the input (or local variable in wrapper mode)

    Examples:
      12 | fmt :"%()"                         → "12"
      {x=5} | fmt :"x is %(x)"               → "x is 5"
      @fmt "x is %(x)"  (with !let x 5 above) → "x is 5"
    """
    import comp._fmt as _fmt

    # Wrapper mode: input is invoke-data (has a "statement" key)
    if isinstance(input_val.data, dict):
        stmt_key = comp.Value.from_python("statement")
        if stmt_key in input_val.data:
            stmt = input_val.data[stmt_key]
            if stmt is None or stmt.shape is not comp.shape_text:
                raise comp.CodeError("@fmt requires a text statement")
            locals_val = input_val.data.get(comp.Value.from_python("locals"))
            input_from_data = input_val.data.get(comp.Value.from_python("input"))
            parsed = _fmt.parse_format_text(stmt.data)
            # In wrapper mode, %(name) resolves from the current scope (locals).
            # Bake the piped-input value ($) into a derived scope so %($)
            # resolves to the value that was piped into the wrapped block.
            base = dict(locals_val.data) if locals_val is not None and isinstance(locals_val.data, dict) else {}
            if input_from_data is not None:
                base[comp.Value.from_python("$")] = input_from_data
            scope = comp.Value(base) if base else comp.Value.from_python({})
            result = _fmt.apply_format(parsed, scope)
            return comp.Value.from_python(result)

    # Pipeline mode: value | fmt :"template"
    fmt_val = args_val.positional(0)
    if fmt_val is None:
        raise comp.CodeError("fmt requires a format string argument")
    if fmt_val.shape is not comp.shape_text:
        raise comp.CodeError(
            f"fmt expects a text argument, got {fmt_val.format()}"
        )
    parsed = _fmt.parse_format_text(fmt_val.data)

    # If the template has a unit annotation, look up a custom substitute
    # in that tag's owning module and use it to render each token.
    substitute_fn = None
    unit_tag = fmt_val.unit
    if unit_tag is not None and unit_tag.module is not None:
        ns = unit_tag.module.namespace()
        sub_entry = ns.get("substitute")
        if sub_entry is not None:
            if isinstance(sub_entry, comp.Callable):
                sub_val = comp._instructions._load_name("substitute", frame)
            elif hasattr(sub_entry, "value") and sub_entry.value is not None:
                sub_val = sub_entry.value
            else:
                sub_val = None
            if sub_val is not None:
                def _make_sub_fn(sv, ut, fr):
                    def substitute_fn(val, spec_str):
                        # Annotate the spec string with the template unit so
                        # the substitute overload can dispatch on it (spec~text[unit])
                        spec_annotated = comp.Value.from_python(spec_str).with_unit(ut)
                        args = comp.Value({comp.Value.from_python("spec"): spec_annotated})
                        result = fr.invoke_block(sv, args, piped=val)
                        if result is None:
                            return ""
                        if result.shape is comp.shape_text:
                            return result.data
                        return result.format()
                    return substitute_fn
                substitute_fn = _make_sub_fn(sub_val, unit_tag, frame)

    result = _fmt.apply_format(parsed, input_val, substitute_fn=substitute_fn)
    return comp.Value.from_python(result)


def _builtin_get_unit_tag(input_val, args_val, frame):
    """Return the unit tag of a value, or nil if the value has no unit.

    Enables dynamic dispatch based on a value's unit annotation.  Compose
    with namespace-lookup to reach unit-owner module callables without an
    explicit import.

    Examples:
      "hello"[sql] | get-unit-tag   // → :sql
      "hello"      | get-unit-tag   // → :nil
      42[meter]    | get-unit-tag   // → :meter
    """
    unit = input_val.unit
    if unit is None:
        return comp.Value.from_python(None)  # nil
    return comp.Value.from_python(unit)


def _builtin_namespace_lookup(input_val, args_val, frame):
    """Look up a named definition in the origin module of a tag value.

    input:  a tag value
    arg:    the name to look up (text)
    returns: the callable/value for that name, or nil if not found

    Only works with tag values — non-tag input always returns nil.
    This is a purely dynamic operation with no build-time guarantees.

    Examples:
      :sql | namespace-lookup "substitute"   // → sql.substitute callable
      :sql | namespace-lookup "missing"      // → :nil
      42   | namespace-lookup "substitute"   // → :nil  (not a tag)
    """
    if not isinstance(input_val.data, comp.Tag):
        return comp.Value.from_python(None)  # nil — not a tag
    tag = input_val.data
    if tag.module is None:
        return comp.Value.from_python(None)  # nil — tag has no owning module
    name_val = args_val.positional(0)
    if name_val is None or name_val.shape is not comp.shape_text:
        raise comp.CodeError("namespace-lookup requires a text name argument")
    name = name_val.data
    # Use the module's namespace — handles short-name collation and overload sets
    ns = tag.module.namespace()
    entry = ns.get(name)
    if entry is None:
        return comp.Value.from_python(None)
    if isinstance(entry, comp.Callable):
        # Build the Callable and return
        try:
            return comp._instructions._load_name(name, frame)
        except NameError:
            return comp.Value.from_python(None)
    # Single Definition
    if hasattr(entry, "value") and entry.value is not None:
        return entry.value
    return comp.Value.from_python(None)


def _resolve_from_module(name, module, frame):
    """Resolve a name to a Value from a specific module's namespace.

    Handles overload sets (Callable with pending entries), single definitions,
    and InternalCallable entries. Returns None if not found or not resolvable.
    """
    ns = module.namespace()
    entry = ns.get(name)
    if entry is None:
        return None
    if isinstance(entry, comp.Callable):
        callable = comp.Callable(name)
        for defn in entry.entries:
            comp._instructions._ensure_definition_value(defn, frame)
            if defn.value is None:
                continue
            data = defn.value.data
            if isinstance(data, comp.Callable):
                for b in data.entries:
                    callable.add(b)
                if data.shape is not None and callable.shape is None:
                    callable.shape = data.shape
                if data.pipeline is not None and callable.pipeline is None:
                    callable.pipeline = data.pipeline
            elif isinstance(data, (comp.Shape, comp.Tag, comp.ShapeUnion)):
                callable.shape = data
            elif isinstance(data, comp.InternalCallable):
                callable.add(data)
            else:
                if len(entry.entries) == 1:
                    return defn.value
        if not callable.entries and callable.shape is not None and callable.pipeline is None:
            return comp.Value.from_python(callable.shape)
        if callable.entries or callable.pipeline:
            return comp.Value(callable)
        for defn in entry.entries:
            if defn.value is not None:
                return defn.value
        return None
    elif hasattr(entry, "value"):
        comp._instructions._ensure_definition_value(entry, frame)
        if entry.value is not None:
            return entry.value
    return None


def _builtin_dispatch(input_val, args_val, frame):
    """Dispatch a call to a function in the module that owns a tag.

    Looks up a named function in the tag's defining module and invokes it
    with the original piped input. Additional args beyond the tag and name
    are forwarded to the dispatched function.

    Args (positional):
        tag: (tag) Identifies which module to dispatch to
        name: (text) Function name to call in that module

    Any additional positional or named args are forwarded.

    Examples:
      entry | dispatch $.vfs "entry-read"
      entry | dispatch $.vfs "entry-write" content
    """
    args_data = args_val.data if isinstance(args_val.data, dict) else {}

    # Extract tag (first positional) and name (second positional)
    tag_val = None
    name_val = None
    pos_index = 0
    forwarded = {}
    for key, val in args_data.items():
        if isinstance(key, comp.Unnamed):
            if pos_index == 0:
                tag_val = val
            elif pos_index == 1:
                name_val = val
            else:
                forwarded[comp.Unnamed()] = val
            pos_index += 1
        else:
            forwarded[key] = val

    if tag_val is None:
        raise comp.CodeError("dispatch: requires a tag as first argument")
    if not isinstance(tag_val.data, comp.Tag):
        raise comp.CodeError(
            f"dispatch: first argument must be a tag, got {tag_val.format()}"
        )
    tag = tag_val.data
    if tag.module is None:
        raise comp.CodeError(
            f"dispatch: tag {tag.qualified} has no owning module"
        )

    if name_val is None or name_val.shape is not comp.shape_text:
        raise comp.CodeError("dispatch: requires a text function name as second argument")
    name = name_val.data

    # Block private functions from dispatch — check namespace definitions
    ns = tag.module.namespace()
    ns_entry = ns.get(name)
    if ns_entry is not None and isinstance(ns_entry, comp.Callable):
        if any(getattr(d, "private", False) for d in ns_entry.entries):
            raise comp.CodeError(
                f"dispatch: cannot dispatch to private function '{name}'"
            )
    elif ns_entry is not None and hasattr(ns_entry, "private") and ns_entry.private:
        raise comp.CodeError(
            f"dispatch: cannot dispatch to private function '{name}'"
        )

    # Resolve callable from the tag's module
    callable_val = _resolve_from_module(name, tag.module, frame)
    if callable_val is None:
        raise comp.CodeError(
            f"dispatch: '{name}' not found in module for {tag.qualified}"
        )

    # Invoke with original piped input and forwarded args
    forwarded_args = comp.Value(forwarded) if forwarded else comp.Value.from_python({})
    return frame.invoke_block(callable_val, forwarded_args, piped=input_val)


def _builtin_promote_root(input_val, args_val, frame):
    """Make a struct field reference the struct itself (self-referential).

    Used to create root entries where $.root points back to $.
    The field name defaults to "root".

    Example:
      {name="C:/" root=nil vfs=disk} | promote-root
      // $.root is now the same object as $
    """
    if not isinstance(input_val.data, dict):
        raise comp.CodeError("promote-root: input must be a struct")
    field = "root"
    try:
        name_val = args_val.positional(0) if args_val else None
    except (IndexError, TypeError):
        name_val = None
    if name_val is not None and isinstance(name_val.data, str):
        field = name_val.data
    key = comp.Value.from_python(field)
    input_val.data[key] = input_val
    return input_val


def _builtin_strip_unit(input_val, args_val, frame):
    """Return the value with its unit annotation stripped.

    Pipeline form of the expr[] postfix syntax.  The returned value is
    identical in data and shape but carries no unit tag.

    Example:
      "hello"[sql] | strip-unit   // → "hello"  (plain text)
    """
    return input_val.with_unit(None)


def _builtin_to_text(input_val, args_val, frame):
    """Return the Comp text representation of any value.

    Equivalent to Value.format() — produces a Comp literal expression string.
    Useful as the generic fallback for fmt substitution.

    Examples:
      42        | to-text   // → "42"
      true      | to-text   // → "true"
      nil       | to-text   // → "nil"
      {x=1 y=2} | to-text   // → "{x=1 y=2}"
    """
    return comp.Value.from_python(input_val.format())


def _builtin_substitute(input_val, args_val, frame):
    """Format a value for text substitution, dispatching on shape.

    This is the default substitution function used by the fmt system when
    rendering %(name) tokens.  Dispatches on the input's shape:

      ~num  — Python format() with spec (e.g. ".2f", "08d", ",")
      ~text — Python format() with spec (e.g. ">10", "^20")
      ~any  — Value.format() (Comp literal representation)

    The optional spec argument is the format spec string (default "").
    Unit annotation on the value is stripped before dispatch; the spec
    itself carries the intended unit context when unit-aware substitution
    is needed.

    Examples:
      3.14159 | substitute :spec=".4f"   // → "3.1416"
      "hello" | substitute :spec=">10"   // → "     hello"
      true    | substitute               // → "true"
      {x=1}   | substitute               // → "{x=1}"
    """
    # Extract optional spec argument (named :spec= or first positional)
    spec = ""
    if isinstance(args_val.data, dict):
        spec_key = comp.Value.from_python("spec")
        spec_val = args_val.data.get(spec_key)
        if spec_val is not None and isinstance(spec_val.data, str):
            spec = spec_val.data

    # Strip unit before dispatch — unit context is in spec when needed
    raw = input_val.with_unit(None)

    if raw.shape is comp.shape_num:
        # Use Python's format() for numeric format specs
        py_num = raw.data
        if comp.num_is_integer(py_num) and not spec:
            return comp.Value.from_python(str(py_num.n))
        try:
            return comp.Value.from_python(format(comp.num_to_float(py_num), spec))
        except (ValueError, TypeError) as e:
            raise comp.CodeError(f"substitute: bad format spec {spec!r} for number: {e}")

    if raw.shape is comp.shape_text:
        try:
            return comp.Value.from_python(format(raw.data, spec))
        except (ValueError, TypeError) as e:
            raise comp.CodeError(f"substitute: bad format spec {spec!r} for text: {e}")

    # Fallback: Comp literal representation
    return comp.Value.from_python(raw.format())


# Registry of internal modules
_internal_registered = {}
_internal_modules = {}


def register_internal_module(resource):
    """Decorator for registering internal modules to a create function."""
    def fn(callback):
        _internal_registered[resource] = callback
        return callback
    return fn


def _builtin_is_pure(input_val, args_val, frame):
    """Check whether a named callable is pure in a given namespace.

    Input (piped): namespace struct (module namespace dict wrapped via
    Value.from_python — keys are Value(str), values are Value(Callable))
    Arg (positional): qualified name (text)

    Returns :true if the callable is pure (declared !pure, or a pure
    builtin), :false otherwise.  Returns :false for names not found
    in the namespace, and :true for tags and shapes (they cannot have
    side effects).

    Usage: namespace | is-pure "my-func"   => :true / :false
    """
    name_val = args_val.positional(0)
    if name_val is None or not isinstance(name_val.data, str):
        return comp.Value.from_python(False)
    name = name_val.data

    ns = input_val.data
    if not isinstance(ns, dict):
        return comp.Value.from_python(False)

    # Namespace was converted via from_python so keys are Value(str)
    name_key = comp.Value.from_python(name)
    entry_val = ns.get(name_key)
    if entry_val is None:
        return comp.Value.from_python(False)

    # Unwrap: from_python wraps Callable in Value
    entry = entry_val.data if isinstance(entry_val, comp.Value) else entry_val
    if not isinstance(entry, comp.Callable):
        return comp.Value.from_python(False)

    for defn in entry.entries:
        if not isinstance(defn, comp.Definition):
            continue
        if defn.shape != comp.shape_block:
            return comp.Value.from_python(True)
        return comp.Value.from_python(comp._pure._is_pure_definition(defn))

    return comp.Value.from_python(False)


def _builtin_walk_cop(input_val, args_val, frame):
    """Walk a native COP value and return native match contexts.

    This keeps the Comp-facing contract as native COP nodes while delegating
    the actual path discovery to comp.runtime.pure.walk_cop.
    """
    from comp._py import _comp_to_python
    from comp.runtime import pure as _runtime_pure

    if input_val is None or not isinstance(input_val.data, dict):
        raise comp.CodeError("walk-cop requires a COP struct as piped input")

    def _named_arg(name, default=None):
        if not isinstance(args_val.data, dict):
            return default
        return args_val.data.get(comp.Value.from_python(name), default)

    def _follow_path(root, path):
        current = root
        for index in path:
            kids = current.data.get(comp.Value.from_python("kids"))
            if kids is None or not isinstance(kids.data, dict):
                raise comp.CodeError("walk-cop: invalid COP path traversal")
            current = kids.positional(index)
        return current

    def _as_text(value):
        if value is None:
            return None
        converted = _comp_to_python(value)
        if converted is None:
            return None
        return converted if isinstance(converted, str) else str(converted)

    def _as_fields(value):
        if value is None:
            return {}
        converted = _comp_to_python(value)
        return converted if isinstance(converted, dict) else {}

    def _as_bool(value, default=True):
        if value is None:
            return default
        converted = _comp_to_python(value)
        if converted is None:
            return default
        return bool(converted)

    filter_val = _named_arg("filter")
    fields_val = _named_arg("fields", comp.Value.from_python({}))
    order_val = _named_arg("order")
    recurse_val = _named_arg("recurse")
    stop_val = _named_arg("stop-on-match", comp.Value.from_python(True))

    matches = _runtime_pure.walk_cop(
        _comp_to_python(input_val),
        filter=_as_text(filter_val),
        fields=_as_fields(fields_val),
        order=_as_text(order_val) or "all",
        recurse=_as_text(recurse_val) or "deep",
        stop_on_match=_as_bool(stop_val),
    )

    native_matches = []
    for match in matches:
        path = match.get("path") or []
        parent_path = match.get("parent")
        native_matches.append({
            "node": _follow_path(input_val, path),
            "parent": comp.Value.from_python(None) if parent_path is None else _follow_path(input_val, parent_path),
            "depth": match.get("depth", 0),
            "position": match.get("position", 0),
            "order": match.get("order", "all"),
        })

    return comp.Value.from_python(native_matches)


def _builtin_apply(input_val, args_val, frame):
    """Apply a struct of arguments to a callable.

    Spreads the piped input struct as arguments to the callable given as
    the first positional argument.  An optional second positional argument
    is used as the piped input ($) for the callable.

    Usage:  params | apply myfunc           — call myfunc with params spread as args
            params | apply myfunc myinput   — call myfunc with params as args, myinput as $
    """
    args_data = args_val.data if isinstance(args_val.data, dict) else {}

    # Extract positional args: callable (required), input (optional)
    positional = []
    for k, v in args_data.items():
        if isinstance(k, comp.Unnamed):
            positional.append(v)

    if not positional:
        raise comp.CodeError("apply requires a callable as the first argument")

    callable_val = positional[0]
    piped = positional[1] if len(positional) > 1 else None

    # The piped input to apply is the struct of args to spread
    spread_args = input_val
    if not isinstance(spread_args.data, dict):
        # Wrap non-struct values as a single positional arg
        spread_args = comp.Value({comp.Unnamed(): spread_args})

    return frame.invoke_block(callable_val, spread_args, piped=piped)


def _builtin_collect(input_val, args_val, frame):
    """Flatten a nested ladder struct into a single flat struct.

    Recursively descends into struct-valued fields depth-first.
    Non-struct leaf values are collected in order.  For conflicting
    named keys, outer (later-added) values override inner ones.

    Usage:  {{{1} 2} 3} | collect   =>  {1 2 3}
            {{{a=1} a=2} a=3} | collect  =>  {a=3}
    """
    result = {}

    def _walk(struct_val):
        for key, value in struct_val.data.items():
            if value.shape is comp.shape_struct:
                _walk(value)
            else:
                if isinstance(key, comp.Unnamed):
                    key = comp.Unnamed()
                result[key] = value

    _walk(input_val)
    return comp.Value(result)


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
        _internal_modules[resource] = module
    return module


@register_internal_module("tag")
def _create_tag_module(module):
    """Tag inspection and hierarchy utilities.

    Provides functions for working with tags: creating raw tags,
    inspecting unit annotations, walking tag hierarchies, and
    querying tag ownership.
    """
    module.add_callable("make-raw-tag", _builtin_make_raw_tag, pure=True)
    module.add_callable("get-unit-tag", _builtin_get_unit_tag, pure=True)
    module.add_callable("owner", _builtin_tag_owner, pure=True)
    module.add_callable("parent", _builtin_tag_parent, pure=True)
    module.add_callable("children", _builtin_tag_children, pure=True)
    module.add_callable("ancestors", _builtin_tag_ancestors, pure=True)
    module.add_callable("is-ancestor", _builtin_tag_is_ancestor, pure=True)


def _builtin_tag_owner(input_val, args_val, frame):
    """Return the module resource name that defined a tag, or nil.

    Usage:
      some-tag | tag.owner   // → "aa.comp"
    """
    data = input_val.data
    if isinstance(data, comp.Tag) and data.module is not None:
        resource = getattr(data.module.source, "resource", None)
        if resource is not None:
            return comp.Value.from_python(resource)
    return comp.Value.from_python(None)


def _builtin_tag_parent(input_val, args_val, frame):
    """Return the parent tag in the current module's hierarchy, or nil.

    Usage:
      child-tag | tag.parent   // → parent-tag or nil
    """
    data = input_val.data
    if not isinstance(data, comp.Tag):
        return comp.Value.from_python(None)

    hierarchy = _get_hierarchy_for_tag(data)
    if hierarchy is None:
        return comp.Value.from_python(None)

    tag_slot = hierarchy._slot.get(data)
    if tag_slot is None:
        return comp.Value.from_python(None)

    parent_slot = hierarchy._parent_slot.get(tag_slot)
    if parent_slot is None:
        return comp.Value.from_python(None)

    # Find any tag in the parent slot
    for tag, slot in hierarchy._slot.items():
        if slot == parent_slot:
            return comp.Value.from_python(tag)
    return comp.Value.from_python(None)


def _builtin_tag_children(input_val, args_val, frame):
    """Return direct child tags in the current module's hierarchy.

    Usage:
      parent-tag | tag.children   // → {child1 child2 ...}
    """
    data = input_val.data
    if not isinstance(data, comp.Tag):
        return comp.Value.from_python({})

    hierarchy = _get_hierarchy_for_tag(data)
    if hierarchy is None:
        return comp.Value.from_python({})

    my_slot = hierarchy._slot.get(data)
    if my_slot is None:
        return comp.Value.from_python({})

    # Find slots whose parent is my_slot
    child_slots = {s for s, p in hierarchy._parent_slot.items() if p == my_slot}
    if not child_slots:
        return comp.Value.from_python({})

    # Collect one representative tag per child slot
    children = []
    seen_slots = set()
    for tag, slot in hierarchy._slot.items():
        if slot in child_slots and slot not in seen_slots:
            children.append(comp.Value.from_python(tag))
            seen_slots.add(slot)

    result = {}
    for child in children:
        result[comp.Unnamed()] = child
    return comp.Value(result)


def _builtin_tag_ancestors(input_val, args_val, frame):
    """Return all ancestor tags from child to root, or empty struct.

    Usage:
      deep-tag | tag.ancestors   // → {parent grandparent ...}
    """
    data = input_val.data
    if not isinstance(data, comp.Tag):
        return comp.Value.from_python({})

    hierarchy = _get_hierarchy_for_tag(data)
    if hierarchy is None:
        return comp.Value.from_python({})

    tag_slot = hierarchy._slot.get(data)
    if tag_slot is None:
        return comp.Value.from_python({})

    ancestors = []
    current = tag_slot
    while True:
        parent_slot = hierarchy._parent_slot.get(current)
        if parent_slot is None:
            break
        current = parent_slot
        for tag, slot in hierarchy._slot.items():
            if slot == current:
                ancestors.append(comp.Value.from_python(tag))
                break

    result = {}
    for anc in ancestors:
        result[comp.Unnamed()] = anc
    return comp.Value(result)


def _builtin_tag_is_ancestor(input_val, args_val, frame):
    """Check if the argument tag is an ancestor of the input tag.

    Usage:
      child-tag | tag.is-ancestor parent-tag   // → true or false
    """
    data = input_val.data
    if not isinstance(data, comp.Tag):
        return comp.Value.from_python(False)

    ancestor_val = args_val.positional(0)
    if ancestor_val is None or not isinstance(ancestor_val.data, comp.Tag):
        return comp.Value.from_python(False)

    hierarchy = _get_hierarchy_for_tag(data)
    if hierarchy is None:
        return comp.Value.from_python(False)

    depth = hierarchy.ancestor_depth(data, ancestor_val.data)
    return comp.Value.from_python(depth is not None)


def _get_hierarchy_for_tag(tag):
    """Get the tag hierarchy from the tag's own defining module.

    Uses the tag's module (where it was defined) rather than the
    calling module, so transitive imports are handled correctly.
    """
    module = getattr(tag, "module", None)
    if module is None:
        return None
    return getattr(module, "tag_hierarchy", None)

