"""Namespace building and lookup for Comp modules."""

import comp


__all__ = ["DefinitionSet"]


def create_namespace(definitions, prefix):
    """Create namespace from definitions dict.

    Create a lookup namespace from definitions.
    If no namespace is given then this will include private definitions.

    Args:
        definitions: (dict) Mapping of qualified names to Definition objects
        prefix: (str | None) Optional namespace to prefix to definitions
    Returns:
        dict: Mapping of fully qualified names to Definitions, OverloadSet or Ambiguous
    """
    namespace = {}
    for qualified, definition in definitions.items():
        for name in _identifier_permutations(definition, prefix):
            if prefix and definition.private:
                continue
            defs = namespace.get(name)
            if defs is None:
                defs = namespace[name] = DefinitionSet()
            defs.definitions.add(definition)
    return namespace


def merge_namespace(base, overrides, clobber):
    """Merge two namespaces into a new resulting namespace.

    Args:
        base: (dict) Base namespace
        overrides: (dict) Namespace with overriding definitions
        clobber: (bool) New definitions replace previous ones
    Returns:
        dict: Mapping of fully qualified names to Definitions, OverloadSet or Ambiguous

    """
    result = dict(base)
    if clobber:
        result.update(overrides)

    else:
        for name, value in overrides.items():
            defs = result.get(name)
            if defs is None:
                defs = result[name] = DefinitionSet()
            defs.definitions.update(value.definitions)

    return result


class DefinitionSet:
    """Collection of definitions for a given qualified name.
    Attrs:
        definitions: (set) of at least one definition
    """
    def __init__(self):
        self.definitions = set()

    def __repr__(self):
        return f"<DefinitionSet x{len(self.definitions)}>"

    def scalar(self):
        """Get single definition if unambiguous or None."""
        if len(self.definitions) != 1:
            return None
        return next(iter(self.definitions))

    def shape(self):
        """Get single shape definition or None"""
        shapes = [d for d in self.definitions if d.shape is comp.shape_shape]
        if len(shapes) != 1:
            return None
        return shapes[0]

    def invokables(self):
        """Get all invokeable (blocks and/or a single shape) or empty list"""
        shapes = [d for d in self.definitions if d.shape is comp.shape_shape]
        blocks = [d for d in self.definitions if d.shape is comp.shape_block]
        if len(shapes) > 1:
            return None
        if len(blocks) + len(shapes) != len(self.definitions):
            return None
        return shapes + blocks


def _identifier_permutations(definition, prefix):
    """Generate lookup name permutations from a Definition.

    For auto-suffixed identifiers like "tree-contains.i001":
    - Generates "tree-contains.i001" (full qualified name)
    - Generates "tree-contains" (base name without suffix)
    - Skips the bare suffix "i001"

    This allows both "tree-contains" and "tree-contains.i001" to resolve.

    Args:
        definition: Definition object with qualified name and auto_suffix flag
        prefix: Optional namespace prefix to add

    Returns:
        list: List of permutation strings to add to namespace
    """
    permutations = []
    qualified = definition.qualified
    parts = qualified.split('.')
    if prefix:
        parts.insert(0, prefix)

    # Generate all suffix permutations
    for i in range(len(parts)):
        name = '.'.join(parts[i:])
        # Skip if this is just the bare auto-generated suffix
        if definition.auto_suffix and i == len(parts) - 1:
            continue
        permutations.append(name)

    # If we have an auto-generated suffix, also add the base name without it
    # e.g., "tree-contains.i001" also generates "tree-contains"
    if definition.auto_suffix and len(parts) > 1:
        base_parts = parts[:-1]
        for i in range(len(base_parts)):
            base_name = '.'.join(base_parts[i:])
            if base_name not in permutations:
                permutations.append(base_name)

    return permutations
