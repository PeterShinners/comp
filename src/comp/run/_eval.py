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
        # Resolve tag reference with namespace support
        tokens = expr.tokens or []
        tag_def = module.resolve_tag(tokens, expr.namespace)
        if tag_def and tag_def.value:
            return tag_def.value
        # Unresolved tag reference - return a basic tag value
        tag_name = ".".join(tokens)
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

    # Pipeline execution
    if isinstance(expr, ast.Pipeline):
        return _evaluate_pipeline(expr, module, scopes)

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

    # No scope prefix - check if first field is IndexField (positional access)
    # IndexField (#0, #1, etc.) should only look in $in, not the unnamed chained scope
    first = expr.kids[0]
    if isinstance(first, ast.IndexField):
        # Bare positional access goes directly to $in scope
        if 'in' not in scopes:
            raise ValueError("$in scope not available")
        
        current_value = scopes['in']
        
        # Handle first field (IndexField)
        if not current_value.is_struct or not current_value.struct:
            raise ValueError("Cannot index non-struct value in $in")
        
        index = first.value
        fields_list = list(current_value.struct.values())
        if 0 <= index < len(fields_list):
            current_value = fields_list[index]
        else:
            raise ValueError(f"Index #{index} out of bounds ($in has {len(fields_list)} fields)")
        
        # Walk through remaining fields
        for field in expr.kids[1:]:
            if not current_value.is_struct or not current_value.struct:
                raise ValueError("Cannot access field on non-struct value")

            if isinstance(field, ast.TokenField):
                field_key = _value.Value(field.value)
                if field_key in current_value.struct:
                    current_value = current_value.struct[field_key]
                else:
                    raise ValueError(f"Field '{field.value}' not found in struct")
            elif isinstance(field, ast.String):
                field_key = _value.Value(field.value)
                if field_key in current_value.struct:
                    current_value = current_value.struct[field_key]
                else:
                    raise ValueError(f"Field '{field.value}' not found in struct")
            elif isinstance(field, ast.IndexField):
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
    
    # Otherwise use unnamed scope (chains $out -> $in) for named field access
    # But also check chained scope for function parameters
    if 'unnamed' not in scopes:
        raise ValueError("Unnamed scope not available")

    current_value = scopes['unnamed']

    # Walk through all fields (no scope prefix to skip)
    for idx, field in enumerate(expr.kids):
        # Handle both regular Values and ChainedScope
        if isinstance(current_value, _scope.ChainedScope):
            # ChainedScope has special lookup for named fields only
            # (IndexField is handled separately above - it goes directly to $in)
            if isinstance(field, ast.TokenField):
                field_key = _value.Value(field.value)
                result = current_value.lookup_field(field_key)
                if result is None:
                    # For FIRST field only, also try chained scope (for function parameters)
                    if idx == 0 and 'chained' in scopes:
                        chained = scopes['chained']
                        if isinstance(chained, _scope.ChainedScope):
                            result = chained.lookup_field(field_key)
                            if result is not None:
                                current_value = result
                                continue
                    raise ValueError(f"Field '{field.value}' not found in unnamed scope")
                current_value = result
            elif isinstance(field, ast.String):
                # String field - look up by string value
                field_key = _value.Value(field.value)
                result = current_value.lookup_field(field_key)
                if result is None:
                    raise ValueError(f"Field '{field.value}' not found in unnamed scope")
                current_value = result
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
                raise ValueError(f"Unsupported field type in unnamed scope: {type(field).__name__}")
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


def _evaluate_pipeline(pipeline: ast.Pipeline, module: '_module.Module', scopes: dict[str, _value.Value]) -> _value.Value:
    """Evaluate a pipeline expression.

    Args:
        pipeline: Pipeline AST node
        module: Module context
        scopes: Scope values dict

    Returns:
        Final value after all pipeline operations
    """
    from . import _invoke

    # Start with the seed value (or None for unseeded pipelines)
    if pipeline.seed is not None:
        current_value = evaluate(pipeline.seed, module, scopes)
    else:
        # Unseeded pipeline - start with $in
        current_value = scopes.get('in', _value.Value(None))

    # Execute each pipeline operation in sequence
    for operation in pipeline.operations:
        if isinstance(operation, ast.PipeFunc):
            # Function invocation: |func or |func {args}
            current_value = _execute_pipe_func(operation, current_value, module, scopes)
        elif isinstance(operation, ast.PipeFallback):
            # Fallback operator: |? expr
            # If current value is a failure, evaluate the fallback expression
            if _is_failure(current_value):
                # Fallback gets the ORIGINAL input, not the failure
                # For now, we'll just evaluate the fallback expression with current scopes
                current_value = evaluate(operation.fallback, module, scopes)
        elif isinstance(operation, ast.PipeStruct):
            # Inline struct transformation: |{field = expr}
            current_value = _execute_pipe_struct(operation, current_value, module, scopes)
        elif isinstance(operation, ast.PipeBlock):
            # Block invocation: |: block
            # Not implemented yet
            raise NotImplementedError("PipeBlock not yet implemented")
        elif isinstance(operation, ast.PipeWrench):
            # Pipeline modifier: |-| func
            # Not implemented yet
            raise NotImplementedError("PipeWrench not yet implemented")
        else:
            raise ValueError(f"Unknown pipeline operation: {type(operation).__name__}")

    return current_value


def _execute_pipe_func(pipe_func: ast.PipeFunc, input_value: _value.Value, module: '_module.Module', scopes: dict[str, _value.Value]) -> _value.Value:
    """Execute a pipeline function operation.

    Args:
        pipe_func: PipeFunc AST node
        input_value: Current value in the pipeline
        module: Module context
        scopes: Scope values dict

    Returns:
        Result of function invocation
    """
    from . import _invoke

    # Get the function reference
    func_ref = pipe_func.func
    if not isinstance(func_ref, ast.FuncRef):
        raise ValueError(f"Expected FuncRef in PipeFunc, got {type(func_ref).__name__}")

    # Look up the function using namespace resolution
    tokens = func_ref.tokens or []
    func_def = module.resolve_func(tokens, func_ref.namespace)
    
    if not func_def:
        func_name = ".".join(tokens)
        namespace_str = f"/{func_ref.namespace}" if func_ref.namespace else ""
        raise ValueError(f"Function '|{func_name}{namespace_str}' not found")

    # Create a new scope context for evaluating arguments
    # The pipeline value should be available as $in when evaluating args
    pipeline_scopes = scopes.copy()
    pipeline_scopes['in'] = input_value
    # Update unnamed scope to chain $out -> $in with the new $in value
    pipeline_scopes['unnamed'] = _scope.ChainedScope(
        pipeline_scopes.get('out', _value.Value(None)),
        input_value
    )

    # Evaluate arguments if provided
    if pipe_func.args and pipe_func.args.kids:
        # Args is a Structure node - evaluate it with pipeline scopes
        args_value = evaluate(pipe_func.args, module, pipeline_scopes)
    else:
        # No arguments - pass empty struct
        args_value = _value.Value(None)
        args_value.struct = {}

    # Invoke the function with input_value as $in
    # Function signature: invoke(func_def, module, input_value, ctx_value, mod_value, arg_value)
    # For pipeline functions, we pass:
    # - input_value as $in (pipeline value)
    # - args_value as $arg (explicit arguments from function call)
    # - empty for $ctx and $mod
    result = _invoke.invoke(
        func_def,
        module,
        input_value,  # $in
        _value.Value(None),  # $ctx
        _value.Value(None),  # $mod
        args_value  # $arg
    )

    return result


def _execute_pipe_struct(pipe_struct: ast.PipeStruct, input_value: _value.Value, module: '_module.Module', scopes: dict[str, _value.Value]) -> _value.Value:
    """Execute a pipeline struct operation.

    Args:
        pipe_struct: PipeStruct AST node
        input_value: Current value in the pipeline
        module: Module context
        scopes: Scope values dict

    Returns:
        Result of evaluating the structure
    """
    # Create a new scope context for evaluating the structure
    # The pipeline value should be available as $in
    pipe_scopes = scopes.copy()
    pipe_scopes['in'] = input_value
    # Update unnamed scope to chain $out -> $in with the new $in value
    pipe_scopes['unnamed'] = _scope.ChainedScope(
        pipe_scopes.get('out', _value.Value(None)),
        input_value
    )

    # PipeStruct contains structure children (StructAssign, StructUnnamed, etc.)
    # We need to evaluate them as a structure
    # Create a temporary Structure node to evaluate
    temp_struct = ast.Structure()
    temp_struct.kids = pipe_struct.kids

    # Evaluate the structure with the pipeline scopes
    result = evaluate(temp_struct, module, pipe_scopes)

    return result


def _is_failure(value: _value.Value) -> bool:
    """Check if a value represents a failure (has #fail tag).

    Args:
        value: Value to check

    Returns:
        True if value is a failure
    """
    # For now, just return False - we'll implement proper failure detection later
    # when we have tag support in the runtime
    return False
