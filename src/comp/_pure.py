"""Pure function evaluation at compile time.

This module handles evaluating pure functions during compilation:
- Identify pure block definitions (marked with !pure)
- Build bytecode for pure blocks
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


def evaluate_pure_definitions(definitions, interp):
    """Evaluate pure function invokes at compile time.

    Two-phase process:
    1. Build Block bytecode for all !pure definitions
    2. Walk each definition's COP tree and evaluate pure invocations
       whose arguments are compile-time constants

    Args:
        definitions: Dict {qualified_name: Definition} to process
        interp: Interpreter instance for execution

    Returns:
        dict: The definitions dictionary (for chaining)

    Side effects:
        - Compiles bytecode for pure block definitions
        - Replaces pure invoke COPs with value.constant COPs
    """
    # Phase 1: Compile all pure definitions to get their Block objects
    pure_blocks = _compile_pure_blocks(definitions, interp)

    if not pure_blocks:
        return definitions

    # Phase 2: Walk each definition and evaluate pure invokes
    for name, defn in definitions.items():
        if defn.resolved_cop is None:
            continue
        new_cop = _eval_pure_in_cop(defn.resolved_cop, pure_blocks, interp)
        if new_cop is not defn.resolved_cop:
            defn.resolved_cop = new_cop

    return definitions


def fold_pure_cop(cop, definitions, interp):
    """Apply pure folding to a single COP tree using compiled pure blocks.

    Used for COP trees that are not part of the definitions dict, such as
    startup blocks, which are obtained separately from module definitions.

    Args:
        cop: (Value) COP tree to fold
        definitions: Dict {qualified_name: Definition} providing pure blocks
        interp: Interpreter instance

    Returns:
        (Value) Folded COP tree (same object if nothing changed)
    """
    pure_blocks = _compile_pure_blocks(definitions, interp)
    if not pure_blocks:
        return cop
    return _eval_pure_in_cop(cop, pure_blocks, interp)


def _compile_pure_blocks(definitions, interp):
    """Find !pure definitions and compile their Block bytecode.

    For each pure definition, generates the definition instructions and
    executes just the BuildBlock instruction (not the final TryInvoke)
    to obtain the Block object with its body_instructions populated.

    Args:
        definitions: Dict of definitions
        interp: Interpreter instance

    Returns:
        Dict {qualified_name: Block} of pure blocks with compiled bytecode
    """
    pure_blocks = {}

    for name, defn in definitions.items():
        if not defn.pure:
            continue
        if defn.resolved_cop is None:
            continue

        try:
            instructions = comp.generate_code_for_definition(defn.resolved_cop)
        except Exception:
            continue

        if not instructions:
            continue

        # function.define/shape.define nodes do NOT get a trailing TryInvoke —
        # the Block/Shape is the value directly.  All other definitions end with
        # TryInvoke, which we skip to avoid invoking with empty args (which would
        # fail for parameterised functions).  Mirror the _no_invoke_tags logic in
        # _codegen.py to decide whether to strip the last instruction.
        _no_invoke_tags = {"function.define", "shape.define", "shape.union"}
        if comp.cop_tag(defn.resolved_cop) in _no_invoke_tags:
            build_only = instructions          # already just BuildBlock
        else:
            build_only = instructions[:-1]    # strip trailing TryInvoke
        try:
            block_val = interp.execute(build_only, {})
            if block_val and isinstance(block_val.data, comp.Block):
                pure_blocks[name] = block_val.data
        except Exception:
            pass

    return pure_blocks


def _eval_pure_in_cop(cop, pure_blocks, interp, _as_stage=False):
    """Walk COP tree and evaluate pure function invocations.

    Processes bottom-up so that inner pure calls are folded before
    checking outer nodes.

    Args:
        cop: COP tree to process
        pure_blocks: Dict {qualified_name: Block} of compiled pure blocks
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
        return _eval_pure_pipeline(cop, pure_blocks, interp)

    # Recurse into children first (bottom-up).
    # For value.binding, kid[0] is the callable — mark it as a stage so that
    # it won't be folded as a standalone reference (it receives piped input).
    kids = comp.cop_kids(cop)
    new_kids = []
    changed = False
    for i, kid in enumerate(kids):
        kid_as_stage = tag == "value.binding" and i == 0
        res = _eval_pure_in_cop(kid, pure_blocks, interp, _as_stage=kid_as_stage)
        new_kids.append(res)
        if res is not kid:
            changed = True

    if changed:
        cop = comp.cop_rebuild(cop, new_kids)
        kids = new_kids

    if not _as_stage:
        # Reference to a pure function — implicit callables (TryInvoke semantics)
        if tag in ("value.reference", "value.namespace"):
            result = _try_eval_reference(cop, pure_blocks, interp)
            if result is not None:
                return result

        # value.binding{pure_ref, const_args} — explicit call with arguments
        if tag == "value.binding":
            result = _try_eval_binding(cop, kids, pure_blocks, interp)
            if result is not None:
                return result

    return cop


def _pick_pure_block(qualified, pure_blocks, input_value):
    """Pick the best matching pure Block for the given input value.

    For a single qualified name (str), returns that block directly.
    For a list of qualified names (overloads), morphs the input against
    each block's input_shape and returns the highest-scoring match.

    Args:
        qualified: (str | list) Qualified name(s) of candidate blocks
        pure_blocks: Dict {qualified_name: Block}
        input_value: (Value) Current piped input for dispatch scoring

    Returns:
        (Block | None) Best matching block, or None
    """
    if isinstance(qualified, str):
        return pure_blocks.get(qualified)

    # Multiple overloads — dispatch by morphing input against each block's shape
    best_block = None
    best_score = None
    for name in qualified:
        block = pure_blocks.get(name)
        if block is None:
            continue
        shape = block.input_shape if block.input_shape is not None else comp.shape_any
        try:
            result = comp.morph(input_value, shape, None)
            if not result.failure_reason:
                if best_score is None or result.score > best_score:
                    best_score = result.score
                    best_block = block
        except Exception:
            pass
    return best_block


def _try_eval_reference(cop, pure_blocks, interp):
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
    block = _pick_pure_block(qualified, pure_blocks, nil_val)
    if block is None:
        return None

    try:
        result = _execute_pure_block(block, nil_val, empty, interp)
        return _make_constant(cop, result)
    except Exception:
        return None


def _try_eval_binding(cop, kids, pure_blocks, interp):
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

    nil_val = comp.Value.from_python(comp.tag_nil)
    block = _pick_pure_block(qualified, pure_blocks, nil_val)
    if block is None:
        return None

    try:
        result = _execute_pure_block(block, nil_val, args_const, interp)
        return _make_constant(cop, result)
    except Exception:
        return None


def _eval_pure_pipeline(cop, pure_blocks, interp):
    """Evaluate leading pure stages of a pipeline at compile time.

    Evaluates pipeline stages left-to-right.  Each stage feeds its result
    as piped input into the next.  Stops at the first non-pure stage or
    non-constant intermediate value.

    Pipeline stage formats:
    - value.reference{pure_func}: function with piped input, no explicit args
    - value.binding{reference{pure_func}, const_args}: function with piped input + args

    Args:
        cop: value.pipeline COP node
        pure_blocks: Dict of compiled pure blocks
        interp: Interpreter

    Returns:
        Modified pipeline COP (possibly reduced to a constant or shorter pipeline)
    """
    stages = list(comp.cop_kids(cop))
    if not stages:
        return cop

    # Recurse into first stage (the initial value being piped)
    first = _eval_pure_in_cop(stages[0], pure_blocks, interp)
    current_value = _get_constant(first)

    if current_value is None:
        # First stage not constant — still recurse remaining stages for sub-pures
        new_stages = [first]
        changed = first is not stages[0]
        for stage in stages[1:]:
            res = _eval_pure_in_cop(stage, pure_blocks, interp, _as_stage=True)
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
        block = _pick_pure_block(qualified, pure_blocks, current_value)
        if block is None:
            break

        # Fold args for this stage (including all-constant structs)
        stage_evaled = _eval_pure_in_cop(args_cop, pure_blocks, interp) if args_cop is not None else None
        args_value = _eval_const_cop(stage_evaled, interp) if stage_evaled is not None else comp.Value.from_python({})
        if args_cop is not None and args_value is None:
            break  # Args not constant

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
            remaining.append(_eval_pure_in_cop(stage, pure_blocks, interp, _as_stage=True))
        if len(remaining) == 1:
            return remaining[0]
        return comp.cop_rebuild(cop, remaining)

    # Nothing evaluated — return with recursed children
    new_stages = [first]
    changed = first is not stages[0]
    for stage in stages[1:]:
        res = _eval_pure_in_cop(stage, pure_blocks, interp, _as_stage=True)
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
    Caller uses _pick_pure_block to resolve.

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


def _execute_pure_block(block, input_value, args_value, interp):
    """Execute a pure block with the given piped input and argument values.

    Args:
        block: Block object with compiled body_instructions
        input_value: Piped input Value (empty struct for no piped input)
        args_value: Arguments Value (empty struct for no args)
        interp: Interpreter

    Returns:
        Result Value

    Raises:
        RuntimeError: If body_instructions is not compiled
    """
    if block.body_instructions is None:
        raise RuntimeError(f"Block {block.qualified!r} has no compiled body instructions")

    block_val = comp.Value(block)
    frame = comp.ExecutionFrame(env={}, interp=interp)
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
