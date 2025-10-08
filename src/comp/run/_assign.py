"""Field assignment helpers for structure building.

This module provides shared utilities for assigning values to struct fields,
handling both simple single-level assignments and nested path assignments.

Used by both expression evaluation (_eval.py) and function execution (_invoke.py)
during structure construction.
"""

__all__ = ["extract_field_key", "assign_nested_field"]

import comp
from . import _value


def extract_field_key(identifier_node, module, scopes, evaluate_func):
    """Extract a field key from an Identifier AST node.
    
    Handles simple field keys (single level):
    - TokenField: field_name -> Value("field_name")
    - String: "field name" -> Value("field name")
    - ComputeField: [expr] -> Value(result)
    
    Field keys are ALWAYS returned as Value objects for consistency.
    This ensures ComputeField works the same as TokenField/String.
    
    Args:
        identifier_node: AST Identifier node with a single child
        module: Module context for evaluation
        scopes: Scope values dict
        evaluate_func: Function to call for evaluating expressions (e.g., _eval.evaluate)
    
    Returns:
        Field key as a Value object
        
    Raises:
        ValueError: If the identifier is not a simple single-field key
    """
    if not isinstance(identifier_node, comp.ast.Identifier):
        return _fail(f"Expected Identifier, got {type(identifier_node).__name__}")
    
    if len(identifier_node.kids) != 1:
        return _fail(f"Expected single field in identifier, got {len(identifier_node.kids)}")
    
    first_field = identifier_node.kids[0]
    
    # Handle ComputeField: [expr]
    if isinstance(first_field, comp.ast.ComputeField):
        if not first_field.expr:
            return _fail("ComputeField missing expression")
        return evaluate_func(first_field.expr, module, scopes)
    
    # Handle TokenField: simple_name
    if isinstance(first_field, comp.ast.TokenField):
        return _value.Value(first_field.value)
    
    # Handle String: "string name"
    if isinstance(first_field, comp.ast.String):
        return _value.Value(first_field.value)
    
    return _fail(f"Unsupported simple field type: {type(first_field).__name__}")


def assign_nested_field(identifier_node, field_value, target_dict, module, scopes, evaluate_func):
    """Assign a value to a nested field path, creating intermediate structures as needed.
    
    BUILD/WRITE MODE: Creates intermediate structures during construction.
    Handles nested paths like: account.active.flag = value
    Creates: account struct -> active struct -> flag field
    
    This is NOT the same as identifier lookup (READ mode). Here we CREATE missing
    intermediate fields; lookup would fail if they don't exist.
    
    All field keys are Value objects for consistency across TokenField, String, and ComputeField.
    
    Args:
        identifier_node: AST Identifier with multiple field nodes (e.g., account.active.flag)
        field_value: The Value to assign at the end of the path
        target_dict: The dict to start from (Value.struct dict with Value keys)
        module: Module context for evaluation
        scopes: Scope values dict
        evaluate_func: Function to call for evaluating expressions (e.g., _eval.evaluate)
    
    Returns:
        None (modifies target_dict in place)
        
    Raises:
        ValueError: If the path is invalid or contains unsupported field types
    """
    from . import _eval
    if not isinstance(identifier_node, comp.ast.Identifier):
        target_dict.clear()
        target_dict.update(_fail(f"Expected Identifier, got {type(identifier_node).__name__}").struct)
        return
    
    if len(identifier_node.kids) < 2:
        target_dict.clear()
        target_dict.update(_fail("Nested assignment requires at least 2 fields in path").struct)
        return 
    
    # Determine if we're starting from a scope
    first_field = identifier_node.kids[0]
    is_scoped = isinstance(first_field, comp.ast.ScopeField)
    
    if is_scoped:
        # Scoped nested assignments in function bodies are handled separately in _invoke.py
        target_dict.clear()
        target_dict.update(_fail("Scoped nested assignments should be handled by caller").struct)
        return 
    
    # Determine which fields to walk and which is final
    walk_fields = identifier_node.kids[:-1]
    final_field = identifier_node.kids[-1]
    
    current_dict = target_dict
    
    # Walk through intermediate fields, creating structures as needed
    for field_node in walk_fields:
        field_key = _extract_single_field_key(field_node, current_dict, module, scopes, evaluate_func)
        if _eval.is_failure(field_key):
            target_dict.clear()
            target_dict.update(field_key.struct)
            return
        
        if field_key in current_dict:
            # Field exists, navigate into it
            current_value = current_dict[field_key]
            
            # Check if we need to navigate into or replace the value
            if not current_value.is_struct or current_value.struct is None:
                # Need to replace with a struct
                new_struct = _value.Value(None)
                new_struct.struct = {}
                current_dict[field_key] = new_struct
                current_dict = new_struct.struct
            else:
                # Navigate into existing struct
                current_dict = current_value.struct
        else:
            # Create new intermediate structure
            new_struct = _value.Value(None)
            new_struct.struct = {}
            current_dict[field_key] = new_struct
            current_dict = new_struct.struct
    
    # Set the final field
    final_key = _extract_single_field_key(final_field, current_dict, module, scopes, evaluate_func)
    if not isinstance(final_key, _value.Unnamed) and _eval.is_failure(final_key):
        target_dict.clear()
        target_dict.update(final_key.struct)
        return

    current_dict[final_key] = field_value


def _extract_single_field_key(field_node, current_dict, module, scopes, evaluate_func):
    """Extract a field key from a single field node.
    
    Helper for assign_nested_field to handle different field types.
    All keys are returned as Value objects for consistency.
    
    Args:
        field_node: AST field node (TokenField, String, IndexField, ComputeField)
        current_dict: Current dict context (for IndexField lookups)
        module: Module context
        scopes: Scope values dict
        evaluate_func: Function for evaluating expressions
    
    Returns:
        Field key as a Value object
    """
    if isinstance(field_node, comp.ast.TokenField):
        return _value.Value(field_node.value)
    
    elif isinstance(field_node, comp.ast.String):
        return _value.Value(field_node.value)
    
    elif isinstance(field_node, comp.ast.IndexField):
        # Index field: get the Nth key from current dict
        index = field_node.value
        if not current_dict:
            return _fail("Cannot index empty struct in assignment")
        
        if not (0 <= index < len(current_dict)):
            return _fail(f"Index #{index} out of bounds (struct has {len(current_dict)} fields)")
        
        keys_list = list(current_dict)
        return keys_list[index]
    
    elif isinstance(field_node, comp.ast.ComputeField):
        # Computed field: evaluate expression to get key
        if not field_node.expr:
            return _fail("ComputeField missing expression")
        
        return evaluate_func(field_node.expr, module, scopes)
    
    else:
        return _fail(f"Unsupported field type in nested assignment: {type(field_node).__name__}")




def _fail(msg):
    """Helper to create an operator failure value."""
    from . import builtin
    return _value.Value({
        _value.Unnamed(): builtin.fail_runtime,
        "message": msg,
    })
