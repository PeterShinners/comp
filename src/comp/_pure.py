"""Pure function evaluation at compile time.

This module handles evaluating pure functions during compilation:
- Identify pure block definitions (marked with !pure)
- Build bytecode for pure blocks
- Walk definition COPs looking for invocations of pure functions
- Replace pure invocations with constant result nodes when arguments
  are also constants

The COP nodes handled:
- value.reference to a pure function: implicit nullary call (TryInvoke semantics)
- value.binding{pure_ref, const_args}: explicit call with constant arguments
- value.pipeline: evaluate leading pure stages with constant inputs
"""

__all__ = [
    "evaluate_pure_definitions",
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

        # The instruction list for a function definition is [BuildBlock, TryInvoke].
        # Execute just BuildBlock (instructions[:-1]) to get the Block object
        # without invoking it (TryInvoke would invoke with empty args, which fails
        # for parameterised functions).
        try:
            build_only = instructions[:-1]
            block_val = interp.execute(build_only, {})
            if block_val and isinstance(block_val.data, comp.Block):
                pure_blocks[name] = block_val.data
        except Exception:
            pass

    return pure_blocks


def _eval_pure_in_cop(cop, pure_blocks, interp):
    """Walk COP tree and evaluate pure function invocations.

    Processes bottom-up so that inner pure calls are folded before
    checking outer nodes.

    Args:
        cop: COP tree to process
        pure_blocks: Dict {qualified_name: Block} of compiled pure blocks
        interp: Interpreter for execution

    Returns:
        Modified COP tree with pure invokes replaced by value.constant nodes
    """
    tag = comp.cop_tag(cop)

    # Pipelines are handled as a special unit (stage-by-stage evaluation)
    if tag == "value.pipeline":
        return _eval_pure_pipeline(cop, pure_blocks, interp)

    # Recurse into children first (bottom-up)
    kids = comp.cop_kids(cop)
    new_kids = []
    changed = False
    for kid in kids:
        res = _eval_pure_in_cop(kid, pure_blocks, interp)
        new_kids.append(res)
        if res is not kid:
            changed = True

    if changed:
        cop = comp.cop_rebuild(cop, new_kids)
        kids = new_kids

    # value.reference to a pure function — implicit nullary invocation
    if tag == "value.reference":
        result = _try_eval_reference(cop, pure_blocks, interp)
        if result is not None:
            return result

    # value.binding{pure_ref, const_args} — explicit call with arguments
    if tag == "value.binding":
        result = _try_eval_binding(cop, kids, pure_blocks, interp)
        if result is not None:
            return result

    return cop


def _try_eval_reference(cop, pure_blocks, interp):
    """Try to evaluate a reference to a pure function as a nullary call.

    A value.reference to a pure function has TryInvoke semantics: it is
    invoked with empty input and empty args.

    Returns:
        value.constant COP if evaluable, None otherwise
    """
    qualified = cop.to_python("qualified")
    if not isinstance(qualified, str):
        return None

    block = pure_blocks.get(qualified)
    if block is None:
        return None

    empty = comp.Value.from_python({})
    try:
        result = _execute_pure_block(block, empty, empty, interp)
        return _make_constant(cop, result)
    except Exception:
        return None


def _try_eval_binding(cop, kids, pure_blocks, interp):
    """Try to evaluate value.binding if callable is pure and args are constant.

    value.binding kids: [0] = callable expression, [1] = args struct.

    Returns:
        value.constant COP if evaluable, None otherwise
    """
    if len(kids) < 2:
        return None

    callable_cop = kids[0]
    args_cop = kids[1]

    # Callable must be a reference to a pure function
    if comp.cop_tag(callable_cop) != "value.reference":
        return None

    qualified = callable_cop.to_python("qualified")
    if not isinstance(qualified, str):
        return None

    block = pure_blocks.get(qualified)
    if block is None:
        return None

    # Args must be a compile-time constant
    args_const = _get_constant(args_cop)
    if args_const is None:
        return None

    empty = comp.Value.from_python({})
    try:
        result = _execute_pure_block(block, empty, args_const, interp)
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
            res = _eval_pure_in_cop(stage, pure_blocks, interp)
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
        if qualified is None or qualified not in pure_blocks:
            # Stage not a pure function reference — stop
            break
        block = pure_blocks[qualified]

        # Fold args for this stage
        stage_evaled = _eval_pure_in_cop(args_cop, pure_blocks, interp) if args_cop is not None else None
        args_value = _get_constant(stage_evaled) if stage_evaled is not None else comp.Value.from_python({})
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
            remaining.append(_eval_pure_in_cop(stage, pure_blocks, interp))
        if len(remaining) == 1:
            return remaining[0]
        return comp.cop_rebuild(cop, remaining)

    # Nothing evaluated — return with recursed children
    new_stages = [first]
    changed = first is not stages[0]
    for stage in stages[1:]:
        res = _eval_pure_in_cop(stage, pure_blocks, interp)
        new_stages.append(res)
        if res is not stage:
            changed = True
    if changed:
        return comp.cop_rebuild(cop, new_stages)
    return cop


def _get_pipeline_stage_parts(stage_cop):
    """Extract the Block and args COP from a pipeline stage.

    Pipeline stages can be:
    - value.reference{pure_func}: piped input only, no args  → (block, None)
    - value.binding{reference{pure_func}, args}: piped + args → (block, args_cop)

    Returns:
        (Block or None, args_cop or None)
    """
    tag = comp.cop_tag(stage_cop)
    kids = comp.cop_kids(stage_cop)

    if tag == "value.reference":
        qualified = stage_cop.to_python("qualified")
        if not isinstance(qualified, str):
            return None, None
        # Return the block name; caller will look it up
        return qualified, None

    if tag == "value.binding" and len(kids) >= 2:
        callable_cop = kids[0]
        args_cop = kids[1]
        if comp.cop_tag(callable_cop) == "value.reference":
            qualified = callable_cop.to_python("qualified")
            if isinstance(qualified, str):
                return qualified, args_cop

    return None, None


def _execute_pure_block(block, input_value, args_value, interp):
    """Execute a pure block with the given piped input and argument values.

    Sets up the parameter environment from the block's signature and
    runs the body instructions.

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

    env = {}
    if block.input_name and block.arg_name:
        env[block.input_name] = input_value
        env[block.arg_name] = args_value
    elif block.input_name:
        # Single param: gets piped input if present, otherwise args
        if input_value.data:
            env[block.input_name] = input_value
        else:
            env[block.input_name] = args_value

    frame = comp.ExecutionFrame(env=env, interp=interp)
    return frame.run(block.body_instructions)


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
