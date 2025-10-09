"""Base classes for AST node hierarchies.

The hierarchy is organized by coordination requirements:
- ValueNode: Self-contained nodes (most common)
- FieldNode: Nodes requiring field_value context from parent
- ShapeNode: Type domain nodes
"""

from collections.abc import Generator

from ..value import Value


class AstNode:
    """Base class for all AST nodes.
    
    All AST nodes are immutable after construction and implement
    the generator-based evaluation protocol.
    
    The evaluate() method is a generator that:
    - Yields: Child node instances to evaluate
    - Receives: Value results from child evaluation
    - Returns: Final Value result
    
    Fail values automatically propagate up the tree unless a node uses
    engine.ignore_failures() to temporarily prevent propagation.
    
    This is a base class that should not be instantiated directly.
    Subclasses must implement evaluate() and unparse().
    """
    
    def evaluate(self, engine) -> Generator['AstNode', Value, Value]:
        """Evaluate this node to produce a Value.
        
        Args:
            engine: The Engine managing execution
            
        Yields:
            Child node instances that need evaluation
            
        Receives:
            Value instances (results from evaluating children)
            
        Returns:
            Final Value result
        """
        raise NotImplementedError(f"{self.__class__.__name__}.evaluate() not implemented")
    
    def unparse(self) -> str:
        """Convert this node back to source code.
        
        Used for debugging, error messages, and code generation.
        Should produce valid Comp source that parses back to equivalent AST.
        
        Returns:
            Source code string
        """
        raise NotImplementedError(f"{self.__class__.__name__}.unparse() not implemented")


class ValueNode(AstNode):
    """Base class for nodes that evaluate to runtime Values.
    
    ValueNodes are self-contained: they don't require coordination context
    from their parent (though they may coordinate their own children).
    
    Examples:
    - Literals: Number, String, Tag
    - Operators: BinaryOp, UnaryOp
    - Structures: Structure, Pipeline
    - Calls: FunctionCall
    - Coordinators: Identifier (coordinates fields)
    
    This is the most common node type.
    """
    pass


class FieldNode(AstNode):
    """Base class for field access nodes.
    
    REQUIRES COORDINATION: Field nodes need their parent (usually Identifier)
    to provide field_value context via:
        with engine.context(field_value=current):
            result = yield field
    
    Field nodes navigate through a value to access a sub-field.
    
    Examples: TokenField, IndexField, ComputeField
    
    Exception: ScopeField is technically a FieldNode but doesn't need
    field_value context since it's always first in the chain (it uses
    engine.scopes instead).
    """
    
    def get_current_value(self, engine) -> Value:
        """Get the current value from engine context.
        
        Parent must have set this via:
            with engine.context(field_value=current):
                result = yield field
                
        Returns:
            The current value to navigate from
            
        Raises:
            RuntimeError: If field_value context is not set
        """
        current = engine.get_context('field_value')
        if current is None:
            raise RuntimeError(
                f"{self.__class__.__name__} requires field_value context. "
                f"Parent must set via: with engine.context(field_value=...)"
            )
        return current


class ShapeNode(AstNode):
    """Base class for nodes that represent shape/type information.
    
    These nodes evaluate in the shape domain and produce ShapeValue results.
    They cannot be used where regular Values are expected.
    
    ShapeValues never escape shape contexts - they're compile-time only.
    
    This is a base class that should not be instantiated directly.
    """
    pass
