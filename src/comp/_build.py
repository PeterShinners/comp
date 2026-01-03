"""Build Comp cop structures into executable instruction sequences.

The builder transforms COP nodes (the parse tree) into a linear sequence
of Instruction objects that can be executed by the interpreter.

Build process responsibilities:
- Resolve all variable references (no runtime lookups)
- Fold constants where possible (already done by resolve())
- Generate register names for temporaries
- Transform nested expressions into linear instruction streams
- Maintain source location info for error reporting

The builder assumes the COP tree has already been through the resolve()
pass, which handles constant folding and some optimizations.
"""


__all__ = [
    "build",
    "Builder",
]

import comp


def build(cop, namespace=None):
    """Build cop structures into instruction sequence.

    Args:
        cop: (Value) Cop structure to build (should be resolved first)
        namespace: (Value) Namespace for resolving identifiers (optional)

    Returns:
        List of Instruction objects
    """
    builder = Builder(namespace)
    builder.build_expr(cop)
    return builder.instructions


class Builder:
    """Builds COP nodes into instruction sequences.

    Attributes:
        instructions: List of generated instructions
        namespace: Namespace for variable resolution
        next_register: Counter for generating unique register names
    """

    def __init__(self, namespace=None):
        self.instructions = []
        self.namespace = namespace
        self.next_register = 0

    def gen_register(self):
        """Generate a unique register name.

        Returns:
            (str) Register name like "%0", "%1", etc.
        """
        name = f"%{self.next_register}"
        self.next_register += 1
        return name

    def build_expr(self, cop):
        """Build an expression COP into instructions.

        This is the main entry point. It delegates to _build_value which
        returns either a Value (for constants) or a register name (str).
        Then this method ensures an instruction is emitted if needed.

        Args:
            cop: COP node to build

        Returns:
            (str) Register name containing the result
        """
        result = self._build_value(cop)

        # If we got a constant Value back, emit a Const instruction
        if not isinstance(result, str):
            dest = self.gen_register()
            instr = comp._interp.Const(cop=cop, value=result, dest=dest)
            self.instructions.append(instr)
            return dest

        return result

    def _build_value(self, cop):
        """Build a value from a COP node.

        This is the internal builder that returns either:
        - A Value (for inlineable constants)
        - A register name string (for computed values)

        The caller is responsible for ensuring instructions get emitted.

        Args:
            cop: COP node to build

        Returns:
            (Value or str) Either a constant Value or a register name
        """
        tag = cop.positional(0).data.qualified

        match tag:
            case "value.constant":
                # Return the constant directly for inlining
                return cop.field("value")

            case "value.reference":
                # Handle references to definitions
                try:
                    definition = cop.field("definition")

                    # If definition has a folded constant value, use it
                    if hasattr(definition, 'value') and definition.value is not None:
                        return definition.value

                    # If definition has resolved_cop, build from that
                    if hasattr(definition, 'resolved_cop') and definition.resolved_cop is not None:
                        return self._build_value(definition.resolved_cop)

                    # If definition has original_cop, build from that
                    if hasattr(definition, 'original_cop') and definition.original_cop is not None:
                        return self._build_value(definition.original_cop)

                    # Shouldn't reach here - unresolved reference
                    raise comp.CodeError(f"Unresolved reference to {definition.qualified}", cop)
                except (AttributeError, KeyError) as e:
                    raise comp.CodeError(f"Invalid value.reference node: {e}", cop)

            case "value.number":
                # Convert to constant Value
                import decimal
                literal = cop.to_python("value")
                return comp.Value.from_python(decimal.Decimal(literal))

            case "value.text":
                # Convert to constant Value
                literal = cop.to_python("value")
                return comp.Value.from_python(literal)

            case "value.math.binary":
                op = cop.to_python("op")
                kids = _cop_kids(cop)

                # Build operands - these can be Values or register names
                left = self._build_value(kids[0])
                right = self._build_value(kids[1])

                # Emit the operation
                dest = self.gen_register()
                instr = comp._interp.BinOp(cop=cop, op=op, left=left, right=right, dest=dest)
                self.instructions.append(instr)
                return dest

            case "value.math.unary":
                op = cop.to_python("op")
                kids = _cop_kids(cop)

                # Build operand
                operand = self._build_value(kids[0])

                # Emit the operation
                dest = self.gen_register()
                instr = comp._interp.UnOp(cop=cop, op=op, operand=operand, dest=dest)
                self.instructions.append(instr)
                return dest

            case "value.invoke":
                # invoke: callable (struct block* | block+)
                # This creates potentially multiple nested calls
                kids = _cop_kids(cop)
                callable_cop = kids[0]

                # Build the callable
                result = self._build_value(callable_cop)

                # Process each argument (struct or block) as a separate call
                for arg_cop in kids[1:]:
                    # For invoke arguments, we need to preserve struct structure
                    # Don't let struct.define unwrap single-field structs
                    arg_tag = arg_cop.positional(0).data.qualified

                    if arg_tag == "struct.define":
                        # Force struct building without unwrapping
                        arg_val = self._build_struct(arg_cop)
                    else:
                        # Block or other value
                        arg_val = self._build_value(arg_cop)

                    # Emit Invoke instruction for this call
                    dest = self.gen_register()
                    instr = comp._interp.Invoke(cop=cop, callable=result, args=arg_val, dest=dest)
                    self.instructions.append(instr)
                    result = dest

                return result

            case "value.block":
                # Block value (anonymous function) - compile it now
                kids = _cop_kids(cop)
                signature_cop = kids[0]  # "s"
                body_cop = kids[1]       # "b"

                # Build the body into instructions (in a separate builder to keep instructions separate)
                body_builder = Builder(namespace=self.namespace)
                # Use build_expr to ensure we get an instruction even for constants
                body_builder.build_expr(body_cop)

                # Emit BuildBlock instruction
                dest = self.gen_register()
                instr = comp._interp.BuildBlock(
                    cop=cop,
                    signature_cop=signature_cop,
                    body_instructions=body_builder.instructions,
                    dest=dest
                )
                self.instructions.append(instr)
                return dest

            case "value.identifier":
                # Variable reference
                kids = _cop_kids(cop)
                if not kids:
                    raise ValueError("Empty identifier")

                # Single identifier - simple variable reference
                if len(kids) == 1:
                    name = kids[0].to_python("value")
                    dest = self.gen_register()
                    instr = comp._interp.LoadVar(cop=cop, name=name, dest=dest)
                    self.instructions.append(instr)
                    return dest

                # Multi-part identifier - check if it's a scoped variable reference
                if len(kids) >= 2:
                    scope = kids[0].to_python("value")
                    if scope == "var":
                        # Variable reference: var.x
                        if len(kids) > 2:
                            raise ValueError("Cannot reference multi-field variable yet (e.g., var.x.y)")
                        name = kids[1].to_python("value")

                        # Emit LoadVar instruction
                        dest = self.gen_register()
                        instr = comp._interp.LoadVar(cop=cop, name=name, dest=dest)
                        self.instructions.append(instr)
                        return dest
                    else:
                        raise ValueError(f"Unknown scope in identifier: {scope}")

                raise ValueError(f"Cannot handle identifier with {len(kids)} parts")

            case "mod.define":
                # Module with multiple top-level expressions/statements
                # Build each and return the last one
                kids = _cop_kids(cop)
                result = None
                for kid in kids:
                    kid_tag = kid.positional(0).data.qualified
                    if kid_tag in ("stmt.assign", "struct.letassign"):
                        self.build_stmt(kid)
                    else:
                        result = self._build_value(kid)
                return result if result is not None else comp.Value.from_python(None)

            case "struct.define":
                # Build struct value
                kids = _cop_kids(cop)

                # Check if this is a statement block (has let assigns or stmt.assign)
                # vs a data struct
                has_statements = False
                for field_cop in kids:
                    field_tag = field_cop.positional(0).data.qualified
                    if field_tag == "struct.letassign":
                        has_statements = True
                        break
                    if field_tag == "struct.posfield":
                        field_kids = _cop_kids(field_cop)
                        if field_kids:
                            value_tag = field_kids[0].positional(0).data.qualified
                            if value_tag == "stmt.assign":
                                has_statements = True
                                break

                # If it's a statement block, execute statements and wrap result in struct
                if has_statements:
                    result = None
                    result_key = None
                    for field_cop in kids:
                        field_tag = field_cop.positional(0).data.qualified
                        field_kids = _cop_kids(field_cop)

                        if field_tag == "struct.posfield":
                            value_cop = field_kids[0]
                            value_tag = value_cop.positional(0).data.qualified

                            if value_tag == "stmt.assign":
                                self.build_stmt(value_cop)
                                result = None
                                result_key = None
                            else:
                                result = self._build_value(value_cop)
                                result_key = comp.Unnamed()
                        elif field_tag == "struct.letassign":
                            self.build_stmt(field_cop)
                            result = None
                            result_key = None
                        elif field_tag == "struct.namefield":
                            result = self._build_value(field_kids[1])
                            name_cop = field_kids[0]
                            result_key = _get_simple_field_name(name_cop)
                        else:
                            raise ValueError(f"Cannot build struct field type: {field_tag}")

                    # Wrap the final result in a struct (if there is one)
                    if result is not None:
                        dest = self.gen_register()
                        instr = comp._interp.BuildStruct(cop=cop, fields=[(result_key, result)], dest=dest)
                        self.instructions.append(instr)
                        return dest
                    else:
                        # No result - return empty struct
                        dest = self.gen_register()
                        instr = comp._interp.BuildStruct(cop=cop, fields=[], dest=dest)
                        self.instructions.append(instr)
                        return dest

                # Otherwise, build a struct value
                fields = []
                for field_cop in kids:
                    field_tag = field_cop.positional(0).data.qualified
                    field_kids = _cop_kids(field_cop)

                    if field_tag == "struct.posfield":
                        # Positional field
                        value = self._build_value(field_kids[0])
                        fields.append((comp.Unnamed(), value))
                    elif field_tag == "struct.namefield":
                        # Named field: name = value
                        name_cop = field_kids[0]
                        value_cop = field_kids[1]
                        # Extract name - for now assume simple identifier
                        name = _get_simple_field_name(name_cop)
                        value = self._build_value(value_cop)
                        fields.append((name, value))
                    else:
                        raise ValueError(f"Cannot build struct field type: {field_tag}")

                # Emit BuildStruct instruction
                dest = self.gen_register()
                instr = comp._interp.BuildStruct(cop=cop, fields=fields, dest=dest)
                self.instructions.append(instr)
                return dest

            case _:
                raise ValueError(f"Cannot build code for: {tag}")

    def _build_struct(self, cop):
        """Build a struct without unwrapping single-field structs.

        This is used for function arguments where we need to preserve
        the struct structure even for single fields like (0).

        Args:
            cop: struct.define COP node

        Returns:
            (str) Register name containing the struct
        """
        kids = _cop_kids(cop)

        # Check if this is a statement block vs data struct
        has_statements = False
        for field_cop in kids:
            field_tag = field_cop.positional(0).data.qualified
            if field_tag == "struct.letassign":
                has_statements = True
                break
            if field_tag == "struct.posfield":
                field_kids = _cop_kids(field_cop)
                if field_kids:
                    value_tag = field_kids[0].positional(0).data.qualified
                    if value_tag == "stmt.assign":
                        has_statements = True
                        break

        # Statement blocks shouldn't be used as invoke arguments
        if has_statements:
            raise ValueError("Cannot use statement block as function argument")

        # Build a data struct
        fields = []
        for field_cop in kids:
            field_tag = field_cop.positional(0).data.qualified
            field_kids = _cop_kids(field_cop)

            if field_tag == "struct.posfield":
                # Positional field
                value = self._build_value(field_kids[0])
                fields.append((comp.Unnamed(), value))
            elif field_tag == "struct.namefield":
                # Named field: name = value
                name_cop = field_kids[0]
                value_cop = field_kids[1]
                name = _get_simple_field_name(name_cop)
                value = self._build_value(value_cop)
                fields.append((name, value))
            else:
                raise ValueError(f"Cannot build struct field type: {field_tag}")

        # Emit BuildStruct instruction
        dest = self.gen_register()
        instr = comp._interp.BuildStruct(cop=cop, fields=fields, dest=dest)
        self.instructions.append(instr)
        return dest

    def build_stmt(self, cop):
        """Build a statement COP into instructions.

        Statements don't return values but may have side effects.

        Args:
            cop: COP node to build
        """
        tag = cop.positional(0).data.qualified

        match tag:
            case "struct.letassign":
                # !let variable assignment
                # COP structure: struct.letassign with kids being a positional struct (n, v)
                kids_struct = cop.data[comp.Value.from_python("kids")]
                # Kids are positional - first is name, second is value
                name_cop = kids_struct.positional(0)
                value_cop = kids_struct.positional(1)

                # Extract variable name from identifier
                name_tag = name_cop.positional(0).data.qualified
                if name_tag == "value.identifier":
                    name_kids = _cop_kids(name_cop)
                    if len(name_kids) != 1:
                        raise ValueError("!let variable name must be a simple identifier")
                    name = name_kids[0].to_python("value")
                else:
                    raise ValueError(f"!let variable name must be identifier, got: {name_tag}")

                # Build the rvalue expression
                source = self._build_value(value_cop)

                # Store to variable
                instr = comp._interp.StoreVar(cop=cop, name=name, source=source)
                self.instructions.append(instr)

            case "stmt.assign":
                kids = _cop_kids(cop)
                lvalue = kids[0]
                rvalue = kids[1]

                # Extract scope and variable name from lvalue
                # Must be dotted identifier like mod.x or mod.foo.bar
                lvalue_tag = lvalue.positional(0).data.qualified
                if lvalue_tag == "value.identifier":
                    lvalue_kids = _cop_kids(lvalue)
                    if len(lvalue_kids) < 2:
                        raise ValueError("Scope assignment requires dotted identifier (e.g., mod.x)")

                    # First field is the scope (var, ctx, mod, pkg, tag, startup)
                    scope = lvalue_kids[0].to_python("value")
                    if scope not in ("var", "ctx", "mod", "pkg", "tag", "startup"):
                        raise ValueError(f"Invalid scope: {scope}. Must be var, ctx, mod, pkg, tag, or startup")

                    # For now, only support var scope in struct context
                    if scope != "var":
                        raise ValueError(f"Only var scope is supported in expressions, got: {scope}")

                    # Rest of the identifier is the variable name (just second field for now)
                    if len(lvalue_kids) > 2:
                        raise ValueError("Cannot assign to multi-field variable yet (e.g., mod.x.y)")

                    name = lvalue_kids[1].to_python("value")
                else:
                    raise ValueError(f"Cannot assign to non-identifier: {lvalue_tag}")

                # Build the rvalue expression
                source = self._build_value(rvalue)

                # Store to variable
                instr = comp._interp.StoreVar(cop=cop, name=name, source=source)
                self.instructions.append(instr)

            case _:
                # Try as expression statement
                self.build_expr(cop)


def _get_simple_field_name(name_cop):
    """Extract a simple field name from a name COP.

    Args:
        name_cop: COP node representing the field name (identifier, text, etc.)

    Returns:
        (str) The field name as a string
    """
    tag = name_cop.positional(0).data.qualified

    if tag == "value.identifier":
        # Simple identifier like "foo"
        kids = _cop_kids(name_cop)
        if len(kids) == 1:
            return kids[0].to_python("value")
        # Multi-part identifier - not supported for field names
        raise ValueError(f"Complex identifiers not supported as field names")
    elif tag == "value.text" or tag == "value.constant":
        # Text literal or constant
        return name_cop.to_python("value")
    else:
        raise ValueError(f"Cannot extract field name from: {tag}")


def _cop_kids(cop):
    """Get kids of a cop node.

    Returns:
        (list) List of child COP nodes (positional values from kids struct)
    """
    kids_val = cop.field("kids")
    if kids_val is None:
        return []
    # kids is a struct, get its positional values (ignoring names like "l", "r")
    kids = []
    for i in range(len(kids_val.data)):
        kids.append(kids_val.positional(i))
    return kids
