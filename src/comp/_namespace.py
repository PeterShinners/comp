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
        for name in _identifier_permutations(qualified, prefix):
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


def _identifier_permutations(qualified, prefix):
    """Generate lookup name permutations."""
    permutations = []
    parts = qualified.split('.')
    if prefix:
        parts.insert(0, prefix)
    for i in range(len(parts)):
        permutations.append('.'.join(parts[i:]))
    return permutations
