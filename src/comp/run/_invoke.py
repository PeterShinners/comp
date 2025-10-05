"""Function invocation for runtime execution."""

__all__ = ["invoke"]

from typing import TYPE_CHECKING

from .. import ast
from . import _eval, _module, _scope, _struct, _value

if TYPE_CHECKING:
    pass


def invoke(
    func_def: '_module.FuncDef',
    module: '_module.Module',
    input_value: _value.Value | None = None,
    ctx_value: _value.Value | None = None,
    mod_value: _value.Value | None = None,
    arg_value: _value.Value | None = None
) -> _value.Value:
    """Invoke a function and return its result.

    Args:
        func_def: Function definition to invoke
        module: Module context for evaluation
        input_value: Input value for $in scope
        ctx_value: Context value for $ctx scope
        mod_value: Module value for $mod scope
        arg_value: Argument value for $arg scope

    Returns:
        Result value from function execution
    """
    # For now, just use the first implementation
    if not func_def.implementations:
        raise ValueError(f"Function {func_def.name} has no implementations")

    impl = func_def.implementations[0]
    
    # Check if this is a Python-implemented function
    if isinstance(impl, _module.PythonFuncImpl):
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
    chained_scope = _scope.ChainedScope(arg_scope, ctx_scope, mod_scope)

    # Unnamed scope chains: $out -> $in (for unscoped field references)
    unnamed_scope = _scope.ChainedScope(out_scope, in_scope)

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
    return _execute_structure(body, module, scopes)


def _execute_structure(struct_node: ast.Structure, module: '_module.Module', scopes: dict[str, _value.Value]) -> _value.Value:
    """Execute a structure definition and build a Value.

    Args:
        struct_node: AST structure node to execute
        module: Module context for evaluation
        scopes: Scope values dict (in, ctx, mod, arg, out, unnamed)

    Returns:
        Structure value with named and unnamed fields
    """
    fields: dict[_value.Value | _struct.Unnamed, _value.Value] = {}

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
        scopes['unnamed'] = _scope.ChainedScope(out_value, scopes['in'])

    for child in struct_node.kids:
        if isinstance(child, ast.StructAssign):
            # Check if this is a local scope assignment (@field = value)
            if child.key and isinstance(child.key, ast.Identifier) and child.key.kids:
                first_field = child.key.kids[0]
                if isinstance(first_field, ast.ScopeField) and first_field.value == '@':
                    # This is a local scope assignment: @field = value
                    # Treat as: @ = {..@ field=value}
                    if len(child.key.kids) == 2 and isinstance(child.key.kids[1], ast.TokenField):
                        field_name = child.key.kids[1].value
                        if child.value:
                            field_value = _eval.evaluate(child.value, module, scopes)

                            # Update local scope: spread existing locals, add new field
                            new_local_fields: dict[_value.Value | _struct.Unnamed, _value.Value] = {}

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
            if child.key and isinstance(child.key, ast.Identifier) and len(child.key.kids) > 1:
                # Nested field assignment - walk down and create intermediate structures
                if child.value:
                    field_value = _eval.evaluate(child.value, module, scopes)

                    # Build the nested structure incrementally
                    # Start from the root and walk down, creating structs as needed
                    current_dict = fields
                    is_scoped = False

                    # Check if first field is a scope reference
                    first_field = child.key.kids[0]
                    if isinstance(first_field, ast.ScopeField):
                        # Starting from a scope - need to modify scope value
                        is_scoped = True
                        scope_symbol = first_field.value
                        if scope_symbol.startswith('$'):
                            scope_name = scope_symbol[1:]
                        elif scope_symbol == '@':
                            scope_name = 'local'
                        elif scope_symbol == '^':
                            scope_name = 'chained'
                        else:
                            raise ValueError(f"Unknown scope: {scope_symbol}")

                        if scope_name not in scopes:
                            raise ValueError(f"Scope {scope_symbol} not defined")

                        # For mutable scopes, we can modify them
                        if scope_name in ('ctx', 'mod', 'arg', 'local'):
                            # Start from the scope's struct
                            scope_value = scopes[scope_name]
                            if not scope_value.is_struct:
                                # Need to create a struct
                                scope_value = _value.Value(None)
                                scope_value.struct = {}
                                scopes[scope_name] = scope_value
                            if scope_value.struct is None:
                                scope_value.struct = {}
                            current_dict = scope_value.struct
                        else:
                            raise ValueError(f"Cannot assign to immutable scope {scope_symbol}")

                    # Determine which fields to walk through
                    if is_scoped:
                        # Skip the scope field (first), walk up to but not including the last
                        walk_fields = child.key.kids[1:-1]
                        final_field = child.key.kids[-1]
                    else:
                        # Walk all but the last field
                        walk_fields = child.key.kids[:-1]
                        final_field = child.key.kids[-1]

                    # Walk through intermediate fields
                    for field_node in walk_fields:
                        if isinstance(field_node, ast.TokenField):
                            field_key = _value.Value(field_node.value)

                            # Get or create intermediate structure
                            if field_key in current_dict:
                                # Field exists, navigate into it
                                current_value = current_dict[field_key]
                                if not current_value.is_struct or current_value.struct is None:
                                    # Need to replace with a struct
                                    new_struct = _value.Value(None)
                                    new_struct.struct = {}
                                    current_dict[field_key] = new_struct
                                    current_dict = new_struct.struct
                                else:
                                    current_dict = current_value.struct
                            else:
                                # Create new intermediate structure
                                new_struct = _value.Value(None)
                                new_struct.struct = {}
                                current_dict[field_key] = new_struct
                                current_dict = new_struct.struct
                        elif isinstance(field_node, ast.String):
                            # String field - same as TokenField but with string value
                            field_key = _value.Value(field_node.value)

                            # Get or create intermediate structure
                            if field_key in current_dict:
                                # Field exists, navigate into it
                                current_value = current_dict[field_key]
                                if not current_value.is_struct or current_value.struct is None:
                                    # Need to replace with a struct
                                    new_struct = _value.Value(None)
                                    new_struct.struct = {}
                                    current_dict[field_key] = new_struct
                                    current_dict = new_struct.struct
                                else:
                                    current_dict = current_value.struct
                            else:
                                # Create new intermediate structure
                                new_struct = _value.Value(None)
                                new_struct.struct = {}
                                current_dict[field_key] = new_struct
                                current_dict = new_struct.struct
                        elif isinstance(field_node, ast.IndexField):
                            # Index field - get the Nth key from current struct
                            index = field_node.value
                            if current_dict:
                                keys_list = list(current_dict.keys())
                                if 0 <= index < len(keys_list):
                                    field_key = keys_list[index]
                                    current_value = current_dict[field_key]
                                    if not current_value.is_struct or current_value.struct is None:
                                        # Need to replace with a struct
                                        new_struct = _value.Value(None)
                                        new_struct.struct = {}
                                        current_dict[field_key] = new_struct
                                        current_dict = new_struct.struct
                                    else:
                                        current_dict = current_value.struct
                                else:
                                    raise ValueError(f"Index #{index} out of bounds (struct has {len(keys_list)} fields)")
                            else:
                                raise ValueError("Cannot index empty struct in assignment")
                        elif isinstance(field_node, ast.ComputeField):
                            # Computed field - evaluate expression to get field key
                            if field_node.expr:
                                computed_key = _eval.evaluate(field_node.expr, module, scopes)

                                # Get or create intermediate structure
                                if computed_key in current_dict:
                                    # Field exists, navigate into it
                                    current_value = current_dict[computed_key]
                                    if not current_value.is_struct or current_value.struct is None:
                                        # Need to replace with a struct
                                        new_struct = _value.Value(None)
                                        new_struct.struct = {}
                                        current_dict[computed_key] = new_struct
                                        current_dict = new_struct.struct
                                    else:
                                        current_dict = current_value.struct
                                else:
                                    # Create new intermediate structure
                                    new_struct = _value.Value(None)
                                    new_struct.struct = {}
                                    current_dict[computed_key] = new_struct
                                    current_dict = new_struct.struct
                            else:
                                raise ValueError("ComputeField missing expression")
                        else:
                            raise NotImplementedError(f"Nested assignment with {type(field_node).__name__} not yet supported")

                    # Set the final field
                    if isinstance(final_field, ast.TokenField):
                        final_key = _value.Value(final_field.value)
                        current_dict[final_key] = field_value
                    elif isinstance(final_field, ast.String):
                        # String field - same as TokenField but with string value
                        final_key = _value.Value(final_field.value)
                        current_dict[final_key] = field_value
                    elif isinstance(final_field, ast.IndexField):
                        # Index assignment - update value at Nth position
                        index = final_field.value
                        if current_dict:
                            keys_list = list(current_dict.keys())
                            if 0 <= index < len(keys_list):
                                # Reuse existing key to preserve order
                                final_key = keys_list[index]
                                current_dict[final_key] = field_value
                            else:
                                raise ValueError(f"Index #{index} out of bounds (struct has {len(keys_list)} fields)")
                        else:
                            raise ValueError("Cannot assign to index in empty struct")
                    elif isinstance(final_field, ast.ComputeField):
                        # Computed field - evaluate expression to get field key
                        if final_field.expr:
                            computed_key = _eval.evaluate(final_field.expr, module, scopes)
                            current_dict[computed_key] = field_value
                        else:
                            raise ValueError("ComputeField missing expression")
                    else:
                        raise NotImplementedError(f"Final field {type(final_field).__name__} not yet supported")

                    # If this was a scoped assignment, update the chained scope
                    if is_scoped and scope_name in ('ctx', 'mod', 'arg'):
                        scopes['chained'] = _scope.ChainedScope(  # type: ignore
                            scopes['arg'], scopes['ctx'], scopes['mod']
                        )

                    # Update $out scope after adding nested field
                    update_out_scope()
            else:
                # Simple field assignment
                # Check if this is a scope assignment (e.g., $mod = {...})
                if (child.key and isinstance(child.key, ast.Identifier) and
                    len(child.key.kids) == 1 and isinstance(child.key.kids[0], ast.ScopeField)):
                    # This is a scope assignment: update the scope directly
                    scope_field = child.key.kids[0]
                    scope_symbol = scope_field.value  # e.g., "$mod", "$ctx", "$arg"

                    # Map scope symbol to scope name
                    if scope_symbol.startswith('$'):
                        scope_name = scope_symbol[1:]  # Remove $ prefix

                        # Only allow mutation of ctx, mod, arg (not in, out)
                        if scope_name in ('ctx', 'mod', 'arg') and child.value:
                            field_value = _eval.evaluate(child.value, module, scopes)
                            # Update the scope
                            scopes[scope_name] = field_value
                            # Recreate chained scope with updated values
                            scopes['chained'] = _scope.ChainedScope(  # type: ignore
                                scopes['arg'], scopes['ctx'], scopes['mod']
                            )
                else:
                    # Regular field assignment
                    if child.key and child.value:
                        # Check if key is a single ComputeField that needs evaluation
                        if (isinstance(child.key, ast.Identifier) and
                            len(child.key.kids) == 1 and
                            isinstance(child.key.kids[0], ast.ComputeField)):
                            # Evaluate the ComputeField expression to get the key
                            compute_field = child.key.kids[0]
                            if compute_field.expr:
                                key = _eval.evaluate(compute_field.expr, module, scopes)
                            else:
                                raise ValueError("ComputeField missing expression")
                        else:
                            # Simple key - should be an Identifier with a single TokenField or String
                            if (isinstance(child.key, ast.Identifier) and
                                len(child.key.kids) == 1):
                                first_field = child.key.kids[0]
                                if isinstance(first_field, ast.TokenField):
                                    key = _value.Value(first_field.value)
                                elif isinstance(first_field, ast.String):
                                    key = _value.Value(first_field.value)
                                else:
                                    raise ValueError(f"Unsupported simple field type: {type(first_field).__name__}")
                            else:
                                raise ValueError("Simple field key must be a single TokenField or String")

                        field_value = _eval.evaluate(child.value, module, scopes)
                        fields[key] = field_value
                        # Update $out scope after adding field
                        update_out_scope()

        elif isinstance(child, ast.StructUnnamed):
            # Unnamed field: just an expression
            if child.value:
                field_value = _eval.evaluate(child.value, module, scopes)
                # Use Unnamed key
                fields[_struct.Unnamed()] = field_value
                # Update $out scope after adding field
                update_out_scope()

        elif isinstance(child, ast.StructSpread):
            # Spread operator: ..expr
            if child.value:
                spread_value = _eval.evaluate(child.value, module, scopes)

                # Handle both regular Values and ChainedScope
                if isinstance(spread_value, _scope.ChainedScope):
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
