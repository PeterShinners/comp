"""Tag types and operations."""

__all__ = ["Tag", "is_parent_or_equal"]


class Tag:
    """Tag value in Comp.

    Tags use identity-based equality (default Python object equality).
    This is important for builtin tags like #true and #false which should
    be singleton instances - comparison operators will return the exact
    same Tag instance, not a new tag with the same name.

    TODO: When implementing comparison operators and tag references:
      - Ensure builtin tags remain singletons across module boundaries
      - Tag equality is based on instance identity, not name/namespace
      - Module resolution must return references to tag definitions,
        not create new Tag instances
    """
    __slots__ = ("name", "identifier", "namespace", "value")
    def __init__(self, identifier: list[str], namespace: str, value: "Value | None" = None):
        self.name = "#" + ".".join(identifier)
        self.identifier = identifier
        self.namespace = namespace
        self.value = value

    def __repr__(self):
        if self.namespace == "builtin":
            return f"{self.name}"
        else:
            return f"{self.name}/{self.namespace}"

    # NOTE: No __eq__ defined - uses identity equality (is)
    # This ensures builtin tags like #true and #false are singletons
    # def __hash__(self):
    #     return hash((self.name, self.namespace))


def is_parent_or_equal(parent: Tag, child: Tag) -> int:
    """Check hierarchical relationship between tags and return distance.

    Tags must be from the same namespace to have a parent-child relationship.

    Returns:
        -1: No parent-child relationship (different branches or namespaces)
         0: Tags are equal (same tag)
         1: Immediate parent (parent is direct parent of child)
         2: Grandparent (2 steps up)
         n: n steps up in hierarchy

    Examples:
        #status compared to #status → 0 (equal)
        #status compared to #error.status → 1 (immediate parent)
        #status compared to #timeout.error.status → 2 (grandparent)
        #error.status compared to #timeout.error.status → 1 (immediate parent)
        #status compared to #active → -1 (different branches)
        #status/main compared to #error.status/other → -1 (different namespaces)

    Args:
        parent: Potential parent or ancestor tag
        child: Potential child or descendant tag

    Returns:
        Integer indicating hierarchical distance, or -1 if no relationship
    """
    # Tags from different namespaces are never in the same hierarchy
    if parent.namespace != child.namespace:
        return -1

    # Check if parent's identifier is a prefix of child's identifier
    # For example: ["status"] is prefix of ["status", "error", "timeout"]
    if len(parent.identifier) > len(child.identifier):
        return -1

    # Check each component matches
    for i, component in enumerate(parent.identifier):
        if child.identifier[i] != component:
            return -1

    # Return the number of steps between them
    # If equal: len(child) - len(parent) = 0
    # If immediate parent: len(child) - len(parent) = 1
    # If grandparent: len(child) - len(parent) = 2, etc.
    return len(child.identifier) - len(parent.identifier)

