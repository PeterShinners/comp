"""Tag definitions and operations"""

import comp


__all__ = [
    "TagDef", "Tag", 
    "tag_bool", "tag_true", "tag_false", "tag_fail"]


class TagDef:
    """A tag definition.

    Tags are lightweight identifiers used to represent various states,
    types, or conditions in the comp language. They are often used for
    error handling, type tagging, and control flow.

    Args:
        name: (str) The name of the tag

    Attributes:
        qualified: (str) Fully qualified tag name
        private: (bool) Tag is private to its module
    """
    __slots__ = ("qualified", "private", "module")

    def __init__(self, qualified, private):
        self.qualified = qualified
        self.module = None
        self.private = private

    def __repr__(self):
        return f"TagDef<{self.qualified}>"

    def __hash__(self):
        return hash((self.qualified, self.module))


class Tag:
    """Reference to a Tag definition.

    To use a tag as a value there must be a reference to its definition.
    The reference stores additional information about where it came from
    and how it was named.

    When tags are referenced from a module they will be created with an
    anchor to the namespace that defined them. This allows for richer
    comparisons. Tags generated at runtime (like serialized data) have
    no anchor, and an only be used more simply (and suspiciously)
    
    Args:
        qualified: (str) Fully qualified name of the tag (no '#' prefix)
        namespace: (str) The name of the namespace used to reference this tag
        anchor: (Namespace | None) The namespace that defines the viewable tags

    """
    __slots__ = ("qualified", "namespace", "anchor")

    def __init__(self, qualified, namespace, anchor):
        self.qualified = qualified
        self.namespace = namespace
        self.anchor = anchor

    def __repr__(self):
        return f"Tag(#{self.qualified}/{self.namespace})"


tag_bool = TagDef("bool", False)
tag_true = TagDef("bool.true", False)
tag_false = TagDef("bool.false", False)
tag_fail = TagDef("fail", False)
