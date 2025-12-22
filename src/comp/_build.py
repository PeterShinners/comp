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
import comp._interp


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

            case "value.identifier":
                # Variable reference
                kids = _cop_kids(cop)
                if not kids:
                    raise ValueError("Empty identifier")

                # Check if it's a scoped variable reference (var.x)
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

                # Simple identifier (legacy support or other uses)
                name = kids[0].to_python("value")
                dest = self.gen_register()
                instr = comp._interp.LoadVar(cop=cop, name=name, dest=dest)
                self.instructions.append(instr)
                return dest

            case "struct.define":
                # Build struct - handle as sequence of statements/expressions
                kids = _cop_kids(cop)

                # Single field case - just unwrap (parenthesized expressions)
                if len(kids) == 1:
                    field_cop = kids[0]
                    field_tag = field_cop.positional(0).data.qualified
                    if field_tag == "struct.posfield":
                        field_kids = _cop_kids(field_cop)
                        return self._build_value(field_kids[0])

                # Multi-field case - build each field, return last one's value
                result = None
                for field_cop in kids:
                    field_tag = field_cop.positional(0).data.qualified
                    field_kids = _cop_kids(field_cop)

                    if field_tag == "struct.posfield":
                        # Check if it's a statement or expression
                        value_cop = field_kids[0]
                        value_tag = value_cop.positional(0).data.qualified

                        if value_tag == "stmt.assign":
                            # Build as statement (no return value needed)
                            self.build_stmt(value_cop)
                            result = None  # Statements don't have values
                        else:
                            # Build as expression
                            result = self._build_value(value_cop)
                    else:
                        raise ValueError(f"Cannot build struct field type: {field_tag}")

                # Return the last expression's result (or None if last was statement)
                return result if result is not None else comp.Value.from_python(None)

            case _:
                raise ValueError(f"Cannot build code for: {tag}")

    def build_stmt(self, cop):
        """Build a statement COP into instructions.

        Statements don't return values but may have side effects.

        Args:
            cop: COP node to build
        """
        tag = cop.positional(0).data.qualified

        match tag:
            case "stmt.assign":
                kids = _cop_kids(cop)
                lvalue = kids[0]
                rvalue = kids[1]

                # Extract scope and variable name from lvalue
                # Must be dotted identifier like var.x or var.foo.bar
                lvalue_tag = lvalue.positional(0).data.qualified
                if lvalue_tag == "value.identifier":
                    lvalue_kids = _cop_kids(lvalue)
                    if len(lvalue_kids) < 2:
                        raise ValueError("Scope assignment requires dotted identifier (e.g., var.x)")

                    # First field is the scope (var, ctx, mod, pkg, tag, startup)
                    scope = lvalue_kids[0].to_python("value")
                    if scope not in ("var", "ctx", "mod", "pkg", "tag", "startup"):
                        raise ValueError(f"Invalid scope: {scope}. Must be var, ctx, mod, pkg, tag, or startup")

                    # For now, only support var scope in struct context
                    if scope != "var":
                        raise ValueError(f"Only var scope is supported in expressions, got: {scope}")

                    # Rest of the identifier is the variable name (just second field for now)
                    if len(lvalue_kids) > 2:
                        raise ValueError("Cannot assign to multi-field variable yet (e.g., var.x.y)")

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
