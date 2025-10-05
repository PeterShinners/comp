"""Function invocation for runtime execution."""

__all__ = ["invoke"]

from typing import TYPE_CHECKING

from .. import ast
from . import _eval, _struct, _value

if TYPE_CHECKING:
    from . import _module


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
    body = impl._ast_node.body

    if body is None:
        return _value.Value(None)

    # Build scope context
    scopes = {
        'in': input_value or _value.Value(None),
        'ctx': ctx_value or _value.Value(None),
        'mod': mod_value or _value.Value(None),
        'arg': arg_value or _value.Value(None),
    }

    # Execute the function body
    return _execute_structure(body, module, scopes)


def _execute_structure(struct_node: ast.Structure, module: '_module.Module', scopes: dict[str, _value.Value]) -> _value.Value:
    """Execute a structure definition and build a Value.

    Args:
        struct_node: AST structure node to execute
        module: Module context for evaluation
        scopes: Scope values dict (in, ctx, mod, arg)

    Returns:
        Structure value with named and unnamed fields
    """
    fields: dict[_value.Value | _struct.Unnamed, _value.Value] = {}

    for child in struct_node.kids:
        if isinstance(child, ast.StructAssign):
            # Named field: key = value
            field_name = child.key.unparse() if child.key else None
            if field_name and child.value:
                field_value = _eval.evaluate(child.value, module, scopes)
                # Key is a string Value
                key = _value.Value(field_name)
                fields[key] = field_value
        elif isinstance(child, ast.StructUnnamed):
            # Unnamed field: just an expression
            if child.value:
                field_value = _eval.evaluate(child.value, module, scopes)
                # Use Unnamed key
                fields[_struct.Unnamed()] = field_value
        elif isinstance(child, ast.StructSpread):
            # Spread operator: ..expr
            # For now, just evaluate and merge
            if child.value:
                spread_value = _eval.evaluate(child.value, module, scopes)
                if spread_value.is_struct and spread_value.struct:
                    # Merge fields from spread value
                    fields.update(spread_value.struct)
        # Ignore other node types for now

    # Create a Value and set struct directly
    result = _value.Value(None)  # Creates empty struct
    result.struct = fields
    return result
