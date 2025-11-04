"""Structure literal AST nodes."""

__all__ = ["Structure", "Block", "StructOp", "FieldOp", "SpreadOp"]

import comp

from . import _base, _ident, _literal


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
        out_struct = comp.Value({})
        for op in self.ops:
            yield comp.Compute(op, disarm_bypass=frame.disarm_bypass, struct_accumulator=out_struct)
        return out_struct

    def unparse(self) -> str:
        """Convert back to source code."""
        if not self.ops:
            return "{}"
        ops_str = " ".join(op.unparse() for op in self.ops)
        return f"{{{ops_str}}}"

    def __repr__(self):
        return f"Structure({len(self.ops)} ops)"


class Block(_base.ValueNode):
    """Block literal: :{field1=val1 val2 ..spread}

    Blocks are deferred structure definitions used for callbacks, control flow,
    and stream generation. They have the same operations as structures but don't
    execute immediately. Instead, they capture their definition context and return
    a RawBlock that can be invoked later using the |: operator.

    Blocks are "raw" until typed with an input shape. The typing happens
    through morphing: RawBlock + BlockShape → Block. This commonly occurs when
    blocks are used as function arguments.

    Correct by Construction:
    - body is a Structure AST node
    """

    def __init__(self, body: Structure):
        """Create block literal.

        Args:
            body (Structure): Structure AST node containing the block's operations

        Raises:
            TypeError: If body is not a Structure instance
        """
        if not isinstance(body, Structure):
            raise TypeError("Block requires a Structure body")
        self.body = body

    def evaluate(self, frame):
        """Create a RawBlock that captures context for later typing and invocation.

        Unlike Structure which executes immediately, Block captures the minimal
        context needed for execution (module, function, $ctx, @local) and returns
        a RawBlock entity. This raw block has no input shape yet and cannot be
        invoked until morphed with a BlockShape to create a Block.

        Captured context:
        - module: From mod_shapes/mod_funcs/mod_tags scope (any will work)
        - function: From @func_ctx scope if present (for $arg access in blocks)
        - ctx_scope: Current $ctx scope value
        - local_scope: Current @local scope value

        NOT captured (provided at invocation time):
        - $in: The input value passed to the block
        - $out: Built during block execution
        - $arg: Comes from function context if present

        Returns comp.Value wrapping a RawBlock entity.
        """
        # Create RawBlock entity with the frame it was defined in
        # The block captures the frame to access scopes like $var, $arg, $ctx, @local
        # This allows blocks to see mutations to $var between invocations
        raw_block = comp.RawBlock(
            block_ast=self,  # The Block AST node itself
            frame=frame      # Capture the entire frame context
        )

        # Return as Value (Value can now wrap Entity objects)
        return comp.Value(raw_block)
        yield  # Make this a generator

    def unparse(self) -> str:
        """Convert back to source code."""
        if not self.structure.ops:
            return ":{}"
        # Whitespace separated - no commas in Comp syntax
        ops_str = " ".join(op.unparse() for op in self.structure.ops)
        return f":{{{ops_str}}}"

    def __repr__(self):
        return f"Block({len(self.body.ops)} ops)"


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

    Args:
        value: Expression that evaluates to field value
        key: None (unnamed), _base.ValueNode (simple), or list of field nodes (deep path)

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
        # Handles multiple cases:
        # 0. Scope assignment: key starts with ScopeField (e.g., @name = value)
        # 1. Private assignment: key contains PrivateField (e.g., value.&.data = 42)
        # 2. Unnamed: key is None, use comp.Unnamed() as key
        # 3. Simple named: key is single _base.ValueNode, evaluate and use
        # 4. Deep path: key is list, walk path creating nested structs

        # Normalize Identifier keys into list-of-fields for processing. This allows
        # the parser to produce Identifier nodes for left-hand-side keys while
        # letting the FieldOp evaluator treat them as deep paths.
        key_obj = self.key
        if isinstance(key_obj, _ident.Identifier):
            key_obj = key_obj.fields

        # Check for private field assignment first (key is list containing PrivateField)
        # This includes both @var.&.field and value.&.field patterns
        if isinstance(key_obj, list) and any(isinstance(f, _ident.PrivateField) for f in key_obj):
            # This is a private assignment like value.&.data = 42 or @var.value.& = data
            return (yield from self._evaluate_private_assignment(frame))

        # Check for scope assignment (key is list starting with ScopeField, no PrivateField)
        if isinstance(key_obj, list) and len(key_obj) >= 2 and isinstance(key_obj[0], _ident.ScopeField):
            # This is a scope assignment like @name = value
            return (yield from self._evaluate_scope_assignment(frame))

        # Get the accumulator from scope stack
        accumulator = frame.scope('struct_accumulator')
        if accumulator is None or not accumulator.is_struct:
            return comp.fail("FieldOp requires struct_accumulator scope")

        # Evaluate the value first (propagate disarm_bypass for fallback handlers)
        value_value = yield comp.Compute(self.value, disarm_bypass=frame.disarm_bypass)
        if frame.bypass_value(value_value):
            return value_value

        # Register any handles in the value with the current frame
        # This handles field assignments that contain handles
        frame.register_handles(value_value)

        # Case 1: Unnamed field
        if self.key is None:
            # Unwrap single-element structs for unnamed fields
            # This allows {[expr]} to work when expr returns {value}
            value_value = value_value.as_scalar()
            accumulator.struct[comp.Unnamed()] = value_value
            return comp.Value(True)

        # Case 2: Simple named field (non-list key)
        if not isinstance(key_obj, list):
            key_value = yield comp.Compute(self.key)
            if frame.bypass_value(key_value):
                return key_value
            accumulator.struct[key_value] = value_value
            return comp.Value(True)

        # Case 3: Deep path - walk and create nested structures
        # Start at the root accumulator
        current_dict = accumulator.struct

        # Walk all but the last field, creating nested structs as needed
        for field_node in key_obj[:-1]:
            # Get the key for this path segment
            key_value = yield from self._evaluate_path_field(frame, field_node, current_dict)
            if frame.bypass_value(key_value):
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
        final_field = key_obj[-1]
        final_key = yield from self._evaluate_path_field(frame, final_field, current_dict)
        if frame.bypass_value(final_key):
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
        elif isinstance(field_node, _ident.TokenField):
            # TokenField: use the field name directly as a string key
            # Don't evaluate it (which would try to look it up)
            return comp.Value(field_node.name)
        else:
            # Normal field: evaluate to get key
            # This handles String, Number, or any other _base.ValueNode
            raise RuntimeError(f"FieldOp should not be literal {type(field_node)} {field_node}")
            key_value = yield comp.Compute(field_node)
            return key_value

    def _evaluate_scope_assignment(self, frame):
        """Handle scope assignment like @name = value or ^item = value.

        The key is a list starting with ScopeField, followed by field names.
        For example: [@, String('name')] for @name = value

        Returns:
            comp.Value(True) on success, fail value on error
        """
        # Evaluate the value to assign
        value_result = yield comp.Compute(self.value)
        if frame.bypass_value(value_result):
            return value_result

        # First element is the ScopeField
        scope_field = self.key[0]

        # Prevent assignments to $mod inside structures/functions
        # $mod can only be assigned at module level using ModuleAssign
        if scope_field.scope_name == 'mod':
            return comp.fail(
                "$mod cannot be assigned inside functions or structures. "
                "Use module-level assignments like: $mod.field = value"
            )

        # Evaluate the scope field to get the scope
        scope_value = yield comp.Compute(scope_field)
        if frame.bypass_value(scope_value):
            return scope_value

        # Scope must be a struct
        if not scope_value.is_struct:
            return comp.fail(f"Scope '{scope_field.scope_name}' is not a struct")

        # Rest of the key is the field path within the scope
        field_path = self.key[1:]

        # Simple case: single field name like @name
        if len(field_path) == 1 and isinstance(field_path[0], comp.ast.String):
            key = comp.Value(field_path[0].value)
            scope_value.struct[key] = value_result
            return comp.Value(True)

        # Complex case: deep path like @user.name
        # Walk the path, creating nested structs as needed
        current_dict = scope_value.struct
        for field_node in field_path[:-1]:
            key_value = yield from self._evaluate_path_field(frame, field_node, current_dict)
            if frame.bypass_value(key_value):
                return key_value

            # Navigate or create nested struct
            if key_value in current_dict:
                current_value = current_dict[key_value]
                if not current_value.is_struct:
                    current_value = comp.Value({})
                    current_dict[key_value] = current_value
                current_dict = current_value.struct
            else:
                new_struct = comp.Value({})
                current_dict[key_value] = new_struct
                current_dict = new_struct.struct

        # Assign to the final field
        final_field = field_path[-1]
        final_key = yield from self._evaluate_path_field(frame, final_field, current_dict)
        if frame.bypass_value(final_key):
            return final_key

        current_dict[final_key] = value_result
        return comp.Value(True)

    def _evaluate_private_assignment(self, frame):
        """Handle private field assignment like value.&.data = 42.

        The key is a list containing a PrivateField somewhere in the path.
        Everything before the & is evaluated to get the target value,
        then we access/modify its private data, and everything after & is
        the path within the private structure.

        Returns:
            comp.Value(True) on success, fail value on error
        """
        # Evaluate the value to assign
        value_result = yield comp.Compute(self.value)
        if frame.bypass_value(value_result):
            return value_result

        # Find the PrivateField in the key path
        private_field_index = None
        for i, field_node in enumerate(self.key):
            if isinstance(field_node, _ident.PrivateField):
                private_field_index = i
                break

        if private_field_index is None:
            return comp.fail("Internal error: PrivateField not found in key path")

        # Get module for private data access
        module = frame.scope('module')
        if module is None:
            return comp.fail("Cannot assign to private data without module context")

        # Split the path: before &, the &, and after &
        path_before = self.key[:private_field_index]
        path_after = self.key[private_field_index + 1:]

        # Evaluate the path before & to get the target value
        if not path_before:
            return comp.fail("Cannot assign to private data without a target value")

        # Start with the first field in path_before
        first_field = path_before[0]
        
        # If it's a ScopeField, evaluate it to get the scope value
        if isinstance(first_field, _ident.ScopeField):
            current_value = yield comp.Compute(first_field)
            if frame.bypass_value(current_value):
                return current_value
            # Continue with remaining path
            path_before = path_before[1:]
        else:
            # Start from unnamed scope and walk to the target value
            current_value = frame.scope('unnamed')
            if current_value is None:
                return comp.fail("No implicit scope available for private assignment")

        # Walk the remaining path before &
        for field_node in path_before:
            if isinstance(field_node, _ident.TokenField):
                # Look up field in current value (from identifier context)
                if not current_value.is_struct:
                    return comp.fail(f"Cannot access field '{field_node.name}' on non-struct")
                key = comp.Value(field_node.name)
                if key not in current_value.struct:
                    return comp.fail(f"Field '{field_node.name}' not found")
                current_value = current_value.struct[key]
            elif isinstance(field_node, _literal.String):
                # Look up field in current value (from assignment key context)
                if not current_value.is_struct:
                    return comp.fail(f"Cannot access field '{field_node.value}' on non-struct")
                key = comp.Value(field_node.value)
                if key not in current_value.struct:
                    return comp.fail(f"Field '{field_node.value}' not found")
                current_value = current_value.struct[key]
            else:
                # Evaluate other field types normally
                current_value = yield comp.Compute(field_node, identifier=current_value)
                if frame.bypass_value(current_value):
                    return current_value

        # Now current_value is the target that has private data
        # Get its private data for this module
        private_data = current_value.get_private(module.module_id)

        # If no path after &, we're replacing entire private data
        if not path_after:
            # Assign entire value as new private data
            current_value.set_private(module.module_id, value_result)
            return comp.Value(True)

        # Otherwise, we need to modify a field within the private data
        # If no private data exists yet, create empty struct
        if private_data is None:
            private_data = comp.Value({})
            current_value.set_private(module.module_id, private_data)

        # Private data must be a struct to assign fields
        if not private_data.is_struct:
            return comp.fail("Cannot assign field in non-struct private data")

        # Walk the path after &, creating nested structs as needed
        current_dict = private_data.struct
        for field_node in path_after[:-1]:
            key_value = yield from self._evaluate_path_field(frame, field_node, current_dict)
            if frame.bypass_value(key_value):
                return key_value

            # Navigate or create nested struct
            if key_value in current_dict:
                current_struct = current_dict[key_value]
                if not current_struct.is_struct:
                    current_struct = comp.Value({})
                    current_dict[key_value] = current_struct
                current_dict = current_struct.struct
            else:
                new_struct = comp.Value({})
                current_dict[key_value] = new_struct
                current_dict = new_struct.struct

        # Assign to the final field in private data
        final_field = path_after[-1]
        final_key = yield from self._evaluate_path_field(frame, final_field, current_dict)
        if frame.bypass_value(final_key):
            return final_key

        current_dict[final_key] = value_result
        return comp.Value(True)

    def unparse(self) -> str:
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

    Args:
        expr: Expression that evaluates to a struct to spread
    """

    def __init__(self, expr: _base.ValueNode):
        if not isinstance(expr, _base.AstNode):
            raise TypeError("Spread expression must be AstNode")
        self.expr = expr

    def evaluate(self, frame):
        # Get the accumulator from scope stack
        accumulator = frame.scope('struct_accumulator')
        if accumulator is None or not accumulator.is_struct:
            return comp.fail("SpreadOp requires struct_accumulator scope")

        # Evaluate spread expression
        spread_value = yield comp.Compute(self.expr)

        # Runtime check: must be a struct
        if not spread_value.is_struct:
            return comp.fail(f"Cannot spread non-struct value: {spread_value}")

        # Register any handles in the spread value with the current frame
        # This handles spreading structs containing handles into outgoing structures
        frame.register_handles(spread_value)

        # Merge into accumulator
        accumulator.struct.update(spread_value.struct)

        # Return success marker
        return comp.Value(True)

    def unparse(self) -> str:
        return f"..{self.expr.unparse()}"

    def __repr__(self):
        return f"SpreadOp({self.expr})"


class ScopeAssignOp(StructOp):
    """Scope assignment operation: @name = value, ^name = value, $scope.name = value

    Assigns a value to a named entry in a scope (local, arg, or named scope).
    Unlike FieldOp which assigns to the struct accumulator, this assigns to a scope.

    Args:
        value: Expression that evaluates to the value to assign
        scope_name: Name of the scope ('local' for @, 'arg' for ^, or custom for $name)
        field_name: Name of the field within the scope
    """

    def __init__(self, value: _base.ValueNode, scope_name: str, field_name: str):
        if not isinstance(value, _base.AstNode):
            raise TypeError("Scope assign value must be AstNode")
        if not isinstance(scope_name, str):
            raise TypeError("Scope name must be string")
        if not isinstance(field_name, str):
            raise TypeError("Field name must be string")

        self.value = value
        self.scope_name = scope_name
        self.field_name = field_name

    def evaluate(self, frame):
        # Evaluate the value to assign
        value_result = yield comp.Compute(self.value)
        if frame.bypass_value(value_result):
            return value_result

        # Get the target scope
        scope = frame.scope(self.scope_name)
        if scope is None:
            return comp.fail(f"Scope '{self.scope_name}' not defined")

        # The scope should be a Value wrapping a struct (dict)
        if not scope.is_struct:
            return comp.fail(f"Scope '{self.scope_name}' is not a struct")

        # Register any handles in the value with the current frame
        frame.register_handles(value_result)

        # Assign to the scope using a String key
        key = comp.Value(self.field_name)
        scope.struct[key] = value_result

        # Return success marker
        return comp.Value(True)

    def unparse(self) -> str:
        """Convert back to source code."""
        if self.scope_name == 'local':
            prefix = '@'
        elif self.scope_name == 'arg':
            prefix = '^'
        else:
            prefix = f'${self.scope_name}.'
        return f"{prefix}{self.field_name} = {self.value.unparse()}"

    def __repr__(self):
        return f"ScopeAssignOp({self.scope_name}.{self.field_name}, {self.value})"
