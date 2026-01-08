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
                return cop.field("value")
                
            case "value.reference":
                # Load from namespace/environment using qualified name
                try:
                    qualified_name = cop.to_python("qualified")
                    instr = comp._interp.LoadVar(cop=cop, name=qualified_name)
                    return self.emit(instr)
                    
                except (AttributeError, KeyError) as e:
                    raise comp.CodeError(f"Invalid reference: {e}", cop)
            
            case "value.identifier":
                # Unresolved identifier - load as local/parameter variable
                # This happens inside function bodies where parameters and locals
                # haven't been resolved to qualified names
                kids = _cop_kids(cop)
                if kids:
                    token_cop = kids[0]  # ident.token
                    name = token_cop.to_python("value")
                    instr = comp._interp.LoadVar(cop=cop, name=name)
                    return self.emit(instr)
                else:
                    raise comp.CodeError("Identifier has no token", cop)
            
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
                
            case "value.invoke":
                return self._build_invoke(cop)
                
            case "value.pipeline":
                return self._build_pipeline(cop)
                
            case "value.block":
                return self._build_block(cop)
                
            case "struct.define":
                return self._build_struct(cop)
                
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
    
    def _build_invoke(self, cop):
        """Build function invocation instructions."""
        kids = _cop_kids(cop)
        callable_cop = kids[0]
        
        # Build the callable
        callable_idx = self._build_value_ensure_register(callable_cop)
        
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
            
            if stage_tag == "value.invoke":
                # Piped invoke: callable(args) with piped input
                invoke_kids = _cop_kids(stage_cop)
                callable_cop = invoke_kids[0]
                callable_idx = self._build_value_ensure_register(callable_cop)
                
                # Build args (remaining kids after callable)
                if len(invoke_kids) > 1:
                    arg_idx = self._build_value_ensure_register(invoke_kids[1])
                else:
                    # Empty args struct
                    arg_idx = self.emit(comp._interp.BuildStruct(cop=stage_cop, fields=[]))
                
                # PipeInvoke passes result as piped input
                instr = comp._interp.PipeInvoke(
                    cop=stage_cop,
                    callable=callable_idx,
                    piped=result,
                    args=arg_idx
                )
                result = self.emit(instr)
            else:
                # Non-invoke stage - just evaluate it (unusual but allowed)
                result = self._build_value_ensure_register(stage_cop)
        
        return result
    
    def _build_block(self, cop):
        """Build block/function instructions."""
        kids = _cop_kids(cop)
        signature_cop = kids[0]  # shape definition
        body_cop = kids[1]       # struct definition with body
        
        # Build body instructions in a separate context
        body_ctx = CodeGenContext()
        body_ctx._build_value(body_cop)
        
        instr = comp._interp.BuildBlock(
            cop=cop,
            signature_cop=signature_cop,
            body_instructions=body_ctx.instructions
        )
        return self.emit(instr)
    
    def _build_struct(self, cop):
        """Build struct construction instructions."""
        kids = _cop_kids(cop)
        fields = []
        
        for kid in kids:
            tag = kid.positional(0).data.qualified
            
            if tag == "struct.posfield":
                # Positional field: (struct.posfield kids=(value))
                field_kids = _cop_kids(kid)
                if field_kids:
                    value_idx = self._build_value_ensure_register(field_kids[0])
                    fields.append((comp.Unnamed(), value_idx))
                    
            elif tag == "struct.letassign":
                # Local variable assignment: !let name=value
                # Kids are positional: [name_cop, value_cop]
                let_kids = _cop_kids(kid)
                if len(let_kids) >= 2:
                    name_cop = let_kids[0]  # value.identifier with the variable name
                    value_cop = let_kids[1]  # expression for the value
                    
                    # Extract the variable name from the identifier
                    name_kids = _cop_kids(name_cop)
                    if name_kids:
                        token_cop = name_kids[0]  # ident.token
                        name = token_cop.to_python("value")
                        
                        # Generate code for the value
                        value_idx = self._build_value_ensure_register(value_cop)
                        
                        # Store as local variable
                        store_instr = comp._interp.StoreVar(
                            cop=kid,
                            name=name,
                            source=value_idx
                        )
                        self.emit(store_instr)
                # !let doesn't produce a field in the struct
                
            elif tag == "struct.namefield":
                # Named field: name=value
                # Kids are [name_cop, value_cop] (in order: n=, v=)
                field_kids = _cop_kids(kid)
                if len(field_kids) >= 2:
                    name_cop = field_kids[0]  # value.identifier with the field name
                    value_cop = field_kids[1]  # expression for the value
                    
                    # Extract the field name from the identifier
                    name_kids = _cop_kids(name_cop)
                    if name_kids:
                        token_cop = name_kids[0]  # ident.token
                        name = token_cop.to_python("value")
                        
                        value_idx = self._build_value_ensure_register(value_cop)
                        fields.append((name, value_idx))
        
        instr = comp._interp.BuildStruct(cop=cop, fields=fields)
        return self.emit(instr)
    
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


def _cop_kids(cop):
    """Extract kids from a COP node (helper function)."""
    return list(cop.field("kids").data.values())