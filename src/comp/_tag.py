"""Tag definitions and operations"""

import comp


__all__ = ["Tag", "tag_nil", "tag_bool", "tag_true", "tag_false", "tag_fail", "create_tagdef"]


class Tag:
    """A tag definition.

    Tags are lightweight identifiers used to represent various states,
    types, or conditions in the comp language. They are often used for
    error handling, type tagging, and control flow.

    Args:
        qualified: (str) Fully qualified tag name
        private: (bool) Tag is private to its module

    Attributes:
        qualified: (str) Fully qualified tag name
        private: (bool) Tag is private to its module
        module: (Module | None) The module that defined this tag
    """

    __slots__ = ("qualified", "private", "module")

    def __init__(self, qualified, private):
        self.qualified = qualified
        self.module = None
        self.private = private

    def __repr__(self):
        return f"Tag<{self.qualified}>"

    def __hash__(self):
        return hash((self.qualified, self.module))


tag_nil = Tag("nil", False)
tag_bool = Tag("bool", False)
tag_true = Tag("bool.true", False)
tag_false = Tag("bool.false", False)
tag_fail = Tag("fail", False)


def create_tagdef(qualified_name, private, cop_node, parent_tag=None):
    """Create a Tag from a value.tag COP node and wrap in a Value.

    This is a pure initialization function that doesn't depend on Module or Interp.

    Args:
        qualified_name: (str) Fully qualified tag name (e.g., "server.status.ok")
        private: (bool) Whether tag is private
        cop_node: (Struct) The value.tag COP node
        parent_tag: (Tag | None) Parent tag for hierarchical tags

    Returns:
        Value: Initialized tag definition wrapped in a Value with cop attribute set

    Raises:
        CodeError: If cop_node is not a value.tag node
    """
    # Validate node type
    tag_value = cop_node.positional(0)
    tag = tag_value.data if hasattr(tag_value, 'data') else tag_value

    if not isinstance(tag, comp.Tag) or tag.qualified != "value.tag":
        raise comp.CodeError(
            f"Expected value.tag node, got {tag.qualified if isinstance(tag, comp.Tag) else type(tag)}",
            cop_node
        )

    # Create Tag
    tag_def = Tag(qualified_name, private)

    # TODO: Handle hierarchical tags and child tags from cop_node
    # For now, just create the basic definition

    # Wrap in Value and set cop attribute
    value = comp.Value.from_python(tag_def)
    value.cop = cop_node

    return value
