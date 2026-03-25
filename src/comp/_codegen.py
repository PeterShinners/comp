"""Definition-focused code generation for the Comp interpreter.

This replaces the Builder pattern with a simpler functional approach.
Each Definition gets transformed into a sequence of Instructions.
"""

import comp


__all__ = [
    "generate_code_for_definition",
]


def generate_code_for_definition(cop, dispatch_own_name=None, dispatch_set_name=None, pure=False, namespace=None):
    """Generate instruction sequence for a single definition.
    
    This is the main entry point for code generation. Takes a Definition
    and produces the instruction sequence needed to compute its value.
    
    The generated code computes the value. The Definition object itself
    handles binding that value to the name in the namespace.
    
    Args:
        cop: (Value) cop nodes
        dispatch_own_name: (str | None) Qualified name of this definition (for !forward)
        dispatch_set_name: (str | None) Base name for Callable lookup (for !forward)
        pure: (bool) Whether this definition is pure (propagated to built blocks)
        
    Returns:
        List[Instruction]: Instruction sequence to compute the value
    """
    # Definitions with no COP (e.g. tag children pre-set by module) have no instructions.
    if cop is None:
        return []

    # Create a code generation context
    ctx = CodeGenContext(
        dispatch_own_name=dispatch_own_name,
        dispatch_set_name=dispatch_set_name,
        is_pure=pure,
        namespace=namespace,
    )

    # Generate instructions for the definition's resolved COP
    # The result is left in a register, no final store needed
    result_reg = ctx.build_expression(cop)

    return ctx.instructions


class CodeGenContext:
    """Code generation context for a single definition.
    
    Uses SSA-style implicit register numbering - instruction index IS the register.
    Operand references are integers pointing to previous instruction indices.
    """
    
    def __init__(self, dispatch_own_name=None, dispatch_set_name=None, is_pure=False, namespace=None):
        self.instructions = []
        self.dispatch_own_name = dispatch_own_name
        self.dispatch_set_name = dispatch_set_name
        self.is_pure = is_pure
        self.namespace = namespace
    
    def emit(self, instr):
        """Emit an instruction and return its index (the implicit result register)."""
        idx = len(self.instructions)
        self.instructions.append(instr)
        return idx
    
    def build_expression(self, cop):
        """Build instructions for an expression COP.
        
        Returns the instruction index containing the final result.
        Always ensures the result is in a register (emits Const if needed).
        """
        return self._build_value_ensure_register(cop)
    
    def _build_value(self, cop):
        """Build a value from a COP node.
        
        Returns either:
        - A register name (str) for computed values  
        - A Value for inlineable constants
        """
        tag = comp.cop_tag(cop)
        
        match tag:
            case "value.constant":
                const_val = cop.field("value")
                # If the constant is a Callable wrapping a Block, emit BuildBlock at runtime
                if isinstance(const_val.data, comp.Callable):
                    block = const_val.data.scalar()
                    if block is not None:
                        if block.body_instructions:
                            body_instructions = block.body_instructions
                        elif block.body is not None:
                            body_ctx = self.__class__(namespace=self.namespace)
                            body_ctx.build_expression(block.body)
                            body_instructions = body_ctx.instructions
                        else:
                            body_instructions = []
                        signature_cop = getattr(block, "signature_cop", None)
                        return self.emit(comp._instructions.BuildBlock(
                            cop=cop,
                            signature_cop=signature_cop,
                            body_instructions=body_instructions
                        ))
                elif isinstance(const_val.data, comp.Block):
                    block = const_val.data
                    if block.body_instructions:
                        body_instructions = block.body_instructions
                    elif block.body is not None:
                        body_ctx = self.__class__(namespace=self.namespace)
                        body_ctx.build_expression(block.body)
                        body_instructions = body_ctx.instructions
                    else:
                        body_instructions = []
                    signature_cop = getattr(block, "signature_cop", None)
                    return self.emit(comp._instructions.BuildBlock(
                        cop=cop,
                        signature_cop=signature_cop,
                        body_instructions=body_instructions
                    ))
                return const_val
                
            case "value.namespace":
                # Explicit namespace reference produced by coptimize
                try:
                    qualified_name = cop.to_python("qualified")
                    if isinstance(qualified_name, list):
                        instr = comp._instructions.LoadOverload(cop=cop, names=qualified_name)
                    else:
                        instr = comp._instructions.LoadVar(cop=cop, name=qualified_name)
                    return self.emit(instr)
                except (AttributeError, KeyError) as e:
                    raise comp.CodeError(f"Invalid namespace reference: {e}", cop)

            case "value.local":
                # Explicit local variable reference produced by coptimize
                name = cop.to_python("name")
                result = self.emit(comp._instructions.LoadLocal(cop=cop, name=name))
                result = _apply_field_access(self, cop, result, _cop_kids(cop))
                return result

            case "value.reference":
                # Legacy resolved namespace reference (from cop_resolve or older paths)
                try:
                    qualified_name = cop.to_python("qualified")
                    if isinstance(qualified_name, list):
                        instr = comp._instructions.LoadOverload(cop=cop, names=qualified_name)
                    else:
                        instr = comp._instructions.LoadVar(cop=cop, name=qualified_name)
                    return self.emit(instr)
                except (AttributeError, KeyError) as e:
                    raise comp.CodeError(f"Invalid reference: {e}", cop)

            case "value.identifier":
                # Unresolved identifier — the name resolution pass
                # (cop_resolve_names) must run before codegen.  All
                # value.identifier nodes should have been converted to
                # value.local, value.namespace, or value.undefined.
                kids = _cop_kids(cop)
                name = kids[0].to_python("value") if kids else "?"
                raise comp.CodeError(
                    f"Unresolved identifier '{name}' reached codegen — "
                    f"name resolution was not run on this COP tree",
                    cop,
                )

            case "value.undefined":
                # Grenade node — name resolution ran but this identifier could
                # not be resolved.  Raise a clear error at code generation time.
                try:
                    undef_name = cop.to_python("name")
                except (KeyError, AttributeError):
                    undef_name = "?"
                raise comp.CodeError(
                    f"Undefined reference '{undef_name}' — "
                    f"name is not defined in any visible scope or import",
                    cop,
                )
            
            case "value.number":
                # Inline constant
                literal = cop.to_python("value")
                return comp.Value(comp.num_from_decimal_str(literal))

            case "value.text":
                # Inline constant
                literal = cop.to_python("value")
                return comp.Value.from_python(literal)

            case "value.cast_unit":
                # value[unit] — apply a unit tag to a value
                kids = _cop_kids(cop)
                value_reg = self._build_value_ensure_register(kids[0])
                unit_reg = self._build_value_ensure_register(kids[1])
                return self.emit(comp._instructions.CastUnit(
                    cop=cop, value_reg=value_reg, unit_reg=unit_reg
                ))

            case "value.strip_unit":
                # expr[] — strip unit annotation from a value
                kids = _cop_kids(cop)
                value_reg = self._build_value_ensure_register(kids[0])
                return self.emit(comp._instructions.StripUnit(
                    cop=cop, value_reg=value_reg
                ))
                
            case "value.math.binary":
                return self._build_binary_op(cop)

            case "value.math.unary":
                return self._build_unary_op(cop)

            case "value.logic.binary":
                return self._build_binary_op(cop)

            case "value.logic.unary":
                return self._build_unary_op(cop)

            case "value.compare":
                return self._build_compare_op(cop)
                
            case "value.invoke":
                return self._build_invoke(cop)
                
            case "value.pipeline":
                return self._build_pipeline(cop)

            case "value.binding":
                return self._build_binding(cop)

            case "value.wrapper":
                return self._build_wrapper(cop)

            case "value.handle":
                return self._build_handle_op(cop)

            case "value.field":
                return self._build_field_access(cop)

            case "value.stash":
                # value.stash: [target_expr, field_ident]
                # expr&field — get named field from current module's stash on expr
                kids = _cop_kids(cop)
                target_reg = self._build_value_ensure_register(kids[0])
                field_name = kids[1].to_python("value")
                return self.emit(comp._instructions.GetStash(
                    cop=cop, target_reg=target_reg, field=field_name
                ))
                
            case "function.define":
                return self._build_function(cop)

            case "startup.define":
                # Context preparation — body is a struct, compile it as a function
                body_cop = list(comp.cop_kids(cop))[0]
                func_cop = comp.create_cop("cop-type.function.define", [body_cop])
                return self._build_function(func_cop)

            case "main.define":
                # Entry point — body is already a function.define
                func_cop = list(comp.cop_kids(cop))[0]
                return self._build_function(func_cop)

            case "value.block":
                return self._build_block(cop)

            case "statement.define":
                return self._build_statement(cop)

            case "struct.define":
                return self._build_struct(cop)

            case "shape.define":
                return self._build_shape(cop)

            case "shape.union":
                return self._build_top_shape_union(cop)

            case "op.defer":
                # !defer expr — wrap expr in a zero-argument anonymous Block.
                kids = _cop_kids(cop)
                inner_cop = kids[0]
                body_ctx = self.__class__(namespace=self.namespace)
                body_ctx._build_value_ensure_register(inner_cop)
                sig_cop = comp.create_cop("block.signature", [])
                return self.emit(comp._instructions.BuildBlock(
                    cop=cop,
                    signature_cop=sig_cop,
                    body_instructions=body_ctx.instructions,
                ))

            case "op.my":
                # !let name expr — evaluate expr, store in frame env, return the value
                # Supports dotted paths: !let abc.xyz 4  → deep-set abc["xyz"] = 4
                kids = _cop_kids(cop)
                name_cop = kids[0] if kids else None
                value_cop = kids[1] if len(kids) > 1 else None
                if name_cop is None or value_cop is None:
                    raise comp.CodeError("op.my requires a name and a value expression", cop)
                path = _extract_path_segments(name_cop)
                value_idx = self._build_value_ensure_register(value_cop)
                if path and len(path) > 1:
                    return self.emit(comp._instructions.DeepSetLocal(
                        cop=cop, base_name=path[0], path=path[1:], value_reg=value_idx
                    ))
                name = _extract_name(name_cop)
                if name is None:
                    raise comp.CodeError("op.my requires a name", cop)
                return self.emit(comp._instructions.StoreLocal(cop=cop, name=name, source=value_idx))

            case "op.deliver":
                # !deliver name expr — publish dependency and bind local name
                kids = _cop_kids(cop)
                name_cop = kids[0] if kids else None
                value_cop = kids[1] if len(kids) > 1 else None
                if name_cop is None or value_cop is None:
                    raise comp.CodeError("op.deliver requires a name and a value expression", cop)
                name = _extract_name(name_cop)
                if name is None:
                    raise comp.CodeError("op.deliver requires a name", cop)
                value_idx = self._build_value_ensure_register(value_cop)
                return self.emit(comp._instructions.DeliverDependency(cop=cop, name=name, source=value_idx))

            case "op.stash":
                # !stash varname&key.path value
                # kids: [target_ident, key_ident, *path_idents, value_expr]
                kids = _cop_kids(cop)
                if len(kids) < 3:
                    raise comp.CodeError("op.stash requires a target, key, and value", cop)
                target_name = _extract_name(kids[0])
                if target_name is None:
                    raise comp.CodeError("op.stash requires a simple variable name as target", cop)
                key = kids[1].to_python("value")
                path = [kids[i].to_python("value") for i in range(2, len(kids) - 1)]
                value_reg = self._build_value_ensure_register(kids[-1])
                return self.emit(comp._instructions.SetStash(
                    cop=cop, target_name=target_name, key=key, path=path, value_reg=value_reg
                ))

            case "op.ctx":
                # !ctx name expr — like !let but also adds to the running frame context
                # Supports dotted paths: !ctx abc.xyz 4  → deep-set abc["xyz"] = 4
                kids = _cop_kids(cop)
                name_cop = kids[0] if kids else None
                value_cop = kids[1] if len(kids) > 1 else None
                if name_cop is None or value_cop is None:
                    raise comp.CodeError("op.ctx requires a name and a value expression", cop)
                path = _extract_path_segments(name_cop)
                value_idx = self._build_value_ensure_register(value_cop)
                if path and len(path) > 1:
                    # Deep ctx: set the path in the base local and update context for base name
                    return self.emit(comp._instructions.DeepSetLocal(
                        cop=cop, base_name=path[0], path=path[1:], value_reg=value_idx,
                        update_context=True,
                    ))
                name = _extract_name(name_cop)
                if name is None:
                    raise comp.CodeError("op.ctx requires a name", cop)
                return self.emit(comp._instructions.SetContext(cop=cop, name=name, source=value_idx))

            case "op.forward":
                # Standalone !forward — re-dispatch using $ as piped input
                return self.emit(comp._instructions.Forward(cop=cop, piped_reg=None))

            case "op.fail":
                # !fail expr — evaluate expr, set as failure, fast-forward
                kids = _cop_kids(cop)
                if not kids:
                    raise comp.CodeError("op.fail requires a value expression", cop)
                value_idx = self._build_value_ensure_register(kids[0])
                return self.emit(comp._instructions.RaiseFail(cop=cop, value_reg=value_idx))

            case "value.fold-fail":
                # Fold-time failure — same codegen as op.fail
                kids = _cop_kids(cop)
                if not kids:
                    raise comp.CodeError("value.fold-fail requires a value expression", cop)
                value_idx = self._build_value_ensure_register(kids[0])
                return self.emit(comp._instructions.RaiseFail(cop=cop, value_reg=value_idx))

            case "value.fallback":
                # expr ?? h1 ?? h2 — chain of Fallback instructions
                # kids[0] is the initial expression; each remaining kid is a handler
                kids = _cop_kids(cop)
                if len(kids) < 2:
                    raise comp.CodeError("value.fallback requires left and right expressions", cop)
                result = self._build_value_ensure_register(kids[0])
                for handler_cop in kids[1:]:
                    handler_ctx = self.__class__(namespace=self.namespace)
                    handler_ctx._build_value_ensure_register(handler_cop)
                    result = self.emit(comp._instructions.Fallback(
                        cop=cop,
                        test_reg=result,
                        handler_instructions=handler_ctx.instructions,
                    ))
                return result

            case "op.on":
                return self._build_on_op(cop)

            case _:
                raise comp.CodeError(f"Unsupported COP tag: {tag}", cop)
    
    def _build_binary_op(self, cop):
        """Build binary operation instructions."""
        op = cop.to_python("op")
        kids = _cop_kids(cop)
        
        left = self._build_value_ensure_register(kids[0])
        right = self._build_value_ensure_register(kids[1])
        
        instr = comp._instructions.BinOp(cop=cop, op=op, left=left, right=right)
        return self.emit(instr)
    
    def _build_unary_op(self, cop):
        """Build unary operation instructions."""
        op = cop.to_python("op")
        kids = _cop_kids(cop)

        operand = self._build_value_ensure_register(kids[0])

        instr = comp._instructions.UnOp(cop=cop, op=op, operand=operand)
        return self.emit(instr)

    def _build_compare_op(self, cop):
        """Build comparison operation instructions."""
        op = cop.to_python("op")
        kids = _cop_kids(cop)

        left = self._build_value_ensure_register(kids[0])
        right = self._build_value_ensure_register(kids[1])

        instr = comp._instructions.CmpOp(cop=cop, op=op, left=left, right=right)
        return self.emit(instr)
    
    def _build_invoke(self, cop):
        """Build function invocation instructions."""
        kids = _cop_kids(cop)
        callable_cop = kids[0]
        
        # Build the callable
        callable_idx = self._build_callable_ensure_register(callable_cop)

        # Process each argument as a separate call.
        # Args are built without TryInvoke so callables can reach :block params.
        result = callable_idx
        for arg_cop in kids[1:]:
            arg_idx = self._build_args_struct(arg_cop)
            instr = comp._instructions.Invoke(cop=cop, callable=result, args=arg_idx)
            result = self.emit(instr)

        return result
    
    def _build_pipeline(self, cop):
        """Build pipeline instructions.
        
        A pipeline threads a value through a series of stages.
        Each stage receives the previous result as piped input.
        """
        kids = _cop_kids(cop)
        self._validate_pipeline_dependencies(kids)

        # First stage: try-invoke with nil as implicit piped input.
        # If kids[0] is not callable, PipeInvoke returns it as-is (try semantics).
        nil_idx = self.emit(comp._instructions.Const(cop=cop, value=comp.Value.from_python(comp.tag_nil)))
        callable_idx = self._build_callable_ensure_register(kids[0])
        args_idx = self.emit(comp._instructions.BuildStruct(cop=kids[0], fields=[]))
        result = self.emit(comp._instructions.PipeInvoke(
            cop=kids[0],
            callable=callable_idx,
            piped=nil_idx,
            args=args_idx,
        ))

        # Each subsequent stage receives the previous result as piped input
        for stage_cop in kids[1:]:
            stage_tag = comp.cop_tag(stage_cop)
            
            if stage_tag == "value.pipeline_fallback":
                # |? handler — catch failure from pipeline; invoke handler with failure as piped input.
                # Compile callable and args of the inner stage into fresh sub-contexts so they
                # run cleanly when the failure is being handled (not contaminated by failure state).
                inner_cop = _cop_kids(stage_cop)[0]
                inner_tag = comp.cop_tag(inner_cop)

                if inner_tag in ("value.invoke", "value.binding"):
                    inner_kids = _cop_kids(inner_cop)
                    callable_cop = inner_kids[0]
                    args_cop = inner_kids[1] if len(inner_kids) > 1 else None
                else:
                    callable_cop = inner_cop
                    args_cop = None

                callable_ctx = self.__class__(namespace=self.namespace)
                callable_ctx._build_callable_ensure_register(callable_cop)

                args_ctx = self.__class__(namespace=self.namespace)
                if args_cop is not None:
                    args_ctx._build_args_struct(args_cop)
                else:
                    args_ctx.emit(comp._instructions.BuildStruct(cop=stage_cop, fields=[]))

                result = self.emit(comp._instructions.PipeFallback(
                    cop=stage_cop,
                    piped_reg=result,
                    callable_instructions=callable_ctx.instructions,
                    args_instructions=args_ctx.instructions,
                ))
            elif stage_tag in ("value.invoke", "value.binding"):
                # Piped invoke/binding: callable(args) with piped input.
                # value.invoke kids: [callable, args_struct]
                # value.binding kids: [callable, bindings_struct]
                # Both share the same layout, so handled identically here.
                stage_kids = _cop_kids(stage_cop)
                callable_cop = stage_kids[0]
                callable_idx = self._build_callable_ensure_register(callable_cop)

                if len(stage_kids) > 1:
                    # Build args without TryInvoke so callables reach :block params
                    arg_idx = self._build_args_struct(stage_kids[1])
                else:
                    arg_idx = self.emit(comp._instructions.BuildStruct(cop=stage_cop, fields=[]))

                instr = comp._instructions.PipeInvoke(
                    cop=stage_cop,
                    callable=callable_idx,
                    piped=result,
                    args=arg_idx
                )
                result = self.emit(instr)
            else:
                # Bare callable stage — special-case !forward, otherwise PipeInvoke
                if stage_tag == "op.forward":
                    # !forward as a pipeline stage: re-dispatch with explicit piped input
                    result = self.emit(comp._instructions.Forward(cop=stage_cop, piped_reg=result))
                else:
                    callable_idx = self._build_callable_ensure_register(stage_cop)
                    arg_idx = self.emit(comp._instructions.BuildStruct(cop=stage_cop, fields=[]))
                    instr = comp._instructions.PipeInvoke(
                        cop=stage_cop,
                        callable=callable_idx,
                        piped=result,
                        args=arg_idx
                    )
                    result = self.emit(instr)
        
        return result

    def _validate_pipeline_dependencies(self, stage_cops):
        """Reject adjacent static pipeline stages with impossible dependencies."""
        if not self.namespace or len(stage_cops) < 2:
            return

        previous_contract = _extract_stage_contract(stage_cops[0], self.namespace)
        for stage_cop in stage_cops[1:]:
            current_contract = _extract_stage_contract(stage_cop, self.namespace)
            if previous_contract is not None and current_contract is not None:
                missing = sorted(current_contract["required"] - previous_contract["provided"])
                if missing:
                    raise comp.CodeError(
                        "Pipeline stage requires missing dependency: " + ", ".join(missing),
                        stage_cop,
                    )
            previous_contract = current_contract

    def _build_binding(self, cop):
        """Build value.binding instructions.

        Kids: [0] = callable expression, [1] = body (args struct).
        Compiles to an Invoke: callable(args).
        """
        kids = _cop_kids(cop)
        callable_cop = kids[0] if kids else None
        body_cop = kids[1] if len(kids) > 1 else None

        callable_idx = self._build_callable_ensure_register(callable_cop)

        if body_cop is not None:
            # Build the args struct without TryInvoke so callables can reach :block params
            args_idx = self._build_args_struct(body_cop)
        else:
            args_idx = self.emit(comp._instructions.BuildStruct(cop=cop, fields=[]))

        instr = comp._instructions.Invoke(cop=cop, callable=callable_idx, args=args_idx)
        return self.emit(instr)

    def _build_on_op(self, cop):
        """Build !on dispatch instructions.

        Evaluates a condition expression and dispatches to the first branch
        whose pattern (shape) successfully morphs the condition value.

        Structure of op.on kids:
          kids[0]   : condition expression
          kids[1:]  : op.on.branch nodes, each with:
                        kids[0] = shape pattern (shape.define)
                        kids[1] = result expression
        """
        kids = _cop_kids(cop)
        if not kids:
            raise comp.CodeError("op.on requires at least a condition expression", cop)

        # Build the condition expression into a register
        condition_idx = self._build_value_ensure_register(kids[0])

        # Build each branch as a pair of instruction lists
        branches = []
        for branch_cop in kids[1:]:
            if comp.cop_tag(branch_cop) != "op.on.branch":
                raise comp.CodeError(f"Expected op.on.branch, got {comp.cop_tag(branch_cop)}", branch_cop)

            branch_kids = _cop_kids(branch_cop)
            if len(branch_kids) < 2:
                raise comp.CodeError("op.on.branch requires a pattern and a result expression", branch_cop)

            # Compile the branch pattern in a fresh sub-context.
            # The pattern is typically a shape.define. When it wraps a single
            # identifier (e.g. ~true, ~false), we load it as a name reference so
            # that DispatchOn receives the actual Tag/Shape object for morph.
            pattern_ctx = self.__class__(namespace=self.namespace)
            _compile_on_pattern(pattern_ctx, branch_kids[0])
            pattern_instructions = pattern_ctx.instructions

            # Compile the result expression in a fresh sub-context
            result_ctx = self.__class__(namespace=self.namespace)
            result_ctx._build_value_ensure_register(branch_kids[1])
            result_instructions = result_ctx.instructions

            branches.append((pattern_instructions, result_instructions))

        return self.emit(comp._instructions.DispatchOn(cop=cop, condition=condition_idx, branches=branches))

    def _build_handle_op(self, cop):
        """Build handle operator instructions (!grab, !drop, !pull, !push)."""
        op = cop.to_python("op")
        kids = _cop_kids(cop)

        if op == "grab":
            tag_reg = self._build_value_ensure_register(kids[0])
            data_reg = self._build_value_ensure_register(kids[1])
            return self.emit(comp._instructions.GrabHandle(cop=cop, tag_reg=tag_reg, data_reg=data_reg))

        elif op == "drop":
            handle_reg = self._build_value_ensure_register(kids[0])
            return self.emit(comp._instructions.DropHandle(cop=cop, handle_reg=handle_reg))

        elif op == "pull":
            handle_reg = self._build_value_ensure_register(kids[0])
            return self.emit(comp._instructions.PullHandle(cop=cop, handle_reg=handle_reg))

        elif op == "push":
            handle_reg = self._build_value_ensure_register(kids[0])
            data_reg = self._build_value_ensure_register(kids[1])
            return self.emit(comp._instructions.PushHandle(cop=cop, handle_reg=handle_reg, data_reg=data_reg))

        else:
            raise comp.CodeError(f"Unknown handle operator: {op!r}", cop)

    def _build_field_access(self, cop):
        """Build field access instructions.
        
        Generates code for expressions like `struct.field`, `struct.a.b`, or
        `struct.#0` where we need to extract fields from struct values.
        """
        # kids[0] is left (the struct), kids[1] is field (the identifier)
        kids = _cop_kids(cop)
        left_cop = kids[0]
        field_cop = kids[1]
        
        # Build the left side (struct expression)
        result = self._build_value_ensure_register(left_cop)
        
        # Extract field accessors from the identifier - may be single field or multiple
        field_tag = comp.cop_tag(field_cop)
        
        if field_tag == "value.identifier":
            # Multiple field parts: chain access
            field_kids = _cop_kids(field_cop)
        else:
            # Single field: wrap in list for uniform handling
            field_kids = [field_cop]
        
        if not field_kids:
            raise comp.CodeError("Postfix field has no identifier", cop)
        
        # Chain field access for each part in the identifier
        for field_token in field_kids:
            field_tag = comp.cop_tag(field_token)
            
            if field_tag == "ident.token":
                # Named field access: struct.fieldname
                field_name = field_token.to_python("value")
                result = self.emit(comp._instructions.GetField(
                    cop=cop,
                    struct_reg=result,
                    field=field_name
                ))
            elif field_tag == "ident.index":
                # Positional field access: struct.#N (0-based)
                index_str = field_token.to_python("value")
                index = int(index_str)
                result = self.emit(comp._instructions.GetIndex(
                    cop=cop,
                    struct_reg=result,
                    index=index
                ))
            elif field_tag == "ident.indexpr":
                # Dynamic positional field access: struct.#(expr)
                expr_kids = _cop_kids(field_token)
                if not expr_kids:
                    raise comp.CodeError("indexpr has no expression", cop)
                index_reg = self._build_value_ensure_register(expr_kids[0])
                result = self.emit(comp._instructions.GetDynamicIndex(
                    cop=cop,
                    struct_reg=result,
                    index_reg=index_reg
                ))
            else:
                raise comp.CodeError(f"Unsupported postfix field type: {field_tag}", cop)
        
        return result
    
    def _build_block(self, cop):
        """Build block/function instructions."""
        kids = _cop_kids(cop)
        # Two kids: [block.signature, body] — from :~shape (body) syntax
        # One kid:  [body]                  — from :[pipeline] or :statement syntax
        if len(kids) >= 2 and comp.cop_tag(kids[0]) == "block.signature":
            signature_cop = kids[0]
            body_cop = kids[1]
        else:
            signature_cop = comp.create_cop("block.signature", [])
            body_cop = kids[0] if kids else comp.create_cop("statement.define", [])

        # Build body instructions in a separate context
        body_ctx = CodeGenContext(is_pure=self.is_pure, namespace=self.namespace)
        body_ctx._build_value_ensure_register(body_cop)
        
        instr = comp._instructions.BuildBlock(
            cop=cop,
            signature_cop=signature_cop,
            body_instructions=body_ctx.instructions,
            pure=self.is_pure,
        )
        return self.emit(instr)

    def _build_wrapper(self, cop):
        """Build value.wrapper instructions.

        @wrapper expr compiles to:
          1. Evaluate expr WITHOUT auto-invoke (passed as raw statement data)
          2. BuildInvokeData — capture statement + current frame state
          3. Load wrapper callable
          4. PipeInvoke: invoke-data | wrapper()

        The wrapper function receives invoke-data as its piped input ($) and
        may call `invoke` to execute the statement, inspect it, ignore it, or
        invoke it multiple times.
        """
        kids = _cop_kids(cop)
        wrapper_cop = kids[0]   # @name identifier
        inner_cop   = kids[1]   # wrapped statement

        # Compile the inner value without auto-invoke so the wrapper receives
        # the raw thing (Block, text, etc.) rather than its called result.
        inner_reg = self._build_callable_ensure_register(inner_cop)

        # Capture current frame state around the statement
        invoke_data_reg = self.emit(comp._instructions.BuildInvokeData(cop=cop, statement_reg=inner_reg))

        # Load wrapper callable and call with invoke-data piped in
        wrapper_reg = self._build_callable_ensure_register(wrapper_cop)
        empty_args  = self.emit(comp._instructions.BuildStruct(cop=cop, fields=[]))
        return self.emit(comp._instructions.PipeInvoke(
            cop=cop,
            callable=wrapper_reg,
            piped=invoke_data_reg,
            args=empty_args,
        ))

    def _build_function(self, cop):
        """Build function.define instructions."""
        # Kids are positional: [function.signature?, body]
        # Signature is optional - check the first kid's tag to distinguish
        kids = _cop_kids(cop)
        if kids and comp.cop_tag(kids[0]) == "function.signature":
            func_sig_cop = kids[0]
            body_cop = kids[1] if len(kids) > 1 else None
        else:
            func_sig_cop = None
            body_cop = kids[0] if kids else None

        # Combined signature = kids of function.signature (signature.input etc.)
        # plus any signature.param nodes from a leading block.signature in the body.
        sig_kids = list(_cop_kids(func_sig_cop)) if func_sig_cop else []

        # Peel a wrapper off the body before compiling the block.
        # The parser places @wrapper inside body_cop as value.wrapper(name, actual-body).
        # We want the wrapper applied to the *compiled Block* at definition time, not
        # baked into the block's body (which would fire it on every call).
        func_wrapper_cop = None
        if body_cop and comp.cop_tag(body_cop) == "value.wrapper":
            wrapper_kids = _cop_kids(body_cop)
            func_wrapper_cop = wrapper_kids[0]   # the @name identifier
            body_cop         = wrapper_kids[1]   # the actual body (statement.define)

        # If the body is a statement.define whose first kid is a block.signature,
        # extract the param nodes from it and fold them into the combined signature.
        if body_cop and comp.cop_tag(body_cop) == "statement.define":
            body_field_kids = _cop_kids(body_cop)
            if body_field_kids and comp.cop_tag(body_field_kids[0]) == "block.signature":
                body_sig_kids = _cop_kids(body_field_kids[0])
                sig_kids = sig_kids + list(body_sig_kids)

        combined_sig = comp.create_cop("block.signature", sig_kids)

        if body_cop is None:
            body_cop = comp.create_cop("statement.define", [])

        # Build body instructions in a separate context
        body_ctx = CodeGenContext(is_pure=self.is_pure, namespace=self.namespace)
        body_ctx._build_value_ensure_register(body_cop)

        block_reg = self.emit(comp._instructions.BuildBlock(
            cop=cop,
            signature_cop=combined_sig,
            body_instructions=body_ctx.instructions,
            dispatch_own_name=self.dispatch_own_name,
            dispatch_set_name=self.dispatch_set_name,
            pure=self.is_pure,
        ))

        # If there was a wrapper, attach it to the block so it is called at every
        # invocation instead of being applied once at definition time.
        if func_wrapper_cop is not None:
            wrapper_reg = self._build_callable_ensure_register(func_wrapper_cop)
            block_reg = self.emit(comp._instructions.SetBlockWrapper(
                cop=cop,
                block_reg=block_reg,
                wrapper_reg=wrapper_reg,
            ))

        return block_reg

    def _build_statement(self, cop):
        """Build statement.define instructions.

        Each kid is a statement.field; evaluate the last one as the result.
        The result is auto-invoked: if callable it is called with empty args,
        otherwise it is returned as-is. This is how (four) calls four.
        An empty statement produces an empty struct.
        """
        field_kids = _cop_kids(cop)

        if not field_kids:
            return self.emit(comp._instructions.BuildStruct(cop=cop, fields=[]))

        result = None
        expr_result = None   # last non-let expression register
        has_trailing_let = False
        for kid in field_kids:
            if comp.cop_tag(kid) == "block.signature":
                continue  # metadata: param declarations consumed by _build_function
            if comp.cop_tag(kid) == "statement.field":
                inner = _cop_kids(kid)
                if inner:
                    inner_tag = comp.cop_tag(inner[0])
                    result = self._build_value_ensure_register(inner[0])
                    if inner_tag in ("op.my", "op.deliver"):
                        has_trailing_let = True
                    else:
                        expr_result = result
                        has_trailing_let = False
            else:
                tag = comp.cop_tag(kid)
                result = self._build_value_ensure_register(kid)
                if tag in ("op.my", "op.deliver"):
                    has_trailing_let = True
                else:
                    expr_result = result
                    has_trailing_let = False

        if result is None:
            return self.emit(comp._instructions.BuildStruct(cop=cop, fields=[]))

        # If trailing !let statements would clobber the return value,
        # emit a SelectResult to preserve the last expression result.
        if has_trailing_let and expr_result is not None:
            return self.emit(comp._instructions.SelectResult(cop=cop, source=expr_result))

        # Statement contained only !my bindings with no value expression — return nil.
        if has_trailing_let:
            nil_val = comp.Value.from_python(comp.tag_nil)
            return self.emit(comp._instructions.Const(cop=cop, value=nil_val))

        return result

    def _build_struct(self, cop):
        """Build struct construction instructions."""
        kids = _cop_kids(cop)
        fields = []

        for kid in kids:
            tag = comp.cop_tag(kid)

            if tag == "struct.posfield":
                inner = _cop_kids(kid)
                if inner:
                    fields.append((comp.Unnamed(), self._build_value_ensure_register(inner[0])))

            elif tag in ("op.my", "op.deliver"):
                # !let binding — side effect only, does not contribute a field
                self._build_value_ensure_register(kid)

            elif tag == "op.ctx":
                # !ctx binding — side effect only, does not contribute a field
                self._build_value_ensure_register(kid)

            elif tag == "struct.letassign":
                # Kids: [0]=name identifier, [1]=value expression
                let_kids = _cop_kids(kid)
                if len(let_kids) >= 2:
                    name = _extract_name(let_kids[0])
                    if name is not None:
                        value_idx = self._build_value_ensure_register(let_kids[1])
                        self.emit(comp._instructions.StoreLocal(cop=kid, name=name, source=value_idx))

            elif tag == "struct.namefield":
                # Kids: [0]=name identifier, [1]=value expression
                field_kids = _cop_kids(kid)
                if len(field_kids) >= 2:
                    name = _extract_name(field_kids[0])
                    if name is not None:
                        value_idx = self._build_value_ensure_register(field_kids[1])
                        fields.append((name, value_idx))

        return self.emit(comp._instructions.BuildStruct(cop=cop, fields=fields))

    def _build_shape(self, cop):
        """Build shape construction instructions.

        Shape type constraints are passed as name strings (resolved at execute time),
        not as register indices — so no LoadVar is emitted for them.
        Defaults are simple constant expressions compiled to register indices.

        When a shape.define wraps a single value (value.constant, value.namespace,
        value.local) that is itself a tag or shape, we compile it directly as a
        value load rather than building an anonymous structural shape.
        """
        kids = _cop_kids(cop)
        fields = []

        # Single-child shape.define wrapping a resolved value (tag or shape
        # reference) — compile the inner value directly instead of building
        # an anonymous struct shape.
        if len(kids) == 1:
            kid_tag = comp.cop_tag(kids[0])
            if kid_tag in ("value.constant", "value.namespace", "value.local",
                           "value.reference", "value.undefined"):
                return self._build_value_ensure_register(kids[0])

            # Single unnamed shape.field with limits (e.g. ~entry<only-dir>):
            # compile as the base shape reference with shape-level limits,
            # not as a struct with an unnamed positional field.
            if kid_tag == "shape.field":
                field_name = None
                try:
                    field_name = kids[0].to_python("name")
                except (KeyError, AttributeError):
                    pass
                if field_name is None:
                    field_kids = _cop_kids(kids[0])
                    has_limits = any(comp.cop_tag(fk) == "value.limit" for fk in field_kids)
                    if has_limits:
                        # Extract the base shape ref and limit refs
                        base_ref = None
                        limit_refs = []
                        for fk in field_kids:
                            fk_tag = comp.cop_tag(fk)
                            if fk_tag == "value.limit":
                                lk = _cop_kids(fk)
                                if lk:
                                    limit_name = _shape_ref_or_reg(self, lk[0])
                                    param_idx = self._build_value_ensure_register(lk[1]) if len(lk) >= 2 else None
                                    limit_refs.append((limit_name, param_idx))
                            elif base_ref is None:
                                base_ref = _shape_ref_or_reg(self, fk)
                        return self.emit(comp._instructions.BuildShapeWithLimits(
                            cop=cop, shape_ref=base_ref, limit_refs=limit_refs,
                        ))

        for kid in kids:
            tag = comp.cop_tag(kid)

            if tag == "shape.union":
                # Shape union — unwrap shape.field kids to get the type references
                member_refs = [_shape_ref_or_reg(self, _cop_kids(m)[0]) for m in _cop_kids(kid)]
                return self.emit(comp._instructions.BuildShapeUnion(cop=cop, member_refs=member_refs))

            elif tag == "shape.field":
                # Named field: name attribute; kids are tagged by COP type:
                # shape.unit, shape.default, value.limit, shape.repeat,
                # or a plain shape ref as the base type.
                name = None
                try:
                    name = kid.to_python("name")
                except (KeyError, AttributeError):
                    pass

                shape_ref = None
                unit_ref = None
                default_idx = None
                limit_refs = []  # list of (name_str, param_idx_or_None)
                repeat_bounds = None  # (min_count, max_count) or None
                field_kids = _cop_kids(kid)
                for fk in field_kids:
                    fk_tag = comp.cop_tag(fk)
                    if fk_tag == "shape.unit":
                        # shape.unit: BRACKET_OPEN identifier BRACKET_CLOSE
                        unit_kids = _cop_kids(fk)
                        if unit_kids:
                            unit_ref = _shape_ref_or_reg(self, unit_kids[0])
                    elif fk_tag == "shape.default":
                        default_fk_kids = _cop_kids(fk)
                        if default_fk_kids:
                            default_idx = self._build_value_ensure_register(default_fk_kids[0])
                    elif fk_tag == "value.limit":
                        lk = _cop_kids(fk)
                        if lk:
                            limit_name = _shape_ref_or_reg(self, lk[0])
                            param_idx = self._build_value_ensure_register(lk[1]) if len(lk) >= 2 else None
                            limit_refs.append((limit_name, param_idx))
                    elif fk_tag == "shape.repeat":
                        repeat_op = fk.to_python("op")
                        rk = _cop_kids(fk)
                        if repeat_op == "*":
                            repeat_bounds = (0, None)
                        elif repeat_op == "=":
                            n = int(rk[0].to_python("value"))
                            repeat_bounds = (n, n)
                        elif repeat_op == "+":
                            n = int(rk[0].to_python("value"))
                            repeat_bounds = (n, None)
                        elif repeat_op == "-":
                            lo = int(rk[0].to_python("value"))
                            hi = int(rk[1].to_python("value"))
                            repeat_bounds = (lo, hi)
                    else:
                        # Base type reference (first non-special kid)
                        if shape_ref is None:
                            shape_ref = _shape_ref_or_reg(self, fk)

                if repeat_bounds is not None:
                    min_c, max_c = repeat_bounds
                    return self.emit(comp._instructions.BuildShapeCollection(
                        cop=cop, shape_ref=shape_ref, unit_ref=unit_ref,
                        limit_refs=limit_refs, min_count=min_c, max_count=max_c,
                    ))

                fields.append((name, shape_ref, unit_ref, default_idx, limit_refs))

        return self.emit(comp._instructions.BuildShape(cop=cop, fields=fields))

    def _build_top_shape_union(self, cop):
        """Build a top-level shape union definition (e.g. !shape foo ~num|text = 0).

        Separates shape.field member kids from the optional shape.default kid.
        """
        kids = _cop_kids(cop)
        member_refs = []
        default_idx = None

        for kid in kids:
            tag = comp.cop_tag(kid)
            if tag == "shape.field":
                field_kids = _cop_kids(kid)
                if field_kids:
                    member_refs.append(_shape_ref_or_reg(self, field_kids[0]))
            elif tag == "shape.default":
                default_kids = _cop_kids(kid)
                if default_kids:
                    default_idx = self._build_value_ensure_register(default_kids[0])

        return self.emit(comp._instructions.BuildShapeUnion(cop=cop, member_refs=member_refs, default_idx=default_idx))

    def _build_value_ensure_register(self, cop):
        """Build a value and ensure it's in a register (has an index).

        If the value is a constant, emit a Const instruction to load it.
        Returns the instruction index.
        """
        result = self._build_value(cop)

        if isinstance(result, int):
            # Already an instruction index
            return result
        else:
            # Constant value - emit Const instruction
            instr = comp._instructions.Const(cop=cop, value=result)
            return self.emit(instr)

    def _build_args_struct(self, cop):
        """Build a struct for function arguments, preserving callables as-is.

        Identical to the struct.define path in _build_struct except that each
        field value is compiled with _build_callable_ensure_register instead of
        _build_value_ensure_register. This preserves callables (Blocks) so they
        can be received by :block parameters.

        Used by _build_binding, _build_invoke, and _build_pipeline in place of
        _build_value_ensure_register when building the args struct.
        """
        tag = comp.cop_tag(cop)
        if tag not in ("struct.define", "statement.define"):
            # Not a struct node — compile as a callable reference
            return self._build_callable_ensure_register(cop)

        kids = _cop_kids(cop)
        fields = []

        for kid in kids:
            kid_tag = comp.cop_tag(kid)

            if kid_tag == "struct.posfield":
                inner = _cop_kids(kid)
                if inner:
                    fields.append((comp.Unnamed(), self._build_callable_ensure_register(inner[0])))

            elif kid_tag in ("op.my", "op.ctx", "op.deliver"):
                # Side-effect bindings — must still evaluate with full semantics
                self._build_value_ensure_register(kid)

            elif kid_tag == "struct.letassign":
                let_kids = _cop_kids(kid)
                if len(let_kids) >= 2:
                    name = _extract_name(let_kids[0])
                    if name is not None:
                        value_idx = self._build_value_ensure_register(let_kids[1])
                        self.emit(comp._instructions.StoreLocal(cop=kid, name=name, source=value_idx))

            elif kid_tag == "struct.namefield":
                field_kids = _cop_kids(kid)
                if len(field_kids) >= 2:
                    name = _extract_name(field_kids[0])
                    if name is not None:
                        # Use _build_callable_ensure_register so that a callable
                        # value (Block) is NOT auto-invoked before being passed
                        value_idx = self._build_callable_ensure_register(field_kids[1])
                        fields.append((name, value_idx))

        return self.emit(comp._instructions.BuildStruct(cop=cop, fields=fields))

    def _build_callable_ensure_register(self, cop):
        """Build a callable reference without auto-invoking it.

        Use this for the callable position in Invoke/PipeInvoke instructions.
        Emits the appropriate load instruction for references, locals, and
        simple identifiers; falls back to _build_value_ensure_register for
        complex expressions.
        """
        tag = comp.cop_tag(cop)

        if tag in ("value.namespace", "value.reference"):
            try:
                qualified_name = cop.to_python("qualified")
                if isinstance(qualified_name, list):
                    instr = comp._instructions.LoadOverload(cop=cop, names=qualified_name)
                else:
                    instr = comp._instructions.LoadVar(cop=cop, name=qualified_name)
                return self.emit(instr)
            except (AttributeError, KeyError) as e:
                raise comp.CodeError(f"Invalid callable reference: {e}", cop)

        elif tag == "value.local":
            name = cop.to_python("name")
            result = self.emit(comp._instructions.LoadLocal(cop=cop, name=name))
            return _apply_field_access(self, cop, result, _cop_kids(cop))

        elif tag == "value.identifier":
            # Legacy unresolved identifier in callable position — use LoadLocal
            # (consistent with the value-position handling above)
            kids = _cop_kids(cop)
            if not kids:
                raise comp.CodeError("Identifier has no token", cop)
            name = kids[0].to_python("value")
            result = self.emit(comp._instructions.LoadLocal(cop=cop, name=name))
            return _apply_field_access(self, cop, result, kids[1:])

        elif tag == "value.undefined":
            try:
                undef_name = cop.to_python("name")
            except (KeyError, AttributeError):
                undef_name = "?"
            raise comp.CodeError(
                f"Undefined reference '{undef_name}' — "
                f"name is not defined in any visible scope or import",
                cop,
            )

        else:
            # Inline block — any statement.define in callable/args position
            # should be compiled as a deferred Block, whether or not it has
            # a block.signature (i.e. !param declarations).
            if tag == "statement.define":
                kids = list(_cop_kids(cop))
                if kids and comp.cop_tag(kids[0]) == "block.signature":
                    return self._build_inline_block_with_signature(cop, kids)
                # No signature — simple inline block like :($ * 10)
                return self._build_inline_block_with_signature(cop, kids)
            # Complex expression — build normally; the result is used as-is
            return self._build_value_ensure_register(cop)

    def _build_inline_block_with_signature(self, cop, kids):
        """Build an inline block from a statement.define in callable/args position.

        When a binding argument like :(!param item~any expr) appears inside
        _build_args_struct, the (!param ...) creates a statement.define with a
        leading block.signature child.  This method compiles it into a proper
        BuildBlock so that parameter declarations take effect and the block
        can be invoked repeatedly by builtins like reduce.

        When there is no block.signature (e.g. :($ * 10)), an empty signature
        is synthesized and all kids are treated as body statements.
        """
        if kids and comp.cop_tag(kids[0]) == "block.signature":
            sig_cop = kids[0]
            body_kids = kids[1:]
        else:
            sig_cop = comp.create_cop("block.signature", [])
            body_kids = kids

        # Build body instructions from the body statement children
        body_ctx = self.__class__(is_pure=self.is_pure, namespace=self.namespace)
        result = None
        expr_result = None
        has_trailing_let = False

        for kid in body_kids:
            kid_tag = comp.cop_tag(kid)
            if kid_tag == "statement.field":
                inner = _cop_kids(kid)
                if inner:
                    inner_tag = comp.cop_tag(inner[0])
                    result = body_ctx._build_value_ensure_register(inner[0])
                    if inner_tag in ("op.my", "op.deliver"):
                        has_trailing_let = True
                    else:
                        expr_result = result
                        has_trailing_let = False
            else:
                result = body_ctx._build_value_ensure_register(kid)
                if comp.cop_tag(kid) in ("op.my", "op.deliver"):
                    has_trailing_let = True
                else:
                    expr_result = result
                    has_trailing_let = False

        if has_trailing_let and expr_result is not None:
            body_ctx.emit(comp._instructions.SelectResult(cop=cop, source=expr_result))

        instr = comp._instructions.BuildBlock(
            cop=cop,
            signature_cop=sig_cop,
            body_instructions=body_ctx.instructions,
            pure=self.is_pure,
        )
        return self.emit(instr)


def _compile_on_pattern(ctx, pattern_cop):
    """Compile an op.on.branch pattern COP into pattern_ctx instructions.

    Patterns are typically value.constant nodes (folded by the optimization
    pass), but may also be value.namespace references when the fold pass
    could not reduce them to constants (e.g. tags with ambiguous definition
    sets).  Both are valid — the runtime evaluates pattern instructions in
    a child frame and accepts any Tag, Shape, or ShapeUnion result.

    Only value.undefined patterns (truly unresolved names) are rejected
    since they indicate a missing import or typo.

    Args:
        ctx: (CodeGenContext) The pattern sub-context to emit instructions into
        pattern_cop: (Value) The shape.define COP node for the branch pattern

    Returns:
        (int) Register index of the pattern value (Tag, Shape, or ShapeUnion)
    """
    tag = comp.cop_tag(pattern_cop)
    if tag == "shape.define":
        kids = _cop_kids(pattern_cop)
        kid_tag = comp.cop_tag(kids[0]) if len(kids) == 1 else None
        # Truly unresolved name — fail hard so the root cause is surfaced.
        if kid_tag == "value.undefined":
            try:
                name = kids[0].to_python("name")
            except Exception:
                name = "?"
            raise comp.CodeError(
                f"!on branch pattern ~{name} is undefined "
                f"— check for a missing import or undefined identifier.",
                pattern_cop,
            )
    # Compile fully — value.constant, value.namespace, struct-pattern shapes, etc.
    return ctx._build_value_ensure_register(pattern_cop)


def _extract_signature_contract(cop):
    """Return dependency contract info for a statically-known callable COP."""
    if cop is None:
        return None

    sig_kids = []
    tag = comp.cop_tag(cop)

    if tag == "function.define":
        kids = list(comp.cop_kids(cop))
        if kids and comp.cop_tag(kids[0]) == "function.signature":
            sig_kids.extend(list(comp.cop_kids(kids[0])))
            body_cop = kids[1] if len(kids) > 1 else None
        else:
            body_cop = kids[0] if kids else None
        if body_cop is not None and comp.cop_tag(body_cop) == "statement.define":
            body_kids = list(comp.cop_kids(body_cop))
            if body_kids and comp.cop_tag(body_kids[0]) == "block.signature":
                sig_kids.extend(list(comp.cop_kids(body_kids[0])))
    elif tag == "statement.define":
        kids = list(comp.cop_kids(cop))
        if kids and comp.cop_tag(kids[0]) == "block.signature":
            sig_kids.extend(list(comp.cop_kids(kids[0])))
    else:
        return None

    provided = set()
    required = set()
    for field_cop in sig_kids:
        field_tag = comp.cop_tag(field_cop)
        try:
            name = field_cop.to_python("name")
        except (KeyError, AttributeError):
            name = None
        if not name:
            continue
        if field_tag == "signature.delivers":
            provided.add(name)
        elif field_tag == "signature.depend":
            has_default = any(comp.cop_tag(kid) == "shape.default" for kid in comp.cop_kids(field_cop))
            if not has_default:
                required.add(name)

    return {"provided": provided, "required": required}


def _extract_stage_contract(stage_cop, namespace):
    """Return dependency contract info for a statically-known pipeline stage."""
    if stage_cop is None:
        return None

    tag = comp.cop_tag(stage_cop)
    callable_cop = stage_cop
    if tag in ("value.invoke", "value.binding"):
        stage_kids = list(comp.cop_kids(stage_cop))
        callable_cop = stage_kids[0] if stage_kids else None
        if callable_cop is None:
            return None

    callable_tag = comp.cop_tag(callable_cop)
    if callable_tag == "value.namespace":
        try:
            qualified = callable_cop.to_python("qualified")
        except (KeyError, AttributeError):
            return None
        if not isinstance(qualified, str):
            return None
        entry = namespace.get(qualified)
        if entry is None or not isinstance(entry, comp.Callable) or len(entry.entries) != 1:
            return None
        definition = entry.entries[0]
        return _extract_signature_contract(definition.resolved_cop or definition.original_cop)

    if callable_tag == "statement.define":
        return _extract_signature_contract(callable_cop)

    return None


def _cop_kids(cop):
    """Extract kids from a COP node (helper function)."""
    return list(cop.field("kids").data.values())


def _shape_ref_or_reg(ctx, cop):
    """Return a shape name string for static shape references, or a register index.

    For value.namespace and value.identifier nodes that refer to a shape by name,
    returns the name string so BuildShape/BuildShapeUnion can resolve it at execute
    time without emitting LoadVar instructions.
    For overloaded names (qualified is a list), returns the list of names so
    BuildShape can build a Callable at execute time.
    For anything else, falls back to compiling to a register.
    """
    tag = comp.cop_tag(cop)
    if tag == "value.namespace":
        try:
            qualified = cop.to_python("qualified")
            if isinstance(qualified, str):
                return qualified
            if isinstance(qualified, list):
                return qualified
        except (KeyError, AttributeError):
            pass
    elif tag == "value.identifier":
        kids = _cop_kids(cop)
        if kids:
            try:
                parts = [k.to_python("value") for k in kids]
                return ".".join(parts)
            except (KeyError, AttributeError):
                pass
    # Fallback: compile to a register (shouldn't occur for well-formed shape defs)
    return ctx._build_value_ensure_register(cop)


def _extract_name(name_cop):
    """Extract a plain string name from an identifier COP node."""
    tag = comp.cop_tag(name_cop)
    if tag == "ident.token":
        return name_cop.to_python("value")
    elif tag == "value.local":
        return name_cop.to_python("name")
    elif tag == "value.identifier":
        kids = _cop_kids(name_cop)
        if kids:
            return kids[0].to_python("value")
    return None


def _extract_path_segments(name_cop):
    """Extract all path segments from an identifier COP.

    Returns a list of str (named field) or int (positional index) segments,
    or None if the COP is not a supported identifier form.

    Examples:
        ident.token("abc")          → ["abc"]
        value.local name="abc"      → ["abc"]
        value.identifier([abc,xyz]) → ["abc", "xyz"]
        value.identifier([abc,#1])  → ["abc", 1]
    """
    tag = comp.cop_tag(name_cop)
    if tag == "ident.token":
        return [name_cop.to_python("value")]
    if tag == "value.local":
        name = name_cop.to_python("name")
        return [name] if name else None
    if tag == "value.identifier":
        segments = []
        for kid in _cop_kids(name_cop):
            kid_tag = comp.cop_tag(kid)
            if kid_tag == "ident.token":
                segments.append(kid.to_python("value"))
            elif kid_tag == "ident.index":
                segments.append(int(kid.to_python("value")))
            else:
                return None  # unsupported segment type (expr field, dollar, etc.)
        return segments if segments else None
    return None


def _apply_field_access(ctx, cop, result, field_kids):
    """Apply a sequence of field/index access tokens to a register result.

    Used by value.local (and the legacy value.identifier path) to emit
    GetField/GetIndex instructions for each token in the remaining kids.

    Args:
        ctx: (CodeGenContext) Code generation context
        cop: (Value) Source COP node for error reporting
        result: (int) Register index of the base value
        field_kids: (list) ident.token / ident.index COP nodes to apply

    Returns:
        (int) Register index of the final result after all accesses
    """
    for kid in field_kids:
        field_tag = comp.cop_tag(kid)
        if field_tag == "ident.token":
            field_name = kid.to_python("value")
            result = ctx.emit(comp._instructions.GetField(cop=cop, field=field_name, struct_reg=result))
        elif field_tag == "ident.index":
            index_str = kid.to_python("value")
            result = ctx.emit(comp._instructions.GetIndex(cop=cop, struct_reg=result, index=int(index_str)))
        elif field_tag == "ident.indexpr":
            expr_kids = _cop_kids(kid)
            if not expr_kids:
                raise comp.CodeError("indexpr has no expression", cop)
            index_reg = ctx._build_value_ensure_register(expr_kids[0])
            result = ctx.emit(comp._instructions.GetDynamicIndex(cop=cop, struct_reg=result, index_reg=index_reg))
        else:
            raise comp.CodeError(f"Unsupported field access token: {field_tag}", cop)
    return result