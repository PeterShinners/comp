"""Expression evaluation for runtime values."""

__all__ = ["evaluate"]

import comp
from . import _value, _invoke, _assign, _ops


def evaluate(expr, module, scopes=None):
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
    if isinstance(expr, comp.ast.Identifier):
        return _evaluate_identifier(expr, module, scopes)

    # Literals
    if isinstance(expr, comp.ast.Number):
        return _value.Value(expr.value)

    if isinstance(expr, comp.ast.String):
        return _value.Value(expr.value)

    if isinstance(expr, comp.ast.TagRef):
        # Resolve tag reference with namespace support
        tokens = expr.tokens or []
        tag_def = module.resolve_tag(tokens, expr.namespace)
        if tag_def and tag_def.value:
            return tag_def.value
        # Unresolved tag reference - raise an error
        tag_name = ".".join(tokens)
        namespace_str = f"{expr.namespace}." if expr.namespace else ""
        raise ValueError(f"Undefined tag reference: #{namespace_str}{tag_name}")

    # Binary operations
    if isinstance(expr, comp.ast.BinaryOp):
        return _ops.evaluate_binary_op(expr, module, scopes, evaluate)

    # Unary operations
    if isinstance(expr, comp.ast.UnaryOp):
        return _ops.evaluate_unary_op(expr, module, scopes, evaluate)

    # Structure literal
    if isinstance(expr, comp.ast.Structure):
        # BUILD MODE: Construct a new struct by evaluating field assignments.
        # This code CREATES intermediate structures as needed when building nested paths.
        # For example, {account.active = #true} creates the 'account' field if it doesn't exist.
        # This is fundamentally different from _evaluate_identifier which READS from existing
        # structures and fails if fields don't exist. Here we build; there we lookup.
        # Note: Works with temporary Python dicts during construction, converts to Value at end.
        fields = {}
        for child in expr.kids:
            if isinstance(child, comp.ast.StructAssign):
                # Check if this is a nested field assignment (e.g., parent.child = value)
                if child.key and isinstance(child.key, comp.ast.Identifier) and len(child.key.kids) > 1:
                    # Nested field assignment - delegate to shared helper
                    if child.value:
                        field_value = evaluate(child.value, module, scopes)
                        _assign.assign_nested_field(
                            child.key, field_value, fields, module, scopes, evaluate
                        )
                else:
                    # Simple field assignment
                    if child.key and child.value:
                        # Extract field key using shared helper (always returns Value)
                        key = _assign.extract_field_key(child.key, module, scopes, evaluate)
                        field_value = evaluate(child.value, module, scopes)
                        # Store in fields dict
                        fields[key] = field_value
            elif isinstance(child, comp.ast.StructSpread):
                # Handle spread operator
                if child.value:
                    spread_value = evaluate(child.value, module, scopes)
                    # Merge fields from the spread value
                    if isinstance(spread_value, ChainedScope):
                        # ChainedScope: merge its virtual struct
                        if spread_value.struct:
                            fields.update(spread_value.struct)
                    elif spread_value.is_struct and spread_value.struct:
                        # Regular Value: merge its struct dict
                        fields.update(spread_value.struct)
            elif isinstance(child, comp.ast.StructUnnamed):
                # Unnamed field: just an expression
                if child.value:
                    field_value = evaluate(child.value, module, scopes)
                    # Use Unnamed key
                    fields[_value.Unnamed()] = field_value

        # Create Value and set struct directly
        # All keys are already Value or Unnamed objects
        result = _value.Value(None)
        result.struct = fields
        return result

    # Pipeline execution
    if isinstance(expr, comp.ast.Pipeline):
        return _evaluate_pipeline(expr, module, scopes)

    raise NotImplementedError(f"Cannot evaluate {type(expr).__name__}")


def _evaluate_identifier(expr, module, scopes):
    """Evaluate an identifier with potential scope reference.
    
    READ MODE: Navigate through existing Value structures via field lookup.
    This code READS from runtime Values and raises errors if fields don't exist.
    For example, @user.account.active looks up 'user', then 'account', then 'active',
    failing if any field is missing. This is fundamentally different from structure
    construction which CREATES missing intermediate fields during building.
    
    Handles scope resolution (@, ^, $), ChainedScope special lookup, and various
    field access types (named, indexed, computed). Works with runtime Value objects,
    not temporary dicts.

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
    if isinstance(first, comp.ast.ScopeField):
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
            if isinstance(current_value, ChainedScope):
                # ChainedScope has special lookup
                if isinstance(field, comp.ast.TokenField):
                    field_key = _value.Value(field.value)
                    result = current_value.lookup_field(field_key)
                    if result is None:
                        raise ValueError(f"Field '{field.value}' not found in chained scope")
                    current_value = result
                elif isinstance(field, comp.ast.String):
                    # String field - look up by string value
                    field_key = _value.Value(field.value)
                    result = current_value.lookup_field(field_key)
                    if result is None:
                        raise ValueError(f"Field '{field.value}' not found in chained scope")
                    current_value = result
                elif isinstance(field, comp.ast.IndexField):
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
                elif isinstance(field, comp.ast.ComputeField):
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

                if isinstance(field, comp.ast.TokenField):
                    # Look up field by name
                    field_key = _value.Value(field.value)
                    if field_key in current_value.struct:
                        current_value = current_value.struct[field_key]
                    else:
                        raise ValueError(f"Field '{field.value}' not found in struct")
                elif isinstance(field, comp.ast.String):
                    # String field - look up by string value
                    field_key = _value.Value(field.value)
                    if field_key in current_value.struct:
                        current_value = current_value.struct[field_key]
                    else:
                        raise ValueError(f"Field '{field.value}' not found in struct")
                elif isinstance(field, comp.ast.IndexField):
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
                elif isinstance(field, comp.ast.ComputeField):
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
    # IndexField (#0, #1, etc.) should only look in $in, not the _value chained scope
    first = expr.kids[0]
    if isinstance(first, comp.ast.IndexField):
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

            if isinstance(field, comp.ast.TokenField):
                field_key = _value.Value(field.value)
                if field_key in current_value.struct:
                    current_value = current_value.struct[field_key]
                else:
                    raise ValueError(f"Field '{field.value}' not found in struct")
            elif isinstance(field, comp.ast.String):
                field_key = _value.Value(field.value)
                if field_key in current_value.struct:
                    current_value = current_value.struct[field_key]
                else:
                    raise ValueError(f"Field '{field.value}' not found in struct")
            elif isinstance(field, comp.ast.IndexField):
                index = field.value
                if current_value.struct:
                    fields_list = list(current_value.struct.values())
                    if 0 <= index < len(fields_list):
                        current_value = fields_list[index]
                    else:
                        raise ValueError(f"Index #{index} out of bounds (struct has {len(fields_list)} fields)")
                else:
                    raise ValueError("Cannot index empty struct")
            elif isinstance(field, comp.ast.ComputeField):
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
    # Note: In pipeline execution, this may be '_value' instead
    scope_key = '_value' if '_value' in scopes else 'unnamed'
    if scope_key not in scopes:
        raise ValueError("Unnamed scope not available")

    current_value = scopes[scope_key]

    # Walk through all fields (no scope prefix to skip)
    for idx, field in enumerate(expr.kids):
        # Handle both regular Values and ChainedScope
        if isinstance(current_value, ChainedScope):
            # ChainedScope has special lookup for named fields only
            # (IndexField is handled separately above - it goes directly to $in)
            if isinstance(field, comp.ast.TokenField):
                field_key = _value.Value(field.value)
                result = current_value.lookup_field(field_key)
                if result is None:
                    # For FIRST field only, also try chained scope (for function parameters)
                    if idx == 0 and 'chained' in scopes:
                        chained = scopes['chained']
                        if isinstance(chained, ChainedScope):
                            result = chained.lookup_field(field_key)
                            if result is not None:
                                current_value = result
                                continue
                    raise ValueError(f"Field '{field.value}' not found in {scope_key} scope")
                current_value = result
            elif isinstance(field, comp.ast.String):
                # String field - look up by string value
                field_key = _value.Value(field.value)
                result = current_value.lookup_field(field_key)
                if result is None:
                    raise ValueError(f"Field '{field.value}' not found in {scope_key} scope")
                current_value = result
            elif isinstance(field, comp.ast.ComputeField):
                # Computed field - evaluate expression to get field key
                if field.expr:
                    computed_key = evaluate(field.expr, module, scopes)
                    result = current_value.lookup_field(computed_key)
                    if result is None:
                        raise ValueError(f"Computed field not found in {scope_key} scope")
                    current_value = result
                else:
                    raise ValueError("ComputeField missing expression")
            else:
                raise ValueError(f"Unsupported field type in {scope_key} scope: {type(field).__name__}")
        else:
            # Regular Value lookup
            if not current_value.is_struct or not current_value.struct:
                raise ValueError("Cannot access field on non-struct value")

            if isinstance(field, comp.ast.TokenField):
                # Look up field by name
                field_key = _value.Value(field.value)
                if field_key in current_value.struct:
                    current_value = current_value.struct[field_key]
                else:
                    raise ValueError(f"Field '{field.value}' not found in struct")
            elif isinstance(field, comp.ast.String):
                # String field - look up by string value
                field_key = _value.Value(field.value)
                if field_key in current_value.struct:
                    current_value = current_value.struct[field_key]
                else:
                    raise ValueError(f"Field '{field.value}' not found in struct")
            elif isinstance(field, comp.ast.IndexField):
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
            elif isinstance(field, comp.ast.ComputeField):
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


def _evaluate_pipeline(pipeline, module, scopes):
    """Evaluate a pipeline expression.

    Args:
        pipeline: Pipeline AST node
        module: Module context
        scopes: Scope values dict

    Returns:
        Final value after all pipeline operations
    """
    # Start with the seed value (or None for unseeded pipelines)
    if pipeline.seed is not None:
        current_value = evaluate(pipeline.seed, module, scopes)
    else:
        # Unseeded pipeline - start with $in
        current_value = scopes.get('in', _value.Value(None))

    # Execute each pipeline operation in sequence
    for operation in pipeline.operations:
        if isinstance(operation, comp.ast.PipeFunc):
            # Function invocation: |func or |func {args}
            current_value = _execute_pipe_func(operation, current_value, module, scopes)
        elif isinstance(operation, comp.ast.PipeFallback):
            # Fallback operator: |? expr
            # If current value is a failure, evaluate the fallback expression
            if _is_failure(current_value):
                # Fallback gets the ORIGINAL input, not the failure
                # For now, we'll just evaluate the fallback expression with current scopes
                current_value = evaluate(operation.fallback, module, scopes)
        elif isinstance(operation, comp.ast.PipeStruct):
            # Inline struct transformation: |{field = expr}
            current_value = _execute_pipe_struct(operation, current_value, module, scopes)
        elif isinstance(operation, comp.ast.PipeBlock):
            # Block invocation: |: block
            # Not implemented yet
            raise NotImplementedError("PipeBlock not yet implemented")
        elif isinstance(operation, comp.ast.PipeWrench):
            # Pipeline modifier: |-| func
            # Not implemented yet
            raise NotImplementedError("PipeWrench not yet implemented")
        else:
            raise ValueError(f"Unknown pipeline operation: {type(operation).__name__}")

    return current_value


def _execute_pipe_func(pipe_func, input_value, module, scopes):
    """Execute a pipeline function operation.

    Args:
        pipe_func: PipeFunc AST node
        input_value: Current value in the pipeline
        module: Module context
        scopes: Scope values dict

    Returns:
        Result of function invocation
    """
    # Get the function reference
    func_ref = pipe_func.func
    if not isinstance(func_ref, comp.ast.FuncRef):
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
    # Update _value scope to chain $out -> $in with the new $in value
    pipeline_scopes['_value'] = ChainedScope(
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


def _execute_pipe_struct(pipe_struct, input_value, module, scopes):
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
    # Update _value scope to chain $out -> $in with the new $in value
    pipe_scopes['_value'] = ChainedScope(
        pipe_scopes.get('out', _value.Value(None)),
        input_value
    )

    # PipeStruct contains structure children (StructAssign, StructUnnamed, etc.)
    # We need to evaluate them as a structure
    # Create a temporary Structure node to evaluate
    temp_struct = comp.ast.Structure()
    temp_struct.kids = pipe_struct.kids

    # Evaluate the structure with the pipeline scopes
    result = evaluate(temp_struct, module, pipe_scopes)

    return result


def _is_failure(value):
    """Check if a value represents a failure (has #fail tag).

    Args:
        value: Value to check

    Returns:
        True if value is a failure
    """
    # For now, just return False - we'll implement proper failure detection later
    # when we have tag support in the runtime
    return False



class ChainedScope:
    """A read-only scope that chains through multiple underlying scopes.

    Used for ^ scope which looks up: $arg -> $ctx -> $mod
    Acts like a Value with struct fields for evaluation purposes.
    """

    def __init__(self, *scopes: _value.Value):
        """Create a chained scope from multiple Value scopes.

        Args:
            *scopes: Values to chain in lookup order (first has priority)
        """
        self.scopes = scopes

    @property
    def is_num(self):
        return False

    @property
    def is_str(self):
        return False

    @property
    def is_tag(self):
        return False

    @property
    def is_struct(self):
        return True

    @property
    def struct(self):
        """Virtual struct that merges all scopes.

        Returns fields from first scope that has them.
        """
        # Create a merged view (later scopes first, so earlier scopes override)
        merged = {}

        for scope in reversed(self.scopes):
            if scope.is_struct and scope.struct:
                merged.update(scope.struct)

        return merged if merged else None

    def lookup_field(self, field_key):
        """Look up a field by walking through scopes.

        Args:
            field_key: The field key to look up

        Returns:
            Value from first scope that has the field, or None
        """
        for scope in self.scopes:
            if scope.is_struct and scope.struct:
                if field_key in scope.struct:
                    return scope.struct[field_key]
        return None

    def __repr__(self) -> str:
        return f"ChainedScope({len(self.scopes)} scopes)"
