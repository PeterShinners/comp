"""Identifier and field access nodes.

Identifiers are chains of field lookups: @user.account.name
Each part of the chain is a different field type that knows how to
navigate through Values.

Identifier is a ValueNode (self-contained coordinator).
Field types are FieldNode (require field_value context from parent).
"""

from .base import ValueNode, FieldNode
from ..value import Value


class Identifier(ValueNode):
    """Chain of field lookups: scope.field.field...

    The key insight: Identifier is NOT one massive evaluation function.
    Instead, it's a coordinator that evaluates fields in sequence, threading
    the current value through each field lookup via engine context.

    Examples:
    - @user.account.active - ScopeField('@') followed by TokenFields
    - one.two.three - TokenFields that start with implicit scope lookup
    - #0.name - IndexField followed by TokenField

    Correct by Construction:
    - At least one field
    - ScopeField can ONLY appear as first field
    - First field can be ScopeField, TokenField, or IndexField
    """

    def __init__(self, fields: list[FieldNode]):
        """Create identifier from field chain.

        Args:
            fields: Ordered list of field nodes to traverse

        Raises:
            ValueError: If fields list is empty or ScopeField appears after first position
            TypeError: If any field is not a Field instance
        """
        if not fields:
            raise ValueError("Identifier requires at least one field")
        if not all(isinstance(f, FieldNode) for f in fields):
            raise TypeError("All fields must be FieldNode instances")

        # ScopeField can ONLY be first (parser guarantees this, but validate anyway)
        for i, field in enumerate(fields):
            if i and isinstance(field, ScopeField):
                raise ValueError(
                    f"ScopeField can only appear as first field, found at position {i}"
                )

        # First field can be: ScopeField, TokenField, IndexField, or ComputeField
        # (StringField would also work but parser can't disambiguate it)

        self.fields = fields

    def evaluate(self, engine):
        """Evaluate identifier by walking field chain.

        Creates an 'identifier' scope containing the current value being navigated.
        Each field accesses this scope to get the value it should operate on.

        No validation needed - constructor guarantees validity.
        """
        # First field evaluates without identifier scope
        # (it will look up in scopes if needed)
        current_value = yield self.fields[0]

        # Walk remaining fields, each uses current from identifier scope
        for field in self.fields[1:]:
            # Create identifier scope with current value
            # Note: dict keys must be Value objects
            identifier_scope = Value({Value('current'): current_value})
            with engine.scope_frame(identifier=identifier_scope):
                current_value = yield field

        return current_value

    def unparse(self) -> str:
        """Convert back to source code."""
        return "".join(field.unparse() for field in self.fields)


class ScopeField(FieldNode):
    """Scope reference: @, ^, $name

    This is always the first field in an identifier - looks up in engine's scopes.
    Doesn't use field_value context.

    Correct by Construction:
    - scope_name is non-empty string
    - Identifier.__init__ ensures this only appears first
    """

    # Valid scope prefixes
    VALID_SCOPES = {'@', '^', '$'}

    def __init__(self, scope_name: str):
        """Create scope field.

        Args:
            scope_name: Scope to look up ('@', '^', '$name', or plain name)

        Raises:
            ValueError: If scope_name is empty
            TypeError: If scope_name is not a string
        """
        if not isinstance(scope_name, str):
            raise TypeError("Scope name must be string")
        if not scope_name:
            raise ValueError("Scope name cannot be empty")
        self.scope_name = scope_name

    def evaluate(self, engine):
        """Look up scope in engine.

        Always called without field_value context (guaranteed by Identifier).

        Runtime check: Scope must exist in engine.scopes.
        """
        # Map symbols to names
        if self.scope_name == '@':
            scope_name = 'local'
        elif self.scope_name == '^':
            scope_name = 'chained'
        elif self.scope_name.startswith('$'):
            scope_name = self.scope_name[1:]
        else:
            scope_name = self.scope_name

        # Runtime check: scope must exist
        scope = engine.get_scope(scope_name)
        if scope is None:
            return engine.fail(f"Scope {self.scope_name} not defined")
        return scope
        yield  # Make it a generator

    def unparse(self) -> str:
        """Convert back to source code."""
        return self.scope_name


class TokenField(FieldNode):
    """Named field access: .name

    Two modes:
    1. First field: Looks up in implicit scopes (unnamed -> out -> in)
    2. Later field: Looks up in current value from field_value context

    Correct by Construction: name is non-empty string.
    """

    def __init__(self, name: str):
        """Create token field.

        Args:
            name: Field name to look up

        Raises:
            ValueError: If name is empty
            TypeError: If name is not a string
        """
        if not isinstance(name, str):
            raise TypeError("Field name must be string")
        if not name:
            raise ValueError("Field name cannot be empty")
        self.name = name

    def evaluate(self, engine):
        """Look up named field.

        If no identifier scope: This is first field, use implicit scopes.
        If identifier scope exists: Look up in current value from that scope.

        Runtime checks:
        - Current value must be a struct
        - Field must exist in struct
        """
        # Check if we're the first field (no identifier scope)
        identifier_scope = engine.get_scope('identifier')

        if identifier_scope is None:
            # First field: use implicit scope lookup
            current = engine.get_scope('unnamed')
            if current is None:
                return engine.fail(f"No implicit scope available for field '{self.name}'")
        else:
            # Later field: get current from identifier scope
            current_key = Value('current')
            if not identifier_scope.is_struct or current_key not in identifier_scope.struct:
                return engine.fail("Invalid identifier scope structure")
            current = identifier_scope.struct[current_key]

        # Handle ChainedScope (special lookup)
        if hasattr(current, 'lookup_field'):
            field_key = Value(self.name)
            result = current.lookup_field(field_key)
            if result is None:
                return engine.fail(f"Field '{self.name}' not found in chained scope")
            return result

        # Runtime check: must be struct
        if not current.is_struct:
            return engine.fail(f"Cannot access field '{self.name}' on non-struct value")

        field_key = Value(self.name)
        # Runtime check: field must exist
        if field_key not in current.struct:
            return engine.fail(f"Field '{self.name}' not found in struct")

        return current.struct[field_key]
        yield  # Make it a generator

    def unparse(self) -> str:
        """Convert back to source code."""
        return f".{self.name}"


class IndexField(FieldNode):
    """Positional field access: #0, #1, #2...

    Two modes:
    1. First field: Looks up in $in scope directly
    2. Later field: Accesses Nth field of current value's struct

    Correct by Construction: index is non-negative integer.
    """

    def __init__(self, index: int):
        """Create index field.

        Args:
            index: Zero-based position to access

        Raises:
            ValueError: If index is negative
            TypeError: If index is not an integer
        """
        if not isinstance(index, int):
            raise TypeError("Index must be integer")
        if index < 0:
            raise ValueError("Index cannot be negative")
        self.index = index

    def evaluate(self, engine):
        """Look up field by position.

        If no identifier scope: This is first field, use $in scope.
        If identifier scope exists: Look up by index in current value from that scope.

        Runtime checks:
        - Current value must be a struct
        - Index must be in bounds
        """
        # Check if we're the first field (no identifier scope)
        identifier_scope = engine.get_scope('identifier')

        if identifier_scope is None:
            # First field: use $in scope
            if 'in' not in engine.scopes:
                return engine.fail("$in scope not available for indexed access")
            current = engine.scopes['in']
        else:
            # Later field: get current from identifier scope
            current_key = Value('current')
            if not identifier_scope.is_struct or current_key not in identifier_scope.struct:
                return engine.fail("Invalid identifier scope structure")
            current = identifier_scope.struct[current_key]

        # Handle ChainedScope
        if hasattr(current, 'lookup_field') and hasattr(current, 'struct'):
            if current.struct:
                fields_list = list(current.struct.values())
                if 0 <= self.index < len(fields_list):
                    return fields_list[self.index]
                else:
                    return engine.fail(
                        f"Index #{self.index} out of bounds "
                        f"(scope has {len(fields_list)} fields)"
                    )
            else:
                return engine.fail("Cannot index empty chained scope")

        # Handle regular Value struct
        if not current.is_struct or not current.struct:
            return engine.fail("Cannot index non-struct value")

        fields_list = list(current.struct.values())
        if 0 <= self.index < len(fields_list):
            return fields_list[self.index]
        else:
            return engine.fail(
                f"Index #{self.index} out of bounds "
                f"(struct has {len(fields_list)} fields)"
            )

        yield  # Make it a generator

    def unparse(self) -> str:
        """Convert back to source code."""
        return f"#{self.index}"


class ComputeField(FieldNode):
    """Computed field access: .[expr]

    Evaluates an expression to determine the field key.
    Gets current value from identifier scope.

    Correct by Construction: expr is a valid AstNode.
    """

    def __init__(self, expr: 'ValueNode'):
        """Create computed field.

        Args:
            expr: Expression that evaluates to field key

        Raises:
            TypeError: If expr is not an AstNode
        """
        from .base import AstNode
        if not isinstance(expr, AstNode):
            raise TypeError("ComputeField expression must be AstNode")
        self.expr = expr

    def evaluate(self, engine):
        """Evaluate expression, then look up that field.

        Runtime checks:
        - Expression must evaluate successfully
        - Current value must be a struct
        - Computed key must exist in struct
        """
        # Get current value from identifier scope (set by Identifier)
        identifier_scope = engine.get_scope('identifier')
        if identifier_scope is None:
            return engine.fail("ComputeField requires identifier scope")

        current_key = Value('current')
        if not identifier_scope.is_struct or current_key not in identifier_scope.struct:
            return engine.fail("Invalid identifier scope structure")
        current = identifier_scope.struct[current_key]

        # First evaluate the expression to get the key
        field_key = yield self.expr

        # Handle ChainedScope
        if hasattr(current, 'lookup_field'):
            result = current.lookup_field(field_key)
            if result is None:
                return engine.fail("Computed field not found in chained scope")
            return result

        # Handle regular Value struct
        if not current.is_struct or not current.struct:
            return engine.fail("Cannot access computed field on non-struct value")

        if field_key not in current.struct:
            # Better error with available keys
            keys_str = ", ".join(str(k) for k in current.struct.keys())
            return engine.fail(
                f"Computed field key {field_key} not found in struct "
                f"(available keys: {keys_str})"
            )

        return current.struct[field_key]

    def unparse(self) -> str:
        """Convert back to source code."""
        return f".[{self.expr.unparse()}]"

