"""Function invocation for runtime execution."""

__all__ = ["invoke"]

import comp
from . import _func, _value, _eval, _assign


def invoke(func, mod, input_value=None, ctx_value=None, mod_value=None, arg_value=None):
    """Invoke a function and return its result.

    Args:
        func: Function definition to invoke
        mod: Module context for evaluation
        input_value: Input value for $in scope
        ctx_value: Context value for $ctx scope
        mod_value: Module value for $mod scope
        arg_value: Argument value for $arg scope

    Returns:
        Result value from function execution
    """
    # For now, just use the first implementation
    if not func.implementations:
        return _fail(f"Function {func.name} has no implementations")

    impl = func.implementations[0]

    # Check if this is a Python-implemented function
    if isinstance(impl, _func.PythonFuncImpl):
        # Call the Python function directly
        in_value = input_value or _value.Value(None)
        arg_val = arg_value or _value.Value(None)
        return impl.python_func(in_value, arg_val)

    # Regular Comp function - execute the body
    body = impl._ast_node.body

    if body is None:
        return _value.Value(None)

    # Build scope context
    # $in is immutable (read-only)
    in_scope = input_value or _value.Value(None)

    # $ctx, $mod, $arg are mutable (can be overwritten in current implementation)
    # In the future, we might want to make these immutable too
    ctx_scope = ctx_value or _value.Value(None)
    mod_scope = mod_value or _value.Value(None)
    arg_scope = arg_value or _value.Value(None)

    # $out starts empty and gets updated as we build the result structure (read-only)
    out_scope = _value.Value(None)

    # ^ is a chained scope: $arg -> $ctx -> $mod (immutable, read-only)
    chained_scope = _eval.ChainedScope(arg_scope, ctx_scope, mod_scope)

    # Unnamed scope chains: $out -> $in (for unscoped field references)
    unnamed_scope = _eval.ChainedScope(out_scope, in_scope)

    scopes = {
        'in': in_scope,
        'ctx': ctx_scope,
        'mod': mod_scope,
        'arg': arg_scope,
        'out': out_scope,
        'chained': chained_scope,  # Maps to ^
        'unnamed': unnamed_scope,  # Maps to unscoped identifiers
    }

    # Execute the function body
    return _execute_structure(body, mod, scopes)


def _execute_structure(struct_node, mod, scopes):
    """Execute a structure definition and build a Value.

    Args:
        struct_node: AST structure node to execute
        mod: Module context for evaluation
        scopes: Scope values dict (in, ctx, mod, arg, out, unnamed)

    Returns:
        Structure value with named and unnamed fields
    """
    fields = {}

    # Initialize local scope if not present
    if 'local' not in scopes:
        local_scope = _value.Value(None)  # Empty struct
        scopes['local'] = local_scope

    # Helper to update $out scope with current fields
    def update_out_scope():
        """Update $out scope to reflect current fields being built."""
        out_value = _value.Value(None)
        out_value.struct = dict(fields)  # Copy current fields
        scopes['out'] = out_value
        # Also update the unnamed scope to chain $out -> $in
        scopes['unnamed'] = _eval.ChainedScope(out_value, scopes['in'])

    for child in struct_node.kids:
        if isinstance(child, comp.ast.StructAssign):
            # Check if this is a local scope assignment (@field = value)
            if child.key and isinstance(child.key, comp.ast.Identifier) and child.key.kids:
                first_field = child.key.kids[0]
                if isinstance(first_field, comp.ast.ScopeField) and first_field.value == '@':
                    # This is a local scope assignment: @field = value
                    # Treat as: @ = {..@ field=value}
                    if len(child.key.kids) == 2 and isinstance(child.key.kids[1], comp.ast.TokenField):
                        field_name = child.key.kids[1].value
                        if child.value:
                            field_value = _eval.evaluate(child.value, mod, scopes)
                            if _eval.is_failure(field_value):
                                return field_value

                            # Update local scope: spread existing locals, add new field
                            new_local_fields: dict[_value.Value | _value.Unnamed, _value.Value] = {}

                            # Spread existing local scope
                            if scopes['local'].is_struct and scopes['local'].struct:
                                new_local_fields.update(scopes['local'].struct)

                            # Add/override the new field
                            key = _value.Value(field_name)
                            new_local_fields[key] = field_value

                            # Create new local scope
                            new_local = _value.Value(None)
                            new_local.struct = new_local_fields
                            scopes['local'] = new_local

                    # Continue to next child - don't add to result struct
                    continue

            # Regular named field: key = value
            # Check if this is a nested field assignment (e.g., parent.child = value)
            if child.key and isinstance(child.key, comp.ast.Identifier) and len(child.key.kids) > 1:
                # Nested field assignment
                if child.value:
                    field_value = _eval.evaluate(child.value, mod, scopes)
                    if _eval.is_failure(field_value):
                        return field_value

                    # Check if first field is a scope reference
                    first_field = child.key.kids[0]
                    if isinstance(first_field, comp.ast.ScopeField):
                        # Scoped nested assignment (e.g., @user.name = value, $ctx.config.port = 80)
                        scope_symbol = first_field.value
                        if scope_symbol.startswith('$'):
                            scope_name = scope_symbol[1:]
                        elif scope_symbol == '@':
                            scope_name = 'local'
                        elif scope_symbol == '^':
                            scope_name = 'chained'
                        else:
                            return _fail(f"Unknown scope: {scope_symbol}")

                        if scope_name not in scopes:
                            return _fail(f"Scope {scope_symbol} not defined")

                        # Only allow mutation of ctx, mod, arg, local scopes
                        if scope_name in ('ctx', 'mod', 'arg', 'local'):
                            # Ensure scope has a struct
                            scope_value = scopes[scope_name]
                            if not scope_value.is_struct:
                                scope_value = _value.Value(None)
                                scope_value.struct = {}
                                scopes[scope_name] = scope_value
                            if scope_value.struct is None:
                                scope_value.struct = {}
                            
                            # Create an identifier without the scope prefix for the helper
                            remaining_path = comp.ast.Identifier()
                            remaining_path.kids = child.key.kids[1:]  # Skip the scope field
                            
                            # Use the shared helper to handle the nested path
                            _assign.assign_nested_field(
                                remaining_path, field_value, scope_value.struct, mod, scopes, _eval.evaluate
                            )
                            
                            # Update chained scope if we modified ctx, mod, or arg
                            if scope_name in ('ctx', 'mod', 'arg'):
                                scopes['chained'] = _eval.ChainedScope(  # type: ignore
                                    scopes['arg'], scopes['ctx'], scopes['mod']
                                )
                        else:
                            return _fail(f"Cannot assign to immutable scope {scope_symbol}")
                    else:
                        # Unscoped nested assignment (e.g., account.active = 1)
                        # Use the shared helper
                        _assign.assign_nested_field(
                            child.key, field_value, fields, mod, scopes, _eval.evaluate
                        )

                    # Update $out scope after adding nested field
                    update_out_scope()
            else:
                # Simple field assignment
                # Check if this is a scope assignment (e.g., $mod = {...})
                if (child.key and isinstance(child.key, comp.ast.Identifier) and
                    len(child.key.kids) == 1 and isinstance(child.key.kids[0], comp.ast.ScopeField)):
                    # This is a scope assignment: update the scope directly
                    scope_field = child.key.kids[0]
                    scope_symbol = scope_field.value  # e.g., "$mod", "$ctx", "$arg"

                    # Map scope symbol to scope name
                    if scope_symbol.startswith('$'):
                        scope_name = scope_symbol[1:]  # Remove $ prefix

                        # Only allow mutation of ctx, mod, arg (not in, out)
                        if scope_name in ('ctx', 'mod', 'arg') and child.value:
                            field_value = _eval.evaluate(child.value, mod, scopes)
                            if _eval.is_failure(field_value):
                                return field_value
                            # Update the scope
                            scopes[scope_name] = field_value
                            # Recreate chained scope with updated values
                            scopes['chained'] = _eval.ChainedScope(  # type: ignore
                                scopes['arg'], scopes['ctx'], scopes['mod']
                            )
                else:
                    # Regular field assignment
                    if child.key and child.value:
                        # Extract field key using shared helper (always returns Value)
                        key = _assign.extract_field_key(child.key, mod, scopes, _eval.evaluate)
                        field_value = _eval.evaluate(child.value, mod, scopes)
                        if _eval.is_failure(field_value):
                            return field_value
                        fields[key] = field_value
                        # Update $out scope after adding field
                        update_out_scope()

        elif isinstance(child, comp.ast.StructUnnamed):
            # Unnamed field: just an expression
            if child.value:
                field_value = _eval.evaluate(child.value, mod, scopes)
                if _eval.is_failure(field_value):
                    return field_value
                # Use Unnamed key
                fields[_value.Unnamed()] = field_value
                # Update $out scope after adding field
                update_out_scope()

        elif isinstance(child, comp.ast.StructSpread):
            # Spread operator: ..expr
            if child.value:
                spread_value = _eval.evaluate(child.value, mod, scopes)
                if _eval.is_failure(spread_value):
                    return spread_value

                # Handle both regular Values and ChainedScope
                if isinstance(spread_value, _eval.ChainedScope):
                    # ChainedScope: merge its virtual struct
                    if spread_value.struct:
                        fields.update(spread_value.struct)
                elif spread_value.is_struct and spread_value.struct:
                    # Regular Value: merge its struct
                    fields.update(spread_value.struct)
                # Update $out scope after spreading
                update_out_scope()
        # Ignore other node types for now

    # Create a Value and set struct directly
    result = _value.Value(None)  # Creates empty struct
    result.struct = fields
    return result



def _fail(msg):
    """Helper to create an operator failure value."""
    from . import builtin
    return _value.Value({
        _value.Unnamed(): builtin.fail_runtime,
        "message": msg,
    })
