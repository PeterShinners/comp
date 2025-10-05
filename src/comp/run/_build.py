"""Build runtime structures from AST nodes."""

__all__ = ["build_tags"]

from typing import Any

from .. import ast
from . import _tag


def build_tags(module: ast.Module, namespace: str = "main") -> list[_tag.Tag]:
    """Extract all tag definitions from a module and build explicit Tag objects.

    Creates a flat list of all tags including:
    - Root tags from TagDefinition nodes
    - Nested tags from TagBody children
    - Implicit parent tags (e.g., #status from #status.active)

    Args:
        module: Parsed Module AST
        namespace: Namespace identifier for these tags (default: "main")

    Returns:
        List of Tag objects with unique identifiers

    Examples:
        >>> import comp
        >>> mod = comp.parse_module("!tag #status.active")
        >>> tags = build_tags(mod)
        >>> [t.name for t in tags]
        ['#status', '#status.active']
    """
    tags_dict: dict[str, _tag.Tag] = {}

    # Walk module to find all TagDefinition nodes
    for stmt in module.statements:
        if isinstance(stmt, ast.TagDefinition):
            _extract_tag_definition(stmt, tags_dict, namespace)

    # Return sorted list for deterministic output
    return sorted(tags_dict.values(), key=lambda t: t.name)


def _extract_tag_definition(tag_def: ast.TagDefinition, tags_dict: dict[str, _tag.Tag], namespace: str):
    """Extract tags from a TagDefinition node and add to tags_dict.

    Args:
        tag_def: TagDefinition AST node
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
            if isinstance(child, ast.TagChild):
                _extract_tag_child(child, parent_path, tags_dict, namespace)


def _extract_tag_child(tag_child: ast.TagChild, parent_path: list[str], tags_dict: dict[str, _tag.Tag], namespace: str):
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
            if isinstance(nested_child, ast.TagChild):
                _extract_tag_child(nested_child, full_path, tags_dict, namespace)


def _ensure_tag_hierarchy(identifier: list[str], tags_dict: dict[str, _tag.Tag], namespace: str):
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


def _add_tag(identifier: list[str], tags_dict: dict[str, _tag.Tag], namespace: str):
    """Add a single tag to tags_dict if it doesn't already exist.

    Args:
        identifier: Tag path components (e.g., ["status", "active"])
        tags_dict: Dictionary to accumulate tags (modified in place)
        namespace: Namespace identifier
    """
    key = ".".join(identifier)

    if key not in tags_dict:
        tags_dict[key] = _tag.Tag(
            identifier=identifier,
            namespace=namespace,
            value=None  # Ignoring values for now
        )
