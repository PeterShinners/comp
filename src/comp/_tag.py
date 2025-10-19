"""Tag related features"""

__all__ = ["TagRef"]


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
    - A child (descendant) of the field's tag type

    Args:
        input_tag_def: TagDefinition of the input tag value
        field_tag_def: TagDefinition of the field's tag type constraint

    Returns:
        True if input tag is compatible with field tag type

    Examples:
        #timeout.error compatible with #error (child)
        #error compatible with #error (same)
        #network.error compatible with #error (child)
        #success NOT compatible with #error (different hierarchy)
    """
    # Same tag - always compatible
    if input_tag_def.path == field_tag_def.path:
        return True

    # Check if input is a child of field's tag (field's path is a prefix)
    if len(field_tag_def.path) >= len(input_tag_def.path):
        return False

    # Compare prefixes - field's path should be a prefix of input's path
    return input_tag_def.path[:len(field_tag_def.path)] == field_tag_def.path

