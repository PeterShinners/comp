"""Nodes for identifier and field lookups."""

__all__ = ["Identifier", "ScopeField", "TokenField", "IndexField", "ComputeField"]

import comp

from . import _base


class Identifier(_base.ValueNode):
    """Chain of field lookups: scope.field.field...

    The key insight: Identifier is NOT one massive evaluation function.
    Instead, it's a coordinator that evaluates fields in sequence, threading
    the current value through each field lookup via engine context.

    Examples:
    - @user.account.active - ScopeField('@') followed by TokenFields
    - one.two.three - TokenFields that start with implicit scope lookup
    - #0.name - IndexField followed by TokenField

    ScopeFields can only be in the first position. The parser can only
    generate StringFields after the first field, but there's no technical
    restriction for the AST.

    Args:
        fields: Ordered list of field nodes to traverse

    """

    def __init__(self, fields: list[_base.FieldNode]):
        if not fields:
            raise ValueError("Identifier requires at least one field")
        if not all(isinstance(f, _base.FieldNode) for f in fields):
            raise TypeError("All fields must be _base.FieldNode instances")

        # ScopeField can ONLY be first (parser guarantees this, but validate anyway)
        for i, field in enumerate(fields):
            if i and isinstance(field, ScopeField):
                raise ValueError(
                    f"ScopeField can only appear as first field, found at index {i}"
                )

        # First field can be: ScopeField, TokenField, IndexField, or ComputeField
        # (StringField would also work but parser can't disambiguate it)

        self.fields = fields

    def evaluate(self, frame):
        # First field evaluates without identifier scope
        # (it will look up in scopes if needed)
        current_value = yield comp.Compute(self.fields[0])

        # Walk remaining fields, each uses current value directly as identifier scope
        for field in self.fields[1:]:
            # Pass current value directly as the identifier scope
            current_value = yield comp.Compute(field, identifier=current_value)

        return current_value

    def unparse(self) -> str:
        return "".join(field.unparse() for field in self.fields)


class ScopeField(_base.FieldNode):
    """Scope reference: @, ^, $name

    Args:
        scope_name: Scope to look up ('@', '^', '$name', or plain name)
    """

    # Valid scope prefixes
    VALID_SCOPES = {'@', '^', '$'}

    def __init__(self, scope_name: str):
        if not isinstance(scope_name, str):
            raise TypeError("Scope name must be string")
        if not scope_name:
            raise ValueError("Scope name cannot be empty")
        self.scope_name = scope_name

    def evaluate(self, frame):
        # Map symbols to names
        if self.scope_name == '@':
            scope_name = 'local'
        elif self.scope_name == '^':
            scope_name = 'unnamed'
        elif self.scope_name.startswith('$'):
            scope_name = self.scope_name[1:]
        else:
            scope_name = self.scope_name

        # Runtime check: scope must exist
        scope = frame.scope(scope_name)
        if scope is None:
            return comp.fail(f"Scope {self.scope_name} not defined")
        return scope
        yield  # Make it a generator

    def unparse(self) -> str:
        return self.scope_name


class TokenField(_base.FieldNode):
    """Named field access: .name

    Args:
        name: Field name to look up
    """

    def __init__(self, name: str):
        if not isinstance(name, str):
            raise TypeError("Field name must be string")
        if not name:
            raise ValueError("Field name cannot be empty")
        self.name = name

    def evaluate(self, frame):
        # Check if we're the first field (no identifier scope)
        current = frame.scope('identifier')

        if current is None:
            # First field: use implicit scope lookup
            current = frame.scope('unnamed')
            if current is None:
                return comp.fail(f"No implicit scope available for field '{self.name}'")

        # Handle ChainedScope (special lookup)
        if hasattr(current, 'lookup_field'):
            field_key = comp.Value(self.name)
            result = current.lookup_field(field_key)
            if result is None:
                return comp.fail(f"Field '{self.name}' not found in chained scope")
            return result

        # Runtime check: must be struct
        if not current.is_struct:
            return comp.fail(f"Cannot access field '{self.name}' on non-struct value")

        field_key = comp.Value(self.name)
        # Runtime check: field must exist
        if field_key not in current.struct:
            return comp.fail(f"Field '{self.name}' not found in struct")

        return current.struct[field_key]
        yield  # Make it a generator

    def unparse(self) -> str:
        return f".{self.name}"


class IndexField(_base.FieldNode):
    """Positional field access: #0, #1, #2... or #(expr)

    Args:
        index: Zero-based position (int literal) or expression that evaluates to a number
    """

    def __init__(self, index: int | _base.ValueNode):
        if isinstance(index, int):
            if index < 0:
                raise ValueError("Index cannot be negative")
        elif not isinstance(index, _base.ValueNode):
            raise TypeError("Index must be integer or ValueNode")
        self.index = index

    def evaluate(self, frame):
        # Evaluate index if it's an expression
        if isinstance(self.index, _base.ValueNode):
            index_value = yield comp.Compute(self.index)
            if frame.is_fail(index_value):
                return index_value
            if not index_value.is_number:
                return comp.fail(f"Index expression must evaluate to a number, got {index_value}")
            # Convert Decimal to int
            index = int(index_value.data)
            if index < 0:
                return comp.fail(f"Index cannot be negative, got {index}")
        else:
            index = self.index
        
        # Check if we're the first field (no identifier scope)
        current = frame.scope('identifier')

        if current is None:
            # First field: use $in scope
            current = frame.scope('in')
            if current is None:
                return comp.fail("$in scope not available for indexed access")

        # Handle ChainedScope
        if hasattr(current, 'lookup_field') and hasattr(current, 'struct'):
            if current.struct:
                fields_list = list(current.struct.values())
                if 0 <= index < len(fields_list):
                    return fields_list[index]
                else:
                    return comp.fail(
                        f"Index #{index} out of bounds "
                        f"(scope has {len(fields_list)} fields)"
                    )
            else:
                return comp.fail("Cannot index empty chained scope")

        # Handle regular Value struct
        if not current.is_struct or not current.struct:
            return comp.fail("Cannot index non-struct value")

        fields_list = list(current.struct.values())
        if 0 <= index < len(fields_list):
            return fields_list[index]
        else:
            return comp.fail(
                f"Index #{index} out of bounds "
                f"(struct has {len(fields_list)} fields)"
            )

    def unparse(self) -> str:
        if isinstance(self.index, int):
            return f"#{self.index}"
        else:
            # Expression - would need to unparse the expression
            return f"#(expr)"


class ComputeField(_base.FieldNode):
    """Computed field access: 'expr'

    Args:
        expr: Expression that evaluates to field key
    """

    def __init__(self, expr: '_base.ValueNode'):
        if not isinstance(expr, _base.ValueNode):
            raise TypeError("ComputeField expression must be ValueNode")
        self.expr = expr

    def evaluate(self, frame):
        # Get current value from identifier scope (set by Identifier)
        current = frame.scope('identifier')
        if current is None:
            return comp.fail("ComputeField requires identifier scope")

        # First evaluate the expression to get the key
        field_key = yield comp.Compute(self.expr)

        # Handle ChainedScope
        if hasattr(current, 'lookup_field'):
            result = current.lookup_field(field_key)
            if result is None:
                return comp.fail("Computed field not found in chained scope")
            return result

        # Handle regular Value struct
        if not current.is_struct or not current.struct:
            return comp.fail("Cannot access computed field on non-struct value")

        if field_key not in current.struct:
            # Better error with available keys
            keys_str = ", ".join(str(k) for k in current.struct.keys())
            return comp.fail(
                f"Computed field key {field_key} not found in struct "
                f"(available keys: {keys_str})"
            )

        return current.struct[field_key]

    def unparse(self) -> str:
        return f".[{self.expr.unparse()}]"

