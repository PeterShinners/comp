"""Pure function evaluation at compile time.

This module handles evaluating pure functions during compilation:
- Look up pure definitions via the module namespace
- Walk definition COPs looking for invocations of pure functions
- Replace pure invocations with constant result nodes when arguments
  are also constants

The COP nodes handled:
- value.reference to a pure function: implicit callables (TryInvoke semantics)
- value.binding{pure_ref, const_args}: explicit call with constant arguments
- value.pipeline: evaluate leading pure stages with constant inputs
"""

__all__ = [
    "evaluate_pure_definitions",
    "fold_pure_cop",
]

import comp


def evaluate_pure_definitions(definitions, namespace, interp):
    """Evaluate pure function invokes at compile time.

    Walks each definition's COP tree and evaluates pure invocations
    whose arguments are compile-time constants, using the module
    namespace to look up pure callables.

    Args:
        definitions: Dict {qualified_name: Definition} to process
        namespace: (dict) Module namespace mapping names to Callable
        interp: Interpreter instance for execution

    Returns:
        dict: The definitions dictionary (for chaining)

    Side effects:
        - Replaces pure invoke COPs with value.constant COPs
    """
    for name, defn in definitions.items():
        if defn.resolved_cop is None:
            continue
        new_cop = _eval_pure_in_cop(defn.resolved_cop, namespace, interp)
        if new_cop is not defn.resolved_cop:
            defn.resolved_cop = new_cop

    return definitions


def fold_pure_cop(cop, namespace, interp):
    """Apply pure folding to a single COP tree using namespace lookup.

    Used for COP trees that are not part of the definitions dict, such as
    startup blocks, which are obtained separately from module definitions.

    Args:
        cop: (Value) COP tree to fold
        namespace: (dict) Namespace mapping names to Callable
        interp: Interpreter instance

    Returns:
        (Value) Folded COP tree (same object if nothing changed)
    """
    return _eval_pure_in_cop(cop, namespace, interp)


# ---------------------------------------------------------------------------
# Namespace-based pure callable lookup
# ---------------------------------------------------------------------------

def _resolve_pure_callable(qualified, namespace, input_value):
    """Find the best matching pure callable for the given qualified name(s).

    For a single qualified name (str), returns that callable directly.
    For a list of qualified names (overloads), morphs the input against
    each callable's input_shape and returns the highest-scoring match.

    Args:
        qualified: (str | list) Qualified name(s) of candidate callables
        namespace: (dict) Module namespace mapping names to Callable
        input_value: (Value) Current piped input for dispatch scoring

    Returns:
        (Block | InternalCallable | None) Best matching pure callable
    """
    if isinstance(qualified, str):
        defn = _find_definition(qualified, namespace)
        if defn is None or not _is_pure_definition(defn):
            return None
        return _get_callable(defn)

    # Multiple overloads — dispatch by morphing input against each
    best = None
    best_score = None
    for name in qualified:
        defn = _find_definition(name, namespace)
        if defn is None or not _is_pure_definition(defn):
            continue
        callable_obj = _get_callable(defn)
        if callable_obj is None:
            continue
        shape = getattr(callable_obj, "input_shape", None) or comp.shape_any
        try:
            result = comp.morph(input_value, shape, None)
            if not result.failure_reason:
                if best_score is None or result.score > best_score:
                    best_score = result.score
                    best = callable_obj
        except Exception:
            pass
    return best


def _find_definition(qualified, namespace):
    """Look up a Definition by its qualified name in the namespace.

    Args:
        qualified: (str) Full qualified name (e.g. "reverse.i001")
        namespace: (dict) Module namespace

    Returns:
        (Definition | None)
    """
    entry = namespace.get(qualified)
    if entry is None:
        return None
    if isinstance(entry, comp.Callable):
        for defn in entry.entries:
            if defn.qualified == qualified:
                return defn
        return None
    if hasattr(entry, "qualified") and entry.qualified == qualified:
        return entry
    return None


def _is_pure_definition(defn):
    """Check if a Definition represents a pure callable.

    A definition is pure if:
    - It was declared with !pure (defn.pure == True), OR
    - Its value is an InternalCallable with pure=True, OR
    - Its value is a Block with pure=True

    Args:
        defn: (Definition) The definition to check

    Returns:
        (bool)
    """
    if defn.pure:
        return True
    if defn.value is None:
        return False
    data = defn.value.data
    if isinstance(data, comp.InternalCallable):
        return data.pure
    if isinstance(data, comp.Callable):
        block = data.scalar()
        if block is not None:
            return block.pure
    return False


def _get_callable(defn):
    """Extract Block or InternalCallable from a Definition's value.

    Args:
        defn: (Definition) The definition

    Returns:
        (Block | InternalCallable | None)
    """
    if defn.value is None:
        return None
    data = defn.value.data
    if isinstance(data, comp.Callable):
        block = data.scalar()
        if block is not None:
            return block
    if isinstance(data, comp.InternalCallable):
        return data
    return None


# ---------------------------------------------------------------------------
# COP tree walking and evaluation
# ---------------------------------------------------------------------------

def _eval_pure_in_cop(cop, namespace, interp, _as_stage=False):
    """Walk COP tree and evaluate pure function invocations.

    Processes bottom-up so that inner pure calls are folded before
    checking outer nodes.

    Args:
        cop: COP tree to process
        namespace: (dict) Module namespace for pure callable lookup
        interp: Interpreter for execution
        _as_stage: If True, this node is a pipeline stage or callable child of
            a binding — skip top-level reference/binding folding since the
            piped input comes from the pipeline context, not from nil.

    Returns:
        Modified COP tree with pure invokes replaced by value.constant nodes
    """
    tag = comp.cop_tag(cop)

    # Pipelines are handled as a special unit (stage-by-stage evaluation)
    if tag == "value.pipeline":
        return _eval_pure_pipeline(cop, namespace, interp)

    # Recurse into children first (bottom-up).
    # For value.binding, kid[0] is the callable — mark it as a stage so that
    # it won't be folded as a standalone reference (it receives piped input).
    kids = comp.cop_kids(cop)
    new_kids = []
    changed = False
    for i, kid in enumerate(kids):
        kid_as_stage = tag == "value.binding" and i == 0
        res = _eval_pure_in_cop(kid, namespace, interp, _as_stage=kid_as_stage)
        new_kids.append(res)
        if res is not kid:
            changed = True

    if changed:
        cop = comp.cop_rebuild(cop, new_kids)
        kids = new_kids

    if not _as_stage:
        # Reference to a pure function — implicit callables (TryInvoke semantics)
        if tag in ("value.reference", "value.namespace"):
            result = _try_eval_reference(cop, namespace, interp)
            if result is not None:
                return result

        # value.binding{pure_ref, const_args} — explicit call with arguments
        if tag == "value.binding":
            result = _try_eval_binding(cop, kids, namespace, interp)
            if result is not None:
                return result

    return cop


def _try_eval_reference(cop, namespace, interp):
    """Try to evaluate a reference to a pure function as a callable.

    Handles both value.reference and value.namespace nodes, and both
    single (str) and overloaded (list) qualified names.  Invoked with
    empty input and empty args (TryInvoke semantics).

    Returns:
        value.constant COP if evaluable, None otherwise
    """
    qualified = cop.to_python("qualified")
    if not isinstance(qualified, (str, list)):
        return None

    nil_val = comp.Value.from_python(comp.tag_nil)
    empty = comp.Value.from_python({})
    block = _resolve_pure_callable(qualified, namespace, nil_val)
    if block is None:
        return None

    try:
        result = _execute_pure_block(block, nil_val, empty, interp)
        return _make_constant(cop, result)
    except Exception:
        return None


def _try_eval_binding(cop, kids, namespace, interp):
    """Try to evaluate value.binding if callable is pure and args are constant.

    Handles both value.reference and value.namespace callables, and both
    single and overloaded qualified names.

    value.binding kids: [0] = callable expression, [1] = args struct.

    Returns:
        value.constant COP if evaluable, None otherwise
    """
    if len(kids) < 2:
        return None

    callable_cop = kids[0]
    args_cop = kids[1]

    if comp.cop_tag(callable_cop) not in ("value.reference", "value.namespace"):
        return None

    qualified = callable_cop.to_python("qualified")
    if not isinstance(qualified, (str, list)):
        return None

    # Args must be a compile-time constant (including all-constant structs)
    args_const = _eval_const_cop(args_cop, interp)
    if args_const is None:
        return None

    # Check block arg purity: if args contain callable values, they must be pure
    if not _args_are_pure(args_const):
        return None

    nil_val = comp.Value.from_python(comp.tag_nil)
    block = _resolve_pure_callable(qualified, namespace, nil_val)
    if block is None:
        return None

    try:
        result = _execute_pure_block(block, nil_val, args_const, interp)
        return _make_constant(cop, result)
    except Exception:
        return None


def _eval_pure_pipeline(cop, namespace, interp):
    """Evaluate leading pure stages of a pipeline at compile time.

    Evaluates pipeline stages left-to-right.  Each stage feeds its result
    as piped input into the next.  Stops at the first non-pure stage or
    non-constant intermediate value.

    Pipeline stage formats:
    - value.reference{pure_func}: function with piped input, no explicit args
    - value.binding{reference{pure_func}, const_args}: function with piped input + args

    Args:
        cop: value.pipeline COP node
        namespace: (dict) Module namespace for pure callable lookup
        interp: Interpreter

    Returns:
        Modified pipeline COP (possibly reduced to a constant or shorter pipeline)
    """
    stages = list(comp.cop_kids(cop))
    if not stages:
        return cop

    # Recurse into first stage (the initial value being piped)
    first = _eval_pure_in_cop(stages[0], namespace, interp)
    current_value = _get_constant(first)

    if current_value is None:
        # First stage not constant — still recurse remaining stages for sub-pures
        new_stages = [first]
        changed = first is not stages[0]
        for stage in stages[1:]:
            res = _eval_pure_in_cop(stage, namespace, interp, _as_stage=True)
            new_stages.append(res)
            if res is not stage:
                changed = True
        if changed:
            return comp.cop_rebuild(cop, new_stages)
        return cop

    # Try to evaluate pure stages
    evaluated_up_to = 0
    for i, stage in enumerate(stages[1:], 1):
        qualified, args_cop = _get_pipeline_stage_parts(stage)
        if qualified is None:
            break
        block = _resolve_pure_callable(qualified, namespace, current_value)
        if block is None:
            break

        # Fold args for this stage (including all-constant structs)
        stage_evaled = _eval_pure_in_cop(args_cop, namespace, interp) if args_cop is not None else None
        args_value = _eval_const_cop(stage_evaled, interp) if stage_evaled is not None else comp.Value.from_python({})
        if args_cop is not None and args_value is None:
            break  # Args not constant

        # Check block arg purity
        if not _args_are_pure(args_value):
            break

        try:
            current_value = _execute_pure_block(block, current_value, args_value, interp)
            evaluated_up_to = i
        except Exception:
            break

    # Build the resulting COP
    if evaluated_up_to == len(stages) - 1:
        # All stages evaluated — return constant
        return _make_constant(cop, current_value)

    if evaluated_up_to > 0:
        # Some stages evaluated — replace evaluated prefix with constant
        const_cop = _make_constant(stages[0], current_value)
        remaining = [const_cop]
        for stage in stages[evaluated_up_to + 1:]:
            remaining.append(_eval_pure_in_cop(stage, namespace, interp, _as_stage=True))
        if len(remaining) == 1:
            return remaining[0]
        return comp.cop_rebuild(cop, remaining)

    # Nothing evaluated — return with recursed children
    new_stages = [first]
    changed = first is not stages[0]
    for stage in stages[1:]:
        res = _eval_pure_in_cop(stage, namespace, interp, _as_stage=True)
        new_stages.append(res)
        if res is not stage:
            changed = True
    if changed:
        return comp.cop_rebuild(cop, new_stages)
    return cop


def _get_pipeline_stage_parts(stage_cop):
    """Extract the qualified name(s) and args COP from a pipeline stage.

    Pipeline stages can be:
    - value.reference / value.namespace: piped input only, no args
    - value.binding{reference/namespace, args}: piped input + args

    qualified may be a str (single overload) or list (multiple overloads).
    Caller uses _resolve_pure_callable to resolve.

    Returns:
        (str | list | None, args_cop or None)
    """
    tag = comp.cop_tag(stage_cop)
    kids = comp.cop_kids(stage_cop)

    if tag in ("value.reference", "value.namespace"):
        qualified = stage_cop.to_python("qualified")
        if not isinstance(qualified, (str, list)):
            return None, None
        return qualified, None

    if tag == "value.binding" and len(kids) >= 2:
        callable_cop = kids[0]
        args_cop = kids[1]
        if comp.cop_tag(callable_cop) in ("value.reference", "value.namespace"):
            qualified = callable_cop.to_python("qualified")
            if isinstance(qualified, (str, list)):
                return qualified, args_cop

    return None, None


# ---------------------------------------------------------------------------
# Block arg purity check
# ---------------------------------------------------------------------------

def _args_are_pure(args_value):
    """Check that any callable values in args are pure.

    Args:
        args_value: (Value) The argument struct

    Returns:
        (bool) True if all callable args are pure (or there are no callable args)
    """
    if not isinstance(args_value.data, dict):
        if isinstance(args_value.data, comp.Callable):
            block = args_value.data.scalar()
            return block.pure if block is not None else True
        if isinstance(args_value.data, comp.InternalCallable):
            return args_value.data.pure
        return True

    # Struct — check all fields
    for key, val in args_value.data.items():
        if isinstance(val.data, comp.Callable):
            block = val.data.scalar()
            if block is not None and not block.pure:
                return False
        elif isinstance(val.data, comp.InternalCallable):
            if not val.data.pure:
                return False
    return True


# ---------------------------------------------------------------------------
# Execution and constant helpers
# ---------------------------------------------------------------------------

def _execute_pure_block(block, input_value, args_value, interp):
    """Execute a pure block or internal callable with given piped input and args.

    Handles both user-defined Block objects (compiled from !pure definitions)
    and InternalCallable objects (Python builtins marked pure=True).

    Args:
        block: (Block | InternalCallable) Compiled block or builtin callable
        input_value: Piped input Value (empty struct for no piped input)
        args_value: Arguments Value (empty struct for no args)
        interp: Interpreter

    Returns:
        (Value) Result value

    Raises:
        RuntimeError: If a Block has no compiled body instructions
    """
    if isinstance(block, comp.InternalCallable):
        callable = comp.Callable(block.name)
        callable.add(block)
        block_val = comp.Value(callable)
        frame = comp.ExecutionFrame(env={}, interp=interp)
        return frame.invoke_block(block_val, args_value, piped=input_value)

    callable = comp.Callable(block.qualified)
    callable.add(block)
    block_val = comp.Value(callable)
    frame = comp.ExecutionFrame(env={}, interp=interp)

    if block.body_instructions is None:
        raise RuntimeError(f"Block {block.qualified!r} has no compiled body instructions")

    return frame.invoke_block(block_val, args_value, piped=input_value)


def _make_constant(original, value):
    """Create a value.constant COP node, preserving position info from original."""
    fields = {"value": value}
    try:
        pos = original.field("pos")
        if pos is not None:
            fields["pos"] = pos
    except (KeyError, AttributeError):
        pass
    return comp.create_cop("value.constant", [], **fields)


def _get_constant(cop):
    """Extract the Value from a value.constant COP node, or None."""
    if comp.cop_tag(cop) == "value.constant":
        try:
            return cop.field("value")
        except (KeyError, AttributeError):
            pass
    return None


_NON_CONST_TAGS = frozenset({
    "value.identifier", "value.reference", "value.namespace", "value.local",
    "value.undefined",
})


def _is_all_constant(cop):
    """Return True if the COP tree has no runtime references (safe to evaluate at compile time)."""
    tag = comp.cop_tag(cop)
    if tag == "value.constant":
        return True
    if tag in _NON_CONST_TAGS:
        return False
    return all(_is_all_constant(kid) for kid in comp.cop_kids(cop))


def _eval_const_cop(cop, interp):
    """Evaluate a COP to a Value if it contains only compile-time constants.

    Handles value.constant directly, and for all-constant composite nodes
    (e.g. a struct whose fields have already been folded to constants),
    generates and executes the instructions to produce the Value.

    Returns:
        Value if successful, None otherwise.
    """
    v = _get_constant(cop)
    if v is not None:
        return v
    if not _is_all_constant(cop):
        return None
    try:
        instructions = comp.generate_code_for_definition(cop)
        if not instructions:
            return None
        frame = comp.ExecutionFrame(env={}, interp=interp)
        return frame.run(instructions)
    except Exception:
        return None
