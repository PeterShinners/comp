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
        self._add_tag("else", comp.tag_else)

        # Builtin shapes
        self._add_shape("num", comp.shape_num)
        self._add_shape("text", comp.shape_text)
        self._add_shape("struct", comp.shape_struct)
        self._add_shape("any", comp.shape_any)
        self._add_shape("func", comp.shape_block)
        self._add_shape("handle", comp.shape_handle)
        self._add_shape("shape", comp.shape_shape)

        # invoke-data shape — build here to avoid circular-import issues
        _invoke_data = comp.Shape("invoke-data", private=False)
        _invoke_data.fields = [
            comp.ShapeField(name="statement", shape=comp.shape_any,    default=None),
            comp.ShapeField(name="input",     shape=comp.shape_any,    default=None),
            comp.ShapeField(name="locals",    shape=comp.shape_struct, default=None),
            comp.ShapeField(name="context",   shape=comp.shape_struct, default=None),
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

        self._add_callable("item-at", _builtin_item_at, pure=True)
        self._add_callable("field-name", _builtin_field_name, pure=True)
        self._add_callable("field-value", _builtin_field_value, pure=True)
        self._add_callable("merge", _builtin_merge, pure=True)

        self._add_callable("wrap", _builtin_wrap)
        self._add_callable("fmt", _builtin_fmt, pure=True)
        self._add_callable("apply", _builtin_apply)
        self._add_callable("update", _builtin_update)
        self._add_callable("flat", _builtin_flat)
        self._add_callable("reduce", _builtin_reduce)
        self._add_callable("forever", _builtin_forever, pure=True)

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

    def finalize(self):
        self._finalized = True


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

    Usage: 1000 | fit :uint8   => 232
           -1   | fit :uint8   => 255
           200  | fit :int8    => -56

    The target shape must have both ge= and le= limits defined.
    The value is first truncated to remove any fractional part, then wrapped.
    """
    import decimal

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
    v = int(input_val.data.to_integral_value(rounding=decimal.ROUND_FLOOR))
    modulus = int(le_val - ge_val) + 1
    ge_int = int(ge_val)
    result = (v - ge_int) % modulus + ge_int
    return comp.Value(decimal.Decimal(result))


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
        raise comp.CodeError("item-at requires struct input")

    indexval = args_val.positional(0)
    if indexval.shape != comp.shape_num:   # needs to be an index integer, maybe allows negative lookup?
        raise comp.CodeError("item-at param must be an index")

    items = list(input_val.data.items())
    item = items[int(indexval.data)]

    if isinstance(item[0], comp.Unnamed):
        item = [item[1]]
    else:
        item = {item[0]: item[1]}
    return comp.Value.from_python(item)


def _builtin_field_name(input_val, args_val, frame):
    """Get the name for a simple single item struct.

    This is expected to work on a simple, single-item structure, as returned
    by `item-at`.
    
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
    by `item-at`.
    
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
        raise comp.CodeError("merge input must not be empty")

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


def _builtin_apply(input_val, args_val, frame):
    """Invoke an invoke-data struct: call $.statement with $.input piped in.

    This is the counterpart to the wrapper mechanism.  A wrapper receives
    invoke-data as its piped input ($) and may call `apply` to actually
    execute the wrapped statement.

    If $.statement is callable (Block, InternalCallable, DefinitionSet) it is
    invoked with $.input as the piped value and an empty args struct.
    Non-callable statements are returned as-is.
    """
    ctx = input_val.data
    if not isinstance(ctx, dict):
        raise comp.CodeError("apply requires invoke-data as piped input")

    _key = comp.Value.from_python
    statement = ctx.get(_key("statement"))
    input_v   = ctx.get(_key("input"))
    params    = ctx.get(_key("params")) or comp.Value.from_python({})

    if statement is None:
        return comp.Value.from_python(comp.tag_nil)

    # Unwrap StatementHandle (used to prevent TryInvoke inside wrapper functions)
    if isinstance(statement.data, comp.StatementHandle):
        statement = statement.data.val

    if isinstance(statement.data, (comp.Block, comp.InternalCallable, comp.DefinitionSet)):
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

    # Unwrap StatementHandle to get the raw Block
    if isinstance(statement.data, comp.StatementHandle):
        statement = statement.data.val

    if isinstance(statement.data, comp.Block):
        new_block = _clone_block_with_extra(
            statement.data,
            lambda last_reg: _instr_mod.MergeWithPiped(cop=None, result_reg=last_reg),
        )
        return comp.Value(new_block)

    # Struct value (e.g. @update {b=2}) — synthesise a trivial block that
    # returns the constant struct and then merges it over piped input.
    if isinstance(statement.data, dict):
        const_val = statement
        new_block = comp.Block("update.const", False)
        new_block.input_name = "$"
        new_block.closure_env = dict(frame.env)
        new_block.captured_dollar_vars = dict(frame._dollar_vars)
        new_block.param_names = []
        new_block.block_names = []
        new_block.dispatch_own_name = None
        new_block.dispatch_set_name = None
        new_block.body_instructions = [
            _instr_mod.Const(cop=None, value=const_val),
            _instr_mod.MergeWithPiped(cop=None, result_reg=0),
        ]
        return comp.Value(new_block)

    raise comp.CodeError("update requires a block or struct statement")


def _builtin_flat(input_val, args_val, frame):
    """@flat wrapper: clone body block with a FlattenFields tail instruction.

    Called at DEFINITION TIME with invoke-data.  Returns a new Block whose body
    is the original body plus a FlattenFields instruction.  At runtime that
    instruction concatenates the inner struct fields of the body's result into a
    single flat struct.

    Use case — multi-expression block whose results should be concatenated:

        !pure tree-values ~tree @flat {
            ($.left  | tree-values)
            {$.value}
            ($.right | tree-values)
        }
    """
    import comp._instructions as _instr_mod
    ctx = input_val.data
    if not isinstance(ctx, dict):
        raise comp.CodeError("flat requires invoke-data as piped input")

    _key = comp.Value.from_python
    statement = ctx.get(_key("statement"))

    if statement is None:
        raise comp.CodeError("flat: no statement in invoke-data")

    # Unwrap StatementHandle to get the raw Block
    if isinstance(statement.data, comp.StatementHandle):
        statement = statement.data.val

    if not isinstance(statement.data, comp.Block):
        raise comp.CodeError("flat requires a block statement")

    new_block = _clone_block_with_extra(
        statement.data,
        lambda last_reg: _instr_mod.FlattenFields(cop=None, result_reg=last_reg),
    )
    return comp.Value(new_block)


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


def _builtin_fmt(input_val, args_val, frame):
    """Format a value using a format string.

    Two modes:

    Wrapper mode — invoked via @fmt "template":
      input_val is an invoke-data struct.  The format string is taken from
      $.statement and substitutions use $.locals for $(name) tokens and
      $.input for %(ref) tokens.

    Pipeline mode — invoked via value | fmt :"template":
      input_val is the value to format.  The format string is the first
      positional argument.  %(ref) tokens draw from input_val; $(name)
      tokens have no locals source (produce empty string).

    Token syntax:
      %()     — the whole piped input
      %(#N)   — Nth unnamed positional field of the piped input, 1-based
      %(name) — named field 'name' of the piped input
      $(name) — local variable 'name' captured from the call site (wrapper mode)

    Examples:
      12 | fmt :"%()"                         → "12"
      {x=5} | fmt :"x is %(x)"               → "x is 5"
      @fmt "x is $(x)"  (with !let x 5 above) → "x is 5"
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
            parsed = _fmt.parse_format_text(stmt.data)
            # In wrapper mode, %(name) resolves from the current scope (locals).
            scope = locals_val if locals_val is not None else comp.Value.from_python({})
            result = _fmt.apply_format(parsed, scope, locals_val=locals_val)
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
    result = _fmt.apply_format(parsed, input_val)
    return comp.Value.from_python(result)


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

