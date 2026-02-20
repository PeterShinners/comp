"""Definition-focused code generation for the Comp interpreter.

This replaces the Builder pattern with a simpler functional approach.
Each Definition gets transformed into a sequence of Instructions.
"""

import comp

__all__ = [
    "generate_code_for_definition",
]


def generate_code_for_definition(cop):
    """Generate instruction sequence for a single definition.
    
    This is the main entry point for code generation. Takes a Definition
    and produces the instruction sequence needed to compute its value.
    
    The generated code computes the value. The Definition object itself
    handles binding that value to the name in the namespace.
    
    Args:
        cop: (Value) cop nodes
        
    Returns:
        List[Instruction]: Instruction sequence to compute the value
    """
    # Create a code generation context
    ctx = CodeGenContext()

    # Generate instructions for the definition's resolved COP
    # The result is left in a register, no final store needed
    result_reg = ctx.build_expression(cop)

    # function.define: the Block IS the value — don't auto-invoke.
    # shape.define: the Shape IS the value — no invokes allowed in shapes.
    # For everything else (expressions), emit TryInvoke to evaluate
    # callables and pass non-callable values through unchanged.
    _no_invoke_tags = {"function.define", "shape.define"}
    if comp.cop_tag(cop) not in _no_invoke_tags:
        ctx.emit(comp._interp.TryInvoke(cop=cop, value=result_reg))

    return ctx.instructions


class CodeGenContext:
    """Code generation context for a single definition.
    
    Uses SSA-style implicit register numbering - instruction index IS the register.
    Operand references are integers pointing to previous instruction indices.
    """
    
    def __init__(self):
        self.instructions = []
    
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
        tag = cop.positional(0).data.qualified
        
        match tag:
            case "value.constant":
                const_val = cop.field("value")
                # If the constant is a Block, emit BuildBlock at runtime
                if isinstance(const_val.data, comp.Block):
                    block = const_val.data
                    if block.body_instructions:
                        body_instructions = block.body_instructions
                    elif block.body is not None:
                        body_ctx = self.__class__()
                        body_ctx.build_expression(block.body)
                        body_instructions = body_ctx.instructions
                    else:
                        body_instructions = []
                    signature_cop = getattr(block, "signature_cop", None)
                    return self.emit(comp._interp.BuildBlock(
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
                        instr = comp._interp.LoadOverload(cop=cop, names=qualified_name)
                    else:
                        instr = comp._interp.LoadVar(cop=cop, name=qualified_name)
                    reg = self.emit(instr)
                    return self.emit(comp._interp.TryInvoke(cop=cop, value=reg))
                except (AttributeError, KeyError) as e:
                    raise comp.CodeError(f"Invalid namespace reference: {e}", cop)

            case "value.local":
                # Explicit local variable reference produced by coptimize
                name = cop.to_python("name")
                result = self.emit(comp._interp.LoadLocal(cop=cop, name=name))
                result = _apply_field_access(self, cop, result, _cop_kids(cop))
                return self.emit(comp._interp.TryInvoke(cop=cop, value=result))

            case "value.reference":
                # Legacy resolved namespace reference (from cop_resolve or older paths)
                try:
                    qualified_name = cop.to_python("qualified")
                    if isinstance(qualified_name, list):
                        instr = comp._interp.LoadOverload(cop=cop, names=qualified_name)
                    else:
                        instr = comp._interp.LoadVar(cop=cop, name=qualified_name)
                    reg = self.emit(instr)
                    return self.emit(comp._interp.TryInvoke(cop=cop, value=reg))
                except (AttributeError, KeyError) as e:
                    raise comp.CodeError(f"Invalid reference: {e}", cop)

            case "value.identifier":
                # Unresolved identifier — coptimize was not run or the name could
                # not be resolved.  Treat the first token as a plain local name so
                # that code still runs when called without a namespace (e.g. blocks
                # compiled before the full namespace is available).
                kids = _cop_kids(cop)
                if not kids:
                    raise comp.CodeError("Identifier has no token", cop)
                name = kids[0].to_python("value")
                result = self.emit(comp._interp.LoadLocal(cop=cop, name=name))
                result = _apply_field_access(self, cop, result, kids[1:])
                return self.emit(comp._interp.TryInvoke(cop=cop, value=result))
            
            case "value.number":
                # Inline constant
                import decimal
                literal = cop.to_python("value")
                return comp.Value.from_python(decimal.Decimal(literal))
                
            case "value.text":
                # Inline constant
                literal = cop.to_python("value") 
                return comp.Value.from_python(literal)
                
            case "value.math.binary":
                return self._build_binary_op(cop)

            case "value.math.unary":
                return self._build_unary_op(cop)

            case "value.compare":
                return self._build_compare_op(cop)
                
            case "value.invoke":
                return self._build_invoke(cop)
                
            case "value.pipeline":
                return self._build_pipeline(cop)

            case "value.binding":
                return self._build_binding(cop)

            case "value.handle":
                return self._build_handle_op(cop)

            case "value.field":
                return self._build_field_access(cop)
                
            case "function.define":
                return self._build_function(cop)

            case "value.block":
                return self._build_block(cop)

            case "statement.define":
                return self._build_statement(cop)

            case "struct.define":
                return self._build_struct(cop)

            case "shape.define":
                return self._build_shape(cop)

            case "op.let":
                # !let name expr — evaluate expr, store in frame env, return the value
                kids = _cop_kids(cop)
                name = _extract_name(kids[0]) if kids else None
                value_cop = kids[1] if len(kids) > 1 else None
                if name is None or value_cop is None:
                    raise comp.CodeError("op.let requires a name and a value expression", cop)
                value_idx = self._build_value_ensure_register(value_cop)
                return self.emit(comp._interp.StoreLocal(cop=cop, name=name, source=value_idx))

            case _:
                raise comp.CodeError(f"Unsupported COP tag: {tag}", cop)
    
    def _build_binary_op(self, cop):
        """Build binary operation instructions."""
        op = cop.to_python("op")
        kids = _cop_kids(cop)
        
        left = self._build_value_ensure_register(kids[0])
        right = self._build_value_ensure_register(kids[1])
        
        instr = comp._interp.BinOp(cop=cop, op=op, left=left, right=right)
        return self.emit(instr)
    
    def _build_unary_op(self, cop):
        """Build unary operation instructions."""
        op = cop.to_python("op")
        kids = _cop_kids(cop)

        operand = self._build_value_ensure_register(kids[0])

        instr = comp._interp.UnOp(cop=cop, op=op, operand=operand)
        return self.emit(instr)

    def _build_compare_op(self, cop):
        """Build comparison operation instructions."""
        op = cop.to_python("op")
        kids = _cop_kids(cop)

        left = self._build_value_ensure_register(kids[0])
        right = self._build_value_ensure_register(kids[1])

        instr = comp._interp.CmpOp(cop=cop, op=op, left=left, right=right)
        return self.emit(instr)
    
    def _build_invoke(self, cop):
        """Build function invocation instructions."""
        kids = _cop_kids(cop)
        callable_cop = kids[0]
        
        # Build the callable
        callable_idx = self._build_callable_ensure_register(callable_cop)
        
        # Process each argument as a separate call
        result = callable_idx
        for arg_cop in kids[1:]:
            arg_idx = self._build_value_ensure_register(arg_cop)
            instr = comp._interp.Invoke(cop=cop, callable=result, args=arg_idx)
            result = self.emit(instr)
            
        return result
    
    def _build_pipeline(self, cop):
        """Build pipeline instructions.
        
        A pipeline threads a value through a series of stages.
        Each stage receives the previous result as piped input.
        """
        kids = _cop_kids(cop)
        
        # First stage is the initial value
        result = self._build_value_ensure_register(kids[0])
        
        # Each subsequent stage receives the previous result as piped input
        for stage_cop in kids[1:]:
            stage_tag = stage_cop.positional(0).data.qualified
            
            if stage_tag in ("value.invoke", "value.binding"):
                # Piped invoke/binding: callable(args) with piped input.
                # value.invoke kids: [callable, args_struct]
                # value.binding kids: [callable, bindings_struct]
                # Both share the same layout, so handled identically here.
                stage_kids = _cop_kids(stage_cop)
                callable_cop = stage_kids[0]
                callable_idx = self._build_callable_ensure_register(callable_cop)

                if len(stage_kids) > 1:
                    arg_idx = self._build_value_ensure_register(stage_kids[1])
                else:
                    arg_idx = self.emit(comp._interp.BuildStruct(cop=stage_cop, fields=[]))

                instr = comp._interp.PipeInvoke(
                    cop=stage_cop,
                    callable=callable_idx,
                    piped=result,
                    args=arg_idx
                )
                result = self.emit(instr)
            else:
                # Bare callable stage - PipeInvoke with empty args
                callable_idx = self._build_callable_ensure_register(stage_cop)
                arg_idx = self.emit(comp._interp.BuildStruct(cop=stage_cop, fields=[]))
                instr = comp._interp.PipeInvoke(
                    cop=stage_cop,
                    callable=callable_idx,
                    piped=result,
                    args=arg_idx
                )
                result = self.emit(instr)
        
        return result

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
            args_idx = self._build_value_ensure_register(body_cop)
        else:
            args_idx = self.emit(comp._interp.BuildStruct(cop=cop, fields=[]))

        instr = comp._interp.Invoke(cop=cop, callable=callable_idx, args=args_idx)
        return self.emit(instr)

    def _build_handle_op(self, cop):
        """Build handle operator instructions (!grab, !drop, !pull, !push)."""
        op = cop.to_python("op")
        kids = _cop_kids(cop)

        if op == "grab":
            tag_reg = self._build_value_ensure_register(kids[0])
            return self.emit(comp._interp.GrabHandle(cop=cop, tag_reg=tag_reg))

        elif op == "drop":
            handle_reg = self._build_value_ensure_register(kids[0])
            return self.emit(comp._interp.DropHandle(cop=cop, handle_reg=handle_reg))

        elif op == "pull":
            handle_reg = self._build_value_ensure_register(kids[0])
            return self.emit(comp._interp.PullHandle(cop=cop, handle_reg=handle_reg))

        elif op == "push":
            handle_reg = self._build_value_ensure_register(kids[0])
            data_reg = self._build_value_ensure_register(kids[1])
            return self.emit(comp._interp.PushHandle(cop=cop, handle_reg=handle_reg, data_reg=data_reg))

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
                result = self.emit(comp._interp.GetField(
                    cop=cop,
                    struct_reg=result,
                    field=field_name
                ))
            elif field_tag == "ident.index":
                # Positional field access: struct.#N (0-based)
                index_str = field_token.to_python("value")
                index = int(index_str)
                result = self.emit(comp._interp.GetIndex(
                    cop=cop,
                    struct_reg=result,
                    index=index
                ))
            else:
                raise comp.CodeError(f"Unsupported postfix field type: {field_tag}", cop)
        
        return result
    
    def _build_block(self, cop):
        """Build block/function instructions."""
        kids = _cop_kids(cop)
        signature_cop = kids[0]  # shape definition
        body_cop = kids[1]       # struct definition with body
        
        # Build body instructions in a separate context
        body_ctx = CodeGenContext()
        body_ctx._build_value_ensure_register(body_cop)
        
        instr = comp._interp.BuildBlock(
            cop=cop,
            signature_cop=signature_cop,
            body_instructions=body_ctx.instructions
        )
        return self.emit(instr)

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
        sig_kids = _cop_kids(func_sig_cop) if func_sig_cop else []
        combined_sig = comp.create_cop("block.signature", sig_kids)

        if body_cop is None:
            body_cop = comp.create_cop("statement.define", [])

        # Build body instructions in a separate context
        body_ctx = CodeGenContext()
        body_ctx._build_value_ensure_register(body_cop)

        instr = comp._interp.BuildBlock(
            cop=cop,
            signature_cop=combined_sig,
            body_instructions=body_ctx.instructions
        )
        return self.emit(instr)

    def _build_statement(self, cop):
        """Build statement.define instructions.

        Each kid is a statement.field; evaluate the last one as the result.
        The result is auto-invoked: if callable it is called with empty args,
        otherwise it is returned as-is. This is how (four) calls four.
        An empty statement produces an empty struct.
        """
        field_kids = _cop_kids(cop)

        if not field_kids:
            return self.emit(comp._interp.BuildStruct(cop=cop, fields=[]))

        result = None
        for kid in field_kids:
            if comp.cop_tag(kid) == "statement.field":
                inner = _cop_kids(kid)
                if inner:
                    result = self._build_value_ensure_register(inner[0])
            else:
                result = self._build_value_ensure_register(kid)

        if result is None:
            return self.emit(comp._interp.BuildStruct(cop=cop, fields=[]))

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

            elif tag == "struct.letassign":
                # Kids: [0]=name identifier, [1]=value expression
                let_kids = _cop_kids(kid)
                if len(let_kids) >= 2:
                    name = _extract_name(let_kids[0])
                    if name is not None:
                        value_idx = self._build_value_ensure_register(let_kids[1])
                        self.emit(comp._interp.StoreLocal(cop=kid, name=name, source=value_idx))

            elif tag == "struct.namefield":
                # Kids: [0]=name identifier, [1]=value expression
                field_kids = _cop_kids(kid)
                if len(field_kids) >= 2:
                    name = _extract_name(field_kids[0])
                    if name is not None:
                        value_idx = self._build_value_ensure_register(field_kids[1])
                        fields.append((name, value_idx))

        return self.emit(comp._interp.BuildStruct(cop=cop, fields=fields))

    def _build_shape(self, cop):
        """Build shape construction instructions.

        Shape type constraints are passed as name strings (resolved at execute time),
        not as register indices — so no LoadVar/TryInvoke is emitted for them.
        Defaults are simple constant expressions compiled to register indices.
        """
        kids = _cop_kids(cop)
        fields = []

        for kid in kids:
            tag = comp.cop_tag(kid)

            if tag == "shape.union":
                # Shape union — members are shape name strings or register indices
                member_refs = [_shape_ref_or_reg(self, m) for m in _cop_kids(kid)]
                return self.emit(comp._interp.BuildShapeUnion(cop=cop, member_refs=member_refs))

            elif tag == "shape.field":
                # Named field: name attribute; first kid is shape type, second is default
                name = None
                try:
                    name = kid.to_python("name")
                except (KeyError, AttributeError):
                    pass

                shape_ref = None
                default_idx = None
                field_kids = _cop_kids(kid)
                if len(field_kids) >= 1:
                    shape_ref = _shape_ref_or_reg(self, field_kids[0])
                if len(field_kids) >= 2:
                    default_idx = self._build_value_ensure_register(field_kids[1])

                fields.append((name, shape_ref, default_idx))

        return self.emit(comp._interp.BuildShape(cop=cop, fields=fields))

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
            instr = comp._interp.Const(cop=cop, value=result)
            return self.emit(instr)

    def _build_callable_ensure_register(self, cop):
        """Build a callable reference without auto-invoking it.

        Use this for the callable position in Invoke/PipeInvoke instructions.
        Emits the appropriate load instruction (no TryInvoke) for references,
        locals, and simple identifiers; falls back to _build_value_ensure_register
        for complex expressions.
        """
        tag = cop.positional(0).data.qualified

        if tag in ("value.namespace", "value.reference"):
            try:
                qualified_name = cop.to_python("qualified")
                if isinstance(qualified_name, list):
                    instr = comp._interp.LoadOverload(cop=cop, names=qualified_name)
                else:
                    instr = comp._interp.LoadVar(cop=cop, name=qualified_name)
                return self.emit(instr)
            except (AttributeError, KeyError) as e:
                raise comp.CodeError(f"Invalid callable reference: {e}", cop)

        elif tag == "value.local":
            name = cop.to_python("name")
            result = self.emit(comp._interp.LoadLocal(cop=cop, name=name))
            return _apply_field_access(self, cop, result, _cop_kids(cop))

        elif tag == "value.identifier":
            # Legacy unresolved identifier in callable position — use LoadLocal
            # (consistent with the value-position handling above)
            kids = _cop_kids(cop)
            if not kids:
                raise comp.CodeError("Identifier has no token", cop)
            name = kids[0].to_python("value")
            result = self.emit(comp._interp.LoadLocal(cop=cop, name=name))
            return _apply_field_access(self, cop, result, kids[1:])

        else:
            # Complex expression — build normally; the result is used as-is
            return self._build_value_ensure_register(cop)


def _cop_kids(cop):
    """Extract kids from a COP node (helper function)."""
    return list(cop.field("kids").data.values())


def _shape_ref_or_reg(ctx, cop):
    """Return a shape name string for static shape references, or a register index.

    For value.namespace and value.identifier nodes that refer to a shape by name,
    returns the name string so BuildShape/BuildShapeUnion can resolve it at execute
    time without emitting LoadVar/TryInvoke instructions.
    For anything else, falls back to compiling to a register.
    """
    tag = comp.cop_tag(cop)
    if tag == "value.namespace":
        try:
            qualified = cop.to_python("qualified")
            if isinstance(qualified, str):
                return qualified
        except (KeyError, AttributeError):
            pass
    elif tag == "value.identifier":
        kids = _cop_kids(cop)
        if kids:
            try:
                return kids[0].to_python("value")
            except (KeyError, AttributeError):
                pass
    # Fallback: compile to a register (shouldn't occur for well-formed shape defs)
    return ctx._build_value_ensure_register(cop)


def _extract_name(name_cop):
    """Extract a plain string name from an ident.token or value.identifier kid."""
    tag = comp.cop_tag(name_cop)
    if tag == "ident.token":
        return name_cop.to_python("value")
    elif tag == "value.identifier":
        kids = _cop_kids(name_cop)
        if kids:
            return kids[0].to_python("value")
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
            result = ctx.emit(comp._interp.GetField(cop=cop, field=field_name, struct_reg=result))
        elif field_tag == "ident.index":
            index_str = kid.to_python("value")
            result = ctx.emit(comp._interp.GetIndex(cop=cop, struct_reg=result, index=int(index_str)))
        else:
            raise comp.CodeError(f"Unsupported field access token: {field_tag}", cop)
    return result