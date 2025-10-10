"""Structure literal AST nodes.

Structures are immutable collections with named and unnamed fields.
Field keys can be any Value (strings, tags, numbers, etc.).

Structure evaluation builds a new struct by evaluating all field expressions
and collecting them into a dict. No engine changes needed - this is pure
ValueNode coordination.
"""

from .base import ValueNode
from ..value import Value, Unnamed


class Structure(ValueNode):
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

    def evaluate(self, engine):
        """Evaluate all operations and assemble into struct.

        Creates an accumulator dict and pushes it onto the scope stack.
        Operations access this accumulator to add their contributions.

        Returns Value with the assembled struct dict.
        """
        struct_dict = {}

        # Push accumulator onto scope stack so operations can access it
        with engine.scope_frame(struct_accumulator=Value(struct_dict)):
            # Evaluate each operation - they will populate the accumulator
            for op in self.ops:
                result = yield op

                # Operations return Value(True) on success, or fail
                if engine.is_fail(result):
                    return result

        # All operations evaluated successfully - return the struct
        return Value(struct_dict)

    def unparse(self) -> str:
        """Convert back to source code."""
        if not self.ops:
            return "{}"
        # Whitespace separated - no commas in Comp syntax
        ops_str = " ".join(op.unparse() for op in self.ops)
        return f"{{{ops_str}}}"

    def __repr__(self):
        return f"Structure({len(self.ops)} ops)"


class StructOp(ValueNode):
    """Base class for structure operation nodes.

    Structure operations contribute to a structure being built by accessing
    the struct_accumulator scope. They return Value(True) on success, or a
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
    - Named: key=value (key is single ValueNode or list for deep paths)
    - Unnamed: value (key is None)

    For simple assignment: `{x=5}`, key is String("x")
    For deep assignment: `{one.two.three=5}`, key is list of field nodes
    For unnamed: `{10}`, key is None

    Correct by Construction:
    - key is None (unnamed), ValueNode (simple), or list[FieldNode] (deep path)
    - value is a ValueNode
    """

    def __init__(self, value: ValueNode, key: ValueNode | list | None = None):
        """Create field assignment operation.

        Args:
            value: Expression that evaluates to field value
            key: None (unnamed), ValueNode (simple), or list of field nodes (deep path)

        Raises:
            TypeError: If value is not a ValueNode, or key type is invalid
        """
        from .base import AstNode
        if not isinstance(value, AstNode):
            raise TypeError("Field value must be AstNode")

        if key is not None:
            if isinstance(key, list):
                if not key:
                    raise TypeError("Field key list cannot be empty")
                # Deep path - validate items are field nodes
                # TODO: Add validation for field node types
            elif not isinstance(key, AstNode):
                raise TypeError("Field key must be None, AstNode, or list")

        self.key = key
        self.value = value

    def evaluate(self, engine):
        """Evaluate field assignment and add to struct accumulator.

        Handles three cases:
        1. Unnamed: key is None, use Unnamed() as key
        2. Simple named: key is single ValueNode, evaluate and use
        3. Deep path: key is list, walk path creating nested structs
        """
        # Get the accumulator from scope stack
        accumulator = engine.get_scope('struct_accumulator')
        if accumulator is None or not accumulator.is_struct:
            return engine.fail("FieldOp requires struct_accumulator scope")

        # Evaluate the value first
        value_value = yield self.value
        if engine.is_fail(value_value):
            return value_value

        # Case 1: Unnamed field
        if self.key is None:
            accumulator.struct[Unnamed()] = value_value
            return Value(True)

        # Case 2: Simple named field
        if not isinstance(self.key, list):
            key_value = yield self.key
            if engine.is_fail(key_value):
                return key_value
            accumulator.struct[key_value] = value_value
            return Value(True)

        # Case 3: Deep path - walk and create nested structures
        # Start at the root accumulator
        current_dict = accumulator.struct

        # Walk all but the last field, creating nested structs as needed
        for field_node in self.key[:-1]:
            # Get the key for this path segment
            key_value = yield from self._evaluate_path_field(engine, field_node, current_dict)
            if engine.is_fail(key_value):
                return key_value

            # Navigate or create nested struct
            if key_value in current_dict:
                current_value = current_dict[key_value]
                # If not a struct, replace with empty struct
                if not current_value.is_struct:
                    current_value = Value({})
                    current_dict[key_value] = current_value
                current_dict = current_value.struct
            else:
                # Create new nested struct
                new_struct = Value({})
                current_dict[key_value] = new_struct
                current_dict = new_struct.struct

        # Handle the final field
        final_field = self.key[-1]
        final_key = yield from self._evaluate_path_field(engine, final_field, current_dict)
        if engine.is_fail(final_key):
            return final_key

        # Assign the value at the final key
        current_dict[final_key] = value_value
        return Value(True)

    def _evaluate_path_field(self, engine, field_node, current_dict):
        """Evaluate a field node in the context of deep path assignment.

        For IndexField: returns existing key at that position (preserves field names)
        For ComputeField: evaluates the expression to compute the key
        For other fields: evaluates normally to get key value

        Args:
            engine: The engine instance
            field_node: Field node to evaluate
            current_dict: Current dict we're navigating in

        Yields:
            Value representing the key for this path segment

        Returns:
            Value (key) or fail value
        """
        from .identifiers import IndexField, ComputeField

        if isinstance(field_node, IndexField):
            # Special handling: get existing key at index position
            keys_list = list(current_dict.keys())
            if not (0 <= field_node.index < len(keys_list)):
                return engine.fail(
                    f"Index #{field_node.index} out of bounds "
                    f"(dict has {len(keys_list)} fields)"
                )
            return keys_list[field_node.index]
        elif isinstance(field_node, ComputeField):
            # ComputeField: evaluate its expression to get the key
            # This allows: {x.[y+1] = 5} where y is a variable
            key_value = yield field_node.expr
            if engine.is_fail(key_value):
                return key_value
            return key_value
        else:
            # Normal field: evaluate to get key
            # This handles String, Number, or any other ValueNode
            key_value = yield field_node
            return key_value

    def unparse(self) -> str:
        """Convert back to source code."""
        if self.key is None:
            # Unnamed field
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
    - expr is a ValueNode instance
    """

    def __init__(self, expr: ValueNode):
        """Create spread operation.

        Args:
            expr: Expression that evaluates to a struct to spread

        Raises:
            TypeError: If expr is not a ValueNode
        """
        from .base import AstNode
        if not isinstance(expr, AstNode):
            raise TypeError("Spread expression must be AstNode")
        self.expr = expr

    def evaluate(self, engine):
        """Evaluate expression, merge its struct into accumulator."""
        # Get the accumulator from scope stack
        accumulator = engine.get_scope('struct_accumulator')
        if accumulator is None or not accumulator.is_struct:
            return engine.fail("SpreadOp requires struct_accumulator scope")

        # Evaluate spread expression
        spread_value = yield self.expr
        if engine.is_fail(spread_value):
            return spread_value

        # Runtime check: must be a struct
        if not spread_value.is_struct:
            return engine.fail(f"Cannot spread non-struct value: {spread_value}")

        # Merge into accumulator
        accumulator.struct.update(spread_value.struct)

        # Return success marker
        return Value(True)

    def unparse(self) -> str:
        """Convert back to source code."""
        return f"..{self.expr.unparse()}"

    def __repr__(self):
        return f"SpreadOp({self.expr})"
