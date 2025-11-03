"""Tag related features"""

__all__ = [
    "TagRef",
    "get_tag_children",
    "get_tag_immediate_children",
    "get_tag_parents",
    "get_tag_natural_parents",
    "get_tag_root",
]


class TagRef:
    """A tag reference value that points to a TagDefinition.

    TagRefs must be created from a TagDefinition - they are runtime references
    to tags defined in modules. This ensures all tags have proper definitions
    and are properly scoped.

    Attributes:
        tag_def: Reference to the TagDefinition
    """

    def __init__(self, tag_def):
        """Create a tag reference from a TagDefinition.

        Args:
            tag_def: A TagDefinition object from a module
        """
        self.tag_def = tag_def

    @property
    def full_name(self) -> str:
        """Get the full hierarchical name (e.g., 'fail.syntax')."""
        return self.tag_def.full_name

    @property
    def value(self):
        """Get the associated value from the tag definition (if any)."""
        return self.tag_def.value

    def __repr__(self):
        return f"#{self.full_name}" if self.tag_def else "#<placeholder>"

    def __eq__(self, other):
        if not isinstance(other, TagRef):
            return False
        # Compare by full name for identity
        return self.full_name == other.full_name

    def __hash__(self):
        return hash(self.full_name)


def is_tag_compatible(input_tag_def, field_tag_def):
    """Check if an input tag is compatible with a field's tag type.

    Compatible means the input tag is either:
    - The same tag as the field's tag type
    - A child (descendant) of the field's tag type (within same module)
    - Extends the field's tag type (across modules via extends_def)
    - A child of a tag that extends the field's tag type

    Args:
        input_tag_def: TagDefinition of the input tag value
        field_tag_def: TagDefinition of the field's tag type constraint

    Returns:
        True if input tag is compatible with field tag type

    Examples:
        #timeout.error compatible with #error (child in same module)
        #error compatible with #error (same)
        #database.fail/sqlite compatible with #fail/builtin (extends + child)
        #success NOT compatible with #error (different hierarchy)
    """
    # Same tag definition - always compatible
    if input_tag_def is field_tag_def:
        return True
    
    # Check if input tag extends the field tag (directly or transitively)
    # Walk up the extends chain
    current = input_tag_def
    visited = set()  # Prevent infinite loops
    while current is not None:
        if id(current) in visited:
            break
        visited.add(id(current))
        
        # Check if current extends field_tag_def
        if current.extends_def is not None:
            if current.extends_def is field_tag_def:
                return True
            # Continue up the extends chain
            current = current.extends_def
        else:
            # No more extends relationships
            break
    
    # Check within-module hierarchy (path-based)
    # Only applies if tags are in the same module
    if input_tag_def.module is field_tag_def.module:
        # Check if input is a child of field's tag (field's path is a prefix)
        if len(field_tag_def.path) >= len(input_tag_def.path):
            return False
        
        # Compare prefixes - field's path should be a prefix of input's path
        return input_tag_def.path[:len(field_tag_def.path)] == field_tag_def.path
    
    # Check if input's parent (in same module) is compatible
    # This handles cases like #database.fail/sqlite where #fail/sqlite extends #fail/builtin
    if input_tag_def.parent_def is not None:
        return is_tag_compatible(input_tag_def.parent_def, field_tag_def)
    
    return False


def get_tag_immediate_children(tag_def):
    """Get immediate children of a tag within its module.

    Returns tags that have this tag as their parent_def (direct children only).

    Args:
        tag_def: TagDefinition to get children of

    Returns:
        list: List of TagDefinition objects that are immediate children
    """
    children = []
    for other_tag in tag_def.module.tags.values():
        if other_tag.parent_def is tag_def:
            children.append(other_tag)
    return children


def get_tag_children(tag_def):
    """Get all descendants of a tag within its module (recursive).

    Returns all tags in the same module that have this tag as an ancestor
    in their parent_def chain.

    Args:
        tag_def: TagDefinition to get descendants of

    Returns:
        list: List of TagDefinition objects that are descendants
    """
    descendants = []
    
    def collect_descendants(parent):
        for child in get_tag_immediate_children(parent):
            descendants.append(child)
            collect_descendants(child)  # Recurse
    
    collect_descendants(tag_def)
    return descendants


def get_tag_natural_parents(tag_def):
    """Get the chain of natural parents within the same module.

    Follows parent_def upward to the root, returning the chain from
    immediate parent to root.

    Args:
        tag_def: TagDefinition to get natural parents of

    Returns:
        list: List of TagDefinition objects from immediate parent to root
    """
    parents = []
    current = tag_def.parent_def
    visited = set()  # Prevent infinite loops
    
    while current is not None:
        if id(current) in visited:
            break
        visited.add(id(current))
        parents.append(current)
        current = current.parent_def
    
    return parents


def get_tag_parents(tag_def):
    """Get all parents including both natural hierarchy and extends chain.

    Returns tags in the order:
    1. Natural parents (parent_def chain within module)
    2. Extended tag (extends_def) of the tag and all its natural parents
    3. Extended tag's natural parents
    4. Extended tag's extended parents (recursive)

    Args:
        tag_def: TagDefinition to get all parents of

    Returns:
        list: List of TagDefinition objects representing the full parent chain
    """
    parents = []
    visited = set()  # Prevent infinite loops
    
    # Helper to collect all parents including extends for a given tag
    def collect_all_parents(tag):
        # Add natural parents
        natural = get_tag_natural_parents(tag)
        for parent in natural:
            if id(parent) not in visited:
                visited.add(id(parent))
                parents.append(parent)
        
        # Follow extends chain from this tag
        current = tag.extends_def
        while current is not None:
            if id(current) in visited:
                break
            visited.add(id(current))
            
            # Add the extended tag
            parents.append(current)
            
            # Add its natural parents
            for nat_parent in get_tag_natural_parents(current):
                if id(nat_parent) not in visited:
                    visited.add(id(nat_parent))
                    parents.append(nat_parent)
            
            # Continue up extends chain
            current = current.extends_def
        
        # Also follow extends chain from natural parents
        for parent in natural:
            if parent.extends_def is not None and id(parent.extends_def) not in visited:
                collect_all_parents(parent)
    
    collect_all_parents(tag_def)
    return parents


def get_tag_root(tag_def):
    """Get the root tag in the natural hierarchy within the same module.

    Follows parent_def chain upward until reaching a tag with no parent.
    Does not follow extends_def (cross-module relationships).

    Args:
        tag_def: TagDefinition to get root of

    Returns:
        TagDefinition: The root tag in the natural hierarchy (may be tag_def itself if it's already a root)
    """
    current = tag_def
    visited = set()  # Prevent infinite loops
    
    while current.parent_def is not None:
        if id(current) in visited:
            break
        visited.add(id(current))
        current = current.parent_def
    
    return current

