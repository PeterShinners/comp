"""Expression evaluation for runtime values."""

__all__ = ["evaluate"]

from typing import TYPE_CHECKING

from .. import ast
from . import _value

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
                field_name = child.key.unparse() if child.key else None
                if field_name and child.value:
                    field_value = evaluate(child.value, module, scopes)
                    fields[field_name] = field_value
        return _value.Value(fields)

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
        # Strip the $ prefix for named scopes
        if scope_name.startswith('$'):
            scope_name = scope_name[1:]

        # Get the scope value
        if scope_name not in scopes:
            raise ValueError(f"Scope ${scope_name} not defined")

        current_value = scopes[scope_name]

        # Walk through remaining fields
        for field in expr.kids[1:]:
            if not current_value.is_struct or not current_value.struct:
                raise ValueError("Cannot access field on non-struct value")

            if isinstance(field, ast.TokenField):
                # Look up field by name
                field_key = _value.Value(field.value)
                if field_key in current_value.struct:
                    current_value = current_value.struct[field_key]
                else:
                    raise ValueError(f"Field '{field.value}' not found in struct")
            elif isinstance(field, ast.IndexField):
                # Look up by index (unnamed fields)
                # For now, raise not implemented
                raise NotImplementedError("Index field lookup not yet implemented")
            else:
                raise ValueError(f"Unsupported field type: {type(field).__name__}")

        return current_value

    # No scope prefix - for now, raise not implemented
    raise NotImplementedError("Non-scope identifiers not yet implemented")
