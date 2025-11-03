"""Tests for tag hierarchy functions."""

import comp


def test_immediate_children():
    """Test getting immediate children of a tag."""
    module = comp.Module()
    
    # Define a tag hierarchy: #status, #status.error, #status.error.timeout, #status.success
    status_def = module.define_tag(["status"])
    error_def = module.define_tag(["status", "error"])
    timeout_def = module.define_tag(["status", "error", "timeout"])
    success_def = module.define_tag(["status", "success"])
    
    # Get immediate children of #status
    children = comp.get_tag_immediate_children(status_def)
    assert len(children) == 2
    assert error_def in children
    assert success_def in children
    assert timeout_def not in children  # Not immediate
    
    # Get immediate children of #status.error
    children = comp.get_tag_immediate_children(error_def)
    assert len(children) == 1
    assert timeout_def in children
    
    # Leaf tag has no children
    children = comp.get_tag_immediate_children(timeout_def)
    assert len(children) == 0


def test_all_children():
    """Test getting all descendants of a tag."""
    module = comp.Module()
    
    # Define a tag hierarchy
    status_def = module.define_tag(["status"])
    error_def = module.define_tag(["status", "error"])
    timeout_def = module.define_tag(["status", "error", "timeout"])
    network_def = module.define_tag(["status", "error", "network"])
    success_def = module.define_tag(["status", "success"])
    
    # Get all descendants of #status
    descendants = comp.get_tag_children(status_def)
    assert len(descendants) == 4
    assert error_def in descendants
    assert timeout_def in descendants
    assert network_def in descendants
    assert success_def in descendants
    
    # Get all descendants of #status.error
    descendants = comp.get_tag_children(error_def)
    assert len(descendants) == 2
    assert timeout_def in descendants
    assert network_def in descendants
    assert success_def not in descendants


def test_natural_parents():
    """Test getting natural parents within same module."""
    module = comp.Module()
    
    # Define a tag hierarchy
    status_def = module.define_tag(["status"])
    error_def = module.define_tag(["status", "error"])
    timeout_def = module.define_tag(["status", "error", "timeout"])
    
    # Get natural parents of #status.error.timeout
    parents = comp.get_tag_natural_parents(timeout_def)
    assert len(parents) == 2
    assert parents[0] is error_def  # Immediate parent first
    assert parents[1] is status_def  # Root last
    
    # Get natural parents of #status.error
    parents = comp.get_tag_natural_parents(error_def)
    assert len(parents) == 1
    assert parents[0] is status_def
    
    # Root tag has no natural parents
    parents = comp.get_tag_natural_parents(status_def)
    assert len(parents) == 0


def test_all_parents_with_extends():
    """Test getting all parents including extends chain."""
    # Create builtin module with base tags
    builtin = comp.Module()
    fail_def = builtin.define_tag(["fail"])
    error_def = builtin.define_tag(["fail", "error"])
    
    # Create app module that extends builtin tags
    app = comp.Module()
    app.namespaces["builtin"] = builtin
    
    # Define #database that extends #fail from builtin
    database_def = app.define_tag(["database"])
    database_def.extends_def = fail_def
    
    # Define #database.timeout (child of #database)
    timeout_def = app.define_tag(["database", "timeout"])
    
    # Get all parents of #database.timeout
    parents = comp.get_tag_parents(timeout_def)
    
    # Should include:
    # 1. Natural parent: #database
    # 2. Extended parent: #fail (from builtin)
    assert len(parents) >= 2
    assert database_def in parents
    assert fail_def in parents
    
    # Get all parents of #database
    parents = comp.get_tag_parents(database_def)
    assert len(parents) == 1
    assert fail_def in parents


def test_parents_empty_for_root():
    """Test that root tags with no extends have no parents."""
    module = comp.Module()
    root_def = module.define_tag(["root"])
    
    parents = comp.get_tag_parents(root_def)
    assert len(parents) == 0


def test_extends_chain():
    """Test following extends chain across multiple modules."""
    # Module A has base tag
    mod_a = comp.Module()
    base_def = mod_a.define_tag(["base"])
    
    # Module B extends A's tag
    mod_b = comp.Module()
    derived_def = mod_b.define_tag(["derived"])
    derived_def.extends_def = base_def
    
    # Module C extends B's tag
    mod_c = comp.Module()
    further_def = mod_c.define_tag(["further"])
    further_def.extends_def = derived_def
    
    # Get all parents of further
    parents = comp.get_tag_parents(further_def)
    assert len(parents) == 2
    assert derived_def in parents
    assert base_def in parents


def test_get_root():
    """Test getting the root tag of a hierarchy."""
    module = comp.Module()
    
    # Define a tag hierarchy
    status_def = module.define_tag(["status"])
    error_def = module.define_tag(["status", "error"])
    timeout_def = module.define_tag(["status", "error", "timeout"])
    
    # Get root of deep tag
    root = comp.get_tag_root(timeout_def)
    assert root is status_def
    
    # Get root of middle tag
    root = comp.get_tag_root(error_def)
    assert root is status_def
    
    # Root tag's root is itself
    root = comp.get_tag_root(status_def)
    assert root is status_def


def test_get_root_with_extends():
    """Test that get_root only follows natural hierarchy, not extends."""
    # Create builtin module with base tags
    builtin = comp.Module()
    fail_def = builtin.define_tag(["fail"])
    
    # Create app module that extends builtin tag
    app = comp.Module()
    database_def = app.define_tag(["database"])
    database_def.extends_def = fail_def
    
    timeout_def = app.define_tag(["database", "timeout"])
    
    # Root should be database (natural parent), not fail (extended parent)
    root = comp.get_tag_root(timeout_def)
    assert root is database_def
    
    # database's root is itself
    root = comp.get_tag_root(database_def)
    assert root is database_def


def test_python_functions_exposed():
    """Test that tag functions are properly exposed in comp namespace."""
    # Just verify the functions are accessible
    assert hasattr(comp, 'get_tag_children')
    assert hasattr(comp, 'get_tag_immediate_children')
    assert hasattr(comp, 'get_tag_parents')
    assert hasattr(comp, 'get_tag_natural_parents')
    assert hasattr(comp, 'get_tag_root')
    
    # Verify they work with actual tags
    module = comp.Module()
    root = module.define_tag(["root"])
    child = module.define_tag(["root", "child"])
    
    # Test exposed functions
    children = comp.get_tag_children(root)
    assert len(children) == 1
    assert children[0] is child
    
    parents = comp.get_tag_natural_parents(child)
    assert len(parents) == 1
    assert parents[0] is root
    
    # Test get_root
    tag_root = comp.get_tag_root(child)
    assert tag_root is root
