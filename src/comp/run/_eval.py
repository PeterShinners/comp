"""Expression evaluation for runtime values."""

__all__ = ["evaluate"]

from typing import TYPE_CHECKING

from .. import ast
from . import _scope, _struct, _value

if TYPE_CHECKING:
    from . import _module


def evaluate(expr, module: '_module.Module', scopes: dict[str, _value.Value] | None = None) -> _value.Value:
    """Evaluate an AST expression to a runtime Value.

    Args:
        expr: AST expression node to evaluate
        module: Module context for resolving references
        scopes: Scope values dict (in, ctx, mod, arg)

    Returns:
        Evaluated Value
    """
    if scopes is None:
        scopes = {}

    if expr is None:
        return _value.Value(None)

    # Scope references and identifiers
    if isinstance(expr, ast.Identifier):
        return _evaluate_identifier(expr, module, scopes)

    # Literals
    if isinstance(expr, ast.Number):
        return _value.Value(expr.value)

    if isinstance(expr, ast.String):
        return _value.Value(expr.value)

    if isinstance(expr, ast.TagRef):
        # Create a tag value from the reference
        tag_name = ".".join(expr.tokens or [])
        if tag_name in module.tags:
            tag_def = module.tags[tag_name]
            return _value.Value(tag_def)
        # Unresolved tag reference - return tag value anyway
        return _value.Value(tag_name)

    # Binary operations
    if isinstance(expr, ast.BinaryOp):
        left = evaluate(expr.left, module, scopes)
        right = evaluate(expr.right, module, scopes)

        # Mathematical operations
        if expr.op == "+":
            if left.is_num and right.is_num:
                return _value.Value(left.num + right.num)
        elif expr.op == "-":
            if left.is_num and right.is_num:
                return _value.Value(left.num - right.num)
        elif expr.op == "*":
            if left.is_num and right.is_num:
                return _value.Value(left.num * right.num)
        elif expr.op == "/":
            if left.is_num and right.is_num:
                return _value.Value(left.num / right.num)
        elif expr.op == "//":
            if left.is_num and right.is_num:
                return _value.Value(left.num // right.num)
        elif expr.op == "%":
            if left.is_num and right.is_num:
                return _value.Value(left.num % right.num)
        elif expr.op == "**":
            if left.is_num and right.is_num:
                return _value.Value(left.num ** right.num)

        # String concatenation
        if expr.op == "+" and left.is_str and right.is_str:
            return _value.Value(left.str + right.str)

        raise ValueError(f"Cannot apply operator {expr.op} to {left} and {right}")

    # Unary operations
    if isinstance(expr, ast.UnaryOp):
        operand = evaluate(expr.operand, module, scopes)

        if expr.op == "-":
            if operand.is_num:
                return _value.Value(-operand.num)
        elif expr.op == "+":
            if operand.is_num:
                return _value.Value(+operand.num)

        raise ValueError(f"Cannot apply unary operator {expr.op} to {operand}")

    # Structure literal
    if isinstance(expr, ast.Structure):
        fields = {}
        for child in expr.kids:
            if isinstance(child, ast.StructAssign):
                # Check if this is a nested field assignment (e.g., parent.child = value)
                if child.key and isinstance(child.key, ast.Identifier) and len(child.key.kids) > 1:
                    # Nested field assignment - walk down and create intermediate structures
                    if child.value:
                        field_value = evaluate(child.value, module, scopes)
                        
                        # Build the nested structure incrementally
                        # Start from the root and walk down, creating dicts as needed
                        current_dict = fields
                        
                        # Walk through all but the last field (these are all TokenFields for unscoped paths)
                        for field_node in child.key.kids[:-1]:
                            if isinstance(field_node, ast.TokenField):
                                field_name = field_node.value
                                
                                # Get or create intermediate structure
                                if field_name in current_dict:
                                    # Field exists, navigate into it
                                    # In evaluate(), fields dict has string keys and Value/dict values
                                    current_value = current_dict[field_name]
                                    if isinstance(current_value, dict):
                                        # Already a dict, use it
                                        current_dict = current_value
                                    elif isinstance(current_value, _value.Value) and current_value.is_struct:
                                        # Need to convert Value to dict for modification
                                        # Create new dict from Value's struct, preserving all existing fields
                                        new_dict = {}
                                        if current_value.struct:
                                            for k, v in current_value.struct.items():
                                                if isinstance(k, _value.Value):
                                                    # Convert Value key to string for fields dict
                                                    new_dict[str(k.to_python())] = v
                                                else:
                                                    # String key (shouldn't happen but handle it)
                                                    new_dict[str(k)] = v
                                        current_dict[field_name] = new_dict
                                        current_dict = new_dict
                                    else:
                                        # Need to replace with a dict
                                        new_dict = {}
                                        current_dict[field_name] = new_dict
                                        current_dict = new_dict
                                else:
                                    # Create new intermediate dict
                                    new_dict = {}
                                    current_dict[field_name] = new_dict
                                    current_dict = new_dict
                            elif isinstance(field_node, ast.String):
                                # String field - same as TokenField but with string value
                                field_name = field_node.value
                                
                                # Get or create intermediate structure
                                if field_name in current_dict:
                                    # Field exists, navigate into it
                                    # In evaluate(), fields dict has string keys and Value/dict values
                                    current_value = current_dict[field_name]
                                    if isinstance(current_value, dict):
                                        # Already a dict, use it
                                        current_dict = current_value
                                    elif isinstance(current_value, _value.Value) and current_value.is_struct:
                                        # Need to convert Value to dict for modification
                                        # Create new dict from Value's struct, preserving all existing fields
                                        new_dict = {}
                                        if current_value.struct:
                                            for k, v in current_value.struct.items():
                                                if isinstance(k, _value.Value):
                                                    # Convert Value key to string for fields dict
                                                    new_dict[str(k.to_python())] = v
                                                else:
                                                    # String key (shouldn't happen but handle it)
                                                    new_dict[str(k)] = v
                                        current_dict[field_name] = new_dict
                                        current_dict = new_dict
                                    else:
                                        # Need to replace with a dict
                                        new_dict = {}
                                        current_dict[field_name] = new_dict
                                        current_dict = new_dict
                                else:
                                    # Create new intermediate dict
                                    new_dict = {}
                                    current_dict[field_name] = new_dict
                                    current_dict = new_dict
                            elif isinstance(field_node, ast.ComputeField):
                                # Computed field - evaluate expression to get field key
                                if field_node.expr:
                                    computed_key_value = evaluate(field_node.expr, module, scopes)
                                    # Use Value directly as key (don't convert to string)
                                    field_key = computed_key_value

                                    # Get or create intermediate structure
                                    if field_key in current_dict:
                                        # Field exists, navigate into it
                                        current_value = current_dict[field_key]
                                        if isinstance(current_value, dict):
                                            # Already a dict, use it
                                            current_dict = current_value
                                        elif isinstance(current_value, _value.Value) and current_value.is_struct:
                                            # Need to convert Value to dict for modification
                                            new_dict = {}
                                            if current_value.struct:
                                                for k, v in current_value.struct.items():
                                                    if isinstance(k, _value.Value):
                                                        new_dict[k] = v
                                                    else:
                                                        new_dict[str(k)] = v
                                            current_dict[field_key] = new_dict
                                            current_dict = new_dict
                                        else:
                                            # Need to replace with a dict
                                            new_dict = {}
                                            current_dict[field_key] = new_dict
                                            current_dict = new_dict
                                    else:
                                        # Create new intermediate dict
                                        new_dict = {}
                                        current_dict[field_key] = new_dict
                                        current_dict = new_dict
                                else:
                                    raise ValueError("ComputeField missing expression")
                            else:
                                # Unsupported field type in nested assignment
                                raise ValueError(f"Unsupported field type in nested assignment: {type(field_node).__name__}")
                        
                        # Set the final field
                        last_field = child.key.kids[-1]
                        if isinstance(last_field, ast.TokenField):
                            current_dict[last_field.value] = field_value
                        elif isinstance(last_field, ast.String):
                            # String field - same as TokenField but with string value
                            current_dict[last_field.value] = field_value
                        elif isinstance(last_field, ast.ComputeField):
                            # Computed field - evaluate expression to get field key
                            if last_field.expr:
                                computed_key_value = evaluate(last_field.expr, module, scopes)
                                # Use Value directly as key
                                current_dict[computed_key_value] = field_value
                            else:
                                raise ValueError("ComputeField missing expression")
                else:
                    # Simple field assignment
                    if child.key and child.value:
                        # Check if key is a single ComputeField that needs evaluation
                        if (isinstance(child.key, ast.Identifier) and
                            len(child.key.kids) == 1 and
                            isinstance(child.key.kids[0], ast.ComputeField)):
                            # Evaluate the ComputeField expression to get the key
                            compute_field = child.key.kids[0]
                            if compute_field.expr:
                                key = evaluate(compute_field.expr, module, scopes)
                            else:
                                raise ValueError("ComputeField missing expression")
                        else:
                            # Simple key - should be an Identifier with a single TokenField or String
                            if (isinstance(child.key, ast.Identifier) and
                                len(child.key.kids) == 1):
                                first_field = child.key.kids[0]
                                if isinstance(first_field, ast.TokenField):
                                    key = first_field.value
                                elif isinstance(first_field, ast.String):
                                    key = first_field.value
                                else:
                                    raise ValueError(f"Unsupported simple field type: {type(first_field).__name__}")
                            else:
                                raise ValueError("Simple field key must be a single TokenField or String")
                        
                        field_value = evaluate(child.value, module, scopes)
                        # Store in fields dict
                        fields[key] = field_value
            elif isinstance(child, ast.StructSpread):
                # Handle spread operator
                if child.value:
                    spread_value = evaluate(child.value, module, scopes)
                    # Merge fields from the spread value
                    if isinstance(spread_value, _scope.ChainedScope):
                        # ChainedScope: merge its virtual struct
                        if spread_value.struct:
                            # Convert Value keys to strings
                            for k, v in spread_value.struct.items():
                                if isinstance(k, _value.Value):
                                    fields[k.to_python()] = v
                                elif isinstance(k, _struct.Unnamed):
                                    # Keep Unnamed keys as-is
                                    fields[k] = v
                    elif spread_value.is_struct and spread_value.struct:
                        # Regular Value: merge its struct dict
                        # Convert Value keys to strings, keep Unnamed as-is
                        for k, v in spread_value.struct.items():
                            if isinstance(k, _value.Value):
                                fields[k.to_python()] = v
                            elif isinstance(k, _struct.Unnamed):
                                fields[k] = v
            elif isinstance(child, ast.StructUnnamed):
                # Unnamed field: just an expression
                if child.value:
                    field_value = evaluate(child.value, module, scopes)
                    # Use Unnamed key
                    fields[_struct.Unnamed()] = field_value
        
        # Convert all string keys to Value keys for proper struct format
        # Also recursively convert any dict values to Value structs
        def convert_to_value_struct(d):
            """Recursively convert dict with string keys to Value struct format."""
            result = {}
            for k, v in d.items():
                # Convert key
                if isinstance(k, str):
                    key = _value.Value(k)
                elif isinstance(k, _struct.Unnamed):
                    key = k
                else:
                    key = k  # Already a Value
                
                # Convert value
                if isinstance(v, dict):
                    # Recursively convert nested dicts
                    value = _value.Value(None)
                    value.struct = convert_to_value_struct(v)
                else:
                    value = v  # Already a Value
                
                result[key] = value
            return result
        
        # Create Value and set struct directly
        result = _value.Value(None)
        result.struct = convert_to_value_struct(fields)
        return result

    raise NotImplementedError(f"Cannot evaluate {type(expr).__name__}")


def _evaluate_identifier(expr: ast.Identifier, module: '_module.Module', scopes: dict[str, _value.Value]) -> _value.Value:
    """Evaluate an identifier with potential scope reference.

    Args:
        expr: Identifier AST node
        module: Module context
        scopes: Scope values dict

    Returns:
        Value from scope lookup
    """
    if not expr.kids:
        raise ValueError("Empty identifier")

    # Check if first field is a scope
    first = expr.kids[0]
    if isinstance(first, ast.ScopeField):
        scope_name = first.value

        # Map scope symbols to scope names
        if scope_name == '@':
            scope_name = 'local'
        elif scope_name == '^':
            scope_name = 'chained'
        elif scope_name.startswith('$'):
            scope_name = scope_name[1:]

        # Get the scope value
        if scope_name not in scopes:
            raise ValueError(f"Scope {first.value} not defined")

        current_value = scopes[scope_name]

        # Walk through remaining fields
        for field in expr.kids[1:]:
            # Handle both regular Values and ChainedScope
            if isinstance(current_value, _scope.ChainedScope):
                # ChainedScope has special lookup
                if isinstance(field, ast.TokenField):
                    field_key = _value.Value(field.value)
                    result = current_value.lookup_field(field_key)
                    if result is None:
                        raise ValueError(f"Field '{field.value}' not found in chained scope")
                    current_value = result
                elif isinstance(field, ast.String):
                    # String field - look up by string value
                    field_key = _value.Value(field.value)
                    result = current_value.lookup_field(field_key)
                    if result is None:
                        raise ValueError(f"Field '{field.value}' not found in chained scope")
                    current_value = result
                elif isinstance(field, ast.IndexField):
                    # Look up by index in ChainedScope
                    index = field.value
                    # Get the Nth field from the chained scope's virtual struct
                    if current_value.struct:
                        fields_list = list(current_value.struct.values())
                        if 0 <= index < len(fields_list):
                            current_value = fields_list[index]
                        else:
                            raise ValueError(f"Index #{index} out of bounds (scope has {len(fields_list)} fields)")
                    else:
                        raise ValueError(f"Cannot index empty chained scope")
                elif isinstance(field, ast.ComputeField):
                    # Computed field - evaluate expression to get field key
                    if field.expr:
                        computed_key = evaluate(field.expr, module, scopes)
                        result = current_value.lookup_field(computed_key)
                        if result is None:
                            raise ValueError(f"Computed field not found in chained scope")
                        current_value = result
                    else:
                        raise ValueError("ComputeField missing expression")
                else:
                    raise ValueError(f"Unsupported field type: {type(field).__name__}")
            else:
                # Regular Value lookup
                if not current_value.is_struct or not current_value.struct:
                    raise ValueError("Cannot access field on non-struct value")

                if isinstance(field, ast.TokenField):
                    # Look up field by name
                    field_key = _value.Value(field.value)
                    if field_key in current_value.struct:
                        current_value = current_value.struct[field_key]
                    else:
                        raise ValueError(f"Field '{field.value}' not found in struct")
                elif isinstance(field, ast.String):
                    # String field - look up by string value
                    field_key = _value.Value(field.value)
                    if field_key in current_value.struct:
                        current_value = current_value.struct[field_key]
                    else:
                        raise ValueError(f"Field '{field.value}' not found in struct")
                elif isinstance(field, ast.IndexField):
                    # Look up by index (positional access to fields)
                    index = field.value
                    if current_value.struct:
                        fields_list = list(current_value.struct.values())
                        if 0 <= index < len(fields_list):
                            current_value = fields_list[index]
                        else:
                            raise ValueError(f"Index #{index} out of bounds (struct has {len(fields_list)} fields)")
                    else:
                        raise ValueError("Cannot index empty struct")
                elif isinstance(field, ast.ComputeField):
                    # Computed field - evaluate expression to get field key
                    if field.expr:
                        computed_key = evaluate(field.expr, module, scopes)
                        if computed_key in current_value.struct:
                            current_value = current_value.struct[computed_key]
                        else:
                            raise ValueError("Computed field not found in struct")
                    else:
                        raise ValueError("ComputeField missing expression")
                else:
                    raise ValueError(f"Unsupported field type: {type(field).__name__}")

        return current_value

    # No scope prefix - use unnamed scope (chains $out -> $in)
    if 'unnamed' not in scopes:
        raise ValueError("Unnamed scope not available")

    current_value = scopes['unnamed']

    # Walk through all fields (no scope prefix to skip)
    for field in expr.kids:
        # Handle both regular Values and ChainedScope
        if isinstance(current_value, _scope.ChainedScope):
            # ChainedScope has special lookup
            if isinstance(field, ast.TokenField):
                field_key = _value.Value(field.value)
                result = current_value.lookup_field(field_key)
                if result is None:
                    raise ValueError(f"Field '{field.value}' not found in unnamed scope")
                current_value = result
            elif isinstance(field, ast.String):
                # String field - look up by string value
                field_key = _value.Value(field.value)
                result = current_value.lookup_field(field_key)
                if result is None:
                    raise ValueError(f"Field '{field.value}' not found in unnamed scope")
                current_value = result
            elif isinstance(field, ast.IndexField):
                # Look up by index in ChainedScope (unnamed scope)
                index = field.value
                if current_value.struct:
                    fields_list = list(current_value.struct.values())
                    if 0 <= index < len(fields_list):
                        current_value = fields_list[index]
                    else:
                        raise ValueError(f"Index #{index} out of bounds (scope has {len(fields_list)} fields)")
                else:
                    raise ValueError("Cannot index empty scope")
            elif isinstance(field, ast.ComputeField):
                # Computed field - evaluate expression to get field key
                if field.expr:
                    computed_key = evaluate(field.expr, module, scopes)
                    result = current_value.lookup_field(computed_key)
                    if result is None:
                        raise ValueError("Computed field not found in unnamed scope")
                    current_value = result
                else:
                    raise ValueError("ComputeField missing expression")
            else:
                raise ValueError(f"Unsupported field type: {type(field).__name__}")
        else:
            # Regular Value lookup
            if not current_value.is_struct or not current_value.struct:
                raise ValueError("Cannot access field on non-struct value")

            if isinstance(field, ast.TokenField):
                # Look up field by name
                field_key = _value.Value(field.value)
                if field_key in current_value.struct:
                    current_value = current_value.struct[field_key]
                else:
                    raise ValueError(f"Field '{field.value}' not found in struct")
            elif isinstance(field, ast.String):
                # String field - look up by string value
                field_key = _value.Value(field.value)
                if field_key in current_value.struct:
                    current_value = current_value.struct[field_key]
                else:
                    raise ValueError(f"Field '{field.value}' not found in struct")
            elif isinstance(field, ast.IndexField):
                # Look up by index (positional access to fields)
                index = field.value
                if current_value.struct:
                    fields_list = list(current_value.struct.values())
                    if 0 <= index < len(fields_list):
                        current_value = fields_list[index]
                    else:
                        raise ValueError(f"Index #{index} out of bounds (struct has {len(fields_list)} fields)")
                else:
                    raise ValueError("Cannot index empty struct")
            elif isinstance(field, ast.ComputeField):
                # Computed field - evaluate expression to get field key
                if field.expr:
                    computed_key = evaluate(field.expr, module, scopes)
                    if computed_key in current_value.struct:
                        current_value = current_value.struct[computed_key]
                    else:
                        # Better error message showing what keys exist
                        keys_str = ", ".join(str(k) for k in current_value.struct.keys())
                        raise ValueError(f"Computed field key {computed_key} not found in struct (available keys: {keys_str})")
                else:
                    raise ValueError("ComputeField missing expression")
            else:
                raise ValueError(f"Unsupported field type: {type(field).__name__}")

    return current_value
