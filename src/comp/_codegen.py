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
    
    Args:
        cop: (Value) cop nodes
        
    Returns:
        List[Instruction]: Instruction sequence to compute the definition
    """
    # Create a code generation context
    ctx = CodeGenContext()
    
    # Generate instructions for the definition's resolved COP
    result_reg = ctx.build_expression(cop)
    
    # Add a final StoreVar to bind the result to the definition name  
    store_instr = comp._interp.StoreVar(
        cop=cop,
        name="return", 
        source=result_reg
    )
    ctx.instructions.append(store_instr)
    
    return ctx.instructions


class CodeGenContext:
    """Code generation context for a single definition.
    
    This replaces the Builder pattern with a cleaner approach.
    Context is immutable once created - no state mutation.
    """
    
    def __init__(self):
        self.instructions = []
        self._next_register = 0
    
    def gen_register(self):
        """Generate a unique register name."""
        name = f"%{self._next_register}"
        self._next_register += 1
        return name
    
    def build_expression(self, cop):
        """Build instructions for an expression COP.
        
        Returns the register name containing the final result.
        """
        return self._build_value(cop)
    
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
                    dest = self.gen_register()
                    
                    instr = comp._interp.LoadVar(cop=cop, name=qualified_name, dest=dest)
                    self.instructions.append(instr)
                    return dest
                    
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
                    dest = self.gen_register()
                    
                    instr = comp._interp.LoadVar(cop=cop, name=name, dest=dest)
                    self.instructions.append(instr)
                    return dest
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
        
        dest = self.gen_register()
        instr = comp._interp.BinOp(cop=cop, op=op, left=left, right=right, dest=dest)
        self.instructions.append(instr)
        return dest
    
    def _build_unary_op(self, cop):
        """Build unary operation instructions.""" 
        op = cop.to_python("op")
        kids = _cop_kids(cop)
        
        operand = self._build_value_ensure_register(kids[0])
        
        dest = self.gen_register()
        instr = comp._interp.UnOp(cop=cop, op=op, operand=operand, dest=dest)
        self.instructions.append(instr)
        return dest
    
    def _build_invoke(self, cop):
        """Build function invocation instructions."""
        kids = _cop_kids(cop)
        callable_cop = kids[0]
        
        # Build the callable
        callable_reg = self._build_value_ensure_register(callable_cop)
        
        # Process each argument as a separate call
        result = callable_reg
        for arg_cop in kids[1:]:
            arg_reg = self._build_value_ensure_register(arg_cop)
            
            dest = self.gen_register() 
            instr = comp._interp.Invoke(cop=cop, callable=result, args=arg_reg, dest=dest)
            self.instructions.append(instr)
            result = dest
            
        return result
    
    def _build_block(self, cop):
        """Build block/function instructions."""
        kids = _cop_kids(cop)
        signature_cop = kids[0]  # shape definition
        body_cop = kids[1]       # struct definition with body
        
        # Build body instructions in a separate context
        body_ctx = CodeGenContext()
        body_ctx._build_value(body_cop)
        
        dest = self.gen_register()
        instr = comp._interp.BuildBlock(
            cop=cop,
            signature_cop=signature_cop,
            body_instructions=body_ctx.instructions,
            dest=dest
        )
        self.instructions.append(instr)
        return dest
    
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
                    value_reg = self._build_value_ensure_register(field_kids[0])
                    # Use unnamed key for positional field
                    fields.append((comp.Unnamed(), value_reg))
                    
            elif tag == "struct.letassign":
                # Local variable assignment: !let name=value
                # Kids are positional: [name_cop, value_cop]
                kids = _cop_kids(kid)
                if len(kids) >= 2:
                    name_cop = kids[0]  # value.identifier with the variable name
                    value_cop = kids[1]  # expression for the value
                    
                    # Extract the variable name from the identifier
                    name_kids = _cop_kids(name_cop)
                    if name_kids:
                        token_cop = name_kids[0]  # ident.token
                        name = token_cop.to_python("value")
                        
                        # Generate code for the value
                        value_reg = self._build_value_ensure_register(value_cop)
                        
                        # Store as local variable
                        store_instr = comp._interp.StoreVar(
                            cop=kid,
                            name=name,
                            source=value_reg
                        )
                        self.instructions.append(store_instr)
                # !let doesn't produce a field in the struct
                
            elif tag == "struct.namedfield":
                # Named field: name=value
                name = kid.to_python("name")
                field_kids = _cop_kids(kid)
                if field_kids:
                    value_reg = self._build_value_ensure_register(field_kids[0])
                    fields.append((name, value_reg))
        
        dest = self.gen_register()
        instr = comp._interp.BuildStruct(cop=cop, fields=fields, dest=dest)
        self.instructions.append(instr)
        return dest
    
    def _build_value_ensure_register(self, cop):
        """Build a value and ensure it's in a register.
        
        If the value is a constant, emit a Const instruction to load it.
        """
        result = self._build_value(cop)
        
        if isinstance(result, str):
            # Already a register
            return result
        else:
            # Constant value - load into register
            dest = self.gen_register()
            instr = comp._interp.Const(cop=cop, value=result, dest=dest)
            self.instructions.append(instr)
            return dest


def _cop_kids(cop):
    """Extract kids from a COP node (helper function)."""
    return list(cop.field("kids").data.values())