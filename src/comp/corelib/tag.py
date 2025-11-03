"""Tag hierarchy and relationship operations.

Functions for navigating tag hierarchies both within modules (natural parents)
and across modules (extended parents via extends).
"""

import comp


def create_module():
    """Create the tag stdlib module.
    
    Returns:
        comp.Module: Module with tag hierarchy functions
    """
    module = comp.Module(module_id="stdlib.tag")
    
    # Define all tag functions
    functions = (
        _immediate_children,
        _children,
        _natural_parents,
        _parents,
        _root,
    )
    
    for py_func in functions:
        name = py_func.__name__[1:].replace('_', '-')  # Remove leading underscore and replace _ with -
        py_function = comp.PythonFunction(name, py_func)
        module.define_function(
            path=[name],
            body=py_function,
            doc=py_func.__doc__,
        )
    
    return module


def _extract_tag(input_value):
    """Extract a TagDefinition from input value.
    
    Args:
        input_value: Value that should contain a tag
        
    Returns:
        tuple: (TagDefinition, error_message) - error_message is None on success
    """
    # Unwrap to scalar if needed
    input_value = input_value.as_scalar()
    
    # Check if it's a tag
    if not input_value.is_tag:
        return None, f"Expected tag, got {type(input_value.data).__name__}"
    
    # Extract TagRef and get TagDefinition
    tag_ref = input_value.data
    if not isinstance(tag_ref, comp.TagRef):
        return None, f"Invalid tag reference: {type(tag_ref).__name__}"
    
    return tag_ref.tag_def, None


def _immediate_children(frame, input_value, args_value=None):
    """Get immediate children of a tag."""
    if False:  # Make this a generator
        yield
    
    tag_def, error = _extract_tag(input_value)
    if error:
        return comp.fail(error)
    
    children = comp.get_tag_immediate_children(tag_def)
    
    # Convert list of TagDefinitions to list of TagRefs wrapped in Values
    result = []
    for child in children:
        tag_ref = comp.TagRef(child)
        result.append(comp.Value(tag_ref))
    
    return comp.Value(result)


def _children(frame, input_value, args_value=None):
    """Get all descendants of a tag (recursive)."""
    if False:  # Make this a generator
        yield
    
    tag_def, error = _extract_tag(input_value)
    if error:
        return comp.fail(error)
    
    children = comp.get_tag_children(tag_def)
    
    # Convert list of TagDefinitions to list of TagRefs wrapped in Values
    result = []
    for child in children:
        tag_ref = comp.TagRef(child)
        result.append(comp.Value(tag_ref))
    
    return comp.Value(result)


def _natural_parents(frame, input_value, args_value=None):
    """Get the chain of natural parents within the same module."""
    if False:  # Make this a generator
        yield
    
    tag_def, error = _extract_tag(input_value)
    if error:
        return comp.fail(error)
    
    parents = comp.get_tag_natural_parents(tag_def)
    
    # Convert list of TagDefinitions to list of TagRefs wrapped in Values
    result = []
    for parent in parents:
        tag_ref = comp.TagRef(parent)
        result.append(comp.Value(tag_ref))
    
    return comp.Value(result)


def _parents(frame, input_value, args_value=None):
    """Get all parents including both natural hierarchy and extends chain."""
    if False:  # Make this a generator
        yield
    
    tag_def, error = _extract_tag(input_value)
    if error:
        return comp.fail(error)
    
    parents = comp.get_tag_parents(tag_def)
    
    # Convert list of TagDefinitions to list of TagRefs wrapped in Values
    result = []
    for parent in parents:
        tag_ref = comp.TagRef(parent)
        result.append(comp.Value(tag_ref))
    
    return comp.Value(result)


def _root(frame, input_value, args_value=None):
    """Get the root tag in the natural hierarchy."""
    if False:  # Make this a generator
        yield
    
    tag_def, error = _extract_tag(input_value)
    if error:
        return comp.fail(error)
    
    root = comp.get_tag_root(tag_def)
    
    # Convert TagDefinition to TagRef wrapped in Value
    tag_ref = comp.TagRef(root)
    
    return comp.Value(tag_ref)
