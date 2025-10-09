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
    
    Example: @user.account.active
    - Evaluate ScopeField('@') -> gets user Value
    - Evaluate TokenField('account') with user context -> gets account Value  
    - Evaluate TokenField('active') with account context -> gets active Value
    
    Correct by Construction: If Identifier exists, it has at least one field.
    """
    
    def __init__(self, fields: list['Field']):
        """Create identifier from field chain.
        
        Args:
            fields: Ordered list of field nodes to traverse
            
        Raises:
            ValueError: If fields list is empty
            TypeError: If any field is not a Field instance
        """
        if not fields:
            raise ValueError("Identifier requires at least one field")
        if not all(isinstance(f, Field) for f in fields):
            raise TypeError("All fields must be Field instances")
        self.fields = fields
    
    def evaluate(self, engine):
        """Evaluate identifier by walking field chain.
        
        This is surprisingly simple: start with first field, then thread
        the result through remaining fields via engine context.
        
        No validation needed - constructor guarantees validity.
        """
        # First field determines starting point (scope or unnamed)
        current_value = yield self.fields[0]
        
        # Walk remaining fields, each uses current_value from context
        for field in self.fields[1:]:
            # Push current value as context for this field
            with engine.context(field_value=current_value):
                current_value = yield field
        
        return current_value
    
    def unparse(self) -> str:
        """Convert back to source code."""
        return "".join(field.unparse() for field in self.fields)


# Field nodes that know how to navigate Values


class Field(FieldNode):
    """Base class for field access operations.
    
    Fields get the current value from engine.get_context('field_value').
    Identifier is responsible for setting this context before evaluating fields.
    
    Inherits from FieldNode: Requires coordination from parent.
    
    Immutable: Fields never change after construction.
    """
    pass


class ScopeField(Field):
    """Scope reference: @, ^, $name
    
    This is the starting point - looks up in engine's scopes.
    Doesn't need field_value context since it's always first.
    
    Correct by Construction: scope_name is validated at construction.
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
        
        Runtime check: Scope must exist in engine.scopes.
        This can fail at runtime if scope isn't defined.
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
        if scope_name not in engine.scopes:
            return engine.fail(f"Scope {self.scope_name} not defined")
        
        return engine.scopes[scope_name]
        yield  # Make it a generator
    
    def unparse(self) -> str:
        """Convert back to source code."""
        return self.scope_name


class TokenField(Field):
    """Named field access: .name
    
    Looks up a named field in the current value's struct.
    Gets current value from engine.get_context('field_value').
    
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
        """Look up named field in current value.
        
        Runtime checks:
        - Current value must be a struct
        - Field must exist in struct
        """
        # Get current value from context (set by Identifier)
        current = engine.get_context('field_value')
        
        # Handle ChainedScope (special lookup)
        if hasattr(current, 'lookup_field'):
            field_key = Value(self.name)
            result = current.lookup_field(field_key)
            if result is None:
                return engine.fail(f"Field '{self.name}' not found in chained scope")
            return result
        
        # Runtime check: must be struct
        if not current.is_struct or not current.struct:
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


class IndexField(Field):
    """Positional field access: #0, #1, #2...
    
    Accesses the Nth field of a struct by position.
    Gets current value from engine.get_context('field_value').
    
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
        """Look up field by position in current value.
        
        Runtime checks:
        - Current value must be a struct
        - Index must be in bounds
        """
        # Get current value from context (set by Identifier)
        current = engine.get_context('field_value')
        
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
            return engine.fail(f"Cannot index non-struct value")
        
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


class ComputeField(Field):
    """Computed field access: .[expr]
    
    Evaluates an expression to determine the field key.
    Gets current value from engine.get_context('field_value').
    
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
        # Get current value from context (set by Identifier)
        current = engine.get_context('field_value')
        
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


class ImplicitField(Field):
    """Implicit field for bare identifiers: 'name' with no scope.
    
    Uses the 'unnamed' scope (chains $out -> $in) for field lookup.
    Special case: bare IndexField goes directly to $in instead.
    
    Correct by Construction: wrapped field is valid Field instance.
    """
    
    def __init__(self, field: Field):
        """Create implicit field wrapper.
        
        Args:
            field: The actual field to look up (TokenField, IndexField, etc.)
            
        Raises:
            TypeError: If field is not a Field instance
        """
        if not isinstance(field, Field):
            raise TypeError("ImplicitField must wrap a Field instance")
        self.field = field
    
    def evaluate(self, engine):
        """Look up field in appropriate implicit scope.
        
        Runtime check: Required scope must exist.
        """
        # IndexField goes to $in directly
        if isinstance(self.field, IndexField):
            if 'in' not in engine.scopes:
                return engine.fail("$in scope not available")
            
            # Evaluate the index field with $in as context
            with engine.context(field_value=engine.scopes['in']):
                result = yield self.field
            return result
        
        # Other fields use unnamed scope (or _value in pipelines)
        scope_key = '_value' if '_value' in engine.scopes else 'unnamed'
        if scope_key not in engine.scopes:
            return engine.fail("Unnamed scope not available")
        
        # Evaluate the field with unnamed scope as context
        with engine.context(field_value=engine.scopes[scope_key]):
            result = yield self.field
        return result
    
    def unparse(self) -> str:
        """Convert back to source code."""
        # Implicit fields don't show scope prefix
        return self.field.unparse()
