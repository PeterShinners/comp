"""Instruction classes for the Comp bytecode interpreter.

Each instruction:
- Has a reference to its source COP node for error reporting
- Contains pre-resolved references (no runtime lookups)
- Holds literal Values when known at build time
- Uses a register-based model (named slots, not stack)

The instruction stream is linear and easy to march through.
Performance optimizations can happen later - clarity first.
"""

import comp



def _deep_set_value(base, path, new_value):
    """Immutably set new_value at path inside a struct, returning the new root.

    Navigates the path creating empty structs for any missing or non-struct
    intermediate values.  Each level is a new comp.Value so the originals
    remain unmodified.

    Args:
        base:      (comp.Value) The struct to update at this level
        path:      (list[str|int]) Remaining path segments
        new_value: (comp.Value) The value to set at the leaf

    Returns:
        (comp.Value) New root struct with the value updated at path
    """
    if not path:
        return new_value

    segment = path[0]
    remaining = path[1:]

    base_data = base.data if isinstance(base.data, dict) else {}

    if isinstance(segment, int):
        # Positional index access
        items = list(base_data.items())
        if segment < 0 or segment >= len(items):
            raise comp.CodeError(
                f"Index {segment} out of range for deep assignment "
                f"(struct has {len(items)} fields)"
            )
        key, current = items[segment]
    else:
        # Named field access
        key = comp.Value.from_python(segment)
        current = base_data.get(key, comp.Value.from_python({}))

    if remaining and not isinstance(current.data, dict):
        current = comp.Value.from_python({})

    new_field_value = _deep_set_value(current, remaining, new_value)
    new_data = dict(base_data)
    new_data[key] = new_field_value
    return comp.Value(new_data)


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------

class Instruction:
    """Base class for all instructions."""

    can_catch_failure = False  # Override True in Fallback/PipeFallback

    def __init__(self, cop):
        self.cop = cop  # Source COP node for error reporting

    def execute(self, frame):
        """Execute this instruction in the given frame."""
        raise NotImplementedError()


# ---------------------------------------------------------------------------
# Load / Store
# ---------------------------------------------------------------------------

class Const(Instruction):
    """Load a constant value."""

    def __init__(self, cop, value):
        super().__init__(cop)
        self.value = value

    def execute(self, frame):
        return frame.set_result(self.value)

    def format(self, idx):
        return f"%{idx}  Const {self.value.format()}"


class LoadVar(Instruction):
    """Load a variable from the environment or namespace.

    This is a pure load — no auto-invocation. The codegen emits an explicit
    TryInvoke instruction after LoadVar when the value is in a value position.
    For callable positions (Invoke/PipeInvoke), no TryInvoke is emitted.
    """

    def __init__(self, cop, name):
        super().__init__(cop)
        self.name = name

    def execute(self, frame):
        value = _load_name(self.name, frame)
        return frame.set_result(value)

    def format(self, idx):
        return f"%{idx}  LoadVar '{self.name}'"


class LoadLocal(Instruction):
    """Load a local variable from the frame environment.

    Used for let-bound locals and function parameters that are only known at
    runtime. Unlike LoadVar, this never consults the module namespace — the
    variable must already be present in frame.env (set by a StoreLocal) or
    frame._dollar_vars (for pipeline inputs $, $$, $$$).
    """

    def __init__(self, cop, name):
        super().__init__(cop)
        self.name = name

    def execute(self, frame):
        value = frame._dollar_vars.get(self.name) or frame.env.get(self.name)
        if value is None:
            raise comp.CodeError(f"Undefined local variable: '{self.name}'")
        return frame.set_result(value)

    def format(self, idx):
        return f"%{idx}  LoadLocal '{self.name}'"


class LoadOverload(Instruction):
    """Load multiple overloaded definitions as a Callable."""

    def __init__(self, cop, names):
        super().__init__(cop)
        self.names = names  # list of qualified names

    def execute(self, frame):
        callable = comp.Callable(self.names[0] if self.names else "?")
        for name in self.names:
            defn = frame.lookup(name)
            if defn is not None:
                if isinstance(defn, comp.DefinitionSet):
                    for d in defn.definitions:
                        _ensure_definition_value(d, frame)
                        if d.value is not None:
                            data = d.value.data
                            if isinstance(data, comp.Callable):
                                for b in data.blocks:
                                    callable.add_block(b)
                                if data.shape is not None and callable.shape is None:
                                    callable.shape = data.shape
                            elif isinstance(data, comp.InternalCallable):
                                callable.add_block(data)
                            elif isinstance(data, (comp.Shape, comp.Tag, comp.ShapeUnion)):
                                callable.shape = data
                elif isinstance(defn, comp.Definition):
                    _ensure_definition_value(defn, frame)
                    if defn.value is not None:
                        data = defn.value.data
                        if isinstance(data, comp.Callable):
                            for b in data.blocks:
                                callable.add_block(b)
                            if data.shape is not None and callable.shape is None:
                                callable.shape = data.shape
                        elif isinstance(data, comp.InternalCallable):
                            callable.add_block(data)
                        elif isinstance(data, (comp.Shape, comp.Tag, comp.ShapeUnion)):
                            callable.shape = data

        if not callable.blocks and callable.shape is None:
            raise NameError(f"No overloads found for '{self.names}'")

        result = comp.Value(callable)
        return frame.set_result(result)

    def format(self, idx):
        names_str = ", ".join(self.names)
        return f"%{idx}  LoadOverload [{names_str}]"


class StoreLocal(Instruction):
    """Store a value into the local frame environment.

    Used by op.my and struct.letassign to bind a name for subsequent
    LoadLocal references within the same function body.
    """

    def __init__(self, cop, name, source):
        super().__init__(cop)
        self.name = name
        self.source = source  # int index of source instruction

    def execute(self, frame):
        value = frame.get_value(self.source)
        frame.env[self.name] = value
        return frame.set_result(value)

    def format(self, idx):
        return f"%{idx}  StoreLocal '{self.name}' = %{self.source}"


class SelectResult(Instruction):
    """Pass through an earlier register's value as the result.

    Used by statement.define codegen to preserve the last expression
    result when trailing !let bindings would otherwise clobber it.
    """

    def __init__(self, cop, source):
        super().__init__(cop)
        self.source = source  # int index of source instruction

    def execute(self, frame):
        value = frame.get_value(self.source)
        return frame.set_result(value)

    def format(self, idx):
        return f"%{idx}  SelectResult %{self.source}"


class SetContext(Instruction):
    """Evaluate an expression, store in local env, and add to frame context (!ctx).

    Like StoreLocal but also updates frame.context so the binding flows down
    as an implicit named argument default into any function called from this
    frame or its descendants.
    """

    def __init__(self, cop, name, source):
        super().__init__(cop)
        self.name = name
        self.source = source  # int index of source instruction

    def execute(self, frame):
        value = frame.get_value(self.source)
        frame.env[self.name] = value
        frame.context[self.name] = value
        return frame.set_result(value)

    def format(self, idx):
        return f"%{idx}  SetContext '{self.name}' = %{self.source}"


class DeepSetLocal(Instruction):
    """Read-modify-write a local variable at a deep field path.

    Loads base_name from frame.env (creating an empty struct if absent or
    non-struct), deep-sets path=value building new immutable structs at each
    level, then stores the resulting root value back to base_name.

    Optionally also updates frame.context (used by !ctx deep assignments).

    Args:
        base_name:      Top-level local variable name (str)
        path:           Remaining path segments; each is a str (named field)
                        or int (positional index)
        value_reg:      Register index of the new value to set at the leaf
        update_context: If True, also write the new root value to frame.context
    """

    def __init__(self, cop, base_name, path, value_reg, update_context=False):
        super().__init__(cop)
        self.base_name = base_name
        self.path = path
        self.value_reg = value_reg
        self.update_context = update_context

    def execute(self, frame):
        base = frame.env.get(self.base_name)
        if base is None or not isinstance(base.data, dict):
            base = comp.Value.from_python({})
        new_value = frame.get_value(self.value_reg)
        result = _deep_set_value(base, self.path, new_value)
        frame.env[self.base_name] = result
        if self.update_context:
            frame.context[self.base_name] = result
        return frame.set_result(result)

    def format(self, idx):
        path_str = ".".join(str(s) for s in self.path)
        return f"%{idx}  DeepSetLocal '{self.base_name}.{path_str}' = %{self.value_reg}"


# ---------------------------------------------------------------------------
# Invocation
# ---------------------------------------------------------------------------

class TryInvoke(Instruction):
    """Invoke the value in a register with empty args if it is callable.

    If the value is a Callable, Block, or InternalCallable, it is called
    with no piped input and empty args. Otherwise the value passes through.

    The codegen emits this explicitly after value-position references and at
    the end of each definition's instruction sequence.
    """

    def __init__(self, cop, value):
        super().__init__(cop)
        self.value = value  # int register index

    def execute(self, frame):
        val = frame.get_value(self.value)
        if isinstance(val.data, (comp.Callable, comp.InternalCallable)):
            empty_args = comp.Value.from_python({})
            try:
                val = frame.invoke_block(val, empty_args, piped=None, source_cop=self.cop)
            except comp.CompFail as e:
                frame.failure = e.value
                return frame.set_result(e.value)
        return frame.set_result(val)

    def format(self, idx):
        return f"%{idx}  TryInvoke %{self.value}"


class Invoke(Instruction):
    """Invoke a function/block with arguments (no piped input)."""

    def __init__(self, cop, callable, args):
        super().__init__(cop)
        self.callable = callable  # int index
        self.args = args          # int index

    def execute(self, frame):
        callable_val = frame.get_value(self.callable)
        args_val = frame.get_value(self.args)
        try:
            result = frame.invoke_block(callable_val, args_val, piped=None, source_cop=self.cop)
        except comp.CompFail as e:
            frame.failure = e.value
            return frame.set_result(e.value)
        return frame.set_result(result)

    def format(self, idx):
        return f"%{idx}  Invoke %{self.callable} (%{self.args})"


class PipeInvoke(Instruction):
    """Invoke a function/block with piped input and arguments."""

    def __init__(self, cop, callable, piped, args):
        super().__init__(cop)
        self.callable = callable  # int index
        self.piped = piped        # int index - the piped input value
        self.args = args          # int index

    def execute(self, frame):
        callable_val = frame.get_value(self.callable)
        piped_val = frame.get_value(self.piped)
        args_val = frame.get_value(self.args)
        try:
            result = frame.invoke_block(callable_val, args_val, piped=piped_val, source_cop=self.cop)
        except comp.CompFail as e:
            frame.failure = e.value
            return frame.set_result(e.value)
        return frame.set_result(result)

    def format(self, idx):
        return f"%{idx}  PipeInvoke %{self.callable} (%{self.piped} | %{self.args})"


class Forward(Instruction):
    """Re-dispatch the current call to the next less-specific overload.

    Reads __self__ from the frame env to find the currently-executing Block,
    looks up its Callable by dispatch_set_name, then re-runs dispatch
    skipping this block (by qualified name).

    piped_reg: int register index for the piped input, or None to use $ from env.
    """

    def __init__(self, cop, piped_reg):
        super().__init__(cop)
        self.piped_reg = piped_reg

    def execute(self, frame):
        # Resolve piped input
        if self.piped_reg is not None:
            piped_val = frame.get_value(self.piped_reg)
        else:
            piped_val = frame._dollar_vars.get("$")

        # Locate the current Block via __self__
        self_val = frame.env.get("__self__")
        if self_val is None or not isinstance(self_val.data, comp.Callable):
            raise comp.CodeError("!forward used outside of a !func body", self.cop)
        current_block = self_val.data.scalar_block()

        dispatch_set_name = getattr(current_block, "dispatch_set_name", None)
        skip_name = current_block.qualified
        if not dispatch_set_name:
            raise comp.CodeError("!forward: current function has no dispatch context", self.cop)

        # Look up the Callable via module namespace.
        callable_val = None
        if frame.module:
            ns = frame.module.namespace()
            item = ns.get(dispatch_set_name)
            if isinstance(item, comp.DefinitionSet):
                # Convert DefinitionSet to Callable for dispatch
                try:
                    callable_val = _load_name(dispatch_set_name, frame)
                except NameError:
                    pass
        if callable_val is None or not isinstance(getattr(callable_val, "data", None), comp.Callable):
            raise comp.CodeError(
                f"!forward: '{dispatch_set_name}' has no other overloads",
                self.cop,
            )

        # Re-dispatch skipping our own block
        _empty = comp.Value.from_python({})
        result = frame._dispatch_overload(callable_val.data, _empty, piped_val, skip_name=skip_name)
        if result is None:
            raise comp.CodeError(
                f"!forward: no other overload of '{dispatch_set_name}' matched",
                self.cop,
            )
        if isinstance(result, comp.Value):
            return frame.set_result(result)
        # Got a Block — invoke it
        callable = comp.Callable(result.qualified)
        callable.add_block(result)
        block_val = comp.Value(callable)
        try:
            return frame.set_result(frame.invoke_block(block_val, _empty, piped=piped_val, source_cop=self.cop))
        except comp.CompFail as e:
            frame.failure = e.value
            return frame.set_result(e.value)

    def format(self, idx):
        if self.piped_reg is not None:
            return f"%{idx}  Forward (piped=%{self.piped_reg})"
        return f"%{idx}  Forward (piped=$)"


# ---------------------------------------------------------------------------
# Arithmetic / Comparison
# ---------------------------------------------------------------------------

class BinOp(Instruction):
    """Binary arithmetic/logical operation."""

    def __init__(self, cop, op, left, right):
        super().__init__(cop)
        self.op = op
        self.left = left    # int index
        self.right = right  # int index

    def execute(self, frame):
        left_val = frame.get_value(self.left)
        right_val = frame.get_value(self.right)
        try:
            if self.op in ("!and", "!or"):
                result = comp._ops.logic_binary(self.op, left_val, right_val)
            else:
                result = comp._ops.math_binary(self.op, left_val, right_val)
        except (TypeError, ValueError, ZeroDivisionError, ArithmeticError) as e:
            fail_val = comp._interp._make_fail_value(e, tag=comp._interp._exception_to_tag(e), cop_val=self.cop)
            frame.failure = fail_val
            return frame.set_result(fail_val)
        return frame.set_result(result)

    def format(self, idx):
        return f"%{idx}  BinOp '{self.op}' %{self.left} %{self.right}"


class UnOp(Instruction):
    """Unary arithmetic/logical operation."""

    def __init__(self, cop, op, operand):
        super().__init__(cop)
        self.op = op
        self.operand = operand  # int index

    def execute(self, frame):
        operand_val = frame.get_value(self.operand)
        try:
            if self.op == "!not":
                result = comp._ops.logic_unary(self.op, operand_val)
            else:
                result = comp._ops.math_unary(self.op, operand_val)
        except (TypeError, ValueError, ArithmeticError) as e:
            fail_val = comp._interp._make_fail_value(e, tag=comp._interp._exception_to_tag(e), cop_val=self.cop)
            frame.failure = fail_val
            return frame.set_result(fail_val)
        return frame.set_result(result)

    def format(self, idx):
        return f"%{idx}  UnOp '{self.op}' %{self.operand}"


class CmpOp(Instruction):
    """Comparison operation (==, !=, <, <=, >, >=)."""

    def __init__(self, cop, op, left, right):
        super().__init__(cop)
        self.op = op
        self.left = left    # int index
        self.right = right  # int index

    def execute(self, frame):
        left_val = frame.get_value(self.left)
        right_val = frame.get_value(self.right)
        try:
            result = comp._ops.compare(self.op, left_val, right_val)
        except (TypeError, ValueError) as e:
            fail_val = comp._interp._make_fail_value(e, tag=comp._interp._exception_to_tag(e), cop_val=self.cop)
            frame.failure = fail_val
            return frame.set_result(fail_val)
        return frame.set_result(result)

    def format(self, idx):
        return f"%{idx}  CmpOp '{self.op}' %{self.left} %{self.right}"


# ---------------------------------------------------------------------------
# Struct / Field Access
# ---------------------------------------------------------------------------

class GetField(Instruction):
    """Get a named field from a struct."""

    def __init__(self, cop, struct_reg, field):
        super().__init__(cop)
        self.struct_reg = struct_reg  # Register containing the struct
        self.field = field  # Field name to extract

    def execute(self, frame):
        struct_val = frame.get_value(self.struct_reg)
        # Look up the field by name
        field_key = comp.Value.from_python(self.field)
        result = struct_val.data.get(field_key)
        if result is None:
            raise comp.CodeError(f"Field '{self.field}' not found in struct", self.cop)
        return frame.set_result(result)

    def format(self, idx):
        return f"%{idx}  GetField %{self.struct_reg}.{self.field}"


class GetIndex(Instruction):
    """Get a field from a struct by position (0-based)."""

    def __init__(self, cop, struct_reg, index):
        super().__init__(cop)
        self.struct_reg = struct_reg  # Register containing the struct
        self.index = index  # 0-based position

    def execute(self, frame):
        struct_val = frame.get_value(self.struct_reg)
        # Get field by position
        items = list(struct_val.data.items())
        if self.index < 0 or self.index >= len(items):
            raise comp.CodeError(f"Index {self.index} out of range for struct with {len(items)} fields", self.cop)
        _, result = items[self.index]
        return frame.set_result(result)

    def format(self, idx):
        return f"%{idx}  GetIndex %{self.struct_reg}.#{self.index}"


class GetDynamicIndex(Instruction):
    """Get a field from a struct by a runtime-computed position (0-based)."""

    def __init__(self, cop, struct_reg, index_reg):
        super().__init__(cop)
        self.struct_reg = struct_reg
        self.index_reg = index_reg

    def execute(self, frame):
        struct_val = frame.get_value(self.struct_reg)
        index_val = frame.get_value(self.index_reg)
        import decimal
        if not isinstance(index_val.data, decimal.Decimal):
            raise comp.CodeError(f"Index expression must be a number, got {type(index_val.data).__name__}", self.cop)
        index = int(index_val.data)
        items = list(struct_val.data.items())
        if index < 0 or index >= len(items):
            raise comp.CodeError(f"Index {index} out of range for struct with {len(items)} fields", self.cop)
        _, result = items[index]
        return frame.set_result(result)

    def format(self, idx):
        return f"%{idx}  GetDynamicIndex %{self.struct_reg}.#(%{self.index_reg})"


class BuildStruct(Instruction):
    """Build a struct from field values."""

    def __init__(self, cop, fields):
        super().__init__(cop)
        self.fields = fields  # List of (key, source_idx) tuples

    def execute(self, frame):
        struct_data = {}
        for key, source in self.fields:
            value = frame.get_value(source)
            struct_data[key] = value
        result = comp.Value.from_python(struct_data)
        return frame.set_result(result)

    def format(self, idx):
        parts = []
        for key, src in self.fields:
            if isinstance(key, comp.Unnamed):
                parts.append(f"%{src}")
            else:
                parts.append(f"{key}=%{src}")
        return f"%{idx}  BuildStruct ({' '.join(parts)})"


class BuildInvokeData(Instruction):
    """Build an invoke-data struct from the current frame state and a statement value.

    Captures:
      statement — the value in statement_reg (a Block, text, or anything else)
      input     — the current piped value (frame._dollar_vars["$"], or nil)
      locals    — all frame env bindings except the $ family
      context   — the frame context dict

    This is emitted by the codegen for every @wrapper expression and for
    wrapper-annotated function definitions, so the wrapper function receives
    the full call-site context.
    """

    def __init__(self, cop, statement_reg):
        super().__init__(cop)
        self.statement_reg = statement_reg

    def execute(self, frame):
        statement_val = frame.get_value(self.statement_reg)

        # Wrap callable statements in StatementHandle to prevent TryInvoke from
        # auto-calling them if a wrapper function accesses $.statement.
        # Non-callable values (text, numbers, structs) are stored as-is.
        if isinstance(statement_val.data, (comp.Callable, comp.InternalCallable)):
            statement_stored = comp.Value(comp.StatementHandle(statement_val))
        else:
            statement_stored = statement_val

        # Current piped input ($)
        _nil = comp.Value.from_python(comp.tag_nil)
        input_val = frame._dollar_vars.get("$", _nil)

        # locals: env bindings that are actual user-defined locals
        # (no namespace-qualified names like mod.func)
        local_data = {}
        for k, v in frame.env.items():
            if "." not in k:
                local_data[comp.Value.from_python(k)] = v
        locals_val = comp.Value(local_data)

        # context dict
        ctx_data = {}
        for k, v in frame.context.items():
            ctx_data[comp.Value.from_python(k)] = v
        context_val = comp.Value(ctx_data)

        _k = comp.Value.from_python
        result = comp.Value({
            _k("statement"): statement_stored,
            _k("input"):     input_val,
            _k("locals"):    locals_val,
            _k("context"):   context_val,
        })
        return frame.set_result(result)

    def format(self, idx):
        return f"%{idx}  BuildInvokeData stmt=%{self.statement_reg}"


class UnwrapStatementHandle(Instruction):
    """Unwrap a StatementHandle, returning the inner callable value.

    If the input register holds a StatementHandle, sets the result to the
    inner value (the original callable).  Otherwise passes the value through
    unchanged.

    Emitted by _build_function immediately after the PipeInvoke that calls a
    definition-time wrapper, so that a pass-through wrapper (one that returns
    $.statement) causes the definition to store the original Block rather than
    the opaque handle.
    """

    def __init__(self, cop, value):
        super().__init__(cop)
        self.value = value  # int register index

    def execute(self, frame):
        val = frame.get_value(self.value)
        if isinstance(val.data, comp.StatementHandle):
            return frame.set_result(val.data.val)
        return frame.set_result(val)

    def format(self, idx):
        return f"%{idx}  UnwrapStatementHandle %{self.value}"


# ---------------------------------------------------------------------------
# Block / Shape Construction
# ---------------------------------------------------------------------------

class BuildBlock(Instruction):
    """Build a block/function value."""

    def __init__(self, cop, signature_cop, body_instructions, dispatch_own_name=None, dispatch_set_name=None, pure=False):
        super().__init__(cop)
        self.signature_cop = signature_cop
        self.body_instructions = body_instructions
        self.dispatch_own_name = dispatch_own_name
        self.dispatch_set_name = dispatch_set_name
        self.pure = pure

    def execute(self, frame):
        # Create a Block object and store the execution data
        block = comp.Block(self.dispatch_own_name or "anonymous")
        block.module = frame.module  # Capture the defining module
        block.body_instructions = self.body_instructions
        block.closure_env = frame.env
        block.captured_dollar_vars = dict(frame._dollar_vars)
        block.signature_cop = self.signature_cop
        block.dispatch_set_name = self.dispatch_set_name
        block.pure = self.pure

        # Parse signature to extract parameter names and shapes.
        # Two formats may appear depending on origin:
        #
        #   block.signature from _build_function:
        #     kids are tagged signature.input / signature.param / signature.block
        #
        #   shape.define from _build_block (inline block):
        #     kids are shape.field nodes with a "name" attribute (legacy format)
        #
        # We dispatch on each kid's COP tag.  signature.param kids accumulate into
        # an arg Shape with named ShapeFields; legacy shape.field kids use the old
        # i==0 (input) / i==1 (arg) index convention.
        sig_kids = list(comp.cop_kids(self.signature_cop))
        param_fields = []   # accumulated ShapeField objects for signature.param nodes
        block_fields = []   # accumulated ShapeField objects for signature.block nodes
        legacy_index = 0    # fallback counter for shape.field kids

        for field_cop in sig_kids:
            field_tag = comp.cop_tag(field_cop)

            if field_tag == "signature.input":
                # --- Input shape declaration (no binding name) ---
                inner_kids = list(comp.cop_kids(field_cop))
                for fkid in inner_kids:
                    fkid_tag = comp.cop_tag(fkid)
                    if fkid_tag == "shape.define":
                        block.input_shape = self._build_shape_from_cop(fkid, frame)
                        break
                    elif fkid_tag in ("value.identifier", "value.constant"):
                        resolved = self._resolve_shape_ref(fkid, frame)
                        if resolved is not None:
                            block.input_shape = resolved
                        break

            elif field_tag in ("signature.param",):
                # --- Named :param or :block declaration ---
                try:
                    param_name = field_cop.to_python("name")
                except (KeyError, AttributeError):
                    param_name = None

                inner_kids = list(comp.cop_kids(field_cop))
                param_type_shape = None
                param_default = None

                for fkid in inner_kids:
                    fkid_tag = comp.cop_tag(fkid)
                    if fkid_tag == "shape.default":
                        # Evaluate the default expression in the current frame
                        default_kids = list(comp.cop_kids(fkid))
                        if default_kids:
                            param_default = frame.eval(default_kids[0])
                    elif fkid_tag == "shape.define":
                        param_type_shape = self._build_shape_from_cop(fkid, frame)
                    else:
                        resolved = self._resolve_shape_ref(fkid, frame)
                        if resolved is not None:
                            param_type_shape = resolved

                # All params are now !param (no separate :block)
                # Use the declared shape for type checking
                sf = comp.ShapeField(name=param_name, shape=param_type_shape, default=param_default)
                param_fields.append(sf)

            else:
                # --- Legacy shape.field format (inline blocks) ---
                try:
                    param_name = field_cop.to_python("name")
                except (KeyError, AttributeError):
                    param_name = None

                param_shape = None
                field_kids = list(comp.cop_kids(field_cop))
                for fkid in field_kids:
                    fkid_tag = comp.cop_tag(fkid)
                    if fkid_tag == "shape.define":
                        param_shape = self._build_shape_from_cop(fkid, frame)
                        break
                    elif fkid_tag in ("value.identifier", "value.constant", "value.namespace"):
                        resolved = self._resolve_shape_ref(fkid, frame)
                        if resolved is not None:
                            param_shape = resolved
                        break

                if legacy_index == 0:
                    if param_name:
                        block.input_name = param_name
                    if param_shape is not None:
                        block.input_shape = param_shape
                elif legacy_index == 1:
                    if param_name:
                        block.arg_name = param_name
                    if param_shape is not None:
                        block.arg_shape = param_shape
                legacy_index += 1

        # Build arg Shape from accumulated :param fields.
        if param_fields:
            arg_shape = comp.Shape("args", private=False)
            arg_shape.fields = param_fields
            block.arg_shape = arg_shape
            block.param_names = [f.name for f in param_fields if f.name]

        callable = comp.Callable(block.qualified)
        callable.add_block(block)
        result = comp.Value(callable)
        return frame.set_result(result)

    def _resolve_shape_ref(self, fkid, frame):
        """Resolve a COP node that references a shape by name (value.identifier etc.).

        Args:
            fkid: (Value) COP node — value.identifier, value.namespace, or value.constant
            frame: (ExecutionFrame) Frame for env/namespace lookup

        Returns:
            (Shape | Tag | ShapeUnion | None) Resolved shape, or None if not resolvable
        """
        fkid_tag = comp.cop_tag(fkid)
        if fkid_tag == "value.constant":
            try:
                const_val = fkid.field("value")
                if isinstance(const_val.data, (comp.Shape, comp.Tag, comp.ShapeUnion)):
                    return const_val.data
            except (KeyError, AttributeError):
                pass
            return None

        ref_name = None
        if fkid_tag == "value.identifier":
            id_kids = comp.cop_kids(fkid)
            if id_kids:
                try:
                    ref_name = id_kids[0].to_python("value")
                except (KeyError, AttributeError):
                    pass
        elif fkid_tag == "value.namespace":
            try:
                ref_name = fkid.to_python("qualified")
                if isinstance(ref_name, list):
                    ref_name = None
            except (KeyError, AttributeError):
                pass

        if not ref_name:
            return None

        # Check frame env first
        if hasattr(frame, "env") and ref_name in frame.env:
            env_val = frame.env[ref_name]
            if hasattr(env_val, "data") and isinstance(env_val.data, (comp.Shape, comp.Tag, comp.ShapeUnion)):
                return env_val.data
            if hasattr(env_val, "data") and isinstance(env_val.data, comp.Callable):
                if env_val.data.shape is not None:
                    return env_val.data.shape

        # Fall back to namespace definition
        defn = frame.lookup(ref_name) if hasattr(frame, "lookup") else None
        if defn is not None:
            if isinstance(defn, comp.DefinitionSet):
                defs = list(defn.definitions)
                defn = defs[0] if defs else None
            if defn is not None and hasattr(defn, "value") and defn.value is not None:
                resolved = defn.value.data
                if isinstance(resolved, (comp.Shape, comp.Tag, comp.ShapeUnion)):
                    return resolved
                if isinstance(resolved, comp.Callable) and resolved.shape is not None:
                    return resolved.shape
        return None

    def _build_shape_from_cop(self, shape_cop, frame):
        """Build a Shape object from a shape.define COP node.

        If the shape.define contains a single value.namespace or value.identifier
        child (not shape.field children), it's a reference to a named shape —
        look it up and return it directly.
        """
        kids = list(comp.cop_kids(shape_cop))

        # Check for a reference to a named shape: shape.define[value.namespace "foo"]
        if kids and not any(comp.cop_tag(k) == "shape.field" for k in kids):
            for kid in kids:
                kid_tag = comp.cop_tag(kid)
                ref_name = None
                # Handle folded constant containing a Shape directly
                if kid_tag == "value.constant":
                    try:
                        const_val = kid.field("value")
                        if isinstance(const_val.data, (comp.Shape, comp.Tag, comp.ShapeUnion)):
                            return const_val.data
                    except (KeyError, AttributeError):
                        pass
                elif kid_tag == "value.namespace":
                    try:
                        ref_name = kid.to_python("qualified")
                        if isinstance(ref_name, list):
                            ref_name = None  # overloads don't resolve to a single shape
                    except (KeyError, AttributeError):
                        pass
                elif kid_tag == "value.identifier":
                    id_kids = comp.cop_kids(kid)
                    if id_kids:
                        try:
                            ref_name = id_kids[0].to_python("value")
                        except (KeyError, AttributeError):
                            pass
                if ref_name:
                    # Check frame env first (evaluated definitions live here)
                    if hasattr(frame, "env") and ref_name in frame.env:
                        env_val = frame.env[ref_name]
                        if hasattr(env_val, "data") and isinstance(env_val.data, (comp.Shape, comp.Tag, comp.ShapeUnion)):
                            return env_val.data
                    # Fall back to namespace / system lookup via _load_name
                    try:
                        name_val = _load_name(ref_name, frame)
                        if hasattr(name_val, "data") and isinstance(name_val.data, (comp.Shape, comp.Tag, comp.ShapeUnion)):
                            return name_val.data
                    except (NameError, Exception):
                        pass
                    # Reference not resolved — return None so input_shape stays unset
                    return None

        shape = comp.Shape("anonymous", private=False)

        for kid in kids:
            kid_tag = comp.cop_tag(kid)
            if kid_tag != "shape.field":
                continue

            # Get field name
            try:
                field_name = kid.to_python("name")
            except (KeyError, AttributeError):
                field_name = None

            # Get shape constraint and default from children
            field_shape = None
            field_default = None
            field_kids = comp.cop_kids(kid)

            for j, fkid in enumerate(field_kids):
                fkid_tag = comp.cop_tag(fkid)
                if fkid_tag.startswith("value."):
                    if field_shape is None:
                        # First value is shape reference
                        if fkid_tag == "value.identifier":
                            id_kids = comp.cop_kids(fkid)
                            if id_kids:
                                ref_name = id_kids[0].to_python("value")
                                try:
                                    name_val = _load_name(ref_name, frame)
                                    if hasattr(name_val, "data") and isinstance(name_val.data, (comp.Shape, comp.Tag, comp.ShapeUnion)):
                                        field_shape = name_val.data
                                except (NameError, Exception):
                                    pass
                        # Mark that we've seen the shape, even if lookup failed
                        if field_shape is None:
                            field_shape = comp.shape_any  # fallback
                    else:
                        # Second value is default - evaluate simple constants
                        field_default = self._eval_simple_value(fkid)

            field_obj = comp.ShapeField(name=field_name, shape=field_shape, default=field_default)
            shape.fields.append(field_obj)

        return shape

    def _eval_simple_value(self, cop):
        """Evaluate a simple constant COP to a Value."""
        import decimal
        tag = comp.cop_tag(cop)

        if tag == "value.number":
            literal = cop.to_python("value")
            return comp.Value.from_python(decimal.Decimal(literal))
        elif tag == "value.text":
            literal = cop.to_python("value")
            return comp.Value.from_python(literal)
        elif tag == "value.identifier":
            # Could be nil, true, false
            id_kids = comp.cop_kids(cop)
            if id_kids:
                name = id_kids[0].to_python("value")
                if name == "nil":
                    return comp.Value.from_python(comp.tag_nil)
                elif name == "true":
                    return comp.Value.from_python(comp.tag_true)
                elif name == "false":
                    return comp.Value.from_python(comp.tag_false)
        # For complex expressions, return None (no default)
        return None

    def format(self, idx):
        return f"%{idx}  BuildBlock ({len(self.body_instructions)} body)"


class BuildShape(Instruction):
    """Build a shape value from field definitions."""

    def __init__(self, cop, fields):
        super().__init__(cop)
        self.fields = fields  # List of (name, shape_ref, unit_ref, default_idx, limit_refs) tuples
        # shape_ref and unit_ref are either a string (name to look up) or int (register index)
        # limit_refs is a list of (name_str, param_reg_or_None) — name resolved by coptimize

    def execute(self, frame):
        shape = comp.Shape("anonymous", private=False)

        for name, shape_ref, unit_ref, default_idx, limit_refs in self.fields:
            # Get shape constraint if provided
            shape_constraint = None
            if shape_ref is not None:
                if isinstance(shape_ref, str):
                    # Static name reference — look up in frame
                    try:
                        shape_val = _load_name(shape_ref, frame)
                    except NameError:
                        shape_val = None
                    # Unwrap Callable (shape may be in callable.shape)
                    if shape_val and isinstance(shape_val.data, comp.Callable):
                        if shape_val.data.shape is not None:
                            shape_val = comp.Value.from_python(shape_val.data.shape)
                    # Unwrap DefinitionSet (lazily resolved shape definitions)
                    if shape_val and isinstance(shape_val.data, comp.DefinitionSet):
                        for defn in shape_val.data.definitions:
                            dv = _ensure_definition_value(defn, frame)
                            if dv and isinstance(dv.data, (comp.Shape, comp.ShapeUnion, comp.Tag)):
                                shape_val = dv
                                break
                    if shape_val and isinstance(shape_val.data, (comp.Shape, comp.ShapeUnion, comp.Tag)):
                        shape_constraint = shape_val.data
                    else:
                        # Not resolved yet (forward ref or unresolvable) — store
                        # name string so _resolve_shape_field in morph can retry
                        shape_constraint = shape_ref
                else:
                    shape_val = frame.get_value(shape_ref)
                    if shape_val and isinstance(shape_val.data, (comp.Shape, comp.ShapeUnion, comp.Tag)):
                        shape_constraint = shape_val.data

            # Get unit constraint if provided
            unit_constraint = None
            if unit_ref is not None:
                if isinstance(unit_ref, str):
                    try:
                        unit_val = _load_name(unit_ref, frame)
                    except NameError:
                        unit_val = None
                    if unit_val and isinstance(unit_val.data, comp.Tag):
                        unit_constraint = unit_val.data
                else:
                    unit_val = frame.get_value(unit_ref)
                    if unit_val and isinstance(unit_val.data, comp.Tag):
                        unit_constraint = unit_val.data

            # Get default if provided
            default_val = None
            if default_idx is not None:
                default_val = frame.get_value(default_idx)

            # Resolve limit function Values from their qualified names
            limits = []
            for lname, lparam_idx in limit_refs:
                func_val = None
                if isinstance(lname, str):
                    try:
                        func_val = _load_name(lname, frame)
                    except NameError:
                        pass
                elif isinstance(lname, list):
                    # Overloaded name (list of qualified names) — build Callable
                    callable = comp.Callable(lname[0] if lname else "?")
                    for oname in lname:
                        try:
                            defn = frame.lookup(oname)
                        except (NameError, KeyError):
                            defn = None
                        if defn is not None:
                            if isinstance(defn, comp.DefinitionSet):
                                for d in defn.definitions:
                                    _ensure_definition_value(d, frame)
                                    if d.value is not None:
                                        data = d.value.data
                                        if isinstance(data, comp.Callable):
                                            for b in data.blocks:
                                                callable.add_block(b)
                                        elif isinstance(data, comp.InternalCallable):
                                            callable.add_block(data)
                            elif isinstance(defn, comp.Definition):
                                _ensure_definition_value(defn, frame)
                                if defn.value is not None:
                                    data = defn.value.data
                                    if isinstance(data, comp.Callable):
                                        for b in data.blocks:
                                            callable.add_block(b)
                                    elif isinstance(data, comp.InternalCallable):
                                        callable.add_block(data)
                    if callable.blocks:
                        func_val = comp.Value(callable)
                elif isinstance(lname, int):
                    func_val = frame.get_value(lname)
                param_val = frame.get_value(lparam_idx) if lparam_idx is not None else None
                if func_val is not None:
                    limits.append((func_val, param_val))

            field = comp.ShapeField(name=name, shape=shape_constraint, unit=unit_constraint, default=default_val, limits=limits)
            shape.fields.append(field)

        result = comp.Value(shape)
        return frame.set_result(result)

    def format(self, idx):
        parts = []
        for name, shape_ref, unit_ref, default_idx, limit_refs in self.fields:
            part = name or "_"
            if shape_ref is not None:
                if isinstance(shape_ref, str):
                    part += f"~{shape_ref}"
                else:
                    part += f"~%{shape_ref}"
            if unit_ref is not None:
                if isinstance(unit_ref, str):
                    part += f"[{unit_ref}]"
                else:
                    part += f"[%{unit_ref}]"
            if default_idx is not None:
                part += f"=%{default_idx}"
            for lname, lparam_idx in limit_refs:
                if isinstance(lname, list):
                    ldisp = "|".join(lname)
                elif isinstance(lname, int):
                    ldisp = f"%{lname}"
                else:
                    ldisp = str(lname)
                part += f"<{ldisp}" + (f" p=%{lparam_idx}" if lparam_idx is not None else "") + ">"
            parts.append(part)
        return f"%{idx}  BuildShape ({' '.join(parts)})"


class BuildShapeUnion(Instruction):
    """Build a shape union from member shapes."""

    def __init__(self, cop, member_refs, default_idx=None):
        super().__init__(cop)
        self.member_refs = member_refs  # List of name strings or register indices
        self.default_idx = default_idx  # Optional register index for default value

    def execute(self, frame):
        shapes = []
        for ref in self.member_refs:
            if isinstance(ref, str):
                try:
                    shape_val = _load_name(ref, frame)
                except NameError:
                    shape_val = None
                # Unwrap Callable to get shape
                if shape_val and isinstance(shape_val.data, comp.Callable):
                    if shape_val.data.shape is not None:
                        shape_val = comp.Value.from_python(shape_val.data.shape)
                # Unwrap DefinitionSet to get the actual shape value
                if shape_val and isinstance(shape_val.data, comp.DefinitionSet):
                    for defn in shape_val.data.definitions:
                        dv = _ensure_definition_value(defn, frame)
                        if dv and isinstance(dv.data, (comp.Shape, comp.ShapeUnion, comp.Tag)):
                            shape_val = dv
                            break
                if shape_val and isinstance(shape_val.data, (comp.Shape, comp.ShapeUnion, comp.Tag)):
                    shapes.append(shape_val.data)
            else:
                val = frame.get_value(ref)
                if val and isinstance(val.data, (comp.Shape, comp.ShapeUnion, comp.Tag)):
                    shapes.append(val.data)

        default_val = None
        if self.default_idx is not None:
            default_val = frame.get_value(self.default_idx)

        union = comp.ShapeUnion(shapes, default=default_val)
        result = comp.Value(union)
        return frame.set_result(result)

    def format(self, idx):
        parts = []
        for ref in self.member_refs:
            parts.append(ref if isinstance(ref, str) else f"%{ref}")
        if self.default_idx is not None:
            parts.append(f"default=%{self.default_idx}")
        return f"%{idx}  BuildShapeUnion ({' '.join(parts)})"


class BuildShapeCollection(Instruction):
    """Build a collection shape from an element type and count bounds.

    Produces a ShapeCollection value that constrains a struct to contain
    N elements all matching the element type.
    """

    def __init__(self, cop, shape_ref, unit_ref, limit_refs, min_count, max_count):
        super().__init__(cop)
        self.shape_ref = shape_ref    # str name or int register index, or None
        self.unit_ref = unit_ref      # str name or int register index, or None
        self.limit_refs = limit_refs  # [(name_str_or_int, param_idx_or_None)]
        self.min_count = min_count    # int
        self.max_count = max_count    # int | None (unbounded)

    def execute(self, frame):
        # Resolve element shape
        shape_constraint = None
        if self.shape_ref is not None:
            if isinstance(self.shape_ref, str):
                try:
                    shape_val = _load_name(self.shape_ref, frame)
                except NameError:
                    shape_val = None
                if shape_val and isinstance(shape_val.data, comp.Callable):
                    if shape_val.data.shape is not None:
                        shape_val = comp.Value.from_python(shape_val.data.shape)
                if shape_val and isinstance(shape_val.data, comp.DefinitionSet):
                    for defn in shape_val.data.definitions:
                        dv = _ensure_definition_value(defn, frame)
                        if dv and isinstance(dv.data, (comp.Shape, comp.ShapeUnion, comp.Tag)):
                            shape_val = dv
                            break
                if shape_val and isinstance(shape_val.data, (comp.Shape, comp.ShapeUnion, comp.Tag)):
                    shape_constraint = shape_val.data  # type: ignore[union-attr]
                else:
                    shape_constraint = self.shape_ref  # keep name for deferred resolution
            else:
                shape_val = frame.get_value(self.shape_ref)
                if shape_val and isinstance(shape_val.data, (comp.Shape, comp.ShapeUnion, comp.Tag)):
                    shape_constraint = shape_val.data

        # Resolve unit
        unit_constraint = None
        if self.unit_ref is not None:
            if isinstance(self.unit_ref, str):
                try:
                    unit_val = _load_name(self.unit_ref, frame)
                except NameError:
                    unit_val = None
                if unit_val and isinstance(unit_val.data, comp.Tag):  # type: ignore[union-attr]
                    unit_constraint = unit_val.data  # type: ignore[union-attr]
            else:
                unit_val = frame.get_value(self.unit_ref)
                if unit_val and isinstance(unit_val.data, comp.Tag):
                    unit_constraint = unit_val.data

        # Resolve limit functions
        limits = []
        for lname, lparam_idx in self.limit_refs:
            func_val = None
            if isinstance(lname, str):
                try:
                    func_val = _load_name(lname, frame)
                except NameError:
                    pass
            elif isinstance(lname, list):
                # Overloaded name — build Callable
                callable = comp.Callable(lname[0] if lname else "?")
                for oname in lname:
                    try:
                        defn = frame.lookup(oname)
                    except (NameError, KeyError):
                        defn = None
                    if defn is not None:
                        if isinstance(defn, comp.DefinitionSet):
                            for d in defn.definitions:
                                _ensure_definition_value(d, frame)
                                if d.value is not None:
                                    data = d.value.data
                                    if isinstance(data, comp.Callable):
                                        for b in data.blocks:
                                            callable.add_block(b)
                                    elif isinstance(data, comp.InternalCallable):
                                        callable.add_block(data)
                        elif isinstance(defn, comp.Definition):
                            _ensure_definition_value(defn, frame)
                            if defn.value is not None:
                                data = defn.value.data
                                if isinstance(data, comp.Callable):
                                    for b in data.blocks:
                                        callable.add_block(b)
                                elif isinstance(data, comp.InternalCallable):
                                    callable.add_block(data)
                if callable.blocks:
                    func_val = comp.Value(callable)
            elif isinstance(lname, int):
                func_val = frame.get_value(lname)
            param_val = frame.get_value(lparam_idx) if lparam_idx is not None else None
            if func_val is not None:
                limits.append((func_val, param_val))

        element = comp.ShapeField(name=None, shape=shape_constraint, unit=unit_constraint, limits=limits)
        collection = comp.ShapeCollection(element, self.min_count, self.max_count)
        return frame.set_result(comp.Value(collection))

    def format(self, idx):
        elem = self.shape_ref if isinstance(self.shape_ref, str) else f"%{self.shape_ref}"
        if self.min_count == self.max_count:
            count = f"*{self.min_count}"
        elif self.max_count is None:
            count = "*" if self.min_count == 0 else f"*{self.min_count}+"
        else:
            count = f"*{self.min_count}-{self.max_count}"
        return f"%{idx}  BuildShapeCollection (~{elem}{count})"


# ---------------------------------------------------------------------------
# Unit Operations
# ---------------------------------------------------------------------------

class CastUnit(Instruction):
    """Apply a unit tag to a value (value[unit] syntax).

    Attaches the specified unit tag to the value. If the value already has a
    unit from the same family, converts using the unit conversion table.
    If units are from incompatible families, raises EvalError.
    Bare-to-unit is always valid. Unit-to-bare (unit=None) is always valid.
    """

    def __init__(self, cop, value_reg, unit_reg):
        super().__init__(cop)
        self.value_reg = value_reg  # register index of the input value
        self.unit_reg = unit_reg    # register index of the unit tag value

    def execute(self, frame):
        value = frame.get_value(self.value_reg)
        unit_val = frame.get_value(self.unit_reg)

        if not isinstance(unit_val.data, comp.Tag):
            raise comp.EvalError(
                f"Unit must be a tag, got {unit_val.format()}", self.cop
            )

        # nil tag means "no unit" — strip any existing annotation
        if unit_val.data is comp.tag_nil:
            return frame.set_result(value.with_unit(None))

        new_unit = unit_val.data
        old_unit = value.unit

        if old_unit is None or old_unit is new_unit:
            # Bare-to-unit or same unit: just attach
            return frame.set_result(value.with_unit(new_unit))

        if old_unit.qualified == new_unit.qualified:
            return frame.set_result(value.with_unit(new_unit))

        # Try conversion between units
        import comp._unit_conv as _uc
        try:
            new_data = _uc.convert(value.data, old_unit, new_unit)
        except comp.EvalError:
            raise
        except Exception as e:
            raise comp.EvalError(
                f"Cannot convert [{old_unit.qualified}] to [{new_unit.qualified}]: {e}",
                self.cop
            )
        result = comp.Value(new_data).with_unit(new_unit)
        return frame.set_result(result)

    def format(self, idx):
        return f"%{idx}  CastUnit %{self.value_reg} %{self.unit_reg}"


class StripUnit(Instruction):
    """Strip the unit annotation from a value (expr[] syntax).

    Returns a new value identical to the input but with no unit annotation.
    Bare-to-bare is a no-op.
    """

    def __init__(self, cop, value_reg):
        super().__init__(cop)
        self.value_reg = value_reg

    def execute(self, frame):
        value = frame.get_value(self.value_reg)
        return frame.set_result(value.with_unit(None))

    def format(self, idx):
        return f"%{idx}  StripUnit %{self.value_reg}"


# ---------------------------------------------------------------------------
# Handle Operations
# ---------------------------------------------------------------------------

class GrabHandle(Instruction):
    """Create a handle instance from a tag value (!grab)."""

    def __init__(self, cop, tag_reg):
        super().__init__(cop)
        self.tag_reg = tag_reg  # Register containing the Tag value

    def execute(self, frame):
        tag_val = frame.get_value(self.tag_reg)
        result = comp._tag.grab_handle(tag_val, frame)
        # Register handle with this frame so it can be auto-dropped on exit.
        handle = result.data
        if frame.live_handles is None:
            frame.live_handles = {handle}
        else:
            frame.live_handles.add(handle)
        return frame.set_result(result)

    def format(self, idx):
        return f"%{idx}  GrabHandle %{self.tag_reg}"


class DropHandle(Instruction):
    """Release a handle, marking it as dropped (!drop)."""

    def __init__(self, cop, handle_reg):
        super().__init__(cop)
        self.handle_reg = handle_reg  # Register containing the HandleInstance value

    def execute(self, frame):
        handle_val = frame.get_value(self.handle_reg)
        result = comp._tag.drop_handle(handle_val, frame)
        # Remove from live tracking so the frame exit doesn't double-drop it.
        if frame.live_handles and isinstance(handle_val.data, comp.HandleInstance):
            frame.live_handles.discard(handle_val.data)
        return frame.set_result(result)

    def format(self, idx):
        return f"%{idx}  DropHandle %{self.handle_reg}"


class PullHandle(Instruction):
    """Get private data from a handle (!pull)."""

    def __init__(self, cop, handle_reg):
        super().__init__(cop)
        self.handle_reg = handle_reg  # Register containing the HandleInstance value

    def execute(self, frame):
        handle_val = frame.get_value(self.handle_reg)
        result = comp._tag.pull_handle(handle_val, frame)
        return frame.set_result(result)

    def format(self, idx):
        return f"%{idx}  PullHandle %{self.handle_reg}"


class PushHandle(Instruction):
    """Store private data in a handle (!push)."""

    def __init__(self, cop, handle_reg, data_reg):
        super().__init__(cop)
        self.handle_reg = handle_reg  # Register containing the HandleInstance value
        self.data_reg = data_reg      # Register containing the data to store

    def execute(self, frame):
        handle_val = frame.get_value(self.handle_reg)
        data_val = frame.get_value(self.data_reg)
        result = comp._tag.push_handle(handle_val, data_val, frame)
        return frame.set_result(result)

    def format(self, idx):
        return f"%{idx}  PushHandle %{self.handle_reg} %{self.data_reg}"


# ---------------------------------------------------------------------------
# Failure / Control Flow
# ---------------------------------------------------------------------------

class RaiseFail(Instruction):
    """!fail expr — set frame.failure to the given value and fast-forward.

    All subsequent instructions in the current frame are skipped (via the
    fast-forward logic in ExecutionFrame.run) until a Fallback or PipeFallback
    instruction catches the failure.
    """

    def __init__(self, cop, value_reg):
        super().__init__(cop)
        self.value_reg = value_reg

    def execute(self, frame):
        val = frame.get_value(self.value_reg)
        # Auto-wrap bare strings and tags into a proper failure struct
        if isinstance(val.data, str):
            val = comp._interp._make_fail_value(val.data)
        elif isinstance(val.data, comp.Tag) and val.data.qualified.startswith("fail"):
            val = comp._interp._make_fail_value("", tag=val.data)
        frame.failure = val
        return frame.set_result(val)

    def format(self, idx):
        return f"%{idx}  RaiseFail %{self.value_reg}"


class MergeWithPiped(Instruction):
    """Merge a result struct over the current piped input ($).

    Appended to a block's body instructions by the @update wrapper.  After the
    body produces a partial update struct, this instruction overlays those fields
    on top of the original piped struct so callers get the full merged record.
    """

    def __init__(self, cop, result_reg):
        super().__init__(cop)
        self.result_reg = result_reg

    def execute(self, frame):
        result = frame.get_value(self.result_reg)
        _nil = comp.Value.from_python(comp.tag_nil)
        piped = frame._dollar_vars.get("$", _nil)
        if not isinstance(piped.data, dict) or not isinstance(result.data, dict):
            return frame.set_result(result)
        merged = dict(piped.data)
        merged.update(result.data)
        return frame.set_result(comp.Value(merged))

    def format(self, idx):
        return f"%{idx}  MergeWithPiped %{self.result_reg}"


class FlattenFields(Instruction):
    """Flatten a struct-of-structs into a single flat struct.

    Appended to a block's body instructions by the @flat wrapper.  The body
    produces a struct whose values are themselves structs (e.g. from a
    multi-expression block).  This instruction concatenates all inner fields in
    order into one flat output struct.
    """

    def __init__(self, cop, result_reg):
        super().__init__(cop)
        self.result_reg = result_reg

    def execute(self, frame):
        result = frame.get_value(self.result_reg)
        if not isinstance(result.data, dict):
            return frame.set_result(comp.Value({comp.Unnamed(): result}))
        combined = {}
        for _k, sub_val in result.data.items():
            if isinstance(sub_val.data, dict):
                for sub_k, sub_v in sub_val.data.items():
                    if isinstance(sub_k, comp.Unnamed):
                        combined[comp.Unnamed()] = sub_v
                    else:
                        combined[sub_k] = sub_v
            else:
                combined[comp.Unnamed()] = sub_val
        return frame.set_result(comp.Value(combined))

    def format(self, idx):
        return f"%{idx}  FlattenFields %{self.result_reg}"


class Fallback(Instruction):
    """expr ?? handler — catch failure from expr and evaluate handler instead.

    If no failure is propagating: the test value passes through unchanged.
    If failure is propagating: clear failure, run handler_instructions in a
    child frame that shares the current env (same $ as the outer expression).
    The handler does NOT receive the failure value — it runs with the original
    frame environment.
    """

    can_catch_failure = True

    def __init__(self, cop, test_reg, handler_instructions):
        super().__init__(cop)
        self.test_reg = test_reg
        self.handler_instructions = handler_instructions

    def execute(self, frame):
        if frame.failure is None:
            return frame.set_result(frame.get_value(self.test_reg))
        # Failure — clear it and evaluate the handler in the same environment
        frame.failure = None
        handler_frame = frame._make_child_frame(dict(frame.env), module=frame.module)
        result = handler_frame.run(self.handler_instructions)
        if handler_frame.failure is not None:
            frame.failure = handler_frame.failure
        return frame.set_result(result)

    def format(self, idx):
        return f"%{idx}  Fallback %{self.test_reg} ({len(self.handler_instructions)} handler instrs)"


class PipeFallback(Instruction):
    """|? handler — catch pipeline failure; invoke handler with failure as piped input.

    If no failure is propagating: pass the piped value through unchanged.
    If failure is propagating: clear failure, invoke the handler callable with
    piped=failure_value so the handler can inspect what went wrong.

    callable_instructions and args_instructions are compiled into fresh child
    frames at runtime to avoid contamination from the parent failure state.
    """

    can_catch_failure = True

    def __init__(self, cop, piped_reg, callable_instructions, args_instructions):
        super().__init__(cop)
        self.piped_reg = piped_reg
        self.callable_instructions = callable_instructions
        self.args_instructions = args_instructions

    def execute(self, frame):
        failure = frame.failure
        if failure is None:
            return frame.set_result(frame.get_value(self.piped_reg))
        # Failure — clear it and invoke the handler with failure as piped input
        frame.failure = None
        callable_frame = frame._make_child_frame(dict(frame.env), module=frame.module)
        callable_val = callable_frame.run(self.callable_instructions)
        args_frame = frame._make_child_frame(dict(frame.env), module=frame.module)
        args_val = args_frame.run(self.args_instructions)
        if args_val is None:
            args_val = comp.Value.from_python({})
        try:
            result = frame.invoke_block(callable_val, args_val, piped=failure, source_cop=self.cop)
        except comp.CompFail as e:
            frame.failure = e.value
            return frame.set_result(e.value)
        return frame.set_result(result)

    def format(self, idx):
        return f"%{idx}  PipeFallback %{self.piped_reg} ({len(self.callable_instructions)} callable instrs)"


class DispatchOn(Instruction):
    """Pattern-dispatch operator (!on).

    Evaluates the condition value, then tests each branch pattern (a Shape)
    in order via morph. Returns the result of the first matching branch.
    Raises CodeError if no branch matches.

    Each branch is a pair of instruction lists:
      - pattern_instructions: produces the Shape to match against
      - result_instructions: produces the value to return on match

    Both lists are run in child frames that share the current
    lexical environment so that !let bindings remain accessible.
    """

    def __init__(self, cop, condition, branches):
        super().__init__(cop)
        self.condition = condition  # int register index of the condition value
        self.branches = branches  # list of (pattern_instructions, result_instructions)

    def execute(self, frame):
        condition_val = frame.get_value(self.condition)

        for pattern_instructions, result_instructions in self.branches:
            # Build the shape/tag pattern in a child frame sharing current env
            pattern_frame = frame._make_child_frame(dict(frame.env), module=frame.module)
            pattern_frame._dollar_vars = dict(frame._dollar_vars)
            pattern_val = pattern_frame.run(pattern_instructions)

            if pattern_val is None:
                continue

            pattern_data = pattern_val.data

            # ~else tag is a catch-all — always matches
            if pattern_data is comp.tag_else:
                matched = True
            # morph() accepts Shape, ShapeUnion, and Tag — pass the raw data object.
            # For anything else (e.g. a bare constant), fall back to equality.
            elif isinstance(pattern_data, (comp.Shape, comp.ShapeUnion, comp.Tag)):
                morph_result = comp.morph(condition_val, pattern_data, frame)
                matched = not morph_result.failure_reason
                # Leaf-tag identity: morph rejects depth-0 matches (tags are
                # abstract shape roots, not values).  For exact leaf-tag dispatch
                # (e.g. ~true, ~false, ~nil, ~less) fall back to qualified-name
                # equality so condition_val bearing that exact tag still matches.
                if not matched and isinstance(pattern_data, comp.Tag) and isinstance(condition_val.data, comp.Tag):
                    matched = (condition_val.data.qualified == pattern_data.qualified)
            else:
                # Direct equality: the condition must produce the same value
                matched = (comp._ops.compare("==", condition_val, pattern_val).data is comp.tag_true)

            if matched:
                result_frame = frame._make_child_frame(frame.env, module=frame.module)
                result_frame._dollar_vars = dict(frame._dollar_vars)
                # Propagate branch failure to the parent frame so fast-forward
                # continues and invoke_block can detect and raise it.
                result = result_frame.run(result_instructions)
                if result_frame.failure is not None:
                    frame.failure = result_frame.failure
                return frame.set_result(result)

        raise comp.CodeError("No branch matched in !on dispatch", self.cop)

    def format(self, idx):
        return f"%{idx}  DispatchOn %{self.condition} ({len(self.branches)} branches)"




def _ensure_definition_value(defn, frame):
    """Lazily populate a definition's value if needed."""
    if defn.value is not None:
        return defn.value
    if defn.original_cop:
        cop_tag = comp.cop_tag(defn.original_cop)
        if cop_tag == "value.block":
            block = comp.create_blockdef(defn.qualified, defn.original_cop)
            block.module = frame.interp.module_cache.get(defn.module_id)
            callable = comp.Callable(defn.qualified)
            callable.add_block(block)
            defn.value = comp.Value(callable)
            return defn.value
        elif cop_tag == "shape.define":
            if frame.module:
                ns = frame.module.namespace()
                shape = comp.create_shape(defn.original_cop, ns)
                defn.value = comp.Value.from_python(shape)
                return defn.value
        elif cop_tag == "shape.union":
            # Build instructions for the union and execute them to get the value
            try:
                instructions = comp.generate_code_for_definition(defn.original_cop)
                child_frame = frame._make_child_frame(dict(frame.env))
                result = child_frame.run(instructions)
                if result is not None and isinstance(result.data, (comp.Shape, comp.ShapeUnion, comp.Tag)):
                    defn.value = result
                    return defn.value
            except Exception:
                pass
    return None



def _load_name(name, frame):
    """Resolve a name to a Value, checking env, module namespace, and system builtins."""
    if name in frame.env:
        return frame.env[name]

    if frame.module:
        ns = frame.module.namespace()
        if name in ns:
            item = ns[name]
            if isinstance(item, comp.DefinitionSet):
                # Build a Callable from the DefinitionSet's definitions
                callable = comp.Callable(name)
                for defn in item.definitions:
                    _ensure_definition_value(defn, frame)
                    if defn.value is None:
                        continue
                    data = defn.value.data
                    if isinstance(data, comp.Callable):
                        # Merge blocks from nested Callable
                        for b in data.blocks:
                            callable.add_block(b)
                        if data.shape is not None and callable.shape is None:
                            callable.shape = data.shape
                        if data.pipeline is not None and callable.pipeline is None:
                            callable.pipeline = data.pipeline
                    elif isinstance(data, (comp.Shape, comp.Tag, comp.ShapeUnion)):
                        callable.shape = data
                    elif isinstance(data, comp.InternalCallable):
                        callable.add_block(data)
                    else:
                        # Non-callable value (e.g. struct) — return directly
                        if len(item.definitions) == 1:
                            return defn.value
                # If only a shape/tag with no blocks, return the shape directly
                if not callable.blocks and callable.shape is not None and callable.pipeline is None:
                    return comp.Value.from_python(callable.shape)
                if callable.blocks or callable.pipeline:
                    return comp.Value(callable)
                # Fallback: single definition value
                for defn in item.definitions:
                    if defn.value is not None:
                        return defn.value
            elif hasattr(item, "value"):
                value = _ensure_definition_value(item, frame)
                if value:
                    return value

    system = frame.interp.system
    if system and name in system._definitions:
        defn = system._definitions[name]
        if defn.value:
            return defn.value

    raise NameError(f"Variable '{name}' not defined")
