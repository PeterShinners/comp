"""Structure literal AST nodes."""

__all__ = ["Structure", "StructOp", "FieldOp", "SpreadOp"]

import comp.engine as comp
from . import _base, _ident


class Structure(_base.ValueNode):
    """Structure literal: {field1=val1 val2 ..spread}

    Evaluates all structure operations and assembles them into a struct dict.
    Operations can be:
    - FieldOp: field assignment (key=value or just value)
    - SpreadOp: spread from another struct (..expr)

    Correct by Construction:
    - ops is a list (can be empty for {})
    - All ops are StructOp instances
    """

    def __init__(self, ops: list['StructOp']):
        """Create structure literal.

        Args:
            ops: List of structure operations (FieldOp, SpreadOp)

        Raises:
            TypeError: If any op is not a StructOp
        """
        if not all(isinstance(op, StructOp) for op in ops):
            raise TypeError("All operations must be StructOp instances")
        self.ops = ops

    def evaluate(self, frame):
        """Evaluate all operations and assemble into struct.

        Creates an accumulator dict and pushes it onto the scope stack.
        Operations access this accumulator to add their contributions.

        Returns comp.Value with the assembled struct dict.
        """
        struct_dict = {}

        # Push accumulator onto scope stack so operations can access it
        # Evaluate each operation - they will populate the accumulator
        for op in self.ops:
            yield comp.Compute(op, struct_accumulator=comp.Value(struct_dict))

        # All operations evaluated successfully - return the struct
        return comp.Value(struct_dict)

    def unparse(self) -> str:
        """Convert back to source code."""
        if not self.ops:
            return "{}"
        # Whitespace separated - no commas in Comp syntax
        ops_str = " ".join(op.unparse() for op in self.ops)
        return f"{{{ops_str}}}"

    def __repr__(self):
        return f"Structure({len(self.ops)} ops)"


class StructOp(_base.ValueNode):
    """Base class for structure operation nodes.

    Structure operations contribute to a structure being built by accessing
    the struct_accumulator scope. They return comp.Value(True) on success, or a
    fail value on error.

    Operations in this family:
    - FieldOp: field assignment (key=value or just value, supports deep paths)
    - SpreadOp: spread fields from another struct (..expr)
    - (future) ScopeOp: scope assignment ($var.path=value)

    This establishes the pattern for all accumulator-based constructs:
    - Structure literals (accumulator = struct dict)
    - Module definitions (accumulator = module scope)
    - Function definitions (accumulator = function registry)
    - Tag/Shape definitions (accumulator = type registry)

    Important: This is different from FieldNode in base.py, which is for
    field ACCESS (reading). StructOp is for field DEFINITION (writing).
    """
    pass


class FieldOp(StructOp):
    """Field assignment operation: key=value or just value

    Represents a field assignment in a structure literal. Can be:
    - Named: key=value (key is single _base.ValueNode or list for deep paths)
    - comp.Unnamed: value (key is None)

    For simple assignment: `{x=5}`, key is String("x")
    For deep assignment: `{one.two.three=5}`, key is list of field nodes
    For unnamed: `{10}`, key is None

    Correct by Construction:
    - key is None (unnamed), _base.ValueNode (simple), or list[FieldNode] (deep path)
    - value is a _base.ValueNode
    """

    def __init__(self, value: _base.ValueNode, key: _base.ValueNode | list | None = None):
        """Create field assignment operation.

        Args:
            value: Expression that evaluates to field value
            key: None (unnamed), _base.ValueNode (simple), or list of field nodes (deep path)

        Raises:
            TypeError: If value is not a _base.ValueNode, or key type is invalid
        """
        if not isinstance(value, _base.AstNode):
            raise TypeError("Field value must be AstNode")

        if key is not None:
            if isinstance(key, list):
                if not key:
                    raise TypeError("Field key list cannot be empty")
                # Deep path - validate items are field nodes
                # TODO: Add validation for field node types
            elif not isinstance(key, _base.AstNode):
                raise TypeError("Field key must be None, AstNode, or list")

        self.key = key
        self.value = value

    def evaluate(self, frame):
        """Evaluate field assignment and add to struct accumulator.

        Handles three cases:
        1. comp.Unnamed: key is None, use comp.Unnamed() as key
        2. Simple named: key is single _base.ValueNode, evaluate and use
        3. Deep path: key is list, walk path creating nested structs
        """
        # Get the accumulator from scope stack
        accumulator = frame.scope('struct_accumulator')
        if accumulator is None or not accumulator.is_struct:
            return comp.fail("FieldOp requires struct_accumulator scope")

        # Evaluate the value first
        value_value = yield comp.Compute(self.value)
        if frame.is_fail(value_value):
            return value_value

        # Case 1: comp.Unnamed field
        if self.key is None:
            accumulator.struct[comp.Unnamed()] = value_value
            return comp.Value(True)

        # Case 2: Simple named field
        if not isinstance(self.key, list):
            key_value = yield comp.Compute(self.key)
            if frame.is_fail(key_value):
                return key_value
            accumulator.struct[key_value] = value_value
            return comp.Value(True)

        # Case 3: Deep path - walk and create nested structures
        # Start at the root accumulator
        current_dict = accumulator.struct

        # Walk all but the last field, creating nested structs as needed
        for field_node in self.key[:-1]:
            # Get the key for this path segment
            key_value = yield from self._evaluate_path_field(frame, field_node, current_dict)
            if frame.is_fail(key_value):
                return key_value

            # Navigate or create nested struct
            if key_value in current_dict:
                current_value = current_dict[key_value]
                # If not a struct, replace with empty struct
                if not current_value.is_struct:
                    current_value = comp.Value({})
                    current_dict[key_value] = current_value
                current_dict = current_value.struct
            else:
                # Create new nested struct
                new_struct = comp.Value({})
                current_dict[key_value] = new_struct
                current_dict = new_struct.struct

        # Handle the final field
        final_field = self.key[-1]
        final_key = yield from self._evaluate_path_field(frame, final_field, current_dict)
        if frame.is_fail(final_key):
            return final_key

        # Assign the value at the final key
        current_dict[final_key] = value_value
        return comp.Value(True)

    def _evaluate_path_field(self, frame, field_node, current_dict):
        """Evaluate a field node in the context of deep path assignment.

        For IndexField: returns existing key at that position (preserves field names)
        For ComputeField: evaluates the expression to compute the key
        For other fields: evaluates normally to get key value

        Args:
            engine: The engine instance
            field_node: Field node to evaluate
            current_dict: Current dict we're navigating in

        Yields:
            comp.Value representing the key for this path segment

        Returns:
            comp.Value (key) or fail value
        """
        if isinstance(field_node, _ident.IndexField):
            # Special handling: get existing key at index position
            keys_list = list(current_dict.keys())
            if not (0 <= field_node.index < len(keys_list)):
                return comp.fail(
                    f"Index #{field_node.index} out of bounds "
                    f"(dict has {len(keys_list)} fields)"
                )
            return keys_list[field_node.index]
        elif isinstance(field_node, _ident.ComputeField):
            # ComputeField: evaluate its expression to get the key
            # This allows: {x.[y+1] = 5} where y is a variable
            key_value = yield comp.Compute(field_node.expr)
            return key_value
        else:
            # Normal field: evaluate to get key
            # This handles String, Number, or any other _base.ValueNode
            key_value = yield comp.Compute(field_node)
            return key_value

    def unparse(self) -> str:
        """Convert back to source code."""
        if self.key is None:
            # comp.Unnamed field
            return self.value.unparse()
        elif isinstance(self.key, list):
            # Deep path
            path_str = "".join(f.unparse() for f in self.key)
            return f"{path_str} = {self.value.unparse()}"
        else:
            # Simple named field
            # Note: spaces around = are optional in Comp, but we use them for clarity
            return f"{self.key.unparse()} = {self.value.unparse()}"

    def __repr__(self):
        if self.key is None:
            return f"FieldOp(unnamed, {self.value})"
        elif isinstance(self.key, list):
            return f"FieldOp({len(self.key)}-deep, {self.value})"
        return f"FieldOp({self.key}, {self.value})"


class SpreadOp(StructOp):
    """Spread operation: ..expr

    Evaluates expression (must be a struct) and merges its fields into
    the struct accumulator.

    Correct by Construction:
    - expr is a _base.ValueNode instance
    """

    def __init__(self, expr: _base.ValueNode):
        """Create spread operation.

        Args:
            expr: Expression that evaluates to a struct to spread

        Raises:
            TypeError: If expr is not a _base.ValueNode
        """
        if not isinstance(expr, _base.AstNode):
            raise TypeError("Spread expression must be AstNode")
        self.expr = expr

    def evaluate(self, frame):
        """Evaluate expression, merge its struct into accumulator."""
        # Get the accumulator from scope stack
        accumulator = frame.scope('struct_accumulator')
        if accumulator is None or not accumulator.is_struct:
            return comp.fail("SpreadOp requires struct_accumulator scope")

        # Evaluate spread expression
        spread_value = yield comp.Compute(self.expr)

        # Runtime check: must be a struct
        if not spread_value.is_struct:
            return comp.fail(f"Cannot spread non-struct value: {spread_value}")

        # Merge into accumulator
        accumulator.struct.update(spread_value.struct)

        # Return success marker
        return comp.Value(True)

    def unparse(self) -> str:
        """Convert back to source code."""
        return f"..{self.expr.unparse()}"

    def __repr__(self):
        return f"SpreadOp({self.expr})"
