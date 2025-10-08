"""Tag types and operations."""

__all__ = ["TagValue", "TagDef", "is_parent_or_equal", "build_tags"]

import comp


class TagValue:
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
    def __init__(self, identifier, namespace, value=None):
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


def is_parent_or_equal(parent, child):
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


class TagDef:
    """Tag definition - immutable, belongs to defining module."""
    def __init__(self, identifier, namespace="main"):
        self.identifier = identifier
        self.name = ".".join(identifier)
        self.namespace = namespace
        self.value = None
        self._value_expr = None
        self._resolved = False
        # Create the TagValue once for identity-based comparison
        self.tag_value = TagValue(identifier, namespace)

    def resolve(self, module):
        """Resolve tag value expression."""
        if self._resolved:
            return

        if self._value_expr:
            from . import _eval  # local import untangles circular
            self.value = _eval.evaluate(self._value_expr, module)

        self._resolved = True

    def __repr__(self):
        if self.value is not None:
            return f"TagDef(#{self.name} = {self.value!r})"
        return f"TagDef(#{self.name})"


def build_tags(module, namespace):
    """Extract all tag definitions from a module and build explicit TagValue objects.

    Creates a flat list of all tags including:
    - Root tags from TagDef nodes
    - Nested tags from TagBody children
    - Implicit parent tags (e.g., #status from #status.active)

    Args:
        module: Parsed Module AST
        namespace: Namespace identifier for these tags (default: "main")

    Returns:
        List of TagValue objects with unique identifiers

    Examples:
        >>> import comp
        >>> mod = comp.parse_module("!tag #status.active")
        >>> tags = build_tags(mod)
        >>> [t.name for t in tags]
        ['#status', '#status.active']
    """
    tags_dict = {}

    # Walk module to find all TagDef nodes
    for stmt in module.statements:
        if isinstance(stmt, comp.ast.TagDef):
            _extract_tag_definition(stmt, tags_dict, namespace)

    # Return sorted list for deterministic output
    return sorted(tags_dict.values(), key=lambda t: t.name)


def _extract_tag_definition(tag_def, tags_dict, namespace):
    """Extract tags from a TagDef node and add to tags_dict.

    Args:
        tag_def: TagDef AST node
        tags_dict: Dictionary to accumulate tags (modified in place)
        namespace: Namespace identifier
    """
    # Create tag for this definition and all its implicit parents
    parent_path = tag_def.tokens
    _ensure_tag_hierarchy(parent_path, tags_dict, namespace)

    # Recursively extract tags from body children (relative to parent)
    body = tag_def.body
    if body:
        for child in body.kids:
            if isinstance(child, comp.ast.TagChild):
                _extract_tag_child(child, parent_path, tags_dict, namespace)


def _extract_tag_child(tag_child, parent_path, tags_dict, namespace):
    """Extract tags from a TagChild node and add to tags_dict.

    Tag children are relative to their parent path. Tokens are stored left-to-right (root-first).
    For example, if parent is ["status"] and child is ["active"],
    the full path is ["status", "active"] representing #status.active.

    Args:
        tag_child: TagChild AST node
        parent_path: Parent tag path (e.g., ["status"])
        tags_dict: Dictionary to accumulate tags (modified in place)
        namespace: Namespace identifier
    """
    # Child paths are relative to parent - parent comes first (left-to-right storage)
    child_tokens = tag_child.tokens
    full_path = parent_path + child_tokens  # parent.child format

    # Create hierarchy for child (ensures all parents exist)
    _ensure_tag_hierarchy(full_path, tags_dict, namespace)

    # Recursively extract tags from nested body
    body = tag_child.body
    if body:
        for nested_child in body.kids:
            if isinstance(nested_child, comp.ast.TagChild):
                _extract_tag_child(nested_child, full_path, tags_dict, namespace)


def _ensure_tag_hierarchy(identifier, tags_dict, namespace):
    """Ensure a tag and all its parent tags exist in tags_dict.

    Tokens are stored left-to-right (root-first).
    For example, given identifier ["status", "active"],
    ensures these tags exist:
    - #status (["status"])
    - #status.active (["status", "active"])

    Args:
        identifier: Tag path components left-to-right (e.g., ["status", "active"])
        tags_dict: Dictionary to accumulate tags (modified in place)
        namespace: Namespace identifier
    """
    # Create all parent paths from left to right
    # For ["status", "active"], create: ["status"], then ["status", "active"]
    for i in range(1, len(identifier) + 1):
        path = identifier[:i]
        _add_tag(path, tags_dict, namespace)


def _add_tag(identifier, tags_dict, namespace):
    """Add a single tag to tags_dict if it doesn't already exist.

    Args:
        identifier: Tag path components (e.g., ["status", "active"])
        tags_dict: Dictionary to accumulate tags (modified in place)
        namespace: Namespace identifier
    """
    key = ".".join(identifier)

    if key not in tags_dict:
        tags_dict[key] = TagValue(
            identifier=identifier,
            namespace=namespace,
            value=None  # Ignoring values for now
        )
