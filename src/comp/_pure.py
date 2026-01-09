"""Pure function evaluation at compile time.

This module handles evaluating pure functions during compilation:
- Identify pure block definitions
- Build bytecode for pure blocks
- Evaluate pure invokes with constant arguments
- Replace invoke COP nodes with constant results
"""

__all__ = [
    "evaluate_pure_definitions",
]

import comp


def evaluate_pure_definitions(definitions, namespace, interp):
    """Evaluate pure function invokes at compile time.

    This is a two-phase process:
    1. Build bytecode for all pure block definitions
    2. Walk each definition's COP tree and evaluate pure invokes

    For pipelines, leading pure stages are evaluated until the first
    non-pure stage is encountered.

    Args:
        definitions: Dict {qualified_name: Definition} to process
        namespace: Namespace dict {name: DefinitionSet}
        interp: Interpreter instance for execution

    Returns:
        dict: The definitions dictionary (for chaining)

    Side effects:
        - Compiles bytecode for pure block definitions
        - Replaces pure invoke COPs with value.constant COPs
    """
    # Phase 1: Identify and compile pure blocks
    pure_blocks = _compile_pure_blocks(definitions, namespace)

    # Phase 2: Walk each definition and evaluate pure invokes
    for name, defn in definitions.items():
        if defn.resolved_cop is None:
            continue
        defn.resolved_cop = _eval_pure_in_cop(defn.resolved_cop, pure_blocks, interp)

    return definitions


def _compile_pure_blocks(definitions, namespace):
    """Find pure block definitions and compile their bytecode.

    Args:
        definitions: Dict of definitions
        namespace: Namespace dict

    Returns:
        Dict {qualified_name: Block} of pure blocks with compiled bytecode
    """
    pure_blocks = {}

    for name, defn in definitions.items():
        if defn.shape != comp.shape_block:
            continue

        # Ensure definition is resolved and folded to get Block value
        if defn.value is None:
            if defn.resolved_cop is None:
                defn.resolved_cop = comp.cop_resolve(defn.original_cop, namespace)
            # Use fold_definition to create Block object
            comp._module.fold_definition(defn)

        if defn.value is None:
            continue

        block = defn.value.data
        if not isinstance(block, comp.Block):
            continue

        if not block.pure:
            continue

        # Compile bytecode for this pure block
        if block.body_instructions is None:
            # Generate instructions for the block definition
            block_cop = defn.resolved_cop or defn.original_cop
            instructions = comp.generate_code_for_definition(block_cop)
            # The instructions for a block definition create a BuildBlock
            # We need to extract the body instructions from it
            if instructions and len(instructions) == 1:
                build_instr = instructions[0]
                if hasattr(build_instr, "body_instructions"):
                    block.body_instructions = build_instr.body_instructions
                    block.closure_env = {}
                    # Extract signature for parameter binding
                    if hasattr(build_instr, "signature_cop"):
                        block.signature_cop = build_instr.signature_cop

        if block.body_instructions is not None:
            pure_blocks[name] = block

    return pure_blocks


def _eval_pure_in_cop(cop, pure_blocks, interp):
    """Walk COP tree and evaluate pure invokes.

    Args:
        cop: COP tree to process
        pure_blocks: Dict of pure blocks with compiled bytecode
        interp: Interpreter for execution

    Returns:
        Modified COP tree with pure invokes replaced by constants
    """
    tag = comp.cop_tag(cop)

    # Handle pipelines specially - evaluate leading pure stages
    if tag == "value.pipeline":
        return _eval_pure_pipeline(cop, pure_blocks, interp)

    # Handle invoke - check if it's a pure call with constant args
    if tag == "value.invoke":
        result = _try_eval_invoke(cop, pure_blocks, interp)
        if result is not None:
            return result

    # Recursively process children
    kids = []
    changed = False
    for kid in comp.cop_kids(cop):
        res = _eval_pure_in_cop(kid, pure_blocks, interp)
        if res is not kid:
            kids.append(res)
            changed = True
        else:
            kids.append(kid)

    if changed:
        # Preserve original fields (like op, value, name, etc.) when rebuilding
        return comp.cop_rebuild(cop, kids)
    return cop


def _eval_pure_pipeline(cop, pure_blocks, interp):
    """Evaluate leading pure stages of a pipeline.

    Evaluates stages from left to right until hitting a non-pure stage.
    The accumulated value becomes a constant that feeds the remaining stages.

    Args:
        cop: value.pipeline COP node
        pure_blocks: Dict of pure blocks
        interp: Interpreter

    Returns:
        Modified pipeline COP (possibly reduced to constant)
    """
    stages = list(comp.cop_kids(cop))
    if not stages:
        return cop

    # First stage is the initial value - fold and try to get constant
    first = stages[0]
    first_folded = comp.cop_fold(_eval_pure_in_cop(first, pure_blocks, interp))
    current_value = _get_constant(first_folded)

    if current_value is None:
        # First stage not constant, can't evaluate any pure stages
        # Still recurse into remaining stages
        kids = [first_folded]
        changed = first_folded is not first
        for stage in stages[1:]:
            res = _eval_pure_in_cop(stage, pure_blocks, interp)
            kids.append(res)
            if res is not stage:
                changed = True
        if changed:
            return comp.create_cop("value.pipeline", kids)
        return cop

    # Try to evaluate pure stages
    evaluated_up_to = 0
    for i, stage in enumerate(stages[1:], 1):
        # Check if this is a pure invoke
        block, args_cop = _get_invoke_parts(stage)
        if block is None or not _is_pure_block(block, pure_blocks):
            break

        # Check if args are constant (fold to ensure literals become constants)
        args_folded = comp.cop_fold(_eval_pure_in_cop(args_cop, pure_blocks, interp))
        args_value = _get_constant(args_folded)
        if args_value is None:
            break

        # Execute the pure function
        try:
            result = _execute_pure_block(block, pure_blocks, current_value, args_value, interp)
            current_value = result
            evaluated_up_to = i
        except Exception:
            # Execution failed, stop here
            break

    # Build result
    if evaluated_up_to == len(stages) - 1:
        # All stages evaluated - return constant
        return _make_constant(cop, current_value)

    if evaluated_up_to > 0:
        # Some stages evaluated - build reduced pipeline
        const_cop = _make_constant(stages[0], current_value)
        remaining = [const_cop]
        for stage in stages[evaluated_up_to + 1:]:
            remaining.append(_eval_pure_in_cop(stage, pure_blocks, interp))
        if len(remaining) == 1:
            return remaining[0]
        return comp.create_cop("value.pipeline", remaining)

    # Nothing evaluated, return with recursed children
    kids = [first_folded]
    changed = first_folded is not first
    for stage in stages[1:]:
        res = _eval_pure_in_cop(stage, pure_blocks, interp)
        kids.append(res)
        if res is not stage:
            changed = True
    if changed:
        return comp.create_cop("value.pipeline", kids)
    return cop


def _try_eval_invoke(cop, pure_blocks, interp):
    """Try to evaluate an invoke if it's pure with constant args.

    Args:
        cop: value.invoke COP node
        pure_blocks: Dict of pure blocks
        interp: Interpreter

    Returns:
        value.constant COP if evaluable, None otherwise
    """
    kids = list(comp.cop_kids(cop))
    if len(kids) < 2:
        return None

    callable_cop = kids[0]
    args_cop = kids[1]

    # Get the block being called
    block = _resolve_to_block(callable_cop, pure_blocks)
    if block is None or not block.pure:
        return None

    # Check if args are constant
    args_folded = comp.cop_fold(args_cop)
    args_value = _get_constant(args_folded)
    if args_value is None:
        return None

    # No piped input for regular invoke
    input_value = comp.Value.from_python({})

    # Execute
    try:
        result = _execute_pure_block(block, pure_blocks, input_value, args_value, interp)
        return _make_constant(cop, result)
    except Exception:
        return None


def _get_invoke_parts(cop):
    """Extract callable and args from an invoke COP.

    Returns:
        (Block or None, args_cop) tuple
    """
    tag = comp.cop_tag(cop)
    if tag != "value.invoke":
        return None, None

    kids = list(comp.cop_kids(cop))
    if len(kids) < 2:
        return None, None

    callable_cop = kids[0]
    args_cop = kids[1]

    # Try to resolve to a block
    if comp.cop_tag(callable_cop) == "value.reference":
        try:
            qualified = callable_cop.field("qualified").data
            # We don't have the block yet, just return the name
            return qualified, args_cop
        except (KeyError, AttributeError):
            pass

    return None, None


def _is_pure_block(block_name, pure_blocks):
    """Check if a block name refers to a pure block."""
    if isinstance(block_name, str):
        return block_name in pure_blocks
    if isinstance(block_name, comp.Block):
        return block_name.pure
    return False


def _resolve_to_block(cop, pure_blocks):
    """Resolve a COP to a Block if it's a pure block reference."""
    tag = comp.cop_tag(cop)
    if tag == "value.reference":
        try:
            qualified = cop.field("qualified").data
            return pure_blocks.get(qualified)
        except (KeyError, AttributeError):
            pass
    return None


def _execute_pure_block(block, pure_blocks, input_value, args_value, interp):
    """Execute a pure block with given input and args.

    Args:
        block: Block object or qualified name
        pure_blocks: Dict of pure blocks
        input_value: Piped input Value
        args_value: Arguments Value
        interp: Interpreter

    Returns:
        Result Value
    """
    if isinstance(block, str):
        block = pure_blocks[block]

    # Create execution frame
    env = {}
    if block.input_name and block.arg_name:
        env[block.input_name] = input_value
        env[block.arg_name] = args_value
    elif block.input_name:
        # Single param - gets input if piped, else args
        if input_value.data:  # Non-empty input
            env[block.input_name] = input_value
        else:
            env[block.input_name] = args_value

    frame = comp.ExecutionFrame(env=env, interp=interp)
    return frame.run(block.body_instructions)


def _make_constant(original, value):
    """Create a value.constant COP node preserving position info."""
    fields = {"value": value}
    try:
        pos = original.field("pos")
        if pos is not None:
            fields["pos"] = pos
    except (KeyError, AttributeError):
        pass
    return comp.create_cop("value.constant", [], **fields)


def _get_constant(cop):
    """Extract constant value from a value.constant COP node."""
    if comp.cop_tag(cop) == "value.constant":
        try:
            return cop.field("value")
        except (KeyError, AttributeError):
            pass
    return None
